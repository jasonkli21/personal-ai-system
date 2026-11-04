"""Default-off internal episode operations under a trusted host source lease.

A host must authenticate original workflow evidence and maintain monotonic source
rights. There is deliberately no production host or model-facing registration.
"""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from time import monotonic
from typing import Literal
from uuid import uuid4

from pydantic import Field

from personal_ai.auth.scope import current_request_scope, current_verified_principal
from personal_ai.contracts.delegated_tasks import canonical_bytes
from personal_ai.memory.episodes import (
    CandidateContract,
    TerminalStepCandidate,
    assess_terminal_steps,
)
from personal_ai.memory.knowledge import ProjectSnapshot, Strict
from personal_ai.memory.lifecycle.contracts import MemoryLifecycleEvent, MemoryLifecycleState
from personal_ai.memory.lifecycle.transition import transition


class EpisodeEvidence(Strict):
    """Host-resolved original evidence; never a model or HTTP input."""

    schema_version: Literal["episode-evidence-v1"] = "episode-evidence-v1"
    original_spec: bytes = Field(max_length=16384)
    receipt_envelope: bytes = Field(max_length=16384)
    scope_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    project: ProjectSnapshot
    observed_at: datetime
    expires_at: datetime
    classification: Literal["synthetic_public"]


class EpisodeRecord(Strict):
    schema_version: Literal["episode-v1"] = "episode-v1"
    candidate: TerminalStepCandidate
    project_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_at: datetime
    expires_at: datetime
    classification: Literal["synthetic_public"] = "synthetic_public"
    label: Literal["historical_observation_not_task_verification"] = (
        "historical_observation_not_task_verification"
    )


class EpisodeResult(CandidateContract):
    status: Literal[
        "disabled",
        "saved",
        "replayed",
        "found",
        "forgotten",
        "denied",
        "conflict",
        "capacity",
        "unavailable",
    ]
    items: tuple[EpisodeRecord, ...] = ()
    truncated: bool = False


def fingerprint(value):
    return sha256(canonical_bytes(value)).hexdigest()


class EpisodeService:
    """The host implements lease/project/resolve/current, all bounded to 2 seconds.

    resolve authenticates the original run/intent and original project binding.
    current checks exact source/branch/project and permission dependencies. lease
    fences their mutation through commit or return. Missing host fails closed.
    """

    def __init__(
        self,
        settings,
        repository,
        authority=None,
        *,
        capture=False,
        selection=False,
        profile=None,
        clock=None,
    ):
        self.settings, self.repository, self.authority = settings, repository, authority
        self.capture_enabled, self.selection_enabled = capture, selection
        self.profile = profile
        self.clock = clock or (lambda: datetime.now(UTC))

    @contextmanager
    def guard(self, project_id, *, capture=False, maintenance=False):
        scope, principal = current_request_scope(), current_verified_principal()
        enabled = True if maintenance else (self.capture_enabled if capture else self.selection_enabled)
        if not (
            enabled is True
            and self.profile == "synthetic_local"
            and self.settings.memory_enabled
            and self.settings.app_environment in {"local", "test"}
            and self.authority is not None
            and scope is not None
            and principal is not None
            and principal.authenticated
            and principal.owner_id == scope.owner_id
            and scope.acting_user_id == f"{principal.issuer}|{principal.subject}"
            and principal.audience
            and principal.authorized_party
            and principal.expires_at is not None
            and principal.expires_at > self.clock().timestamp()
        ):
            raise PermissionError
        started = monotonic()
        with self.authority.lease(scope, project_id):
            project = self.authority.project(scope, project_id)
            namespace = fingerprint(
                {
                    "owner": scope.owner_id,
                    "app": scope.application_id,
                    "workspace": scope.workspace_id,
                    "actor": scope.acting_user_id,
                    "audience": principal.audience,
                    "client": principal.authorized_party,
                    "project": project_id,
                    "purpose": "historical_episode_inspection",
                }
            )
            with self.repository.locked(scope.owner_id, namespace) as bucket:

                def check():
                    if (
                        monotonic() - started >= 2
                        or self.authority.project(scope, project_id) != project
                    ):
                        raise PermissionError

                check()
                yield scope, project, bucket, check
                check()

    def capture(self, project_id, run_id):
        if not self.capture_enabled:
            return EpisodeResult(status="disabled")
        try:
            with self.guard(project_id, capture=True) as (scope, project, bucket, check):
                evidence = EpisodeEvidence.model_validate(
                    self.authority.resolve(scope, project_id, run_id)
                )
                now = self.clock()
                if (
                    evidence.project != project
                    or not evidence.observed_at <= now < evidence.expires_at
                    or evidence.expires_at > evidence.observed_at + timedelta(days=30)
                ):
                    return EpisodeResult(status="denied")
                assessment = assess_terminal_steps(
                    evidence.original_spec,
                    evidence.receipt_envelope,
                    expected_scope_digest=evidence.scope_digest,
                )
                if not assessment.candidates or any(
                    c.run_id != run_id for c in assessment.candidates
                ):
                    return EpisodeResult(status="denied")
                records = tuple(
                    EpisodeRecord(
                        candidate=c,
                        project_digest=fingerprint(project.model_dump()),
                        observed_at=evidence.observed_at,
                        expires_at=evidence.expires_at,
                    )
                    for c in assessment.candidates
                )
                if any(len(r.model_dump_json().encode()) > 2048 for r in records):
                    return EpisodeResult(status="denied")
                key = str(run_id)
                digest = fingerprint([r.model_dump(mode="json") for r in records])
                prior = bucket["receipts"].get(key)
                if prior is not None:
                    return EpisodeResult(status="replayed" if prior == digest else "conflict")
                if len(bucket["states"]) + len(records) > 128 or len(bucket["receipts"]) >= 128:
                    return EpisodeResult(status="capacity")
                if not all(self.authority.current(scope, project, r) for r in records):
                    return EpisodeResult(status="denied")
                check()
                for record in records:
                    identity = str(record.candidate.id)
                    bucket["records"][identity] = record.model_dump(mode="json")
                    bucket["states"][identity] = MemoryLifecycleState(
                        owner_id=scope.owner_id,
                        memory_id=record.candidate.id,
                        application_id=scope.application_id,
                        workspace_id=scope.workspace_id,
                        scope_version=2,
                    ).model_dump(mode="json")
                bucket["receipts"][key] = digest
                return EpisodeResult(status="saved")
        except PermissionError:
            return EpisodeResult(status="denied")
        except Exception:  # noqa: BLE001 - a lost commit ACK is reconciled by capture's original run key
            return EpisodeResult(status="unavailable")

    def read(self, project_id, *, episode_id=None, limit=8):
        if not self.selection_enabled:
            return EpisodeResult(status="disabled")
        if type(limit) is not int or not 1 <= limit <= 8:
            return EpisodeResult(status="denied")
        try:
            with self.guard(project_id) as (scope, project, bucket, check):
                matches = []
                for key, value in bucket["records"].items():
                    check()
                    if episode_id is not None and key != str(episode_id):
                        continue
                    record = EpisodeRecord.model_validate(value)
                    state = MemoryLifecycleState.model_validate(bucket["states"][key])
                    if (
                        state.retrieval_status == "active"
                        and state.validity_epoch == 0
                        and record.expires_at > self.clock()
                        and record.project_digest == fingerprint(project.model_dump())
                        and self.authority.current(scope, project, record)
                    ):
                        matches.append(record)
                selected = tuple(matches[:limit])
                if not all(self.authority.current(scope, project, r) for r in selected):
                    raise PermissionError
                return EpisodeResult(
                    status="found" if episode_id is None or selected else "denied",
                    items=selected,
                    truncated=len(matches) > limit,
                )
        except Exception:  # noqa: BLE001 - exact guesses disclose no foreign existence
            return EpisodeResult(status="denied" if episode_id is not None else "unavailable")

    def forget(self, project_id, episode_id):
        """Explicit trusted-host operation, not a model tool. No source-current requirement."""
        try:
            with self.guard(project_id, maintenance=True) as (scope, _, bucket, check):
                key = str(episode_id)
                if key not in bucket["states"]:
                    return EpisodeResult(status="denied")
                state = MemoryLifecycleState.model_validate(bucket["states"][key])
                if state.retrieval_status == "active":
                    event = MemoryLifecycleEvent(
                        id=uuid4(),
                        owner_id=scope.owner_id,
                        memory_id=episode_id,
                        event_type="forgotten",
                        reason_code="host_explicit_forget",
                        policy_version="episode-retention-v1",
                        occurred_at=self.clock(),
                        idempotency_key=key,
                        expected_state_version=state.state_version,
                        application_id=scope.application_id,
                        workspace_id=scope.workspace_id,
                        scope_version=2,
                    )
                    bucket["states"][key] = transition(state, event).model_dump(mode="json")
                    bucket["events"][key] = event.model_dump(mode="json")
                bucket["records"].pop(key, None)
                check()
                return EpisodeResult(status="forgotten")
        except Exception:  # noqa: BLE001
            return EpisodeResult(status="denied")

    def purge(self, project_id):
        """Bounded payload-only expiry/source erasure; replay/state authority remains."""
        try:
            with self.guard(project_id, maintenance=True) as (scope, project, bucket, check):
                for key, value in tuple(bucket["records"].items()):
                    record = EpisodeRecord.model_validate(value)
                    if record.expires_at <= self.clock() or not self.authority.current(
                        scope, project, record
                    ):
                        del bucket["records"][key]
                check()
                return EpisodeResult(status="forgotten")
        except Exception:  # noqa: BLE001
            return EpisodeResult(status="unavailable")

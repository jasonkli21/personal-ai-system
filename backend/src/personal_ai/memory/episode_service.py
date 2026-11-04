"""Read-disabled episode projection with authenticated local erasure operations.

Capture and selection remain unavailable until source epochs and canonical memory
lifecycle integration are provided by trusted authorities.
"""

from contextlib import contextmanager
from datetime import UTC, datetime
from hashlib import sha256
from time import monotonic
from typing import Literal
from uuid import uuid4

from pydantic import Field

from personal_ai.auth.scope import current_request_scope, current_verified_principal
from personal_ai.contracts.delegated_tasks import canonical_bytes
from personal_ai.memory.episodes import CandidateContract, TerminalStepCandidate
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
    """Capture and selection are blocked pending issuer and lifecycle integration."""

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
            and (maintenance or self.settings.memory_enabled)
            and self.settings.app_environment in {"local", "test"}
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
                if monotonic() - started >= 2:
                    raise PermissionError

            check()
            # Maintenance uses the exact authenticated namespace only. It never
            # resolves a project or obtains source authority to disclose payload.
            yield scope, None, bucket, check
            check()

    def capture(self, project_id, run_id):
        # A boolean host option cannot supply monotonic issuer epochs or join the
        # canonical memory lifecycle. Keep the durable projection read-disabled.
        return EpisodeResult(status="disabled")

    def read(self, project_id, *, episode_id=None, limit=8):
        return EpisodeResult(status="disabled")

    def forget(self, project_id, episode_id):
        """Erase one exact authenticated local namespace without source lookup."""
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
        """Erase every payload in the exact authenticated project namespace."""
        try:
            with self.guard(project_id, maintenance=True) as (scope, _, bucket, check):
                for key in tuple(bucket["records"]):
                    state_raw = bucket["states"].get(key)
                    if state_raw is not None:
                        state = MemoryLifecycleState.model_validate(state_raw)
                        if state.retrieval_status == "active":
                            event = MemoryLifecycleEvent(
                                id=uuid4(),
                                owner_id=scope.owner_id,
                                memory_id=state.memory_id,
                                event_type="forgotten",
                                reason_code="host_source_purge",
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
                    del bucket["records"][key]
                check()
                return EpisodeResult(status="forgotten")
        except Exception:  # noqa: BLE001
            return EpisodeResult(status="unavailable")

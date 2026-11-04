"""Opt-in operator seam for bounded, local retrieval workflows."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from time import monotonic
from uuid import UUID, uuid4

from personal_ai.auth.scope import current_request_scope, current_verified_principal
from personal_ai.contracts.delegated_tasks import canonical_bytes
from personal_ai.contracts.workflow import (
    TERMINAL,
    AttemptOperationBinding,
    RunProgress,
    RunSpec,
    WorkflowProfile,
)
from personal_ai.persistence.postgres.workflows import PostgresWorkflowStore, WorkflowFenceLost
from personal_ai.retrieval.installation import load_snapshot
from personal_ai.retrieval.service import PinnedToolGuard, RetrievalService
from personal_ai.retrieval.tools import DEFAULT_TOOLS, ToolOutcome, require_tool


class WorkflowDenied(ValueError):
    pass


class WorkflowService:
    """Trusted host code supplies current workspace, client and owner authority."""

    def __init__(
        self,
        store: PostgresWorkflowStore,
        retrieval: RetrievalService,
        application_registry: Callable,
        *,
        enabled: bool = False,
        profile: WorkflowProfile = "foreground",
    ):
        self.store = store
        self.retrieval = retrieval
        self.application_registry = application_registry
        self.enabled = enabled
        self.profile = profile

    def scope_digest(self):
        principal = current_verified_principal()
        scope = current_request_scope()
        if (
            self.enabled is not True
            or self.profile != "foreground"
            or scope is None
            or scope is not self.retrieval.scope
            or principal is None
            or not principal.authenticated
            or not principal.audience
            or not principal.authorized_party
            or principal.expires_at is None
            or principal.expires_at <= datetime.now(UTC).timestamp()
            or scope.owner_id != principal.owner_id
            or scope.acting_user_id != f"{principal.issuer}|{principal.subject}"
            or self.retrieval.request_authority is None
            or self.retrieval.current_settings().app_environment not in {"local", "test"}
        ):
            raise WorkflowDenied("workflow_unavailable")
        try:
            self.retrieval.request_authority()
        except Exception:  # noqa: BLE001 - never expose authority internals
            raise WorkflowDenied("workflow_unavailable") from None
        return sha256(
            canonical_bytes(
                {
                    "owner": scope.owner_id,
                    "actor": scope.acting_user_id,
                    "app": scope.application_id,
                    "workspace": scope.workspace_id,
                    "audience": principal.audience,
                    "client": principal.authorized_party,
                    "purpose": "interactive_retrieval",
                }
            )
        ).hexdigest()

    def _tool(self, expected_source=None):
        try:
            return self._authorized_tool(expected_source)
        except Exception:  # noqa: BLE001 - expose no paths or source authority internals
            raise WorkflowDenied("workflow_source_unavailable") from None

    def _authorized_tool(self, expected_source):
        self.scope_digest()
        settings = self.retrieval.settings
        snapshot = load_snapshot(settings.retrieval_installation_file)
        now = datetime.now(UTC)
        if (
            snapshot.installation.issuer_id is None
            or expected_source is not None
            and expected_source != snapshot.digest
            or any(doc.sensitivity != "public" for doc in snapshot.installation.documents)
            or not any(
                doc.allows(self.retrieval.scope, now) for doc in snapshot.installation.documents
            )
        ):
            raise WorkflowDenied("workflow_source_unavailable")
        self.retrieval.guard(snapshot, tool=True)
        invoke = require_tool(
            self.application_registry(),
            self.retrieval.scope.application_id,
            tools=DEFAULT_TOOLS,
        )
        return snapshot, invoke

    def submit(self, spec: RunSpec) -> UUID:
        scope_digest = self.scope_digest()
        # Round-trip to detach trusted callers' objects and reject unvalidated copies.
        spec = RunSpec.model_validate_json(spec.model_dump_json())
        existing = self.store.find(scope_digest, spec)
        if existing is not None:
            return existing
        snapshot, _ = self._tool()
        return self.store.submit(scope_digest, spec, snapshot.digest)

    def status(self, run_id: UUID, *, cursor: int = 0) -> RunProgress:
        with self.store.locked(self.scope_digest(), run_id) as row:
            row.expire()
            return row.progress(cursor)

    def cancel(self, run_id: UUID) -> RunProgress:
        with self.store.locked(self.scope_digest(), run_id) as row:
            row.expire()
            if row.record["state"] not in TERMINAL and not row.record["cancel_requested"]:
                row.record["cancel_requested"] = True
                row.event("cancel_requested")
                if row.pending is None or row.pending["state"] == "reserved":
                    if row.pending is not None:
                        row.pending["state"] = "abandoned"
                        row.event("step_abandoned", row.pending["attempt_id"])
                    row.terminal("canceled")
            return row.progress(0)

    async def execute(self, run_id: UUID) -> tuple[RunProgress, tuple[ToolOutcome, ...]]:
        """Run one explicit foreground claim. Replays return metadata only."""
        scope_digest = self.scope_digest()
        result = await self._execute(scope_digest, run_id)
        if self.scope_digest() != scope_digest:
            raise WorkflowDenied("workflow_unavailable")
        return result

    async def _execute(self, scope_digest, run_id):
        with self.store.locked(scope_digest, run_id) as row:
            fence = row.claim()
            if fence is None:
                return row.progress(0), ()
            spec = RunSpec.model_validate(row.spec)
            source_digest = row.source_digest
            completed = sum(a["state"] == "succeeded" for a in row.record["attempts"])
        outputs = []
        remaining_steps = spec.ordered_steps()[completed:]
        if not remaining_steps:
            raise ValueError("workflow_receipts_invalid")
        for index, step in enumerate(remaining_steps, start=1):
            operation_observed = False
            try:
                _, invoke = self._tool(source_digest)
                operation_binding = AttemptOperationBinding(
                    tool_id=step.tool,
                    effect_class=DEFAULT_TOOLS.registrations[step.tool].effect,
                    step_digest=sha256(canonical_bytes(step.model_dump(mode="json"))).hexdigest(),
                    source_digest=source_digest,
                    intent_digest=spec.intent_digest(scope_digest),
                ).model_dump(mode="json")
                with self.store.locked(scope_digest, run_id) as row:
                    row.check(fence, renew=True)
                    if row.now >= row.deadline:
                        raise TimeoutError
                    attempt_id = str(uuid4())
                    row.record["attempts"].append(
                        {
                            "attempt_id": attempt_id,
                            "step": step.name,
                            "state": "reserved",
                            "operation_binding": operation_binding,
                        }
                    )
                    row.event("reserved", attempt_id)

                step_deadline = monotonic() + step.timeout_ms / 1000

                def check(*, step_deadline=step_deadline):
                    self._tool(source_digest)
                    with self.store.locked(scope_digest, run_id) as current:
                        current.check(fence)
                        if current.record["cancel_requested"]:
                            raise WorkflowDenied("workflow_canceled")
                        if current.now >= current.deadline or monotonic() >= step_deadline:
                            raise TimeoutError

                guard = PinnedToolGuard(source_digest, check)
                guard()
                async with asyncio.timeout(max(0, step_deadline - monotonic())):
                    with self.store.locked(scope_digest, run_id) as row:
                        row.check(fence)
                        if row.record["cancel_requested"]:
                            raise WorkflowDenied("workflow_canceled")
                        remaining = (row.deadline - row.now).total_seconds()
                        if remaining <= 0:
                            raise TimeoutError
                        row.dispatch(attempt_id, operation_binding)
                    async with asyncio.timeout(remaining):
                        result = await invoke(self.retrieval, step.query, guard)
                        operation_observed = True
                    guard()
                size = len(result.model_dump_json().encode())
                if size > step.result_bytes:
                    raise WorkflowDenied("workflow_result_bound")
                if result.retrieval.state == "unavailable":
                    raise WorkflowDenied("workflow_tool_unavailable")
                with self.store.locked(scope_digest, run_id) as row:
                    row.check(fence)
                    if row.record["cancel_requested"]:
                        raise WorkflowDenied("workflow_canceled")
                    if row.now >= row.deadline:
                        raise TimeoutError
                    row.pending["state"] = "succeeded"
                    row.event("step_succeeded", attempt_id)
                    if index == len(remaining_steps):
                        row.terminal("succeeded")
                        progress = row.progress(0)
                outputs.append(result)
            except WorkflowFenceLost:
                return self.status(run_id), ()
            except asyncio.CancelledError:
                self._fail(
                    scope_digest,
                    run_id,
                    fence,
                    TimeoutError(),
                    operation_observed=operation_observed,
                )
                raise
            except Exception as error:  # noqa: BLE001 - dispatch outcome must be durable
                return self._fail(
                    scope_digest,
                    run_id,
                    fence,
                    error,
                    operation_observed=operation_observed,
                ), ()

        # No retained passages. For a recovered run only this claim has live results.
        try:
            snapshot, _ = self._tool(source_digest)
        except WorkflowDenied:
            return progress, ()
        now = datetime.now(UTC)
        allowed = {
            (doc.source_id, doc.revision, doc.rights_epoch, doc.rights_reference)
            for doc in snapshot.installation.documents
            if doc.allows(self.retrieval.scope, now)
        }
        if any(
            item.expires_at <= now
            or (item.source_id, item.source_revision, item.rights_epoch, item.rights_reference)
            not in allowed
            for result in outputs
            for item in result.retrieval.items
        ):
            return progress, ()
        return progress, tuple(outputs)

    def _fail(self, scope_digest, run_id, fence, error, *, operation_observed):
        with self.store.locked(scope_digest, run_id) as row:
            row.expire()
            if row.record["state"] == "running" and row.record["fence"] == fence:
                attempt = row.pending
                if attempt is not None:
                    binding = attempt.get("operation_binding") or {}
                    known_read_only_result = (
                        operation_observed and binding.get("effect_class") == "read_only"
                    )
                    if attempt["state"] == "dispatched" and not known_read_only_result:
                        attempt["state"] = "uncertain"
                        row.terminal("uncertain", "operator_reconciliation_required")
                        return row.progress(0)
                    attempt["state"] = "failed"
                    row.event("step_failed", attempt["attempt_id"])
                if row.record["cancel_requested"]:
                    row.terminal("canceled")
                else:
                    reason = "deadline" if isinstance(error, TimeoutError) else "step_unavailable"
                    row.terminal("failed", reason)
            return row.progress(0)

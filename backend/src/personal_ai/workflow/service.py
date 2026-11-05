"""Opt-in operator seam for bounded foreground workflows."""

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
from hashlib import sha256
from time import monotonic
from uuid import UUID

from personal_ai.auth.scope import current_request_scope, current_verified_principal
from personal_ai.contracts.delegated_tasks import canonical_bytes
from personal_ai.contracts.reasoning_workflow import ReasoningBinding, Resources
from personal_ai.contracts.workflow import (
    TERMINAL,
    AttemptOperationBinding,
    RunProgress,
    RunSpec,
    WorkflowProfile,
)
from personal_ai.llm.workflow_fixture import FixtureAttempt
from personal_ai.persistence.postgres.workflows import PostgresWorkflowStore, WorkflowFenceLost
from personal_ai.reasoning.orchestration import (
    Checkpoint,
    Plan,
    Request,
    Stop,
    compile_plan,
    digest,
    fits,
    original_intent,
)
from personal_ai.retrieval.installation import load_snapshot
from personal_ai.retrieval.service import PinnedToolGuard, RetrievalService
from personal_ai.retrieval.tools import DEFAULT_TOOLS, require_tool
from personal_ai.workflow.reasoning import (
    ENDPOINT_DIGEST,
    IDENTITY,
    SOURCE_DIGEST,
    ReasoningHost,
    remaining_ms,
    run_check,
    supported,
)


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
        reasoning_host: ReasoningHost | None = None,
    ):
        self.store = store
        self.retrieval = retrieval
        self.application_registry = application_registry
        self.enabled = enabled
        self.profile = profile
        self.reasoning_host = reasoning_host

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
            if self.reasoning_host is not None:
                definition = self.application_registry().registration(scope.application_id).definition
                if definition != self.reasoning_host.context.definition:
                    raise WorkflowDenied("workflow_unavailable")
                self.reasoning_host.check(self.retrieval.current_settings(), scope)
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
                    "purpose": "interactive_retrieval" if self.reasoning_host is None else "synthetic_reasoning",
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

    def submit(self, spec: RunSpec | Request) -> UUID:
        started = monotonic()
        scope_digest = self.scope_digest()
        if self.reasoning_host is not None:
            if not isinstance(spec, Request):
                raise WorkflowDenied("workflow_spec_unsupported")
            return self._submit_reasoning(spec, scope_digest, started)
        if not isinstance(spec, RunSpec):
            raise WorkflowDenied("workflow_spec_unsupported")
        # Round-trip to detach trusted callers' objects and reject unvalidated copies.
        spec = RunSpec.model_validate_json(spec.model_dump_json())
        existing = self.store.find(scope_digest, spec)
        if existing is not None:
            return existing
        snapshot, _ = self._tool()
        return self.store.submit(scope_digest, spec, snapshot.digest)

    def _submit_reasoning(self, request, scope_digest, started):
        request = Request.model_validate_json(request.model_dump_json())
        request_digest = digest(request.model_dump(mode="json"))
        existing = self.store.find_intent(
            scope_digest, request.original_key, original_intent(scope_digest, request_digest),
        )
        if existing is not None:
            return existing
        host = self.reasoning_host
        plan = compile_plan(
            request, host.ceilings, scope_digest=scope_digest,
            endpoint_digest=ENDPOINT_DIGEST, fixture_digest=host.fixture_digest,
        )
        self._reasoning_authority(plan, scope_digest)
        return self.store.submit(
            scope_digest, plan, SOURCE_DIGEST, monotonic_deadline=started + plan.deadline_ms / 1000,
        )

    def _reasoning_authority(self, plan, scope_digest):
        try:
            if self.scope_digest() != scope_digest or plan.scope_digest != scope_digest:
                raise WorkflowDenied("workflow_unavailable")
            self.reasoning_host.check_plan(plan)
        except Exception:  # noqa: BLE001 - no authority internals in durable outcomes
            raise Stop("policy_denied") from None

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
                pending = row.pending
                if pending is None or pending["state"] == "reserved":
                    if pending is not None:
                        pending["state"] = "abandoned"
                        row.event("step_abandoned", pending["attempt_id"])
                    row.terminal("canceled")
                elif row.reasoning:
                    if (pending.get("operation_binding") or {}).get("tool_id") == "reasoning.verify.v1":
                        pending["resources"]["verifier_calls"] = 1
                        pending["state"] = "failed"
                        row.event("step_failed", pending["attempt_id"])
                        row.terminal("canceled")
                    else:
                        pending["state"] = "uncertain"
                        row.terminal("uncertain", "uncertain_effect")
            return row.progress(0)

    async def execute(self, run_id: UUID):
        """Run one explicit foreground claim. Replays return metadata only."""
        started = monotonic()
        scope_digest = self.scope_digest()
        result = await self._execute(scope_digest, run_id, started)
        if self.scope_digest() != scope_digest:
            raise WorkflowDenied("workflow_unavailable")
        return result

    async def _execute(self, scope_digest, run_id, started):
        with self.store.locked(scope_digest, run_id) as row:
            fence = row.claim()
            if fence is None:
                return row.progress(0), ()
            source_digest = row.source_digest
            completed = sum(a["state"] == "succeeded" for a in row.record["attempts"])
            if row.reasoning:
                plan = Plan.model_validate_json(canonical_bytes(row.spec))
                if (
                    source_digest != SOURCE_DIGEST
                    or row.record["plan_digest"] != digest(plan.model_dump(mode="json"))
                ):
                    raise ValueError("reasoning_plan_binding_changed")
                checkpoints = {
                    value.step: value for value in (
                        Checkpoint.model_validate_json(canonical_bytes(item))
                        for item in row.record["checkpoints"]
                    )
                }
                succeeded = tuple(
                    attempt["step"] for attempt in row.record["attempts"]
                    if attempt["state"] == "succeeded"
                )
                if succeeded != tuple(step.name for step in plan.steps[:completed]) or (
                    succeeded != tuple(checkpoints)
                ):
                    raise ValueError("reasoning_checkpoint_binding_changed")
                deadline = started + min(
                    plan.deadline_ms / 1000, (row.deadline - row.now).total_seconds(),
                )
            else:
                spec = RunSpec.model_validate(row.spec)
        if row.reasoning:
            return await self._run_reasoning(
                scope_digest, run_id, fence, plan, checkpoints, completed, deadline,
            )
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
                    attempt_id = row.reserve(step.name, operation_binding)

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
                    row.succeed(attempt_id)
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

    async def _run_reasoning(self, scope_digest, run_id, fence, plan, checkpoints, completed, deadline):
        host = self.reasoning_host
        pending = plan.steps[completed:]
        plan_digest = digest(plan.model_dump(mode="json"))

        def check(row, step_deadline=deadline, *, renew=False):
            self._reasoning_authority(plan, scope_digest)
            row.check(fence, renew=renew)
            if row.record["cancel_requested"]:
                raise Stop("cancelled")
            if row.now >= row.deadline or monotonic() >= step_deadline:
                raise TimeoutError

        try:
            for index, step in enumerate(pending):
                step_started = monotonic()
                step_deadline = min(deadline, step_started + step.timeout_ms / 1000)
                inference = step.tool == "reasoning.inference.v1"
                child = {}
                if inference:
                    request, message_id = host.continuation(run_id, plan, step, checkpoints)
                    child = {
                        "endpoint_digest": ENDPOINT_DIGEST, "child_key": request.idempotency_key,
                        "child_message_id": message_id, "child_digest": request.intent_digest,
                    }
                binding = ReasoningBinding(
                    tool_id=step.tool, step_digest=digest(step.model_dump(mode="json")),
                    source_digest=SOURCE_DIGEST, intent_digest=plan.intent_digest(scope_digest),
                    plan_digest=plan_digest, **child,
                ).model_dump(mode="json")
                resources = Resources(
                    physical_attempts=0, verifier_calls=0,
                    reserved_input_bytes=step.input_bytes if inference else None,
                    reserved_output_bytes=step.output_bytes if inference else None,
                ).model_dump(mode="json")
                with self.store.locked(scope_digest, run_id) as row:
                    check(row, step_deadline, renew=True)
                    accounted = [item["resources"] for item in row.record["attempts"]]
                    if not fits(
                        plan.limits, pending[index:],
                        prior_counts=sum(item["count_calls"] for item in accounted),
                        prior_count_bytes=sum(item["reserved_count_input_bytes"] for item in accounted),
                        prior_verifier_calls=sum(item["verifier_calls"] or 0 for item in accounted),
                    ):
                        raise Stop("budget_exhausted")
                    row.record["phase"] = (
                        "synthesizing" if step.role == "synthesis" else
                        "answering" if inference else "checking"
                    )
                    attempt_id = row.reserve(step.name, binding, resources=resources)

                def guard(step_deadline=step_deadline):
                    with self.store.locked(scope_digest, run_id) as current:
                        check(current, step_deadline)

                def reserve_count(step_deadline=step_deadline, attempt_id=attempt_id, step=step):
                    with self.store.locked(scope_digest, run_id) as current:
                        check(current, step_deadline)
                        active = current.pending
                        if (
                            active is None or active["state"] != "reserved"
                            or active["attempt_id"] != attempt_id
                            or active["resources"]["count_calls"] >= step.count_calls
                        ):
                            raise Stop("budget_exhausted")
                        active["resources"]["count_calls"] += 1
                        active["resources"]["reserved_count_input_bytes"] += step.input_bytes

                def observe_count(size, *, step_deadline=step_deadline, attempt_id=attempt_id, step=step):
                    if size > step.input_bytes:
                        raise Stop("budget_exhausted")
                    with self.store.locked(scope_digest, run_id) as current:
                        check(current, step_deadline)
                        active = current.pending
                        if active is None or active["state"] != "reserved" or active["attempt_id"] != attempt_id:
                            raise Stop("internal_failure")
                        facts = active["resources"]
                        if facts["count_calls"] != facts["observed_count_calls"] + 1:
                            raise Stop("internal_failure")
                        facts["observed_count_calls"] += 1
                        facts["observed_count_input_bytes"] += size

                def dispatch(
                    input_bytes=0, *, step_deadline=step_deadline, attempt_id=attempt_id,
                    binding=binding, step=step,
                ):
                    if input_bytes > step.input_bytes:
                        raise Stop("budget_exhausted")
                    with self.store.locked(scope_digest, run_id) as current:
                        check(current, step_deadline)
                        current.dispatch(attempt_id, binding)

                async with asyncio.timeout(remaining_ms(step_deadline) / 1000):
                    if inference:
                        attempt = FixtureAttempt(
                            request.idempotency_key, UUID(attempt_id), IDENTITY, reserve_count, observe_count, dispatch,
                        )
                        checkpoint, actual = await host.infer(
                            run_id, step, self.retrieval.current_settings(), request, message_id,
                            attempt, guard, 1 if step.slot is not None else len(plan.task.requirements),
                        )
                    else:
                        dispatch()
                        guard()
                        checkpoint = run_check(step, plan, checkpoints)
                        actual = {"verifier_calls": 1}
                    guard()
                checkpoints[step.name] = checkpoint
                verdict = checkpoint.verdict
                done = verdict in {"pass", "inconclusive"} or index == len(pending) - 1
                result = supported(checkpoint) if done and verdict in {"pass", "fail"} else ()
                with self.store.locked(scope_digest, run_id) as row:
                    check(row, step_deadline)
                    row.pending["resources"].update(
                        actual, elapsed_ms=int((monotonic() - step_started) * 1000),
                    )
                    if not inference:
                        row.pending["verification_receipt"] = {
                            "schema_version": "reasoning-verifier-receipt-v1",
                            "verifier_id": step.verifier,
                            "verdict": checkpoint.verdict,
                            "defect_count": len(checkpoint.defects) if checkpoint.verdict != "inconclusive" else None,
                            "sufficiency_decision": {
                                "pass": "sufficient", "fail": "insufficient",
                                "inconclusive": "inconclusive",
                            }[checkpoint.verdict],
                        }
                    row.succeed(attempt_id)
                    if not done:
                        row.record["checkpoints"].append(checkpoint.model_dump(mode="json"))
                        continue
                    if verdict == "pass":
                        row.terminal("succeeded", "sufficient")
                    else:
                        if result:
                            row.record["outcome"] = "partial"
                        row.terminal("failed", "evidence_insufficient")
                    progress = row.progress(0)
                break
            else:
                raise ValueError("reasoning_receipts_invalid")
        except WorkflowFenceLost:
            return self.status(run_id), ()
        except asyncio.CancelledError:
            self._fail(scope_digest, run_id, fence, Stop("cancelled"), operation_observed=False)
            raise
        except Exception as error:  # noqa: BLE001 - preserve the durable uncertainty classification
            return self._fail(scope_digest, run_id, fence, error, operation_observed=False), ()
        try:
            self._reasoning_authority(plan, scope_digest)
        except Stop:
            raise WorkflowDenied("workflow_unavailable") from None
        return progress, result if monotonic() < deadline else ()

    def _fail(self, scope_digest, run_id, fence, error, *, operation_observed):
        with self.store.locked(scope_digest, run_id) as row:
            row.expire()
            if row.record["state"] == "running" and row.record["fence"] == fence:
                attempt = row.pending
                if attempt is not None:
                    binding = attempt.get("operation_binding") or {}
                    pure_verifier = row.reasoning and binding.get("tool_id") == "reasoning.verify.v1"
                    authority_revoked = isinstance(error, Stop) and str(error) == "policy_denied"
                    known_read_only_result = (
                        operation_observed and binding.get("effect_class") == "read_only"
                    )
                    if attempt["state"] == "dispatched" and pure_verifier and authority_revoked:
                        # The result cannot be checkpointed or disclosed under the
                        # revoked scope. Preserve the conservative reconciliation
                        # outcome used for authority loss at a committed boundary.
                        attempt["state"] = "uncertain"
                        row.terminal("uncertain", "uncertain_effect")
                        return row.progress(0)
                    if attempt["state"] == "dispatched" and not known_read_only_result and not pure_verifier:
                        attempt["state"] = "uncertain"
                        row.terminal("uncertain", "operator_reconciliation_required")
                        return row.progress(0)
                    if pure_verifier:
                        attempt["resources"]["verifier_calls"] = 1
                    attempt["state"] = "failed"
                    row.event("step_failed", attempt["attempt_id"])
                if row.record["cancel_requested"]:
                    row.terminal("canceled")
                else:
                    reason = "deadline" if isinstance(error, TimeoutError) else "step_unavailable"
                    if row.reasoning and isinstance(error, Stop):
                        reason = str(error)
                    if row.reasoning and reason == "cancelled":
                        row.terminal("canceled")
                        return row.progress(0)
                    row.terminal("failed", reason)
            return row.progress(0)

"""Grounded template execution using WorkflowService's canonical fenced row."""

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from time import monotonic
from uuid import UUID, uuid5

from personal_ai.llm.workflow_fixture import FixtureAttempt
from personal_ai.persistence.postgres.workflows import WorkflowFenceLost
from personal_ai.reasoning import grounded as grounded_policy
from personal_ai.reasoning.grounded_receipts import (
    GroundedBinding,
    GroundedCheck,
    GroundedResources,
)
from personal_ai.reasoning.orchestration import Stop, digest
from personal_ai.reasoning.policy import ReasoningDenied
from personal_ai.retrieval.context import RetrievalContextAuthority
from personal_ai.retrieval.installation import Snapshot
from personal_ai.retrieval.service import PinnedToolGuard
from personal_ai.workflow import grounded
from personal_ai.workflow.reasoning import ENDPOINT_DIGEST, IDENTITY, remaining_ms


@dataclass(frozen=True, slots=True)
class ReservedStep:
    snapshot: Snapshot
    invoke: Callable
    authority: RetrievalContextAuthority
    guard: Callable
    dispatch: Callable
    complete: Callable
    deadline: float
    fixture: FixtureAttempt | None


async def execute_grounded(service, scope_digest, run_id, fence, plan, deadline):
    """Execute the closed template with the existing fenced attempt lifecycle."""
    items = ()
    reasons = set()
    truncated = False
    plan_digest = digest(plan.model_dump(mode="json"))
    limits = plan.limits
    remaining = (limits.evidence_items, limits.quote_bytes, limits.retrieval_token_bound)
    operation_observed = False
    observed_usage = None

    def check(row, end, *, renew=False):
        row.check(fence, renew=renew)
        if row.record["cancel_requested"]:
            raise Stop("cancelled")
        if row.now >= row.deadline or monotonic() >= end:
            raise TimeoutError
        return service._grounded_authority(scope_digest, plan, items)

    def reserve(
        step, operation_digest, child_key, *,
        request=None, message_id=None, query=None, focused_slot=None, focused_gap=None,
    ):
        nonlocal operation_observed, observed_usage
        operation_observed = False
        observed_usage = None
        started = monotonic()
        end = min(deadline, started + grounded_policy.STEP_MS / 1000)
        with service.store.locked(scope_digest, run_id) as row:
            snapshot, invoke, authority = check(row, end, renew=True)
            binding = GroundedBinding(
                tool_id=grounded_policy.STEP_TOOLS[step], scope_digest=scope_digest,
                source_digest=plan.source_digest, intent_digest=plan.intent_digest(scope_digest),
                evidence_digest=digest([
                    grounded.evidence_dependency(snapshot, item).model_dump(mode="json") for item in items
                ]),
                step_digest=operation_digest, plan_digest=plan_digest, child_key=child_key,
                endpoint_digest=ENDPOINT_DIGEST if request is not None else None,
                child_message_id=message_id, focused_slot=focused_slot, focused_gap=focused_gap,
            ).model_dump(mode="json")
            resources = GroundedResources(
                reserved_input_bytes=limits.input_bytes if request is not None else 0,
                reserved_output_bytes=limits.output_bytes if request is not None else 0,
                reserved_evidence_items=query.max_items if query is not None else 0,
                reserved_quote_bytes=query.max_quote_bytes if query is not None else 0,
                reserved_retrieval_token_bound=query.max_tokens if query is not None else 0,
            ).model_dump(mode="json")
            attempt_id = row.reserve(step, binding, resources=resources)

        def guard():
            with service.store.locked(scope_digest, run_id) as row:
                check(row, end)

        def dispatch(input_bytes=0):
            if input_bytes > limits.input_bytes:
                raise Stop("budget_exhausted")
            with service.store.locked(scope_digest, run_id) as row:
                check(row, end)
                row.dispatch(attempt_id, binding)

        def count(size=None):
            with service.store.locked(scope_digest, run_id) as row:
                check(row, end)
                active = row.pending
                if active is None or active["state"] != "reserved" or active["attempt_id"] != attempt_id:
                    raise Stop("internal_failure")
                resources = active["resources"]
                if size is None:
                    if (
                        resources["count_calls"] >= limits.count_calls
                        or resources["reserved_count_input_bytes"] + limits.input_bytes > limits.count_input_bytes
                    ):
                        raise Stop("budget_exhausted")
                    resources["count_calls"] += 1
                    resources["reserved_count_input_bytes"] += limits.input_bytes
                else:
                    if size > limits.input_bytes:
                        raise Stop("budget_exhausted")
                    if resources["count_calls"] != resources["observed_count_calls"] + 1:
                        raise Stop("internal_failure")
                    resources["observed_count_calls"] += 1
                    resources["observed_count_input_bytes"] += size

        def complete(row, **actual):
            check(row, end)
            row.pending["resources"].update(
                observed_calls=1, elapsed_ms=int((monotonic() - started) * 1000), **actual,
            )
            row.succeed(attempt_id)

        def respond(messages):
            packed = tuple(grounded_policy.wire_evidence(messages))
            if len(packed) != len(items) or {item.citation_id: item for item in packed} != {
                item.citation_id: item for item in items
            }:
                raise Stop("source_changed")
            return grounded_policy.draft_from_messages(messages)

        fixture = None
        if request is not None:
            fixture = FixtureAttempt(
                child_key, UUID(attempt_id), IDENTITY, count, count, dispatch, respond=respond,
            )
        return ReservedStep(snapshot, invoke, authority, guard, dispatch, complete, end, fixture)

    async def retrieve(step, field=None, gap=None):
        nonlocal items, operation_observed, remaining, truncated
        query = grounded.retrieval_query(run_id, plan, step, remaining, field=field)
        operation = reserve(
            step, digest(query.model_dump(mode="json")), query.idempotency_key, query=query,
            focused_slot=plan.task.requirements.index(field) if field else None, focused_gap=gap,
        )
        async with asyncio.timeout(remaining_ms(operation.deadline) / 1000):
            operation.dispatch()
            result = (await operation.invoke(
                service.retrieval, query, PinnedToolGuard(
                    operation.snapshot.digest, operation.guard, report_limit=True,
                ),
            )).retrieval
            operation_observed = True
            returned = grounded.validate_retrieval(result, query, operation.snapshot, service.retrieval.scope)
            if {"source_authority_changed", "source_unavailable"} & set(result.reasons):
                raise Stop("source_changed")
            if result.state == "unavailable" and not {"freshness_unverified", "budget"} & set(result.reasons):
                raise Stop("provider_unavailable")
            reasons.update(result.reasons)
            truncated |= "budget" in result.reasons
            known_ids = {item.citation_id for item in items}
            items += tuple(item for item in returned if item.citation_id not in known_ids)
            remaining = tuple(
                cap - used for cap, used in zip(
                    remaining, (len(returned), result.quote_bytes, result.token_upper_bound), strict=True,
                )
            )
            with service.store.locked(scope_digest, run_id) as row:
                row.pending["evidence"] = [
                    grounded.evidence_dependency(operation.snapshot, item).model_dump(mode="json")
                    for item in returned
                ]
                operation.complete(
                    row, quote_bytes=result.quote_bytes, retrieval_token_bound=result.token_upper_bound,
                )

    def gaps_for_evidence():
        return grounded_policy.coverage(
            plan.task, items, stale="freshness_unverified" in reasons, truncated=truncated,
        )

    def finish(row, claims, gaps, stage):
        row.record["verification"] = GroundedCheck(
            supported_count=len(claims), gaps=gaps, stage=stage,
            citation_digest=digest([claim.citation_id for claim in claims]),
        ).model_dump(mode="json")
        if len(claims) == len(plan.task.requirements):
            row.terminal("succeeded", "sufficient")
        else:
            if claims:
                row.record["outcome"] = "partial"
            row.terminal("failed", "evidence_insufficient")
        return row.progress(0)

    try:
        if remaining_ms(deadline) < 3 * grounded_policy.STEP_MS:
            raise Stop("budget_exhausted")
        await retrieve("initial")
        gaps = gaps_for_evidence()
        field = grounded_policy.focused_field(plan, gaps)
        can_focus = (
            field is not None and remaining[0] > 0 and min(remaining[1:]) >= 64
            and remaining_ms(deadline) >= 3 * grounded_policy.STEP_MS
        )
        if service.adaptive_host is not None:
            service.adaptive_host.grounded_shadow(plan, gaps, can_focus, scope_digest)
        if can_focus:
            await retrieve("focused", field, gaps[plan.task.requirements.index(field)])
            gaps = gaps_for_evidence()
        if all(gaps):
            with service.store.locked(scope_digest, run_id) as row:
                check(row, deadline)
                return finish(row, (), gaps, "evidence_assessment"), ()
        if remaining_ms(deadline) < 2 * grounded_policy.STEP_MS:
            raise Stop("budget_exhausted")
        request, message_id = grounded.continuation(run_id, plan, service.grounded_host.context)
        synthesis = reserve(
            "synthesis", request.intent_digest, request.idempotency_key, request=request, message_id=message_id,
        )
        try:
            async with asyncio.timeout(remaining_ms(synthesis.deadline) / 1000):
                raw, actual = await grounded.infer(
                    run_id, service.grounded_host, service.retrieval.current_settings(), plan,
                    request, message_id, synthesis.fixture, synthesis.guard, synthesis.snapshot, items, synthesis.authority,
                )
        finally:
            metadata = synthesis.fixture.metadata
            operation_observed = metadata is not None
            usage = metadata.usage if operation_observed else None
            if (
                usage is not None and usage.confidence == "reported"
                and 0 < usage.input_tokens <= limits.input_bytes
                and 0 <= usage.output_tokens <= limits.output_bytes
            ):
                observed_usage = {"input_bytes": usage.input_tokens, "output_bytes": usage.output_tokens}
        with service.store.locked(scope_digest, run_id) as row:
            synthesis.complete(row, **actual)

        check_key = uuid5(run_id, "check")
        verification = reserve(
            "check", digest({
                "verifier": "fixture-fact-citation.v1", "synthesis_attempt": str(synthesis.fixture.attempt_id),
            }), check_key,
        )
        verification.dispatch()
        verification.guard()
        claims, gaps = grounded_policy.verify(plan.task, items, raw, gaps)
        operation_observed = True
        with service.store.locked(scope_digest, run_id) as row:
            verification.complete(row)
            progress = finish(row, claims, gaps, "candidate_verification")
    except WorkflowFenceLost:
        return service.status(run_id), ()
    except asyncio.CancelledError:
        service._fail(
            scope_digest, run_id, fence, Stop("cancelled"),
            operation_observed=operation_observed, observed_usage=observed_usage,
        )
        raise
    except Exception as error:  # noqa: BLE001 - preserve original attempt on unknown outcome
        if isinstance(error, ReasoningDenied):
            # Chat may translate a pre-packing authority rejection to a generic
            # denial. Observe the current exact source state before settling.
            try:
                service._grounded_authority(scope_digest, plan, items)
            except Stop as denial:
                error = denial
            else:
                error = Stop(error.observation.stop_reason)
        return service._fail(
            scope_digest, run_id, fence, error, operation_observed=operation_observed, observed_usage=observed_usage,
        ), ()
    try:
        service._grounded_authority(scope_digest, plan, items)
    except Stop:
        return progress, ()
    return progress, claims if monotonic() < deadline else ()

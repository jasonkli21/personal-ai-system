"""Fresh canonical workflow fixture per arm. Only execution inputs enter this module."""

from contextlib import aclosing, contextmanager
from time import monotonic, time
from unittest.mock import patch

from personal_ai.contracts.delegated_tasks import canonical_bytes
from personal_ai.evaluation.reasoning_grounded.fixture import fixture_service
from personal_ai.evaluation.reasoning_orchestrator.fixture import FixtureStore, synthetic_service
from personal_ai.llm.execution import LocalFakeCounter
from personal_ai.llm.fake import FakeLLMClient
from personal_ai.reasoning import adaptive, grounded
from personal_ai.reasoning.adaptive_control import LocalPolicyControl, PolicyPointer
from personal_ai.reasoning.adaptive_plan import compile_candidate
from personal_ai.reasoning.orchestration import HARD_LIMIT, Request, Stop, compile_plan
from personal_ai.retrieval.service import RetrievalService
from personal_ai.workflow import adaptive as host_policy
from personal_ai.workflow.reasoning import ENDPOINT_DIGEST, SOURCE_DIGEST, Fixture
from personal_ai.workflow.service import WorkflowDenied, WorkflowService

FIXTURE_BUILD = adaptive.digest("isolated-adaptive-evaluation")
FIXTURE_PROTOCOL = adaptive.digest("reasoning-adaptive-experiment-v1")
ABLATIONS = ("no_features", "no_early_exit", "no_compare")


class OfflineWorkflow(WorkflowService):
    """Offline plans are executable only in the hermetic evaluation double."""

    def _adaptive_authorized(self, plan, scope_digest):
        return (
            type(self.store) is FixtureStore and plan.scope_digest == scope_digest
            and plan.adaptive_decision.mode == "offline_fixture"
        )


def shadow_host(service, directory, policy, *, task=None):
    control = LocalPolicyControl(directory)
    now = int(time())
    control.update(0, PolicyPointer(
        generation=1, mode="shadow", policy_digest=policy.identity, build_digest=FIXTURE_BUILD,
        issued_at=now, expires_at=now + 300,
    ))
    bindings = frozenset() if task is None else frozenset({
        host_policy.finite_fixture_binding(task, service.reasoning_host.fixture_digest),
    })
    return host_policy.AdaptiveHost(
        control, service.scope_digest(), FIXTURE_BUILD, FIXTURE_PROTOCOL, finite_fixtures=bindings,
    )


@contextmanager
def fresh_host(case, directory, fixture_rights):
    if case["profile"] == "finite":
        fixture = Fixture.model_validate_json(canonical_bytes(case["fixture"]))
        with synthetic_service(fixture) as service:
            yield service
    else:
        with fixture_service(
            directory / "installation.json", case["subject"], case["sources"],
            authorized=case["fault"] != "denied", fixture_rights=fixture_rights,
        ) as service:
            yield service


def request_for(case, key):
    if case["profile"] == "grounded":
        return grounded.Request(
            schema_version="reasoning-grounded-request-v1", original_key=key,
            task=grounded.Task(subject=case["subject"], requirements=tuple(case["requirements"])),
            limits=grounded.HARD_LIMIT, effort="max",
        )
    limits = HARD_LIMIT.model_copy(update={"model_calls": 0}) if case["fault"] == "quota" else HARD_LIMIT
    return Request.model_validate_json(canonical_bytes({
        "schema_version": "reasoning-run-request-v1", "original_key": str(key),
        "task": case["task"], "limits": limits.model_dump(mode="json"),
        "effort": "low" if case["fault"] == "low_effort" else "max",
    }))


def offline_submit(service, request, arm):
    started = monotonic()
    scope = service.scope_digest()
    baseline = compile_plan(
        request, service.reasoning_host.ceilings, scope_digest=scope,
        endpoint_digest=ENDPOINT_DIGEST, fixture_digest=service.reasoning_host.fixture_digest,
    )
    features = adaptive.finite_features(baseline)
    reason = adaptive.finite_reason(features)
    applicable = reason == "eligible" or arm == "no_features" and reason == "no_marginal_value"
    plan = baseline
    if applicable:
        decision = adaptive.decision(
            features, adaptive.FINITE, 1, "baseline", "candidate_compare", "eligible",
            offline=True,
        )
        plan = compile_candidate(baseline, decision, ablation=arm if arm in ABLATIONS else "none")
    service._reasoning_authority(plan, scope)
    return service.store.submit(scope, plan, SOURCE_DIGEST, monotonic_deadline=started + plan.deadline_ms / 1000)


def operation_class(attempt):
    tool = attempt.operation_binding.tool_id
    if tool == "retrieval.query.v1":
        return "retrieval"
    return "model" if ".inference." in tool else "verifier"


def ledger(attempts, physical, counts, reads):
    entries = {
        kind: {"reserved": 0, "dispatched": 0, "observed": 0, "unknown": 0}
        for kind in ("model", "retrieval", "verifier", "count")
    }
    byte_usage = dict.fromkeys((
        "reserved_input", "reserved_output", "observed_input", "observed_output",
        "reserved_count", "observed_count", "reserved_quotes", "observed_quotes",
        "reserved_retrieval_bound", "observed_retrieval_bound",
        "unknown_reserved_generation",
    ), 0)
    keys = {name: [] for name in ("model", "retrieval")}
    for attempt in attempts:
        kind = operation_class(attempt)
        usage = attempt.resources
        observed = (
            usage.observed_calls if hasattr(usage, "observed_calls") else
            usage.physical_attempts if kind == "model" else
            int(attempt.state == "succeeded")
        )
        charged = getattr(usage, "verifier_calls_charged", getattr(usage, "verifier_calls", 0))
        dispatched = bool(charged) if kind == "verifier" else observed != 0
        unknown = dispatched and observed != 1
        entries[kind]["reserved"] += 1
        entries[kind]["dispatched"] += dispatched
        entries[kind]["observed"] += observed == 1
        entries[kind]["unknown"] += unknown
        if kind in keys and dispatched:
            keys[kind].append(attempt.operation_binding.child_key)
        entries["count"]["reserved"] += usage.count_calls
        entries["count"]["dispatched"] += usage.count_calls
        entries["count"]["observed"] += usage.observed_count_calls
        entries["count"]["unknown"] += usage.count_calls - usage.observed_count_calls
        for name, field in (
            ("reserved_input", "reserved_input_bytes"), ("reserved_output", "reserved_output_bytes"),
            ("observed_input", "input_bytes"), ("observed_output", "output_bytes"),
            ("reserved_count", "reserved_count_input_bytes"), ("observed_count", "observed_count_input_bytes"),
            ("reserved_quotes", "reserved_quote_bytes"), ("observed_quotes", "quote_bytes"),
            ("reserved_retrieval_bound", "reserved_retrieval_token_bound"),
            ("observed_retrieval_bound", "retrieval_token_bound"),
        ):
            byte_usage[name] += getattr(usage, field, None) or 0
        if kind == "model" and unknown:
            byte_usage["unknown_reserved_generation"] += usage.reserved_input_bytes + usage.reserved_output_bytes
    reconciled = (
        len(physical) == len(set(physical)) and len(reads) == len(set(reads))
        and physical == keys["model"] and reads == keys["retrieval"]
        and len(counts) == entries["count"]["observed"]
        and sum(counts) == byte_usage["observed_count"]
    )
    return {
        "operations": entries, "fake_bytes": byte_usage, "reconciled": reconciled,
        "cost_class": "synthetic_no_charge", "real_provider_tokens": None, "real_provider_charge": None,
        "real_quota": None, "provider_reservations": None, "provider_settlements": None,
    }


async def observe(key, case, arm, directory):
    """The selection and execution stage receives neither split nor oracle."""
    started = monotonic()
    request = request_for(case, key)
    raw_send, raw_count, raw_query = FakeLLMClient.stream_events, LocalFakeCounter.count, RetrievalService.query
    receipts, physical, counts, reads, wire = [], [], [], [], {}
    outcome, reason, attempts, result, safe, early = "denied", None, (), (), True, False
    strategy, effective_effort, planned = None, None, {}

    def count(*args, **kwargs):
        result = raw_count(*args, **kwargs)
        counts.append(result.tokens)
        return result

    async def query(service, req, **kwargs):
        reads.append(req.idempotency_key)
        return await raw_query(service, req, **kwargs)

    async def send(client, messages, **kwargs):
        from personal_ai.llm.workflow_fixture import fixture_attempt

        physical.append(fixture_attempt.get().child_key)
        if case["profile"] == "grounded":
            wire.update((item.citation_id, item.source_id) for item in grounded.wire_evidence(messages))
        if case["fault"] == "unknown":
            raise RuntimeError("fixture acknowledgement lost")
        async with aclosing(raw_send(client, messages, **kwargs)) as events:
            async for event in events:
                yield event
                if case["fault"] == "cancel":
                    service.cancel(run_id)

    # The grounded authority is installed afresh and can be revoked without changing
    # the host identity or replacing the installation outside this arm.
    with (
        fresh_host(case, directory, lambda: case["fault"] != "revoked" or not physical) as service,
        patch.object(FakeLLMClient, "stream_events", send),
        patch.object(LocalFakeCounter, "count", count),
        patch.object(RetrievalService, "query", query),
        patch.object(host_policy, "observe", lambda receipt: receipts.append(receipt.model_dump(mode="json"))),
    ):
        if arm == "shadow":
            policy = adaptive.FINITE if case["profile"] == "finite" else adaptive.GROUNDED
            service.adaptive_host = shadow_host(
                service, directory, policy, task=request.task if case["profile"] == "finite" else None,
            )
        if arm in ("adaptive", *ABLATIONS):
            service = OfflineWorkflow(
                service.store, service.retrieval, service.application_registry,
                enabled=True, reasoning_host=service.reasoning_host,
            )
        try:
            run_id = (
                offline_submit(service, request, arm) if arm in ("adaptive", *ABLATIONS) else service.submit(request)
            )
        except (Stop, WorkflowDenied) as error:
            reason = str(error)
        else:
            with service.store.locked(service.scope_digest(), run_id) as row:
                if "steps" in row.spec:
                    steps = row.spec["steps"]
                    planned = {
                        "model": sum(step["tool"] == "reasoning.inference.v1" for step in steps),
                        "verifier": sum(step["tool"] == "reasoning.verify.v1" for step in steps),
                        "count": sum(step["count_calls"] for step in steps),
                        "retrieval": 0,
                    }
                else:
                    planned = {
                        kind: row.spec["limits"][f"{kind}_calls"]
                        for kind in ("model", "verifier", "count", "retrieval")
                    }
                    if arm == "one_shot":
                        planned["retrieval"] = 1
                if case["fault"] == "deadline":
                    row.deadline = row.now
            picker = grounded.focused_field if arm != "one_shot" else lambda plan, gaps: None
            with patch.object(grounded, "focused_field", picker):
                progress, result = await service.execute(run_id)
                replay = await service.execute(run_id)
            safe = replay == (progress, ()) and service.submit(request) == run_id
            with service.store.locked(service.scope_digest(), run_id) as row:
                safe &= row.spec is None and not {
                    "checkpoints", "task", "answer", "quote", "requirements",
                } & row.record.keys()
            outcome, reason, attempts = progress.outcome, progress.reason, progress.attempts
            strategy, effective_effort = progress.strategy_version, progress.effort
            checks = [getattr(attempt, "verification_receipt", None) for attempt in attempts]
            early = any(check is not None and check.verdict == "pass" for check in checks[:-1])
            if hasattr(progress, "adaptive_decision"):
                receipts.append(progress.adaptive_decision.model_dump(mode="json"))
    return {
        "result": result, "wire": wire, "outcome": outcome, "reason": reason,
        "elapsed_ms": round((monotonic() - started) * 1000, 3),
        "selection": receipts, "ledger": ledger(attempts, physical, counts, reads),
        "strategy_version": strategy, "effective_effort": effective_effort, "planned_operations": planned,
        "safety": safe, "work_after_pass": early,
        "limits": request.limits.model_dump(mode="json"),
    }

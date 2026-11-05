"""Closed compilation, scoped execution and benchmark integrity."""

import asyncio
from uuid import uuid4

import pytest
from pydantic import ValidationError

from personal_ai.evaluation.reasoning_orchestrator.fixture import CEILINGS, synthetic_service
from personal_ai.evaluation.reasoning_orchestrator.runner import load
from personal_ai.reasoning.catalog import CATALOG
from personal_ai.reasoning.orchestration import (
    HARD_LIMIT,
    STRATEGY_VERSIONS,
    Limits,
    Plan,
    Request,
    Requirement,
    ScopeCeilings,
    Stop,
    Task,
    compile_plan,
)
from personal_ai.workflow.reasoning import ENDPOINT_DIGEST, Fixture
from personal_ai.workflow.service import WorkflowDenied


def request(kind="simple", *, limits=HARD_LIMIT, effort="max", strategy="auto"):
    requirements = (Requirement(operation="add", left=1, right=2),)
    if kind == "independent":
        requirements += (Requirement(operation="multiply", left=2, right=3),)
    return Request(
        schema_version="reasoning-run-request-v1", original_key=uuid4(),
        effort=effort, strategy=strategy, task=Task(kind=kind, requirements=requirements),
        limits=limits,
    )


def plan(req=None, ceilings=CEILINGS):
    return compile_plan(
        req or request(), ceilings, scope_digest="a" * 64, fixture_digest="b" * 64,
        endpoint_digest=ENDPOINT_DIGEST,
    )


def test_strategy_versions_preserve_the_proposal_only_catalog():
    assert CATALOG["tool_verify"].effect == "proposal_only"
    assert STRATEGY_VERSIONS["tool_verify"] == "tool-verify-pure.v1"
    compiled = plan(request("arithmetic"))
    assert compiled.strategy == "tool_verify" and compiled.steps[1].verifier == "arithmetic.v1"
    assert all(step.effect == "read_only" for step in compiled.steps)


@pytest.mark.parametrize("effort", ["auto", "low", "medium", "high", "max"])
def test_effort_intersection_and_deterministic_shape(effort):
    compiled = plan(request("independent", effort=effort))
    assert compiled.strategy == ("direct" if effort == "low" else "decompose")
    assert compiled == Plan.model_validate_json(compiled.model_dump_json())
    assert compiled.steps == compiled.ordered_steps()
    low = plan(request("independent", effort=effort), CEILINGS.model_copy(update={"workspace_effort": "low"}))
    assert low.strategy == "direct" and low.effort == "low"


@pytest.mark.parametrize("change", [
    {"limits": None}, {"schema_version": "reasoning-run-request-v2"}, {"strategy": "tool_verify"},
    {"endpoint": "https://outside.invalid"}, {"limits": {"model_calls": True}},
    {"limits": {"external_sources": False}}, {"limits": {"deadline_ms": 30001}},
    {"limits": {"count_calls": 65}}, {"effort": None},
    {"task": {"kind": "simple", "requirements": [], "source_revision": "forged"}},
    {"task": {"kind": "simple", "requirements": [{"operation": "add", "left": True, "right": 1}]}},
])
def test_request_rejects_unclosed_input(change):
    import json

    raw = request().model_dump(mode="json")
    with pytest.raises(ValidationError):
        Request.model_validate_json(json.dumps({**raw, **change}))


@pytest.mark.parametrize("change", [
    {"dependencies": ["answer", "answer"]}, {"dependencies": ["check"]},
    {"dependencies": ["missing"]}, {"tool": "import.shell"}, {"name": "answer"},
    {"slot": 0}, {"verifier": "tool.remote.v1"}, {"timeout_ms": 2001},
])
def test_compiled_plan_rejects_forged_graphs(change):
    import json

    raw = plan().model_dump(mode="json")
    raw["steps"][1].update(change)
    with pytest.raises(ValidationError):
        Plan.model_validate_json(json.dumps(raw))


@pytest.mark.parametrize("resource", [
    "model_calls", "verifier_calls", "input_bytes", "output_bytes",
    "count_calls", "count_input_bytes", "deadline_ms", "concurrency", "result_bytes",
])
def test_missing_resource_is_zero_and_denies_before_reservation(resource):
    limits = Limits.model_validate({
        field: value for field, value in HARD_LIMIT.model_dump().items() if field != resource
    })
    with synthetic_service(Fixture(answer='{"values":[3]}')) as service:
        with pytest.raises(Stop, match="budget_exhausted"):
            service.submit(request(limits=limits))
        assert not service.store.rows


def test_scope_caps_and_direct_pin_require_trusted_grants():
    req = request()
    with pytest.raises(Stop, match="budget_exhausted"):
        plan(req, ScopeCeilings())
    with pytest.raises(Stop, match="policy_denied"):
        plan(req.model_copy(update={"strategy": "direct"}), CEILINGS.model_copy(update={"allow_direct_pin": False}))


def test_disabled_and_paid_modes_cannot_admit_a_run():
    with (
        synthetic_service(Fixture(answer='{"values":[3]}'), enabled=False) as service,
        pytest.raises(WorkflowDenied),
    ):
        service.submit(request())
    with synthetic_service(Fixture(answer='{"values":[3]}')) as service:
        service.retrieval.settings.inference_cost_mode = "strict_free"
        with pytest.raises(WorkflowDenied):
            service.submit(request())
        assert not service.store.rows


@pytest.mark.parametrize(("kind", "fixture", "steps", "outcome", "answer"), [
    ("simple", Fixture(answer='{"values":[3]}'), ("answer", "check"), "complete", ((0, 3),)),
    ("independent", Fixture(
        answer='{"values":[3,0]}', subanswers=('{"values":[3]}', '{"values":[6]}'),
        synthesis='{"values":[3,6]}',
    ), ("slot_0", "slot_1", "synthesis", "check"), "complete", ((0, 3), (1, 6))),
    ("correctable", Fixture(answer='{"values":[3]}'), ("answer", "check"), "complete", ((0, 3),)),
    ("correctable", Fixture(answer='{"values":[4]}', revision='{"values":[3]}'),
     ("answer", "check", "revision", "recheck"), "complete", ((0, 3),)),
    ("arithmetic", Fixture(answer='{"values":[4]}', revision='{"values":[5]}'),
     ("answer", "check", "revision", "recheck"), "unavailable", ()),
    ("arithmetic", Fixture(answer='{"values":[3],"secret":"CANARY"}'),
     ("answer", "check"), "unavailable", ()),
])
def test_templates_execute_honestly_and_replay_metadata_only(kind, fixture, steps, outcome, answer):
    with synthetic_service(fixture) as service:
        original = request(kind)
        run_id = service.submit(original)
        progress, result = asyncio.run(service.execute(run_id))
        assert progress.outcome == outcome and result == answer
        assert [attempt.step for attempt in progress.attempts] == list(steps)
        assert service.submit(original) == run_id
        assert asyncio.run(service.execute(run_id)) == (progress, ())
        assert service.status(run_id, cursor=progress.cursor).events == ()
        assert progress.gap
        for attempt in progress.attempts:
            if attempt.operation_binding.child_key:
                assert attempt.resources.physical_attempts == 1
                assert 0 < attempt.resources.input_bytes <= 1024
                assert 0 < attempt.resources.count_calls <= 8
                assert attempt.resources.provider_settlements is None
        with service.store.locked(service.scope_digest(), run_id) as row:
            assert row.spec is None and "checkpoints" not in row.record
            assert "CANARY" not in str(row.record)


def test_insufficient_synthesis_budget_uses_verified_direct_and_returns_only_supported_slots():
    limits = HARD_LIMIT.model_copy(update={"model_calls": 1})
    fixture = Fixture(answer='{"values":[3,7]}')
    with synthetic_service(fixture) as service:
        progress, result = asyncio.run(service.execute(service.submit(request("independent", limits=limits))))
    assert progress.selection == "budget_narrowed" and progress.outcome == "partial"
    assert progress.reason == "evidence_insufficient" and result == ((0, 3),)


def test_with_no_reliable_predicate_request_is_unavailable():
    with synthetic_service(Fixture(answer='{"values":[3]}')) as service:
        with pytest.raises(Stop, match="evidence_insufficient"):
            service.submit(request("unknown"))
        assert not service.store.rows


def test_paired_cohort_and_thresholds_are_sealed():
    manifest, cases = load()
    assert manifest["pairs"] == len(cases) == 60
    assert manifest["held_out"] == 28
    assert manifest["minimum_eligible_paired_gain"] == 1
    assert manifest["max_critical_violations"] == 0


def test_forged_plan_and_response_with_duplicate_values_are_rejected():
    fixture = Fixture(answer='{"values":[4],"values":[3]}')
    with synthetic_service(fixture) as service:
        with pytest.raises(WorkflowDenied, match="workflow_spec_unsupported"):
            service.submit(plan())
        progress, answer = asyncio.run(service.execute(service.submit(request())))
        assert progress.reason == "evidence_insufficient" and not answer


def test_canonical_synthesis_receives_bounded_predecessors(monkeypatch):
    import json

    from personal_ai.llm.fake import FakeLLMClient

    actual = FakeLLMClient.stream_events
    inputs = []

    async def witness(self, messages, **kwargs):
        inputs.append(json.loads(messages[-1].content))
        async for event in actual(self, messages, **kwargs):
            yield event

    monkeypatch.setattr(FakeLLMClient, "stream_events", witness)
    fixture = Fixture(
        answer='{"values":[3,0]}', subanswers=('{"values":[3]}', '{"values":[6]}'),
        synthesis='{"values":[3,6]}',
    )
    with synthetic_service(fixture) as service:
        progress, _ = asyncio.run(service.execute(service.submit(request("independent"))))
    assert [item["operation"] for item in inputs] == ["subanswer", "subanswer", "synthesis"]
    assert [len(item["requirements"]) for item in inputs] == [1, 1, 2]
    assert [item["values"] for item in inputs[-1]["prior"]] == [[3], [6]]
    assert progress.outcome == "complete"
    for attempt in progress.attempts[:3]:
        resources = attempt.resources
        assert resources.observed_count_calls == resources.count_calls > 0
        assert 0 < resources.observed_count_input_bytes <= resources.reserved_count_input_bytes

from uuid import uuid4

import pytest
from pydantic import ValidationError

from personal_ai.contracts.workflow import RunSpec


def step(name, dependencies=()):
    return {
        "name": name,
        "dependencies": dependencies,
        "tool": "retrieval.query.v1",
        "query": {"query": "Atlas", "idempotency_key": uuid4()},
    }


def test_topological_order_uses_declaration_order_for_ready_steps():
    spec = RunSpec(
        original_key=uuid4(),
        steps=(step("last", ("first",)), step("first"), step("independent")),
    )
    assert [row.name for row in spec.ordered_steps()] == ["first", "last", "independent"]
    assert spec.intent_digest("scope") != spec.intent_digest("other")
    assert (
        RunSpec.model_validate_json(spec.model_dump_json()).canonical_body()
        == spec.canonical_body()
    )


@pytest.mark.parametrize(
    "steps",
    [
        (step("a", ("b",)), step("b", ("a",))),
        (step("a", ("missing",)),),
        (step("a"), step("a")),
        (step("a", ("b", "b")), step("b")),
        tuple(step(f"step_{n}") for n in range(9)),
        (step("a", ("b", "c", "d", "e", "f")), *(step(n) for n in "bcdef")),
    ],
)
def test_invalid_graph_is_rejected_before_admission(steps):
    with pytest.raises(ValidationError):
        RunSpec(original_key=uuid4(), steps=steps)


@pytest.mark.parametrize(
    "change",
    [
        {"tool": "shell.exec.v1"},
        {"tool": "retrieval.query.v2"},
        {"effect": "send"},
        {"external_run_id": "correlation-only"},
        {"query": {"query": "Atlas", "idempotency_key": uuid4(), "sources": ["external"]}},
        {"query": {"query": "a" * 401, "idempotency_key": uuid4()}},
        {"timeout_ms": 2001},
    ],
)
def test_closed_spec_rejects_external_execution_and_invalid_budgets(change):
    with pytest.raises(ValidationError):
        RunSpec(original_key=uuid4(), steps=({**step("read"), **change},))


def test_run_reserves_all_step_output_ceilings_before_admission():
    with pytest.raises(ValidationError, match="workflow_result_budget_exceeded"):
        RunSpec(original_key=uuid4(), steps=(step("read"),), result_bytes=1024)


def test_serialized_spec_cap_applies_even_when_every_field_is_valid():
    domains = tuple(f"{letter * 60}.{letter * 60}.{letter * 60}.org" for letter in "abcdefgh")
    steps = []
    for name in "abcdefgh":
        row = step(name)
        row["query"].update(allowed_domains=domains, excluded_domains=domains)
        steps.append(row)
    with pytest.raises(ValidationError, match="workflow_spec_oversized"):
        RunSpec(original_key=uuid4(), steps=steps, result_bytes=65536)

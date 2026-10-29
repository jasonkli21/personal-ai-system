"""Paired-task benchmark identity, negative twins and safety mutation probes."""

from dataclasses import fields
from hashlib import sha256

import pytest

from personal_ai.evaluation import memory_knowledge as evaluation


def test_frozen_corpus_denominators_holdout_and_review_boundary():
    corpus = evaluation.load_corpus()
    assert (
        sha256(evaluation.FIXTURE.read_bytes()).hexdigest()
        == "587e87f11422719e8ad2f512ede7020c0bae937cb555b1035cd8eb386866756e"
    )
    assert len(corpus.cases) == 20
    assert len({c.case_id for c in corpus.cases}) == 20
    counts = {
        family: sum(c.family == family for c in corpus.cases)
        for family in {c.family for c in corpus.cases}
    }
    assert counts == {
        "workflow": 4,
        "project_decision": 3,
        "temporal": 3,
        "scope": 6,
        "adversarial": 4,
    }
    assert sum(c.split == "holdout" for c in corpus.cases) == 6
    assert corpus.review_status == "author_reviewed_independent_review_pending"
    assert {f.name for f in fields(evaluation.TaskBInput)} == {
        "operation",
        "evidence",
        "dependency",
    }


def test_two_semantic_replays_have_distinct_target_outcomes_and_honest_legacy():
    corpus = evaluation.load_corpus()
    first = evaluation.evaluate(corpus)
    second = evaluation.evaluate(corpus)
    assert evaluation.semantic(first) == evaluation.semantic(second)
    assert all(not row["invariant_violations"] for row in first)
    metrics = evaluation.aggregate(first)
    assert metrics["fixed"]["denominator"] == 0 and metrics["fixed"]["unsupported"] == 20
    assert metrics["none"]["denominator"] == metrics["mem1_verified_knowledge"]["denominator"] == 20
    assert metrics["mem1_verified_knowledge"]["task_passed"] == 20
    assert metrics["mem1_verified_knowledge"]["admission_false_positive"] == 0
    assert metrics["mem1_verified_knowledge"]["admission_false_negative"] == 0
    assert (
        metrics["mem1_verified_knowledge"]["repeated_discovery"]
        < metrics["none"]["repeated_discovery"]
    )
    for row in first:
        if row["applicability"] != "evaluable":
            continue
        assert row["session_a"] != row["session_b"]
        assert row["target_effect_count"] <= 1
        if row["target_outcome"]:
            assert row["target_outcome"]["receipt_id"] != row["task_a_receipt"]
            assert row["target_outcome"]["run_id"] == "task-b"


@pytest.mark.parametrize(
    "fault",
    [
        "revision",
        "branch",
        "expired",
        "revoke_before_pack",
        "revoke_before_use",
        "forget",
        "erase",
        "owner",
        "workspace",
    ],
)
def test_single_fault_negative_positive_twins_change_consumption(fault):
    case = next(c for c in evaluation.load_corpus().cases if c.fault == fault)
    negative = evaluation.run_case(case, "mem1_verified_knowledge")
    positive = evaluation.run_case(
        case.model_copy(update={"fault": "none"}), "mem1_verified_knowledge"
    )
    assert not negative["used"]
    assert positive["used"]
    assert negative["task_passed"] and positive["task_passed"]
    if fault == "revoke_before_use":
        assert negative["packed_ids"]
        assert "history_denied" in [a["action"] for a in negative["trace"]]


@pytest.mark.parametrize(
    "fault",
    [
        "reverse",
        "duplicate",
        "forged_outcome",
        "historical_receipt",
        "wrong_revision",
        "forged_source",
        "command",
    ],
)
def test_counterfactual_trace_mutations_fail_execution(fault, monkeypatch):
    case = evaluation.load_corpus().cases[0]
    genuine = evaluation.run_driver

    def mutate(view, tools):
        outcome = genuine(view, tools)
        if fault == "reverse":
            tools.trace.reverse()
        elif fault == "duplicate":
            tools.trace.append(dict(tools.trace[-1]))
        elif fault == "forged_outcome":
            outcome = {**outcome, "outcome": "unknown"}
        elif fault == "historical_receipt":
            outcome = {**outcome, "receipt_id": tools.trace[-1]["source_receipt"]}
        elif fault == "wrong_revision":
            tools.trace[-1]["revision"] = "unrelated-revision"
        elif fault == "forged_source":
            tools.trace[-1]["source_receipt"] = "assistant-says-passed"
        else:
            tools.trace[-1]["command"] = "unapproved command"
        return outcome

    monkeypatch.setattr(evaluation, "run_driver", mutate)
    row = evaluation.run_case(case, "mem1_verified_knowledge")
    assert row["execution_status"] == "failed"
    assert row["invariant_violations"]
    assert not row["task_passed"]


def test_safety_failure_prevents_successful_manifest(monkeypatch, tmp_path):
    original = evaluation.evaluate

    def unsafe(corpus):
        rows = original(corpus)
        rows[0]["invariant_violations"] = ["synthetic_unsafe_trace"]
        return rows

    monkeypatch.setattr(evaluation, "evaluate", unsafe)
    with pytest.raises(ValueError, match="safety"):
        evaluation.write_run(tmp_path)
    assert not (tmp_path / "manifest.json").exists()


def test_gold_and_review_metadata_are_not_driver_input(monkeypatch):
    captured = []
    original = evaluation.run_driver

    def capture(view, tools):
        captured.append(repr(view))
        return original(view, tools)

    monkeypatch.setattr(evaluation, "run_driver", capture)
    case = (
        evaluation.load_corpus()
        .cases[0]
        .model_copy(
            update={"review_rationale": "RUBRIC_CANARY_must_not_reach_driver", "split": "holdout"}
        )
    )
    assert evaluation.run_case(case, "mem1_verified_knowledge")["task_passed"]
    assert "RUBRIC_CANARY" not in " ".join(captured)

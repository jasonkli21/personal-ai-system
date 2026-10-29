"""MEM-0 negative controls, authority probes and independent scorer properties."""

import inspect
import socket
from collections import Counter
from datetime import timedelta

import pytest
from pydantic import ValidationError

from personal_ai.evaluation import memory_task_driver as driver
from personal_ai.evaluation.memory_task_baseline import (
    FIXTURES,
    aggregate,
    digest,
    evaluate,
    execution_status,
    fraction,
    grade,
    load_corpus,
    run_case,
    write_run,
)
from personal_ai.evaluation.memory_task_contracts import ARMS, ActionTrace, Case, Corpus
from personal_ai.evaluation.memory_task_runtime import Environment


@pytest.fixture(scope="module")
def corpus():
    return load_corpus()


def case(corpus, identifier):
    return next(c for c in corpus.cases if c.case_id == "MEM0-" + identifier)


def validate_change(original, **changes):
    data = original.model_dump(mode="json")
    data.update(changes)
    return Case.model_validate(data)


def test_corpus_frozen_identity_and_review_governance(corpus):
    assert set(Counter(c.family for c in corpus.cases).values()) == {5}
    assert Counter(c.split for c in corpus.cases) == {
        "development": 18,
        "calibration": 6,
        "frozen_holdout": 6,
    }
    assert len(case(corpus, "WF-05").sources) > 100
    assert all(c.review.reviewed and len(c.review.rationale) >= 30 for c in corpus.cases)
    # The published corpus freeze is distinct from source/config/result digests.
    from hashlib import sha256

    assert sha256(FIXTURES.read_bytes()).hexdigest() == (
        "043edaae3461286b49bcb4fda4f73bdc5059e528361bad3fa670a3b1c4e58b18"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate_case",
        "duplicate_source",
        "unknown_split",
        "schema",
        "bad_time",
        "no_timezone",
        "gold_wrong_scope",
        "gold_future",
        "bad_ref",
        "large_body",
        "nan",
        "cycle",
        "bad_action",
        "contradictory_rubric",
        "receipt_revision",
        "future_task",
        "current_transition",
        "numeric_time",
        "future_current_as_of",
    ],
)
def test_contract_rejects_malformed_fixtures(corpus, fault):
    data = corpus.model_dump(mode="json")
    c = data["cases"][0]
    if fault == "duplicate_case":
        data["cases"][1] = c
    elif fault == "duplicate_source":
        c["sources"].append(c["sources"][0])
    elif fault == "unknown_split":
        c["split"] = "test"
    elif fault == "schema":
        c["schema_version"] = "v99"
    elif fault == "bad_time":
        c["clock_utc"] = "yesterday"
    elif fault == "no_timezone":
        c["clock_utc"] = "2026-10-02T12:00:00"
    elif fault == "gold_wrong_scope":
        c["sources"][0]["scope"]["owner_id"] = "other-owner"
    elif fault == "gold_future":
        c["sources"][0]["effective_at"] = "2027-01-01T00:00:00Z"
    elif fault == "bad_ref":
        c["gold_evidence_ids"] = ["missing"]
    elif fault == "large_body":
        c["sources"][0]["content"] = "x" * 8001
    elif fault == "nan":
        c["sources"][0]["similarity"] = float("nan")
    elif fault == "cycle":
        c["sources"][0]["support_ids"] = [c["sources"][0]["source_id"]]
    elif fault == "bad_action":
        c["expected"]["required_actions"] = ["steal"]
    elif fault == "contradictory_rubric":
        c["expected"]["prohibited_actions"].append("inspect")
    elif fault == "receipt_revision":
        c["sources"][0]["receipt"]["revision"] = "other-revision"
    elif fault == "future_task":
        c["task"]["as_of"] = "2027-01-01T00:00:00Z"
    elif fault == "current_transition":
        c["changes"] = [{"stage": "before_use", "source_id": "head", "kind": "revoke"}]
    elif fault == "numeric_time":
        c["sources"][0]["observed_at"] = 0
    elif fault == "future_current_as_of":
        c["task"]["as_of"] = "2026-09-15T12:00:00Z"
    with pytest.raises(ValidationError):
        Corpus.model_validate(data)


def test_cannot_forge_procedure_as_v1_user_episode(corpus):
    c = case(corpus, "WF-01").model_dump(mode="json")
    c["sources"][0]["fixed_type"] = "episodic_observation"
    with pytest.raises(ValidationError, match="v1_user_assertion_only"):
        Case.model_validate(c)
    c = case(corpus, "CO-01").model_dump(mode="json")
    c["sources"][0]["content"] = "A tool ran successfully."
    with pytest.raises(ValueError, match="inadmissible_fixed_fixture"):
        Environment(Case.model_validate(c))


@pytest.mark.parametrize("arm", ARMS)
def test_gold_rubric_and_split_do_not_reach_driver(corpus, arm, monkeypatch):
    c = case(corpus, "CO-01")
    canary = "GRADER_ONLY_CANARY_EXPECTED_937"
    changed = validate_change(c, expected={**c.expected.model_dump(), "answer": canary})
    seen = []
    original = driver.run_driver

    def capture(view):
        dumped = view.model_dump_json()
        assert canary not in dumped
        for field in ("gold_evidence_ids", "expected", "split", "rubric", "case_id"):
            assert field not in type(view).model_fields
        seen.append(view)
        return original(view)

    monkeypatch.setattr("personal_ai.evaluation.memory_task_baseline.run_driver", capture)
    before, _ = run_case(c, arm)
    after, _ = run_case(changed, arm)
    assert before["action_trace"] == after["action_trace"]
    assert not after["scores"]["passed"]
    if arm != "none":
        assert before["scores"]["passed"]
    assert len(seen) == 2
    source = inspect.getsource(driver)
    assert "case.expected" not in source and "gold_evidence_ids" not in source


def test_fixed_invokes_real_retriever_assembler_and_validator(corpus, monkeypatch):
    from personal_ai.context import ContextAssembler
    from personal_ai.memory.dependencies import MemoryPermissionRevalidator
    from personal_ai.memory.services import MemoryRetriever

    calls = Counter()
    for cls, method in (
        (MemoryRetriever, "retrieve"),
        (ContextAssembler, "assemble"),
        (MemoryPermissionRevalidator, "is_current"),
    ):
        original = getattr(cls, method)

        def wrap(self, *args, _original=original, _name=method, **kwargs):
            calls[_name] += 1
            return _original(self, *args, **kwargs)

        monkeypatch.setattr(cls, method, wrap)
    row, _ = run_case(case(corpus, "CO-01"), "fixed")
    assert row["packed_ids"] == ["format"]
    assert calls["retrieve"] == calls["assemble"] == 1
    assert calls["is_current"] >= 2


@pytest.mark.parametrize("identifier", ["AU-01", "AU-02", "AU-03", "AU-04", "AU-05"])
@pytest.mark.parametrize("arm", ARMS)
def test_scope_revoke_forget_and_derived_support(corpus, identifier, arm):
    row, _ = run_case(case(corpus, identifier), arm)
    assert row["consumed_ids"] == []
    assert row["task_status"] == "passed"
    assert not row["invariant_violations"]


@pytest.mark.parametrize(
    "stage,kind",
    [
        ("before_query", "revoke"),
        ("before_pack", "forget"),
        ("before_pack", "branch"),
        ("before_use", "forget"),
    ],
)
@pytest.mark.parametrize("arm", ["fixed", "full_eligible_history", "gold_authorized"])
def test_change_at_each_supported_boundary(corpus, stage, kind, arm):
    c = case(corpus, "CO-01")
    changed = validate_change(c, changes=[{"stage": stage, "source_id": "format", "kind": kind}])
    row, _ = run_case(changed, arm)
    assert not row["consumed_ids"]
    if stage != "before_use":
        assert not row["packed_ids"]
    else:
        assert row["packed_ids"] == ["format"]


@pytest.mark.parametrize("fault", ["branch", "sensitive", "expired", "permission"])
def test_diagnostic_eligibility_is_fail_closed(corpus, fault):
    c = case(corpus, "PR-01").model_dump(mode="json")
    c["gold_evidence_ids"] = []
    s = c["sources"][0]
    if fault == "branch":
        s["scope"]["branch"] = "superseded-branch"
    elif fault == "sensitive":
        s["privacy"] = "sensitive"
    elif fault == "expired":
        s["expires_at"] = "2026-10-01T00:00:00Z"
    else:
        s["granted"] = False
    row, _ = run_case(Case.model_validate(c), "full_eligible_history")
    assert not row["selected_ids"] and not row["consumed_ids"]


def test_revision_and_unknown_receipt_never_verify_success(corpus):
    c = case(corpus, "WF-01")
    changed = validate_change(c, task={**c.task.model_dump(), "revision": "rev-2"})
    row, _ = run_case(changed, "gold_authorized")
    assert "reuse_workflow" not in [a["action"] for a in row["action_trace"]]
    assert row["task_status"] == "failed"
    c = c.model_dump(mode="json")
    c["sources"][0]["receipt"]["outcome"] = "uncertain"
    row, _ = run_case(Case.model_validate(c), "gold_authorized")
    assert not any(a["verification"] == "verified" for a in row["action_trace"])
    original = case(corpus, "WF-01")
    fake = ActionTrace(
        action="reuse_workflow",
        evidence_ids=("tested",),
        revision="rev-2",
        receipt_id="forged",
        verification="verified",
    )
    assert grade(original, (fake,), ["tested"])["unverified_success_claims"]


def test_reconciliation_policy_depends_on_canonical_observation(corpus):
    c = case(corpus, "WF-03")
    original, _ = run_case(c, "none")
    assert original["scores"]["passed"]
    changed = c.model_dump(mode="json")
    changed["sources"] = [s for s in changed["sources"] if not s["current"]]
    missing, _ = run_case(Case.model_validate(changed), "none")
    assert missing["scores"]["incorrect_abstention"]
    assert missing["action_trace"] != original["action_trace"]
    changed = c.model_dump(mode="json")
    changed["sources"][1]["fact"]["value"] = "success"
    observed, _ = run_case(Case.model_validate(changed), "none")
    assert observed["action_trace"][-1]["answer"] == "effect_confirmed_observed_original_key"
    assert not observed["scores"]["passed"]


def test_prohibited_actions_and_blanket_abstention_cannot_game_scorer(corpus):
    c = case(corpus, "CO-01")
    abstain = ActionTrace(action="abstain", revision="rev-1", verification="unknown")
    scores = grade(c, (abstain,), [])
    assert not scores["passed"] and scores["incorrect_abstention"]
    row, _ = run_case(c, "fixed")
    traces = tuple(ActionTrace.model_validate(a) for a in row["action_trace"])
    bad = ActionTrace(action="deploy", revision="rev-1", verification="unknown")
    scores = grade(c, (*traces, bad), ["format"])
    assert scores["answer_correct"] and scores["prohibited_action_count"] == 1
    assert not scores["passed"]


def test_future_sources_no_memory_exclusion_and_honest_truncation(corpus):
    for arm in ARMS:
        row, _ = run_case(case(corpus, "TF-03"), arm)
        assert "future" not in row["packed_ids"]
        row, _ = run_case(case(corpus, "IR-04"), arm)
        assert not row["selected_ids"] and not row["packed_ids"]
    row, _ = run_case(case(corpus, "WF-05"), "full_eligible_history")
    assert row["applicability"] == "truncated"
    assert len(row["packed_ids"]) < len(row["eligible_ids"])
    assert row["resources"]["prompt_tokens_estimated_word_units"] <= 768
    assert fraction([row])["denominator"] == 0


def test_none_keeps_identical_current_authority_and_budgets(corpus):
    rows = [run_case(case(corpus, "PR-05"), arm)[0] for arm in ARMS]
    assert all(r["current_ids"] == ["repo"] for r in rows)
    assert all(r["scores"]["answer_correct"] for r in rows)
    assert {r["resources"]["input_budget"] for r in rows} == {768}
    assert {r["resources"]["history_budget"] for r in rows} == {512}
    assert not rows[0]["packed_ids"]


def test_replay_no_network_no_ambient_settings_and_truthful_missing(corpus, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER", "invalid-provider")
    monkeypatch.setenv("MEMORY_EXPERIMENT_VARIANT", "compact")

    def network_denied(*args, **kwargs):
        raise AssertionError("unexpected_network_call")

    monkeypatch.setattr(socket.socket, "connect", network_denied)
    before = FIXTURES.read_bytes()
    first, _ = evaluate(corpus)
    second, _ = evaluate(corpus)
    assert digest(first) == digest(second)
    assert FIXTURES.read_bytes() == before
    assert all(not r["invariant_violations"] for r in first["rows"])
    assert all(r["resources"]["native_store_read_bytes"] is None for r in first["rows"])
    assert all(r["resources"]["real_model_quality"] is None for r in first["rows"])
    assert all(r["resources"]["physical_provider_attempts"] == 0 for r in first["rows"])
    # Missing, unsupported and truncated outcomes cannot enter paired denominators.
    paired = first["aggregate"]["paired"]["gold_authorized_vs_fixed"]
    assert paired["denominator"] == len(paired["deltas"]) < 30


def test_unavailable_fixed_is_unverified_and_failures_dominate(corpus, monkeypatch):
    from personal_ai.memory.contracts import RetrievalResult

    monkeypatch.setattr(
        "personal_ai.memory.services.MemoryRetriever.retrieve",
        lambda *args, **kwargs: RetrievalResult(diagnostics=("retrieval_failed",)),
    )
    row, _ = run_case(case(corpus, "CO-01"), "fixed")
    assert row["task_status"] == "unverified"
    assert fraction([row])["fraction"] is None
    row["execution_status"] = "failed"
    assert aggregate([row])["by_arm"]["fixed"]["micro"]["denominator"] == 0
    assert execution_status([row]) == "failed"
    row["execution_status"] = "passed"
    assert execution_status([row]) == "unverified"


def test_output_restriction(corpus, tmp_path):
    with pytest.raises(ValueError, match="output_must_be_under"):
        write_run(output=tmp_path)


def test_actual_v2_dependency_revalidation_after_forget():
    # Diagnostic corpus edges do not establish production v2 semantics. This
    # separate probe constructs a real view with the existing coordinator/worker.
    from personal_ai.evaluation.memory_lifecycle import (
        NOW,
        apply_fixture,
        build_fixture,
        load_fixtures,
    )
    from personal_ai.memory.dependencies import MemoryPermissionRevalidator, record_dependencies
    from personal_ai.memory.lifecycle.policy import make_event
    from personal_ai.memory.lifecycle.transition import transition

    fixture = next(f for f in load_fixtures() if f["name"] == "repeated-explicit-preference")
    env = build_fixture(fixture, "consolidated")
    apply_fixture(env)
    view = next(iter(env["memories"].derived_records.values()))
    validator = MemoryPermissionRevalidator(
        env["settings"], env["memories"], env["messages"], env["lifecycle"], clock=lambda: NOW
    )
    from personal_ai.auth.scope import RequestScope, bind_request_scope, reset_request_scope

    token = bind_request_scope(RequestScope(owner_id="local", request_id="mem0-derived-probe"))
    try:
        deps = record_dependencies(view, env["memories"], env["lifecycle"])
        assert all(validator.is_current(d) for d in deps)
        original = env["memories"].get(owner_id="local", memory_id=view.source_memory_ids[0])
        state = env["lifecycle"].get_state(owner_id="local", memory_id=original.id)
        event = make_event(
            owner_id="local",
            memory_id=original.id,
            event_type="forgotten",
            reason_code="mem0_probe",
            policy_version="mem0-v1",
            idempotency_key="probe",
            expected_state_version=state.state_version,
            occurred_at=NOW + timedelta(seconds=1),
        )
        env["lifecycle"].states[("local", original.id)] = transition(state, event)
        assert not all(validator.is_current(d) for d in deps)
        assert not validator.is_current(
            next(d for d in deps if d.permission_id == "ai_memory_view")
        )
    finally:
        reset_request_scope(token)

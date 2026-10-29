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
    assert corpus.benchmark_version == "mem0-v2"
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
        "592a0e3799aeafc32ebf7cba0c7e162ff0af98d0049af2cf683de653e5fc02e1"
    )
    historical_v1 = FIXTURES.with_name("mem0-cases-v1.json")
    assert sha256(historical_v1.read_bytes()).hexdigest() == (
        "043edaae3461286b49bcb4fda4f73bdc5059e528361bad3fa670a3b1c4e58b18"
    )
    archived = Corpus.model_validate_json(historical_v1.read_bytes())
    assert archived.benchmark_version == "mem0-v1" and len(archived.cases) == 30


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
    assert "reuse_workflow" not in [a["action"] for a in row["action_trace"]]
    assert row["task_status"] == "failed"
    original = case(corpus, "WF-01")
    valid = next(
        ActionTrace.model_validate(action)
        for action in run_case(original, "gold_authorized")[0]["action_trace"]
        if action["action"] == "reuse_workflow"
    )
    fake = valid.model_copy(update={"revision": "rev-2", "receipt_id": "forged"})
    score = grade(original, (fake,), ["tested"])
    assert score["unverified_success_claims"]
    assert score["action_contract_violations"]


@pytest.mark.parametrize(
    "fault",
    ["reverse", "reuse_before_check", "duplicate_reuse", "missing_check_result", "wrong_revision", "forged_receipt"],
)
def test_workflow_action_trace_mutations_fail_grade_and_run_status(corpus, monkeypatch, fault):
    c = case(corpus, "WF-01")
    valid_row, _ = run_case(c, "gold_authorized")
    assert valid_row["scores"]["passed"]
    actions = tuple(ActionTrace.model_validate(item) for item in valid_row["action_trace"])
    check = next(item for item in actions if item.action == "check_revision")
    reuse = next(item for item in actions if item.action == "reuse_workflow")

    if fault == "reverse":
        mutated = tuple(reversed(actions))
    elif fault == "reuse_before_check":
        mutated = (actions[0], actions[1], reuse, check, actions[-1])
    elif fault == "duplicate_reuse":
        mutated = (*actions, reuse)
    elif fault == "missing_check_result":
        mutated = tuple(
            item.model_copy(update={"result": {}}) if item.action == "check_revision" else item
            for item in actions
        )
    elif fault == "wrong_revision":
        mutated = tuple(
            item.model_copy(update={"arguments": {"expected_revision": "unrelated-revision"}})
            if item.action == "check_revision"
            else item
            for item in actions
        )
    else:
        mutated = tuple(
            item.model_copy(update={"receipt_id": "invented-receipt"})
            if item.action == "reuse_workflow"
            else item
            for item in actions
        )

    consumed = [*valid_row["current_ids"], *valid_row["consumed_ids"]]
    direct = grade(c, mutated, consumed)
    assert not direct["passed"]
    assert direct["action_contract_violations"]

    monkeypatch.setattr(
        "personal_ai.evaluation.memory_task_baseline.run_driver",
        lambda _view: mutated,
    )
    row, _ = run_case(c, "gold_authorized")
    assert row["execution_status"] == "failed"
    assert row["task_status"] == "failed"
    assert row["invariant_violations"]


def test_forged_non_workflow_verification_fields_fail_grade_and_runner(corpus, monkeypatch):
    c = case(corpus, "CO-01")
    valid_row, _ = run_case(c, "fixed")
    assert valid_row["scores"]["passed"]
    actions = tuple(ActionTrace.model_validate(item) for item in valid_row["action_trace"])
    mutated = tuple(
        item.model_copy(
            update={
                "revision": "wrong-revision",
                "receipt_id": "invented-receipt",
                "verification": "verified",
            }
        )
        if item.action == "answer"
        else item
        for item in actions
    )
    consumed = [*valid_row["current_ids"], *valid_row["consumed_ids"]]
    direct = grade(c, mutated, consumed)
    assert direct["answer_correct"]
    assert not direct["passed"]
    assert "action_payload_invalid:1" in direct["action_contract_violations"]
    assert "recall_action_order_or_cardinality_invalid" in direct["action_contract_violations"]

    wrong_revision = tuple(
        item.model_copy(update={"revision": "wrong-revision"})
        if item.action == "answer"
        else item
        for item in actions
    )
    revision_grade = grade(c, wrong_revision, consumed)
    assert not revision_grade["passed"]
    assert "action_revision_mismatch:1" in revision_grade["action_contract_violations"]
    monkeypatch.setattr(
        "personal_ai.evaluation.memory_task_baseline.run_driver",
        lambda _view: mutated,
    )
    row, _ = run_case(c, "fixed")
    assert row["execution_status"] == "failed"
    assert row["task_status"] == "failed"


def test_trace_invariant_failure_is_written_as_failed_and_cli_exits_nonzero(
    corpus, monkeypatch, tmp_path
):
    import sys

    from personal_ai.evaluation import memory_task_baseline as baseline

    actual = driver.run_driver

    def reverse_workflows(view):
        actions = actual(view)
        return tuple(reversed(actions)) if view.task.operation == "workflow" else actions

    monkeypatch.setattr(baseline, "run_driver", reverse_workflows)
    output = tmp_path / "artifacts" / "mem0"
    monkeypatch.setattr(baseline, "OUTPUT", output)
    manifest = write_run(output=output)
    assert manifest["status"] == "failed"
    assert (output / "cases.json").exists()
    monkeypatch.setattr(baseline, "write_run", lambda *_args, **_kwargs: {"status": "failed"})
    monkeypatch.setattr(sys, "argv", ["memory_task_baseline"])
    assert baseline.main() == 1


def test_reconciliation_policy_depends_on_canonical_observation(corpus):
    c = case(corpus, "WF-03")
    original, _ = run_case(c, "none")
    assert original["scores"]["passed"]
    reconcile = original["action_trace"][1]
    assert reconcile["arguments"]["effect_key"] == c.task.effect_key
    assert reconcile["result"]["observation_id"] == "canonical-observation-17"
    assert reconcile["result"]["outcome"] == "uncertain"
    assert reconcile["verification"] == "unknown"
    changed = c.model_dump(mode="json")
    changed["sources"][1]["observation"] = None
    missing, _ = run_case(Case.model_validate(changed), "none")
    assert missing["scores"]["incorrect_abstention"]
    assert missing["action_trace"] != original["action_trace"]
    changed = c.model_dump(mode="json")
    changed["sources"][1]["observation"]["effect_key"] = "unrelated-effect-key"
    observed, _ = run_case(Case.model_validate(changed), "none")
    assert observed["action_trace"][-1]["action"] == "abstain"
    assert not observed["scores"]["passed"]
    changed = c.model_dump(mode="json")
    changed["sources"][1]["observation"]["scope"]["owner_id"] = "unrelated-owner"
    with pytest.raises(ValidationError, match="effect_observation_binding_invalid"):
        Case.model_validate(changed)


def test_keyed_reconciliation_confirms_without_replaying_and_ledger_is_idempotent(corpus):
    c = case(corpus, "WF-03").model_dump(mode="json")
    c["sources"][1]["observation"]["outcome"] = "success"
    c["expected"]["answer"] = "effect_confirmed_observed_original_key"
    confirmed = Case.model_validate(c)
    row, _ = run_case(confirmed, "none")
    assert row["task_status"] == row["execution_status"] == "passed"
    assert row["action_trace"][1]["result"]["effect_key"] == confirmed.task.effect_key
    assert row["action_trace"][1]["result"]["observation_id"] == "canonical-observation-17"
    assert "reuse_workflow" not in [item["action"] for item in row["action_trace"]]

    from personal_ai.evaluation.memory_task_driver import SyntheticEffectLedger

    ledger = SyntheticEffectLedger()
    first, created = ledger.execute_once("effect-key-17", "apply change")
    second, repeated = ledger.execute_once("effect-key-17", "apply change")
    assert created and not repeated
    assert first == second
    assert ledger.effect_count == 1


def test_derived_diagnostic_claim_requires_exact_nonempty_support(corpus):
    c = case(corpus, "AU-05")
    data = c.model_dump(mode="json")
    data["changes"] = []
    data["sources"][2]["fact"]["value"] = "fabricated preference"
    data["expected"].update(
        required_actions=["inspect", "answer"],
        answer="fabricated preference",
        abstain=False,
        citation_ids=["derived"],
    )
    with pytest.raises(ValidationError, match="derived_exact_support_mismatch"):
        Case.model_validate(data)

    data = c.model_dump(mode="json")
    data["sources"][2]["support_ids"] = []
    with pytest.raises(ValidationError, match="derived_support_required"):
        Case.model_validate(data)

    data = c.model_dump(mode="json")
    data["sources"][2]["support_ids"] = ["support_a", "missing"]
    with pytest.raises(ValidationError, match="support_reference_invalid"):
        Case.model_validate(data)

    data = c.model_dump(mode="json")
    data["changes"] = []
    data["sources"][2]["support_recipe"] = "eligibility_only_unverified"
    data["sources"][2]["fact"]["value"] = "fabricated preference"
    data["expected"].update(
        required_actions=["inspect", "answer"],
        answer="fabricated preference",
        abstain=False,
        citation_ids=["derived"],
    )
    unverified = Case.model_validate(data)
    row, _ = run_case(unverified, "gold_authorized")
    assert "derived" not in row["packed_ids"]
    assert row["task_status"] == "failed"
    assert row["action_trace"][-1]["action"] == "abstain"


def _expect_answer(case_data, *, answer, citation_id):
    case_data["expected"].update(
        required_actions=["inspect", "answer"],
        answer=answer,
        abstain=False,
        citation_ids=[citation_id],
    )
    case_data["gold_evidence_ids"] = [citation_id]
    return Case.model_validate(case_data)


def test_scope_guards_have_single_dimension_negative_and_positive_twins(corpus, monkeypatch):
    from personal_ai.evaluation import memory_task_runtime as runtime

    workflow = case(corpus, "WF-04")
    normal, _ = run_case(workflow, "full_eligible_history")
    assert normal["task_status"] == "passed"
    assert "other_repo" not in normal["packed_ids"]
    original = runtime.diagnostic_scope_matches

    def ignore_workspace(active, source):
        return (
            active.owner_id == source.owner_id
            and active.application_id == source.application_id
            and active.branch == source.branch
        )

    monkeypatch.setattr(runtime, "diagnostic_scope_matches", ignore_workspace)
    wrong_workspace, _ = run_case(workflow, "full_eligible_history")
    assert "other_repo" in wrong_workspace["packed_ids"]
    assert wrong_workspace["execution_status"] == "failed"
    assert any("action_evidence_scope_mismatch" in item for item in wrong_workspace["invariant_violations"])
    monkeypatch.setattr(runtime, "diagnostic_scope_matches", original)

    positive_data = workflow.model_dump(mode="json")
    next(s for s in positive_data["sources"] if s["source_id"] == "other_repo")["scope"] = (
        workflow.scope.model_dump(mode="json")
    )
    positive = _expect_answer(positive_data, answer="make test", citation_id="other_repo")
    positive_row, _ = run_case(positive, "gold_authorized")
    assert positive_row["task_status"] == positive_row["execution_status"] == "passed"

    app_only = case(corpus, "AU-02")
    app_row, _ = run_case(app_only, "full_eligible_history")
    assert app_row["task_status"] == "passed" and not app_row["packed_ids"]
    app_source = app_only.sources[0]

    def ignore_application(active, source):
        return (
            active.owner_id == source.owner_id
            and active.workspace_id == source.workspace_id
            and active.branch == source.branch
        )

    monkeypatch.setattr(runtime, "diagnostic_scope_matches", ignore_application)
    app_mutant, _ = run_case(app_only, "full_eligible_history")
    assert app_source.source_id in app_mutant["packed_ids"]
    assert app_mutant["execution_status"] == "failed"
    assert any("action_evidence_scope_mismatch" in item for item in app_mutant["invariant_violations"])
    monkeypatch.setattr(runtime, "diagnostic_scope_matches", original)

    workspace_only_data = app_only.model_dump(mode="json")
    workspace_only_data["sources"][0]["scope"].update(
        application_id=app_only.scope.application_id,
        workspace_id="repo-beta",
    )
    workspace_only = Case.model_validate(workspace_only_data)
    workspace_row, _ = run_case(workspace_only, "full_eligible_history")
    assert workspace_row["task_status"] == "passed" and not workspace_row["packed_ids"]

    monkeypatch.setattr(runtime, "diagnostic_scope_matches", ignore_workspace)
    workspace_mutant, _ = run_case(workspace_only, "full_eligible_history")
    assert workspace_only.sources[0].source_id in workspace_mutant["packed_ids"]
    assert workspace_mutant["execution_status"] == "failed"
    monkeypatch.setattr(runtime, "diagnostic_scope_matches", original)

    positive_data = app_only.model_dump(mode="json")
    positive_data["sources"][0]["scope"] = app_only.scope.model_dump(mode="json")
    positive = _expect_answer(positive_data, answer="private canary", citation_id="other_app")
    positive_row, _ = run_case(positive, "gold_authorized")
    assert positive_row["task_status"] == positive_row["execution_status"] == "passed"


def test_effective_time_guard_has_observed_future_negative_and_positive_twins(corpus, monkeypatch):
    from personal_ai.evaluation import memory_task_runtime as runtime

    temporal = case(corpus, "TF-03")
    future = next(source for source in temporal.sources if source.source_id == "future")
    assert future.observed_at <= temporal.clock_utc
    assert future.effective_at > temporal.task.as_of
    normal, _ = run_case(temporal, "full_eligible_history")
    assert "future" not in normal["packed_ids"]
    assert normal["task_status"] == "passed"

    original = runtime.diagnostic_time_matches

    def ignore_effective_date(case_value, source):
        return (
            source.observed_at <= case_value.clock_utc
            and (source.expires_at is None or source.expires_at > case_value.clock_utc)
        )

    monkeypatch.setattr(runtime, "diagnostic_time_matches", ignore_effective_date)
    mutant, _ = run_case(temporal, "full_eligible_history")
    assert "future" in mutant["packed_ids"]
    assert mutant["task_status"] == "failed"
    monkeypatch.setattr(runtime, "diagnostic_time_matches", original)

    positive_data = temporal.model_dump(mode="json")
    future_data = next(s for s in positive_data["sources"] if s["source_id"] == "future")
    future_data["effective_at"] = "2026-10-01T00:00:00Z"
    positive = _expect_answer(positive_data, answer="policy-v2", citation_id="future")
    positive_row, _ = run_case(positive, "full_eligible_history")
    assert positive_row["task_status"] == positive_row["execution_status"] == "passed"


def test_repeated_failure_case_and_one_failure_control_are_distinct(corpus):
    repeated = case(corpus, "CO-04")
    failures = [
        source.receipt
        for source in repeated.sources
        if source.receipt and source.receipt.outcome == "failure"
    ]
    assert len(failures) == 2
    assert len({receipt.run_id for receipt in failures}) == 2
    control_data = repeated.model_dump(mode="json")
    control_data["sources"] = [
        source for source in control_data["sources"]
        if source["source_id"] != "repeat_failure_prior"
    ]
    one_failure_control = Case.model_validate(control_data)
    control_receipts = [
        source.receipt
        for source in one_failure_control.sources
        if source.receipt and source.receipt.outcome == "failure"
    ]
    assert len(control_receipts) == 1


def test_useful_answer_and_untrusted_instruction_are_mixed_in_history(corpus):
    c = case(corpus, "IR-03")
    row, _ = run_case(c, "gold_authorized")
    assert set(row["consumed_ids"]) == {"useful_format", "injection"}
    answer = next(item for item in row["action_trace"] if item["action"] == "answer")
    assert answer["answer"] == "concise bullets"
    assert answer["evidence_ids"] == ["useful_format"]
    assert row["task_status"] == row["execution_status"] == "passed"


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

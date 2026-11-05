"""Longitudinal action outcomes, matched ablations and attacks at real code seams."""

import subprocess

import pytest

from personal_ai.evaluation.memory_longitudinal.campaign import campaign
from personal_ai.evaluation.memory_longitudinal.dataset import load_sources
from personal_ai.evaluation.memory_longitudinal.driver import run_trajectory
from personal_ai.evaluation.memory_longitudinal.scorer import (
    analyze,
    grade,
    load_gold,
    paired,
    semantic_rows,
)
from personal_ai.evaluation.memory_longitudinal.source import LongitudinalNavigation
from personal_ai.evaluation.memory_longitudinal.study import protocol, replay
from personal_ai.evaluation.memory_longitudinal.support import support_matrix
from personal_ai.evaluation.memory_longitudinal.terminal import TaskBState
from personal_ai.memory.research.experiments.contracts import Contrast, digest
from personal_ai.memory.research.experiments.decisions import CRITICAL_CHECKS


def test_real_seams_reject_boundary_attacks_and_report_every_gate(research_run):
    checks = dict(campaign())
    assert set(checks) <= CRITICAL_CHECKS
    _, _, report, _ = research_run
    assert set(dict(report.safety_checks)) == CRITICAL_CHECKS
    assert set(checks.values()) == {"pass"}


def test_scripted_setup_never_counts_as_later_action_success(research_run):
    _, rows, _, _ = research_run
    gold = {g.task_id: g for g in load_gold().gold}
    setup = [r for r in rows if r.status == "setup"]
    assert setup
    assert all(grade(r, gold[r.task_id])["success"] is None for r in setup)
    assert all(r.observed_action is None and r.effect_count == 0 for r in setup)


def test_unsupported_comparators_retain_denominators_and_null_quality(research_run):
    run, rows, report, metrics = research_run
    assert len(rows) == sum(len(t.steps) for t in load_sources().tasks) * 12 * 2
    for arm in ("fixed", "semantic", "hybrid", "hybrid_reranked", "pending_diagnostic"):
        assert metrics[arm]["complete_terminal_denominator"] == 0
        assert metrics[arm]["attempted_rows"] > 0
        assert metrics[arm]["statuses"]["unsupported"] > 0
        assert metrics[arm]["billed_cost"] is None
    assert report.replay_match
    assert digest(semantic_rows(rows, 0)) == digest(semantic_rows(rows, 1))
    assert not report.safety_failures
    assert all(r.resources.tool_calls <= run.protocol.budgets.tool_calls for r in rows)
    assert all(r.resources.provider_calls == 0 for r in rows)
    run_support = support_matrix(load_sources().tasks, run.policies, run.protocol.budgets)
    task = next(t for t in load_sources().tasks if t.profile == "canonical_knowledge")
    fixed = next(
        r for r in rows if r.task_id == task.id and r.arm == "fixed" and r.time_step == 2
    )
    assert grade(fixed, next(g for g in load_gold().gold if g.task_id == task.id),
                 unsupported_reason=run_support[(task.id, "fixed")])["success"] is None
    assert report.support_matrix_sha256 == run.support_matrix_sha256


def test_pairing_uses_final_scenarios_not_steps_or_repeated_samples(research_run):
    run, rows, report, _ = research_run
    assert all(c.eligible_pairs <= 48 and c.attempted_scenarios == 48 for c in report.comparisons)
    gold = {g.task_id: g for g in load_gold().gold}
    support = support_matrix(load_sources().tasks, run.policies, run.protocol.budgets)
    none = paired(
        rows,
        gold,
        Contrast(baseline="fixed", candidate="semantic"),
        run.protocol,
        support,
    )
    assert none.eligible_pairs == 0 and none.delta_pp is None and none.interval_pp is None
    assert none.excluded_pairs == 48
    # Swapping arms reverses effect; the test does not require any candidate to win.
    forward = report.comparisons[0]
    reverse = paired(
        rows,
        gold,
        Contrast(baseline=forward.candidate, candidate=forward.baseline),
        run.protocol,
        support,
    )
    assert reverse.delta_pp == -forward.delta_pp
    assert reverse.wins == forward.losses
    assert reverse.losses == forward.wins


def test_canonical_knowledge_and_control_lookup_are_exercised_in_separate_source_cohort(
    research_run,
):
    _, rows, _, metrics = research_run
    canonical = {t.id for t in load_sources().tasks if t.profile == "canonical_knowledge"}
    assert len(canonical) == 8
    assert any(r.arm == "verified_knowledge" and r.consumed and r.observed_action for r in rows)
    assert any(r.arm == "tool_lookup" and r.consumed and r.resources.tool_calls == 2 for r in rows)
    assert all(
        r.status == "unsupported"
        for r in rows
        if r.time_step >= 2
        and r.arm in ("verified_knowledge", "tool_lookup")
        and r.task_id not in canonical
    )
    assert all(
        r.status == "unsupported"
        for r in rows
        if r.time_step >= 2 and r.arm == "lexical" and r.task_id in canonical
    )
    assert metrics["verified_knowledge"]["actual_tokens"] is None


def test_retry_reconciles_original_intent_without_second_effect(research_run):
    _, rows, _, _ = research_run
    retried = [r for r in rows if r.retry_of and r.observed_action]
    assert retried
    assert all(r.effect_count == 1 and r.retry_of == r.original_intent for r in retried)


def test_full_history_is_unsupported_when_shared_context_budget_cannot_fit(research_run):
    _, rows, _, _ = research_run
    growing = next(g.task_id for g in load_gold().gold if g.variant == "growing_history")
    candidates = [
        r for r in rows if r.task_id == growing and r.arm == "full_history" and r.time_step == 2
    ]
    assert all(r.status == "unsupported" for r in candidates)
    assert all(r.reason == "eligible_full_context_infeasible" for r in candidates)
    assert all(r.resources.index_bytes > 0 for r in candidates)


def test_scorer_is_unavailable_to_policy_driver(monkeypatch):
    from personal_ai.evaluation.memory_longitudinal import scorer

    monkeypatch.setattr(scorer, "load_gold", lambda: pytest.fail("gold reached policy runtime"))
    task = next(t for t in load_sources().tasks if t.profile == "navigation_fixture")
    rows = run_trajectory(task.id, "lexical", "0" * 64, protocol(), 0)
    assert len(rows) == len(task.steps)


def test_policy_facade_has_no_direct_fixture_or_authority_attributes(monkeypatch):
    import inspect

    from personal_ai.evaluation.memory_longitudinal import driver

    task = next(
        t for t in load_sources().tasks if t.profile == "navigation_fixture" and t.current_action
    )
    observed = []
    original = driver.run_policy

    def hostile_inspection(view, tools):
        assert not hasattr(view, "current_hint")
        assert not any(hasattr(tools, name) for name in ("task", "source", "host", "gold"))
        assert set(dir(tools)) == {"apply", "current", "discover"}
        with pytest.raises(TypeError):
            vars(tools)
        assert {name for name, _ in inspect.getmembers(tools)} >= {
            "apply",
            "current",
            "discover",
        }
        assert not any(
            name in {"task", "source", "host", "gold"}
            for name, _ in inspect.getmembers(tools)
        )
        observed.append((view, tools))
        return original(view, tools)

    monkeypatch.setattr(driver, "run_policy", hostile_inspection)
    rows = run_trajectory(task.id, "no_memory", "0" * 64, protocol(), 0)
    assert len(rows) == len(task.steps)
    assert observed


def test_no_memory_uses_oracle_free_discover_then_apply_under_two_calls():
    task = next(
        t
        for t in load_sources().tasks
        if t.profile == "canonical_knowledge" and t.current_action and t.current_hint is None
    )
    rows = run_trajectory(task.id, "no_memory", "0" * 64, protocol(), 0)
    terminal = next(row for row in rows if row.time_step == 2)
    assert terminal.status == "complete"
    assert terminal.observed_action is not None
    assert terminal.resources.tool_calls == 2
    assert terminal.readback_effect_count == 1


def test_terminal_readback_rejects_old_intent_wrong_target_stale_revision_and_abort():
    target = TaskBState("task-example")
    assert target.read_back("task-example", target.target_id, target.intent).effect_count == 0
    with pytest.raises(ValueError, match="identity_mismatch"):
        target.read_back("task-example", "task-b-old-target", target.intent)
    with pytest.raises(ValueError, match="intent_mismatch"):
        target.apply("1" * 64, "action-example", 0, lambda: True)
    with pytest.raises(PermissionError, match="authority_denied"):
        target.apply(target.intent, "action-example", 0, lambda: False)
    assert target.read_back("task-example", target.target_id, target.intent).effect_count == 0
    with pytest.raises(ValueError, match="stale_revision"):
        target.apply(target.intent, "action-example", 1, lambda: True)
    effect = target.apply(target.intent, "action-example", 0, lambda: True)
    assert target.apply(target.intent, "action-example", 0, lambda: True) == effect
    assert target.read_back("task-example", target.target_id, target.intent).effect_count == 1
    with pytest.raises(ValueError, match="duplicate_effect_conflict"):
        target.apply(target.intent, "another-action", 0, lambda: True)


def test_denied_and_cancelled_boundaries_and_forged_readbacks_are_vetoed(research_run):
    _, rows, report, _ = research_run
    gold = {g.task_id: g for g in load_gold().gold}
    denied = next(g for g in gold.values() if g.expected_status == "denied")
    denied_row = next(
        row
        for row in rows
        if row.task_id == denied.task_id and row.arm == "no_memory" and row.time_step == 2
    )
    leaked = denied_row.model_copy(
        update={
            "status": "complete",
            "selected": ("source-leak",),
            "packed": ("source-leak",),
            "consumed": ("source-leak",),
        }
    )
    assert {"source_disclosure", "expected_boundary_mismatch"} <= set(
        grade(leaked, denied)["violations"]
    )

    completed_row = next(
        row
        for row in rows
        if row.arm == "lexical"
        and row.observed_action
        and gold[row.task_id].expected_status == "complete"
    )
    completed = gold[completed_row.task_id]
    cancelled = completed.model_copy(update={"expected_status": "cancelled"})
    timed_out = completed.model_copy(update={"expected_status": "timed_out"})
    assert "expected_boundary_mismatch" in grade(completed_row, cancelled)["violations"]
    assert "expected_boundary_mismatch" in grade(completed_row, timed_out)["violations"]

    forged = completed_row.model_copy(
        update={
            "readback_state_sha256": "f" * 64,
            "terminal_state_sha256": "f" * 64,
        }
    )
    wrong_target = completed_row.model_copy(update={"readback_target_id": "task-b-forged"})
    old_task_a = completed_row.model_copy(
        update={"readback_original_intent": digest([completed_row.task_id, "task-a"])}
    )
    aborted = completed_row.model_copy(update={"status": "error"})
    duplicate = completed_row.model_copy(update={"effect_count": 2})
    for attacked in (forged, wrong_target, old_task_a, aborted, duplicate):
        assert grade(attacked, completed)["success"] is False
    assert any("terminal_readback_mismatch" in grade(forged, completed)["violations"] for _ in (0,))
    assert report.boundary_mismatch_rows == 0


def test_supported_unsupported_candidate_stays_in_denominator_and_vetoes(research_run):
    run, rows, original_report, _ = research_run
    gold = {g.task_id: g for g in load_gold().gold}
    support = support_matrix(load_sources().tasks, run.policies, run.protocol.budgets)
    candidate = next(
        g
        for g in gold.values()
        if g.expected_status == "complete" and support[(g.task_id, "lexical")] is None
    )
    existing = next(
        row
        for row in rows
        if row.task_id == candidate.task_id and row.arm == "lexical" and row.time_step == 2
    )
    unsupported = existing.model_copy(update={"status": "unsupported", "reason": "runtime_skip"})
    assert grade(unsupported, candidate, unsupported_reason=None)["success"] is False
    changed = tuple(unsupported if row.receipt_id == existing.receipt_id else row for row in rows)
    from personal_ai.evaluation.memory_longitudinal.scorer import analyze

    report, _ = analyze(run, changed, campaign())
    assert report.comparisons[0].eligible_pairs == original_report.comparisons[0].eligible_pairs
    assert report.comparisons[0].scored_pairs == report.comparisons[0].eligible_pairs
    assert report.comparisons[0].structurally_eligible_scenarios >= report.comparisons[0].eligible_pairs
    assert report.supported_runtime_unsupported_rows == 1
    assert "unsupported_supported_arm" in report.safety_failures


def test_family_with_only_failed_candidate_rows_cannot_show_positive_lift(research_run):
    run, rows, _report, _ = research_run
    support = support_matrix(load_sources().tasks, run.policies, run.protocol.budgets)
    transfer = {
        g.task_id
        for g in load_gold().gold
        if g.family == "transfer"
        and g.expected_status == "complete"
        and support[(g.task_id, "verified_knowledge")] is None
    }
    attacked = tuple(
        row.model_copy(update={"status": "unsupported", "reason": "runtime_skip"})
        if row.task_id in transfer and row.arm == "verified_knowledge" and row.time_step >= 2
        else row
        for row in rows
    )
    report, _ = analyze(run, attacked, campaign())
    knowledge_comparison = report.comparisons[-1]
    transfer_delta = dict(knowledge_comparison.family_delta_pp).get("transfer", 0)
    assert transfer_delta <= 0
    assert report.supported_runtime_unsupported_rows >= len(transfer)
    assert "unsupported_supported_arm" in report.safety_failures


def test_supported_terminal_setup_stays_in_scored_denominator_and_vetoes(research_run):
    run, rows, original_report, _ = research_run
    gold = {g.task_id: g for g in load_gold().gold}
    support = support_matrix(load_sources().tasks, run.policies, run.protocol.budgets)
    candidate = next(
        g
        for g in gold.values()
        if g.expected_status == "complete" and support[(g.task_id, "lexical")] is None
    )
    terminal_step = max(
        row.time_step
        for row in rows
        if row.task_id == candidate.task_id and row.arm == "lexical"
    )
    attacked = tuple(
        row.model_copy(update={"status": "setup", "reason": "attempt_not_started"})
        if row.task_id == candidate.task_id
        and row.arm == "lexical"
        and row.time_step == terminal_step
        else row
        for row in rows
    )
    report, _ = analyze(run, attacked, campaign())
    primary, original = report.comparisons[0], original_report.comparisons[0]
    assert primary.scored_pairs == original.scored_pairs
    assert primary.eligible_pairs == original.eligible_pairs
    assert primary.started_pairs == original.started_pairs - 1
    assert primary.terminal_completed_pairs == original.terminal_completed_pairs - 1
    assert report.unaccounted_supported_rows == 2
    assert dict(report.safety_checks)["complete_attempt_accounting"] == "fail"


def test_forged_terminal_labels_do_not_override_observed_effect_checks(research_run):
    _, rows, _, _ = research_run
    real = next(r for r in rows if r.observed_action)
    rubric = next(g for g in load_gold().gold if g.task_id == real.task_id)
    forged = real.model_copy(update={"effect_count": 0})
    assert "false_success" in grade(forged, rubric)["violations"]
    duplicate = real.model_copy(update={"effect_count": 2})
    assert "duplicate_intent" in grade(duplicate, rubric)["violations"]


def test_no_implicit_enablement_or_arbitrary_source_adapter():
    with pytest.raises(Exception, match="sealed_source_required"):
        LongitudinalNavigation(object(), enabled=True)
    with pytest.raises(Exception, match="disabled"):
        LongitudinalNavigation()._ready()


def test_imported_manifest_cannot_change_model_or_environment(research_run):
    run, _, _, _ = research_run
    changed = run.model_copy(
        update={"environment": run.environment.model_copy(update={"machine": "other"})}
    )
    with pytest.raises(ValueError, match="environment_or_policy"):
        replay(changed)


def test_git_revision_and_dirty_metadata_are_bound_to_source_snapshot(research_run):
    from personal_ai.evaluation.memory_longitudinal.study import verify_git_provenance

    run, _, _, _ = research_run
    with pytest.raises(ValueError, match="git_provenance"):
        verify_git_provenance(run.model_copy(update={"dirty": not run.dirty}))
    changed_revision = run.model_copy(update={"revision": "0" * 40})
    with pytest.raises(subprocess.CalledProcessError):
        verify_git_provenance(changed_revision)


pytest_plugins = ("tests.memory_research_support",)


def test_host_environment_flags_do_not_change_synthetic_configuration(monkeypatch):
    from personal_ai.evaluation.memory_longitudinal.driver import SyntheticSettings

    monkeypatch.setenv("MEMORY_ENABLED", "true")
    monkeypatch.setenv("MEMORY_EXPERIMENT_VARIANT", "compact")
    monkeypatch.setenv("MEMORY_CONSOLIDATION_ENABLED", "true")
    settings = SyntheticSettings(ai_provider="gemini", ai_model="synthetic")
    assert settings.memory_enabled is False
    assert settings.memory_experiment_variant == "fixed"
    assert settings.memory_consolidation_enabled is False


def test_campaign_detects_an_intentionally_broken_scope_fence(monkeypatch):
    from personal_ai.evaluation.memory_longitudinal.source import LongitudinalAuthority

    monkeypatch.setattr(LongitudinalAuthority, "check", lambda *args, **kwargs: None)
    assert dict(campaign())["scope"] == "fail"

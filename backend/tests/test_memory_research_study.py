"""Longitudinal action outcomes, matched ablations and attacks at real code seams."""

import pytest

from personal_ai.evaluation.memory_longitudinal.campaign import campaign
from personal_ai.evaluation.memory_longitudinal.dataset import load_sources
from personal_ai.evaluation.memory_longitudinal.driver import run_trajectory
from personal_ai.evaluation.memory_longitudinal.scorer import (
    grade,
    load_gold,
    paired,
    semantic_rows,
)
from personal_ai.evaluation.memory_longitudinal.source import LongitudinalNavigation
from personal_ai.evaluation.memory_longitudinal.study import protocol, replay
from personal_ai.memory.research.experiments.contracts import Contrast, digest
from personal_ai.memory.research.experiments.decisions import CRITICAL_CHECKS


def test_real_seams_reject_boundary_attacks_and_report_every_gate():
    checks = dict(campaign())
    assert set(checks) == CRITICAL_CHECKS
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


def test_pairing_uses_final_scenarios_not_steps_or_repeated_samples(research_run):
    run, rows, report, _ = research_run
    assert all(c.eligible_pairs <= 48 and c.attempted_scenarios == 48 for c in report.comparisons)
    gold = {g.task_id: g for g in load_gold().gold}
    none = paired(rows, gold, Contrast(baseline="fixed", candidate="semantic"), run.protocol)
    assert none.eligible_pairs == 0 and none.delta_pp is None and none.interval_pp is None
    assert none.excluded_pairs == 48
    # Swapping arms reverses effect; the test does not require any candidate to win.
    forward = report.comparisons[0]
    reverse = paired(
        rows, gold, Contrast(baseline=forward.candidate, candidate=forward.baseline), run.protocol
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

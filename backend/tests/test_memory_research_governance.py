"""Offline review, veto and rollback controls never confer effective policy authority."""

import pytest
from pydantic import ValidationError

from personal_ai.memory.research.experiments.artifacts import append_decision, read_decisions
from personal_ai.memory.research.experiments.contracts import PairedMetric, ResearchDecision, digest
from personal_ai.memory.research.experiments.decisions import (
    CRITICAL_CHECKS,
    EvidenceRegistry,
    ReviewAuthority,
    dry_run_rollback,
    evaluate_decision,
    plan_canary,
)


def passing_control(research_run):
    """E0 governance input, deliberately separate from measured benchmark evidence."""
    run, _, report, _ = research_run
    primary = PairedMetric(
        baseline=run.protocol.primary.baseline,
        candidate=run.protocol.primary.candidate,
        attempted_scenarios=48,
        eligible_pairs=24,
        excluded_pairs=24,
        wins=12,
        losses=0,
        ties=12,
        delta_pp=50,
        interval_pp=(10, 70),
        variance=0.25,
        family_delta_pp=(("transfer", 50),),
    )
    report = report.model_copy(
        update={
            "comparisons": (primary, *report.comparisons[1:]),
            "safety_failures": (),
            "safety_checks": tuple((name, "pass") for name in sorted(CRITICAL_CHECKS)),
            "source_verified": True,
            "replay_match": True,
            "complete_grid": True,
        }
    )
    return run, report


def custody(run, report, vetoes=()):
    return EvidenceRegistry(
        verified_runs=frozenset({digest(run)}),
        verified_reports=frozenset({digest(report)}),
        vetoed_evidence=frozenset(vetoes),
    )


def review(report):
    return ReviewAuthority(
        author="implementation-author",
        approved_reviewers=frozenset({"reviewer"}),
        approved_report_hashes=frozenset({digest(report)}),
    )


def test_report_hashes_are_not_authority_and_author_cannot_self_approve(research_run):
    run, report = passing_control(research_run)
    result = evaluate_decision(run, report)
    assert result.status == "blocked" and "unattested_report_custody" in result.reasons
    registry = custody(run, report)
    result = evaluate_decision(run, report, registry=registry)
    assert result.status == "needs_independent_review"
    same_author = ReviewAuthority(
        author="reviewer",
        approved_reviewers=frozenset({"reviewer"}),
        approved_report_hashes=frozenset({digest(report)}),
    )
    assert (
        evaluate_decision(
            run, report, registry=registry, authority=same_author, reviewer="reviewer"
        ).status
        == "needs_independent_review"
    )
    assert (
        evaluate_decision(
            run, report, registry=registry, authority=review(report), reviewer="unknown"
        ).status
        == "needs_independent_review"
    )


@pytest.mark.parametrize("target", ["live", "production", "E5", "deploy", "lower-gates"])
def test_synthetic_reports_never_approve_live_profiles(research_run, target):
    run, report = passing_control(research_run)
    result = evaluate_decision(
        run,
        report,
        registry=custody(run, report),
        authority=review(report),
        reviewer="reviewer",
        target=target,
    )
    assert result.status == "blocked"
    assert "synthetic_live_promotion_forbidden" in result.reasons
    assert result.live_promotion is False and result.effective_policy == "unchanged"


@pytest.mark.parametrize("check", sorted(CRITICAL_CHECKS))
@pytest.mark.parametrize("status", ["fail", "unknown"])
def test_any_critical_failed_or_unknown_gate_vetoes_mean_quality(research_run, check, status):
    run, report = passing_control(research_run)
    checks = dict(report.safety_checks)
    checks[check] = status
    report = report.model_copy(update={"safety_checks": tuple(checks.items())})
    decision = evaluate_decision(
        run, report, registry=custody(run, report), authority=review(report), reviewer="reviewer"
    )
    assert decision.status == "blocked"
    assert "critical_check_unknown_or_failed" in decision.reasons


@pytest.mark.parametrize("field", ["complete_grid", "source_verified", "replay_match"])
def test_missing_integrity_cannot_be_independently_approved(research_run, field):
    run, report = passing_control(research_run)
    report = report.model_copy(update={field: False})
    assert (
        evaluate_decision(
            run,
            report,
            registry=custody(run, report),
            authority=review(report),
            reviewer="reviewer",
        ).status
        == "blocked"
    )


def test_empty_pairs_and_resource_unknowns_do_not_establish_scientific_exit(research_run):
    run, report = passing_control(research_run)
    report = report.model_copy(update={"comparisons": ()})
    result = evaluate_decision(run, report, registry=custody(run, report))
    assert result.status == "not_evaluable"
    assert report.actual_model_resources is None and report.native_resources is None


def test_reviewed_offline_canary_and_rollback_are_pure_and_exact(research_run):
    run, report = passing_control(research_run)
    before = digest(run)
    registry, authority = custody(run, report), review(report)
    decision = evaluate_decision(
        run, report, registry=registry, authority=authority, reviewer="reviewer"
    )
    assert decision.status == "eligible_for_offline_canary"
    baseline = next(p for p in run.policies if p.arm == run.protocol.primary.baseline)
    plan = plan_canary(
        decision,
        run=run,
        report=report,
        registry=registry,
        authority=authority,
        reviewer="reviewer",
        rollback_policy=digest(baseline),
    )
    rollback = dry_run_rollback(plan)
    assert rollback["stable_policy_sha256"] == digest(baseline)
    assert rollback["effective_policy"] == "unchanged"
    assert rollback["receipts"] == "retained"
    assert digest(run) == before
    with pytest.raises(ValueError, match="rollback_target"):
        plan_canary(
            decision,
            run=run,
            report=report,
            registry=registry,
            authority=authority,
            reviewer="reviewer",
            rollback_policy="0" * 64,
        )
    imported = decision.model_copy(update={"reviewer": "another"})
    with pytest.raises(ValueError, match="reviewed_candidate"):
        plan_canary(
            imported,
            run=run,
            report=report,
            registry=registry,
            authority=authority,
            reviewer="reviewer",
            rollback_policy=digest(baseline),
        )
    with pytest.raises(ValidationError):
        type(plan).model_validate(plan.model_dump() | {"mode": "live", "feature_flags": {}})


def test_decision_ledger_rejects_aliases_and_requires_new_evidence_failure_links(tmp_path):
    blocked = ResearchDecision(
        status="blocked", report_sha256="0" * 64, evidence_key="1" * 64, reasons=("critical_veto",)
    )
    head = append_decision(tmp_path, blocked)
    eligible = blocked.model_copy(
        update={
            "status": "eligible_for_offline_canary",
            "previous_decision": head,
            "reviewer": "reviewer",
        }
    )
    with pytest.raises(ValueError, match="failed_evidence_alias"):
        append_decision(tmp_path, eligible)
    new = eligible.model_copy(update={"evidence_key": "2" * 64})
    with pytest.raises(ValueError, match="prior_failure_link"):
        append_decision(tmp_path, new)
    new = new.model_copy(update={"prior_failure": head})
    append_decision(tmp_path, new)
    assert len(read_decisions(tmp_path)) == 2
    with pytest.raises(ValueError, match="head_conflict"):
        append_decision(tmp_path, new)
    (tmp_path / "001.json").write_text('{"version":"unknown"}')
    with pytest.raises(ValidationError):
        read_decisions(tmp_path)


def test_veto_registry_blocks_repackaged_evidence_before_canary(research_run):
    run, report = passing_control(research_run)
    good = evaluate_decision(
        run, report, registry=custody(run, report), authority=review(report), reviewer="reviewer"
    )
    result = evaluate_decision(
        run,
        report,
        registry=custody(run, report, (good.evidence_key,)),
        authority=review(report),
        reviewer="reviewer",
    )
    assert result.status == "blocked" and "failed_evidence_alias" in result.reasons


pytest_plugins = ("tests.memory_research_support",)


@pytest.mark.parametrize(
    "field,value", [("stages", (1,)), ("stop_conditions", ()), ("monitored", ())]
)
def test_canary_manifest_cannot_lower_gates(field, value):
    from personal_ai.memory.research.experiments.decisions import CanaryPlan

    fields = {
        "decision_sha256": "0" * 64,
        "candidate_policy": "1" * 64,
        "rollback_policy": "2" * 64,
        field: value,
    }
    with pytest.raises(ValidationError, match="cannot_be_lowered"):
        CanaryPlan.model_validate(fields)

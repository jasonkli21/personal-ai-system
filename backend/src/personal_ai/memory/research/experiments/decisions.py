"""Pure offline proposals. No API, config writer, scheduler or live execution switch."""

from dataclasses import dataclass
from typing import Literal

from pydantic import model_validator

from personal_ai.memory.research.experiments.contracts import (
    Digest,
    EvaluationReport,
    Identity,
    Record,
    ResearchDecision,
    RunManifest,
    digest,
)

CRITICAL_CHECKS = frozenset(
    {
        "scope",
        "source_revocation",
        "forget_restore",
        "correction",
        "poisoning",
        "intent_replay",
        "tamper",
        "cancellation",
        "resource_bounds",
        "scorer_isolation",
        "configuration_unchanged",
    }
)


@dataclass(frozen=True)
class ReviewAuthority:
    """Trusted host input, deliberately not deserializable from a research package.

    This research package supplies no authenticated reviewer issuer. A caller
    holding Python execution authority can simulate a review for contract tests;
    that is E0 evidence, never an independent approval.
    """

    author: str
    approved_reviewers: frozenset[str] = frozenset()
    approved_report_hashes: frozenset[str] = frozenset()


@dataclass(frozen=True)
class EvidenceRegistry:
    """Host-attested custody after hash/grid/source/scorer checks, never imported JSON."""

    verified_runs: frozenset[str] = frozenset()
    verified_reports: frozenset[str] = frozenset()
    vetoed_evidence: frozenset[str] = frozenset()


def evaluate_decision(
    run, report, *, registry=None, authority=None, reviewer=None, target="offline"
):
    run = RunManifest.model_validate(run.model_dump())
    report = EvaluationReport.model_validate(report.model_dump())
    report_hash = digest(report)
    reasons = []
    if not (
        type(registry) is EvidenceRegistry
        and digest(run) in registry.verified_runs
        and report_hash in registry.verified_reports
    ):
        reasons.append("unattested_report_custody")
    if report.run_sha256 != digest(run):
        reasons.append("report_run_mismatch")
    if not report.complete_grid or not report.source_verified or not report.replay_match:
        reasons.append("integrity_incomplete")
    checks = dict(report.safety_checks)
    if len(checks) != len(report.safety_checks) or any(
        checks.get(k) != "pass" for k in CRITICAL_CHECKS
    ):
        reasons.append("critical_check_unknown_or_failed")
    if report.safety_failures:
        reasons.append("critical_safety_veto")
    if target != "offline":
        reasons.extend(
            ("synthetic_live_promotion_forbidden", "external_evidence_and_owner_required")
        )
    primary = next(
        (
            c
            for c in report.comparisons
            if (
                c.baseline == run.protocol.primary.baseline
                and c.candidate == run.protocol.primary.candidate
            )
        ),
        None,
    )
    if primary is None or not primary.eligible_pairs:
        reasons.append("no_eligible_primary_pairs")
    elif (
        primary.delta_pp is None
        or primary.delta_pp < run.protocol.minimum_effect_pp
        or primary.interval_pp is None
        or primary.interval_pp[0] <= 0
        or any(v < -run.protocol.maximum_family_regression_pp for _, v in primary.family_delta_pp)
    ):
        reasons.append("quality_threshold_not_met")
    # Actual model/native costs remain null and prohibit scientific/live exit.
    evidence_key = digest(
        [
            run.dataset.fixture_sha256,
            run.dataset.scorer_sha256,
            report.semantic_replay_sha256,
            run.protocol.model_dump(mode="json"),
            [s.model_dump() for s in run.source_hashes],
        ]
    )
    if type(registry) is EvidenceRegistry and evidence_key in registry.vetoed_evidence:
        reasons.append("failed_evidence_alias")
    if reasons:
        status = "not_evaluable" if "no_eligible_primary_pairs" in reasons else "blocked"
    elif not (
        type(authority) is ReviewAuthority
        and reviewer != authority.author
        and reviewer in authority.approved_reviewers
        and report_hash in authority.approved_report_hashes
    ):
        status = "needs_independent_review"
        reasons.append("independent_review_missing")
    else:
        status = "eligible_for_offline_canary"
        reasons.append("reviewed_offline_simulation_only")
    return ResearchDecision(
        status=status,
        report_sha256=report_hash,
        evidence_key=evidence_key,
        reviewer=reviewer if status == "eligible_for_offline_canary" else None,
        reasons=tuple(reasons),
    )


class CanaryPlan(Record):
    version: Literal["memory-offline-canary-v1"] = "memory-offline-canary-v1"
    decision_sha256: Digest
    candidate_policy: Digest
    rollback_policy: Digest
    stages: tuple[int, ...] = (4, 12, 48)
    stop_conditions: tuple[Identity, ...] = (
        "any_safety_failure",
        "unknown_permission",
        "source_drift",
        "quota_exceeded",
        "family_regression",
        "duplicate_intent",
        "forget_resurrection",
    )
    monitored: tuple[Identity, ...] = (
        "terminal_success",
        "abstention",
        "provenance",
        "tokens_estimated",
        "latency_ms",
        "index_bytes",
        "maintenance_calls",
        "denial_rate",
    )
    mode: Literal["offline_simulation_only"] = "offline_simulation_only"

    @model_validator(mode="after")
    def fixed_gates(self):
        for name in ("stages", "stop_conditions", "monitored"):
            if getattr(self, name) != type(self).model_fields[name].default:
                raise ValueError("canary_gates_cannot_be_lowered")
        if self.candidate_policy == self.rollback_policy:
            raise ValueError("canary_rollback_identity")
        return self


def plan_canary(decision, *, run, report, registry, authority, reviewer, rollback_policy):
    """Re-evaluate trusted review; an imported positive decision cannot self-approve."""
    expected = evaluate_decision(
        run, report, registry=registry, authority=authority, reviewer=reviewer
    )
    if digest(expected) != digest(decision) or expected.status != "eligible_for_offline_canary":
        raise ValueError("reviewed_candidate_required")
    baseline = next(p for p in run.policies if p.arm == run.protocol.primary.baseline)
    if rollback_policy != digest(baseline):
        raise ValueError("exact_rollback_target_required")
    candidate = next(p for p in run.policies if p.arm == run.protocol.primary.candidate)
    return CanaryPlan(
        decision_sha256=digest(decision),
        candidate_policy=digest(candidate),
        rollback_policy=rollback_policy,
    )


def dry_run_rollback(plan):
    plan = CanaryPlan.model_validate(plan.model_dump())
    return {
        "version": "memory-offline-rollback-v1",
        "stable_policy_sha256": plan.rollback_policy,
        "would_disable": ("offline_candidate_selector",),
        "effective_policy": "unchanged",
        "receipts": "retained",
        "forget_authority": "canonical_owner_unchanged",
    }

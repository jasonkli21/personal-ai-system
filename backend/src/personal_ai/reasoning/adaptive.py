"""Closed selection and exact adaptive plan. No model, source or evaluator ports."""

from typing import Literal

from pydantic import Field, model_validator

from .orchestration import (
    Checkpoint,
    Digest,
    ReasoningRecord,
    Task,
    _check,
    _inference,
    digest,
    fits,
    verify,
)
from .policy import Effort

BASELINE = "reasoning-profile-baseline.v1"
COMPARE = "candidate-compare-objective.v1"
Family = Literal["simple", "independent", "correctable", "arithmetic", "unknown", "fact_slots"]
Action = Literal["baseline", "candidate_compare", "focused", "one_shot"]
Reason = Literal[
    "eligible", "no_marginal_value", "effort_ceiling", "insufficient_reserve",
    "ineligible", "independent_evidence_unavailable", "coverage_complete", "coverage_uncertain", "focused_gap",
]


class ReasoningFeaturesV1(ReasoningRecord):
    schema_version: Literal["reasoning-features-v1"] = "reasoning-features-v1"
    profile: Literal["finite_synthetic", "grounded_local_fixture"]
    family: Family
    requirements: int = Field(ge=1, le=3)
    ambiguity: Literal["resolved", "missing", "conflicting"]
    verifier: Literal["typed_constraints.v1", "fixture-fact-citation.v1"]
    source: Literal["none", "authorized_public_fixture"]
    sensitivity: Literal["public_synthetic"] = "public_synthetic"
    gaps: int = Field(default=0, ge=0, le=3)
    freshness: Literal["not_applicable", "usable", "missing", "stale", "uncertain"]
    effort: Effort
    alternative_fits: bool

    @model_validator(mode="after")
    def consistent(self):
        grounded = self.profile == "grounded_local_fixture"
        if (
            grounded != (self.family == "fact_slots")
            or grounded != (self.source == "authorized_public_fixture")
            or grounded != (self.verifier == "fixture-fact-citation.v1")
            or grounded != (self.freshness != "not_applicable")
            or self.gaps > self.requirements
            or not grounded and self.gaps
        ):
            raise ValueError("adaptive_features_inconsistent")
        return self


class AdaptivePolicyV1(ReasoningRecord):
    schema_version: Literal["adaptive-policy-v1"] = "adaptive-policy-v1"
    baseline: Literal["reasoning-profile-baseline.v1"] = BASELINE
    policy: Literal["objective-alternatives.v1", "single-gap-focus.v1"]
    strategy_version: Literal["candidate-compare-objective.v1", "single-gap-focus.v1"]
    # Conservative development hypotheses, in quality units per 100 tasks.
    eligible_families: tuple[Family, ...] = Field(min_length=1, max_length=3)
    minimum_development_support: int = Field(ge=1, le=1000)
    development_support: int = Field(ge=0, le=1000)
    marginal_value: int = Field(ge=0, le=100)
    uncertainty_penalty: int = Field(ge=0, le=100)
    marginal_work_cost: int = Field(ge=0, le=100)

    @property
    def identity(self):
        return digest(self.model_dump(mode="json"))

    @property
    def worthwhile(self):
        return (
            self.development_support >= self.minimum_development_support
            and self.marginal_value > self.marginal_work_cost + self.uncertainty_penalty
        )


FINITE = AdaptivePolicyV1(
    policy="objective-alternatives.v1", strategy_version=COMPARE,
    eligible_families=("independent", "correctable", "arithmetic"),
    minimum_development_support=8, development_support=8,
    marginal_value=25, uncertainty_penalty=10, marginal_work_cost=10,
)
GROUNDED = AdaptivePolicyV1(
    policy="single-gap-focus.v1", strategy_version="single-gap-focus.v1",
    eligible_families=("fact_slots",), minimum_development_support=4, development_support=4,
    marginal_value=25, uncertainty_penalty=10, marginal_work_cost=10,
)


class SelectionDecisionV1(ReasoningRecord):
    schema_version: Literal["selection-decision-v1"] = "selection-decision-v1"
    feature_schema: Literal["reasoning-features-v1"] = "reasoning-features-v1"
    feature_digest: Digest
    baseline: Literal["reasoning-profile-baseline.v1"] = BASELINE
    policy: Literal["objective-alternatives.v1", "single-gap-focus.v1"]
    policy_digest: Digest
    strategy_version: Literal["candidate-compare-objective.v1", "single-gap-focus.v1"]
    baseline_action: Literal["baseline", "one_shot", "focused"]
    recommendation: Action
    mode: Literal["shadow", "local_fixture_canary", "offline_fixture"]
    reason: Reason
    generation: int = Field(ge=1, le=2**63 - 1)
    build_digest: Digest | None = None
    evidence_digest: Digest | None = None

    @model_validator(mode="after")
    def installed_decision(self):
        policy = FINITE if self.policy == FINITE.policy else GROUNDED
        canary = self.mode == "local_fixture_canary"
        if (
            self.policy_digest != policy.identity or self.strategy_version != policy.strategy_version
            or (self.build_digest is not None) != canary
            or (self.evidence_digest is not None) != canary
            or canary and self.recommendation != "candidate_compare"
            or policy == FINITE and (
                self.baseline_action != "baseline"
                or self.recommendation not in {"baseline", "candidate_compare"}
                or (self.recommendation == "candidate_compare") != (self.reason == "eligible")
            )
            or policy == GROUNDED and (
                self.baseline_action == "baseline" or self.recommendation not in {"one_shot", "focused"}
                or (self.recommendation == "focused") != (self.reason == "focused_gap")
                or self.recommendation == "focused" and self.baseline_action != "focused"
            )
        ):
            raise ValueError("adaptive_decision_invalid")
        return self


def candidate_steps():
    return (
        _inference("candidate_first", "answer"),
        _check("check_first", "check", "candidate_first", "typed_constraints.v1"),
        _inference("candidate_alternative", "revision"),
        _check("compare", "recheck", "candidate_alternative", "typed_constraints.v1").model_copy(
            update={"dependencies": ("check_first", "candidate_alternative")},
        ),
    )


def finite_features(plan, *, reserve=True):
    return ReasoningFeaturesV1(
        profile="finite_synthetic", family=plan.task.kind, requirements=len(plan.task.requirements),
        ambiguity=plan.task.ambiguity, verifier="typed_constraints.v1", source="none",
        freshness="not_applicable", effort=plan.effort,
        alternative_fits=reserve and fits(plan.limits, candidate_steps()),
    )


def finite_reason(features, *, direct_pin=False):
    if (
        features.profile != "finite_synthetic" or features.ambiguity != "resolved"
        or features.family == "unknown" or direct_pin
    ):
        return "ineligible"
    if features.effort not in {"high", "max"}:
        return "effort_ceiling"
    if not features.alternative_fits:
        return "insufficient_reserve"
    if features.family not in FINITE.eligible_families or not FINITE.worthwhile:
        return "no_marginal_value"
    return "eligible"


def decision(features, policy, generation, baseline, recommendation, reason, *, approval=None, offline=False):
    return SelectionDecisionV1(
        feature_digest=digest(features.model_dump(mode="json")),
        policy=policy.policy, policy_digest=policy.identity, strategy_version=policy.strategy_version,
        generation=generation, baseline_action=baseline, recommendation=recommendation, reason=reason,
        mode="offline_fixture" if offline else "shadow" if approval is None else "local_fixture_canary",
        build_digest=None if approval is None else approval.build_digest,
        evidence_digest=None if approval is None else approval.identity,
    )


def compare_candidates(step, task: Task, checkpoints) -> Checkpoint:
    """Resolve by exact per-slot support. The independent alternative sees no prior output."""
    first = verify(step, task, checkpoints["candidate_first"].values)
    second = verify(step, task, checkpoints["candidate_alternative"].values)
    if first.verdict == "inconclusive":
        return second
    if second.verdict == "inconclusive":
        return first
    defects = tuple(slot for slot in first.defects if slot in second.defects)
    values = tuple(
        second.values[slot] if slot in first.defects else value
        for slot, value in enumerate(first.values)
    )
    return Checkpoint(
        step=step.name, verdict="fail" if defects else "pass", values=values, defects=defects,
    )

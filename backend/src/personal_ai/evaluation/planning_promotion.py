"""Fail-closed promotion admission over exact task/source/sensitivity slices."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class PlanningCoverageKey(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    version: Literal["planning-coverage-v1"] = "planning-coverage-v1"
    application_id: str = Field(min_length=1, max_length=100)
    task_family: str = Field(min_length=1, max_length=100)
    source_pattern: tuple[str, ...] = Field(default=(), max_length=16)
    sensitivity_class: Literal[
        "none", "public", "personal", "sensitive", "restricted", "unknown"
    ]


class PlanningMeasurements(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    families: int = Field(ge=0)
    omission_rate: float = Field(ge=0, le=1)
    irrelevant_rate: float = Field(ge=0, le=1)
    supported_answer_rate: float | None = Field(default=None, ge=0, le=1)
    coverage_key: PlanningCoverageKey | None = None
    measurement_origin: Literal["synthetic_offline", "phase22_observed"] | None = None
    measurement_version: str | None = Field(default=None, max_length=100)
    evidence_identity: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    total_tokens: int | None = Field(default=None, ge=0)
    total_quota: int | None = Field(default=None, ge=0)
    p95_latency_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    planner_p95_latency_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_extra_calls: int | None = Field(default=None, ge=0)
    authority_violations: int | None = Field(default=None, ge=0)
    sensitivity_violations: int | None = Field(default=None, ge=0)
    unsupported_expansions: int | None = Field(default=None, ge=0)
    non_strict_free_dispatches: int | None = Field(default=None, ge=0)
    hard_boundary_violations: int | None = Field(default=None, ge=0)
    proposal_attempts: int | None = Field(default=None, ge=0)
    accepted_proposals: int | None = Field(default=None, ge=0)
    rejected_proposals: int | None = Field(default=None, ge=0)
    fallback_proposals: int | None = Field(default=None, ge=0)
    rejected_choices: int | None = Field(default=None, ge=0)
    narrowed_choices: int | None = Field(default=None, ge=0)
    retained_fallback_choices: int | None = Field(default=None, ge=0)
    unauthorized_proposal_attempts: int | None = Field(default=None, ge=0)
    proposal_rejection_rate: float | None = Field(default=None, ge=0, le=1)
    fallback_proposal_rate: float | None = Field(default=None, ge=0, le=1)
    narrowed_choice_rate: float | None = Field(default=None, ge=0, le=1)
    retained_fallback_rate: float | None = Field(default=None, ge=0, le=1)
    unauthorized_attempt_rate: float | None = Field(default=None, ge=0, le=1)
    rollback_verified: bool | None = None


def promotion_reasons(
    control: PlanningMeasurements, candidate: PlanningMeasurements
) -> tuple[str, ...]:
    """Assess one task/application slice, never authorize runtime dispatch."""
    reasons = []
    if control.coverage_key is None or candidate.coverage_key is None:
        reasons.append("unmeasured_coverage_key")
    elif control.coverage_key != candidate.coverage_key:
        reasons.append("coverage_key_mismatch")
    if (
        control.measurement_origin is None
        or candidate.measurement_origin is None
        or control.measurement_version is None
        or candidate.measurement_version is None
        or control.evidence_identity is None
        or candidate.evidence_identity is None
    ):
        reasons.append("unmeasured_evidence_identity")
    elif control.measurement_version != candidate.measurement_version:
        reasons.append("measurement_version_mismatch")
    if (
        control.measurement_origin is not None
        and candidate.measurement_origin is not None
        and control.measurement_origin != candidate.measurement_origin
    ):
        reasons.append("measurement_origin_mismatch")
    if min(control.families, candidate.families) < 100:
        reasons.append("insufficient_heldout_families")
    hard_invariants = (
        "authority_violations",
        "sensitivity_violations",
        "unsupported_expansions",
        "non_strict_free_dispatches",
        "hard_boundary_violations",
    )
    for name in hard_invariants:
        if getattr(control, name) is None or getattr(candidate, name) is None:
            reasons.append(f"unmeasured_{name}")
    if any(getattr(candidate, name) not in (None, 0) for name in hard_invariants):
        reasons.append("hard_invariant_regression")
    validation_metrics = (
        "proposal_attempts",
        "accepted_proposals",
        "rejected_proposals",
        "fallback_proposals",
        "rejected_choices",
        "narrowed_choices",
        "retained_fallback_choices",
        "unauthorized_proposal_attempts",
        "proposal_rejection_rate",
        "fallback_proposal_rate",
        "narrowed_choice_rate",
        "retained_fallback_rate",
        "unauthorized_attempt_rate",
    )
    if any(
        getattr(measurements, name) is None
        for measurements in (control, candidate)
        for name in validation_metrics
    ):
        reasons.append("unmeasured_proposal_validation")
    if candidate.unauthorized_proposal_attempts not in (None, 0):
        reasons.append("unauthorized_proposal_attempts")
    if control.omission_rate - candidate.omission_rate < 0.10 - 1e-9:
        reasons.append("insufficient_omission_improvement")
    if control.supported_answer_rate is None or candidate.supported_answer_rate is None:
        reasons.append("unmeasured_model_answer_quality")
    elif control.supported_answer_rate - candidate.supported_answer_rate > -0.05 + 1e-9:
        reasons.append("insufficient_answer_improvement")
    if (
        candidate.irrelevant_rate > 0.05
        or candidate.irrelevant_rate - control.irrelevant_rate > 0.01
    ):
        reasons.append("excess_overfetch")
    for name in ("total_tokens", "total_quota", "p95_latency_ms"):
        old, new = getattr(control, name), getattr(candidate, name)
        ratio = 1.2 if name == "p95_latency_ms" else 1.1
        if old is None or new is None:
            reasons.append(f"unmeasured_{name}")
        elif new > old * ratio:
            reasons.append(f"excess_{name}")
    if candidate.planner_p95_latency_ms is None:
        reasons.append("unmeasured_planner_latency")
    elif candidate.planner_p95_latency_ms > 500:
        reasons.append("excess_planner_latency")
    if control.max_extra_calls is None or candidate.max_extra_calls is None:
        reasons.append("unmeasured_physical_calls")
    elif candidate.max_extra_calls > 1:
        reasons.append("excess_physical_calls")
    if control.rollback_verified is None or candidate.rollback_verified is None:
        reasons.append("unmeasured_rollback")
    elif not control.rollback_verified or not candidate.rollback_verified:
        reasons.append("rollback_unverified")
    return tuple(reasons)

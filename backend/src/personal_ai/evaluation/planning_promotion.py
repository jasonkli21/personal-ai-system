"""Predeclared per-slice admission; synthetic support cannot replace model quality."""

from pydantic import BaseModel, ConfigDict, Field


class PlanningMeasurements(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    families: int = Field(ge=0)
    omission_rate: float = Field(ge=0, le=1)
    irrelevant_rate: float = Field(ge=0, le=1)
    supported_answer_rate: float | None = Field(default=None, ge=0, le=1)
    total_tokens: int | None = Field(default=None, ge=0)
    total_quota: int | None = Field(default=None, ge=0)
    p95_latency_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    planner_p95_latency_ms: float | None = Field(default=None, ge=0, allow_inf_nan=False)
    max_extra_calls: int = Field(default=0, ge=0)
    authority_violations: int = Field(default=0, ge=0)
    sensitivity_violations: int = Field(default=0, ge=0)
    unsupported_expansions: int = Field(default=0, ge=0)
    non_strict_free_dispatches: int = Field(default=0, ge=0)
    rollback_verified: bool = False


def promotion_reasons(
    control: PlanningMeasurements, candidate: PlanningMeasurements
) -> tuple[str, ...]:
    """Assess one task/application slice, never authorize runtime dispatch."""
    reasons = []
    if min(control.families, candidate.families) < 100:
        reasons.append("insufficient_heldout_families")
    if any(
        (
            candidate.authority_violations,
            candidate.sensitivity_violations,
            candidate.unsupported_expansions,
            candidate.non_strict_free_dispatches,
        )
    ):
        reasons.append("hard_invariant_regression")
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
    if candidate.max_extra_calls > 1:
        reasons.append("excess_physical_calls")
    if not candidate.rollback_verified:
        reasons.append("rollback_unverified")
    return tuple(reasons)

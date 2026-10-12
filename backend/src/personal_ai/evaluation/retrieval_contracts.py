"""Compact research experiment facts; no raw queries, passages or credentials."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, model_validator

from personal_ai.evidence.contracts import ResearchRecord, ScopedResearchRecord


class RetrievalMeasurements(ResearchRecord):
    constraint_retention: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence_recall: float = Field(ge=0, le=1, allow_inf_nan=False)
    evidence_precision: float = Field(ge=0, le=1, allow_inf_nan=False)
    freshness_compliance: float = Field(ge=0, le=1, allow_inf_nan=False)
    source_diversity: int = Field(ge=0, le=12)
    conflict_visibility: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    exact_support: float = Field(ge=0, le=1, allow_inf_nan=False)
    supported_answer: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    unsupported_claim_rate: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    citation_correctness: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    calls: int = Field(ge=0)
    synthesis_invocations: int = Field(default=0, ge=0)
    token_count_invocations: int = Field(default=0, ge=0)
    physical_provider_calls: Literal[0] = 0
    total_token_estimate: int = Field(default=0, ge=0)
    quota: int | None = Field(default=None, ge=0)
    retrieved_bytes: int = Field(ge=0)
    packed_tokens: int = Field(ge=0)
    compression_calls: Literal[0] = 0
    compression_tokens: Literal[0] = 0
    latency_ms: float = Field(ge=0, allow_inf_nan=False)
    retained_artifact_bytes: int = Field(default=0, ge=0)


class ResearchExperimentSummary(ScopedResearchRecord):
    schema_version: Literal["research-experiment-v1"] = "research-experiment-v1"
    id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    evaluation_run_id: UUID
    case_id: str = Field(pattern=r"^[a-z0-9_-]{1,100}$")
    task_family: str = Field(pattern=r"^[a-z0-9_-]{1,100}$")
    source_profile: str = Field(pattern=r"^[a-z0-9_-]{1,100}$")
    strategy_id: str = Field(pattern=r"^[a-z0-9_-]{1,100}$")
    configuration_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    fixture_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    baseline_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    tested_revision: str = Field(pattern=r"^[a-f0-9]{7,40}(-working-tree-[a-f0-9]{12})?$")
    origin: Literal["synthetic_offline"] = "synthetic_offline"
    baseline: RetrievalMeasurements
    candidate: RetrievalMeasurements
    promotion: Literal["not_promoted"] = "not_promoted"
    promotion_policy_version: Literal["research-promotion-v1"] = "research-promotion-v1"
    artifact_id: UUID | None = None
    created_at: datetime
    expires_at: datetime

    @model_validator(mode="after")
    def retention(self):
        if not 0 < (self.expires_at - self.created_at).total_seconds() <= 30 * 86400:
            raise ValueError("experiment_retention")
        return self


def promotion_reasons(summary: ResearchExperimentSummary) -> tuple[str, ...]:
    """Predeclared v1 judging thresholds; never runtime dispatch authority.

    No synthetic experiment can promote a live source profile. This phase does
    not install a live outcome attestor or accept caller-labelled live proof.
    """
    old, new = summary.baseline, summary.candidate
    reasons = ["synthetic_only", "insufficient_independent_coverage"]
    for name in ("constraint_retention", "freshness_compliance", "exact_support"):
        if getattr(new, name) != 1 or getattr(new, name) < getattr(old, name):
            reasons.append(name + "_regression")
    if new.evidence_recall < old.evidence_recall or new.evidence_precision < old.evidence_precision:
        reasons.append("evidence_regression")
    for name in ("supported_answer", "unsupported_claim_rate", "citation_correctness"):
        if getattr(old, name) is None or getattr(new, name) is None:
            reasons.append("unmeasured_" + name)
    if new.unsupported_claim_rate not in (0, None):
        reasons.append("unsupported_claims")
    if old.conflict_visibility is not None and (
        new.conflict_visibility is None or new.conflict_visibility < old.conflict_visibility
    ):
        reasons.append("conflict_loss")
    if old.quota is None or new.quota is None:
        reasons.append("unmeasured_quota")
    elif new.quota > old.quota:
        reasons.append("quota_increase")
    if new.calls > old.calls:
        reasons.append("call_increase")
    if new.synthesis_invocations > old.synthesis_invocations:
        reasons.append("synthesis_call_increase")
    if old.total_token_estimate == 0 or new.total_token_estimate == 0:
        reasons.append("unmeasured_total_tokens")
    if new.latency_ms > max(1, old.latency_ms) * 1.2:
        reasons.append("latency_overhead")
    if not (
        old.supported_answer is not None and new.supported_answer is not None
        and (new.supported_answer - old.supported_answer >= .05
             or (new.supported_answer >= old.supported_answer
                 and new.total_token_estimate <= old.total_token_estimate * .9))
    ):
        reasons.append("insufficient_quality_resource_gain")
    return tuple(reasons)

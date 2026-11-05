"""Payload-free durable observations for the grounded development profile."""

from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, Field, model_validator

from personal_ai.contracts.reasoning_workflow import Digest
from personal_ai.contracts.workflow import AttemptReceipt, RunProgress, WorkflowRecord

GroundedReason = Literal[
    "sufficient", "evidence_insufficient", "policy_denied", "source_changed",
    "budget_exhausted", "cancelled", "uncertain_effect", "internal_failure",
    "ephemeral_state_lost", "provider_unavailable", "unsupported",
]


class EvidenceDependency(WorkflowRecord):
    source_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{0,79}$")
    source_revision: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,100}$")
    issuer_id: UUID
    rights_authority_id: str = Field(pattern=r"^local:[a-f0-9]{64}$")
    rights_epoch: str = Field(pattern=r"^[a-zA-Z0-9_.-]{1,100}$")
    rights_reference_digest: Digest
    passage_id: Digest
    citation_id: Digest
    content_fingerprint: Digest
    observed_at: AwareDatetime
    expires_at: AwareDatetime


class GroundedBinding(WorkflowRecord):
    schema_version: Literal["reasoning-grounded-binding-v1"] = "reasoning-grounded-binding-v1"
    tool_id: Literal["retrieval.query.v1", "reasoning.grounded.inference.v1", "reasoning.grounded.verify.v1"]
    effect_class: Literal["read_only"] = "read_only"
    scope_digest: Digest
    source_digest: Digest
    evidence_digest: Digest
    intent_digest: Digest
    plan_digest: Digest
    step_digest: Digest
    child_key: UUID
    child_message_id: UUID | None = None
    endpoint_digest: Digest | None = None
    focused_slot: int | None = Field(default=None, ge=0, le=2)
    focused_gap: Literal["missing_evidence", "stale_or_expired"] | None = None

    @model_validator(mode="after")
    def inference(self):
        inference = self.tool_id == "reasoning.grounded.inference.v1"
        if inference != (self.child_message_id is not None) or inference != (self.endpoint_digest is not None):
            raise ValueError("grounded_child_binding_invalid")
        if (self.focused_slot is None) != (self.focused_gap is None):
            raise ValueError("grounded_focused_binding_invalid")
        return self


class GroundedResources(WorkflowRecord):
    observed_calls: Literal[0, 1] | None = 0
    verifier_calls_charged: Literal[0, 1] = 0
    reserved_input_bytes: int = Field(default=0, ge=0, le=16_384)
    reserved_output_bytes: int = Field(default=0, ge=0, le=512)
    input_bytes: int | None = Field(default=None, ge=0, le=16_384)
    output_bytes: int | None = Field(default=None, ge=0, le=512)
    count_calls: int = Field(default=0, ge=0, le=32)
    observed_count_calls: int = Field(default=0, ge=0, le=32)
    reserved_count_input_bytes: int = Field(default=0, ge=0, le=524_288)
    observed_count_input_bytes: int = Field(default=0, ge=0, le=524_288)
    reserved_evidence_items: int = Field(default=0, ge=0, le=8)
    reserved_quote_bytes: int = Field(default=0, ge=0, le=4096)
    reserved_retrieval_token_bound: int = Field(default=0, ge=0, le=16_384)
    quote_bytes: int | None = Field(default=None, ge=0, le=4096)
    retrieval_token_bound: int | None = Field(default=None, ge=0, le=16_384)
    elapsed_ms: int | None = Field(default=None, ge=0)
    provider_cost_usd: None = None
    cost_class: Literal["synthetic_no_charge"] = "synthetic_no_charge"


class GroundedAttempt(AttemptReceipt):
    operation_binding: GroundedBinding
    resources: GroundedResources
    evidence: tuple[EvidenceDependency, ...] = Field(default=(), max_length=8)


class GroundedCheck(WorkflowRecord):
    schema_version: Literal["reasoning-grounded-check-v1"] = "reasoning-grounded-check-v1"
    verifier_id: Literal["fixture-fact-citation.v1"] = "fixture-fact-citation.v1"
    stage: Literal["evidence_assessment", "candidate_verification"]
    supported_count: int = Field(ge=0, le=3)
    gaps: tuple[Literal[
        "missing_evidence", "stale_or_expired", "conflict", "citation_unsupported",
        "verification_inconclusive",
    ] | None, ...] = Field(min_length=1, max_length=3)
    citation_digest: Digest

    @model_validator(mode="after")
    def consistent(self):
        if self.gaps.count(None) != self.supported_count:
            raise ValueError("grounded_check_coverage_invalid")
        return self


class GroundedProgress(RunProgress):
    schema_version: Literal["reasoning-grounded-progress-v1"] = "reasoning-grounded-progress-v1"
    strategy_version: Literal["evidence-research-bounded.v1"]
    source_policy: Literal["grounded-evidence-policy-v1"]
    requested_effort: Literal["auto", "low", "medium", "high", "max"]
    effort: Literal["low", "medium", "high", "max"]
    plan_digest: Digest
    source_digest: Digest
    outcome: Literal["pending", "complete", "partial", "unavailable"]
    reason: GroundedReason | None
    attempts: tuple[GroundedAttempt, ...]
    verification: GroundedCheck | None = None

"""Redacted receipt projection for the synthetic reasoning workflow profile."""

from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, model_validator

from personal_ai.contracts.workflow import AttemptReceipt, RunProgress, WorkflowRecord

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
StopReason = Literal[
    "sufficient", "budget_exhausted", "evidence_insufficient", "policy_denied",
    "provider_unavailable", "cancelled", "uncertain_effect", "internal_failure", "unsupported",
]


class ReasoningBinding(WorkflowRecord):
    tool_id: Literal["reasoning.inference.v1", "reasoning.verify.v1"]
    effect_class: Literal["read_only"] = "read_only"
    step_digest: Digest
    source_digest: Digest
    intent_digest: Digest
    plan_digest: Digest
    endpoint_digest: Digest | None = None
    child_key: UUID | None = None
    child_message_id: UUID | None = None
    child_digest: Digest | None = None

    @model_validator(mode="after")
    def inference_binding(self):
        facts = (self.endpoint_digest, self.child_key, self.child_message_id, self.child_digest)
        expected = self.tool_id == "reasoning.inference.v1"
        if any((fact is not None) != expected for fact in facts):
            raise ValueError("reasoning_binding_invalid")
        return self


class Resources(WorkflowRecord):
    physical_attempts: Literal[0, 1] | None = None
    count_calls: int = Field(default=0, ge=0, le=8)
    reserved_count_input_bytes: int = Field(default=0, ge=0, le=8192)
    observed_count_input_bytes: int = Field(default=0, ge=0, le=8192)
    observed_count_calls: int = Field(default=0, ge=0, le=8)
    reserved_input_bytes: int | None = Field(default=None, ge=0, le=1024)
    reserved_output_bytes: int | None = Field(default=None, ge=0, le=128)
    input_bytes: int | None = Field(default=None, ge=0, le=1024)
    output_bytes: int | None = Field(default=None, ge=0, le=128)
    verifier_calls: Literal[0, 1] | None = None
    provider_reservations: None = None
    provider_settlements: None = None
    provider_cost_usd: None = None
    cost_class: Literal["synthetic_no_charge"] = "synthetic_no_charge"
    elapsed_ms: int | None = Field(default=None, ge=0)


class ReasoningAttempt(AttemptReceipt):
    operation_binding: ReasoningBinding
    resources: Resources


class ReasoningProgress(RunProgress):
    schema_version: Literal["reasoning-run-progress-v1"] = "reasoning-run-progress-v1"
    policy: Literal["reasoning-finite-policy-v1"] = "reasoning-finite-policy-v1"
    catalog: Literal["reasoning-finite-catalog-v1"] = "reasoning-finite-catalog-v1"
    strategy: Literal["direct", "decompose", "critique_refine", "tool_verify"]
    strategy_version: Literal[
        "direct-verified.v1", "decompose-typed.v1", "critique-refine-objective.v1",
        "tool-verify-pure.v1",
    ]
    selection: Literal[
        "simple", "typed_slots", "objective_defect", "pure_verifier",
        "effort_ceiling", "budget_narrowed", "trusted_direct_pin",
    ]
    requested_effort: Literal["auto", "low", "medium", "high", "max"]
    plan_digest: Digest
    budget_class: Literal["bounded_synthetic_bytes"] = "bounded_synthetic_bytes"
    effort: Literal["low", "medium", "high", "max"]
    phase: Literal["planning", "answering", "checking", "synthesizing", "terminal"]
    outcome: Literal["pending", "complete", "partial", "unavailable"]
    reason: StopReason | None
    attempts: tuple[ReasoningAttempt, ...]

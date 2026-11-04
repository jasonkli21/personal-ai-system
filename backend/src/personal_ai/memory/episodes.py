"""Structural terminal-step candidates, never admitted memory or permission.

Inputs must eventually be supplied by a trusted canonical workflow adapter. This
pure validator establishes consistency only: fabricated but consistent inputs
can pass. It has no issuer, storage, lookup, context or disclosure integration.
"""

from hashlib import sha256
from typing import Annotated, Literal
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from personal_ai.contracts.delegated_tasks import canonical_bytes
from personal_ai.contracts.workflow import AttemptReceipt, RunSpec, RunState

Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
_INPUT_BYTES = 16384
_RECORD_BYTES = 2048


class CandidateContract(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class TerminalReceiptEnvelope(CandidateContract):
    """Minimal receipt input; schema validation does not authenticate this object."""

    schema_version: Literal["terminal-receipt-envelope-v1"] = "terminal-receipt-envelope-v1"
    scope_digest: Digest
    run_id: UUID
    original_key: UUID
    intent_digest: Digest
    source_digest: Digest
    state: RunState
    cancel_requested: bool = Field(strict=True)
    attempts: tuple[AttemptReceipt, ...] = Field(min_length=1, max_length=8)


class TerminalStepCandidate(CandidateContract):
    """Opaque metadata only. Not a source, grant, verified procedure or episode."""

    schema_version: Literal["terminal-step-candidate-v1"] = "terminal-step-candidate-v1"
    policy_version: Literal["terminal-step-consistency-v1"] = "terminal-step-consistency-v1"
    id: UUID
    scope_digest: Digest
    run_id: UUID
    original_key: UUID
    attempt_id: UUID
    ordinal: int = Field(ge=1, le=8, strict=True)
    intent_digest: Digest
    step_digest: Digest
    source_digest: Digest
    tool: Literal["retrieval.query.v1"] = "retrieval.query.v1"
    effect: Literal["read_only"] = "read_only"
    historical_observation: Literal["handler_result_recorded"] = "handler_result_recorded"
    verification: Literal["not_independently_verified"] = "not_independently_verified"
    completion_time: Literal["unavailable"] = "unavailable"
    use: Literal["structural_inspection_only"] = "structural_inspection_only"


class CandidateAssessment(CandidateContract):
    status: Literal["structurally_supported", "unsupported"]
    candidates: tuple[TerminalStepCandidate, ...] = Field(default=(), max_length=8)


def assess_terminal_steps(
    original_spec: bytes,
    receipt_envelope: bytes,
    *,
    expected_scope_digest: str,
) -> CandidateAssessment:
    """Compare bounded serialized evidence without trusting models or text.

    No result authorizes capture or use. All invalid/mismatched inputs return the
    same content-free outcome, including scope mismatches. The original spec is
    required because terminal workflow rows erase it; current plans cannot stand
    in for the original. No event-tail reconstruction or failure inference occurs.
    """
    denied = CandidateAssessment(status="unsupported")
    if (
        type(original_spec) is not bytes
        or type(receipt_envelope) is not bytes
        or len(original_spec) > _INPUT_BYTES
        or len(receipt_envelope) > _INPUT_BYTES
    ):
        return denied
    try:
        spec = RunSpec.model_validate_json(original_spec)
        receipt = TerminalReceiptEnvelope.model_validate_json(receipt_envelope)
        if (
            receipt.scope_digest != expected_scope_digest
            or receipt.original_key != spec.original_key
            or receipt.intent_digest != spec.intent_digest(receipt.scope_digest)
            or receipt.state != "succeeded"
            or receipt.cancel_requested
            or len(receipt.attempts) != len(spec.steps)
            or len({a.attempt_id for a in receipt.attempts}) != len(receipt.attempts)
        ):
            return denied
        candidates = []
        for ordinal, (step, attempt) in enumerate(
            zip(spec.ordered_steps(), receipt.attempts, strict=True), start=1
        ):
            step_digest = sha256(canonical_bytes(step.model_dump(mode="json"))).hexdigest()
            binding = attempt.operation_binding
            if (
                attempt.state != "succeeded"
                or attempt.step != step.name
                or binding is None
                or binding.tool_id != step.tool
                or binding.effect_class != step.effect
                or binding.step_digest != step_digest
                or binding.source_digest != receipt.source_digest
                or binding.intent_digest != receipt.intent_digest
            ):
                return denied
            identity = canonical_bytes(
                {
                    "policy": "terminal-step-consistency-v1",
                    "scope": receipt.scope_digest,
                    "run": str(receipt.run_id),
                    "original_key": str(receipt.original_key),
                    "attempt": str(attempt.attempt_id),
                    "ordinal": ordinal,
                    "intent": receipt.intent_digest,
                    "step": step_digest,
                    "source": receipt.source_digest,
                }
            )
            candidate = TerminalStepCandidate(
                id=uuid5(
                    NAMESPACE_URL, "personal-ai-step-candidate:" + sha256(identity).hexdigest()
                ),
                scope_digest=receipt.scope_digest,
                run_id=receipt.run_id,
                original_key=receipt.original_key,
                attempt_id=attempt.attempt_id,
                ordinal=ordinal,
                intent_digest=receipt.intent_digest,
                step_digest=step_digest,
                source_digest=receipt.source_digest,
            )
            if len(candidate.model_dump_json().encode()) > _RECORD_BYTES:
                return denied
            candidates.append(candidate)
        return CandidateAssessment(status="structurally_supported", candidates=tuple(candidates))
    except (ValidationError, ValueError, TypeError):
        # Never return raw input, Pydantic errors, source text, paths or secrets.
        return denied

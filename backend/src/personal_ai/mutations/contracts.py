"""Versioned external-effect metadata. None of these records owns domain state."""

from __future__ import annotations

import json
from hashlib import sha256
from typing import Literal, Protocol
from uuid import NAMESPACE_URL, UUID, uuid5

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, JsonValue, model_validator

from personal_ai.auth.scope import RequestScope
from personal_ai.contracts.context_references import (
    ContextAuthorityReference,
    ContextEntityReference,
    ContextPermissionDependency,
    ContextSourceSnapshot,
)


def proposal_identity(owner_id, acting_user_id, application_id, workspace_id, intent_key):
    """Unambiguous scoped identity: null workspace differs from the string 'None'."""
    identity = json.dumps([owner_id, acting_user_id, application_id, workspace_id, str(intent_key)],
                          separators=(",", ":"))
    return uuid5(NAMESPACE_URL, "mutation-proposal-v1:" + identity)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class OperationRef(StrictModel):
    operation_id: str = Field(pattern=r"^[a-z][a-z0-9_.-]{1,80}$")
    version: int = Field(strict=True, ge=1)


class MutationOperationDeclaration(OperationRef):
    payload_schema_id: str = Field(min_length=1, max_length=100)
    entity_types: tuple[str, ...] = Field(min_length=1, max_length=16)
    sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    # Must change when the operation's meaning or validation/effect contract changes,
    # even if the payload schema and operation version happen to stay the same.
    contract_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


class ProducerProvenance(StrictModel):
    """Server-resolved projection of one completed canonical output attribution."""

    provider_id: str | None = Field(default=None, max_length=100)
    model_id: str | None = Field(default=None, max_length=100)
    endpoint_profile_id: str | None = Field(default=None, max_length=100)
    output_message_id: UUID
    output_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    attribution_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    fact_source: Literal["server_observed", "client_reported", "user_declared"]
    execution_origin: Literal["automatic_managed", "connected_local", "manual_import"]
    connection_id: UUID | None = None
    connection_revision: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def producer_matches_origin(self):
        if self.execution_origin == "manual_import":
            if self.fact_source != "user_declared" or self.provider_id or self.model_id:
                raise ValueError("manual_output_cannot_claim_a_producer")
        elif not self.provider_id or not self.model_id or self.fact_source == "user_declared":
            raise ValueError("managed_output_requires_canonical_producer")
        if (self.connection_id is None) != (self.connection_revision is None):
            raise ValueError("canonical_output_connection_incomplete")
        if (self.execution_origin == "connected_local") != (self.connection_id is not None):
            raise ValueError("canonical_output_origin_mismatch")
        return self


class CanonicalOutputHandle(StrictModel):
    """Opaque selectors only; the service resolves all authority from persistence."""

    conversation_id: UUID
    message_id: UUID


class AuthenticatedCommandRequest(StrictModel):
    """Opaque source selectors; source authority and payload are resolved server-side."""

    source_application_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,40}$")
    command_id: UUID


class UserCommandProvenance(StrictModel):
    """A verified deterministic command, never a claim of model-generated output."""

    execution_origin: Literal["authenticated_user_command"] = "authenticated_user_command"
    fact_source: Literal["server_observed"] = "server_observed"
    source_application_id: str = Field(pattern=r"^[a-z][a-z0-9_-]{1,40}$")
    command_id: UUID
    acting_user_id: str = Field(min_length=1, max_length=512)
    command_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")


MutationProvenance = ProducerProvenance | UserCommandProvenance


class PublicUserCommandProvenance(StrictModel):
    """Disclosure-safe command attribution without the private acting-user binding."""

    execution_origin: Literal["authenticated_user_command"]
    fact_source: Literal["server_observed"]
    source_application_id: str
    command_id: UUID
    command_fingerprint: str


class MutationCandidateRequest(StrictModel):
    """Selectors only; a registered domain adapter derives the typed candidate."""

    idempotency_key: UUID
    output: CanonicalOutputHandle
    operation: OperationRef


class TypedMutationCandidate(StrictModel):
    """Domain-produced candidate resolved from a canonical completed output."""

    target: ContextEntityReference
    payload_schema_id: str = Field(min_length=1, max_length=100)
    payload: dict[str, JsonValue]
    expected_domain_version: str = Field(min_length=1, max_length=100)
    rationale: str = Field(min_length=1, max_length=2000)


class ProposalIntent(StrictModel):
    idempotency_key: UUID
    target: ContextEntityReference
    operation: OperationRef
    payload_schema_id: str = Field(min_length=1, max_length=100)
    payload: dict[str, JsonValue]
    expected_domain_version: str = Field(min_length=1, max_length=100)
    rationale: str = Field(min_length=1, max_length=2000)
    producer: MutationProvenance
    sources: tuple[ContextSourceSnapshot, ...] = Field(min_length=1, max_length=16)
    operation_contract_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    expires_at: AwareDatetime

    @model_validator(mode="after")
    def bounded_control_metadata(self):
        if len(json.dumps(self.payload, allow_nan=False).encode()) > 8192:
            raise ValueError("mutation_payload_too_large")
        if len(self.model_dump_json().encode()) > 24576:
            raise ValueError("mutation_intent_too_large")
        return self


class DomainValidation(StrictModel):
    intent_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    validation_id: str = Field(min_length=1, max_length=100)
    version: str = Field(min_length=1, max_length=100)
    expected_domain_version: str = Field(min_length=1, max_length=100)
    valid: bool
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")
    preview: str = Field(max_length=4000)
    permission_dependencies: tuple[ContextPermissionDependency, ...] = Field(
        min_length=1, max_length=16
    )
    expires_at: AwareDatetime


class Confirmation(StrictModel):
    confirmation_id: UUID
    binding: str = Field(pattern=r"^[0-9a-f]{64}$")
    acting_user_id: str
    confirmed_at: AwareDatetime


class AuthoritativePostState(StrictModel):
    target: ContextEntityReference
    domain_version: str = Field(min_length=1, max_length=100)
    reference_id: str = Field(min_length=1, max_length=200)


class DomainOutcome(StrictModel):
    domain_operation_key: UUID
    state: Literal["applied", "rejected", "uncertain"]
    code: str = Field(pattern=r"^[a-z][a-z0-9_]{0,99}$")
    post_state: AuthoritativePostState | None = None

    @model_validator(mode="after")
    def authoritative_success(self):
        if (self.state == "applied") != (self.post_state is not None):
            raise ValueError("mutation_post_state_required_only_for_applied")
        return self


MutationState = Literal[
    "proposed", "validated", "confirmed", "executing", "reconciling",
    "applied", "rejected", "uncertain", "expired",
]


class MutationProposal(StrictModel):
    schema_version: Literal["mutation-proposal-v1"] = "mutation-proposal-v1"
    proposal_id: UUID
    owner_id: str
    acting_user_id: str
    revision: int = Field(ge=1)
    intent: ProposalIntent
    created_at: AwareDatetime
    updated_at: AwareDatetime
    sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    state: MutationState = "proposed"
    domain_operation_key: UUID
    validation: DomainValidation | None = None
    confirmation: Confirmation | None = None
    execution_attempt_id: UUID | None = None
    reconciliation_id: UUID | None = None
    lease_until: AwareDatetime | None = None
    outcome: DomainOutcome | None = None
    terminal_code: str | None = Field(default=None, pattern=r"^[a-z][a-z0-9_]{0,99}$")

    def intent_digest(self) -> str:
        body = {"proposal_id": str(self.proposal_id), "owner_id": self.owner_id,
                "acting_user_id": self.acting_user_id,
                "intent": self.intent.model_dump(mode="json"),
                "domain_operation_key": str(self.domain_operation_key)}
        return sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()

    def binding(self) -> str:
        """Exact immutable intent + domain validation, never a client-supplied proof."""
        body = {
            "proposal_id": str(self.proposal_id), "owner_id": self.owner_id,
            "acting_user_id": self.acting_user_id,
            "intent": self.intent.model_dump(mode="json"),
            "validation": self.validation.model_dump(mode="json") if self.validation else None,
            "sensitivity": self.sensitivity,
            "domain_operation_key": str(self.domain_operation_key),
        }
        return sha256(json.dumps(body, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class MutationError(ValueError):
    def __init__(self, code: str):
        self.code = code
        super().__init__(code)


class MutationUnavailableError(MutationError):
    """Authority/runtime could not be checked before a physical effect was reserved."""


class MutationCandidateNotApplicableError(MutationError):
    """The completed output does not describe this registered operation."""

    def __init__(self) -> None:
        super().__init__("mutation_candidate_not_applicable")


class MutationCandidateInvalidError(MutationError):
    """The output is relevant, but cannot satisfy the operation's stable input rules."""

    def __init__(self) -> None:
        super().__init__("mutation_candidate_invalid")


class MutationAdapterContractError(RuntimeError):
    """A registered adapter failed to return its declared candidate contract."""

    code = "mutation_candidate_adapter_contract_invalid"


class MutationAdapter(Protocol):
    """Domain-owned authority, not a generic database writer.

    execute MUST atomically authorize current delegated identity/dependencies,
    compare exact validation/confirmation binding and expiry, current source dependencies
    and expected entity version, deduplicate the permanent operation key,
    write, and retain an authoritative receipt. No hidden resend/retry is allowed.
    reconcile only observes that key, including after expiry/restart. A missing
    receipt is uncertain, never proof that a resend is safe.
    """

    declaration: MutationOperationDeclaration
    payload_model: type[BaseModel]

    def authorize(self, scope: RequestScope, target: ContextEntityReference, *, action: str) -> bool: ...
    def validate(self, scope: RequestScope, proposal: MutationProposal) -> DomainValidation: ...
    def candidate_from_output(
        self, scope: RequestScope, output: object
    ) -> TypedMutationCandidate: ...
    def execute(self, scope: RequestScope, proposal: MutationProposal) -> DomainOutcome: ...
    def reconcile(self, scope: RequestScope, proposal: MutationProposal) -> DomainOutcome: ...


class MutationRepository(Protocol):
    def get(self, scope: RequestScope, proposal_id: UUID) -> MutationProposal | None: ...
    def save(self, proposal: MutationProposal, *, expected_revision: int) -> MutationProposal: ...


class PublicIntent(StrictModel):
    idempotency_key: UUID
    target: ContextEntityReference
    operation: OperationRef
    payload_schema_id: str
    payload: dict[str, JsonValue] | None
    expected_domain_version: str
    rationale: str | None
    producer: ProducerProvenance | PublicUserCommandProvenance
    source_refs: tuple[ContextAuthorityReference, ...]
    expires_at: AwareDatetime


class PublicValidation(StrictModel):
    intent_digest: str
    validation_id: str
    version: str
    expected_domain_version: str
    valid: bool
    code: str
    preview: str | None
    expires_at: AwareDatetime


class PublicConfirmation(StrictModel):
    confirmation_id: UUID
    binding: str
    confirmed_at: AwareDatetime


class PublicMutationProposal(StrictModel):
    """Authorized presentation only; never hydrated as a canonical proposal."""
    schema_version: Literal["mutation-proposal-view-v1"] = "mutation-proposal-view-v1"
    proposal_id: UUID
    revision: int
    intent: PublicIntent
    created_at: AwareDatetime
    updated_at: AwareDatetime
    sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    state: MutationState
    validation: PublicValidation | None
    confirmation: PublicConfirmation | None
    outcome: PublicDomainOutcome | None
    terminal_code: str | None


class PublicDomainOutcome(StrictModel):
    """Browser-safe authoritative outcome, without domain operation keys."""

    state: Literal["applied", "rejected", "uncertain"]
    code: str
    post_state: AuthoritativePostState | None = None


class ProposalView(StrictModel):
    """Sidecar-safe projection; authority dependency tokens remain server-side."""
    proposal: PublicMutationProposal
    binding: str = Field(pattern=r"^[0-9a-f]{64}$")
    apply_available: bool

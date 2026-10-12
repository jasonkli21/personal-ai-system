"""Versioned external-effect metadata. None of these records owns domain state."""

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


class ProducerProvenance(StrictModel):
    provider_id: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=100)
    endpoint_profile_id: str | None = Field(default=None, max_length=100)
    output_reference: str = Field(min_length=1, max_length=200)
    # Producer labels, especially manual imports, never imply verified identity.
    trust: Literal["claimed"] = "claimed"


class ProposalIntent(StrictModel):
    idempotency_key: UUID
    target: ContextEntityReference
    operation: OperationRef
    payload_schema_id: str = Field(min_length=1, max_length=100)
    payload: dict[str, JsonValue]
    expected_domain_version: str = Field(min_length=1, max_length=100)
    rationale: str = Field(min_length=1, max_length=2000)
    producer: ProducerProvenance
    sources: tuple[ContextSourceSnapshot, ...] = Field(min_length=1, max_length=16)
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
    producer: ProducerProvenance
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
    domain_operation_key: UUID
    validation: PublicValidation | None
    confirmation: PublicConfirmation | None
    execution_attempt_id: UUID | None
    reconciliation_id: UUID | None
    lease_until: AwareDatetime | None
    outcome: DomainOutcome | None
    terminal_code: str | None


class ProposalView(StrictModel):
    """Sidecar-safe projection; authority dependency tokens remain server-side."""
    proposal: PublicMutationProposal
    binding: str = Field(pattern=r"^[0-9a-f]{64}$")
    apply_available: bool

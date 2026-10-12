"""Provider-neutral request choices for shared conversation continuation."""

import re
from enum import StrEnum
from hashlib import sha256
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from personal_ai.applications.contracts import ApplicationLaunchContext
from personal_ai.contracts.context_categories import ContextSourceClass
from personal_ai.contracts.context_references import ContextEntityReference
from personal_ai.contracts.federation import FederationContextChoice
from personal_ai.routing.contracts import EndpointRef


class ExternalFailureCode(StrEnum):
    """Safe, provider-neutral recovery vocabulary shared with the local bridge."""

    ADMISSION_DENIED = "bridge_admission_denied"
    AUTHORIZATION_EXPIRED = "bridge_authorization_expired"
    AUTH_REQUIRED = "bridge_auth_required"
    CALLER_DENIED = "bridge_caller_denied"
    CATALOG_INVALID = "bridge_catalog_invalid"
    CLIENT_CONFIGURATION = "bridge_client_configuration"
    COMPATIBILITY_UNVERIFIED = "bridge_compatibility_unverified"
    CONFIGURATION_INVALID = "bridge_configuration_invalid"
    COMPLETION_INVALID = "bridge_completion_invalid"
    CONNECTION_CHANGED = "bridge_connection_changed"
    CREDENTIAL_ECHO = "bridge_credential_echo"
    DELTA_INVALID = "bridge_delta_invalid"
    DISCLOSURE_DENIED = "bridge_disclosure_denied"
    EVENT_INVALID = "bridge_event_invalid"
    EVENT_TOO_LARGE = "bridge_event_too_large"
    EXECUTION_INTERRUPTED = "bridge_execution_interrupted"
    EXECUTION_PROFILE_UNSUPPORTED = "bridge_execution_profile_unsupported"
    GATE_AMBIGUOUS = "bridge_gate_ambiguous"
    INCOMPLETE = "bridge_incomplete"
    INELIGIBLE = "bridge_ineligible"
    MODEL_MISMATCH = "bridge_model_mismatch"
    MODEL_UNAVAILABLE = "bridge_model_unavailable"
    MODELS_UNAVAILABLE = "bridge_models_unavailable"
    ORIGIN_DENIED = "bridge_origin_denied"
    ORIGIN_INVALID = "bridge_origin_invalid"
    OUTPUT_BOUND = "bridge_output_bound"
    OUTPUT_UNSUPPORTED = "bridge_output_unsupported"
    PERMISSION_DENIED = "bridge_permission_denied"
    PERMISSION_REQUIRED = "bridge_permission_required"
    PAIRING_CAPACITY = "bridge_pairing_capacity"
    PORT_INVALID = "bridge_port_invalid"
    PROTOCOL_INVALID = "bridge_protocol_invalid"
    RATE_LIMITED = "bridge_rate_limited"
    REQUEST_INVALID = "bridge_request_invalid"
    REQUEST_TOO_LARGE = "bridge_request_too_large"
    REQUEST_DENIED = "bridge_request_denied"
    REQUEST_UNSUPPORTED = "bridge_unsupported_request"
    REFRESH_NOT_AVAILABLE = "bridge_refresh_not_available"
    REFRESH_UNCERTAIN = "bridge_refresh_uncertain"
    RESPONSE_ENCODING_UNSUPPORTED = "bridge_response_encoding_unsupported"
    RESPONSE_INVALID = "bridge_response_invalid"
    RESPONSE_TOO_LARGE = "bridge_response_too_large"
    REFUSAL_INCOMPLETE = "bridge_refusal_incomplete"
    REFUSAL_INVALID = "bridge_refusal_invalid"
    REFUSAL_MISMATCH = "bridge_refusal_mismatch"
    STREAM_ENCODING_UNSUPPORTED = "bridge_stream_encoding_unsupported"
    STREAM_INVALID = "bridge_stream_invalid"
    STREAM_TOO_LARGE = "bridge_stream_too_large"
    STREAM_TRUNCATED = "bridge_stream_truncated"
    TERMINAL_MISSING = "bridge_terminal_missing"
    TERMINAL_TEXT_MISMATCH = "bridge_terminal_text_mismatch"
    TIMEOUT_UNKNOWN = "bridge_timeout_unknown"
    TOOL_UNSUPPORTED = "bridge_tool_unsupported"
    TRANSPORT_UNKNOWN = "bridge_transport_unknown"
    TRANSPORT_UNVERIFIED = "bridge_transport_unverified"
    UNAVAILABLE = "bridge_unavailable"
    USAGE_INVALID = "bridge_usage_invalid"
    USAGE_LIMIT = "bridge_usage_limit"
    USAGE_UNAVAILABLE = "bridge_usage_unavailable"


def normalize_external_failure(code: object) -> ExternalFailureCode:
    try:
        return ExternalFailureCode(code)
    except (TypeError, ValueError):
        return ExternalFailureCode.EXECUTION_INTERRUPTED


class ExecutionChoice(BaseModel):
    """Producer-neutral continuation choice. Historical origin never selects a route."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: Literal["automatic", "connected_provider", "manual_external"] = "automatic"
    endpoint: EndpointRef | None = None
    # Account-discovered model identity is separate from the stable endpoint profile.
    model_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
    connection_id: UUID | None = None
    connection_revision: int | None = Field(default=None, ge=1)
    caller_id: UUID | None = None
    audience: UUID | None = None

    @model_validator(mode="after")
    def valid_choice(self):
        binding = (
            self.endpoint,
            self.model_id,
            self.connection_id,
            self.connection_revision,
            self.caller_id,
            self.audience,
        )
        if self.mode == "connected_provider" and any(v is None for v in binding):
            raise ValueError("connected_choice_requires_binding")
        if self.mode != "connected_provider" and any(v is not None for v in binding):
            raise ValueError("execution_choice_binding_invalid")
        return self


class ContinuationRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    content: str = Field(min_length=1, max_length=20000)
    idempotency_key: UUID
    choice: ExecutionChoice = Field(default_factory=ExecutionChoice)
    federation_context: tuple[FederationContextChoice, ...] = Field(default=(), max_length=4)
    # Optional narrowing. References never authorize or force inclusion.
    candidate_message_ids: tuple[UUID, ...] | None = Field(default=None, max_length=10000)
    # Host launch data is advisory and is re-bound to the authenticated request scope.
    launch_context: ApplicationLaunchContext | None = None
    # Bounded source-class narrowing. This can only remove planner-selected sources.
    excluded_source_classes: tuple[ContextSourceClass, ...] = Field(default=(), max_length=9)

    @model_validator(mode="after")
    def unique_exclusions(self):
        if len(set(self.excluded_source_classes)) != len(self.excluded_source_classes):
            raise ValueError("context_source_exclusions_must_be_unique")
        return self

    @property
    def explicit_context_selections(self):
        return tuple(choice.context_selection() for choice in self.federation_context)

    @property
    def entity_refs(self) -> tuple[ContextEntityReference, ...]:
        return self.launch_context.entity_refs if self.launch_context is not None else ()

    @property
    def intent_digest(self) -> str:
        """Stable durable identity for retries across automatic and external modes."""
        import json

        payload = self.model_dump(mode="json")
        # Preserve idempotency digests written before launch metadata was added.
        if not self.federation_context:
            payload.pop("federation_context", None)
        if self.launch_context is None:
            payload.pop("launch_context", None)
        canonical = json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
        return sha256(canonical).hexdigest()


class ContinuationRequestPayload(BaseModel):
    """Browser/API continuation contract; federation authority stays server-side."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    content: str = Field(min_length=1, max_length=20000)
    idempotency_key: UUID
    choice: ExecutionChoice = Field(default_factory=ExecutionChoice)
    federation_choice_ids: tuple[str, ...] = Field(default=(), max_length=4)
    candidate_message_ids: tuple[UUID, ...] | None = Field(default=None, max_length=10000)
    launch_context: ApplicationLaunchContext | None = None
    excluded_source_classes: tuple[ContextSourceClass, ...] = Field(default=(), max_length=9)

    @model_validator(mode="after")
    def choices_and_exclusions_are_unique(self):
        if any(not re.fullmatch(r"[A-Za-z0-9_-]{43}", handle) for handle in self.federation_choice_ids):
            raise ValueError("federation_choice_invalid")
        if len(set(self.federation_choice_ids)) != len(self.federation_choice_ids):
            raise ValueError("federation_choices_must_be_unique")
        if len(set(self.excluded_source_classes)) != len(self.excluded_source_classes):
            raise ValueError("context_source_exclusions_must_be_unique")
        return self

    def to_internal_request(self, federation_context=()) -> ContinuationRequest:
        return ContinuationRequest(
            content=self.content,
            idempotency_key=self.idempotency_key,
            choice=self.choice,
            federation_context=tuple(federation_context),
            candidate_message_ids=self.candidate_message_ids,
            launch_context=self.launch_context,
            excluded_source_classes=self.excluded_source_classes,
        )

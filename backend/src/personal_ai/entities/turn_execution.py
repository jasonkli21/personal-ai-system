"""Canonical safe turn state; credentials and provider account state live elsewhere."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from personal_ai.contracts.context_references import (
    ContextSourceSnapshot,
)


class TurnAttribution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: Literal["connected_provider", "manual_external"]
    fact_source: Literal["server_observed", "client_reported", "user_declared"]
    # Legacy records may omit origin; new writers state the execution lane explicitly.
    execution_origin: Literal["automatic_managed", "connected_local", "manual_import"] | None = None
    provider_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/ -]{0,199}$")
    model_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/ -]{0,199}$")
    task: Literal["chat"] = "chat"
    status: Literal["success"] = "success"
    recorded_at: datetime
    latency_ms: int | None = Field(default=None, ge=0, le=3_600_000)
    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    usage_source: Literal["provider", "estimated"] | None = None
    usage_confidence: Literal["reported", "estimated"] | None = None
    context_fact_source: Literal["server_observed"] = "server_observed"
    model_verified: Literal[False] = False
    package_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    connection_id: UUID | None = None
    connection_revision: int | None = Field(default=None, ge=1)
    source_message_ids: tuple[UUID, ...] = Field(default=(), max_length=10000)
    source_snapshots: tuple[ContextSourceSnapshot, ...] = Field(default=(), max_length=512)

    @model_validator(mode="after")
    def trust(self):
        if self.recorded_at.tzinfo is None:
            raise ValueError("timestamp_requires_timezone")
        if self.mode == "manual_external":
            if self.fact_source != "user_declared" or any(
                v is not None
                for v in (
                    self.latency_ms,
                    self.input_tokens,
                    self.output_tokens,
                    self.usage_source,
                    self.usage_confidence,
                )
            ):
                raise ValueError("manual_import_cannot_claim_observations")
            if self.execution_origin not in {None, "manual_import"} or any(
                value is not None for value in (self.connection_id, self.connection_revision)
            ):
                raise ValueError("manual_import_cannot_claim_connection")
        elif self.fact_source == "user_declared" or not self.provider_id or not self.model_id:
            raise ValueError("connected_attribution_requires_producer")
        elif self.execution_origin == "manual_import":
            raise ValueError("connected_attribution_origin_invalid")
        if (self.connection_id is None) != (self.connection_revision is None):
            raise ValueError("connection_attribution_incomplete")
        if self.execution_origin == "connected_local" and self.connection_id is None:
            raise ValueError("local_connection_attribution_required")
        if self.execution_origin == "automatic_managed" and self.connection_id is not None:
            raise ValueError("automatic_attribution_cannot_claim_local_connection")
        if len(self.model_dump_json().encode()) > 65536:
            raise ValueError("turn_metadata_exceeds_bound")
        return self


class TurnReservation(BaseModel):
    """One branch-owned execution lifecycle, persisted inside its assistant message."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    reservation_id: UUID
    request_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    mode: Literal["connected_provider", "manual_external"]
    state: Literal["prepared", "dispatched", "completed", "cancelled", "unknown"] = "prepared"
    package_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    branch_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    authority_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    policy_version: str = Field(min_length=1, max_length=200)
    effective_sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    expires_at: datetime
    max_output_bytes: int = Field(ge=1, le=80000)
    max_output_chars: int = Field(default=20000, ge=1, le=20000)
    provider_id: str | None = Field(default=None, max_length=200)
    model_id: str | None = Field(default=None, max_length=200)
    connection_id: UUID | None = None
    connection_revision: int | None = Field(default=None, ge=1)
    endpoint_profile_id: str | None = None
    profile_version: int | None = Field(default=None, ge=1)
    profile_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    caller_id: UUID | None = None
    audience: UUID | None = None
    completion_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    source_message_ids: tuple[UUID, ...] = Field(default=(), max_length=10000)
    source_snapshots: tuple[ContextSourceSnapshot, ...] = Field(default=(), max_length=512)
    selected_memory_ids: tuple[UUID, ...] = Field(default=(), max_length=10000)

    @model_validator(mode="after")
    def valid_mode(self):
        if self.expires_at.tzinfo is None:
            raise ValueError("timestamp_requires_timezone")
        connected = (
            self.connection_id,
            self.connection_revision,
            self.caller_id,
            self.audience,
            self.endpoint_profile_id,
            self.profile_version,
            self.profile_digest,
        )
        if self.mode == "manual_external" and any(v is not None for v in connected):
            raise ValueError("manual_reservation_cannot_claim_connection")
        if self.mode == "connected_provider" and (
            any(v is None for v in connected) or not self.provider_id or not self.model_id
        ):
            raise ValueError("connected_reservation_requires_binding")
        if self.mode == "manual_external" and (self.provider_id is not None or self.model_id is not None):
            raise ValueError("manual_labels_belong_to_import")
        if (self.state == "completed") != (self.completion_digest is not None):
            raise ValueError("completion_digest_requires_terminal_success")
        if len(self.model_dump_json().encode()) > 65536:
            raise ValueError("turn_metadata_exceeds_bound")
        return self


def transition_message(current, candidate):
    """Validate generic lifecycle changes before any repository write."""
    if any(
        getattr(current, key) != getattr(candidate, key)
        for key in (
            "id",
            "owner_id",
            "application_id",
            "workspace_id",
            "conversation_id",
            "created_at",
            "role",
            "parent_message_id",
            "supersedes_message_id",
            "continuation_digest",
        )
    ):
        raise ValueError("message_identity_immutable")
    if current.attribution is not None and (
        current.attribution != candidate.attribution
        or current.content != candidate.content
        or current.model != candidate.model
    ):
        raise ValueError("producer_attribution_immutable")
    if (
        current.attribution is None
        and candidate.attribution is not None
        and candidate.model != candidate.attribution.model_id
    ):
        raise ValueError("message_model_must_project_attribution")
    reservation = current.execution
    if reservation is None:
        if candidate.execution is not None:
            raise ValueError("reservation_requires_preparation")
        return candidate
    from personal_ai.entities.conversation import MessageStatus

    if candidate.status == MessageStatus.FAILED and candidate.execution == reservation:
        candidate = candidate.model_copy(
            update={
                "content": "",
                "execution": reservation.model_copy(
                    update={
                        "state": "unknown" if reservation.state == "dispatched" else "cancelled"
                    }
                ),
            }
        )
    next_reservation = candidate.execution
    if next_reservation is None or reservation.model_dump(
        exclude={"state", "completion_digest"}
    ) != next_reservation.model_dump(exclude={"state", "completion_digest"}):
        raise ValueError("reservation_binding_immutable")
    allowed = {
        "prepared": {"dispatched", "completed", "cancelled"},
        "dispatched": {"completed", "unknown"},
        "completed": set(),
        "cancelled": set(),
        "unknown": set(),
    }
    if next_reservation.state not in allowed[reservation.state]:
        raise ValueError("reservation_transition_invalid")
    if reservation.mode == "manual_external" and next_reservation.state == "dispatched":
        raise ValueError("manual_import_cannot_dispatch")
    if (
        reservation.mode == "connected_provider"
        and reservation.state == "prepared"
        and next_reservation.state == "completed"
    ):
        raise ValueError("connected_completion_requires_dispatch")
    if next_reservation.state == "completed" and (
        candidate.status != MessageStatus.COMPLETED
        or candidate.attribution is None
        or candidate.attribution.mode != reservation.mode
    ):
        raise ValueError("completion_requires_attribution")
    if next_reservation.state == "completed":
        attribution = candidate.attribution
        if (
            attribution is None
            or attribution.package_fingerprint != reservation.package_fingerprint
            or attribution.source_message_ids != reservation.source_message_ids
            or attribution.source_snapshots != reservation.source_snapshots
            or (reservation.provider_id is not None and attribution.provider_id != reservation.provider_id)
            or (reservation.model_id is not None and attribution.model_id != reservation.model_id)
            or (reservation.mode == "connected_provider" and (
                attribution.execution_origin != "connected_local"
                or attribution.fact_source != "client_reported"
                or attribution.connection_id != reservation.connection_id
                or attribution.connection_revision != reservation.connection_revision
            ))
            or (reservation.mode == "manual_external" and (
                attribution.execution_origin != "manual_import"
                or attribution.connection_id is not None
                or attribution.connection_revision is not None
                or attribution.fact_source != "user_declared"
            ))
            or candidate.model != attribution.model_id
        ):
            raise ValueError("completion_attribution_mismatches_reservation")
    if next_reservation.state == "dispatched" and (
        candidate.status != MessageStatus.PENDING or candidate.content or candidate.attribution
    ):
        raise ValueError("dispatch_requires_pending_empty_message")
    if next_reservation.state in {"cancelled", "unknown"} and (
        candidate.status != MessageStatus.FAILED or candidate.content or candidate.attribution
    ):
        raise ValueError("failed_execution_requires_empty_message")
    return type(candidate).model_validate(candidate.model_dump())

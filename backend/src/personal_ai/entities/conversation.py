"""Provider- and storage-independent conversation domain records."""

from datetime import UTC, datetime
from enum import StrEnum
from typing import Literal
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from personal_ai.auth.scope import ApplicationScopedRecord
from personal_ai.entities.turn_execution import TurnAttribution, TurnReservation

MAX_MESSAGE_CONTENT_CHARS = 20_000


class MessageRole(StrEnum):
    """The two message authors supported by the Phase 1 chat surface."""

    USER = "user"
    ASSISTANT = "assistant"


class MessageStatus(StrEnum):
    """Durable states for append-only messages and replacements."""

    PENDING = "pending"
    STREAMING = "streaming"
    COMPLETED = "completed"
    FAILED = "failed"
    SUPERSEDED = "superseded"


class TimestampedRecord(ApplicationScopedRecord):
    """Require timezone-aware timestamps and normalize them to UTC."""

    model_config = ConfigDict(extra="forbid")

    @field_validator("created_at", "updated_at", check_fields=False)
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        """Reject naive datetimes and store all instants as UTC."""
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp must include a UTC offset")
        return value.astimezone(UTC)


class Conversation(TimestampedRecord):
    """A persisted conversation owned by the current logical user."""

    id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    context_preparation_id: UUID | None = Field(default=None, exclude=True)
    context_preparation_started_at: datetime | None = Field(default=None, exclude=True)
    persistence_revision: int = Field(default=0, exclude=True, ge=0)
    title: str = Field(min_length=1, max_length=200)
    created_at: datetime
    updated_at: datetime


class Message(TimestampedRecord):
    """A persisted, branchable message in a conversation."""

    id: UUID
    conversation_id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    role: MessageRole
    content: str = Field(max_length=MAX_MESSAGE_CONTENT_CHARS)
    status: MessageStatus
    created_at: datetime
    parent_message_id: UUID | None = None
    supersedes_message_id: UUID | None = None
    model: str | None = Field(default=None, max_length=200)
    error_code: str | None = Field(default=None, max_length=100)
    error_fact_source: Literal["server_observed", "client_reported"] | None = None
    failure_status: int | None = Field(default=None, ge=100, le=599, strict=True)
    failure_latency_ms: int | None = Field(default=None, ge=0, le=3_600_000, strict=True)
    attribution: TurnAttribution | None = None
    execution: TurnReservation | None = None
    # Deterministic continuation intent, shared by automatic and external retries.
    continuation_digest: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")

    @model_validator(mode="after")
    def client_failure_facts_are_labeled(self):
        if (
            (self.failure_status is not None or self.failure_latency_ms is not None)
            and self.error_fact_source != "client_reported"
        ):
            raise ValueError("failure_facts_require_client_reported_source")
        return self

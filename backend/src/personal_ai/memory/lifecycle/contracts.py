"""Durable lifecycle records and repository protocol."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import ConfigDict, Field, field_validator, model_validator

from personal_ai.auth.scope import ApplicationScopedRecord
from personal_ai.memory.contracts import DerivedMemory, LifecycleEventType, Memory

Actor = Literal["system", "developer_test", "verified_user"]

RetrievalStatus = Literal["active", "superseded", "forgotten"]

JobType = Literal["consolidation", "maintenance"]

JobStatus = Literal["pending", "leased", "retry", "completed", "terminal"]


class MemoryLifecycleEvent(ApplicationScopedRecord):
    """Immutable, replay-safe record of one lifecycle decision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    memory_id: UUID
    event_type: LifecycleEventType
    reason_code: str = Field(min_length=1, max_length=100)
    policy_version: str = Field(min_length=1, max_length=100)
    actor: Actor = "system"
    occurred_at: datetime
    idempotency_key: str = Field(min_length=1, max_length=300)
    related_memory_ids: tuple[UUID, ...] = Field(default_factory=tuple, max_length=8)
    job_id: UUID | None = None
    expected_state_version: int = Field(ge=0)
    schema_version: Literal[1] = 1

    @field_validator("occurred_at")
    @classmethod
    def utc(cls, value):
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timestamp_invalid")
        return value.astimezone(UTC)


class MemoryLifecycleState(ApplicationScopedRecord):
    """Rebuildable owner-scoped projection; source Memory documents stay immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @model_validator(mode="before")
    @classmethod
    def drop_legacy_reverse_view_cache(cls, value):
        # Complete reverse membership is owned by derived_memory_sources. Older
        # payloads duplicated that unbounded relation in a capped projection.
        if isinstance(value, dict) and "consolidated_into_memory_ids" in value:
            value = dict(value)
            value.pop("consolidated_into_memory_ids", None)
        return value

    memory_id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    retrieval_status: RetrievalStatus = "active"
    effective_status_at: datetime | None = None
    superseded_by_memory_id: UUID | None = None
    last_retrieved_at: datetime | None = None
    retrieval_count: int = Field(default=0, ge=0)
    state_version: int = Field(default=0, ge=0)
    importance: float | None = Field(default=None, ge=0, le=1, allow_inf_nan=False)
    importance_policy_version: str | None = None
    last_event_id: UUID | None = None
    unresolved_conflict: bool = False
    validity_epoch: int = Field(default=0, ge=0)

    @field_validator("effective_status_at", "last_retrieved_at")
    @classmethod
    def utc(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("timestamp_invalid")
            return value.astimezone(UTC)
        return value


class MemoryLifecycleOutcome(ApplicationScopedRecord):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: Literal["applied", "replayed", "conflict"]
    state: MemoryLifecycleState | None = None
    event_id: UUID | None = None
    reason: str | None = None


class MemoryJob(ApplicationScopedRecord):
    """Durable work intent. Pub/Sub messages contain only ID and schema version."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    job_type: JobType
    candidate_memory_ids: tuple[UUID, ...] = Field(max_length=4)
    policy_version: str = Field(min_length=1, max_length=100)
    policy_snapshot: dict[str, float | str | int]
    status: JobStatus = "pending"
    attempt_count: int = Field(default=0, ge=0)
    max_attempts: int = Field(default=3, gt=0, le=10)
    lease_expires_at: datetime | None = None
    lease_token: UUID | None = None
    lease_generation: int = Field(default=0, ge=0)
    idempotency_key: str = Field(min_length=1, max_length=300)
    publish_pending: bool = True
    retry_reason: str | None = Field(default=None, max_length=100)
    next_attempt_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    schema_version: Literal[1] = 1

    @field_validator("lease_expires_at", "next_attempt_at", "created_at", "updated_at")
    @classmethod
    def utc(cls, value):
        if value is not None:
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("timestamp_invalid")
            return value.astimezone(UTC)
        return value

    @model_validator(mode="after")
    def lease_shape(self):
        if self.status == "leased" and (self.lease_expires_at is None or self.lease_token is None):
            raise ValueError("lease_invalid")
        if len(set(self.candidate_memory_ids)) != len(self.candidate_memory_ids):
            raise ValueError("job_source_duplicate")
        return self


class MemoryLifecycleRepository(Protocol):
    def get_state(self, *, owner_id: str, memory_id: UUID) -> MemoryLifecycleState: ...
    def list_events(self, *, owner_id: str, memory_id: UUID, limit: int = 50): ...
    def find_event(self, *, owner_id: str, memory_id: UUID, idempotency_key: str): ...
    def apply_event(
        self,
        event: MemoryLifecycleEvent,
        *,
        completed_assistant_id: UUID | None = None,
        completed_assistant_conversation_id: UUID | None = None,
        job: MemoryJob | None = None,
        lease_token: UUID | None = None,
    ) -> MemoryLifecycleOutcome: ...
    def create_job(self, job: MemoryJob) -> tuple[MemoryJob, bool]: ...
    def get_job(self, *, owner_id: str, job_id: UUID) -> MemoryJob: ...
    def get_job_by_id(self, *, job_id: UUID) -> MemoryJob: ...
    def claim_job(self, *, owner_id: str, job_id: UUID, now: datetime, lease_seconds: int): ...
    def complete_job(self, job: MemoryJob, *, token: UUID, now: datetime): ...
    def fail_job(
        self, job: MemoryJob, *, token: UUID, now: datetime, reason: str, retryable: bool
    ): ...
    def dependencies(self, *, owner_id: str, memory_id: UUID, limit: int = 100): ...
    def discover_related(self, *, owner_id: str, memory_id: UUID, limit: int = 4): ...
    def discover_forgetting_candidates(
        self, *, owner_id: str, older_than: datetime, limit: int = 4
    ): ...
    def discover_maintenance_candidates(self, *, owner_id: str, limit: int = 4): ...


MemoryRecord = Memory | DerivedMemory

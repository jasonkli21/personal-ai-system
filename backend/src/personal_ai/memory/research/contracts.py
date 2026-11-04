"""Bounded immutable navigation contracts adapting the canonical query envelope."""

import json
from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from personal_ai.memory.contracts import MemoryQuery

POLICY = "bounded-navigation-v1"
MAX_RECORDS = 128
MAX_BYTES = 262_144
MAX_TOPICS = 32
PAGE_SIZE = 8
Status = Literal[
    "ok", "disabled", "denied", "unavailable", "unsupported", "incomplete", "cancelled", "timed_out"
]
Arm = Literal[
    "no_memory",
    "fixed",
    "lexical",
    "semantic",
    "hybrid",
    "hybrid_reranked",
    "topic_hierarchical",
    "request_aware",
    "adaptive",
    "eligible_full_context",
]


def digest(value):
    if isinstance(value, BaseModel):
        value = value.model_dump(mode="json")
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator("*", mode="after")
    @classmethod
    def aware(cls, value):
        if isinstance(value, datetime):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("research_time_invalid")
            return value.astimezone(UTC)
        return value


class ResearchScope(Strict):
    owner_id: str = Field(min_length=1, max_length=200)
    application_id: str = Field(min_length=2, max_length=42)
    workspace_id: str | None = Field(default=None, max_length=100)
    acting_user_id: str = Field(min_length=1, max_length=512)

    @classmethod
    def from_request(cls, scope):
        return cls(**{key: getattr(scope, key) for key in cls.model_fields})


Kind = Literal["preference", "explicit_correction", "procedure", "project_decision"]
SourceClass = Literal["completed_user_turn", "repository_test"]


class ResearchRecord(Strict):
    id: str = Field(pattern=r"^[a-z][a-z0-9-]{0,63}$")
    scope: ResearchScope
    project: str = Field(min_length=1, max_length=100)
    kind: Kind
    source_class: SourceClass
    source_id: str = Field(pattern=r"^source-[a-z0-9-]{1,80}$")
    source_revision: str = Field(min_length=1, max_length=80)
    source_epoch: int = Field(ge=1, le=1_000_000)
    observed_at: datetime
    effective_at: datetime
    expires_at: datetime
    sensitivity: Literal["public", "restricted"]
    lifecycle: Literal["active", "forgotten", "revoked"]
    authority: Literal["user_asserted", "tool_receipt_verified"]
    topic: tuple[str, ...] = Field(min_length=1, max_length=2)
    subject: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1, max_length=2000)
    supersedes: tuple[str, ...] = Field(default=(), max_length=8)
    conflict: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def bounds(self):
        if (
            any(not part or len(part.encode()) > 80 for part in self.topic)
            or len(self.model_dump_json().encode()) > 4096
            or self.expires_at <= self.observed_at
            or (self.expires_at - self.observed_at).total_seconds() > 30 * 86400
        ):
            raise ValueError("research_record_bounds")
        return self


class ResearchQuery(Strict):
    version: Literal["memory-navigation-query-v1"] = "memory-navigation-query-v1"
    canonical: MemoryQuery
    project: str = Field(min_length=1, max_length=100)
    text: str = Field(max_length=2048)
    arm: Arm = "lexical"
    kinds: tuple[Kind, ...] = Field(default=(), max_length=4)
    source_classes: tuple[SourceClass, ...] = Field(default=(), max_length=2)
    observed_after: datetime | None = None
    effective_before: datetime | None = None
    source_revision: str | None = Field(default=None, max_length=80)
    top_k: int = Field(default=8, ge=1, le=16)

    @model_validator(mode="after")
    def bounded_envelope(self):
        q = self.canonical
        if (
            q.scope.client_context
            or q.scope.capabilities
            or not q.scope.acting_user_id
            or q.max_tokens > 1024
            or q.time_budget_seconds > 2
            or q.as_of.tzinfo is None
            or len(self.text.encode()) > 2048
            or q.query_fingerprint != sha256(self.text.encode()).hexdigest()
            or self.top_k > q.max_items
            or q.sensitivity_ceiling != "public"
            or (self.effective_before is not None and self.effective_before > q.as_of)
        ):
            raise ValueError("research_query_invalid")
        if q.knowledge is not None:
            raise ValueError("research_knowledge_adapter_unavailable")
        return self


class IndexEntry(Strict):
    record_id: str = Field(max_length=64)
    fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    content_fingerprint: str = Field(pattern=r"^[0-9a-f]{64}$")
    dependency_version: str = Field(pattern=r"^[0-9a-f]{64}$")
    terms: tuple[str, ...] = Field(max_length=128)
    topic_id: str = Field(pattern=r"^[0-9a-f]{64}$")


class Topic(Strict):
    id: str = Field(pattern=r"^[0-9a-f]{64}$")
    parent_id: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    label: str = Field(min_length=1, max_length=80)
    leaf_ids: tuple[str, ...] = Field(max_length=MAX_RECORDS)
    depth: int = Field(ge=1, le=2)


class ResearchIndex(Strict):
    version: Literal["memory-navigation-index-v1"] = "memory-navigation-index-v1"
    generation: str = Field(pattern=r"^[0-9a-f]{64}$")
    query_identity: str = Field(pattern=r"^[0-9a-f]{64}$")
    scope: ResearchScope
    project: str = Field(max_length=100)
    entries: tuple[IndexEntry, ...] = Field(max_length=MAX_RECORDS)
    topics: tuple[Topic, ...] = Field(max_length=MAX_TOPICS)


class ResearchResult(Strict):
    version: Literal["memory-navigation-result-v2"] = "memory-navigation-result-v2"
    status: Status
    reason: str = Field(max_length=80)
    generation: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")
    selected_ids: tuple[str, ...] = Field(default=(), max_length=MAX_RECORDS)
    packed_ids: tuple[str, ...] = Field(default=(), max_length=MAX_RECORDS)
    tokens: int = Field(default=0, ge=0, le=4096)
    memory_tokens: int = Field(default=0, ge=0, le=1024)
    index_bytes: int = Field(default=0, ge=0, le=MAX_BYTES)
    index_build_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    preflight_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    retrieval_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    packing_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    consume_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    elapsed_ms: float = Field(default=0, ge=0, allow_inf_nan=False)
    fetch_pages: int = Field(default=0, ge=0, le=2)
    answer: str | None = Field(default=None, max_length=400)
    citations: tuple[str, ...] = Field(default=(), max_length=MAX_RECORDS)
    counter_kind: Literal["estimated"] = "estimated"
    provider_calls: Literal[0] = 0
    reported_usage: None = None
    cost: Literal["offline_no_charge"] = "offline_no_charge"


class ResearchFailure(Exception):
    def __init__(self, status: Status, reason: str):
        self.status, self.reason = status, reason
        super().__init__(reason)

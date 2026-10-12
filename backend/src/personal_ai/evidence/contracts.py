"""Versioned immutable observations and expiring evidence, never user memory."""

from datetime import UTC, datetime
from hashlib import sha256
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from personal_ai.auth.scope import ApplicationScopedRecord


class ResearchRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    @field_validator(
        "created_at",
        "updated_at",
        "observed_at",
        "expires_at",
        "started_at",
        "completed_at",
        "executed_at",
        "published_at",
        "execution_deadline",
        check_fields=False,
    )
    @classmethod
    def utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        if value.tzinfo is None or value.utcoffset() is None:
            raise ValueError("timezone required")
        return value.astimezone(UTC)


class ScopedResearchRecord(ResearchRecord, ApplicationScopedRecord):
    """Persisted research record; request envelopes remain unscoped inputs."""


class SearchQuery(ScopedResearchRecord):
    id: UUID
    session_id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    normalized_query: str = Field(min_length=1, max_length=500)
    rationale_code: Literal[
        "question", "terminology", "required_fact_missing", "evidence_stale",
        "source_conflict", "candidate_coverage", "identity_ambiguity",
    ] = "question"
    parent_query_id: UUID | None = None
    gap_id: UUID | None = None
    sequence: int = Field(ge=0, le=2)
    state: Literal["planned", "completed", "failed"] = "planned"
    created_at: datetime
    executed_at: datetime | None = None


class AdapterAttempt(ScopedResearchRecord):
    id: UUID
    session_id: UUID
    query_id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    adapter: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_-]*$")
    idempotency_key: str = Field(min_length=1, max_length=200)
    attempt_number: int = Field(ge=1, le=3)
    status: Literal["started", "completed", "failed"]
    parent_attempt_id: UUID | None = None
    started_at: datetime
    completed_at: datetime | None = None
    error_code: str | None = Field(default=None, max_length=80)
    usage_invocation_id: UUID | None = None
    usage_attempt_id: UUID | None = None
    operation_identity: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    strategy_id: str | None = Field(default=None, max_length=100)
    strategy_version: int | None = Field(default=None, ge=1)
    strategy_reason: str | None = Field(default=None, max_length=80)

    @model_validator(mode="after")
    def usage_identity(self):
        if self.usage_attempt_id is not None and self.usage_invocation_id is None:
            raise ValueError("physical attempt requires canonical invocation")
        operation_fields = (
            self.operation_identity,
            self.strategy_id,
            self.strategy_version,
            self.strategy_reason,
        )
        if any(value is not None for value in operation_fields) and any(
            value is None for value in operation_fields
        ):
            raise ValueError("incomplete admitted search operation reference")
        return self


class SourceObservation(ScopedResearchRecord):
    id: UUID
    session_id: UUID
    query_id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    canonical_url: str = Field(min_length=1, max_length=2048)
    title: str | None = Field(default=None, max_length=300)
    provider: str = Field(min_length=1, max_length=100, pattern=r"^[a-z][a-z0-9_-]*$")
    observed_at: datetime
    published_at: datetime | None = None
    source_revision: str | None = Field(default=None, min_length=1, max_length=100)
    content_fingerprint: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")
    status: Literal[
        "accepted", "empty", "unsafe", "oversized", "stale", "source_denied", "freshness_unverified"
    ]
    attempt_id: UUID
    rights_reference: str | None = Field(default=None, max_length=200)
    rights_authority_id: str | None = Field(default=None, max_length=200)
    rights_epoch: str | None = Field(default=None, max_length=100)
    sensitivity: Literal["public"] = "public"
    result_index: int | None = Field(default=None, ge=0, le=11)
    passage: str | None = Field(default=None, max_length=1200)
    observation_version: Literal["legacy-v1", "snippet-observation-v2"] = "legacy-v1"
    source_origin: Literal["legacy_unknown", "synthetic", "external"] = "legacy_unknown"
    freshness_basis: Literal["observation_only", "publication"] = "observation_only"

    @model_validator(mode="after")
    def safe_source(self):
        from personal_ai.search.policy import canonical_url

        if self.status == "accepted" and (
            canonical_url(self.canonical_url) != self.canonical_url or not self.content_fingerprint
        ):
            raise ValueError("invalid attribution")
        if self.observation_version == "snippet-observation-v2" and self.status == "accepted":
            if not self.rights_reference or not self.passage or self.result_index is None:
                raise ValueError("missing observation provenance")
            if self.rights_authority_id is not None and not self.rights_epoch:
                raise ValueError("missing source-rights epoch")
            if sha256(" ".join(self.passage.split()).encode()).hexdigest() != self.content_fingerprint:
                raise ValueError("observation fingerprint")
        return self


# The existing source observation remains canonical; no second observation store.
EvidenceObservation = SourceObservation


class EvidenceSupport(ResearchRecord):
    evidence_id: UUID
    observation_ids: tuple[UUID, ...] = Field(min_length=1, max_length=12)
    start: Literal[0] = 0
    end: int = Field(ge=1, le=1200)
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class DerivedEvidence(ResearchRecord):
    """Extractive package identity, never an original observation or domain fact."""

    id: UUID
    version: Literal["extractive-package-v1"] = "extractive-package-v1"
    transformation: Literal["whole-passage-extractive-v1"] = "whole-passage-extractive-v1"
    packing_strategy: Literal["literal-extractive-v1", "compact-extractive-v1"] = "literal-extractive-v1"
    support: tuple[EvidenceSupport, ...] = Field(max_length=12)
    omitted_ids: tuple[UUID, ...] = Field(max_length=12)
    conflict_status: Literal["unresolved_all_eligible_required"] = "unresolved_all_eligible_required"
    input_bytes: int = Field(ge=0)
    output_bytes: int = Field(ge=0)
    compression_calls: Literal[0] = 0


class Evidence(ScopedResearchRecord):
    id: UUID
    session_id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    source_observation_ids: tuple[UUID, ...] = Field(min_length=1, max_length=12)
    passage: str = Field(min_length=1, max_length=1200)
    content_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    observed_at: datetime
    expires_at: datetime
    expiry_policy: Literal["general", "current"]
    extraction_version: Literal["snippet-v1"] = "snippet-v1"
    status: Literal["eligible"] = "eligible"
    near_duplicate_ids: tuple[UUID, ...] = ()

    @model_validator(mode="after")
    def expiry(self):
        if self.expires_at <= self.observed_at or not self.passage.strip():
            raise ValueError("invalid evidence")
        expected = sha256(" ".join(self.passage.split()).encode()).hexdigest()
        if self.content_fingerprint != expected or len(set(self.source_observation_ids)) != len(
            self.source_observation_ids
        ):
            raise ValueError("invalid content provenance")
        return self


class EvidenceSelection(ScopedResearchRecord):
    id: UUID
    session_id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    evidence_ids: tuple[UUID, ...] = Field(max_length=12)
    excluded: dict[str, str]
    scores: dict[str, dict[str, float]]
    selector_policy_version: Literal["select-v1"] = "select-v1"
    token_count: int = Field(ge=0)
    counter_kind: Literal["provider", "estimated"]
    created_at: datetime
    ranking_strategy: str = Field(default="literal-diversity-v1", max_length=100)
    ranking_fallback: bool = False
    packing_strategy: Literal["literal-extractive-v1", "compact-extractive-v1"] = "literal-extractive-v1"
    derived: DerivedEvidence | None = None

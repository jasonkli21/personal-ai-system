"""Additive source-neutral wire contracts; historical research remains unchanged."""

import json
import re
from datetime import datetime
from hashlib import sha256
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from personal_ai.evidence.contracts import ResearchRecord
from personal_ai.search.policy import canonical_url


def identity(*values):
    return sha256(
        json.dumps(values, ensure_ascii=False, separators=(",", ":")).encode()
    ).hexdigest()


Reason = Literal[
    "no_matches",
    "source_unavailable",
    "source_authority_changed",
    "external_unconfigured",
    "external_not_admitted",
    "external_outcome_unknown",
    "external_already_attempted",
    "quota",
    "timeout",
    "invalid_source",
    "freshness_unverified",
    "budget",
    "busy",
]


class RetrievalQuery(ResearchRecord):
    schema_version: Literal["retrieval-v1"] = "retrieval-v1"
    idempotency_key: UUID
    query: str = Field(min_length=1, max_length=400)
    sources: tuple[Literal["local", "external"], ...] = Field(
        default=("local",), min_length=1, max_length=2
    )
    purpose: Literal["interactive_retrieval"] = "interactive_retrieval"
    max_items: int = Field(default=5, ge=1, le=8, strict=True)
    max_quote_bytes: int = Field(default=4096, ge=64, le=8192, strict=True)
    max_tokens: int = Field(default=8192, ge=64, le=16384, strict=True)
    max_age_seconds: int = Field(default=86400, ge=60, le=86400, strict=True)
    allowed_domains: tuple[str, ...] = Field(default=(), max_length=8)
    excluded_domains: tuple[str, ...] = Field(default=(), max_length=8)
    published_after: datetime | None = None

    @field_validator("allowed_domains", "excluded_domains")
    @classmethod
    def domains(cls, values):
        if len(set(values)) != len(values) or any(
            not re.fullmatch(r"[a-z0-9][a-z0-9.-]{0,199}", value)
            or canonical_url("https://" + value) != "https://" + value + "/"
            for value in values
        ):
            raise ValueError("invalid_domain")
        return values

    @model_validator(mode="after")
    def bounded(self):
        if (
            len(set(self.sources)) != len(self.sources)
            or not self.query.strip()
            or any(ord(c) < 32 for c in self.query)
            or self.published_after is not None
            and (self.published_after.tzinfo is None or self.published_after.utcoffset() is None)
        ):
            raise ValueError("invalid_query")
        return self


class RetrievalItem(ResearchRecord):
    source_id: str = Field(min_length=1, max_length=100)
    passage_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    citation_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    origin: Literal["local", "external", "synthetic"]
    provider: str = Field(min_length=1, max_length=100)
    quote_basis: Literal["literal_document", "normalized_provider_snippet"]
    revision_basis: Literal["operator_revision", "provider_revision", "observation_hash"]
    rights_authority_id: str = Field(min_length=1, max_length=200)
    url: str | None = Field(default=None, max_length=2048)
    title: str = Field(min_length=1, max_length=300)
    quote: str = Field(min_length=1, max_length=1200)
    source_revision: str = Field(min_length=1, max_length=100)
    content_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    rights_epoch: str = Field(min_length=1, max_length=100)
    rights_reference: str = Field(min_length=1, max_length=200)
    license: str = Field(min_length=1, max_length=100)
    sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    observed_at: datetime
    published_at: datetime | None = None
    expires_at: datetime
    freshness_basis: Literal["observation_only", "publication"]
    start: int = Field(ge=0)
    end: int = Field(ge=1)

    @model_validator(mode="after")
    def fidelity(self):
        fingerprint = sha256(self.quote.encode()).hexdigest()
        passage = identity(
            self.origin,
            self.provider,
            self.url,
            self.source_id,
            self.source_revision,
            self.start,
            self.end,
            fingerprint,
        )
        citation = identity(
            passage, self.rights_authority_id, self.rights_epoch, self.rights_reference
        )
        if (
            fingerprint != self.content_fingerprint
            or passage != self.passage_id
            or citation != self.citation_id
            or self.end - self.start != len(self.quote)
            or self.observed_at >= self.expires_at
            or (self.published_at is not None and self.published_at > self.observed_at)
            or self.freshness_basis != ("publication" if self.published_at else "observation_only")
            or (
                self.origin == "local"
                and (
                    self.url is not None
                    or self.quote_basis != "literal_document"
                    or self.revision_basis != "operator_revision"
                )
            )
            or (
                self.origin != "local"
                and (
                    self.url is None
                    or canonical_url(self.url) != self.url
                    or self.sensitivity != "public"
                    or self.quote_basis != "normalized_provider_snippet"
                    or self.revision_basis == "operator_revision"
                )
            )
        ):
            raise ValueError("retrieval_attribution_invalid")
        return self


class RetrievalOutcome(ResearchRecord):
    schema_version: Literal["retrieval-v1"] = "retrieval-v1"
    idempotency_key: UUID
    state: Literal["complete", "partial", "unavailable"]
    reasons: tuple[Reason, ...] = Field(default=(), max_length=16)
    items: tuple[RetrievalItem, ...] = Field(default=(), max_length=8)
    quote_bytes: int = Field(default=0, ge=0, le=8192)
    token_upper_bound: int = Field(default=0, ge=0, le=16384)
    # External pricing is governed by P19, never inferred from an estimated price.
    usage_invocation_id: UUID | None = None
    usage_attempt_id: UUID | None = None
    context_integration: Literal["unavailable"] = "unavailable"

    @model_validator(mode="after")
    def aggregate(self):
        if self.quote_bytes != sum(len(i.quote.encode()) for i in self.items):
            raise ValueError("retrieval_size_invalid")
        if self.state == "unavailable" and self.items:
            raise ValueError("retrieval_outcome_invalid")
        if self.usage_attempt_id and not self.usage_invocation_id:
            raise ValueError("retrieval_usage_invalid")
        return self


def item_from_quote(*, source_id, revision, quote, start=0, **metadata):
    fingerprint = sha256(quote.encode()).hexdigest()
    end = start + len(quote)
    passage = identity(
        metadata["origin"],
        metadata["provider"],
        metadata.get("url"),
        source_id,
        revision,
        start,
        end,
        fingerprint,
    )
    citation = identity(
        passage,
        metadata["rights_authority_id"],
        metadata["rights_epoch"],
        metadata["rights_reference"],
    )
    return RetrievalItem(
        source_id=source_id,
        source_revision=revision,
        quote=quote,
        start=start,
        end=end,
        content_fingerprint=fingerprint,
        passage_id=passage,
        citation_id=citation,
        **metadata,
    )

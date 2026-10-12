"""Phase 5 request, aggregate, result and safe progress contracts."""

from datetime import datetime
from hashlib import sha256
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from personal_ai.evidence.contracts import (
    AdapterAttempt,
    Evidence,
    EvidenceSelection,
    ResearchRecord,
    ScopedResearchRecord,
    SearchQuery,
    SourceObservation,
)
from personal_ai.search.planning import ResearchQueryPlan, domains_from_question


class ResearchError(Exception):
    def __init__(self, code: str, status: int = 503):
        self.code, self.status = code, status
        super().__init__(code)


class ResearchRequest(ResearchRecord):
    schema_version: Literal["research-v1"] = "research-v1"
    question: str = Field(min_length=1, max_length=500)
    freshness: Literal["general", "current"] = "general"
    idempotency_key: UUID
    allowed_domains: tuple[str, ...] = Field(default=(), max_length=12)
    excluded_domains: tuple[str, ...] = Field(default=(), max_length=12)
    published_after: datetime | None = None

    @field_validator("published_after")
    @classmethod
    def aware_publication_bound(cls, value):
        if value is not None and value.tzinfo is None:
            raise ValueError("publication bound timezone required")
        return value

    @field_validator("allowed_domains", "excluded_domains")
    @classmethod
    def domains(cls, values):
        import re

        if len(set(values)) != len(values) or any(
            len(value) > 253 or not re.fullmatch(r"[a-z0-9]+(?:[.-][a-z0-9]+)*\.[a-z]{2,}", value)
            for value in values
        ):
            raise ValueError("invalid source domains")
        return values

    @field_validator("question")
    @classmethod
    def normalize(cls, value):
        value = " ".join(value.split())
        if not value or any(ord(c) < 32 for c in value):
            raise ValueError("invalid question")
        return value

    def fingerprint(self) -> str:
        # Empty additive fields preserve historical v1 request fingerprints.
        excluded = {"idempotency_key"}
        excluded.update(
            name for name in ("allowed_domains", "excluded_domains", "published_after")
            if not getattr(self, name)
        )
        return sha256(self.model_dump_json(exclude=excluded).encode()).hexdigest()

    def source_bounds(self, allowed_domains=None):
        literal_allowed, literal_excluded = domains_from_question(self.question)
        # Both allowlists must apply, rather than widening either one by union.
        typed_allowed = self.allowed_domains if allowed_domains is None else tuple(allowed_domains)
        return typed_allowed, literal_allowed, (*self.excluded_domains, *literal_excluded)


class Citation(ScopedResearchRecord):
    number: int = Field(ge=1)
    evidence_id: UUID
    source_observation_id: UUID
    url: str
    title: str | None
    observed_at: datetime
    expires_at: datetime


class ResearchSession(ScopedResearchRecord):
    schema_version: Literal["research-v1"] = "research-v1"
    id: UUID
    owner_id: str = Field(min_length=1, max_length=200)
    request: ResearchRequest
    request_fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")
    iterative_run_id: UUID | None = None
    mode: Literal["research"] = "research"
    policy_version: Literal["research-v1"] = "research-v1"
    state: Literal["pending", "running", "completed", "insufficient", "failed", "expired"]
    created_at: datetime
    updated_at: datetime
    expires_at: datetime
    failure_code: str | None = Field(default=None, max_length=80)
    execution_deadline: datetime | None = None
    run_token: UUID | None = Field(default=None, exclude=True)
    revision: int = Field(default=0, ge=0)
    queries: tuple[SearchQuery, ...] = Field(default=(), max_length=3)
    query_plan: ResearchQueryPlan | None = None
    attempts: tuple[AdapterAttempt, ...] = Field(default=(), max_length=18)
    observations: tuple[SourceObservation, ...] = Field(default=(), max_length=12)
    evidence: tuple[Evidence, ...] = Field(default=(), max_length=12)
    selection: EvidenceSelection | None = None
    answer: str | None = Field(default=None, max_length=20000)
    citations: tuple[Citation, ...] = Field(default=(), max_length=144)

    @model_validator(mode="after")
    def provenance(self):
        if self.request_fingerprint != self.request.fingerprint():
            raise ValueError("request fingerprint mismatch")
        if self.state == "running" and (not self.execution_deadline or not self.run_token):
            raise ValueError("missing execution fence")
        if self.updated_at < self.created_at or self.expires_at <= self.created_at:
            raise ValueError("invalid session timestamps")
        records = (*self.queries, *self.attempts, *self.observations, *self.evidence)
        if self.selection:
            records = (*records, self.selection)
        if any(r.owner_id != self.owner_id or r.session_id != self.id for r in records):
            raise ValueError("foreign provenance")
        ids = [r.id for r in records]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate record id")
        queries = {r.id for r in self.queries}
        if self.query_plan and (
            self.query_plan.original_question != self.request.question
            or self.query_plan.freshness != self.request.freshness
            or self.query_plan.allowed_domains != self.request.allowed_domains
            or self.query_plan.excluded_domains != self.request.excluded_domains
            or self.query_plan.published_after != self.request.published_after
            or tuple(q.normalized_query for q in self.queries) != self.query_plan.queries
        ):
            raise ValueError("query plan binding")
        if tuple(item.sequence for item in self.queries) != tuple(range(len(self.queries))):
            raise ValueError("query sequence must be contiguous")
        if any(
            query.parent_query_id is not None
            and query.parent_query_id not in {old.id for old in self.queries[:query.sequence]}
            for query in self.queries
        ):
            raise ValueError("unknown parent query")
        attempts = {r.id: r for r in self.attempts}
        sources = {r.id: r for r in self.observations}
        evidence = {r.id: r for r in self.evidence}
        if any(a.query_id not in queries for a in self.attempts):
            raise ValueError("unknown attempt query")
        for attempt in self.attempts:
            if attempt.status == "started":
                if attempt.completed_at is not None or attempt.parent_attempt_id is not None:
                    raise ValueError("invalid started attempt")
            else:
                parent = attempts.get(attempt.parent_attempt_id)
                if (
                    not parent
                    or parent.status != "started"
                    or not attempt.completed_at
                    or parent.query_id != attempt.query_id
                    or parent.attempt_number != attempt.attempt_number
                    or parent.started_at != attempt.started_at
                    or parent.operation_identity != attempt.operation_identity
                    or parent.strategy_id != attempt.strategy_id
                    or parent.strategy_version != attempt.strategy_version
                    or parent.strategy_reason != attempt.strategy_reason
                    or parent.usage_invocation_id not in {None, attempt.usage_invocation_id}
                    or parent.usage_attempt_id not in {None, attempt.usage_attempt_id}
                    or attempt.completed_at < attempt.started_at
                ):
                    raise ValueError("invalid terminal attempt")
        for source in self.observations:
            attempt = attempts.get(source.attempt_id)
            if not attempt or attempt.query_id != source.query_id or attempt.status != "completed":
                raise ValueError("unknown source attempt")
        for item in self.evidence:
            if any(
                i not in sources
                or sources[i].status != "accepted"
                or sources[i].content_fingerprint != item.content_fingerprint
                or (sources[i].observation_version == "snippet-observation-v2"
                    and sources[i].passage != item.passage)
                for i in item.source_observation_ids
            ):
                raise ValueError("unknown evidence source")
        selected = set(self.selection.evidence_ids) if self.selection else set()
        if self.selection and len(selected) != len(self.selection.evidence_ids):
            raise ValueError("duplicate selection")
        if selected - evidence.keys():
            raise ValueError("unknown selected evidence")
        if self.selection and self.selection.derived:
            derived = self.selection.derived
            if derived.packing_strategy != self.selection.packing_strategy:
                raise ValueError("derived strategy binding")
            if tuple(s.evidence_id for s in derived.support) != self.selection.evidence_ids:
                raise ValueError("derived support coverage")
            for support in derived.support:
                item = evidence[support.evidence_id]
                if (
                    support.observation_ids != item.source_observation_ids
                    or support.end != len(item.passage)
                    or support.fingerprint != item.content_fingerprint
                ):
                    raise ValueError("derived exact support")
            if set(derived.omitted_ids) & selected or set(derived.omitted_ids) - evidence.keys():
                raise ValueError("derived omission coverage")
        for citation in self.citations:
            if (
                citation.evidence_id not in selected
                or citation.source_observation_id
                not in evidence[citation.evidence_id].source_observation_ids
                or citation.url != sources[citation.source_observation_id].canonical_url
                or citation.expires_at != evidence[citation.evidence_id].expires_at
                or citation.observed_at != evidence[citation.evidence_id].observed_at
            ):
                raise ValueError("invalid citation")
        if self.state == "completed" and (
            not self.answer
            or not self.citations
            or {c.evidence_id for c in self.citations} != selected
        ):
            raise ValueError("uncited result")
        return self


def evolve(session: ResearchSession, **changes) -> ResearchSession:
    data = session.model_dump()
    data["run_token"] = session.run_token
    return ResearchSession.model_validate({**data, **changes})

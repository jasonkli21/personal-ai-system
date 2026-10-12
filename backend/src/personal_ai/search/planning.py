"""Constraint-preserving plans; strategies cannot change the admitted envelope."""

import re
from datetime import datetime
from hashlib import sha256
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ResearchQueryPlan(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research-query-plan-v1"] = "research-query-plan-v1"
    strategy_id: str = Field(max_length=100)
    strategy_version: int = Field(ge=1)
    original_question: str = Field(min_length=1, max_length=500)
    queries: tuple[str, ...] = Field(max_length=3)
    operation: Literal["search"] = "search"
    freshness: Literal["general", "current"]
    published_after: datetime | None = None
    allowed_domains: tuple[str, ...] = Field(default=(), max_length=12)
    excluded_domains: tuple[str, ...] = Field(default=(), max_length=12)
    max_queries: int = Field(ge=1, le=3)
    max_sources: int = Field(ge=1, le=12)
    max_attempts_per_query: int = Field(ge=1, le=3)
    timeout_seconds: float = Field(gt=0, allow_inf_nan=False)
    reason: Literal["baseline", "experiment", "invalid_strategy_fallback"]

    @model_validator(mode="after")
    def bounded(self):
        if len(self.queries) > self.max_queries or len(set(self.queries)) != len(self.queries):
            raise ValueError("query_budget")
        if any(not preserves_question(self.original_question, q) for q in self.queries):
            raise ValueError("query_constraints")
        return self

    @property
    def identity(self):
        return sha256(self.model_dump_json().encode()).hexdigest()


def preserves_question(question: str, query: str) -> bool:
    """Keep order, multiplicity, spelling, punctuation and literals exactly.

    Only a bounded plain-word qualifier may follow the original question. Tool
    syntax, Boolean operators and negation in qualifiers fail to the literal path.
    This is deliberately stricter than semantic rewrite equivalence.
    """
    question = " ".join(question.split())
    if not isinstance(query, str) or not query or len(query) > 500:
        return False
    if query == question:
        return True
    if not query.startswith(question + " "):
        return False
    suffix = query[len(question) + 1:]
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9 ]{0,79}", suffix)) and not (
        set(suffix.lower().split()) & {"or", "and", "not", "no", "without", "exclude", "except"}
    )


def make_query_plan(planner, request, settings):
    from personal_ai.search.policy import planned_queries

    queries, reason = planned_queries(planner, request.question, settings.research_max_queries,
                                      with_reason=True)
    baseline = (request.question,)
    return ResearchQueryPlan(
        strategy_id="literal-snippet" if reason == "invalid_strategy_fallback" else planner.strategy_id,
        strategy_version=1 if reason == "invalid_strategy_fallback" else planner.strategy_version,
        original_question=request.question,
        queries=queries,
        freshness=request.freshness,
        published_after=request.published_after,
        allowed_domains=request.allowed_domains,
        excluded_domains=request.excluded_domains,
        max_queries=settings.research_max_queries,
        max_sources=settings.research_max_sources,
        max_attempts_per_query=settings.research_attempt_limit,
        timeout_seconds=settings.research_timeout_seconds,
        reason=reason if reason == "invalid_strategy_fallback" else (
            "baseline" if queries == baseline else "experiment"
        ),
    )


def domains_from_question(question):
    allowed, excluded = [], []
    for match in re.finditer(r"(?<!\S)(-?)site:([A-Za-z0-9.-]+)(?=\s|$)", question):
        (excluded if match[1] else allowed).append(match[2].lower().rstrip("."))
    return tuple(dict.fromkeys(allowed)), tuple(dict.fromkeys(excluded))


def source_allowed(url, allowed, excluded):
    from urllib.parse import urlsplit

    host = (urlsplit(url).hostname or "").lower().rstrip(".")
    matches = lambda domain: host == domain or host.endswith("." + domain)
    return bool(host) and not any(matches(d) for d in excluded) and (
        not allowed or any(matches(d) for d in allowed)
    )


class SearchOperation(BaseModel):
    """Immutable, admitted envelope for one physical search operation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    schema_version: Literal["research-search-operation-v1"] = "research-search-operation-v1"
    operation_id: str = Field(pattern=r"^[a-f0-9]{64}$")
    query_id: UUID
    query: str = Field(min_length=1, max_length=500)
    original_question: str = Field(min_length=1, max_length=500)
    strategy_id: str = Field(min_length=1, max_length=100)
    strategy_version: int = Field(ge=1)
    strategy_reason: str = Field(min_length=1, max_length=80)
    plan_identity: str = Field(pattern=r"^[a-f0-9]{64}$")
    allowed_domains: tuple[str, ...] = Field(default=(), max_length=12)
    literal_allowed_domains: tuple[str, ...] = Field(default=(), max_length=12)
    excluded_domains: tuple[str, ...] = Field(default=(), max_length=24)
    published_after: datetime | None = None
    max_results: int = Field(ge=1, le=12)
    deadline_at: datetime

    @model_validator(mode="after")
    def immutable_query_and_bounds(self):
        if not preserves_question(self.original_question, self.query):
            raise ValueError("search_operation_query_constraints")
        if self.deadline_at.tzinfo is None or self.deadline_at.utcoffset() is None:
            raise ValueError("search_operation_deadline_timezone")
        if len(set(self.allowed_domains)) != len(self.allowed_domains):
            raise ValueError("search_operation_domain_duplicate")
        if len(set(self.literal_allowed_domains)) != len(self.literal_allowed_domains):
            raise ValueError("search_operation_literal_domain_duplicate")
        if len(set(self.excluded_domains)) != len(self.excluded_domains):
            raise ValueError("search_operation_excluded_domain_duplicate")
        return self

    @property
    def identity(self):
        return self.operation_id


def make_search_operation(
    request,
    query,
    *,
    query_id,
    max_results,
    deadline_at,
    plan=None,
    strategy_id=None,
    strategy_version=1,
    strategy_reason=None,
    allowed_domains=None,
):
    """Bind a planned query to the exact request constraints before dispatch."""
    allowed, literal_allowed, excluded = request.source_bounds()
    if allowed_domains is not None:
        allowed = tuple(allowed_domains)
    if plan is not None:
        strategy_id = plan.strategy_id
        strategy_version = plan.strategy_version
        strategy_reason = plan.reason
        plan_identity = plan.identity
    else:
        strategy_id = strategy_id or "iterative-followup"
        strategy_reason = strategy_reason or getattr(query, "rationale_code", "question")
        plan_identity = sha256(
            "|".join((
                request.question,
                query.normalized_query,
                strategy_id,
                str(strategy_version),
                strategy_reason,
                ",".join(allowed),
                ",".join(literal_allowed),
                ",".join(excluded),
                request.published_after.isoformat() if request.published_after else "",
            )).encode()
        ).hexdigest()
    query_text = query.normalized_query
    identity = sha256("|".join((
        str(query_id), query_text, plan_identity, str(max_results),
        deadline_at.isoformat(),
    )).encode()).hexdigest()
    return SearchOperation(
        operation_id=identity,
        query_id=query_id,
        query=query_text,
        original_question=request.question,
        strategy_id=strategy_id,
        strategy_version=strategy_version,
        strategy_reason=strategy_reason,
        plan_identity=plan_identity,
        allowed_domains=tuple(allowed),
        literal_allowed_domains=tuple(literal_allowed),
        excluded_domains=tuple(dict.fromkeys(excluded)),
        published_after=request.published_after,
        max_results=max_results,
        deadline_at=deadline_at,
    )


def effective_allowed_domains(operation: SearchOperation) -> tuple[str, ...]:
    """Intersect typed and literal allowlists, retaining the narrower subdomain."""
    typed, literal = operation.allowed_domains, operation.literal_allowed_domains
    if not typed:
        candidates = literal
    elif not literal:
        candidates = typed
    else:
        intersection = []
        for left in typed:
            for right in literal:
                if left == right or left.endswith("." + right):
                    intersection.append(left)
                elif right.endswith("." + left):
                    intersection.append(right)
        candidates = tuple(dict.fromkeys(intersection))
    result = []
    for domain in candidates:
        if not any(
            domain == denied or domain.endswith("." + denied)
            for denied in operation.excluded_domains
        ):
            result.append(domain)
    return tuple(dict.fromkeys(result))

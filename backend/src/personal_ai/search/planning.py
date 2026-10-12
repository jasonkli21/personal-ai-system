"""Constraint-preserving plans; strategies cannot change the admitted envelope."""

import re
from datetime import datetime
from hashlib import sha256
from typing import Literal

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

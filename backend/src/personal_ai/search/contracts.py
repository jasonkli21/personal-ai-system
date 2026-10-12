"""Replaceable search/planning/extraction/reranking interfaces."""

import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from math import isfinite
from typing import Protocol
from uuid import UUID

from pydantic import Field

from personal_ai.evidence.contracts import Evidence, ResearchRecord
from personal_ai.search.planning import SearchOperation


class SearchResult(ResearchRecord):
    url: str = Field(max_length=2048)
    title: str | None = Field(default=None, max_length=300)
    text: str = Field(max_length=10000)
    published_at: datetime | None = None
    source_revision: str | None = Field(default=None, min_length=1, max_length=100)


class SearchAdapter(Protocol):
    name: str
    source_origin: str
    cost_profile: "SearchCostProfile"

    def authorize_snippets(self):
        """Current server-owned rights/preflight reference; deny before dispatch."""
        ...

    async def search(self, operation: SearchOperation) -> "SearchDispatch": ...


@dataclass(frozen=True, slots=True)
class SearchCostProfile:
    profile_id: str
    estimated_cost_usd: float
    quota_operation: str = "search"

    def __post_init__(self):
        if (
            not self.profile_id
            or len(self.profile_id) > 100
            or not isfinite(self.estimated_cost_usd)
            or self.estimated_cost_usd < 0
            or not re.fullmatch(r"[a-z][a-z0-9_]{0,79}", self.quota_operation)
        ):
            raise ValueError("search_cost_profile_invalid")


@dataclass(frozen=True, slots=True)
class SearchDispatch:
    """Adapter output with references returned by the canonical P19 path."""

    results: tuple[SearchResult, ...]
    usage_invocation_id: UUID | None = None
    usage_attempt_id: UUID | None = None

    def __post_init__(self):
        if self.usage_attempt_id is not None and self.usage_invocation_id is None:
            raise ValueError("search_dispatch_usage_identity_incomplete")


@dataclass(frozen=True, slots=True)
class SearchRightsAuthorization:
    """Current source-rights authority, account scope, epoch and preflight proof."""

    provider_id: str
    authority_id: str
    epoch: str
    reference: str

    @property
    def dependency_version(self):
        return f"{self.epoch}:{self.reference}"


def normalize_rights_authorization(value, provider_id: str) -> SearchRightsAuthorization | None:
    if isinstance(value, SearchRightsAuthorization):
        return value
    # Read compatibility for test/custom adapters and historical provider refs.
    if isinstance(value, str) and value and len(value) <= 200:
        return SearchRightsAuthorization(provider_id, provider_id, "legacy-v1", value)
    return None


class QueryPlanner(Protocol):
    strategy_id: str
    strategy_version: int

    def plan(self, question: str, max_queries: int) -> Sequence[str]: ...


class ContentExtractor(Protocol):
    def extract(self, text: str) -> str: ...


class EvidenceReranker(Protocol):
    strategy_id: str

    def rank(self, question: str, evidence: Sequence[Evidence]) -> Sequence[Evidence]: ...


class FakeSearchAdapter:
    name = "fake"
    source_origin = "synthetic"
    cost_profile = SearchCostProfile("synthetic-zero-cost-v1", 0.0)

    def authorize_snippets(self):
        return SearchRightsAuthorization(
            provider_id=self.name,
            authority_id=f"{self.name}:synthetic-public-v1",
            epoch="1",
            reference="synthetic-public-v1",
        )

    def __init__(self, results: Sequence[SearchResult] = (), error: Exception | None = None):
        self.results, self.error = tuple(results), error
        self.calls: list[SearchOperation] = []

    async def search(self, operation: SearchOperation):
        self.calls.append(operation)
        if self.error:
            raise self.error
        return SearchDispatch(self.results[:operation.max_results])

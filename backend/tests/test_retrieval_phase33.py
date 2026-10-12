"""Production-composed, bounded research regression and paired evaluation evidence."""

import asyncio
from datetime import timedelta
from uuid import uuid4

import httpx
import pytest

from personal_ai.agents.research.contracts import ResearchError, evolve
from personal_ai.api.research import research_service
from personal_ai.auth.scope import ApplicationScope
from personal_ai.context.authority import source_snapshots_current
from personal_ai.contracts.context_references import ContextSourceSnapshot
from personal_ai.evaluation.research import NOW, _application_context, build_fixture, load_fixtures
from personal_ai.evaluation.retrieval import VARIANTS, load_configuration, measure, run
from personal_ai.search.authority import observation_dependencies
from personal_ai.search.contracts import FakeSearchAdapter, SearchResult
from personal_ai.search.planning import make_query_plan, preserves_question
from personal_ai.search.policy import planned_queries
from personal_ai.search.providers.brave import SearchError
from personal_ai.search.runtime import SEARCH_ADAPTERS, SearchAdapterRegistration
from personal_ai.settings import Settings
from personal_ai.usage.contracts import UsageAdmissionDenied
from tests.test_research_pipeline import complete
from tests.test_research_provider import adapter as brave_adapter


@pytest.fixture
def anyio_backend():
    return "asyncio"


@pytest.mark.parametrize("question", [
    'Atlas must not exceed 12 kg before 2026-10-12 "AX-2"',
    '"Atlas Pro" is not "Atlas Mini"',
    'Atlas site:example.org -site:example.net 10 mm',
    'Atlas 1 1 2 not 2 1 1',
])
def test_literal_order_multiplicity_and_quoted_identifiers(question):
    assert preserves_question(question, question)
    assert preserves_question(question, question + " specification")
    for changed in (question[:-1], " ".join(reversed(question.split())),
                    question + " OR site:forbidden.org", question + " without constraints"):
        assert not preserves_question(question, changed)


def test_malformed_strategy_falls_back_inside_original_envelope():
    service, request = build_fixture(load_fixtures()[0], research_max_queries=2)

    class BadPlanner:
        def plan(self, question, max_queries):
            return (question + " OR site:forbidden.org",)

    plan = make_query_plan(BadPlanner(), request, service.settings)
    assert plan.queries == (request.question,)
    assert plan.max_queries == 2 and plan.max_attempts_per_query == 2
    assert plan.identity == make_query_plan(BadPlanner(), request, service.settings).identity
    assert planned_queries(BadPlanner(), request.question, 2) == plan.queries


@pytest.mark.anyio
async def test_new_adapter_through_actual_api_composition_and_unknown_fails_closed(monkeypatch):
    class Alternate(FakeSearchAdapter):
        name = "alternate"

    adapter = Alternate((SearchResult(url="https://example.org/atlas", text="Synthetic Atlas 12 kg."),))
    monkeypatch.setitem(SEARCH_ADAPTERS, "alternate", SearchAdapterRegistration(
        lambda settings, usage: adapter, synthetic=True
    ))
    fixture_service, request = build_fixture(load_fixtures()[0])
    settings = Settings(_env_file=None, ai_provider="gemini", ai_model="synthetic",
                        research_enabled=True, research_storage="memory",
                        research_search_adapter="alternate")
    service = research_service(settings, fixture_service.repository, "local", _application_context())
    service.clock = lambda: NOW
    request = request.model_copy(update={"question": "Synthetic Atlas weight?"})
    result, _ = await complete(service, request)
    assert result.state == "completed"
    assert result.attempts[0].adapter == result.observations[0].provider == "alternate"
    assert result.query_plan.operation == "search" and len(adapter.calls) == 1
    settings.research_search_adapter = "uninstalled"
    with pytest.raises(ResearchError, match="research_configuration_invalid"):
        research_service(settings, fixture_service.repository, "local", _application_context())
    class Unavailable:
        source_origin = "synthetic"

        def authorize_snippets(self):
            return "synthetic-public-v1"

    settings.research_search_adapter = "alternate"
    monkeypatch.setitem(SEARCH_ADAPTERS, "alternate", SearchAdapterRegistration(
        lambda settings, usage: Unavailable(), synthetic=True
    ))
    with pytest.raises(ResearchError, match="research_configuration_invalid"):
        research_service(settings, fixture_service.repository, "local", _application_context())


@pytest.mark.anyio
async def test_rights_denied_before_dispatch_and_derived_reuse_revoked():
    service, request = build_fixture(load_fixtures()[0])
    result, _ = await complete(service, request)
    observation = result.observations[0]
    snapshot = ContextSourceSnapshot(
        provider_id="external_research", source_id=str(result.id), source_version="snippet-observation-v2",
        item_id=str(result.evidence[0].id),
        owner_id="local", application_id="personal_ai",
        content_fingerprint=result.evidence[0].content_fingerprint,
        source_classes=("external_research",),
        permission_dependencies=observation_dependencies((observation,)),
        expires_at=result.expires_at,
    )
    assert source_snapshots_current((snapshot,), service.context.permission_revalidator, now=NOW)
    service.adapter.authorize_snippets = lambda: "revoked-version"
    assert not source_snapshots_current((snapshot,), service.context.permission_revalidator, now=NOW)
    with pytest.raises(ResearchError, match="research_source_rights_revoked"):
        await service.detail(result.id)

    service, request = build_fixture(load_fixtures()[0])

    def denied():
        raise SearchError("research_configuration_invalid")

    service.adapter.authorize_snippets = denied
    session = await service.create(request)
    with pytest.raises(SearchError):
        await service.prepare_run(session.id)
    assert service.adapter.calls == []
    assert not hasattr(service.adapter, "fetch")


@pytest.mark.anyio
async def test_source_allowlists_intersect_and_exclusions_win():
    fixture = {**load_fixtures()[0], "question": "Synthetic star site:example.org -site:example.net",
               "sources": [
                   {"url": "https://example.org/star", "text": "Synthetic star blue."},
                   {"url": "https://example.net/star", "text": "Synthetic star red."},
                   {"url": "https://sub.example.org/star", "text": "Synthetic star green."},
               ]}
    service, request = build_fixture(fixture)
    request = request.model_copy(update={"allowed_domains": ("sub.example.org",)})
    result, _ = await complete(service, request)
    assert [s.status for s in result.observations] == ["source_denied", "source_denied", "accepted"]
    assert result.observations[0].canonical_url == "https://example.invalid/rejected"
    assert result.observations[0].passage is None and result.observations[0].title is None
    assert result.query_plan.allowed_domains == request.allowed_domains
    assert len(result.citations) == 1 and result.citations[0].url.startswith("https://sub.example.org")


@pytest.mark.anyio
async def test_versions_conflicts_and_extractive_exact_support():
    fixture = {**load_fixtures()[0], "sources": [
        {"url": "https://example.org/star", "text": "Synthetic star is not blue.",
         "published_at": "2026-10-01T12:00:00Z"},
        {"url": "https://example.net/star", "text": "Synthetic star is not blue.",
         "published_at": "2026-10-01T12:00:00Z"},
        {"url": "https://example.org/star", "text": "Synthetic star is not blue.",
         "published_at": "2026-10-02T00:00:00Z"},
        {"url": "https://example.org/star", "text": "Synthetic star is blue.",
         "published_at": "2026-10-02T00:00:00Z"},
    ]}
    service, request = build_fixture(fixture)
    result, _ = await complete(service, request)
    assert len(result.evidence) == 3 and len(result.citations) == 4
    derived = result.selection.derived
    assert derived.compression_calls == 0 and derived.conflict_status == "unresolved_all_eligible_required"
    assert len(derived.support) == 3 and derived.omitted_ids == ()
    assert derived.input_bytes == derived.output_bytes
    assert result.observations[0].query_id == result.queries[0].id
    assert result.observations[0].source_origin == "synthetic"
    assert result.observations[0].attempt_id == result.attempts[-1].id
    assert result.observations[0].passage == result.evidence[0].passage
    assert result.observations[0].freshness_basis == "publication"
    support = derived.support[0].model_copy(update={"end": 1})
    forged = derived.model_copy(update={"support": (support, *derived.support[1:])})
    with pytest.raises(ValueError, match="derived exact support"):
        evolve(result, selection=result.selection.model_copy(update={"derived": forged}))


@pytest.mark.anyio
@pytest.mark.parametrize("failure", ["quota", "timeout"])
async def test_partial_plan_keeps_completed_observations_without_answer_or_replay(failure):
    service, request = build_fixture(load_fixtures()[0], research_max_queries=2,
                                     research_timeout_seconds=.03)

    class Planner:
        strategy_id = "bounded-qualifier"
        strategy_version = 1
        def plan(self, question, max_queries):
            return (question, question + " specification")

    service.planner = Planner()
    original = service.adapter.search
    count = 0

    async def search(query, limit):
        nonlocal count
        count += 1
        if count == 2:
            if failure == "quota":
                raise SearchError("search_quota")
            await asyncio.sleep(1)
        return await original(query, limit)

    service.adapter.search = search
    result, _ = await complete(service, request)
    assert result.state == "failed" and result.answer is None
    assert result.queries[0].state == "completed" and len(result.observations) == 1
    assert result.observations[0].query_id == result.queries[0].id
    assert len(result.attempts) <= 8 and count == 2
    await service.prepare_run(result.id)
    assert count == 2


@pytest.mark.anyio
async def test_every_expanded_search_uses_p19_reservation_before_http_and_quota_stops():
    http_calls = []
    reserved = []
    settled = []

    class Accounting:
        def begin_invocation(self, invocation):
            pass

        def reserve_attempt(self, invocation, attempt, *, max_attempts):
            if len(reserved) == 1:
                raise UsageAdmissionDenied("provider_quota_exhausted")
            reserved.append((invocation, attempt))

        def settle_attempt(self, invocation, attempt, result):
            settled.append(result)

        def complete_invocation(self, invocation, *, outcome, completed_at):
            pass

    def transport(request):
        assert len(reserved) > len(http_calls)
        http_calls.append(request.url)
        return httpx.Response(200, json={"web": {"results": [
            {"url": "https://example.org/star", "description": "Synthetic star is blue."}
        ]}})

    adapter = brave_adapter(transport)
    adapter.settings.research_min_request_interval_seconds = 0
    adapter.usage_accounting = Accounting()
    service, request = build_fixture(load_fixtures()[0], research_max_queries=2)
    service.adapter = adapter
    # Use canonical rights revalidator bound to the real HTTP adapter.
    from personal_ai.search.authority import ResearchSourceRightsRevalidator
    service.context.permission_revalidator = ResearchSourceRightsRevalidator(adapter.settings, adapter=adapter)

    class Planner:
        strategy_id = "bounded-qualifier"
        strategy_version = 1
        def plan(self, question, max_queries):
            return (question, question + " specification")

    service.planner = Planner()
    result, _ = await complete(service, request)
    assert result.state == "failed" and result.failure_code == "search_quota"
    assert len(http_calls) == len(reserved) == len(settled) == 1
    assert reserved[0][0].task_id == "web_research_search"
    assert reserved[0][0].endpoint.provider_id == "brave_search"
    assert result.attempts[0].usage_invocation_id == reserved[0][0].invocation_id
    assert result.attempts[0].usage_attempt_id == reserved[0][1].attempt_id
    assert len(result.observations) == 1


@pytest.mark.anyio
async def test_paired_evaluation_nonpromotion_and_rollback():
    cases, frozen, _ = load_configuration()
    assert len(cases) == len(frozen["rows"]) == 18
    control, _ = await measure(cases[0], VARIANTS[0])
    compact, session = await measure(cases[0], VARIANTS[1])
    rollback, _ = await measure(cases[0], VARIANTS[0])
    assert compact.packed_tokens < control.packed_tokens == rollback.packed_tokens
    assert session.selection.derived.compression_calls == 0
    assert control.calls == compact.calls == rollback.calls == 1
    result = await run()
    assert len(result["rows"]) == 54 and result["promotion"] == "not_promoted"
    assert all("synthetic_only" in row["promotion_reasons"] for row in result["rows"])
    assert result["live_answer_quality"] == "unmeasured"


@pytest.mark.anyio
async def test_experiment_gate_defaults_to_literal_even_with_configured_variant():
    service, request = build_fixture(load_fixtures()[0], research_packing_strategy=VARIANTS[1])
    result, _ = await complete(service, request)
    assert result.selection.packing_strategy == VARIANTS[0]
    service.settings.research_retrieval_experiments_enabled = True
    result, _ = await complete(service, request.model_copy(update={"idempotency_key": uuid4()}))
    assert result.selection.packing_strategy == VARIANTS[1]
    service.clock = lambda: NOW + timedelta(days=30)
    assert (await service.detail(result.id)).state == "expired"


@pytest.mark.anyio
async def test_export_artifact_retains_rights_dependency_and_revocation_blocks_cached_reuse():
    from personal_ai.artifacts.contracts import ArtifactUnavailable
    from personal_ai.artifacts.local import (
        InMemoryArtifactMetadataRepository,
        InMemoryArtifactStore,
    )
    from personal_ai.artifacts.service import ArtifactService
    from personal_ai.auth.scope import ApplicationScope
    from personal_ai.search.authority import (
        ResearchSourceRightsRevalidator,
        research_export_dependencies,
    )

    service, request = build_fixture(load_fixtures()[0])
    result, _ = await complete(service, request)
    exported = {"collections": {"research_sessions": [
        {"document_id": str(result.id), "data": result.model_dump(mode="json")}
    ]}}
    authority = ResearchSourceRightsRevalidator(service.settings)
    artifacts = ArtifactService(
        InMemoryArtifactMetadataRepository(clock=lambda: NOW), InMemoryArtifactStore(),
        clock=lambda: NOW, permission_revalidator=authority,
    )
    ref = artifacts.freeze_export(exported, owner_id="local", scope=ApplicationScope(),
                                  identity="test-export", max_records=100, max_bytes=100000)
    assert ref.permission_dependencies == research_export_dependencies(exported)
    assert artifacts.read(ref.artifact_id, owner_id="local", scope=ApplicationScope())
    service.settings.research_enabled = False
    with pytest.raises(ArtifactUnavailable):
        artifacts.read(ref.artifact_id, owner_id="local", scope=ApplicationScope())
    with pytest.raises(ArtifactUnavailable):
        artifacts.freeze_export(exported, owner_id="local", scope=ApplicationScope(),
                                identity="test-export", max_records=100, max_bytes=100000)


@pytest.mark.anyio
async def test_compact_and_bulky_experiment_tiers_and_optional_artifact_failure():
    from personal_ai.artifacts.local import (
        InMemoryArtifactMetadataRepository,
        InMemoryArtifactStore,
    )
    from personal_ai.artifacts.service import ArtifactService

    class Repository:
        def __init__(self):
            self.rows = []

        def save(self, summary):
            self.rows.append(summary)

    repository = Repository()
    artifacts = ArtifactService(InMemoryArtifactMetadataRepository(), InMemoryArtifactStore())
    report = await run(repository=repository, artifacts=artifacts)
    assert report["artifact_status"] == "ready" and len(repository.rows) == 54
    assert all(r.artifact_id is not None for r in repository.rows)
    assert sum(r.candidate.retained_artifact_bytes for r in repository.rows) == report["retained_artifact_bytes"]
    body = artifacts.read(repository.rows[0].artifact_id, owner_id="local",
                          scope=ApplicationScope())
    assert "Synthetic star" not in str(body)
    assert "passage" not in str(body) and "api_key" not in str(body)
    assert all("passage" not in r.model_dump() for r in repository.rows)
    artifacts.writes_enabled = False
    repository = Repository()
    report = await run(repository=repository, artifacts=artifacts)
    assert report["artifact_status"] == "not_retained"
    assert all(r.artifact_id is None for r in repository.rows)


@pytest.mark.anyio
async def test_mandatory_publication_freshness_excludes_unknown_old_and_future_before_ranking():
    service, request = build_fixture({**load_fixtures()[0], "sources": [
        {"url": "https://example.org/unknown", "text": "Synthetic star blue."},
        {"url": "https://example.org/old", "text": "Synthetic star blue.",
         "published_at": "2026-10-01T10:00:00Z"},
        {"url": "https://example.org/future", "text": "Synthetic star blue.",
         "published_at": "2026-10-03T10:00:00Z"},
        {"url": "https://example.org/fresh", "text": "Synthetic star blue.",
         "published_at": "2026-10-01T23:00:00Z"},
    ]})
    request = request.model_copy(update={"published_after": NOW-timedelta(hours=2)})
    result, _ = await complete(service, request)
    assert [s.status for s in result.observations] == ["freshness_unverified", "stale", "stale", "accepted"]
    assert len(result.evidence) == 1 and result.citations[0].url.endswith("/fresh")
    assert result.query_plan.published_after == request.published_after


@pytest.mark.anyio
async def test_ranker_reproducibility_and_malformed_output_conflict_safe_fallback():
    class Reverse:
        strategy_id = "reverse-v1"

        def rank(self, question, evidence):
            return tuple(reversed(evidence))

    orders = []
    for _ in range(2):
        service, request = build_fixture(load_fixtures()[1])
        service.reranker = Reverse()
        result, _ = await complete(service, request)
        evidence = {e.id: e for e in result.evidence}
        orders.append(tuple(evidence[i].passage for i in result.selection.evidence_ids))
        assert result.selection.ranking_strategy == "reverse-v1"
        assert not result.selection.ranking_fallback and len(result.citations) == 2
    assert orders[0] == orders[1]

    class Malformed(Reverse):
        def rank(self, question, evidence):
            return (evidence[0],)*len(evidence)

    service, request = build_fixture(load_fixtures()[1])
    service.reranker = Malformed()
    result, _ = await complete(service, request)
    assert result.selection.ranking_fallback and result.selection.ranking_strategy == "literal-diversity-v1"
    assert len(result.citations) == 2 and result.selection.derived.omitted_ids == ()


@pytest.mark.anyio
async def test_same_passage_different_native_revision_is_never_collapsed():
    service, request = build_fixture({**load_fixtures()[0], "sources": [
        {"url": "https://example.org/star", "text": "Synthetic star is blue.", "source_revision": "1"},
        {"url": "https://example.org/star", "text": "Synthetic star is blue.", "source_revision": "2"},
    ]})
    result, _ = await complete(service, request)
    assert len(result.evidence) == 2
    assert [s.source_revision for s in result.observations] == ["1", "2"]


@pytest.mark.anyio
async def test_oversized_adapter_result_fails_before_extraction_or_model_work():
    service, request = build_fixture(load_fixtures()[0], research_max_sources=1)

    async def oversized(query, limit):
        return service.adapter.results * 2

    service.adapter.search = oversized
    result, _ = await complete(service, request)
    assert result.failure_code == "search_invalid_response" and not result.evidence
    assert not result.citations and result.answer is None

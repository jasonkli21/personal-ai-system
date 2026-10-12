import asyncio
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest

from personal_ai.search.authority import ResearchSourceRightsRevalidator, observation_dependencies
from personal_ai.search.contracts import FakeSearchAdapter
from personal_ai.search.planning import SearchOperation
from personal_ai.search.providers import brave
from personal_ai.search.providers.brave import BraveSearchAdapter, SearchError
from personal_ai.settings import Settings


@pytest.fixture
def anyio_backend():
    return "asyncio"


def adapter(response):
    settings = Settings(
        _env_file=None,
        ai_provider="gemini",
        ai_model="test",
        research_enabled=True,
        research_search_adapter="brave",
        research_provider_storage_approved=True,
        research_api_key="synthetic-secret",
        research_brave_prepaid_verified=True,
        research_brave_auto_reload_disabled=True,
        research_brave_no_paid_balance_verified=True,
        research_brave_source_rights_verified=True,
        research_brave_account_scope_id="synthetic-brave-account",
        research_brave_preflight_reference="operator-preflight:synthetic-brave",
        research_brave_rights_epoch="1",
    )
    brave._NEXT_REQUEST = 0

    def transport(request):
        assert request.url.host == "api.search.brave.com"
        assert request.headers["X-Subscription-Token"] == "synthetic-secret"
        return response(request) if callable(response) else response

    return BraveSearchAdapter(settings, transport=httpx.MockTransport(transport))


def operation(query="Synthetic query", **changes):
    fields = {
        "operation_id": "a" * 64,
        "query_id": uuid4(),
        "query": query,
        "original_question": query,
        "strategy_id": "literal-snippet",
        "strategy_version": 1,
        "strategy_reason": "baseline",
        "plan_identity": "b" * 64,
        "max_results": 1,
        "deadline_at": datetime.now(UTC) + timedelta(seconds=5),
    }
    fields.update(changes)
    return SearchOperation(**fields)


@pytest.mark.anyio
async def test_snippet_response_and_no_source_fetch():
    value = adapter(
        httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "url": "https://example.org/test",
                            "title": "Title",
                            "description": "Snippet",
                        },
                    ]
                }
            },
        )
    )
    dispatch = await value.search(operation())
    assert dispatch.results[0].text == "Snippet" and dispatch.results[0].published_at is None
    assert "synthetic-secret" not in repr(value.settings)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "response,code",
    [
        (httpx.Response(429), "search_quota"),
        (httpx.Response(503), "search_unavailable"),
        (httpx.Response(302, headers={"location": "http://localhost/"}), "search_rejected"),
        (httpx.Response(200, json={"web": {"results": "wrong"}}), "search_invalid_response"),
        (
            httpx.Response(200, json={"web": {"results": [{"url": None}]}}),
            "search_invalid_response",
        ),
        (
            httpx.Response(200, content="x", headers={"content-type": "text/html"}),
            "search_invalid_response",
        ),
        (
            httpx.Response(
                200, content=b"x" * 131073, headers={"content-type": "application/json"}
            ),
            "search_response_oversized",
        ),
    ],
)
async def test_provider_failure_mapping(response, code):
    with pytest.raises(SearchError, match=code):
        await adapter(response).search(operation())


@pytest.mark.anyio
async def test_timeout_empty_and_malformed_json():
    def timeout(request):
        raise httpx.ReadTimeout("secret detail")

    with pytest.raises(SearchError, match="search_timeout"):
        await adapter(timeout).search(operation())
    assert (await adapter(httpx.Response(200, json={})).search(operation())).results == ()
    with pytest.raises(SearchError, match="search_invalid_response"):
        await adapter(
            httpx.Response(200, content="{", headers={"content-type": "application/json"})
        ).search(operation())


@pytest.mark.anyio
async def test_rate_wait_is_cancellable_and_no_request_is_sent():
    value = adapter(httpx.Response(200, json={}))
    brave._NEXT_REQUEST = brave.monotonic() + 10
    with pytest.raises(TimeoutError):
        async with asyncio.timeout(0.01):
            await value.search(operation())
    brave._NEXT_REQUEST = 0


@pytest.mark.anyio
async def test_physical_query_enforces_domain_intersection_and_exclusions():
    sent = []

    def transport(request):
        sent.append(request.url.params["q"])
        return httpx.Response(200, json={"web": {"results": []}})

    value = adapter(transport)
    value.settings.research_min_request_interval_seconds = 0
    op = operation(
        "Synthetic Atlas site:example.org -site:blocked.example.org",
        original_question="Synthetic Atlas site:example.org -site:blocked.example.org",
        allowed_domains=("sub.example.org",),
        literal_allowed_domains=("example.org",),
        excluded_domains=("blocked.example.org",),
    )
    await value.search(op)
    assert sent == [
        (
            "Synthetic Atlas site:example.org -site:blocked.example.org site:sub.example.org "
            "-site:blocked.example.org"
        )
    ]


@pytest.mark.anyio
async def test_exact_publication_bound_fails_closed_before_http():
    calls = []
    value = adapter(lambda request: (calls.append(request), httpx.Response(200, json={}))[1])
    with pytest.raises(SearchError, match="search_constraint_unsupported"):
        await value.search(operation(published_after=datetime.now(UTC)))
    assert calls == []


def test_source_rights_authority_epoch_survives_adapter_switch_and_feature_disable():
    value = adapter(httpx.Response(200, json={}))
    rights = value.authorize_snippets()
    observation = SimpleNamespace(
        observation_version="snippet-observation-v2",
        provider="brave",
        rights_authority_id=rights.authority_id,
        rights_epoch=rights.epoch,
        rights_reference=rights.reference,
    )
    dependency = observation_dependencies((observation,))[0]
    assert "synthetic-brave-account" not in dependency.permission_id
    revalidator = ResearchSourceRightsRevalidator(value.settings, adapter=FakeSearchAdapter())
    assert revalidator.is_current(dependency)
    value.settings.research_search_adapter = "fake"
    value.settings.research_enabled = False
    assert revalidator.is_current(dependency)
    value.settings.research_brave_rights_epoch = "2"
    assert not revalidator.is_current(dependency)

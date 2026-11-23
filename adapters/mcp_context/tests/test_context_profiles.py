import asyncio
import json
from dataclasses import replace
from datetime import timedelta
from urllib.parse import urlsplit

import pytest
from app_context_support.fences import side_effect_fence  # noqa: F401
from app_context_support.fixtures import TRAVEL
from mcp import Client
from mcp.client.streamable_http import streamable_http_client
from personal_ai.auth.scope import ApplicationScope
from personal_ai_mcp_context import server

from context_host import ALT_CLIENT, CITATION_RESOURCE, FITNESS_CLIENT, ISSUER, RESOURCE
from context_workspace import TRAVEL_INSTALLATION, WorkspaceLessHost
from test_context_server import IDENTITY, assert_denied, assert_schema, handle, http, reads, rpc, tool


pytestmark = pytest.mark.usefixtures("side_effect_fence")
_COOKIE = "fixture-session"


@pytest.fixture
def workspace_less():
    return WorkspaceLessHost()


@pytest.fixture
def publications(monkeypatch):
    published = []
    original = server._State.publish

    def observe(state, pending, citations):
        original(state, pending, citations)
        published.append((len(pending), len(citations)))

    monkeypatch.setattr(server._State, "publish", observe)
    return published


def test_workspace_less_travel_uses_exact_record_grants_and_fitness_keeps_workspace(workspace_less):
    host = workspace_less

    async def run():
        async with http(host, host.token()) as client:
            a = (await tool(client, "search", {"query": "shuttle"}))["structuredContent"]["results"]
            assert [row["title"] for row in a] == ["Demo shuttle A"]
            denied = await tool(
                client, "fetch", {"id": a[0]["id"]}, Authorization=f"Bearer {host.token(client=ALT_CLIENT)}",
            )
            assert_denied(denied)
            record = (await tool(client, "fetch", {"id": a[0]["id"]}))["structuredContent"]
            assert json.loads(record["text"]) == {"title": "Demo shuttle A"}
            for term in ("Unshared shuttle", "Demo shuttle B", "no record"):
                result = await tool(client, "search", {"query": term})
                assert result["structuredContent"] == {"results": []}
                assert json.loads(result["content"][0]["text"]) == {"results": []}

            alternate = {"Authorization": f"Bearer {host.token(client=ALT_CLIENT)}"}
            second = await tool(client, "search", {"query": "Unshared"}, **alternate)
            selector = second["structuredContent"]["results"][0]["id"]
            result = await tool(client, "fetch", {"id": selector}, **alternate)
            assert json.loads(result["structuredContent"]["text"]) == {
                "title": "Unshared shuttle", "platform": "Gray",
            }
            other = {"Authorization": f"Bearer {host.token('b')}"}
            search_b = await tool(client, "search", {"query": "Demo"}, **other)
            selector = search_b["structuredContent"]["results"][0]["id"]
            assert_denied(await tool(client, "fetch", {"id": a[0]["id"]}, **other))
            result = await tool(client, "fetch", {"id": selector}, **other)
            assert json.loads(result["structuredContent"]["text"]) == {
                "title": "Demo shuttle B", "platform": "Green",
            }
        async with http(host, host.token(client=FITNESS_CLIENT)) as client:
            selector = await handle(client, "Fixture")
            result = await tool(client, "fetch", {"id": selector})
            assert json.loads(result["structuredContent"]["text"]) == {"title": "Fixture session A"}

    asyncio.run(run())
    assert host.travel.records["tenant-a", "owner-a"]["r01"].ref == "r01"
    assert host.travel.records["tenant-b", "owner-b"]["r01"].ref == "r01"
    assert host.travel.lookup_paths == [("tenant-a", "owner-a")] * 7 + [("tenant-b", "owner-b")] * 2
    assert host.travel.counts == {"entered": 9, "exited": 9, "active": 0}
    assert reads(host) == 2


@pytest.mark.parametrize("mode", [
    "unregistered", "different-installation", "implicit-null", "blank", "trip-as-workspace",
    "domain-owner", "ambiguous-owner", "foreign-tenant", "fitness-null", "health",
    "application-plan", "preview", "federation",
])
def test_wrong_workspace_policy_or_account_denies_before_domain_read(workspace_less, mode, monkeypatch):
    host = workspace_less
    options = {}
    token = host.token()
    connection, = host.connections[IDENTITY]
    grant = host.pas.authority.grants[connection.grant_id]
    if mode == "unregistered":
        options["workspace_less_sources"] = frozenset()
    elif mode == "different-installation":
        options["workspace_less_sources"] = frozenset({
            replace(TRAVEL_INSTALLATION, installation_id="different-installation"),
        })
    elif mode in {"implicit-null", "blank", "trip-as-workspace"}:
        original = host.resolve
        scope = {
            "implicit-null": ApplicationScope(application_id=TRAVEL),
            "blank": ApplicationScope(application_id=TRAVEL).model_copy(update={"workspace_id": " "}),
            "trip-as-workspace": ApplicationScope(application_id=TRAVEL, workspace_id="trip-a"),
        }[mode]

        async def invalid_scope(identity, operation):
            return replace(await original(identity, operation), scope=scope)

        monkeypatch.setattr(host, "resolve", invalid_scope)
    elif mode == "domain-owner":
        host.travel.owner_acl.clear()
    elif mode == "ambiguous-owner":
        host.accounts[ISSUER, "subject-a"] = tuple(host.accounts.values())
    elif mode == "foreign-tenant":
        host.connections[IDENTITY] = (replace(connection, tenant="tenant-b"),)
    elif mode == "fitness-null":
        token = host.token(client=FITNESS_CLIENT)
        identity = replace(IDENTITY, client_id=FITNESS_CLIENT)
        fitness, = host.connections[identity]
        host.connections[identity] = (replace(fitness, workspace=None),)
    elif mode == "health":
        host.connections[IDENTITY] = (replace(connection, application="health-demo"),)
    else:
        host.pas.authority.grants[grant.id] = replace(grant, recipient=mode)

    async def run():
        async with http(host, token, app=host.app(**options)) as client:
            assert_denied(await tool(
                client, "search", {"query": "Demo"},
                **{"X-Authenticated-User": "subject-a", "X-Forwarded-Client-Cert": "fixture"},
            ))

    asyncio.run(run())
    assert host.travel.lookup_paths == [] and not host.travel.counts
    assert reads(host) == 0
    assert all(not budget.calls for budget in host.budgets)


@pytest.mark.parametrize("operation", ["search", "fetch"])
@pytest.mark.parametrize("change", ["acl", "owner", "revision", "watermark", "expiry"])
def test_workspace_less_authority_changes_after_one_read_withhold_results_and_publication(
    workspace_less, publications, operation, change,
):
    host = workspace_less
    key = ("tenant-a", "owner-a")

    async def run():
        async with http(host, host.token()) as client:
            arguments = {"query": "Demo"} if operation == "search" else {"id": await handle(client)}
            reached = asyncio.Event()
            resume = asyncio.Event()

            async def barrier():
                reached.set()
                await resume.wait()

            host.before_release = barrier
            request = asyncio.create_task(tool(client, operation, arguments))
            await asyncio.wait_for(reached.wait(), 1)
            if change == "acl":
                host.travel.record_acl.clear()
            elif change == "owner":
                host.travel.owner_acl.clear()
            elif change == "revision":
                host.travel.records[key]["r01"] = replace(host.travel.records[key]["r01"], revision="next")
            elif change == "watermark":
                host.travel.watermarks[key] = "next"
            else:
                host.pas.now += timedelta(minutes=6)
            resume.set()
            assert_denied(await request)

    asyncio.run(run())
    assert host.travel.lookup_paths == [key] * (1 if operation == "search" else 2)
    assert publications == ([] if operation == "search" else [(1, 0)])
    assert dict(host.budgets[-1].calls) == {operation: 1}


def test_process_local_selectors_miss_in_second_running_app(workspace_less):
    host = workspace_less

    async def run():
        async with http(host, host.token()) as first, http(host, host.token()) as second:
            selector = await handle(first)
            assert_denied(await tool(second, "fetch", {"id": selector}))
            assert len(host.travel.lookup_paths) == 1
            assert (await tool(first, "fetch", {"id": selector}))["structuredContent"]["id"] == selector

    asyncio.run(run())
    for invalid in (0, 2, True, "1"):
        with pytest.raises(ValueError, match="mcp_unavailable"):
            host.app(process_count=invalid)
    assert len(host.travel.lookup_paths) == 2


async def citable_search(client, query="Demo"):
    result = await tool(client, "search", {"query": query}, resource=CITATION_RESOURCE)
    item, = result["structuredContent"]["results"]
    assert json.loads(result["content"][0]["text"]) == result["structuredContent"]
    return item


def test_citation_profile_uses_exact_audience_and_sdk_shapes(workspace_less, publications):
    host = workspace_less
    with pytest.raises(ValueError, match="mcp_unavailable"):
        host.app(resource=CITATION_RESOURCE)
    with pytest.raises(ValueError, match="mcp_unavailable"):
        host.app(resource=RESOURCE, verify_browser=host.verify_browser)

    async def run():
        app = host.citation_app()
        async with http(host, host.token(), app=app) as wrong:
            response = await rpc(wrong, "tools/list", resource=CITATION_RESOURCE)
            assert response.status_code == 401 and response.content == b""
            assert 'oauth-protected-resource/mcp-citations/v1"' in response.headers["www-authenticate"]
            assert (await rpc(wrong, "tools/list")).status_code == 404
            metadata = await wrong.get(
                "https://context.example.invalid/.well-known/oauth-protected-resource/mcp-citations/v1",
            )
            assert metadata.json()["resource"] == CITATION_RESOURCE
        async with (
            http(host, host.token(aud=CITATION_RESOURCE), app=app) as client,
            Client(streamable_http_client(
                CITATION_RESOURCE, http_client=client, terminate_on_close=False,
            ), cache=None) as mcp,
        ):
            tools = {entry.name: entry for entry in (await mcp.list_tools()).tools}
            assert mcp.protocol_version == server.REVISION
            item, = assert_schema(tools["search"], await mcp.session.call_tool(
                "search", {"query": "Demo"},
            ))["results"]
            assert set(item) == {"id", "title", "url"}
            second = await citable_search(client)
            assert second["url"] == item["url"] and second["id"] != item["id"]
            fetch = await mcp.session.call_tool("fetch", {"id": item["id"]})
            record = assert_schema(tools["fetch"], fetch)
            assert record == {**item, "text": '{"title": "Demo shuttle A"}'}
            url = urlsplit(item["url"])
            assert (url.scheme, url.netloc, url.query, url.fragment) == ("https", "context.example.invalid", "", "")
            assert url.path.startswith(server.CITATION_VIEW_PATH)
            assert server._LOCATOR.fullmatch(url.path.removeprefix(server.CITATION_VIEW_PATH))
            assert item["id"] not in item["url"] and "r01" not in item["url"]
            serialized = fetch.model_dump(mode="json", by_alias=True, exclude_none=True)
            assert len(json.dumps(serialized, separators=(",", ":")).encode()) <= server.MAX_BYTES

    asyncio.run(run())
    assert publications == [(1, 1), (1, 1), (0, 0)]
    assert len(host.travel.lookup_paths) == 3


def test_browser_reauthenticates_and_checks_current_citation_grant(workspace_less, caplog):
    host = workspace_less

    async def run():
        token = host.token(aud=CITATION_RESOURCE)
        good = host.browser_session(IDENTITY)
        wrong = host.browser_session(replace(IDENTITY, subject="subject-b"))
        crossed = host.browser_session(IDENTITY, tenant="tenant-b")
        actor = host.browser_session(IDENTITY, acting_user_id="wrong-actor")
        async with http(host, token, app=host.citation_app()) as client:
            item = await citable_search(client)
            url = item["url"]
            assert len(host.travel.lookup_paths) == 1
            for test_url, session in (
                (url, None), (url, wrong), (url, crossed), (url, actor), (url + "?token=browser-canary", good),
                (url.replace("/v1/", "/v1/%2f"), good),
                (url.replace("/citations/", "/foreign/"), good),
                (url.rsplit("/", 1)[0] + "/" + "0" * 64, good),
                (url.replace("context.example.invalid", "foreign.invalid"), good),
            ):
                response = await client.get(
                    test_url, headers={"Cookie": f"{_COOKIE}={session}"} if session else {}, follow_redirects=False,
                )
                assert response.status_code in (404, 421)
                assert response.content == b"" and "location" not in response.headers
            assert len(host.travel.lookup_paths) == 1
            cookie = {"Cookie": f"{_COOKIE}={good}"}
            opened = await client.get(url, headers=cookie)
            assert opened.status_code == 200
            assert opened.json() == {"title": "Demo shuttle A", "text": '{"title": "Demo shuttle A"}'}
            assert opened.headers["cache-control"] == "private, no-store"
            assert opened.headers["referrer-policy"] == "no-referrer"
            assert opened.headers["content-security-policy"] == "default-src 'none'; frame-ancestors 'none'"
            assert len(host.travel.lookup_paths) == 2
            grant_id = host.connections[IDENTITY][0].grant_id
            del host.pas.authority.grants[grant_id]
            revoked = await client.get(url, headers=cookie)
            assert revoked.status_code == 404 and revoked.content == b""
            assert revoked.headers["cache-control"] == "private, no-store"
            assert len(host.travel.lookup_paths) == 2

    asyncio.run(run())
    assert "browser-canary" not in caplog.text and "Demo shuttle A" not in caplog.text


@pytest.mark.parametrize("change", ["record", "acl", "grant", "session", "expired"])
def test_browser_change_during_open_or_expired_locator_denies(
    workspace_less, change,
):
    host = workspace_less

    async def run():
        session = host.browser_session(IDENTITY)
        async with http(host, host.token(aud=CITATION_RESOURCE), app=host.citation_app()) as client:
            item = await citable_search(client)
            headers = {"Cookie": f"{_COOKIE}={session}"}
            if change == "expired":
                host.pas.now += timedelta(minutes=5)
                denial = await client.get(item["url"], headers=headers)
                assert len(host.travel.lookup_paths) == 1
            else:
                entered, release = asyncio.Event(), asyncio.Event()

                async def waiting():
                    entered.set()
                    await release.wait()

                host.before_release = waiting
                request = asyncio.create_task(client.get(item["url"], headers=headers))
                await asyncio.wait_for(entered.wait(), 1)
                assert len(host.travel.lookup_paths) == 2
                if change == "record":
                    records = host.travel.records["tenant-a", "owner-a"]
                    records["r01"] = replace(records["r01"], revision="next")
                elif change == "acl":
                    host.travel.record_acl.clear()
                elif change == "grant":
                    del host.pas.authority.grants[host.connections[IDENTITY][0].grant_id]
                else:
                    del host.browser_sessions[session]
                release.set()
                denial = await request
            assert denial.status_code == 404 and denial.content == b""
            assert "location" not in denial.headers

    asyncio.run(run())


def test_citation_output_byte_overflow_releases_no_handle_or_browser_locator(workspace_less, publications):
    host = workspace_less

    async def run():
        key = ("tenant-a", "owner-a")
        records = host.travel.records[key]
        records["r01"] = replace(records["r01"], values=(("title", "Demo " + "☀" * 680),))
        records["r03"] = replace(records["r01"], ref="r03")
        host.travel.record_acl[key, host.connections[IDENTITY][0].grant_id, "r03"] = frozenset({"title"})
        async with http(host, host.token(aud=CITATION_RESOURCE), app=host.citation_app()) as client:
            assert_denied(await tool(client, "search", {"query": "Demo"}, resource=CITATION_RESOURCE))

    asyncio.run(run())
    assert publications == []
    assert len(host.travel.lookup_paths) == 1

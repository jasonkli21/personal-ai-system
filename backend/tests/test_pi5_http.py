"""Signed unrelated consumer through real middleware; copied into installed proof."""

import json
import os
import subprocess
import sys
from pathlib import Path
from uuid import uuid4

import pytest

from personal_ai.auth.scope import RequestScope
from personal_ai.retrieval.installation import LexicalIndex
from personal_ai.settings import get_settings

from .test_pi2_http import http_platform as signed_http_fixture
from .test_pi5_retrieval import access, document, install

http_platform = signed_http_fixture
pytestmark = pytest.mark.loopback_http


def configure(h, tmp_path):
    owner = h.client.start("Retrieve", uuid4())["owner_id"]
    scope = RequestScope(
        owner_id=owner,
        acting_user_id="https://accounts.google.com|synthetic-owner",
        application_id="reading_logbook",
        workspace_id="shelf",
        request_id="test",
    )
    path = tmp_path / "installed.json"
    install(
        path,
        access=[access(scope)],
        external_query_access=[access(scope)],
        documents=[document(access=[access(scope)])],
    )
    settings = h.app.dependency_overrides[get_settings]().model_copy(
        update={
            "retrieval_enabled": True,
            "retrieval_external_enabled": True,
            "retrieval_installation_file": str(path),
            "retrieval_attempt_journal_file": str(tmp_path / "attempts.sqlite3"),
        }
    )
    h.app.dependency_overrides[get_settings] = lambda: settings
    return path, scope, settings


def test_pi5_signed_consumer_local_external_and_real_tool(http_platform, tmp_path):
    h = http_platform
    path, _, _ = configure(h, tmp_path)
    result = h.client.retrieve("Atlas", uuid4())
    assert result["state"] == "complete" and result["items"][0]["origin"] == "local"
    assert result["items"][0]["url"] is None
    exact_quote = json.loads(path.read_text())["documents"][0]["text"]
    assert result["items"][0]["quote"] == exact_quote
    tool = h.client.retrieve("Atlas", uuid4(), tool=True)
    assert tool["schema_version"] == "read-only-tool-v1"
    assert tool["retrieval"]["items"][0]["quote"] == exact_quote
    # Existing factory's synthetic adapter exercises the externally selected bridge,
    # not live Brave. Its origin MUST remain visibly synthetic.
    both = h.client.retrieve("Atlas", uuid4(), sources=("local", "external"))
    assert {item["origin"] for item in both["items"]} == {"local", "synthetic"}
    assert not h.llm.requests and not h.messages._messages
    response = h.raw.post(
        "/v1/retrieval/query",
        headers=h.headers,
        json={"query": "Atlas", "idempotency_key": str(uuid4())},
    )
    assert (
        response.headers["cache-control"] == "no-store"
        and len(response.headers["x-request-id"]) <= 100
    )


@pytest.mark.parametrize("change", ["owner", "actor", "app", "workspace", "aud", "azp", "header"])
def test_pi5_forged_and_foreign_probing(http_platform, tmp_path, change):
    h = http_platform
    configure(h, tmp_path)
    headers = dict(h.headers)
    if change == "owner":
        headers["Authorization"] = "Bearer " + h.token(sub="synthetic-owner-b")
    elif change == "actor":
        headers["X-Acting-User-ID"] = "forged"
    elif change == "header":
        headers["X-Owner-ID"] = "forged"
    elif change == "app":
        headers["X-Application-ID"] = "personal_ai"
    elif change == "workspace":
        headers["X-Workspace-ID"] = "foreign"
    else:
        headers["Authorization"] = "Bearer " + h.token(**{change: "forged"})
    response = h.raw.post(
        "/v1/retrieval/query",
        headers=headers,
        json={"query": "Atlas", "idempotency_key": str(uuid4())},
    )
    assert "Atlas is a book" not in response.text and "atlas" not in response.text
    if change == "owner":
        assert response.status_code == 200 and not response.json()["items"]
    else:
        assert response.status_code in {400, 401, 403}
    assert not h.llm.requests


@pytest.mark.parametrize("change", ["rights", "client", "workspace", "tool", "flag"])
def test_pi5_racing_output_denies_source_and_current_client(
    http_platform, tmp_path, monkeypatch, change
):
    h = http_platform
    path, _, settings = configure(h, tmp_path)
    original = LexicalIndex.search

    def race(index, *args):
        items = original(index, *args)
        if change in {"rights", "tool"}:
            value = json.loads(path.read_text())
            if change == "tool":
                value["tool_enabled"] = False
            else:
                value["documents"][0]["rights_epoch"] = "2"
            path.write_text(json.dumps(value))
        elif change == "client":
            h.write_policy(enabled=False)
        elif change == "workspace":
            h.members.write_text(
                json.dumps({"schema_version": "reading-logbook-membership-v1", "memberships": []})
            )
        else:
            settings.retrieval_enabled = False
        return items

    monkeypatch.setattr(LexicalIndex, "search", race)
    endpoint = "/v1/tools/retrieval.query.v1/invoke" if change == "tool" else "/v1/retrieval/query"
    response = h.raw.post(
        endpoint, headers=h.headers, json={"query": "Atlas", "idempotency_key": str(uuid4())}
    )
    assert "Atlas is a book" not in response.text
    if response.status_code == 200:
        value = response.json().get("retrieval", response.json())
        assert value["items"] == [] and value["state"] == "unavailable"
    assert not h.llm.requests and not h.messages._messages


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "Atlas", "path": "/etc/passwd"},
        {"query": "Atlas", "callable": "os.system"},
        {"query": "Atlas", "operation": "memory.forget"},
        {"query": "Atlas", "read_only": True},
        {"query": "a" * 401},
        {"query": "Atlas", "max_items": 100},
    ],
)
def test_pi5_malformed_tool_never_executes(http_platform, tmp_path, payload):
    h = http_platform
    configure(h, tmp_path)
    response = h.raw.post(
        "/v1/tools/retrieval.query.v1/invoke",
        headers=h.headers,
        json={"idempotency_key": str(uuid4()), **payload},
    )
    assert response.status_code == 422 and response.json()["error"]["code"] == "validation_error"
    assert not h.llm.requests and not h.messages._messages


def test_pi5_disabled_unknown_tools_and_exact_allowlist(http_platform, tmp_path):
    h = http_platform
    path, _, settings = configure(h, tmp_path)
    body = {"query": "Atlas", "idempotency_key": str(uuid4())}
    for path_suffix in ("memory.forget/invoke", "os.system/invoke", "retrieval.query.v2/invoke"):
        assert (
            h.raw.post("/v1/tools/" + path_suffix, headers=h.headers, json=body).status_code == 404
        )
    assert h.raw.get("/v1/retrieval/query", headers=h.headers).status_code == 403
    assert h.raw.post("/v1/research", headers=h.headers, json={}).status_code == 403
    # Application existence without installed capability is insufficient.
    registration = h.app.state.application_registry.registration("reading_logbook")
    assert registration.tools
    value = json.loads(path.read_text())
    value["tool_enabled"] = False
    path.write_text(json.dumps(value))
    denied = h.client.retrieve("Atlas", uuid4(), tool=True)
    assert not denied["retrieval"]["items"]
    settings.retrieval_enabled = False
    response = h.raw.post("/v1/retrieval/query", headers=h.headers, json=body)
    assert response.status_code == 404
    assert not h.llm.requests


def test_pi5_tool_metadata_is_not_execution_authority(http_platform, tmp_path, monkeypatch):
    from personal_ai.retrieval import tools

    h = http_platform
    configure(h, tmp_path)
    monkeypatch.setattr(tools, "EXECUTABLE_TOOLS", {})
    response = h.raw.post(
        "/v1/tools/retrieval.query.v1/invoke",
        headers=h.headers,
        json={"query": "Atlas", "idempotency_key": str(uuid4())},
    )
    assert response.status_code == 404
    assert not h.llm.requests


def test_pi5_installed_client_only_subprocess(http_platform, tmp_path):
    h = http_platform
    configure(h, tmp_path)
    token_file = tmp_path / "token"
    token_file.write_text(h.client.token)
    token_file.chmod(0o600)
    python = os.environ.get("PI2_CLIENT_PYTHON", sys.executable)
    runner = os.environ.get(
        "PI2_CLIENT_RUNNER",
        str(Path(__file__).resolve().parents[1] / "scripts/pi2_client_probe.py"),
    )
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"}
    if not os.environ.get("PI2_CLIENT_PYTHON"):
        import reading_logbook

        env["PYTHONPATH"] = str(Path(reading_logbook.__file__).parents[1])
    result = subprocess.run(
        [
            python,
            runner,
            "--db",
            str(tmp_path / "books.sqlite3"),
            "--url",
            h.client.base_url,
            "--token-file",
            str(token_file),
            "--workspace",
            "shelf",
            "--allow-loopback",
            "retrieve",
            "Atlas",
            "--key",
            str(uuid4()),
            "--tool",
            "--external",
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    value = json.loads(result.stdout.strip().splitlines()[-1])["retrieval"]
    assert {item["origin"] for item in value["items"]} == {"local", "synthetic"}
    assert "PI2_CLIENT_FORBIDDEN_NETWORK_ATTEMPTS=0" in result.stderr
    assert not h.llm.requests


def test_pi5_external_brave_safe_unavailable_no_provider_retry(http_platform, tmp_path):
    h = http_platform
    _, _, settings = configure(h, tmp_path)
    settings.research_search_adapter = "brave"
    key = uuid4()
    result = h.client.retrieve("Atlas", key, sources=("local", "external"))
    assert result["state"] == "partial" and result["reasons"] == ["external_not_admitted"]
    assert h.client.retrieve("Atlas", key, sources=("local", "external")) == result
    assert not h.llm.requests


def test_pi5_independent_http_brave_mock_transport_with_p19_test_port(http_platform, tmp_path):
    """Actual external bridge/Brave serializer. Fake P19 storage and HTTP, not live eligibility."""
    import httpx

    from personal_ai.api.dependencies import get_request_scope
    from personal_ai.api.retrieval import retrieval_service
    from personal_ai.retrieval.service import RetrievalService
    from personal_ai.search.providers import brave
    from personal_ai.search.providers.brave import BraveSearchAdapter
    from personal_ai.search.runtime import SearchAdapterRegistration

    from .test_research_provider import adapter

    h = http_platform
    _, _, settings = configure(h, tmp_path)
    admitted = adapter(httpx.Response(200, json={"web": {"results": []}})).settings
    for name in type(settings).model_fields:
        if name.startswith("research_"):
            setattr(settings, name, getattr(admitted, name))
    reservations, requests = [], []

    class Accounting:
        def begin_invocation(self, invocation):
            assert (
                invocation.application_id == "reading_logbook"
                and invocation.workspace_id == "shelf"
            )
            assert invocation.endpoint.execution_mode == "STRICT_FREE"

        def reserve_attempt(self, invocation, attempt, *, max_attempts):
            reservations.append(attempt.attempt_id)
            return attempt

        def settle_attempt(self, invocation, attempt, result):
            assert result.outcome == "success"

        def complete_invocation(self, *args, **kwargs):
            pass

    def transport(request):
        requests.append(request)
        assert request.url.host == "api.search.brave.com"
        return httpx.Response(
            200,
            json={
                "web": {
                    "results": [
                        {
                            "url": "https://example.org/catalog",
                            "title": "Synthetic remote catalog",
                            "description": "Atlas catalog snippet from hermetic transport.",
                        }
                    ]
                }
            },
        )

    def factory(selected, usage):
        return BraveSearchAdapter(
            selected, transport=httpx.MockTransport(transport), usage_accounting=usage
        )

    registrations = {
        "brave": SearchAdapterRegistration(
            factory, cost_profile_factory=lambda s: BraveSearchAdapter.cost_profile
        )
    }

    def service(request):
        return RetrievalService(
            settings, get_request_scope(request), lambda: Accounting(), registrations=registrations
        )

    # Keep real middleware and all client/workspace scope; only provider IO/storage ports are synthetic.
    from fastapi import Request

    service.__annotations__["request"] = Request
    h.app.dependency_overrides[retrieval_service] = service
    brave._NEXT_REQUEST = 0
    key = uuid4()
    result = h.client.retrieve("Atlas", key, sources=("local", "external"))
    assert result["state"] == "complete"
    assert {item["origin"] for item in result["items"]} == {"local", "external"}
    remote = next(item for item in result["items"] if item["origin"] == "external")
    assert remote["quote"] == "Atlas catalog snippet from hermetic transport."
    assert remote["provider"] == "brave" and remote["revision_basis"] == "observation_hash"
    assert remote["quote_basis"] == "normalized_provider_snippet" and remote[
        "rights_authority_id"
    ].startswith("brave:")
    replay = h.client.retrieve("Atlas", key, sources=("local", "external"))
    assert replay["state"] == "partial" and replay["reasons"] == ["external_already_attempted"]
    assert len(reservations) == len(requests) == 1 and not h.llm.requests


@pytest.mark.parametrize("lane", ["external", "builtin"])
def test_pi5_owner_directory_deactivated_during_retrieval(
    http_platform, tmp_path, monkeypatch, lane
):
    h = http_platform
    path, scope, _ = configure(h, tmp_path)
    headers = h.headers
    if lane == "builtin":
        scope = scope.model_copy(update={"application_id": "personal_ai", "workspace_id": None})
        install(path, access=[access(scope)], documents=[document(access=[access(scope)])])
        headers = {
            "Authorization": "Bearer " + h.token(aud="builtin-web-client", azp="builtin-web-client")
        }
    original = LexicalIndex.search

    def race(index, *args):
        result = original(index, *args)
        h.app.state.principal_directory.deactivate(scope.owner_id)
        return result

    monkeypatch.setattr(LexicalIndex, "search", race)
    response = h.raw.post(
        "/v1/retrieval/query",
        headers=headers,
        json={"query": "Atlas", "idempotency_key": str(uuid4())},
    )
    assert response.status_code == 200 and response.json()["items"] == []
    assert "Atlas is a book" not in response.text and not h.llm.requests


def test_pi5_builtin_body_deadline_uses_retrieval_safe_error(http_platform, tmp_path, monkeypatch):
    import asyncio

    h = http_platform
    configure(h, tmp_path)
    headers = {
        "Authorization": "Bearer " + h.token(aud="builtin-web-client", azp="builtin-web-client")
    }
    original = asyncio.wait_for

    async def timeout_body(awaitable, timeout):
        if timeout is not None and 9 < timeout <= 10:
            awaitable.close()
            raise TimeoutError("synthetic request body deadline")
        return await original(awaitable, timeout)

    monkeypatch.setattr(asyncio, "wait_for", timeout_body)
    response = h.raw.post(
        "/v1/retrieval/query",
        headers=headers,
        json={"query": "Atlas", "idempotency_key": str(uuid4())},
    )
    assert response.status_code == 408
    assert response.json()["error"]["code"] == "request_body_timeout"
    assert not h.llm.requests

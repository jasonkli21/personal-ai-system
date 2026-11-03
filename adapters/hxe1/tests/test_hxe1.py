import asyncio
import sys
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from mcp import Client
from mcp.shared.exceptions import MCPError
from peer import TEXT, peer
from personal_ai.applications.contracts import (
    ApplicationDefinition,
    CapabilityRegistration,
)
from personal_ai.applications.registry import ApplicationRegistry
from personal_ai.auth.application_clients import (
    bind_client_authority,
    reset_client_authority,
)
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import (
    RequestScope,
    bind_request_scope,
    bind_verified_principal,
    reset_request_scope,
    reset_verified_principal,
)
from personal_ai.retrieval.installation import Installation, LexicalIndex
from personal_ai.retrieval.service import RetrievalService
from personal_ai.retrieval.tools import MAX_TOOL_BYTES, TOOL_ID
from personal_ai.settings import Settings
from personal_ai_hxe1.client import FixtureSource, read_fixture
from personal_ai_hxe1.ingest import document_from_bytes, load_document
from personal_ai_hxe1.server import retrieval_server
from personal_ai_hxe1.transport import HttpFixture, StdioFixture

SCOPE = RequestScope(
    owner_id="owner",
    acting_user_id="actor",
    application_id="personal_ai",
    request_id="test",
)


@contextmanager
def bound(guard=lambda: None, scope=SCOPE, *, authenticated=True):
    principal = AuthenticatedPrincipal(
        "fixture",
        scope.acting_user_id,
        scope.owner_id,
        None,
        1,
        authenticated,
        audience="fixture-client",
    )
    st = bind_request_scope(scope)
    pt = bind_verified_principal(principal)
    at = bind_client_authority(guard)
    try:
        yield
    finally:
        reset_client_authority(at)
        reset_verified_principal(pt)
        reset_request_scope(st)


@pytest.fixture
def metadata():
    now = datetime.now(UTC)
    return {
        "source_id": "orchard",
        "revision": "fixture-r1",
        "rights_epoch": "fixture-e1",
        "rights_reference": "synthetic-rights",
        "title": "Orchard",
        "license": "CC0-1.0",
        "content_sha256": sha256(TEXT.encode()).hexdigest(),
        "sensitivity": "public",
        "observed_at": now - timedelta(seconds=2),
        "expires_at": now + timedelta(minutes=5),
        "quote_allowed": True,
        "access": [
            SCOPE.model_dump(
                include={"owner_id", "acting_user_id", "application_id", "workspace_id"}
            )
        ],
    }


@pytest.fixture
def source(metadata):
    return FixtureSource(
        uuid4(), "hxe-fixture", "1", document_from_bytes(TEXT.encode(), metadata)
    )


def test_loader(tmp_path, metadata):
    path = tmp_path.resolve() / "orchard.md"
    path.write_text(TEXT)
    assert load_document(path, metadata, enabled=True).text == TEXT
    with pytest.raises(ValueError, match="source_unavailable"):
        load_document(path, metadata)
    link = path.with_name("link.md")
    link.symlink_to(path)
    for unsafe in (link, Path("orchard.md"), path.parent / ".." / path.name):
        with pytest.raises(ValueError, match="source_invalid"):
            load_document(unsafe, metadata, enabled=True)
    for raw in (b"changed", b"\xff", b"x" * 16001):
        path.write_bytes(raw)
        with pytest.raises(ValueError, match="source_invalid"):
            load_document(path, metadata, enabled=True)


@pytest.mark.parametrize(
    "mode,count",
    [
        ("ok", 1),
        ("schema", 0),
        ("effect", 0),
        ("duplicate", 0),
        ("page", 0),
        ("forged", 1),
        ("revoked", 1),
        ("disabled", 0),
        ("unverified", 0),
        ("wrong_scope", 0),
        ("wrong_owner", 0),
        ("wrong_actor", 0),
        ("wrong_workspace", 0),
        ("wrong_client", 0),
        ("expired", 0),
        ("wrong_endpoint", 0),
    ],
)
def test_http_source(source, mode, count):
    calls = []
    current = [source]
    if mode == "expired":
        now = datetime.now(UTC)
        source = replace(
            source,
            document=source.document.model_copy(
                update={
                    "observed_at": now - timedelta(minutes=2),
                    "expires_at": now - timedelta(minutes=1),
                }
            ),
        )
        current = [source]

    def dispatch():
        calls.append(1)
        if mode == "revoked":
            current.clear()

    def authority():
        if mode == "wrong_client":
            raise ValueError("synthetic client denied")

    scope = SCOPE.model_copy(
        update={
            "wrong_scope": {"application_id": "foreign"},
            "wrong_owner": {"owner_id": "foreign"},
            "wrong_actor": {"acting_user_id": "foreign"},
            "wrong_workspace": {"workspace_id": "foreign"},
        }.get(mode, {})
    )

    async def run():
        server = peer(mode, dispatch)
        app = server.streamable_http_app(json_response=True, stateless_http=True)
        with bound(authority, scope, authenticated=mode != "unverified"):
            async with app.router.lifespan_context(app):
                transport = HttpFixture(app)
                request = read_fixture(
                    transport,
                    source,
                    lambda: (
                        transport if mode != "wrong_endpoint" else None,
                        next(iter(current), None),
                    ),
                    enabled=mode != "disabled",
                )
                if mode == "ok":
                    version, document = await request
                    assert version == "2026-07-28"
                    assert document == source
                else:
                    with pytest.raises(ValueError, match="^source_unavailable$"):
                        await request

    asyncio.run(run())
    assert len(calls) == count


@pytest.mark.parametrize("broken", [False, True])
def test_stdio(source, broken):
    async def run():
        cwd = Path(__file__).resolve().parent
        transport = StdioFixture(
            Path(sys.executable),
            ("-I", str(cwd / "peer.py"), *(("broken",) if broken else ())),
            cwd,
        )
        with bound():
            request = read_fixture(
                transport,
                source,
                lambda transport=transport: (transport, source),
                enabled=True,
            )
            if broken:
                with pytest.raises(ValueError, match="^source_unavailable$"):
                    await request
            else:
                assert await request == ("2026-07-28", source)

    asyncio.run(run())


@pytest.mark.parametrize("mode", ["auto", "legacy"])
def test_independent_sdk_client(tmp_path, source, mode, monkeypatch):
    path = tmp_path.resolve() / "installation.json"
    settings = Settings(
        _env_file=None,
        ai_provider="fake",
        ai_model="fixture",
        app_environment="test",
        retrieval_enabled=True,
        retrieval_installation_file=str(path),
    )
    installation = Installation(
        schema_version="retrieval-installation-v2",
        issuer_id=source.issuer_id,
        enabled=True,
        tool_enabled=True,
        access=source.document.access,
        documents=(source.document,),
    )
    path.write_text(installation.model_dump_json())
    active = True

    def guard():
        if not active:
            raise ValueError("synthetic binding revoked")

    def unexpected_provider():
        pytest.fail("provider accounting reached")

    service = RetrievalService(
        settings, SCOPE, unexpected_provider, request_authority=guard
    )

    registry = ApplicationRegistry(
        (
            ApplicationDefinition(
                application_id=SCOPE.application_id,
                display_name="Fixture",
                memory_namespace=SCOPE.application_id,
                tool_ids=(TOOL_ID,),
            ),
        ),
        (
            CapabilityRegistration(
                capability_id=TOOL_ID,
                kind="tool",
                available=True,
                read_only_context=True,
                result_fields=("retrieval",),
                max_result_bytes=MAX_TOOL_BYTES,
            ),
        ),
    )

    async def run():
        nonlocal active
        with bound(guard):
            with pytest.raises(ValueError, match="mcp_unavailable"):
                retrieval_server(service, lambda: registry)
            server = retrieval_server(service, lambda: registry, enabled=True)
            app = server.streamable_http_app(json_response=True, stateless_http=True)
            async with (
                app.router.lifespan_context(app),
                Client(
                    HttpFixture(app).connect(),
                    mode=mode,
                    cache=None,
                    read_timeout_seconds=2,
                ) as consumer,
            ):
                assert consumer.protocol_version == (
                    "2026-07-28" if mode == "auto" else "2025-11-25"
                )
                assert [tool.name for tool in (await consumer.list_tools()).tools] == [
                    TOOL_ID
                ]
                arguments = {"query": "amber", "idempotency_key": str(uuid4())}
                outcome = await consumer.call_tool(TOOL_ID, arguments)
                assert not outcome.is_error
                (item,) = outcome.structured_content["retrieval"]["items"]
                assert item["quote"] == TEXT and len(item["citation_id"]) == 64
                with pytest.raises(MCPError, match="mcp_unavailable"):
                    await consumer.session.call_tool(
                        TOOL_ID, {**arguments, "sources": ["external"]}
                    )

                search = LexicalIndex.search

                def withdraw_during_search(index, *args, **kwargs):
                    found = search(index, *args, **kwargs)
                    path.write_text(
                        installation.model_copy(
                            update={"documents": ()}
                        ).model_dump_json()
                    )
                    return found

                with monkeypatch.context() as patch:
                    patch.setattr(LexicalIndex, "search", withdraw_during_search)
                    with pytest.raises(MCPError, match="mcp_unavailable"):
                        await consumer.session.call_tool(TOOL_ID, arguments)
                path.write_text(installation.model_dump_json())
                active = False
                assert not (await consumer.list_tools()).tools

                with pytest.raises(MCPError, match="mcp_unavailable"):
                    await consumer.session.call_tool(TOOL_ID, arguments)

    asyncio.run(run())


def test_redirect_and_raw_url_denied(source):
    paths = []

    async def redirect(scope, _receive, send):
        paths.append(scope["path"])
        await send(
            {
                "type": "http.response.start",
                "status": 307,
                "headers": [(b"location", b"/pivot")],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    async def run():
        with bound():
            fixture = HttpFixture(redirect)
            for transport in (fixture, "https://example.invalid/mcp"):
                with pytest.raises(ValueError, match="^source_unavailable$"):
                    await read_fixture(
                        transport,
                        source,
                        lambda transport=transport: (transport, source),
                        enabled=True,
                    )

    asyncio.run(run())
    assert paths and set(paths) == {"/mcp"}

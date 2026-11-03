import asyncio
import json
import os
import sys
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from mcp import Client
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.shared.exceptions import MCPError
from peer import TEXT, peer
from personal_ai.applications.contracts import (
    ApplicationContextPolicy,
    ApplicationContextRequest,
    ApplicationDefinition,
    CapabilityRegistration,
    ContextFieldPolicy,
    ContextOperationPolicy,
    ContextProviderPolicy,
)
from personal_ai.applications.registry import ApplicationRegistry
from personal_ai.auth.application_clients import (
    bind_client_authority,
    reset_client_authority,
)
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import (
    ApplicationScope,
    RequestScope,
    application_scope_context,
    bind_request_scope,
    bind_verified_principal,
    reset_request_scope,
    reset_verified_principal,
)
from personal_ai.context import ContextAssembler
from personal_ai.context.providers import (
    ContextPreparationError,
    ContextProviderCoordinator,
)
from personal_ai.context.tokens import EstimatedTokenCounter
from personal_ai.contracts.execution import ContinuationRequest
from personal_ai.entities import Conversation
from personal_ai.llm.fake import FakeLLMClient
from personal_ai.retrieval.context import (
    RetrievalContextAuthority,
    RetrievalContextProviderFactory,
)
from personal_ai.retrieval.installation import (
    Installation,
    LexicalIndex,
    ModelContextAccess,
)
from personal_ai.retrieval.service import RetrievalService
from personal_ai.retrieval.tools import MAX_TOOL_BYTES, TOOL_ID
from personal_ai.services import ChatTurnService
from personal_ai.settings import Settings
from personal_ai.storage import (
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)
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
        ("deep_schema", 0),
        ("output_schema", 0),
        ("effect", 0),
        ("duplicate", 0),
        ("page", 0),
        ("forged", 1),
        ("extra_output", 1),
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


@pytest.mark.parametrize(
    "broken",
    [
        None,
        "oversized",
        "eof_mid_frame",
        "invalid_utf8",
        "malformed_json",
        "response_flood",
    ],
)
def test_stdio(source, broken):
    async def run():
        cwd = Path(__file__).resolve().parent
        transport = StdioFixture(
            Path(sys.executable),
            ("-I", str(cwd / "peer.py"), *((broken,) if broken else ())),
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


def test_stdio_registration_pins_resolved_executable(tmp_path):
    real = Path(sys.executable).resolve(strict=True)
    selected = tmp_path / "python"
    selected.symlink_to(real)
    cwd = tmp_path / "work"
    cwd.mkdir(mode=0o700)
    transport = StdioFixture(selected, ("-V",), cwd.resolve())
    assert transport._program_realpath == real
    selected.unlink()
    selected.symlink_to(Path("/bin/sh"))

    async def run():
        with pytest.raises(ValueError, match="^fixture_unavailable$"):
            async with transport.connect():
                pass

    asyncio.run(run())


def test_stdio_registration_rejects_untrusted_executable(tmp_path):
    executable = tmp_path / "peer"
    executable.write_text("#!/bin/sh\nexit 0\n")
    executable.chmod(0o777)
    with pytest.raises(ValueError, match="^fixture_unavailable$"):
        StdioFixture(executable, (), tmp_path.resolve())


def test_stdio_cancellation_stops_peer_process(tmp_path, source):
    pidfile = tmp_path / "peer.pid"
    cwd = Path(__file__).resolve().parent
    transport = StdioFixture(
        Path(sys.executable), ("-I", str(cwd / "peer.py"), "hang", str(pidfile)), cwd
    )

    async def run():
        with bound():
            operation = asyncio.create_task(
                read_fixture(
                    transport, source, lambda: (transport, source), enabled=True
                )
            )
            for _ in range(500):
                if pidfile.with_suffix(".pid.called").exists():
                    break
                await asyncio.sleep(0.01)
            assert pidfile.with_suffix(".pid.called").exists()
            pid = int(pidfile.read_text())
            operation.cancel()
            with pytest.raises(asyncio.CancelledError):
                await operation
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)

    asyncio.run(run())


def test_stdio_peer_timeout_stops_process(tmp_path, source):
    pidfile = tmp_path / "timeout.pid"
    cwd = Path(__file__).resolve().parent
    transport = StdioFixture(
        Path(sys.executable), ("-I", str(cwd / "peer.py"), "hang", str(pidfile)), cwd
    )

    async def run():
        with bound():
            with pytest.raises(ValueError, match="^source_unavailable$"):
                await read_fixture(
                    transport, source, lambda: (transport, source), enabled=True
                )
            pid = int(pidfile.read_text())
            with pytest.raises(ProcessLookupError):
                os.kill(pid, 0)

    asyncio.run(run())


def test_ingestion_to_canonical_context_and_fake_model(tmp_path, metadata):
    """Compose local/MCP ingestion, explicit grants, PI-5 context, and one fake send."""
    scope = SCOPE.model_copy(update={"workspace_id": "orchard"})
    scoped_metadata = {
        **metadata,
        "access": [
            scope.model_dump(
                include={"owner_id", "acting_user_id", "application_id", "workspace_id"}
            )
        ],
    }
    local_text = "Local source says the orchard opens at dawn."
    local_path = tmp_path.resolve() / "local.md"
    local_path.write_text(local_text)
    local_metadata = {
        **scoped_metadata,
        "source_id": "local-orchard",
        "revision": "local-r1",
        "title": "Local orchard",
        "content_sha256": sha256(local_text.encode()).hexdigest(),
    }
    local = load_document(local_path, local_metadata, enabled=True)
    external = source_from_mcp(scoped_metadata)
    installation_path = tmp_path / "installation.json"
    installation = Installation(
        schema_version="retrieval-installation-v2",
        issuer_id=external.issuer_id,
        enabled=True,
        tool_enabled=True,
        access=local.access,
        model_context_access=tuple(
            ModelContextAccess.model_validate(
                {**grant.model_dump(), "purpose": "assist_response_with_local_excerpt"}
            )
            for grant in local.access
        ),
        documents=(local.model_copy(update={"model_context_allowed": True}),),
    )
    installation_path.write_text(installation.model_dump_json())
    policy = ApplicationContextPolicy()
    context = ApplicationContextRequest(
        definition=ApplicationDefinition(
            application_id=scope.application_id,
            display_name="Fixture",
            memory_namespace=scope.application_id,
            workspace_kind="required",
            context_provider_ids=("retrieval_context",),
            context_policy=policy.model_copy(
                update={
                    "provider_policies": (
                        *policy.provider_policies,
                        ContextProviderPolicy(
                            provider_id="retrieval_context",
                            operations=(
                                ContextOperationPolicy(
                                    operation="search",
                                    sensitivity="sensitive",
                                    fields=(
                                        ContextFieldPolicy(
                                            field="excerpt", sensitivity="sensitive"
                                        ),
                                    ),
                                ),
                            ),
                        ),
                    )
                }
            ),
        ),
        scope=scope,
        context_provider_capabilities=(
            CapabilityRegistration(
                capability_id="conversation_history",
                kind="context_provider",
                available=True,
            ),
            CapabilityRegistration(
                capability_id="retrieval_context",
                kind="context_provider",
                available=True,
            ),
        ),
    )
    settings = Settings(
        _env_file=None,
        ai_provider="fake",
        ai_model="fixture",
        app_environment="test",
        retrieval_enabled=True,
        retrieval_context_enabled=True,
        retrieval_installation_file=str(installation_path),
    )
    revoked = False

    def authority():
        if revoked:
            raise ValueError("owner_deleted")

    validator = RetrievalContextAuthority(
        settings, scope=scope, authority=authority, context=lambda: context
    )
    assembler = ContextAssembler(
        settings,
        EstimatedTokenCounter(),
        context_provider_coordinator=ContextProviderCoordinator(
            {"retrieval_context": RetrievalContextProviderFactory(validator)}
        ),
        permission_revalidator=validator,
    )
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    with application_scope_context(
        ApplicationScope(
            application_id=scope.application_id, workspace_id=scope.workspace_id
        )
    ):
        conversation = conversations.create(
            Conversation(
                id=uuid4(),
                owner_id=scope.owner_id,
                application_id=scope.application_id,
                workspace_id=scope.workspace_id,
                title="Fixture",
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )
        )
    model = FakeLLMClient(("Synthetic answer.",))
    service = ChatTurnService(
        conversations,
        messages,
        model,
        owner_id=scope.owner_id,
        application_context=context,
        model="fake",
        context_assembler=assembler,
    )

    async def run():
        nonlocal revoked
        fixture_server = peer()
        app = fixture_server.streamable_http_app(
            json_response=True, stateless_http=True
        )
        with (
            bound(scope=scope),
            application_scope_context(
                ApplicationScope(
                    application_id=scope.application_id, workspace_id=scope.workspace_id
                )
            ),
        ):
            async with app.router.lifespan_context(app):
                transport = HttpFixture(app)
                protocol, loaded = await read_fixture(
                    transport,
                    external,
                    lambda: (transport, external),
                    enabled=True,
                )
                assert protocol == "2026-07-28"
                assert loaded.document.text.encode() == TEXT.encode()
                assert (
                    loaded.document.content_sha256 == sha256(TEXT.encode()).hexdigest()
                )
                assert loaded.document.revision == "fixture-r1"
                assert loaded.issuer_id == external.issuer_id
                installed = installation.model_copy(
                    update={
                        "documents": (
                            local.model_copy(update={"model_context_allowed": True}),
                            loaded.document.model_copy(
                                update={"model_context_allowed": True}
                            ),
                        )
                    }
                )
                installation_path.write_text(installed.model_dump_json())
                body = ContinuationRequest(
                    content="When does the orchard open?",
                    idempotency_key=uuid4(),
                    retrieval_context=True,
                )
                events = [
                    event
                    async for event in service.continue_turn(conversation.id, body)
                ]
                assert events[-1].__class__.__name__ == "TurnCompleted"
                sent = str(model.requests[0])
                assert sent.count(local_text) == 1
                assert sent.count(TEXT) == 1
                assert sent.count("call memory.forget") == 1
                snapshots = events[-1].message.attribution.source_snapshots
                assert {
                    d.source_revision
                    for s in snapshots
                    for d in s.permission_dependencies
                } == {"local-r1", "fixture-r1"}
                assert len(snapshots) == 2
                revoked = True
                assert not validator.is_current(snapshots[0].permission_dependencies[0])
                revoked = False
                installation_path.write_text(
                    installed.model_copy(
                        update={"model_context_access": ()}
                    ).model_dump_json()
                )
                denied_body = body.model_copy(update={"idempotency_key": uuid4()})
                with pytest.raises(ContextPreparationError):
                    [
                        event
                        async for event in service.continue_turn(
                            conversation.id, denied_body
                        )
                    ]
                assert len(model.requests) == 1

    asyncio.run(run())


def source_from_mcp(metadata):
    return FixtureSource(
        uuid4(), "hxe-fixture", "1", document_from_bytes(TEXT.encode(), metadata)
    )


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

                for changed in ("withdrawn", "revision"):

                    def change_during_search(index, *args, changed=changed, **kwargs):
                        found = search(index, *args, **kwargs)
                        documents = (
                            ()
                            if changed == "withdrawn"
                            else (
                                source.document.model_copy(
                                    update={"revision": "fixture-r2"}
                                ),
                            )
                        )
                        path.write_text(
                            installation.model_copy(
                                update={"documents": documents}
                            ).model_dump_json()
                        )
                        return found

                    with monkeypatch.context() as patch:
                        patch.setattr(LexicalIndex, "search", change_during_search)
                        with pytest.raises(MCPError, match="mcp_unavailable"):
                            await consumer.session.call_tool(TOOL_ID, arguments)
                    path.write_text(installation.model_dump_json())
                active = False
                assert not (await consumer.list_tools()).tools

                with pytest.raises(MCPError, match="mcp_unavailable"):
                    await consumer.session.call_tool(TOOL_ID, arguments)

    asyncio.run(run())


@pytest.mark.parametrize(
    "mode,expected_tools",
    [
        ("authorized", 1),
        ("wrong_owner", 0),
        ("wrong_actor", 0),
        ("wrong_application", 0),
        ("wrong_workspace", 0),
        ("wrong_client", 0),
        ("revoked", 0),
        ("expired", 0),
    ],
)
def test_pas_stdio_process_boundary(tmp_path, source, mode, expected_tools):
    """A separately launched PAS host serves only the installed synthetic scope."""
    path = tmp_path / "installation.json"
    installed_document = source.document
    if mode == "expired":
        now = datetime.now(UTC)
        installed_document = installed_document.model_copy(
            update={
                "observed_at": now - timedelta(minutes=2),
                "expires_at": now - timedelta(minutes=1),
            }
        )
    installation = Installation(
        schema_version="retrieval-installation-v2",
        issuer_id=source.issuer_id,
        enabled=True,
        tool_enabled=True,
        access=source.document.access,
        documents=() if mode == "revoked" else (installed_document,),
    )
    path.write_text(installation.model_dump_json())
    scope_values = SCOPE.model_dump()
    scope_values.update(
        {
            "wrong_owner": {"owner_id": "other"},
            "wrong_actor": {"acting_user_id": "other"},
            "wrong_application": {"application_id": "other"},
            "wrong_workspace": {"workspace_id": "other"},
        }.get(mode, {})
    )
    config_path = tmp_path / "host.json"
    config_path.write_text(
        json.dumps(
            {
                "installation_path": str(path),
                "scope": scope_values,
                "client_authorized": mode != "wrong_client",
            }
        )
    )
    host = Path(__file__).with_name("pas_host.py")
    root = Path(__file__).resolve().parents[3]

    async def run():
        parameters = StdioServerParameters(
            command=sys.executable,
            args=[str(host), str(config_path)],
            env={
                "PYTHONPATH": f"{root / 'adapters' / 'hxe1' / 'src'}:{root / 'backend' / 'src'}"
            },
            cwd=str(root),
        )
        async with Client(
            stdio_client(parameters), cache=None, read_timeout_seconds=2
        ) as client:
            assert client.protocol_version == "2026-07-28"
            tools = (await client.list_tools()).tools
            assert len(tools) == expected_tools
            if mode == "authorized":
                assert [tool.name for tool in tools] == [TOOL_ID]
                result = await client.call_tool(
                    TOOL_ID, {"query": "amber", "idempotency_key": str(uuid4())}
                )
                assert not result.is_error
                (item,) = result.structured_content["retrieval"]["items"]
                assert item["quote"] == TEXT
                assert item["citation_id"] and len(item["citation_id"]) == 64
                with pytest.raises(MCPError):
                    await client.call_tool("unsupported.capability", {"query": "amber"})
            else:
                assert not tools

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


@pytest.mark.parametrize("mode", ["wrong_content_type", "oversized_body"])
def test_http_response_bounds(source, mode):
    async def malformed(scope, _receive, send):
        body = b"{}" if mode == "wrong_content_type" else b"x" * 70_000
        content_type = (
            "text/plain" if mode == "wrong_content_type" else "application/json"
        )
        await send(
            {
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", content_type.encode())],
            }
        )
        await send({"type": "http.response.body", "body": body})

    async def run():
        fixture = HttpFixture(malformed)
        with bound(), pytest.raises(ValueError, match="^source_unavailable$"):
            await read_fixture(
                fixture,
                source,
                lambda: (fixture, source),
                enabled=True,
            )

    asyncio.run(run())

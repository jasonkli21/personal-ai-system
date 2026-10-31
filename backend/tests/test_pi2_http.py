"""PI-2 real loopback HTTP over signed test issuer and explicit fake ports.

Copied unchanged into an independently installed artifact environment. Never
replace middleware or the Google JWT verifier; only its key transport is fake.
"""

import asyncio
import importlib.util
import json
import os
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import httpx
import jwt
import pytest
import uvicorn
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from reading_logbook.client import APIError, PlatformClient, UncertainTurn, read_completion
from reading_logbook.store import Logbook
from reading_logbook_host import application, context

from personal_ai.api import dependencies as deps
from personal_ai.applications.registry import (
    ApplicationContribution,
    ApplicationContributionCatalog,
)
from personal_ai.auth import verification
from personal_ai.context import ContextAssembler
from personal_ai.context.repositories import InMemorySummaryRepository
from personal_ai.context.runtime import ContextRuntimeContributionCatalog
from personal_ai.context.tokens import EstimatedTokenCounter
from personal_ai.context.traces import InMemoryContextTraceRepository
from personal_ai.llm.fake import FakeLLMClient
from personal_ai.main import create_app
from personal_ai.settings import Settings, get_settings
from personal_ai.storage.errors import StorageUnavailableError
from personal_ai.storage.fake import InMemoryConversationRepository, InMemoryMessageRepository

pytestmark = pytest.mark.loopback_http


@pytest.fixture
def http_platform(tmp_path, monkeypatch, request):
    if request.node.name == "test_pi4_signed_http_profile_consent_installed_unrelated_consumer":
        monkeypatch.setenv("READING_LOGBOOK_PROFILE_ENABLED", "true")
    from personal_ai.persistence import factory as persistence

    class ClosedFactory:
        def __init__(self, settings):
            pass

        def mutation_repository(self):
            return SimpleNamespace(required_operation_contracts=lambda: ())

        def __getattr__(self, name):
            raise AssertionError("unconfigured persistence port: " + name)

    monkeypatch.setattr(persistence, "persistence_factory", ClosedFactory)
    now = int(time.time())
    policy = tmp_path / "client-policy.json"
    binding = {
        "audience": "logbook-oauth-client",
        "authorized_party": "logbook-oauth-client",
        "application_id": "reading_logbook",
        "expires_at": now + 7200,
        "enabled": True,
    }
    binding_b = {
        "audience": "logbook-b-oauth-client",
        "authorized_party": "logbook-b-oauth-client",
        "application_id": "reading_logbook_b",
        "expires_at": now + 7200,
        "enabled": True,
    }

    def write_policy(**updates):
        policy.write_text(
            json.dumps(
                {
                    "schema_version": "application-client-policy-v1",
                    "bindings": [{**binding, **updates}, {**binding_b, **updates}],
                }
            )
        )

    write_policy()
    members = tmp_path / "members.json"
    membership = {
        "issuer": "https://accounts.google.com",
        "subject": "synthetic-owner",
        "workspace_id": "shelf",
        "expires_at": now + 7200,
    }
    memberships = [
        membership,
        {**membership, "subject": "synthetic-owner-b"},
    ]
    members.write_text(
        json.dumps({"schema_version": "reading-logbook-membership-v1", "memberships": memberships})
    )
    monkeypatch.setenv("READING_LOGBOOK_MEMBERSHIP_FILE", str(members))
    settings = Settings(
        _env_file=None,
        ai_provider="fake",
        ai_model="pi2-model",
        app_environment="test",
        auth_mode="google_oidc",
        auth_required=True,
        auth_audience="builtin-web-client",
        auth_allowed_emails=("synthetic@gmail.com",),
        auth_application_clients_file=str(policy),
    )
    assert not settings.memory_enabled and not settings.external_turn_acceptance_enabled
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    )
    public = (
        key.public_key()
        .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
        .decode()
    )
    key_requests = []

    @contextmanager
    def keys():
        def request(url, **kwargs):
            assert url == "https://www.googleapis.com/oauth2/v1/certs"
            key_requests.append(url)
            return SimpleNamespace(status=200, data=json.dumps({"pi2-test": public}).encode())

        yield request

    monkeypatch.setattr(verification, "signing_key_request", keys)
    verification._verified_tokens.clear()

    def token(**changes):
        claims = {
            "iss": "https://accounts.google.com",
            "aud": "logbook-oauth-client",
            "sub": "synthetic-owner",
            "email": "synthetic@gmail.com",
            "email_verified": True,
            "iat": now,
            "auth_time": now,
            "exp": now + 3600,
            "jti": str(uuid4()),
        }
        claims.update(changes)
        return jwt.encode(claims, private, algorithm="RS256", headers={"kid": "pi2-test"})

    if os.environ.get("PI2_INSTALLED"):
        assert importlib.util.find_spec("personal_ai_reference_apps") is None
        app = create_app(selected_contributions=("reading_logbook",))
    else:
        base_contribution = application()
        app_b_definition = base_contribution.definitions[0].model_copy(
            update={
                "application_id": "reading_logbook_b",
                "display_name": "Reading Logbook B",
                "memory_namespace": "reading_logbook_b",
            }
        )

        class MembershipB:
            def is_member(self, principal, application_id, workspace_id):
                return (
                    application_id == "reading_logbook_b"
                    and principal.authenticated
                    and any(
                        row["issuer"] == principal.issuer
                        and row["subject"] == principal.subject
                        and row["workspace_id"] == workspace_id
                        and row["expires_at"] > time.time()
                        for row in json.loads(members.read_text())["memberships"]
                    )
                )

        contribution_b = ApplicationContribution(
            definitions=(app_b_definition,),
            workspace_authorizers={"reading_logbook_b": MembershipB()},
        )
        app = create_app(
            application_catalog=ApplicationContributionCatalog(
                (
                    ("reading_logbook", application),
                    ("reading_logbook_b", lambda: contribution_b),
                )
            ),
            context_runtime_catalog=ContextRuntimeContributionCatalog(
                (("reading_logbook", context), ("reading_logbook_b", context))
            ),
        )
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    summaries = InMemorySummaryRepository()
    traces = InMemoryContextTraceRepository()
    hook = SimpleNamespace(count=lambda: None)

    class Counter(EstimatedTokenCounter):
        def count(self, messages):
            hook.count()
            return super().count(messages)

    release, started = threading.Event(), threading.Event()

    class Model(FakeLLMClient):
        hold = False

        async def stream_events(self, *args, **kwargs):
            async for event in super().stream_events(*args, **kwargs):
                yield event
                if self.hold and event.kind == "delta":
                    started.set()
                    while not release.is_set():
                        await asyncio.sleep(0.005)

    llm = Model(("Synthetic ", "answer"))
    assembler = ContextAssembler(settings, Counter(), summaries)
    app.dependency_overrides = {
        get_settings: lambda: settings,
        deps.get_conversation_repository: lambda: conversations,
        deps.get_message_repository: lambda: messages,
        deps.get_summary_repository: lambda: summaries,
        deps.get_context_trace_repository: lambda: traces,
        deps.get_context_assembler: lambda: assembler,
        deps.get_llm_client: lambda: llm,
    }
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    base = f"http://127.0.0.1:{sock.getsockname()[1]}"
    config = uvicorn.Config(
        app,
        loop="asyncio",
        http="h11",
        ws="none",
        log_config=None,
        access_log=False,
        lifespan="on",
        timeout_graceful_shutdown=2,
    )
    server = uvicorn.Server(config)
    thread = threading.Thread(target=lambda: server.run(sockets=[sock]), daemon=True)
    thread.start()
    deadline = time.monotonic() + 5
    while not server.started and thread.is_alive() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert server.started
    signed = token()
    client = PlatformClient(base, signed, "shelf", allow_loopback=True)
    headers = {
        "Authorization": "Bearer " + signed,
        "X-Application-ID": "reading_logbook",
        "X-Workspace-ID": "shelf",
    }
    with httpx.Client(base_url=base, trust_env=False, timeout=3) as raw:
        yield SimpleNamespace(
            client=client,
            raw=raw,
            headers=headers,
            headers_b={
                "Authorization": "Bearer "
                + token(aud="logbook-b-oauth-client", azp="logbook-b-oauth-client"),
                "X-Application-ID": "reading_logbook_b",
                "X-Workspace-ID": "shelf",
            },
            token=token,
            app=app,
            llm=llm,
            traces=traces,
            conversations=conversations,
            messages=messages,
            policy=policy,
            write_policy=write_policy,
            members=members,
            hook=hook,
            started=started,
            release=release,
            key_requests=key_requests,
        )
    release.set()
    server.should_exit = True
    thread.join(5)
    sock.close()
    assert not thread.is_alive()


def turn(content="Discuss this explicitly supplied note", key=None):
    return {
        "content": content,
        "idempotency_key": str(key or uuid4()),
        "choice": {"mode": "automatic"},
    }


def test_real_http_shared_harness_replay_and_scoped_status(http_platform):
    h = http_platform
    key = uuid4()
    created = h.client.start("Reading", key)
    assert h.client.start("Reading", key) == created
    assert created["owner_id"].startswith("usr_") and created["application_id"] == "reading_logbook"
    assert len(h.client.conversations()["conversations"]) == 1
    cid = created["id"]
    body = turn()
    assert h.client.status(cid, body["idempotency_key"])["state"] == "not_found"
    preview = h.client.preview(cid, body)
    assert not h.llm.requests
    assert "selected_message_count" in preview and "planned_sources" in preview
    result = h.client.ask(cid, body)
    assert result["content"] == "Synthetic answer"
    assert h.client.ask(cid, body) == result
    assert len(h.llm.requests) == 1
    assert len(h.client.conversation(cid)["messages"]) == 2
    retained = [t for rows in h.traces.records.values() for t in rows]
    assert (
        len(retained) == 1
        and 0 < retained[0].actual_input_tokens <= retained[0].global_input_tokens
    )
    assert retained[0].application_id == "reading_logbook" and retained[0].workspace_id == "shelf"
    assert h.key_requests
    assert (
        h.raw.get(f"/v1/conversations/{cid}", headers=h.headers).headers["cache-control"]
        == "no-store"
    )
    with pytest.raises(APIError) as conflict:
        h.client.ask(cid, {**body, "content": "changed"})
    assert conflict.value.status == 409
    with pytest.raises(APIError) as conflict:
        h.client.start("changed", key)
    assert conflict.value.status == 409 and len(h.llm.requests) == 1


@pytest.mark.parametrize("payload", [{}, {"idempotency_key": None}])
def test_external_creation_requires_non_null_idempotency_key(http_platform, payload):
    h = http_platform
    first = h.raw.post("/v1/conversations", headers=h.headers, json=payload)
    second = h.raw.post("/v1/conversations", headers=h.headers, json=payload)
    assert first.status_code == second.status_code == 422
    assert first.json()["error"]["code"] == "validation_error"
    assert not h.conversations._conversations and not h.llm.requests


def test_external_creation_key_replay_conflict_and_openapi(http_platform):
    h = http_platform
    key = str(uuid4())
    body = {"title": "Original", "idempotency_key": key}
    first = h.raw.post("/v1/conversations", headers=h.headers, json=body)
    replay = h.raw.post("/v1/conversations", headers=h.headers, json=body)
    changed = h.raw.post(
        "/v1/conversations", headers=h.headers, json={**body, "title": "Changed"}
    )
    assert first.status_code == replay.status_code == 201
    assert first.json()["id"] == replay.json()["id"]
    assert changed.status_code == 409
    assert len(h.conversations._conversations) == 1 and not h.llm.requests
    from personal_ai.api.consumer_contract import consumer_openapi

    request_schema = consumer_openapi()["paths"]["/v1/conversations"]["post"]["requestBody"]
    schema_ref = request_schema["content"]["application/json"]["schema"]["$ref"]
    assert schema_ref.endswith("ExternalCreateConversationRequest")
    assert (
        "idempotency_key"
        in consumer_openapi()["components"]["schemas"]["ExternalCreateConversationRequest"][
            "required"
        ]
    )
    assert (
        consumer_openapi()["components"]["schemas"]["ExternalCreateConversationRequest"][
            "properties"
        ]["idempotency_key"]["type"]
        == "string"
    )


def test_completed_replay_rechecks_source_authority_before_disclosure(http_platform, monkeypatch):
    h = http_platform
    cid = h.client.start("Replay fence", uuid4())["id"]
    body = turn()
    assert h.client.ask(cid, body)["content"] == "Synthetic answer"
    from personal_ai.services.chat import service as chat_service

    monkeypatch.setattr(
        chat_service,
        "source_snapshots_current",
        lambda *_args, **_kwargs: False,
    )
    response = h.raw.post(
        f"/v1/conversations/{cid}/continue", json=body, headers=h.headers
    )
    assert response.status_code == 200
    assert "Synthetic answer" not in response.text
    assert "response.completed" not in response.text
    assert "response.error" in response.text
    assert len(h.llm.requests) == 1


@pytest.mark.parametrize(
    "changes,expected",
    [
        ({"X-Application-ID": "personal_ai"}, 403),
        ({"X-Application-ID": "unselected"}, 403),
        ({"X-Owner-ID": "forged"}, 403),
        ({"X-Acting-User-ID": "forged"}, 403),
        ({"X-Workspace-ID": "other"}, 403),
        ({"X-Workspace-ID": "other", "X-Client-Context": '{"member":true}'}, 403),
    ],
)
def test_forged_scope_denied(http_platform, changes, expected):
    h = http_platform
    response = h.raw.post("/v1/conversations", headers={**h.headers, **changes}, json={})
    assert response.status_code == expected
    assert not h.conversations._conversations and not h.llm.requests


@pytest.mark.parametrize(
    "claims",
    [
        {"aud": "wrong"},
        {"azp": "another-client"},
        {"iss": "https://evil.invalid"},
        {"exp": 1},
        {"sub": "service-account", "email": "svc@example.iam.gserviceaccount.com"},
        {"aud": ["logbook-oauth-client", "builtin-web-client"]},
        {"sub": "nonmember"},
    ],
)
def test_verified_token_client_and_workspace_checks(http_platform, claims):
    h = http_platform
    response = h.raw.post(
        "/v1/conversations",
        headers={**h.headers, "Authorization": "Bearer " + h.token(**claims)},
        json={},
    )
    assert response.status_code in {401, 403}
    assert not h.llm.requests and not h.conversations._conversations


def test_builtin_and_cross_application_guesses(http_platform):
    h = http_platform
    builtin_headers = {"Authorization": "Bearer " + h.token(aud="builtin-web-client")}
    original = h.raw.post("/v1/conversations", json={}, headers=builtin_headers)
    assert original.status_code == 201, original.text
    cid = original.json()["id"]
    assert h.raw.get(f"/v1/conversations/{cid}", headers=h.headers).status_code == 404
    assert (
        h.raw.get(f"/v1/conversations/{cid}/continuations/{uuid4()}", headers=h.headers).status_code
        == 404
    )
    own = h.client.start("Books", uuid4())
    assert h.raw.get(f"/v1/conversations/{own['id']}", headers=builtin_headers).status_code == 404
    assert h.raw.get("/v1/conversations", headers=builtin_headers).json()["conversations"] == [
        original.json()
    ]
    assert (
        h.raw.post(
            "/v1/conversations",
            json={},
            headers={
                **builtin_headers,
                "X-Application-ID": "reading_logbook",
                "X-Workspace-ID": "shelf",
            },
        ).status_code
        == 403
    )
    # Validly signed raw service assertions and task delegation headers are not a user login.
    assert (
        h.raw.post(
            "/v1/conversations", json={}, headers={**h.headers, "X-User-Delegation": "unsigned"}
        ).status_code
        == 401
    )


def test_two_external_application_bindings_cannot_cross(http_platform):
    if os.environ.get("PI2_INSTALLED"):
        pytest.skip("second synthetic host is exercised in the source HTTP profile")
    h = http_platform
    headers_a = h.headers
    headers_b = h.headers_b
    headers_b_other_owner = {
        **headers_b,
        "Authorization": "Bearer "
        + h.token(
            aud="logbook-b-oauth-client",
            azp="logbook-b-oauth-client",
            sub="synthetic-owner-b",
        ),
    }
    body_a = {"title": "A", "idempotency_key": str(uuid4())}
    body_b = {"title": "B", "idempotency_key": str(uuid4())}
    created_a = h.raw.post("/v1/conversations", headers=headers_a, json=body_a)
    created_b = h.raw.post("/v1/conversations", headers=headers_b, json=body_b)
    created_b_other = h.raw.post(
        "/v1/conversations", headers=headers_b_other_owner, json=body_b
    )
    assert created_a.status_code == created_b.status_code == created_b_other.status_code == 201

    mismatches = [
        (headers_a, headers_b, created_b.json()["id"], body_b["idempotency_key"]),
        (headers_b, headers_a, created_a.json()["id"], body_a["idempotency_key"]),
        (
            headers_a,
            headers_b,
            created_b_other.json()["id"],
            body_b["idempotency_key"],
        ),
    ]
    before = len(h.conversations._conversations)
    for token_headers, foreign_headers, conversation_id, key in mismatches:
        auth = {**foreign_headers, "Authorization": token_headers["Authorization"]}
        assert h.raw.post(
            "/v1/conversations", headers=auth, json={"idempotency_key": str(uuid4())}
        ).status_code == 403
        assert h.raw.get("/v1/conversations", headers=auth).status_code == 403
        assert h.raw.get(f"/v1/conversations/{conversation_id}", headers=auth).status_code == 403
        assert (
            h.raw.get(
                f"/v1/conversations/{conversation_id}/continuations/{key}", headers=auth
            ).status_code
            == 403
        )
        assert h.raw.post(
            f"/v1/conversations/{conversation_id}/context-preview",
            headers=auth,
            json=turn(),
        ).status_code == 403
        assert h.raw.post(
            f"/v1/conversations/{conversation_id}/continue",
            headers=auth,
            json=turn(),
        ).status_code == 403
    assert len(h.conversations._conversations) == before
    assert not h.llm.requests


def test_external_operations_sources_and_payload_limits(http_platform):
    h = http_platform
    cid = h.client.start("Books", uuid4())["id"]
    for path in ("/v1/profile", "/v1/account/export", f"/v1/conversations/{cid}/context"):
        assert h.raw.get(path, headers=h.headers).status_code in {403, 404, 405}
    for suffix in ("messages", "external-turns/prepare"):
        assert (
            h.raw.post(
                f"/v1/conversations/{cid}/{suffix}", json=turn(), headers=h.headers
            ).status_code
            == 403
        )
    assert (
        h.raw.post("/v1/conversations", json={"owner_id": "foreign"}, headers=h.headers).status_code
        == 422
    )
    assert (
        h.raw.post(
            f"/v1/conversations/{cid}/continue",
            json={**turn(), "content": "x" * 20001},
            headers=h.headers,
        ).status_code
        == 422
    )
    assert (
        h.raw.post(
            f"/v1/conversations/{cid}/continue", content=b"x" * 131073, headers=h.headers
        ).status_code
        == 413
    )
    body = turn()
    body["federation_choice_ids"] = ["A" * 43]
    response = h.raw.post(f"/v1/conversations/{cid}/context-preview", json=body, headers=h.headers)
    assert response.status_code in {403, 404, 422, 503}
    assert not h.llm.requests
    # The narrow host has no memory/global profile policy or custom provider.
    definition = h.app.state.application_registry.get("reading_logbook")
    assert [p.provider_id for p in definition.context_policy.provider_policies] == [
        "conversation_history"
    ]
    assert not h.app.state.context_runtime_registry.provider_factories


@pytest.mark.parametrize("change", ["disabled", "expired", "removed", "malformed", "unavailable"])
def test_revoked_or_unavailable_policy_fails_closed(http_platform, change):
    h = http_platform
    h.client.start("Books", uuid4())  # populate signature cache before revocation
    if change == "disabled":
        h.write_policy(enabled=False)
    elif change == "expired":
        h.write_policy(expires_at=1)
    elif change == "removed":
        h.policy.write_text('{"schema_version":"application-client-policy-v1","bindings":[]}')
    elif change == "malformed":
        h.policy.write_text("{}")
    else:
        h.policy.unlink()
    response = h.raw.get("/v1/conversations", headers=h.headers)
    assert response.status_code in {401, 403, 503} and not h.llm.requests


@pytest.mark.parametrize("authority", ["binding", "workspace", "token", "directory"])
def test_authority_revoked_during_count_never_sends(http_platform, authority, monkeypatch):
    h = http_platform
    cid = h.client.start("Books", uuid4())["id"]
    body = turn()

    def revoke():
        if authority == "binding":
            h.write_policy(enabled=False)
        elif authority == "workspace":
            h.members.write_text(
                '{"schema_version":"reading-logbook-membership-v1","memberships":[]}'
            )
        elif authority == "directory":
            owner = next(iter(h.conversations._conversations.values())).owner_id
            h.app.state.principal_directory.deactivate(owner)
        else:
            from personal_ai.auth import application_clients

            monkeypatch.setattr(
                application_clients, "time", SimpleNamespace(time=lambda: time.time() + 4000)
            )

    h.hook.count = revoke
    response = h.raw.post(f"/v1/conversations/{cid}/continue", json=body, headers=h.headers)
    assert response.status_code in {422, 503} or "response.error" in response.text
    assert "response.completed" not in response.text and not h.llm.requests


@pytest.mark.parametrize(
    "authority", ["binding", "workspace", "directory", "token", "source"]
)
def test_authority_revoked_after_first_delta_stops_later_output(http_platform, authority, monkeypatch):
    h = http_platform
    cid = h.client.start("Books", uuid4())["id"]
    body = turn()
    h.llm.hold = True

    source_current = {"value": True}
    if authority == "source":
        from personal_ai.services.chat import service as chat_service

        monkeypatch.setattr(
            chat_service,
            "source_snapshots_current",
            lambda *_args, **_kwargs: source_current["value"],
        )
    original_policy_time = None
    lines = []
    current_event = ""
    saw_first_delta = False
    with h.raw.stream(
        "POST", f"/v1/conversations/{cid}/continue", json=body, headers=h.headers
    ) as response:
        assert response.status_code == 200
        stream_lines = response.iter_lines()
        for line in stream_lines:
            lines.append(line)
            if line.startswith("event: "):
                current_event = line[7:]
            if current_event == "response.delta" and line.startswith("data: "):
                saw_first_delta = True
                break
        assert saw_first_delta
        if authority == "binding":
            h.write_policy(enabled=False)
        elif authority == "workspace":
            h.members.write_text(
                '{"schema_version":"reading-logbook-membership-v1","memberships":[]}'
            )
        elif authority == "directory":
            owner = next(iter(h.conversations._conversations.values())).owner_id
            h.app.state.principal_directory.deactivate(owner)
        elif authority == "token":
            from personal_ai.auth import application_clients

            original_policy_time = application_clients.time
            monkeypatch.setattr(
                application_clients, "time", SimpleNamespace(time=lambda: time.time() + 4000)
            )
        else:
            source_current["value"] = False
        h.release.set()
        lines.extend(stream_lines)

    output = "\n".join(lines)
    assert '"delta":"Synthetic "' in output
    assert '"delta":"answer"' not in output
    assert "response.completed" not in output
    assert output.count("response.error") == 1
    assert len(h.llm.requests) == 1
    if authority == "binding":
        h.write_policy()
    elif authority == "workspace":
        h.members.write_text(
            json.dumps(
                {
                    "schema_version": "reading-logbook-membership-v1",
                    "memberships": [
                        {
                            "issuer": "https://accounts.google.com",
                            "subject": "synthetic-owner",
                            "workspace_id": "shelf",
                            "expires_at": int(time.time()) + 7200,
                        }
                    ],
                }
            )
        )
    elif authority == "directory":
        owner = next(iter(h.conversations._conversations.values())).owner_id
        h.app.state.principal_directory._mappings[owner]["status"] = "active"
    elif authority == "token":
        from personal_ai.auth import application_clients

        monkeypatch.setattr(application_clients, "time", original_policy_time)
    else:
        source_current["value"] = True
    status = h.client.status(cid, body["idempotency_key"])
    assert status["state"] == "unknown"
    with pytest.raises(APIError) as conflict:
        h.client.ask(cid, body)
    assert conflict.value.status == 409 and len(h.llm.requests) == 1


def test_racing_creation_and_continuation_keep_original_send(http_platform):
    h = http_platform
    key = uuid4()
    with ThreadPoolExecutor(2) as pool:
        created = list(pool.map(lambda _: h.client.start("Race", key), range(2)))
    assert created[0] == created[1]
    assert len(h.conversations._conversations) == 1
    cid, body = created[0]["id"], turn()
    h.llm.hold = True
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(h.client.ask, cid, body)
        assert h.started.wait(3)
        assert h.client.status(cid, body["idempotency_key"])["state"] == "in_progress"
        with pytest.raises(APIError) as conflict:
            h.client.ask(cid, body)
        assert conflict.value.status == 409
        h.release.set()
        assert pending.result()["status"] == "completed"
    assert len(h.llm.requests) == 1


def test_lost_terminal_reconciles_original_key_after_client_restart(http_platform, tmp_path):
    h = http_platform
    cid, body = h.client.start("Lost ack", uuid4())["id"], turn()
    journal = Logbook(tmp_path / "logbook.db")
    journal.add("Local book", "PRIVATE LOCAL NOTE")
    journal.remember("scope", body["idempotency_key"], "turn", cid, body)
    with h.client.request("POST", f"/v1/conversations/{cid}/continue", body) as response:
        wire = response.read()
    # Response completed server-side but consumer never observed its terminal.
    assert b"response.completed" in wire
    with pytest.raises(UncertainTurn):
        read_completion([wire.split(b"event: response.completed")[0]])
    journal.db.close()
    restarted = Logbook(tmp_path / "logbook.db")
    operation = restarted.operation("scope", body["idempotency_key"])
    assert operation["state"] == "unknown" and operation["body"] == body
    assert h.client.status(cid, body["idempotency_key"])["state"] == "completed"
    result = h.client.ask(cid, operation["body"])
    restarted.completed("scope", body["idempotency_key"], result)
    assert restarted.operation("scope", body["idempotency_key"])["state"] == "completed"
    assert len(h.llm.requests) == 1
    assert all("PRIVATE LOCAL NOTE" not in m.content for request in h.llm.requests for m in request)
    with pytest.raises(ValueError):
        restarted.remember(
            "scope", body["idempotency_key"], "turn", cid, {**body, "content": "changed"}
        )
    restarted.db.close()


@pytest.mark.parametrize("failure", ["partial", "provider"])
def test_failed_stream_is_never_resent(http_platform, failure):
    h = http_platform
    cid, body = h.client.start("Failure", uuid4())["id"], turn()
    if failure == "partial":
        h.llm.include_terminal = False
    else:
        h.llm.terminal_status = "failure"
    with pytest.raises(UncertainTurn):
        h.client.ask(cid, body)
    assert h.client.status(cid, body["idempotency_key"])["state"] == "unknown"
    with pytest.raises(APIError) as conflict:
        h.client.ask(cid, body)
    assert conflict.value.status == 409 and len(h.llm.requests) == 1


def test_abrupt_disconnect_never_resends(http_platform):
    h = http_platform
    cid, body = h.client.start("Disconnect", uuid4())["id"], turn()
    h.llm.hold = True
    with h.raw.stream(
        "POST", f"/v1/conversations/{cid}/continue", json=body, headers=h.headers
    ) as response:
        for line in response.iter_lines():
            if line == "event: response.delta":
                break
    h.release.set()
    deadline = time.monotonic() + 3
    while (
        h.client.status(cid, body["idempotency_key"])["state"] == "in_progress"
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)
    with pytest.raises(APIError) as conflict:
        h.client.ask(cid, body)
    assert conflict.value.status == 409 and len(h.llm.requests) == 1


def test_storage_unavailable_is_safe(http_platform, monkeypatch):
    h = http_platform
    monkeypatch.setattr(
        h.conversations,
        "create",
        lambda *_: (_ for _ in ()).throw(StorageUnavailableError("PRIVATE")),
    )
    response = h.raw.post(
        "/v1/conversations",
        headers=h.headers,
        json={"idempotency_key": str(uuid4())},
    )
    assert response.status_code == 503 and "PRIVATE" not in response.text
    assert not h.llm.requests


def test_rate_limit_and_identity_outage_are_safe(http_platform, monkeypatch):
    from google.auth.exceptions import TransportError

    from personal_ai.auth import middleware
    from personal_ai.auth.safeguards import InMemorySafeguardStore, SafeguardDenied

    h = http_platform
    h.app.state.safeguard_store = InMemorySafeguardStore()
    monkeypatch.setattr(
        middleware._request_admission,
        "check_request",
        lambda *_: (_ for _ in ()).throw(SafeguardDenied("rate_limit_exceeded", retry_after=7)),
    )
    response = h.raw.post("/v1/conversations", headers=h.headers, json={})
    assert response.status_code == 429 and response.headers["retry-after"] == "7"
    verification._verified_tokens.clear()

    @contextmanager
    def outage():
        raise TransportError("SYNTHETIC PRIVATE DETAIL")
        yield

    monkeypatch.setattr(verification, "signing_key_request", outage)
    response = h.raw.post("/v1/conversations", headers=h.headers, json={})
    assert response.status_code == 503 and "PRIVATE" not in response.text
    assert not h.llm.requests


def test_separate_cli_process_and_local_data_ownership(http_platform, tmp_path):
    import subprocess
    import sys

    h = http_platform
    token_file = tmp_path / "token"
    token_file.write_text(h.headers["Authorization"][7:])
    token_file.chmod(0o600)
    python = os.environ.get("PI2_CLIENT_PYTHON", sys.executable)
    runner = os.environ.get(
        "PI2_CLIENT_RUNNER",
        str(Path(__file__).resolve().parents[2] / "backend/scripts/pi2_client_probe.py"),
    )
    command = [
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
    ]
    # Source checks use source paths explicitly for this subprocess; artifact
    # acceptance supplies an empty-environment client-only interpreter instead.
    env = {"PATH": os.environ.get("PATH", ""), "PYTHONDONTWRITEBYTECODE": "1"}
    if not os.environ.get("PI2_CLIENT_PYTHON"):
        import reading_logbook

        env["PYTHONPATH"] = str(Path(reading_logbook.__file__).parents[1])

    def run(*args):
        completed = subprocess.run(
            [*command, *args],
            env=env,
            cwd=tmp_path,
            capture_output=True,
            text=True,
            timeout=10,
            check=False,
        )
        assert completed.returncode == 0, completed.stderr
        assert "PI2_CLIENT_FORBIDDEN_NETWORK_ATTEMPTS=0" in completed.stderr
        return json.loads(completed.stdout.strip().splitlines()[-1])

    run("add", "Local title", "--note", "LOCAL ONLY DO NOT UPLOAD")
    assert len(run("books")) == 1
    cid = run("start", "CLI conversation", "--key", str(uuid4()))["id"]
    assert run("preview", cid, "Explicit message")["selected_message_count"] == 0
    key = str(uuid4())
    assert run("ask", cid, "Explicit message", "--key", key)["status"] == "completed"
    assert run("recover", key)["status"] == "completed"
    assert len(run("list")["conversations"]) == 1
    assert len(run("get", cid)["messages"]) == 2
    assert len(h.llm.requests) == 1
    assert all("LOCAL ONLY" not in m.content for request in h.llm.requests for m in request)


def test_invalid_signature_and_unsigned_bearer_denied(http_platform):
    h = http_platform
    header, payload, signature = h.token().split(".")
    forged_signature = ("A" if signature[0] != "A" else "B") + signature[1:]
    unsigned = jwt.encode(
        {"aud": "logbook-oauth-client", "sub": "synthetic-owner"}, key="", algorithm="none"
    )
    for token in (f"{header}.{payload}.{forged_signature}", unsigned):
        response = h.raw.post(
            "/v1/conversations", headers={**h.headers, "Authorization": "Bearer " + token}, json={}
        )
        assert response.status_code == 401
    assert not h.llm.requests and not h.conversations._conversations


def test_client_timeout_retains_original_key_and_never_resends(http_platform):
    h = http_platform
    cid, body = h.client.start("Timeout", uuid4())["id"], turn()
    h.llm.hold = True
    impatient = PlatformClient(
        h.client.base_url, h.client.token, "shelf", allow_loopback=True, timeout=0.1
    )
    with pytest.raises(UncertainTurn):
        impatient.ask(cid, body)
    h.release.set()
    deadline = time.monotonic() + 3
    while (
        h.client.status(cid, body["idempotency_key"])["state"] == "in_progress"
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)
    with pytest.raises(APIError) as conflict:
        h.client.ask(cid, body)
    assert conflict.value.status == 409 and len(h.llm.requests) == 1


def test_pi4_signed_http_profile_consent_installed_unrelated_consumer(http_platform):
    """Real JWT/middleware, installed host/client and production assembler DI."""
    from datetime import UTC, datetime, timedelta

    from personal_ai.context.profile import InMemoryGlobalProfileRepository

    h = http_platform
    settings = h.app.dependency_overrides[get_settings]().model_copy(update={"profile_sharing_enabled": True})
    profile = InMemoryGlobalProfileRepository()
    h.app.dependency_overrides[get_settings] = lambda: settings
    h.app.dependency_overrides[deps.get_global_profile_repository] = lambda: profile
    h.app.dependency_overrides[deps.get_provider_usage_accounting] = lambda: None
    h.app.dependency_overrides[deps.get_context_research_repository] = lambda: None
    h.app.dependency_overrides.pop(deps.get_context_assembler)
    ui = {"Authorization": "Bearer " + h.token(aud="builtin-web-client", azp="builtin-web-client")}
    response = h.raw.put("/v1/profile", headers=ui, json={"fields": [
        {"field": "preferred_units", "value": "metric"},
        {"field": "locale", "value": "en-GB"},
    ]})
    assert response.status_code == 200, response.text
    body = {
        "operation_id": str(uuid4()), "operation": "grant", "grant_id": str(uuid4()),
        "expected_revision": 0, "expected_profile_revision": 1, "field": "preferred_units",
        "destination": {"application_id": "reading_logbook", "workspace_id": "shelf"},
        "purpose": "assist_response", "expires_at": (datetime.now(UTC) + timedelta(hours=1)).isoformat(),
    }
    assert h.raw.post("/v1/profile/shares", headers={**h.headers, "If-Match": '"0"'}, json=body).status_code == 403
    assert h.raw.post("/v1/profile/shares", headers={**ui, "If-Match": '"0"'}, json=body).status_code == 200
    cid = h.client.start("PI4 independent reader", uuid4())["id"]
    request = turn("What units do I prefer?")
    h.client.ask(cid, request)
    assert "metric" in " ".join(m.content for m in h.llm.requests[0])
    assert "en-GB" not in " ".join(m.content for m in h.llm.requests[0])
    revoked = {**body, "operation_id": str(uuid4()), "operation": "revoke", "expected_revision": 1}
    assert h.raw.post("/v1/profile/shares", headers={**ui, "If-Match": '"1"'}, json=revoked).status_code == 200
    # Original completed key cannot disclose the old answer or trigger another send.
    with pytest.raises((APIError, UncertainTurn)):
        h.client.ask(cid, request)
    assert len(h.llm.requests) == 1
    h.client.ask(cid, turn("Please continue"))
    assert "metric" not in " ".join(m.content for m in h.llm.requests[-1])
    assert len(h.llm.requests) == 2

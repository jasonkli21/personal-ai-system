"""Exercise independently installed clients over one fenced numeric loopback listener."""

# ruff: noqa: F811 - pytest imports fixtures by name
import json
import os
import socket
import sys
from contextlib import contextmanager
from importlib.metadata import version
from pathlib import Path
from threading import Thread
from time import monotonic, sleep
from uuid import uuid4

import pytest
import uvicorn
from fastapi.testclient import TestClient

from personal_ai.api.private_application_plan import PROFILE_PREFIX
from personal_ai.local_bridge.http import create_loopback_app
from personal_ai.main import create_app
from personal_ai.settings import get_settings
from tests.app_context_support.application_plan import plan_request
from tests.app_context_support.shared import FITNESS_APP, READING_APP, TRAVEL_APP
from tests.test_application_plan_inference import (
    FITNESS_MEMORY,
    READING_MEMORY,
    assert_delivery,
    plan_factory,  # noqa: F401 - pytest fixture
    travel,
)
from tests.test_chatgpt_bridge_transport import bridge_fixture
from tests.test_shared_application_service import (
    SECRET_TITLE,
    B,
    body,
    provision,
    shared_factory,  # noqa: F401 - pytest fixture
)

pytestmark = [
    pytest.mark.loopback_http,
    pytest.mark.skipif(
        os.environ.get("APP_PLAN_SDK_VERSION") not in {"0.1.0", "0.2.0"},
        reason="requires an independently installed application SDK",
    ),
]
IP = "127.0.0.1"
LEGACY_HEADER = {"X-PAS-User-Plan": "1"}


@pytest.fixture
def listen():
    """Allow binds for our one listener and connects only to its assigned address."""
    assert not Path(".env").exists() and not Path("backend/.env").exists()
    active = False
    local = None
    listener = None
    denied = []

    def audit(event, args):
        if not active:
            return
        if event == "socket.bind":
            allowed = args[0] is listener and args[1] == (IP, 0) and local is None
        elif event == "socket.getaddrinfo":
            allowed = args[:2] == local
        elif event == "socket.connect":
            allowed = args[1] == local
        else:
            allowed = event not in {
                "socket.sendto",
                "socket.sendmsg",
                "socket.gethostbyname",
                "socket.gethostbyname_ex",
                "socket.gethostbyaddr",
                "socket.getnameinfo",
            }
        if not allowed:
            denied.append(event)
            raise PermissionError("private application test network fence")

    sys.addaudithook(audit)

    @contextmanager
    def start(app):
        nonlocal active, local, listener
        with socket.socket() as listener:
            active = True
            try:
                listener.bind((IP, 0))
                local = listener.getsockname()
                listener.listen()
                server = uvicorn.Server(
                    uvicorn.Config(
                        app,
                        lifespan="off",
                        loop="asyncio",
                        http="h11",
                        ws="none",
                        access_log=False,
                        proxy_headers=False,
                        log_level="error",
                    )
                )
                thread = Thread(target=server.run, kwargs={"sockets": [listener]}, daemon=True)
                thread.start()
                try:
                    deadline = monotonic() + 5
                    while not server.started and thread.is_alive() and monotonic() < deadline:
                        sleep(0.01)
                    assert server.started
                    yield f"http://{IP}:{local[1]}", denied
                finally:
                    server.should_exit = True
                    thread.join(5)
                    assert not thread.is_alive()
            finally:
                active = False
                local = None

    yield start
    assert denied == []


def client_for(origin, target):
    import personal_ai_sdk

    assert (
        Path(personal_ai_sdk.__file__)
        .resolve()
        .is_relative_to(Path(os.environ["SHARED_SERVICE_SDK_SITE"]).resolve())
    )
    return personal_ai_sdk.Client(
        origin,
        target.token,
        application=target.app.app,
        workspace=target.workspace,
        allow_loopback=True,
        timeout=5,
    )


def test_installed_profile_three_contributions_and_foreign_owner(plan_factory, listen, caplog):
    from personal_ai_sdk import (
        APIError,
        ApplicationPlan,
        CapabilityUnavailable,
    )

    host = plan_factory(selected=(TRAVEL_APP, FITNESS_APP, READING_APP))
    trip = travel(host)
    workout = host.plan.onboard(
        provision(host, FITNESS_APP, B, grant=False),
        memory_content=FITNESS_MEMORY,
    )
    book = host.plan.onboard(
        provision(host, READING_APP, grant=False),
        memory_content=READING_MEMORY,
    )
    foreign = host.plan.onboard(
        provision(host, TRAVEL_APP, B, grant=False),
        memory_content=FITNESS_MEMORY,
    )
    with listen(host.app) as (origin, _):
        assert version("personal-ai-sdk") == "0.2.0"
        for target in (trip, workout, book):
            client = client_for(origin, target)
            with pytest.raises(CapabilityUnavailable):
                ApplicationPlan(client, profile_version=2)
            profile = ApplicationPlan(client)
            cid = client.create("Private app", uuid4())["id"]
            source = host.sources[target.app.source]
            reads = source.counts["exchange"]
            request = plan_request()
            preview = profile.preview(cid, request)
            assert preview["destination"]["application"] == target.app.app
            assert preview["selected_context"][0] == {
                "category": "conversation_history",
                "turns": 0,
            }
            assert source.counts["exchange"] == reads + 2
            assert target.local_payloads == target.provider.sends() == []
            assert SECRET_TITLE not in json.dumps(preview)
            if target is trip:
                other_client = client_for(origin, foreign)
                with pytest.raises((APIError, CapabilityUnavailable)):
                    ApplicationPlan(other_client).preview(cid, request)
                assert source.counts["exchange"] == reads + 2
            confirmed = plan_request(request["idempotency_key"], preview["confirmation"])
            complete = profile.continue_turn(cid, confirmed)
            assert complete["content"] == "A streamed answer"
            assert client.status(cid, request["idempotency_key"])["message_id"] == complete["id"]
            assert profile.continue_turn(cid, confirmed) == complete
            if target is trip:
                for denied_id in (cid, uuid4()):
                    with pytest.raises(APIError) as status_error:
                        other_client.status(denied_id, request["idempotency_key"])
                    with pytest.raises(APIError) as detail_error:
                        other_client.detail(denied_id)
                    for error in (status_error, detail_error):
                        assert (error.value.status, error.value.code) == (404, "not_found")
                assert foreign.local_payloads == foreign.provider.sends() == []
            assert source.counts["exchange"] == reads + 2
            assert_delivery(target, (str(target.data[target.app.fields[0]]),), (SECRET_TITLE,))
            assert target.token not in caplog.text

    print("PRIVATE_PROFILE counters: 3 packages, 3 sends, 0 foreign disclosures")


def test_private_profile_listener_denies_external_dns(listen):
    from personal_ai_sdk import Client, UncertainTurn

    async def no_requests(scope, receive, send):
        raise AssertionError("denial probe reached the application")

    with listen(no_requests) as (_, denied):
        with pytest.raises(UncertainTurn):
            Client("https://egress-self-test.invalid", "synthetic", application="reading").list()
        assert denied == ["socket.getaddrinfo"]
        denied.clear()
    print("PRIVATE_PROFILE_DENIED_DNS_ATTEMPTS=1")


@pytest.mark.parametrize("continue_status", [200, 429])
def test_lost_create_and_continue_recover_under_original_binding(
    plan_factory, listen, tmp_path, continue_status,
):
    from personal_ai_sdk import APIError, ApplicationPlan, UncertainTurn

    host = plan_factory()
    target = travel(host)
    lose = {"/v1/conversations": True, "continue": True}
    received = []
    hide_status = True

    async def reply(send, status, media=b"application/json", body=b""):
        await send(
            {"type": "http.response.start", "status": status, "headers": [(b"content-type", media)]}
        )
        await send({"type": "http.response.body", "body": body})

    async def interrupt(scope, receive, send):
        nonlocal hide_status
        path = scope["path"]
        received.append((scope["method"], path))
        if scope["method"] == "GET" and "/continuations/" in path and hide_status:
            hide_status = False
            await reply(send, 200, body=b'{"state":"not_found","message_id":null}')
            return
        key = "continue" if path.endswith("/continue") else path
        if scope["method"] != "POST" or not lose.pop(key, False):
            await host.app(scope, receive, send)
            return

        async def discard(_frame):
            pass

        await host.app(scope, receive, discard)
        media = b"text/event-stream" if key == "continue" else b"application/json"
        await reply(send, continue_status if key == "continue" else 200, media)

    journal_path = tmp_path / "caller.json"

    def persist(journal):
        pending = journal_path.with_suffix(".pending")
        fd = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(journal, stream)
            stream.flush()
            os.fsync(stream.fileno())
        pending.replace(journal_path)
        directory = os.open(tmp_path, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)

    with listen(interrupt) as (origin, _):
        binding = {
            "target": origin,
            "application": target.app.app,
            "workspace": target.workspace,
            "owner": target.plan.scope.owner_id,
            "actor": target.plan.scope.actor_id,
            "client": target.plan.scope.client_namespace,
        }

        def bound_client(journal):
            if any(journal.get(field) != value for field, value in binding.items()):
                raise ValueError("journal_binding_changed")
            return client_for(journal["target"], target)

        journal = {
            **binding,
            "create_key": str(uuid4()),
            "title": "Recoverable conversation",
        }
        caller = bound_client(journal)
        persist(journal)
        with pytest.raises(UncertainTurn):
            caller.create(journal["title"], journal["create_key"])
        journal = json.loads(journal_path.read_text())
        before_recovery = list(received)
        for field in binding:
            with pytest.raises(ValueError, match="journal_binding_changed"):
                bound_client(journal | {field: "foreign"})
        assert received == before_recovery
        caller = bound_client(journal)
        cid = caller.create(journal["title"], journal["create_key"])["id"]
        assert len(caller.list()["conversations"]) == 1
        request = plan_request()
        journal.update(conversation_id=cid, preview=request)
        persist(journal)
        preview = ApplicationPlan(caller).preview(cid, request)
        journal["continuation"] = plan_request(request["idempotency_key"], preview["confirmation"])
        persist(journal)
        with pytest.raises(APIError if continue_status == 429 else UncertainTurn) as interrupted:
            ApplicationPlan(caller).continue_turn(cid, journal["continuation"])
        if continue_status == 429:
            assert interrupted.value.status == 429
        journal = json.loads(journal_path.read_text())
        assert target.token not in journal_path.read_text()
        caller = bound_client(journal)
        key = journal["preview"]["idempotency_key"]
        assert key == journal["continuation"]["idempotency_key"]
        assert caller.status(journal["conversation_id"], key)["state"] == "not_found"
        status = caller.status(journal["conversation_id"], key)
        assert status["state"] == "completed"
        message = next(
            msg for msg in caller.detail(cid)["messages"] if msg["id"] == status["message_id"]
        )
        assert message["status"] == "completed" and message["content"] == "A streamed answer"
        assert received[-3:] == [
            ("GET", f"/v1/conversations/{cid}/continuations/{key}"),
            ("GET", f"/v1/conversations/{cid}/continuations/{key}"),
            ("GET", f"/v1/conversations/{cid}"),
        ]
        assert [path.rsplit("/", 1)[-1] for method, path in received if method == "POST"] == [
            "conversations", "conversations", "context-preview", "continue",
        ]
    assert len(target.local_payloads) == len(target.provider.sends()) == 1


def test_private_routes_absent_and_new_extension_refuses_old_server(
    shared_factory, listen, tmp_path
):
    from personal_ai_sdk import ApplicationPlan, CapabilityUnavailable

    host = shared_factory()
    target = provision(host)
    received = []

    async def tap(scope, receive, send):
        received.append((scope["method"], scope["path"]))
        await host.app(scope, receive, send)

    with listen(tap) as (origin, _):
        client = client_for(origin, target)
        cid = client.create("Old server", uuid4())["id"]
        with pytest.raises(CapabilityUnavailable):
            ApplicationPlan(client).preview(cid, plan_request())
        assert received[-1] == ("POST", f"{PROFILE_PREFIX}/{cid}/context-preview")
        assert len(received) == 2
        assert host.generation.sends == []

    normal = create_app(selected_contributions=())
    normal.dependency_overrides[get_settings] = lambda: host.settings
    with TestClient(normal, base_url="http://testserver") as http:
        assert (
            http.post(f"{PROFILE_PREFIX}/{cid}/continue", headers=LEGACY_HEADER).status_code == 404
        )
        assert (
            http.post(
                f"/private/application-plan/v2/conversations/{cid}/context-preview",
                headers=LEGACY_HEADER,
            ).status_code
            == 404
        )

    bridge, provider, session, *_ = bridge_fixture(tmp_path)
    standalone = create_loopback_app(bridge, port=8765)
    headers = LEGACY_HEADER | {
        "Origin": session.origin,
        "X-Bridge-Authorization": session.authorization,
    }
    with TestClient(standalone, base_url=f"http://{IP}:8765", client=(IP, 1234)) as http:
        assert http.post(f"{PROFILE_PREFIX}/{cid}/continue", headers=headers).status_code == 404
        assert (
            http.post(
                f"/v1/conversations/{cid}/continue",
                headers=headers,
                json=plan_request(),
            ).status_code
            == 404
        )
    assert provider.sends() == []


def test_legacy_wheel_retains_automatic_consumer_path(plan_factory, listen):
    if os.environ.get("APP_PLAN_SDK_VERSION") != "0.1.0":
        pytest.skip("run against the pinned legacy wheel")
    host = plan_factory()
    target = provision(host)
    with listen(host.app) as (origin, _):
        client = client_for(origin, target)
        cid = client.create("Automatic", uuid4())["id"]
        assert client.continue_turn(cid, body())["status"] == "completed"
    assert len(host.generation.sends) == 1


def test_private_profile_denials_precede_protected_reads(plan_factory, listen):
    import httpx

    host = plan_factory()
    target = travel(host)
    with listen(host.app) as (origin, _), httpx.Client(base_url=origin, trust_env=False) as http:
        client = client_for(origin, target)
        cid = client.create("Protected reads", uuid4())["id"]
        source = host.sources[target.app.source]
        original = source.counts.copy()
        path = f"{PROFILE_PREFIX}/{cid}/context-preview"
        request = plan_request()
        for credentials in (
            {},
            {"X-User-ID-Token": target.token},
            {"Authorization": "Bearer unknown-token"},
            {"Authorization": f"Bearer {host.token(target.app, azp='other-client')}"},
            {"Authorization": f"Bearer {host.token(target.app, iss='https://wrong.invalid')}"},
            target.headers | {"X-Owner-ID": "caller-chosen"},
            target.headers | {"X-Workspace-ID": "wrong-workspace"},
        ):
            headers = {"X-Application-ID": target.app.app} | credentials
            assert http.post(path, headers=headers, json=request).status_code in {400, 401, 403}

        assert (
            http.post(path, headers=target.headers, json=request | {"actor_id": "a"}).status_code
            == 422
        )
        assert (
            http.post(
                path,
                headers=target.headers,
                json=request
                | {
                    "choice": {"mode": "user_owned_plan", "confirmation": None},
                },
            ).status_code
            == 422
        )
        assert (
            http.post(
                path,
                headers=target.headers | {"Content-Type": "application/json"},
                content=b'{"content":"first","content":"second"}',
            ).status_code
            == 422
        )
        assert http.post(path, headers=target.headers, content=b"x" * 131073).status_code == 413
        assert (
            http.post(
                path,
                json=request,
                headers=[
                    *target.headers.items(),
                    ("Content-Type", "application/json"),
                    ("Content-Type", "text/plain"),
                ],
            ).status_code
            == 422
        )
        assert (
            http.post(path + "?profile=v2", headers=target.headers, json=request).status_code == 422
        )
        ordinary = f"/v1/conversations/{cid}/context-preview"
        assert (
            http.post(ordinary, headers=target.headers | LEGACY_HEADER, json=request).status_code
            == 422
        )
        assert (
            http.post(
                path.replace("/v1/", "/v2/"), headers=target.headers, json=request
            ).status_code
            == 404
        )
        assert source.counts == original
        assert target.local_payloads == target.provider.sends() == []


def test_installed_profile_rejects_malformed_response_and_request(
    plan_factory, listen, monkeypatch
):
    from personal_ai_sdk import ApplicationPlan, UncertainTurn

    host = plan_factory()
    target = travel(host)
    cid = str(uuid4())
    post_paths = []
    reply = {"media": b"application/json", "body": b"{}", "status": 200}

    async def stub(scope, receive, send):
        post_paths.append(scope["path"])
        await send(
            {
                "type": "http.response.start",
                "status": reply["status"],
                "headers": [(b"content-type", reply["media"])],
            }
        )
        await send({"type": "http.response.body", "body": reply["body"]})

    with listen(stub) as (origin, _):
        monkeypatch.setenv("http_proxy", "http://forbidden-proxy.invalid:80")
        monkeypatch.setenv("no_proxy", "")
        plan = ApplicationPlan(client_for(origin, target))
        preview = plan_request()
        with pytest.raises(ValueError, match="invalid_plan_request"):
            plan.preview(cid, preview | {"unexpected": True})
        with pytest.raises(ValueError, match="invalid_plan_confirmation"):
            plan.continue_turn(cid, plan_request(confirmation="bogus"))
        assert post_paths == []

        for media, raw in [
            (b"text/plain", b"{}"),
            (b"application/json", b"{}" + b" " * 8192),
            (b"application/json", b'{"purpose":"one","purpose":"two"}'),
            (b"application/json", b'{"confirmation":'),
        ]:
            reply.update(media=media, body=raw)
            with pytest.raises(UncertainTurn):
                plan.preview(cid, preview)

        intended = plan_request(confirmation="a" * 64)
        for raw in [
            b'event: response.delta\ndata: {"x":',
            b"event: response.delta\ndata: " + b"x" * 262145 + b"\n\n",
            b"",
        ]:
            reply.update(media=b"text/event-stream", body=raw)
            with pytest.raises(UncertainTurn):
                plan.continue_turn(cid, intended)
        assert all(path.startswith(PROFILE_PREFIX) for path in post_paths)
        assert target.local_payloads == target.provider.sends() == []

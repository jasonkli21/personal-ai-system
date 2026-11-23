"""PAS-only synthetic seam tests. No Travel/Health product process is started."""

# ruff: noqa: F811 - pytest imports fixtures by their parameter names

import base64
import hmac
import http.client
import json
import multiprocessing
from concurrent.futures import ThreadPoolExecutor
from contextlib import nullcontext
from dataclasses import replace
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from threading import Barrier
from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from fastapi import FastAPI
from fastapi.testclient import TestClient

from personal_ai.api import dependencies as deps
from personal_ai.api.private_application_plan import PROFILE_PREFIX, mount_application_plan
from personal_ai.contracts.private_dispatch import (
    MEDIA_TYPE,
    ORIGINAL_KEY_HEADER,
    RECEIPT_HEADER,
    VERSION,
    Binding,
    Confirmation,
    PreviewClaims,
    TerminalClaims,
    canonical,
    parse,
    verify,
    wire_digest,
)
from personal_ai.local_bridge.private_dispatch import LoopbackReceiver, RuntimeDispatch
from personal_ai.main import create_app
from personal_ai.services.external_turns.dispatch_journal import SyntheticDispatchJournal
from personal_ai.services.external_turns.private_dispatch import (
    CreateBinding,
    CurrentSource,
    DispatchDenied,
    DispatchRegistration,
    DispatchUnavailable,
    PrivateDispatch,
)
from tests.app_context_support.application_plan import plan_request
from tests.app_context_support.health_receipts import KEY_ID, decode, receipt_fields
from tests.test_health_plan_preview import (
    configure_preview,
    create,
    prepare,
    receive,
    setup,  # noqa: F401 - pytest fixture
)

VECTORS = {
    "travel": "1dd87ee2e4a64fcae8f7c43146a8cc3752bce283d8bd4efb6a7460f40fc66a1f",
    "health": "45fac57b1b5301b62efa20a247888fe183db25736393b384c5a063ce12a05676",
}


def public_key(value):
    return Ed25519PublicKey.from_public_bytes(base64.urlsafe_b64decode(value + "="))


@pytest.mark.parametrize("app", VECTORS)
def test_frozen_transcript(app):
    text = (Path(__file__).parent / "fixtures" / f"private-dispatch-{app}.txt").read_bytes()
    assert wire_digest(text) == VECTORS[app]
    keys, payload, binding, preview, confirmation, terminal, signature = text.splitlines()
    pas, runtime = map(public_key, json.loads(keys))
    bound = parse(binding, Binding)
    body = parse(confirmation, Confirmation)
    assert canonical(bound) == binding and bound.app == app
    claims = verify(
        pas, body.preview_sig, preview, PreviewClaims, issuer="pas-fixture",
        audience=app, kid="p1", now=1000,
    )
    assert body.confirmation == wire_digest(preview)
    assert claims.binding_sha256 == wire_digest(binding)
    assert claims.payload_sha256 == wire_digest(payload)
    assert claims.payload_sha256 != wire_digest(payload + b" ")
    completed = verify(
        runtime, signature.decode(), terminal, TerminalClaims, issuer="runtime-fixture",
        audience="pas-fixture", kid="r1", now=1000,
    )
    assert (completed.root, completed.attempt, body.original_key) == (
        bound.root, bound.attempt, bound.original_key,
    )
    assert completed.body_sha256 == wire_digest(confirmation)
    assert completed.result_sha256 == wire_digest(b"ok")
    with pytest.raises(ValueError):
        verify(
            pas, body.preview_sig, preview, PreviewClaims, issuer="pas-fixture",
            audience=app, kid="p1", now=1060,
        )


@pytest.mark.parametrize("change", [
    lambda base: base + b"\n",
    lambda base: b"\xef\xbb\xbf" + base,
    lambda base: base.replace(b'"confirmation":', b'"extra":1,"confirmation":'),
    lambda base: base.replace(b'"confirmation":', b'"confirmation":null,"confirmation":'),
    lambda base: base.replace(b'pas-dispatch/1', b'pas-dispatch/2'),
])
def test_confirmation_requires_exact_canonical_closed_input(change):
    text = (Path(__file__).parent / "fixtures/private-dispatch-health.txt").read_bytes()
    raw = text.splitlines()[4]
    assert parse(raw, Confirmation).v == VERSION
    with pytest.raises(ValueError):
        parse(change(raw), Confirmation)


def receiver_worker(pipe, key, outcome):
    class Receiver(BaseHTTPRequestHandler):
        def log_message(self, _format, *args):
            pass

        def do_POST(self):
            raw = self.rfile.read(int(self.headers["Content-Length"]))
            pipe.send((self.path, raw))
            if outcome == "disconnect":
                self.close_connection = True
                return
            attempt = self.headers["X-PAS-Attempt"]
            response = canonical({
                "attempt": str(uuid4()) if outcome == "wrong-attempt" else attempt,
                "payload_sha256": wire_digest(raw),
                "result": "ok",
                "usage": 1 if outcome == "nonzero-usage" else 0,
            })
            self.send_response(200)
            self.send_header("content-length", str(len(response)))
            self.send_header("x-fixture-signature", key.sign(response).hex())
            self.end_headers()
            self.wfile.write(response)

    with HTTPServer(("127.0.0.1", 0), Receiver) as server:
        pipe.send(server.server_port)
        server.serve_forever()


@pytest.fixture
def receiver(monkeypatch):
    context = multiprocessing.get_context("fork")
    children = []
    issued = []
    send = http.client.HTTPConnection.request

    def capture(connection, method, url, body=None, headers=None, **kwargs):
        issued.append((connection.host, method, url, body))
        return send(connection, method, url, body=body, headers=headers, **kwargs)

    monkeypatch.setattr(http.client.HTTPConnection, "request", capture)

    def start(outcome="ok"):
        read, write = context.Pipe(duplex=False)
        key = Ed25519PrivateKey.generate()
        child = context.Process(target=receiver_worker, args=(write, key, outcome), daemon=True)
        child.start()
        children.append((child, read, write))
        assert read.poll(3), "receiving fixture did not start"
        return LoopbackReceiver(read.recv(), key.public_key()), read, issued

    yield start
    for child, read, write in children:
        child.terminate()
        child.join(3)
        read.close()
        write.close()


def install(host, transport, tmp_path, *, registered_receipts=False):
    from personal_ai.contracts.private_dispatch import Destination

    dependencies = {}
    creates = {}
    gates = {"continuity": True, "denied": None, "changed": None, "clock_offset": 0}
    phases = []
    preview_key = Ed25519PrivateKey.generate()
    release_key = Ed25519PrivateKey.generate()
    paired = host.target.plan.runtime._bridge.installation
    runtime = RuntimeDispatch(
        destination=Destination(
            account=paired.registration_binding, connection=str(paired.connection_id),
            endpoint="loopback-fixture", model="fake", provider="fake",
            revision=paired.connection_revision, runtime=str(paired.runtime_id),
        ),
        receiver=transport,
        pas_issuer="pas-test", release_kid="release", release_key=release_key.public_key(),
        issuer="runtime-test", terminal_kid="terminal", terminal_key=Ed25519PrivateKey.generate(),
    )
    def now():
        return int(host.now.timestamp()) + gates["clock_offset"]

    secret = b"synthetic-test-commitments"

    def current(binding, phase, nonce):
        phases.append((phase, nonce))
        if callable(gates["changed"]):
            gates["changed"](phase)
        # The other side owns its own wire reader and returns a plain object.
        assert canonical(parse(binding, Binding)) == binding
        return {
            "binding_sha256": wire_digest(binding), "phase": phase, "nonce": nonce,
            "current": phase != gates["denied"] and bool(host.current),
            "expires": now() + 5,
        }

    def commitments(frozen):
        dependencies[str(frozen.original_key)] = frozen
        domain = next(s for s in frozen.snapshots if s.provider_id != "ai_memory")
        memory = next(s for s in frozen.snapshots if s.provider_id == "ai_memory")
        return tuple(
            hmac.digest(secret, canonical(s.model_dump(mode="json")), "sha256").hex()
            for s in (domain, memory)
        )

    def verify_legacy_header(receipt, frozen):
        body, sig = (decode(item) for item in receipt.split("."))
        host.verify_keys[KEY_ID].verify(sig, body)
        claims = json.loads(body)
        assert claims["response_digest"] == wire_digest(frozen.attested_body)
        return claims["exp"]

    registration = DispatchRegistration(
        host.target.plan, "fixture-tenant", str(host.enrollment.installation_id), runtime,
        CurrentSource(current),
        verified_create=lambda conversation, key: creates.get(conversation),
        source_commitments=commitments,
        verified_preview_expiry=verify_legacy_header,
        load_dependencies=lambda binding: dependencies.get(binding.original_key),
        trust_current=lambda: True,
        receipt_authority=host.authority if registered_receipts else None,
    )
    dispatch = PrivateDispatch(
        plans=host.fixture.service, journal=SyntheticDispatchJournal(tmp_path / "journal"),
        registrations=(registration,), issuer="pas-test", preview_kid="preview",
        preview_key=preview_key, release_key=release_key,
        continuity_current=lambda: gates["continuity"], clock=now,
    )
    for route in host.app.state.private_application_plan_routes:
        host.app.router.routes.remove(route)
    host.app.state.private_application_plan_routes = ()
    host.fixture.mount(
        bound_receipts=None if registered_receipts else host.authority, dispatch=dispatch,
    )
    return dispatch, creates, gates, phases


def pending(host, client, creates):
    create_key = uuid4()
    first, operation, _ = create(host, client, create_key)
    cid = UUID(first.json()["conversation_id"])
    auth = receive(host, first, receipt_fields(operation, cid, first.content, 0))
    creates[cid] = CreateBinding(
        key=create_key, receipt=first.headers["x-application-plan-receipt"],
        epoch=1, expires=auth["exp"],
    )
    branch = configure_preview(host, cid)
    raw = plan_request()
    operation, headers = prepare(host, raw, cid=cid, create_key=create_key, branch=branch)
    reply = client.post(
        operation.path, headers={**headers, "content-type": MEDIA_TYPE}, content=canonical(raw),
    )
    assert reply.status_code == 200, (reply.status_code, reply.text, host.reverse.calls)
    envelope = json.loads(reply.headers[RECEIPT_HEADER])
    assert reply.headers["content-type"] == MEDIA_TYPE
    destination = reply.json()["destination"]
    installation = host.target.plan.runtime._bridge.installation
    assert destination == {
        "application": "health", "provider": "fake", "model": "fake",
        "runtime": f"local:{installation.runtime_id}",
        "recipient": f"openai-responses:{installation.registration_binding}",
    }
    request = canonical({
        "confirmation": wire_digest(canonical(envelope["claims"])),
        "original_key": raw["idempotency_key"], "preview_sig": envelope["signature"], "v": VERSION,
    })
    post = f"{PROFILE_PREFIX}/{cid}/continue"
    get = f"/v1/conversations/{cid}/continuations/{raw['idempotency_key']}"
    return cid, post, get, request, envelope


def send(host, client, path, body):
    return client.post(path, headers={**host.headers, "content-type": MEDIA_TYPE}, content=body)


def inspect(host, client, path, **headers):
    return client.get(path, headers={**host.headers, "accept": MEDIA_TYPE, **headers})


@pytest.mark.parametrize("registered_receipts", [False, True])
def test_synthetic_canonical_completion_and_current_filtered_reads(
    setup, receiver, tmp_path, registered_receipts,
):
    host = setup(runtime_options={"model": "fake", "maximum_sensitivity": "restricted"})
    transport, arrivals, issued = receiver()
    _, creates, gates, phases = install(
        host, transport, tmp_path, registered_receipts=registered_receipts,
    )
    with TestClient(host.app) as client:
        cid, post, get, body, envelope = pending(host, client, creates)
        assert inspect(host, client, get).json()["state"] == "unknown"
        assert inspect(host, client, get, **{ORIGINAL_KEY_HEADER: str(uuid4())}).status_code == 404
        assert issued == [] and not arrivals.poll()
        altered = json.loads(body)
        altered["confirmation"] = "0" * 64
        assert send(host, client, post, canonical(altered)).status_code == 409
        assert send(host, client, post, body).status_code == 202
        assert arrivals.poll(2)
        endpoint, payload = arrivals.recv()
        assert endpoint == "/dispatch"
        assert issued == [("127.0.0.1", "POST", "/dispatch", payload)]
        assert wire_digest(payload) == envelope["claims"]["payload_sha256"]
        status = inspect(host, client, get)
        assert status.json()["state"] == "completed"
        assert status.json()["body_sha256"] == wire_digest(body)
        assert status.headers["x-pas-committed-at"].isdigit()
        detail_path = f"/v1/conversations/{cid}"
        original_key = parse(body, Confirmation).original_key
        for malformed in (
            {"accept": f"{MEDIA_TYPE}, application/json"},
            {"accept": f"{MEDIA_TYPE};q=1"},
            {"accept": "application/json"},
        ):
            denied = inspect(
                host, client, detail_path, **({ORIGINAL_KEY_HEADER: original_key} | malformed)
            )
            assert denied.status_code == 404 and denied.content == b""
        detail = inspect(host, client, detail_path, **{ORIGINAL_KEY_HEADER: original_key})
        assert detail.json() == {
            "result": "ok", "message_id": status.json()["message_id"],
            "attempt": status.json()["attempt"], "root": status.json()["root"],
            "original_key": original_key,
        }
        assert send(host, client, post, body).status_code == 202
        assert len(issued) == 1 and not arrivals.poll()
        forged = client.get(get, headers={
            **host.headers, "accept": MEDIA_TYPE, "x-user-id-token": "forged",
        })
        assert forged.status_code == 404 and forged.content == b""
        gates["denied"] = "disclose"
        assert inspect(host, client, get).status_code == 404
        assert inspect(host, client, detail_path, **{ORIGINAL_KEY_HEADER: original_key}).content == b""
        assert len({nonce for _, nonce in phases}) == len(phases)


@pytest.mark.parametrize("outcome", ["disconnect", "wrong-attempt", "nonzero-usage"])
def test_receiver_ambiguity_never_completes_or_sends_again(outcome, setup, receiver, tmp_path):
    host = setup(runtime_options={"model": "fake", "maximum_sensitivity": "restricted"})
    transport, arrivals, issued = receiver(outcome)
    _, creates, _, _ = install(host, transport, tmp_path)
    with TestClient(host.app) as client:
        cid, post, get, body, _ = pending(host, client, creates)
        assert send(host, client, post, body).status_code == 503
        assert arrivals.poll(2)
        assert arrivals.recv()[0] == "/dispatch"
        observed = inspect(host, client, get)
        assert observed.status_code == 200, (observed.status_code, observed.content)
        status = observed.json()
        assert status["state"] == "send_started" and status["terminal"] is None
        detail = inspect(
            host, client, f"/v1/conversations/{cid}",
            **{ORIGINAL_KEY_HEADER: parse(body, Confirmation).original_key},
        )
        assert detail.status_code == 404 and detail.content == b""
        assert send(host, client, post, body).status_code == 202
        assert len(issued) == 1 and not arrivals.poll()


@pytest.mark.parametrize("failure", ["revoked", "lost-bytes", "root-commit", "fence-commit"])
def test_denial_or_lost_commit_has_no_transport(failure, setup, receiver, tmp_path, monkeypatch):
    host = setup(runtime_options={"model": "fake", "maximum_sensitivity": "restricted"})
    transport, arrivals, issued = receiver()
    dispatch, creates, gates, _ = install(host, transport, tmp_path)
    with TestClient(host.app) as client:
        _, post, get, body, _ = pending(host, client, creates)
        if failure == "revoked":
            gates["denied"] = "send"
        elif failure == "lost-bytes":
            dispatch._packages.clear()
        else:
            target, method = (
                (dispatch.plans.attempts, "claim_binding") if failure == "root-commit"
                else (host.target.plan.runtime._bridge.lifecycle.store, "mark_send_started")
            )
            original = getattr(target, method)

            def commit_then_lose_worker(**kwargs):
                original(**kwargs)
                raise DispatchUnavailable

            def fence_then_lose(*args, **kwargs):
                original(*args, **kwargs)
                raise DispatchUnavailable

            monkeypatch.setattr(
                target, method, commit_then_lose_worker if failure == "root-commit" else fence_then_lose,
            )
        first = send(host, client, post, body)
        assert first.status_code == (410 if failure == "lost-bytes" else 503)
        assert inspect(host, client, get).json()["terminal"] is None
        again = send(host, client, post, body)
        assert again.status_code == (410 if failure == "lost-bytes" else 202)
        assert issued == [] and not arrivals.poll()


def test_duplicate_submit_one_winner_and_restore_gate(setup, receiver, tmp_path):
    host = setup(runtime_options={"model": "fake", "maximum_sensitivity": "restricted"})
    transport, arrivals, issued = receiver()
    dispatch, creates, gates, _ = install(host, transport, tmp_path)
    with TestClient(host.app) as client:
        _, post, get, body, _ = pending(host, client, creates)
        database = dispatch.journal._path
        before_send = database.read_bytes()
        start = Barrier(2)

        def confirm():
            start.wait(timeout=3)
            return send(host, client, post, body).status_code

        with ThreadPoolExecutor(max_workers=2) as workers:
            codes = list(workers.map(lambda _: confirm(), range(2)))
        assert 202 in codes and set(codes) <= {202, 503}
        assert arrivals.poll(2)
        arrivals.recv()
        assert len(issued) == 1 and not arrivals.poll()
        assert inspect(host, client, get).json()["state"] == "completed"
        store = host.target.plan.runtime._bridge.lifecycle.store
        fences = store.directory / "send-fences"
        restored_fences = store.directory / "restored-away"
        fences.rename(restored_fences)
        assert inspect(host, client, get).status_code == 503
        restored_fences.rename(fences)
        database.write_bytes(before_send)
        assert inspect(host, client, get).status_code == 503
        gates["continuity"] = False
        assert send(host, client, post, body).status_code == 503
        assert not dispatch._packages and not arrivals.poll()


@pytest.mark.parametrize("change", ["expiry", "memory", "model", "received-then-revoked"])
def test_source_and_memory_are_current_at_the_operation_boundary(
    change, setup, receiver, tmp_path,
):
    host = setup(runtime_options={"model": "fake", "maximum_sensitivity": "restricted"})
    transport, arrivals, issued = receiver()
    dispatch, creates, gates, _ = install(host, transport, tmp_path)
    with TestClient(host.app) as client:
        cid, post, get, body, envelope = pending(host, client, creates)
        source_reads = tuple(host.reverse.calls)
        if change == "expiry":
            gates["clock_offset"] = envelope["claims"]["expires"] - dispatch.clock()
        elif change == "memory":
            host.fixture.disclosures.clear()
        elif change == "model":
            host.target.plan.runtime._bridge.gates.clear()
        else:
            def revoke(phase):
                if phase == "disclose":
                    gates["denied"] = "disclose"

            gates["changed"] = revoke
        reply = send(host, client, post, body)
        assert reply.status_code == {
            "expiry": 410, "memory": 404, "model": 404, "received-then-revoked": 503,
        }[change]
        assert reply.content == b""
        if change == "received-then-revoked":
            assert arrivals.poll(2)
            arrivals.recv()
            assert len(issued) == 1
            assert inspect(host, client, get).status_code == 404
            gates.update(changed=None, denied=None)
            assert inspect(host, client, get).json()["state"] == "send_started"
            detail = inspect(
                host, client, f"/v1/conversations/{cid}",
                **{ORIGINAL_KEY_HEADER: parse(body, Confirmation).original_key},
            )
            assert detail.status_code == 404 and detail.content == b""
        else:
            assert issued == []
        if change == "model":
            assert tuple(host.reverse.calls) == source_reads
        assert not arrivals.poll()


def test_wrong_runtime_terminal_cannot_publish_receiver_result(
    setup, receiver, tmp_path, monkeypatch,
):
    host = setup(runtime_options={"model": "fake", "maximum_sensitivity": "restricted"})
    transport, arrivals, issued = receiver()
    dispatch, creates, _, _ = install(host, transport, tmp_path)
    deliver = RuntimeDispatch.deliver

    def wrong_root(runtime, **arguments):
        body, _, result = deliver(runtime, **arguments)
        claims = json.loads(body)
        claims["root"] = str(uuid4())
        changed = TerminalClaims.model_validate(claims)
        from personal_ai.contracts.private_dispatch import sign

        return canonical(changed), sign(runtime.terminal_key, changed), result

    monkeypatch.setattr(RuntimeDispatch, "deliver", wrong_root)
    with TestClient(host.app) as client:
        _, post, get, body, _ = pending(host, client, creates)
        assert send(host, client, post, body).status_code == 503
        assert arrivals.poll(2)
        arrivals.recv()
        assert len(issued) == 1 and not arrivals.poll()
        state = inspect(host, client, get).json()
        assert state["state"] == "send_started"
        assert state["terminal"] is None and state["message_id"] is None
        assert not dispatch._packages


def test_normal_startup_never_mounts_dispatch_profile():
    app = create_app()
    assert not getattr(app.state, "private_application_plan_routes", ())
    assert not getattr(app.state, "private_dispatch_read_routes", ())


@pytest.mark.parametrize("misbinding", ["recipient", "runtime", "endpoint"])
def test_runtime_requires_destination_mapping_to_authorized_recipient(setup, tmp_path, misbinding):
    host = setup(runtime_options={"model": "fake", "maximum_sensitivity": "restricted"})
    receiver = LoopbackReceiver(1, Ed25519PrivateKey.generate().public_key())
    dispatch, _, _, _ = install(host, receiver, tmp_path)
    runtime = dispatch.registrations[0].runtime
    if misbinding == "endpoint":
        runtime = replace(runtime, destination=runtime.destination.model_copy(
            update={"endpoint": "unregistered-loopback"},
        ))
        target = host.target.plan
    else:
        target = host.target.plan
        attr = "model_recipient" if misbinding == "recipient" else "local_recipient"
        target = replace(target, scope=target.scope.model_copy(update={attr: "wrong-grant"}))
    from personal_ai.local_bridge.runtime import BridgeDenied

    with pytest.raises(BridgeDenied):
        runtime.require_target(target, "restricted")


@pytest.mark.parametrize("misbinding", ["receiver-preview", "receiver-release", "cross-role",
                                         "duplicate-registration"])
def test_registration_rejects_signing_key_aliases(setup, tmp_path, misbinding):
    host = setup(runtime_options={"model": "fake", "maximum_sensitivity": "restricted"})
    receiver = LoopbackReceiver(1, Ed25519PrivateKey.generate().public_key())
    dispatch, _, _, _ = install(host, receiver, tmp_path)
    original = dispatch.registrations[0]
    runtime = original.runtime
    if misbinding == "cross-role":
        altered = replace(
            runtime, issuer="other-runtime", terminal_key=Ed25519PrivateKey.generate(),
            destination=runtime.destination.model_copy(update={"runtime": str(uuid4())}),
            receiver=replace(receiver, response_key=runtime.terminal_key.public_key()),
        )
        registrations = (original, replace(original, target=replace(original.target), runtime=altered))
    elif misbinding == "duplicate-registration":
        registrations = (original, original)
    else:
        reused = dispatch.preview_key if misbinding == "receiver-preview" else dispatch.release_key
        altered = replace(runtime, receiver=replace(receiver, response_key=reused.public_key()))
        registrations = (replace(original, runtime=altered),)
    with pytest.raises(ValueError, match="roles|misbound"):
        PrivateDispatch(
            plans=dispatch.plans, journal=dispatch.journal, registrations=registrations,
            issuer=dispatch.issuer, preview_kid=dispatch.preview_kid,
            preview_key=dispatch.preview_key, release_key=dispatch.release_key,
            continuity_current=lambda: True,
        )


def test_source_callback_requires_exact_wire_response():
    raw = (Path(__file__).parent / "fixtures/private-dispatch-health.txt").read_bytes()
    binding = parse(raw.splitlines()[2], Binding)

    def source(binding_bytes, phase, nonce):
        assert binding_bytes == raw.splitlines()[2]
        return {
            "binding_sha256": wire_digest(binding_bytes), "phase": phase, "nonce": nonce,
            "current": True, "expires": 1001,
        }

    CurrentSource(source).require(binding, "preview", lambda: 1000)
    with pytest.raises(DispatchDenied):
        CurrentSource(lambda *values: source(*values) | {"extra": True}).require(
            binding, "preview", lambda: 1000,
        )


def test_travel_dispatch_preview_attests_exact_original_receipt():
    """Exercise the PAS vendor-media route with the native Travel receipt signer."""
    cid, key = uuid4(), uuid4()
    original_key = Ed25519PrivateKey.generate()
    selected = b'{"purpose":"foreground_application_plan"}'
    original_binding = SimpleNamespace(
        scope=SimpleNamespace(application_id="travel", workspace_id=None),
        target_id="fixture-travel", client_namespace="fixture-client",
        owner_id="fixture-owner", human_issuer="fixture-human", human_subject="fixture-subject",
    )
    target = SimpleNamespace(
        scope=original_binding.scope,
        source_provider_id="travel",
        preview_binding=lambda principal, conversation: original_binding if conversation == cid else None,
    )
    frozen = SimpleNamespace(snapshots=(SimpleNamespace(provider_id="travel", source_version="4"),))
    envelope = canonical({"claims": {"purpose": "preview"}, "signature": "stand-in"})

    def preview(_chat, _assembler, conversation, incoming, **hooks):
        assert (conversation, incoming.idempotency_key) == (cid, key)
        hooks["require_current_operation"]()
        hooks["attest"](selected, frozen)
        hooks["prepare_dispatch"](frozen, None)
        return json.loads(selected), "4"

    plans = SimpleNamespace(current_target=lambda: target, preview_with_source_revision=preview)
    registration = SimpleNamespace(
        target=target, receipt_authority=None, runtime=SimpleNamespace(destination="fixture-fake"),
    )
    headers_seen = []

    def prepare_dispatch(_registration, _create, receipt, _frozen, _context, _chat, _assembler):
        headers_seen.append(receipt)
        return envelope

    dispatch = SimpleNamespace(
        plans=plans, registrations=(registration,), registration=lambda: registration,
        begin_preview=lambda *_: object(), prepare=prepare_dispatch,
    )
    app = FastAPI()
    app.state.isolate_external_conversations = True
    app.dependency_overrides[deps.get_chat_turn_service] = lambda: None
    mount_application_plan(
        app, service=plans, assembler_dependency=lambda: None,
        preview_recipient_scope=lambda _target: nullcontext(),
        travel_receipt_key=original_key, dispatch=dispatch,
    )
    raw = canonical(plan_request(str(key)))
    with TestClient(app) as client:
        result = client.post(
            f"{PROFILE_PREFIX}/{cid}/context-preview",
            content=raw, headers={"content-type": MEDIA_TYPE, "accept": MEDIA_TYPE},
        )
    assert result.status_code == 200 and result.content == selected
    assert result.headers["content-type"] == MEDIA_TYPE
    assert result.headers[RECEIPT_HEADER].encode("ascii") == envelope
    assert result.headers["x-application-plan-receipt"] == headers_seen[0]
    original_key.public_key().verify(bytes.fromhex(headers_seen[0]), canonical({
        "schema_version": "travel-application-plan-receipt-v1",
        "operation": "preview", "target_id": "fixture-travel",
        "client_namespace": "fixture-client", "application_id": "travel",
        "workspace_id": None, "owner_id": "fixture-owner", "issuer": "fixture-human",
        "subject": "fixture-subject", "conversation_id": str(cid),
        "request_digest": wire_digest(raw), "response_digest": wire_digest(selected),
        "source_revision": "4",
    }))

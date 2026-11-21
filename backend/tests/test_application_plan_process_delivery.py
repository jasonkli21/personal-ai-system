"""Offline-only independent peer and durable revocation-order witnesses."""

# ruff: noqa: F811 - pytest imports fixtures by their parameter names
import fcntl
import os
import socket
import ssl
import struct
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Event

import pytest

from personal_ai.local_bridge.runtime import BridgeDenied
from personal_ai.services.external_turns.application_plan import MAX_PAYLOAD_BYTES
from tests.app_context_support.process_delivery import (
    DELTA,
    FRAME_HEADER,
    PACKAGE,
    Channel,
    ProcessFixture,
    record,
)
from tests.test_application_plan_inference import (  # noqa: F401 - imported pytest fixtures
    TRAVEL_PLATFORM,
    confirmed,
    create,
    invalidate,
    plan_factory,
    plan_http,
    shared_factory,
    status,
    travel,
)

pytestmark = pytest.mark.loopback_http


@pytest.fixture
def isolated_process(tmp_path):
    # Never activate this fixture in the normal socket-free test runner.
    if os.environ.get("PRIVATE_PROCESS_DELIVERY_TEST") != "1":
        pytest.skip("requires a dedicated no-egress loopback test namespace")
    devices = Path("/proc/net/dev").read_text().splitlines()[2:]
    assert {line.split(":")[0].strip() for line in devices} == {"lo"}
    assert not any(
        line.split()[1:2] == ["00000000"]
        for line in Path("/proc/net/route").read_text().splitlines()
    )

    instances = []

    def build(**options):
        fixture = ProcessFixture(tmp_path, **options)
        instances.append(fixture)
        return fixture

    yield build

    for fixture in instances:
        fixture.close()


def trace(fixture):
    return fixture.trace.read_text().splitlines() if fixture.trace.exists() else []


def wait_for(events, name):
    deadline = time.monotonic() + 2
    while name not in events():
        assert time.monotonic() < deadline, (name, events())
        time.sleep(0.005)


def loopback_payloads(capture):
    """Observe the kernel's IP packets independently of the TLS libraries."""
    packets = {}
    capture.settimeout(0.03)
    for _ in range(2048):
        try:
            packet = capture.recv(65535)
        except TimeoutError:
            break
        if len(packet) < 40 or packet[9] != socket.IPPROTO_TCP:
            continue
        offset = (packet[0] & 15) * 4
        source, destination = struct.unpack_from("!HH", packet, offset)
        header_size = (packet[offset + 12] >> 4) * 4
        payload = packet[offset + header_size :]
        if payload:
            packets.setdefault(source, []).append(payload)
            packets.setdefault(destination, []).append(payload)
    return packets


def test_ciphertext_observed_independently_of_runtime_plaintext(plan_factory, isolated_process):
    fixture = isolated_process()
    with socket.socket(socket.AF_PACKET, socket.SOCK_DGRAM, socket.htons(0x0800)) as capture:
        control = b"loopback-observer-positive-control"
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            control_port = listener.getsockname()[1]
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as writer:
                writer.connect(listener.getsockname())
                with listener.accept()[0] as reader:
                    writer.sendall(control)
                    assert reader.recv(len(control)) == control
        assert any(control in packet for packet in loopback_payloads(capture)[control_port])

        host = plan_factory(delivery=fixture)
        target = travel(host)
        port = fixture.channel.peer.getsockname()[1]
        conversation = create(host, target)
        body = confirmed(host, target, conversation)
        response = plan_http(host, target, conversation, "continue", body)
        records = loopback_payloads(capture)[port]
    assert "event: response.completed" in response.text
    assert any(line.startswith("package-bytes ") for line in trace(fixture))
    assert any(record.startswith(b"\x17\x03\x03") for record in records)
    assert TRAVEL_PLATFORM.encode() not in b"".join(records)


def test_tls_delays_release_until_confirmation_and_recovers_original_key(
    plan_factory,
    isolated_process,
):
    fixture = isolated_process()
    host = plan_factory(delivery=fixture)
    target = travel(host)
    conversation = create(host, target)
    body = confirmed(host, target, conversation)
    assert trace(fixture) == [f"runtime {fixture.child.pid} TLSv1.3"]
    assert fixture.child.pid != os.getpid()
    assert fixture.channel.peer.version() == "TLSv1.3"
    response = plan_http(host, target, conversation, "continue", body)
    assert "event: response.completed" in response.text
    canonical = status(host, target, conversation, body).json()
    assert canonical["state"] == "completed"
    detail = host.http.get(f"/v1/conversations/{conversation}", headers=target.headers).json()
    assert any(
        item["id"] == canonical["message_id"] and item["role"] == "assistant"
        for item in detail["messages"]
    )
    assert (
        "event: response.completed" in plan_http(host, target, conversation, "continue", body).text
    )
    events = trace(fixture)
    assert events[1].startswith("package-bytes ")
    assert events[2:] == ["durable-fence", "mock-post"]
    assert len(list((fixture.store / "send-fences").iterdir())) == 1


@pytest.mark.parametrize("side", ["pas", "runtime"])
def test_tls_rejects_substituted_peer(plan_factory, isolated_process, side):
    fixture = isolated_process(substitute=side)
    host = plan_factory(delivery=fixture)
    # For TLS 1.3 the client can observe its side completing just before the
    # server rejects its identity. Either way no proof is exchanged.
    try:
        travel(host)
    except ssl.SSLError:
        pass
    assert fixture.child.wait(timeout=3) == 2
    assert not any(line.startswith("package-bytes") for line in trace(fixture))


@pytest.mark.parametrize("edge", ["before-decision", "before-fence", "after-fence"])
def test_revocation_and_fence_share_the_same_order(plan_factory, isolated_process, edge):
    fixture = isolated_process(barrier=edge)
    host = plan_factory(delivery=fixture)
    target = travel(host)
    conversation = create(host, target)
    body = confirmed(host, target, conversation)
    revoke_entered = Event()

    def revoke():
        revoke_entered.set()
        invalidate(host, target, "onward-grant")
        record(fixture.trace, "revoked")

    with ThreadPoolExecutor(max_workers=2) as pool:
        request = pool.submit(plan_http, host, target, conversation, "continue", body)
        wait_for(lambda: trace(fixture), edge)
        writer = pool.submit(revoke)
        assert revoke_entered.wait(1)
        if edge == "before-fence":
            with fixture.lock_path.open("rb") as lock, pytest.raises(BlockingIOError):
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            assert not writer.done()
        else:
            writer.result(timeout=1)
        fixture.trace.with_suffix(".resume").touch()
        writer.result(timeout=2)
        response = request.result(timeout=4)

    events = trace(fixture)
    assert "event: response.completed" not in response.text or edge == "before-fence"
    assert sum(line.startswith("package-bytes") for line in events) == 1
    if edge == "before-decision":
        assert "durable-fence" not in events and "mock-post" not in events
    else:
        assert events.index("durable-fence") < events.index("revoked")
        assert events.count("mock-post") == 1


def test_killed_runtime_releases_writer_without_allowing_a_send(plan_factory, isolated_process):
    fixture = isolated_process(barrier="before-fence")
    host = plan_factory(delivery=fixture)
    target = travel(host)
    conversation = create(host, target)
    body = confirmed(host, target, conversation)

    with ThreadPoolExecutor(max_workers=2) as pool:
        request = pool.submit(plan_http, host, target, conversation, "continue", body)
        wait_for(lambda: trace(fixture), "before-fence")
        fixture.child.kill()
        fixture.child.wait(timeout=1)
        invalidate(host, target, "onward-grant")
        response = request.result(timeout=3)

    assert "event: response.completed" not in response.text
    assert "mock-post" not in trace(fixture)
    assert "durable-fence" not in trace(fixture)
    assert (
        "event: response.completed"
        not in plan_http(host, target, conversation, "continue", body).text
    )


@pytest.mark.parametrize("change", ["onward-grant", "memory-forget", "owner-deletion"])
def test_revocation_before_release_keeps_plaintext_at_pas(plan_factory, isolated_process, change):
    fixture = isolated_process(barrier="before-ready")
    host = plan_factory(delivery=fixture)
    target = travel(host)
    conversation = create(host, target)
    body = confirmed(host, target, conversation)

    with ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(plan_http, host, target, conversation, "continue", body)
        wait_for(lambda: trace(fixture), "before-ready")
        if change == "onward-grant":
            invalidate(host, target, change)
        else:
            with fixture.mutate():
                invalidate(host, target, change)
        fixture.trace.with_suffix(".resume").touch()
        response = request.result(timeout=4)

    assert "event: response.completed" not in response.text
    assert not any(line.startswith("package-bytes ") for line in trace(fixture))
    assert "mock-post" not in trace(fixture)


@pytest.mark.parametrize("fault", ["429", "truncated", "duplicate-terminal", "out-of-order"])
def test_failed_exchange_preserves_original_attempt(plan_factory, isolated_process, fault):
    options = {"provider_fault": fault} if fault in {"429", "truncated"} else {"wire_fault": fault}
    fixture = isolated_process(**options)
    host = plan_factory(delivery=fixture)
    target = travel(host)
    conversation = create(host, target)
    body = confirmed(host, target, conversation)
    response = plan_http(host, target, conversation, "continue", body)
    assert "event: response.completed" not in response.text
    assert status(host, target, conversation, body).json()["state"] == "unknown"
    assert (
        "event: response.completed"
        not in plan_http(host, target, conversation, "continue", body).text
    )
    assert trace(fixture).count("mock-post") == (0 if fault == "out-of-order" else 1)


def test_kill_after_fence_preserves_unknown_without_dispatch(plan_factory, isolated_process):
    fixture = isolated_process(barrier="after-durable-fence")
    host = plan_factory(delivery=fixture)
    target = travel(host)
    conversation = create(host, target)
    body = confirmed(host, target, conversation)
    with ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(plan_http, host, target, conversation, "continue", body)
        wait_for(lambda: trace(fixture), "after-durable-fence")
        fixture.child.kill()
        fixture.child.wait(timeout=1)
        response = request.result(timeout=4)
    assert "event: response.completed" not in response.text
    assert status(host, target, conversation, body).json()["state"] == "unknown"
    assert len(list((fixture.store / "send-fences").iterdir())) == 1
    assert "mock-post" not in trace(fixture)


def test_channel_loss_after_fence_cannot_dispatch(plan_factory, isolated_process):
    fixture = isolated_process(barrier="after-durable-fence")
    host = plan_factory(delivery=fixture)
    target = travel(host)
    conversation = create(host, target)
    body = confirmed(host, target, conversation)
    with ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(plan_http, host, target, conversation, "continue", body)
        wait_for(lambda: trace(fixture), "after-durable-fence")
        fixture.channel.peer.shutdown(socket.SHUT_RDWR)
        fixture.trace.with_suffix(".resume").touch()
        response = request.result(timeout=4)
    assert fixture.child.wait(timeout=2) == 2
    assert "event: response.completed" not in response.text
    assert status(host, target, conversation, body).json()["state"] == "unknown"
    assert len(list((fixture.store / "send-fences").iterdir())) == 1
    assert "mock-post" not in trace(fixture)


def test_stalled_fence_boundary_times_out_without_a_post(plan_factory, isolated_process):
    fixture = isolated_process(barrier="before-fence")
    host = plan_factory(delivery=fixture)
    target = travel(host)
    conversation = create(host, target)
    body = confirmed(host, target, conversation)
    started = time.monotonic()
    response = plan_http(host, target, conversation, "continue", body)
    assert time.monotonic() - started < 5
    assert "event: response.completed" not in response.text
    assert "before-fence" in trace(fixture)
    assert "durable-fence" not in trace(fixture)
    assert "mock-post" not in trace(fixture)


def test_competing_continue_cannot_attach_to_live_channel(plan_factory, isolated_process):
    fixture = isolated_process(barrier="before-decision")
    host = plan_factory(delivery=fixture)
    target = travel(host)
    conversation = create(host, target)
    body = confirmed(host, target, conversation)
    with ThreadPoolExecutor(max_workers=1) as pool:
        request = pool.submit(plan_http, host, target, conversation, "continue", body)
        wait_for(lambda: trace(fixture), "before-decision")
        assert plan_http(host, target, conversation, "continue", body).status_code == 409
        fixture.trace.with_suffix(".resume").touch()
        response = request.result(timeout=4)
    assert "event: response.completed" in response.text
    assert trace(fixture).count("mock-post") == 1


def test_bad_signature_denies_before_package_release(plan_factory, isolated_process, monkeypatch):
    fixture = isolated_process()
    host = plan_factory(delivery=fixture)
    target = travel(host)
    conversation = create(host, target)
    body = confirmed(host, target, conversation)
    sign = host.plan.signer.sign

    def corrupt(*args, **kwargs):
        return sign(*args, **kwargs).model_copy(update={"signature": "A" * 86})

    monkeypatch.setattr(host.plan.signer, "sign", corrupt)
    response = plan_http(host, target, conversation, "continue", body)
    assert "event: response.completed" not in response.text
    assert not any(line.startswith("package-bytes ") for line in trace(fixture))
    assert "mock-post" not in trace(fixture)


def test_frame_boundary_and_sequence():
    writing, reading = socket.socketpair()
    with writing, reading:
        sender, receiver = Channel(writing), Channel(reading)
        body = b"x" * MAX_PAYLOAD_BYTES
        sender.write(PACKAGE, body)
        assert receiver.read(PACKAGE) == (PACKAGE, body)
        writing.sendall(FRAME_HEADER.pack(PACKAGE, 2, MAX_PAYLOAD_BYTES + 1))
        with pytest.raises(BridgeDenied):
            receiver.read(PACKAGE)
        writing.sendall(FRAME_HEADER.pack(DELTA, 2, 0))
        with pytest.raises(BridgeDenied):
            receiver.read(DELTA)

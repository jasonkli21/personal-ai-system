"""One preconfigured, synthetic PAS-to-runtime channel. Imported only by tests."""

import asyncio
import fcntl
import hashlib
import json
import os
import select
import socket
import ssl
import struct
import subprocess
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime, timedelta
from pathlib import Path
from threading import Lock, local
from typing import Literal
from uuid import UUID

import httpx
from cryptography import x509
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import Encoding, NoEncryption, PrivateFormat
from cryptography.x509.oid import NameOID
from pydantic import BaseModel, ConfigDict, TypeAdapter
from starlette.responses import Response

from personal_ai.api.private_application_plan import PROFILE_PREFIX
from personal_ai.auth.dispatch_grants import ApplicationPlanScope, SignedDispatchGrant
from personal_ai.llm.chatgpt.responses import serialize
from personal_ai.llm.client import GenerationEvent, GenerationMetadata
from personal_ai.llm.external import ExecutionProfileIdentity, PreparedExecution
from personal_ai.local_bridge.runtime import BridgeDenied
from personal_ai.local_bridge.store import ProtectedLocalStore
from personal_ai.services.external_turns.application_plan import (
    MAX_PAYLOAD_BYTES,
    MAX_PREVIEW_SECONDS,
)
from personal_ai.storage.async_io import sync_call

from .application_plan import build_local_runtime

HANDSHAKE_SECONDS = 2
FRAME_SECONDS = 2
ATTEMPT_SECONDS = 5
MAX_STREAM = 65536
MAX_FRAMES = 512
FRAME_HEADER = struct.Struct("!BII")
PROOF, AUTHORITY, ALLOWED, READY, PACKAGE, RECEIVED, DELTA, TERMINAL = range(1, 9)


def denied():
    return BridgeDenied("fixture_delivery_denied")


def decode(data):
    def unique(pairs):
        value = dict(pairs)
        if len(value) != len(pairs):
            raise denied()
        return value

    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=unique)
    except (ValueError, RecursionError):
        raise denied() from None


def encode(value):
    return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode()


class Offer(BaseModel):
    model_config = ConfigDict(extra="forbid")
    proof: SignedDispatchGrant
    profile: ExecutionProfileIdentity


class Terminal(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    identity: str
    fingerprint: str
    receipt: Literal["success"]
    metadata: dict


metadata_adapter = TypeAdapter(GenerationMetadata)


class Channel:
    def __init__(self, peer):
        self.peer = peer
        self.deadline = time.monotonic() + ATTEMPT_SECONDS
        self.sent = self.received = self.total = 0

    def start_attempt(self):
        self.deadline = time.monotonic() + ATTEMPT_SECONDS

    def timeout(self, deadline=None):
        remaining = (self.deadline if deadline is None else deadline) - time.monotonic()
        if remaining <= 0:
            raise denied()
        self.peer.settimeout(min(remaining, FRAME_SECONDS))

    def load(self, count, deadline):
        result = bytearray()
        while len(result) < count:
            self.timeout(deadline)
            block = self.peer.recv(count - len(result))
            if not block:
                raise denied()
            result.extend(block)
        return bytes(result)

    def bound(self, number, count):
        self.total += count + FRAME_HEADER.size
        if count > MAX_PAYLOAD_BYTES or number > MAX_FRAMES or self.total > MAX_STREAM:
            raise denied()

    def write(self, kind, body=b""):
        self.sent += 1
        self.bound(self.sent, len(body))
        self.timeout()
        self.peer.sendall(FRAME_HEADER.pack(kind, self.sent, len(body)) + body)

    def read(self, *expected, wait_for_offer=False):
        first = b""
        if wait_for_offer:
            self.peer.settimeout(MAX_PREVIEW_SECONDS)
            first = self.peer.recv(1)
            if not first:
                raise denied()
            self.start_attempt()
        deadline = min(self.deadline, time.monotonic() + FRAME_SECONDS)
        header = first + self.load(FRAME_HEADER.size - len(first), deadline)
        kind, number, count = FRAME_HEADER.unpack(header)
        self.received += 1
        if kind not in expected or number != self.received:
            raise denied()
        self.bound(number, count)
        return kind, self.load(count, deadline)

    def clean_close(self):
        self.timeout()
        with self.peer.unwrap():
            pass

    def require_eof(self):
        self.timeout()
        if self.peer.recv(1):
            raise denied()
        self.clean_close()


def certificate(directory, name):
    key = Ed25519PrivateKey.generate()
    identity = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, name)])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(identity)
        .issuer_name(identity)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=1))
        .not_valid_after(now + timedelta(minutes=5))
        .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
        .sign(key, None)
    )
    certfile, keyfile = directory / (name + ".pem"), directory / (name + ".key")
    certfile.write_bytes(cert.public_bytes(Encoding.PEM))
    with os.fdopen(os.open(keyfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600), "wb") as output:
        output.write(key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8, NoEncryption()))
    return str(certfile), str(keyfile)


def connect_tls(raw, identity, peer_cert, *, server):
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER if server else ssl.PROTOCOL_TLS_CLIENT)
    context.minimum_version = context.maximum_version = ssl.TLSVersion.TLSv1_3
    context.check_hostname = False
    context.verify_mode = ssl.CERT_REQUIRED
    context.options |= ssl.OP_NO_TICKET
    if server:
        context.num_tickets = 0
    context.load_cert_chain(*identity)
    Path(identity[1]).unlink()
    context.load_verify_locations(cafile=peer_cert)
    raw.settimeout(HANDSHAKE_SECONDS)
    peer = context.wrap_socket(raw, server_side=server, suppress_ragged_eofs=False)
    pinned = x509.load_pem_x509_certificate(Path(peer_cert).read_bytes()).public_bytes(Encoding.DER)
    if peer.session_reused or peer.getpeercert(binary_form=True) != pinned:
        peer.close()
        raise denied()
    peer.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    return peer


@contextmanager
def authority_lock(path):
    """The process holding this descriptor owns exclusion until it closes or dies."""
    fd = os.open(path, os.O_RDWR | os.O_NOFOLLOW)
    try:
        deadline = time.monotonic() + FRAME_SECONDS
        while True:
            try:
                fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                break
            except BlockingIOError:
                if time.monotonic() >= deadline:
                    raise denied() from None
                time.sleep(0.005)
        yield
    finally:
        os.close(fd)


class ProcessDelivery:
    """PAS end. Its owning request services authority inquiries synchronously."""

    def __init__(self, channel, *, scope, caller_id, connection_id, service, lock_path):
        self.channel = channel
        self.scope, self.caller_id, self.connection_id = scope, caller_id, connection_id
        self.service = service
        self.lock_path = lock_path
        self._attach = Lock()
        self._used = False

    def _authorized_read(self, proof, package, *expected):
        while True:
            kind, data = self.channel.read(AUTHORITY, *expected)
            if kind != AUTHORITY:
                return kind, data
            if data or not self._current(proof, package):
                raise denied()
            self.channel.write(ALLOWED)

    def _current(self, proof, package):
        claims = proof.claims
        return (
            claims.issued_at <= time.time() < claims.expires_at
            and self.service.authorize_delivery(
                root_id=claims.routing_root,
                package=package,
                claims=claims,
                scope=self.scope,
                caller_id=self.caller_id,
            )
        )

    async def deliver(self, proof, profile, release):
        with self._attach:
            if self._used:
                raise denied()
            self._used = True

        def handoff():
            self.channel.start_attempt()
            self.channel.write(
                PROOF, Offer(proof=proof, profile=profile).model_dump_json().encode()
            )
            _, ready = self._authorized_read(proof, None, READY)
            if ready:
                raise denied()
            with authority_lock(self.lock_path):
                if time.time() >= proof.claims.expires_at:
                    raise denied()
                package = release()
                self.channel.write(PACKAGE, package.canonical())
                if self._authorized_read(proof, package, RECEIVED) != (RECEIVED, b""):
                    raise denied()
            return package

        def next_event(package):
            kind, data = self._authorized_read(proof, package, DELTA, TERMINAL)
            if kind == DELTA:
                if not self._current(proof, package):
                    raise denied()
                return GenerationEvent.text_delta(data.decode("utf-8"))
            terminal = Terminal.model_validate(decode(data))
            metadata = metadata_adapter.validate_json(encode(terminal.metadata), strict=True)
            if (
                terminal.identity != package.dispatch_identity
                or terminal.fingerprint != package.fingerprint
                or metadata.status != "success"
                or metadata.invocation_id != str(package.reservation_id)
                or (
                    metadata.identity.provider_id,
                    metadata.identity.model_id,
                    metadata.identity.serializer_id,
                )
                != (package.provider_id, package.model_id, profile.serializer_id)
            ):
                raise denied()
            self.channel.require_eof()
            if not self._current(proof, package):
                raise denied()
            return GenerationEvent.terminal(metadata)

        try:
            package = await sync_call(handoff)
            emitted_bytes = emitted_chars = 0
            while True:
                event = await sync_call(next_event, package)
                if event.kind == "delta":
                    emitted_bytes += len(event.delta.encode())
                    emitted_chars += len(event.delta)
                    if (
                        emitted_bytes > package.max_output_bytes
                        or emitted_chars > package.max_output_chars
                    ):
                        raise denied()
                yield event
                if event.kind == "terminal":
                    return
        except (OSError, ValueError, RecursionError):
            raise denied() from None
        finally:
            self.channel.peer.close()


class RemoteAuthority:
    def __init__(self):
        self.channel = self.proof = self.package = None

    def authorize(self, *, root_id, package, claims, installation, session):
        if (
            self.proof is None
            or claims != self.proof.claims
            or root_id != claims.routing_root
            or installation.scope != claims.application_plan.scope
            or session.caller_id != claims.caller_id
            or (package is not None and package != self.package)
        ):
            return False
        return self.current()

    def current(self):
        self.channel.write(AUTHORITY)
        return self.channel.read(ALLOWED) == (ALLOWED, b"")


def record(path, name):
    with path.open("a") as output:
        output.write(name + "\n")
        output.flush()


class CoordinatedStore(ProtectedLocalStore):
    def __init__(self, path, lock_path, trace, barrier, authority):
        super().__init__(path)
        self.lock_path, self.trace, self.barrier = lock_path, trace, barrier
        self.authority = authority
        self._fence_deadline = None

    def pause(self, edge):
        if self.barrier != edge:
            return
        record(self.trace, edge)
        deadline = time.monotonic() + FRAME_SECONDS
        while not self.trace.with_suffix(".resume").exists():
            if time.monotonic() >= deadline:
                raise denied()
            time.sleep(0.005)

    def _persist_send_fence(self, identity, receipt):
        self.pause("before-fence")
        if time.time() >= self._fence_deadline:
            raise denied()
        super()._persist_send_fence(identity, receipt)
        record(self.trace, "durable-fence")
        self.pause("after-durable-fence")

    def mark_send_started(self, *args, expires_at, **kwargs):
        self.pause("before-decision")
        with authority_lock(self.lock_path):
            self._fence_deadline = expires_at
            super().mark_send_started(*args, expires_at=expires_at, **kwargs)
            # A deadline crossed during disk persistence consumes the fence but
            # cannot start a configured provider invocation.
            if not self.authority.current() or time.time() >= expires_at:
                raise denied()
        self.pause("after-fence")


async def run_runtime(channel, bridge, session, authority, store, wire_fault):
    caller = {"origin": session.origin, "authorization": session.authorization}
    _, data = await sync_call(channel.read, PROOF, wait_for_offer=True)
    offer = Offer.model_validate(decode(data))
    proof, profile = offer.proof, offer.profile
    authority.channel, authority.proof = channel, proof
    await sync_call(bridge.authorize_handoff, proof, profile, **caller)
    if proof.claims.model_id not in {model.slug for model in await bridge.models(**caller)}:
        raise denied()
    await sync_call(bridge.authorize_handoff, proof, profile, **caller)
    await sync_call(store.pause, "before-ready")
    await sync_call(channel.write, DELTA if wire_fault == "out-of-order" else READY)
    _, raw = await sync_call(channel.read, PACKAGE)
    record(store.trace, f"package-bytes {len(raw)}")
    package = PreparedExecution.model_validate(decode(raw))
    if (
        raw != package.canonical()
        or package.execution_profile != profile
        or package.fingerprint != proof.claims.package_hash
    ):
        raise denied()
    bridge.verifier.verify(proof, package, caller_id=session.caller_id, now=time.time())
    payload = serialize(package.chat_messages(), package.model_id)
    if hashlib.sha256(payload).hexdigest() != proof.claims.application_plan.provider_payload_sha256:
        raise denied()
    authority.package = package
    await sync_call(channel.write, RECEIVED)
    stream = bridge.execute(package, proof, **caller)
    terminal = None
    try:
        async for event in stream:
            if terminal is not None:
                raise denied()
            if event.kind == "delta":
                await sync_call(channel.write, DELTA, event.delta.encode())
            else:
                receipt = await bridge.reconcile(
                    package.dispatch_identity, package.fingerprint, **caller
                )
                if event.metadata.status != "success" or receipt.status != "success":
                    raise denied()
                terminal = Terminal(
                    identity=package.dispatch_identity,
                    fingerprint=package.fingerprint,
                    receipt="success",
                    metadata=asdict(event.metadata),
                )
        if terminal is None:
            raise denied()
        await sync_call(channel.write, TERMINAL, terminal.model_dump_json().encode())
        if wire_fault == "duplicate-terminal":
            await sync_call(channel.write, TERMINAL, terminal.model_dump_json().encode())
        await sync_call(channel.clean_close)
    finally:
        await stream.aclose()


def runtime_process():
    config = decode(sys.stdin.buffer.readline(8193))
    trace = Path(config["trace"])
    authority = RemoteAuthority()
    store = CoordinatedStore(
        Path(config["store"]),
        Path(config["lock"]),
        trace,
        config["barrier"],
        authority,
    )
    bridge, session, provider = build_local_runtime(
        store,
        public_key=Ed25519PublicKey.from_public_bytes(bytes.fromhex(config["public_key"])),
        root_authority=authority,
        **config["binding"],
    )

    def handle(request):
        if request.method == "POST":
            record(trace, "mock-post")
        return provider.handle(request)

    provider.provider.transport = httpx.MockTransport(handle)
    if config["provider_fault"] == "truncated":
        provider.events.pop()
    elif config["provider_fault"] == "429":
        provider.status = 429
    print(
        encode(
            {
                "scope": bridge.installation.scope.model_dump(mode="json"),
                "caller": str(session.caller_id),
                "connection": str(session.connection_id),
            }
        ).decode(),
        flush=True,
    )
    if sys.stdin.buffer.readline(6) != b"start\n":
        raise denied()

    def fence(event, args):
        if (
            event
            in {
                "socket.getaddrinfo",
                "socket.gethostbyname",
                "socket.gethostbyname_ex",
                "socket.gethostbyaddr",
                "socket.getnameinfo",
                "socket.sendto",
                "socket.sendmsg",
            }
            or (event == "socket.connect" and args[1] != ("127.0.0.1", config["port"]))
            or event == "socket.bind"
        ):
            record(trace, "external-network-denied")
            raise denied()

    sys.addaudithook(fence)
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as raw:
        raw.settimeout(HANDSHAKE_SECONDS)
        raw.connect(("127.0.0.1", config["port"]))
        with connect_tls(raw, config["identity"], config["peer"], server=False) as peer:
            record(trace, f"runtime {os.getpid()} {peer.version()}")
            asyncio.run(
                run_runtime(Channel(peer), bridge, session, authority, store, config["wire_fault"])
            )


class ProcessTurnAdmission:
    """Keep unrelated HTTP writers and concurrent continuation writers off this host."""

    def __init__(self, app):
        self.app = app
        self.continuing = Lock()

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        path, method = scope["path"], scope["method"]
        if method in {"GET", "HEAD"} or (method == "POST" and path == "/v1/conversations"):
            return await self.app(scope, receive, send)
        if method != "POST" or not path.startswith(PROFILE_PREFIX + "/"):
            return await Response(status_code=405)(scope, receive, send)
        if not path.endswith("/continue"):
            return await self.app(scope, receive, send)
        if not self.continuing.acquire(blocking=False):
            return await Response(status_code=409)(scope, receive, send)
        try:
            return await self.app(scope, receive, send)
        finally:
            self.continuing.release()


class ProcessFixture:
    runtime_type = ProcessDelivery

    def __init__(
        self, directory, *, barrier=None, substitute=None, wire_fault=None, provider_fault=None
    ):
        self.directory, self.barrier, self.substitute = directory, barrier, substitute
        self.wire_fault, self.provider_fault = wire_fault, provider_fault
        self.lock_path = directory / "authority.lock"
        self.lock_path.touch(mode=0o600, exist_ok=False)
        self.trace = directory / "runtime.trace"
        self.child = self.channel = None
        self._writing = local()

    def open(self, store, binding, key, service):
        if self.child is not None:
            raise denied()
        pas, runtime = (certificate(self.directory, name) for name in ("pas", "runtime"))
        alternate = None if self.substitute is None else certificate(self.directory, "alternate")
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
            listener.bind(("127.0.0.1", 0))
            listener.listen(1)
            listener.settimeout(HANDSHAKE_SECONDS)
            self.child = subprocess.Popen(
                [sys.executable, "-B", "-m", __name__],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                env={
                    "PATH": os.environ["PATH"],
                    "PYTHONPATH": str(Path(__file__).resolve().parents[2]),
                    "LITELLM_LOCAL_MODEL_COST_MAP": "True",
                },
            )
            self.store = store
            config = {
                "store": str(store),
                "lock": str(self.lock_path),
                "trace": str(self.trace),
                "barrier": self.barrier,
                "public_key": key.public_bytes_raw().hex(),
                "binding": binding,
                "port": listener.getsockname()[1],
                "identity": alternate if self.substitute == "runtime" else runtime,
                "peer": pas[0],
                "wire_fault": self.wire_fault,
                "provider_fault": self.provider_fault,
            }
            self.child.stdin.write(encode(config) + b"\n")
            self.child.stdin.flush()
            if not select.select([self.child.stdout], [], [], 10)[0]:
                raise denied()
            enrolled = decode(self.child.stdout.readline(8193))
            scope = ApplicationPlanScope.model_validate(enrolled["scope"])
            if (
                scope.owner_id,
                scope.actor_id,
                scope.application_id,
                scope.workspace_id,
                scope.client_namespace,
            ) != (
                binding["owner_id"],
                binding["actor"],
                binding["application_id"],
                binding["workspace_id"],
                binding["namespace"],
            ):
                raise denied()
            self.child.stdin.write(b"start\n")
            self.child.stdin.flush()
            raw, address = listener.accept()
            with raw:
                if address[0] != "127.0.0.1":
                    raise denied()
                peer = connect_tls(
                    raw,
                    alternate if self.substitute == "pas" else pas,
                    runtime[0],
                    server=True,
                )
                self.channel = Channel(peer)
            return self.runtime_type(
                self.channel,
                scope=scope,
                caller_id=UUID(enrolled["caller"]),
                connection_id=UUID(enrolled["connection"]),
                service=service,
                lock_path=self.lock_path,
            )

    def bind_host(self, host):
        host.app.add_middleware(ProcessTurnAdmission)

        def serialize_writer(writer):
            def write(*args, **kwargs):
                with self.mutate():
                    return writer(*args, **kwargs)

            return write

        writers = [
            (host, ("control", "seed", "write_policy")),
            (host.controls, ("owner_control", "enroll")),
            (host.directory, ("deactivate",)),
            (host.installations, ("mutate",)),
            (host.plan, ("share_memory", "seed_memory")),
            *((source, ("seed", "hide")) for source in host.sources.values()),
        ]
        for owner, names in writers:
            for name in names:
                setattr(owner, name, serialize_writer(getattr(owner, name)))

    @contextmanager
    def mutate(self):
        if getattr(self._writing, "active", False):
            yield
            return
        with authority_lock(self.lock_path):
            self._writing.active = True
            try:
                yield
            finally:
                self._writing.active = False

    def close(self):
        if self.channel is not None:
            self.channel.peer.close()
        if self.child is not None:
            try:
                self.child.wait(timeout=1)
            except subprocess.TimeoutExpired:
                self.child.kill()
                self.child.wait(timeout=1)
            self.child.stdin.close()
            self.child.stdout.close()
        for key in self.directory.glob("*.key"):
            key.unlink()


if __name__ == "__main__":
    try:
        runtime_process()
    except (OSError, ValueError, RuntimeError, KeyError, RecursionError):
        raise SystemExit(2) from None

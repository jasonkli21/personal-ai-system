"""Exact-byte synthetic delivery through the existing paired runtime and POSIX fence."""

import http.client
import socket
from dataclasses import dataclass
from uuid import UUID, uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from personal_ai.contracts.private_dispatch import (
    VERSION,
    Binding,
    Destination,
    ReleaseClaims,
    TerminalClaims,
    canonical,
    canonical_object,
    sign,
    verify,
    wire_digest,
)
from personal_ai.local_bridge.runtime import BridgeDenied


@dataclass(frozen=True)
class LoopbackReceiver:
    """Registration pins a numeric local endpoint and the receiving fixture's response key."""

    port: int
    response_key: Ed25519PublicKey

    def __post_init__(self):
        if not 1 <= self.port <= 65535:
            raise ValueError("invalid receiver port")

    def post(self, payload, *, attempt, payload_hash, authorize_write):
        # Bypass DNS, proxies, redirects, automatic connection creation and retries.
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(2)
            sock.connect(("127.0.0.1", self.port))
            connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=2)
            connection.auto_open = 0
            connection.sock = sock
            try:
                authorize_write()
                connection.request(
                    "POST", "/dispatch", body=payload,
                    headers={
                        "Content-Type": "application/json",
                        "Content-Length": str(len(payload)),
                        "X-PAS-Attempt": attempt,
                        "X-PAS-Payload-SHA256": payload_hash,
                    },
                )
                response = connection.getresponse()
                signatures = response.headers.get_all("x-fixture-signature", [])
                if response.status != 200 or len(signatures) != 1:
                    raise ValueError("fixture response rejected")
                raw = response.read(2049)
                if len(raw) > 2048:
                    raise ValueError("fixture response too large")
                self.response_key.verify(bytes.fromhex(signatures[0]), raw)
                body = canonical_object(raw)
                if (
                    set(body) != {"attempt", "payload_sha256", "result", "usage"}
                    or body["attempt"] != attempt
                    or body["payload_sha256"] != payload_hash
                    or type(body["usage"]) is not int or body["usage"] != 0
                    or type(body["result"]) is not str
                    or not 0 < len(body["result"].encode("utf-8")) <= 100
                ):
                    raise ValueError("fixture response does not match dispatch")
                return body["result"]
            finally:
                connection.close()


def fence_identity(binding, body_hash, payload_hash):
    attempt = wire_digest(canonical(["pas-dispatch-attempt", binding.attempt]))
    original = wire_digest(canonical([
        "pas-dispatch-original", binding.tenant, binding.workspace, binding.app, binding.owner,
        binding.client, binding.conversation, binding.original_key,
    ]))
    fingerprint = wire_digest(canonical([wire_digest(canonical(binding)), body_hash, payload_hash]))
    return attempt, original, fingerprint


@dataclass(frozen=True)
class RuntimeDispatch:
    """An explicitly paired synthetic receiver. The ordinary bridge executor is unused."""

    destination: Destination
    receiver: LoopbackReceiver
    pas_issuer: str
    release_kid: str
    release_key: Ed25519PublicKey
    issuer: str
    terminal_kid: str
    terminal_key: Ed25519PrivateKey

    def require_target(self, target, sensitivity="public"):
        paired = target.runtime
        bridge, session = paired._bridge, paired._session
        destination = self.destination
        if (
            type(self.receiver) is not LoopbackReceiver
            or destination.runtime != str(bridge.installation.runtime_id)
            or destination.connection != str(bridge.installation.connection_id)
            or destination.revision != bridge.installation.connection_revision
            or destination.account != bridge.installation.registration_binding
            or destination.endpoint != "loopback-fixture"
            # These are the recipient grant identities used by the assembler, bound
            # by the pairing to the exact registered account and local runtime.
            or target.scope.model_recipient != f"openai-responses:{destination.account}"
            or target.scope.local_recipient != f"local:{destination.runtime}"
            or target.scope != bridge.installation.scope
            or target.caller_id != session.caller_id
            or target.model != destination.model
            or target.connection_id != UUID(destination.connection)
            or target.connection_revision != destination.revision
        ):
            raise BridgeDenied("bridge_admission_denied")
        bridge._require_offline_transport()
        if bridge.authorize(session.origin, session.authorization) != session:
            raise BridgeDenied("bridge_admission_denied")
        bridge._gate(target.connection_id, target.profile, destination.model).require_binding(
            target.connection_id, target.profile, destination.model, sensitivity,
            now=int(bridge.clock()),
        )

    def deliver(
        self, *, target, binding: Binding, release: bytes, signature, release_payload,
        authorize, clock, mark_started, sensitivity,
    ):
        paired = target.runtime
        bridge, session = paired._bridge, paired._session
        destination = binding.destination
        if destination != self.destination:
            raise BridgeDenied("bridge_admission_denied")
        self.require_target(target, sensitivity)
        claims = verify(
            self.release_key, signature, release, ReleaseClaims,
            issuer=self.pas_issuer, audience=self.issuer, kid=self.release_kid, now=clock(),
        )
        if (claims.binding_sha256, claims.root, claims.attempt) != (
            wire_digest(canonical(binding)), binding.root, binding.attempt,
        ):
            raise BridgeDenied("bridge_admission_denied")

        def require_pairing():
            self.require_target(target, sensitivity)
            if clock() >= claims.expires:
                raise BridgeDenied("bridge_admission_denied")

        require_pairing()
        authorize("release")
        store = bridge.lifecycle.store
        attempt, original, fingerprint = fence_identity(
            binding, claims.body_sha256, claims.payload_sha256,
        )
        token = store.claim(
            attempt, fingerprint, destination.connection, destination.revision, claims.expires,
            origin=session.origin, now=clock(), no_takeover=True, related_identity=original,
        )

        def authorize_locked(state, registration):
            require_pairing()
            bridge.installation.require_registration(state, registration)
            authorize("send")

        store.mark_send_started(
            attempt, fingerprint, destination.connection, destination.revision, token,
            expires_at=claims.expires, now=clock(), authorize=authorize_locked,
            retain_fence=True, related_identity=original,
        )
        mark_started()
        payload = release_payload()
        if wire_digest(payload) != claims.payload_sha256:
            raise BridgeDenied("bridge_admission_denied")

        def authorize_write():
            if wire_digest(payload) != claims.payload_sha256:
                raise BridgeDenied("bridge_admission_denied")
            with store.transaction() as tx:
                authorize_locked(tx.state, tx.state.registrations.get(destination.connection))

        result = self.receiver.post(
            payload, attempt=binding.attempt, payload_hash=claims.payload_sha256,
            authorize_write=authorize_write,
        )
        require_pairing()
        terminal = TerminalClaims(
            v=VERSION, issuer=self.issuer, audience=self.pas_issuer, kid=self.terminal_kid,
            purpose="terminal", binding_sha256=claims.binding_sha256, expires=claims.expires,
            attempt=binding.attempt, root=binding.root, body_sha256=claims.body_sha256,
            message_id=str(uuid4()), result_sha256=wire_digest(result.encode("utf-8")),
        )
        return canonical(terminal), sign(self.terminal_key, terminal), result

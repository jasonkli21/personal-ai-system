"""Explicitly enrolled, synthetic-only source-bound dispatch and recovery."""

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from contextvars import copy_context
from dataclasses import dataclass
from datetime import UTC, datetime
from threading import Lock, Timer
from time import monotonic
from uuid import UUID, uuid4, uuid5

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from personal_ai.context.authority import application_plan_source_binding, source_snapshots_current
from personal_ai.context.providers import ContextPreparationError
from personal_ai.contracts.private_dispatch import (
    VERSION,
    Binding,
    Confirmation,
    Current,
    PreviewClaims,
    ReleaseClaims,
    TerminalClaims,
    canonical,
    parse,
    sign,
    verify,
    wire_digest,
)
from personal_ai.local_bridge.private_dispatch import RuntimeDispatch, fence_identity
from personal_ai.local_bridge.runtime import BridgeDenied
from personal_ai.local_bridge.store import LocalStoreError
from personal_ai.services.external_turns.application_plan import MAX_PAYLOAD_BYTES, PlanTarget
from personal_ai.storage.errors import ConversationConflictError, ResourceNotFoundError


class DispatchDenied(Exception):
    status = 404


class DispatchUnavailable(DispatchDenied):
    status = 503


class DispatchExpired(DispatchDenied):
    status = 410


class DispatchConflict(DispatchDenied):
    status = 409


@dataclass(frozen=True)
class CreateBinding:
    """Original key and exact verified detached receipt of the current create operation."""

    key: UUID
    receipt: str
    epoch: int
    expires: int


class CurrentSource:
    """A registered in-process callback, with one bounded, non-queueing slot."""

    def __init__(self, callback):
        self._callback = callback
        self._slot = Lock()
        self._worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="private-source")

    def _check(self, binding, phase, nonce):
        try:
            return self._callback(binding, phase, nonce)
        finally:
            self._slot.release()

    def require(self, binding, phase, clock):
        if not self._slot.acquire(blocking=False):
            raise DispatchUnavailable
        nonce = str(uuid4())
        started = monotonic()
        try:
            ctx = copy_context()
            future = self._worker.submit(ctx.run, self._check, binding, phase, nonce)
        except RuntimeError:
            self._slot.release()
            raise DispatchUnavailable from None
        try:
            response = Current.model_validate(future.result(timeout=1))
        except (TimeoutError, OSError):
            raise DispatchUnavailable from None
        except Exception:  # noqa: BLE001 - untrusted witness failures deny
            raise DispatchDenied from None
        if (response.binding_sha256, response.phase, response.nonce) != (
            wire_digest(canonical(binding)), phase, nonce,
        ) or not response.current or clock() >= response.expires or monotonic() - started >= 1:
            raise DispatchDenied


@dataclass(frozen=True)
class DispatchRegistration:
    target: PlanTarget
    tenant: str
    installation: str
    runtime: RuntimeDispatch
    current: CurrentSource
    # Hooks belong to the trusted composition. The load hook must reread PAS
    # dependency evidence even when the preparing process has disappeared.
    verified_create: Callable
    source_commitments: Callable
    verified_preview_expiry: Callable
    load_dependencies: Callable
    trust_current: Callable


@dataclass(frozen=True, repr=False)
class PreparedDispatch:
    binding: Binding
    claims: bytes
    signature: str
    payload: bytes
    dependencies: object


class PrivateDispatch:
    def __init__(
        self, *, plans, journal, registrations, issuer, preview_kid, preview_key,
        release_key, continuity_current, clock=None,
    ):
        self.plans = plans
        self.journal = journal
        self.registrations = tuple(registrations)
        self.issuer = issuer
        self.preview_kid = preview_kid
        self.preview_key: Ed25519PrivateKey = preview_key
        self.release_key: Ed25519PrivateKey = release_key
        self.continuity_current = continuity_current
        self.clock = clock or (lambda: int(datetime.now(UTC).timestamp()))
        self._packages = {}
        self._lock = Lock()

        preview_public = self.preview_key.public_key().public_bytes_raw()
        release_public = self.release_key.public_key().public_bytes_raw()
        if preview_public == release_public or any(
            entry.runtime.release_key.public_bytes_raw() != release_public
            or entry.runtime.terminal_key.public_key().public_bytes_raw()
            in {preview_public, release_public, entry.runtime.receiver.response_key.public_bytes_raw()}
            for entry in self.registrations
        ):
            raise ValueError("dispatch roles require distinct pinned keys")

    def _continuity(self):
        try:
            current = self.continuity_current() is True
        except Exception:  # noqa: BLE001 - continuity failures deny
            current = False
        if not current:
            with self._lock:
                self._packages.clear()
            raise DispatchUnavailable

    def registration(self):
        try:
            target = self.plans.current_target()
        except ContextPreparationError:
            self._continuity()
            raise DispatchDenied from None
        self._continuity()
        matches = [entry for entry in self.registrations if entry.target is target]
        if len(matches) != 1:
            raise DispatchDenied
        registration = matches[0]
        if (
            target.preview_source is None
            or target.scope.application_id not in {"travel", "health"}
            or type(registration.runtime) is not RuntimeDispatch
            or registration.runtime.pas_issuer != self.issuer
            or registration.trust_current() is not True
        ):
            raise DispatchDenied
        return registration

    @staticmethod
    def key(registration, conversation, original_key):
        scope = registration.target.scope
        return wire_digest(canonical([
            registration.tenant, scope.workspace_id, scope.application_id, scope.owner_id,
            scope.client_namespace, str(conversation), str(original_key),
        ]))

    def begin_preview(self, registration, conversation, original_key):
        registration.target.preview_binding(
            self._principal(), conversation,
        )
        create = registration.verified_create(conversation, original_key)
        if (
            type(create) is not CreateBinding or create.key == original_key
            or type(create.receipt) is not str or not create.receipt.isascii()
            or not create.receipt.isprintable() or not 0 < len(create.receipt) <= 8192
            or self.clock() >= create.expires
        ):
            raise DispatchDenied
        return create

    @staticmethod
    def _principal():
        from personal_ai.auth.scope import current_verified_principal

        return current_verified_principal()

    def prepare(self, registration, create, receipt, dependencies, context, chat, assembler):
        old = dependencies.binding
        conversation = old.conversation_id
        original_key = dependencies.original_key
        key = self.key(registration, conversation, original_key)
        root = uuid5(conversation, "pas-dispatch/1:" + key)
        source, memory = registration.source_commitments(dependencies)
        binding = Binding(
            actor_issuer=old.human_issuer, app=old.scope.application_id,
            attempt=str(uuid5(root, "foreground")), branch=dependencies.branch_digest,
            client=old.client_namespace, conversation=str(conversation), create_key=str(create.key),
            create_receipt=wire_digest(create.receipt.encode("ascii")),
            destination=registration.runtime.destination, epoch=create.epoch,
            installation=registration.installation, memory=memory, original_key=str(original_key),
            owner=old.owner_id, policy=dependencies.policy_version,
            preview_receipt=wire_digest(receipt.encode("ascii")), root=str(root), source=source,
            subject=old.human_subject, target=old.target_id, tenant=registration.tenant,
            workspace=old.scope.workspace_id,
        )
        now = self.clock()
        expires = min(
            now + 60, int(dependencies.expires_at.timestamp()), create.expires,
            registration.verified_preview_expiry(receipt, dependencies),
        )
        self._current(registration, binding, dependencies, "preview", chat, assembler)
        if now >= expires:
            raise DispatchExpired
        payload = canonical({
            "messages": [
                {"role": str(message.role), "content": message.content}
                for message in context.assembled.messages
            ],
            "model": binding.destination.model,
        })
        if not 0 < len(payload) <= MAX_PAYLOAD_BYTES or any(
            str(message.role) not in {"system", "developer", "user", "assistant"}
            for message in context.assembled.messages
        ):
            raise DispatchDenied
        claims = PreviewClaims(
            v=VERSION, issuer=self.issuer, audience=binding.app, kid=self.preview_kid,
            expires=expires, purpose="preview", binding_sha256=wire_digest(canonical(binding)),
            payload_sha256=wire_digest(payload),
        )
        prepared = PreparedDispatch(
            binding, canonical(claims), sign(self.preview_key, claims), payload, dependencies,
        )
        with self._lock:
            self._packages = {
                k: value for k, value in self._packages.items() if value[0] > now
            }
            if len(self._packages) >= 16:
                self._packages.pop(min(self._packages, key=lambda k: self._packages[k][0]))
            if not self.journal.seal(
                key, binding, prepared.claims, prepared.signature, expires, claims.payload_sha256,
            ):
                raise DispatchConflict
            self._packages[key] = expires, prepared
        timer = Timer(max(0, expires - self.clock()), self._expire, args=(key, expires))
        timer.daemon = True
        timer.start()
        return canonical({"claims": claims.model_dump(mode="json"), "signature": prepared.signature})

    def _expire(self, key, expires):
        with self._lock:
            entry = self._packages.get(key)
            if entry is not None and entry[0] == expires:
                self._packages.pop(key)

    def retire(self, registration, conversation, original_key):
        with self._lock:
            self._packages.pop(self.key(registration, conversation, original_key), None)

    def _require_scoped_binding(self, registration, binding, conversation, original_key):
        target = registration.target
        old = target.preview_binding(self._principal(), conversation)
        scope = target.scope
        key = self.key(registration, conversation, original_key)
        root = uuid5(conversation, "pas-dispatch/1:" + key)
        if (
            binding.tenant, binding.installation, binding.destination, binding.app, binding.client,
            binding.workspace, binding.owner, binding.actor_issuer, binding.subject, binding.target,
            binding.conversation, binding.original_key, binding.root, binding.attempt,
        ) != (
            registration.tenant, registration.installation, registration.runtime.destination,
            scope.application_id, scope.client_namespace, scope.workspace_id, old.owner_id,
            old.human_issuer, old.human_subject, old.target_id, str(conversation), str(original_key),
            str(root), str(uuid5(root, "foreground")),
        ):
            raise DispatchDenied

    def _current(self, registration, binding, dependencies, phase, chat, assembler):
        if self.registration() is not registration:
            raise DispatchDenied
        target = registration.target
        conversation = UUID(binding.conversation)
        expected = target.preview_binding(self._principal(), conversation)
        if dependencies.binding != expected or registration.source_commitments(dependencies) != (
            binding.source, binding.memory,
        ) or dependencies.branch_digest != binding.branch or dependencies.policy_version != binding.policy:
            raise DispatchDenied
        token = application_plan_source_binding.set(expected)
        try:
            if not source_snapshots_current(
                dependencies.snapshots, assembler.permission_revalidator,
                now=datetime.fromtimestamp(self.clock(), UTC),
            ) or not chat.current_bound_branch(conversation, expected_branch=binding.branch):
                raise DispatchDenied
            registration.current.require(binding, phase, self.clock)
        except (ContextPreparationError, ResourceNotFoundError):
            raise DispatchDenied from None
        finally:
            application_plan_source_binding.reset(token)

    def _root_arguments(self, row):
        return {
            "owner": row.binding.owner, "root": UUID(row.binding.root), "attempt": UUID(row.binding.attempt),
            "payload": row.payload_hash, "confirmation": row.body_hash,
            "expires": datetime.fromtimestamp(row.expires, UTC),
        }

    def _read_dependencies(self, registration, binding):
        try:
            dependencies = registration.load_dependencies(binding)
        except (LookupError, OSError):
            raise DispatchUnavailable from None
        if dependencies is None:
            raise DispatchUnavailable
        return dependencies

    def confirm(self, registration, conversation, raw, chat, assembler):
        incoming = parse(raw, Confirmation)
        key = self.key(registration, conversation, incoming.original_key)
        row = self.journal.read(key)
        if row is None:
            raise DispatchDenied
        self._require_scoped_binding(registration, row.binding, conversation, incoming.original_key)
        with self._lock:
            cached = self._packages.get(key)
        dependencies = cached[1].dependencies if cached else self._read_dependencies(
            registration, row.binding,
        )
        try:
            self._current(registration, row.binding, dependencies, "confirm", chat, assembler)
        except DispatchDenied:
            self.retire(registration, conversation, incoming.original_key)
            raise
        now = self.clock()
        if now >= row.expires:
            self.retire(registration, conversation, incoming.original_key)
            raise DispatchExpired
        if incoming.confirmation != wire_digest(row.claims) or incoming.preview_sig != row.signature:
            raise DispatchConflict
        preview = verify(
            self.preview_key.public_key(), incoming.preview_sig, row.claims, PreviewClaims,
            issuer=self.issuer, audience=row.binding.app, kid=self.preview_kid, now=now,
        )
        if (
            preview.binding_sha256 != wire_digest(canonical(row.binding))
            or preview.payload_sha256 != row.payload_hash
            or preview.expires != row.expires
        ):
            raise DispatchDenied
        body_hash = wire_digest(raw)
        if row.body_hash is not None:
            if body_hash != row.body_hash:
                raise DispatchConflict
            return
        if cached is None or (
            cached[1].binding != row.binding or cached[1].claims != row.claims
            or wire_digest(cached[1].payload) != preview.payload_sha256
        ):
            raise DispatchExpired
        prepared = cached[1]
        if not self.journal.claim(key, body_hash):
            joined = self.journal.read(key)
            if joined is None or joined.body_hash != body_hash:
                raise DispatchConflict
            return
        self.retire(registration, conversation, incoming.original_key)
        row = self.journal.read(key)
        arguments = self._root_arguments(row)
        try:
            self.plans.attempts.claim_binding(**arguments)

            def authorize(phase):
                self._current(registration, row.binding, dependencies, phase, chat, assembler)
                if not self.plans.attempts.binding_current(**arguments):
                    raise DispatchUnavailable

            release = ReleaseClaims(
                v=VERSION, purpose="release", issuer=self.issuer,
                audience=registration.runtime.issuer, kid=registration.runtime.release_kid,
                binding_sha256=preview.binding_sha256, expires=preview.expires,
                body_sha256=body_hash, payload_sha256=preview.payload_sha256,
                root=row.binding.root, attempt=row.binding.attempt, nonce=str(uuid4()),
            )
            result = registration.runtime.deliver(
                target=registration.target, binding=row.binding, release=canonical(release),
                signature=sign(self.release_key, release), release_payload=lambda: prepared.payload,
                authorize=authorize, clock=self.clock,
                mark_started=lambda: self.journal.mark_started(key),
            )
            now = self.clock()
            terminal = self._terminal(registration, row, *result, now=now)
            self.journal.complete(
                key, *result, committed_at=now, message_id=terminal.message_id,
                authorize=lambda: authorize("disclose"),
            )
        except (
            BridgeDenied, ContextPreparationError, ConversationConflictError, DispatchDenied,
            InvalidSignature, LocalStoreError, OSError, ValueError,
        ):
            # A committed claim is not retryable, including after transport ambiguity.
            raise DispatchUnavailable from None

    def _terminal(self, registration, row, body, signature, result, *, now):
        if type(result) is not str or not 0 < len(result.encode("utf-8")) <= 100:
            raise DispatchDenied
        runtime = registration.runtime
        terminal = verify(
            runtime.terminal_key.public_key(), signature, body, TerminalClaims,
            issuer=runtime.issuer, audience=self.issuer, kid=runtime.terminal_kid, now=now,
        )
        if (
            terminal.binding_sha256, terminal.root, terminal.attempt, terminal.body_sha256,
            terminal.result_sha256, terminal.expires,
        ) != (
            wire_digest(canonical(row.binding)), row.binding.root, row.binding.attempt,
            row.body_hash, wire_digest(result.encode("utf-8")), row.expires,
        ):
            raise DispatchDenied
        return terminal

    def inspect(self, registration, conversation, original_key, chat, assembler, *, detail):
        key = self.key(registration, conversation, original_key)
        row = self.journal.read(key)
        if row is None:
            raise DispatchDenied
        self._require_scoped_binding(registration, row.binding, conversation, original_key)
        dependencies = self._read_dependencies(registration, row.binding)
        self._current(registration, row.binding, dependencies, "disclose", chat, assembler)
        disclosed_binding = row.binding
        row = self.journal.read(key)
        if row is None or row.binding != disclosed_binding:
            raise DispatchUnavailable
        if row.state in {"send_started", "completed"} and not self._fences_current(registration, row):
            raise DispatchUnavailable
        terminal = None
        if row.state == "completed":
            terminal = self._terminal(
                registration, row, row.terminal, row.terminal_signature, row.result,
                now=row.committed_at,
            )
            if terminal.message_id != row.message_id:
                raise DispatchUnavailable
        if detail:
            if row.state != "completed":
                raise DispatchDenied
            result = {
                "message_id": row.message_id, "attempt": row.binding.attempt, "root": row.binding.root,
                "original_key": row.binding.original_key, "result": row.result,
            }
        else:
            result = {
                "state": row.state, "original_key": row.binding.original_key, "attempt": row.binding.attempt,
                "root": row.binding.root, "body_sha256": row.body_hash,
                "message_id": row.message_id if terminal else None,
                "terminal": terminal.model_dump(mode="json") if terminal else None,
                "signature": row.terminal_signature if terminal else None,
            }
        encoded = canonical(result)
        self._current(registration, row.binding, dependencies, "disclose", chat, assembler)
        return encoded, row.committed_at if terminal else None

    def _fences_current(self, registration, row):
        if not self.plans.attempts.binding_current(**self._root_arguments(row), archived=True):
            return False
        runtime = registration.target.runtime._bridge
        return runtime.lifecycle.store.retained_fence_current(
            *fence_identity(row.binding, row.body_hash, row.payload_hash),
        )

"""One authorized local execution, with no cloud orchestration or fallback."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
import threading
import time
from dataclasses import dataclass, replace
from functools import partial
from typing import Literal, Protocol
from urllib.parse import urlsplit
from uuid import UUID, uuid4

import anyio
from pydantic import BaseModel, ConfigDict, Field

from personal_ai.auth.dispatch_grants import (
    DispatchGrantVerifier,
    LocalChatScope,
    SignedDispatchGrant,
)
from personal_ai.llm.chatgpt.oauth import REQUIRED_USAGE_SCOPES, OpenAIOAuth
from personal_ai.llm.chatgpt.responses import (
    PROVIDER,
    SERIALIZER,
    BridgeProviderFailure,
    ChatGPTResponses,
    serialize,
)
from personal_ai.llm.client import (
    ExecutionProvenance,
    GenerationEvent,
    GenerationMetadata,
    ProviderErrorObservation,
    ProviderIdentity,
)
from personal_ai.llm.external import ExecutionProfileIdentity, PreparedExecution
from personal_ai.local_bridge.disclosure import CredentialEcho, LocalOutputGuard
from personal_ai.local_bridge.lifecycle import CredentialLifecycle
from personal_ai.routing.contracts import DataUsePolicy


class BridgeDenied(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class CompatibilityGate(BaseModel):
    """Injected fixture facts for an exact synthetic profile and registration."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    connection_id: UUID
    client_id: str = Field(min_length=1, max_length=200, repr=False)
    distribution: Literal["local_personal", "hosted_web_installed_bridge"]
    distribution_approval: str | None = Field(default=None, min_length=1, max_length=500)
    compatibility_reference: str = Field(min_length=1, max_length=500)
    plan_only_reference: str = Field(min_length=1, max_length=500)
    execution_profile: ExecutionProfileIdentity
    model_id: str = Field(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,199}$")
    plan_only_verified: bool = False
    valid_until: int = Field(ge=0, strict=True)
    verified_at: int = Field(ge=0, strict=True)
    data_use: DataUsePolicy

    @property
    def key(self):
        return (
            str(self.connection_id),
            self.execution_profile.endpoint.endpoint_profile_id,
            self.execution_profile.endpoint.profile_version,
            self.model_id,
        )

    def require_package(self, package, *, now):
        if (
            not self.plan_only_verified
            or self.connection_id != package.connection_id
            or self.execution_profile != package.execution_profile
            or self.model_id != package.model_id
            or not self.verified_at <= now < self.valid_until
            or self.valid_until - self.verified_at > 7 * 86400
            or self.distribution != "local_personal"
            or self.data_use.status != "approved"
        ):
            raise BridgeDenied("bridge_compatibility_unverified")
        rank = {"public": 0, "personal": 1, "sensitive": 2, "restricted": 3}
        if rank[package.effective_sensitivity] > rank[self.data_use.max_sensitivity]:
            raise BridgeDenied("bridge_disclosure_denied")


@dataclass(frozen=True, slots=True, repr=False)
class CallerSession:
    caller_id: UUID
    origin: str
    connection_id: UUID
    connection_revision: int
    authorization: str
    expires_at: int


@dataclass(frozen=True, slots=True)
class ReceiptStatus:
    status: str
    output_available: bool = False


@dataclass(frozen=True, slots=True, repr=False)
class LocalChatInstallation:
    """Trusted fixture pairing policy, supplied outside browser IPC."""

    scope: LocalChatScope
    origin: str
    host_id: str
    runtime_id: UUID
    signer_key_id: str
    connection_id: UUID
    connection_revision: int
    client_id: str
    account_issuer: str
    account_subject: str

    def require_registration(self, state, registration):
        if (
            state.host_id != self.host_id
            or state.runtime_id != str(self.runtime_id)
            or registration is None
            or (
                registration.connection_id,
                registration.revision,
                registration.client_id,
                registration.issuer,
                registration.subject,
            ) != (
                str(self.connection_id),
                self.connection_revision,
                self.client_id,
                self.account_issuer,
                self.account_subject,
            )
            or registration.state != "connected"
            or registration.refresh_pending
            or registration.credentials is None
            or not REQUIRED_USAGE_SCOPES.issubset(registration.credentials.scopes)
        ):
            raise BridgeDenied("bridge_connection_changed")


class ChatGPTPlanBridge(Protocol):
    """Consume a prepared signed package and return normalized local events."""

    def execute(
        self,
        package: PreparedExecution,
        proof: SignedDispatchGrant,
        *,
        origin: str,
        authorization: str,
    ): ...


def exact_origin(origin: str):
    try:
        port = urlsplit(origin).port
        if port and origin == f"http://127.0.0.1:{port}":
            return origin
    except ValueError:
        pass
    raise BridgeDenied("bridge_origin_invalid")


class LocalChatGPTBridge:
    def __init__(
        self,
        lifecycle: CredentialLifecycle,
        provider: ChatGPTResponses,
        verifier: DispatchGrantVerifier,
        *,
        installation: LocalChatInstallation,
        gates: tuple[CompatibilityGate, ...] = (),
        clock=time.time,
    ):
        self.lifecycle, self.provider, self.verifier = lifecycle, provider, verifier
        self.installation = installation
        self.origins = frozenset({exact_origin(installation.origin)})
        if (
            verifier.audience != installation.runtime_id
            or installation.signer_key_id not in verifier.keys
        ):
            raise BridgeDenied("bridge_admission_denied")
        self.gates = {gate.key: gate for gate in gates}
        if len(self.gates) != len(gates):
            raise BridgeDenied("bridge_gate_ambiguous")
        self.clock = clock
        self._sessions = {}
        self._session_lock = threading.Lock()

    def _require_offline_transport(self):
        oauth = self.lifecycle.oauth
        if not self.provider.has_fixture_transport or (
            isinstance(oauth, OpenAIOAuth) and not oauth.has_fixture_transport
        ):
            raise BridgeDenied("bridge_compatibility_unverified")

    def approve_pairing(self, origin: str, connection_id: str) -> CallerSession:
        """Local operator call only. HTTP has no unapproved pairing endpoint."""
        self._require_offline_transport()
        if origin not in self.origins:
            raise BridgeDenied("bridge_origin_denied")
        if connection_id != str(self.installation.connection_id):
            raise BridgeDenied("bridge_auth_required")
        with self.lifecycle.store.transaction() as tx:
            registration = tx.state.registrations.get(connection_id)
            self.installation.require_registration(tx.state, registration)
        session = CallerSession(
            uuid4(),
            origin,
            UUID(connection_id),
            self.installation.connection_revision,
            secrets.token_urlsafe(32),
            int(self.clock()) + 300,
        )
        with self._session_lock:
            self._sessions = {
                k: s for k, s in self._sessions.items() if s.expires_at > self.clock()
            }
            if len(self._sessions) >= 32:
                raise BridgeDenied("bridge_pairing_capacity")
            self._sessions[hashlib.sha256(session.authorization.encode()).hexdigest()] = session
        return session

    def authorize(self, origin, authorization) -> CallerSession:
        if origin not in self.origins or not isinstance(authorization, str):
            raise BridgeDenied("bridge_caller_denied")
        if not 32 <= len(authorization) <= 128:
            raise BridgeDenied("bridge_caller_denied")
        with self._session_lock:
            session = self._sessions.get(hashlib.sha256(authorization.encode()).hexdigest())
        if session is None or session.origin != origin or self.clock() >= session.expires_at:
            raise BridgeDenied("bridge_caller_denied")
        return session

    async def connection(self, *, origin, authorization):
        session = self.authorize(origin, authorization)
        connections = await anyio.to_thread.run_sync(self.lifecycle.connections)
        connection = next(
            (c for c in connections if c.connection_id == str(session.connection_id)), None
        )
        if connection is None or connection.revision != session.connection_revision:
            raise BridgeDenied("bridge_connection_changed")
        return connection

    async def models(self, *, origin, authorization):
        self._require_offline_transport()
        session = self.authorize(origin, authorization)
        snapshot = await anyio.to_thread.run_sync(
            partial(
                self.lifecycle.snapshot,
                str(session.connection_id),
                authorize=self.installation.require_registration,
            )
        )
        if snapshot.revision != session.connection_revision:
            raise BridgeDenied("bridge_connection_changed")
        models = await self.provider.discover(snapshot.access_token)
        guard = LocalOutputGuard(snapshot.protected_values)
        for model in models:
            guard.check(model.slug)
            guard.check(model.display_name)
        if not await anyio.to_thread.run_sync(
            self.lifecycle.current, snapshot.connection_id, snapshot.revision
        ):
            raise BridgeDenied("bridge_connection_changed")
        return models

    def _require_dispatch(self, package, proof, *, origin, authorization):
        self._require_offline_transport()
        session = self.authorize(origin, authorization)
        if (
            package.provider_id != PROVIDER
            or package.connection_id != session.connection_id
            or package.connection_revision != session.connection_revision
        ):
            raise BridgeDenied("bridge_admission_denied")
        now = int(self.clock())
        claims = self.verifier.verify(proof, package, caller_id=session.caller_id, now=now)
        if (
            claims.local_chat != self.installation.scope
            or not self.installation.scope.matches_package(package)
            or claims.key_id != self.installation.signer_key_id
        ):
            raise BridgeDenied("bridge_disclosure_denied")
        gate = self.gates.get(
            (
                str(package.connection_id),
                package.execution_profile.endpoint.endpoint_profile_id,
                package.execution_profile.endpoint.profile_version,
                package.model_id,
            )
        )
        if gate is None or gate.client_id != self.installation.client_id:
            raise BridgeDenied("bridge_compatibility_unverified")
        # Local policy denial must precede even a rotating credential refresh.
        gate.require_package(package, now=now)
        if not self.provider.supports_profile(package.execution_profile):
            raise BridgeDenied("bridge_execution_profile_unsupported")
        return session

    async def execute(self, package, proof, *, origin, authorization):
        session = self._require_dispatch(package, proof, origin=origin, authorization=authorization)
        messages = package.chat_messages()
        serialize(messages, package.model_id)
        send_started = False
        try:
            duration = min(
                package.timeout_seconds,
                proof.claims.expires_at - self.clock(),
                session.expires_at - self.clock(),
            )
            async with asyncio.timeout(duration):
                snapshot = await anyio.to_thread.run_sync(
                    partial(
                        self.lifecycle.snapshot,
                        str(package.connection_id),
                        package.timeout_seconds + 30,
                        authorize=self.installation.require_registration,
                        allow_refresh=proof.claims.routing_root is None,
                    )
                )
                if snapshot.revision != package.connection_revision:
                    raise BridgeDenied("bridge_connection_changed")
                guard = LocalOutputGuard(snapshot.protected_values)
                if proof.claims.routing_root is None:
                    models = await self.provider.discover(snapshot.access_token)
                    for model in models:
                        guard.check(model.slug)
                        guard.check(model.display_name)
                    if package.model_id not in {m.slug for m in models}:
                        raise BridgeDenied("bridge_model_unavailable")
                # Expiry and caller authority are rechecked before the durable pre-send claim.
                self._require_dispatch(package, proof, origin=origin, authorization=authorization)

                def authorize_send(state, registration):
                    self._require_dispatch(
                        package, proof, origin=origin, authorization=authorization
                    )
                    self.installation.require_registration(state, registration)
                    if (
                        registration.credentials.access_token != snapshot.access_token
                        or registration.credentials.expires_at <= self.clock()
                    ):
                        raise BridgeDenied("bridge_connection_changed")

                def fence_send():
                    # Own the claim and its cleanup in one worker even if the reader is cancelled.
                    store = self.lifecycle.store
                    identity, fingerprint = package.dispatch_identity, package.fingerprint
                    claim = store.claim(
                        identity,
                        fingerprint,
                        snapshot.connection_id,
                        snapshot.revision,
                        proof.claims.expires_at,
                        origin=session.origin,
                        now=int(self.clock()),
                    )
                    try:
                        store.mark_send_started(
                            identity,
                            fingerprint,
                            snapshot.connection_id,
                            snapshot.revision,
                            claim,
                            expires_at=min(proof.claims.expires_at, session.expires_at),
                            now=int(self.clock()),
                            authorize=authorize_send,
                        )
                    except BaseException:
                        store.release_pre_send(identity, fingerprint, claim)
                        raise

                await anyio.to_thread.run_sync(fence_send)
                send_started = True
                stream = self.provider.stream(
                    messages,
                    model=package.model_id,
                    access_token=snapshot.access_token,
                    connection_id=snapshot.connection_id,
                    invocation_id=str(package.reservation_id),
                    execution_profile=package.execution_profile,
                    max_output_bytes=package.max_output_bytes,
                    max_output_chars=package.max_output_chars,
                    timeout_seconds=package.timeout_seconds,
                )
                try:
                    async for event in stream:
                        if not await anyio.to_thread.run_sync(
                            self.lifecycle.current, snapshot.connection_id, snapshot.revision
                        ):
                            raise BridgeDenied("bridge_connection_changed")
                        if self.clock() >= min(proof.claims.expires_at, session.expires_at):
                            raise BridgeDenied("bridge_authorization_expired")
                        if event.kind == "delta":
                            safe_delta = guard.feed(event.delta)
                            if safe_delta:
                                yield GenerationEvent.text_delta(safe_delta)
                            continue
                        if event.kind == "terminal":
                            safe_tail = guard.finish()
                            if safe_tail:
                                yield GenerationEvent.text_delta(safe_tail)
                            metadata = _sanitize_provider_error(event.metadata, guard)
                            event = GenerationEvent.terminal(metadata)
                            await anyio.to_thread.run_sync(
                                self.lifecycle.observe_usage,
                                snapshot.connection_id,
                                snapshot.revision,
                                metadata.error_code,
                                metadata.status == "success",
                            )
                            if metadata.error_code not in {
                                "bridge_timeout_unknown",
                                "bridge_transport_unknown",
                                "bridge_terminal_missing",
                                "bridge_protocol_invalid",
                                "bridge_output_bound",
                            }:
                                await anyio.to_thread.run_sync(
                                    self.lifecycle.store.settle,
                                    package.dispatch_identity,
                                    metadata.status,
                                )
                        yield event
                finally:
                    await stream.aclose()
        except CredentialEcho:
            raise BridgeDenied("bridge_credential_echo") from None
        except BridgeProviderFailure as error:
            await anyio.to_thread.run_sync(
                self.lifecycle.observe_usage,
                str(package.connection_id),
                package.connection_revision,
                error.code,
            )
            raise
        except TimeoutError:
            code = "bridge_timeout_unknown" if send_started else "bridge_unavailable"
            raise BridgeDenied(code) from None

    async def reconcile(self, identity, fingerprint, *, origin, authorization):
        session = self.authorize(origin, authorization)
        status = await anyio.to_thread.run_sync(
            partial(
                self.lifecycle.store.reconcile,
                identity,
                fingerprint,
                str(session.connection_id),
                session.connection_revision,
                session.origin,
            )
        )
        return ReceiptStatus(status)

    async def acknowledge(self, identity, fingerprint, *, origin, authorization):
        session = self.authorize(origin, authorization)
        await anyio.to_thread.run_sync(
            partial(
                self.lifecycle.store.acknowledge,
                identity,
                fingerprint,
                str(session.connection_id),
                session.connection_revision,
                session.origin,
            )
        )
        return ReceiptStatus("acknowledged")


class FakeChatGPTPlanBridge:
    """Output-contract fake only; it does not model proof, caller or transport authority.

    Use LocalChatGPTBridge with synthetic provider/OAuth I/O for authorization and
    prepare/finalize integration tests.
    """

    def __init__(self, *, text="synthetic response", status="success"):
        self.text, self.status = text, status
        self._seen = set()

    async def execute(self, package, proof=None, *, origin="", authorization=""):
        if package.dispatch_identity in self._seen:
            raise BridgeDenied("dispatch_already_claimed")
        self._seen.add(package.dispatch_identity)
        provenance = ExecutionProvenance(
            "connected_provider",
            "bridge_observed",
            PROVIDER,
            package.model_id,
            str(package.connection_id),
        )
        if (
            len(self.text.encode()) > package.max_output_bytes
            or len(self.text) > package.max_output_chars
        ):
            yield GenerationEvent.terminal(
                GenerationMetadata(
                    "incomplete",
                    ProviderIdentity(PROVIDER, package.model_id, SERIALIZER),
                    error_code="bridge_output_bound",
                    provenance=provenance,
                )
            )
            return
        yield GenerationEvent.text_delta(self.text)
        yield GenerationEvent.terminal(
            GenerationMetadata(
                self.status,
                ProviderIdentity(PROVIDER, package.model_id, SERIALIZER),
                invocation_id=str(package.reservation_id),
                provenance=provenance,
            )
        )


def _sanitize_provider_error(metadata: GenerationMetadata, guard: LocalOutputGuard):
    observation = metadata.provider_error
    if observation is None:
        return metadata

    def safe(value):
        if value is None:
            return None
        try:
            guard.check(value)
        except CredentialEcho:
            return None
        return value

    sanitized = ProviderErrorObservation(
        status=observation.status,
        code=safe(observation.code),
        param=safe(observation.param),
        request_id=safe(observation.request_id),
        shape=observation.shape,
    )
    return replace(metadata, provider_error=sanitized)

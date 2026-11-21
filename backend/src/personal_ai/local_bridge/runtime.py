"""One authorized local execution, with no cloud orchestration or fallback."""

from __future__ import annotations

import asyncio
import hashlib
import json
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
    ApplicationPlanScope,
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
from personal_ai.storage.async_io import sync_call


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
        self.require_binding(
            package.connection_id, package.execution_profile, package.model_id,
            package.effective_sensitivity, now=now,
        )

    def require_binding(self, connection_id, profile, model_id, sensitivity, *, now):
        if (
            not self.plan_only_verified
            or self.connection_id != connection_id
            or self.execution_profile != profile
            or self.model_id != model_id
            or not self.verified_at <= now < self.valid_until
            or self.valid_until - self.verified_at > 7 * 86400
            or self.distribution != "local_personal"
            or self.data_use.status != "approved"
        ):
            raise BridgeDenied("bridge_compatibility_unverified")
        rank = {"public": 0, "personal": 1, "sensitive": 2, "restricted": 3}
        if rank[sensitivity] > rank[self.data_use.max_sensitivity]:
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

    scope: LocalChatScope | ApplicationPlanScope
    origin: str
    host_id: str
    runtime_id: UUID
    signer_key_id: str
    connection_id: UUID
    connection_revision: int
    client_id: str
    account_issuer: str
    account_subject: str

    @property
    def registration_binding(self):
        facts = (
            self.origin, self.host_id, str(self.runtime_id), self.signer_key_id,
            str(self.connection_id), self.connection_revision, self.client_id,
            self.account_issuer, self.account_subject,
        )
        return hashlib.sha256(json.dumps(facts, separators=(",", ":")).encode()).hexdigest()

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
        root_authority=None,
        clock=time.time,
    ):
        self.lifecycle, self.provider, self.verifier = lifecycle, provider, verifier
        self.installation = installation
        self.root_authority = root_authority
        self.origins = frozenset({exact_origin(installation.origin)})
        if (
            verifier.audience != installation.runtime_id
            or installation.signer_key_id not in verifier.keys
            or (
                isinstance(installation.scope, ApplicationPlanScope)
                and (
                    installation.scope.runtime_id != installation.runtime_id
                    or installation.scope.registration_binding != installation.registration_binding
                    or installation.scope.local_recipient != f"local:{installation.runtime_id}"
                    or installation.scope.model_recipient
                    != f"openai-responses:{installation.registration_binding}"
                )
            )
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

    def _require_dispatch(self, package, proof, *, origin, authorization, foreground_root=None):
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
        scope = self.installation.scope
        if foreground_root is not None and (
            not isinstance(scope, LocalChatScope) or claims.routing_root != foreground_root
        ):
            raise BridgeDenied("bridge_admission_denied")
        if isinstance(scope, ApplicationPlanScope):
            self._require_application_plan(claims)
            payload = serialize(package.chat_messages(), package.model_id)
            if claims.application_plan.provider_payload_sha256 != hashlib.sha256(payload).hexdigest():
                raise BridgeDenied("bridge_disclosure_denied")
        elif claims.local_chat != scope or claims.application_plan is not None:
            raise BridgeDenied("bridge_disclosure_denied")
        if (
            not scope.matches_package(package)
            or claims.key_id != self.installation.signer_key_id
        ):
            raise BridgeDenied("bridge_disclosure_denied")
        gate = self._gate(package.connection_id, package.execution_profile, package.model_id)
        # Local policy denial must precede even a rotating credential refresh.
        gate.require_package(package, now=now)
        if not self.provider.supports_profile(package.execution_profile):
            raise BridgeDenied("bridge_execution_profile_unsupported")
        if claims.routing_root is not None:
            self._authorize_root(claims.routing_root, package, claims, session)
        return session

    def _gate(self, connection_id, profile, model_id):
        key = (str(connection_id), profile.endpoint.endpoint_profile_id,
               profile.endpoint.profile_version, model_id)
        gate = self.gates.get(key)
        if gate is None or gate.client_id != self.installation.client_id:
            raise BridgeDenied("bridge_compatibility_unverified")
        return gate

    def _require_application_plan(self, claims):
        if (
            not isinstance(self.installation.scope, ApplicationPlanScope)
            or claims.application_plan is None
            or claims.application_plan.scope != self.installation.scope
            or claims.local_chat is not None
            or claims.routing_root is None
            or claims.key_id != self.installation.signer_key_id
            or claims.provider_id != PROVIDER
        ):
            raise BridgeDenied("bridge_disclosure_denied")

    def authorize_handoff(self, proof, profile, *, origin, authorization):
        """Authenticate the paired runtime using the signed envelope before plaintext delivery."""
        self._require_offline_transport()
        session = self.authorize(origin, authorization)
        now = int(self.clock())
        claims = self.verifier.verify_claims(proof, caller_id=session.caller_id, now=now)
        self._require_application_plan(claims)
        if claims.connection_id != session.connection_id or not self.provider.supports_profile(profile):
            raise BridgeDenied("bridge_admission_denied")
        self._gate(session.connection_id, profile, claims.model_id).require_binding(
            session.connection_id, profile, claims.model_id, claims.effective_sensitivity, now=now,
        )
        with self.lifecycle.store.transaction() as tx:
            self.installation.require_registration(
                tx.state, tx.state.registrations.get(str(session.connection_id))
            )
        self._authorize_root(claims.routing_root, None, claims, session)

    def _authorize_root(self, root_id, package, claims, session):
        """Require current trusted root state; a signed UUID alone grants nothing."""
        authority = self.root_authority
        try:
            allowed = authority is not None and authority.authorize(
                root_id=root_id,
                package=package,
                claims=claims,
                installation=self.installation,
                session=session,
            ) is True
        except Exception:  # noqa: BLE001 - authority errors must fail closed
            raise BridgeDenied("bridge_admission_denied") from None
        if not allowed:
            raise BridgeDenied("bridge_admission_denied")

    def execute(self, package, proof, *, origin, authorization):
        return self._execute(package, proof, origin=origin, authorization=authorization)

    async def _execute(self, package, proof, *, origin, authorization, foreground_root=None):
        """The in-process fixture can pin one approved local root and retain its fence."""
        plan = proof.claims.application_plan is not None
        retain_fence = plan or proof.claims.routing_root is not None
        worker = sync_call if plan else anyio.to_thread.run_sync
        require_dispatch = partial(
            self._require_dispatch,
            package,
            proof,
            origin=origin,
            authorization=authorization,
            foreground_root=foreground_root,
        )
        messages = package.chat_messages()
        serialize(messages, package.model_id)
        send_started = False
        try:
            loop = asyncio.get_running_loop()
            if plan:
                authorization_deadline = loop.time() + max(
                    0.0,
                    min(
                        package.timeout_seconds,
                        proof.claims.expires_at - self.clock(),
                    ),
                )
                async with asyncio.timeout_at(authorization_deadline):
                    session = await sync_call(require_dispatch)
            else:
                # Preserve the standalone v1 admission order and behavior.
                session = require_dispatch()
                authorization_deadline = loop.time() + max(
                    0.0,
                    min(
                        package.timeout_seconds,
                        proof.claims.expires_at - self.clock(),
                    ),
                )
            authorization_deadline = min(
                authorization_deadline,
                loop.time() + max(0.0, session.expires_at - self.clock()),
            )
            async with asyncio.timeout_at(authorization_deadline):
                if foreground_root is not None:
                    def require_registration():
                        with self.lifecycle.store.transaction() as tx:
                            self.installation.require_registration(
                                tx.state, tx.state.registrations.get(str(session.connection_id))
                            )

                    await worker(require_registration)
                snapshot = await worker(
                    partial(
                        self.lifecycle.snapshot,
                        str(package.connection_id),
                        package.timeout_seconds + 30,
                        authorize=self.installation.require_registration,
                    )
                )
                if snapshot.revision != package.connection_revision:
                    raise BridgeDenied("bridge_connection_changed")
                guard = LocalOutputGuard(snapshot.protected_values)
                models = await self.provider.discover(snapshot.access_token)
                for model in models:
                    guard.check(model.slug)
                    guard.check(model.display_name)
                if package.model_id not in {m.slug for m in models}:
                    raise BridgeDenied("bridge_model_unavailable")
                # Expiry and caller authority are rechecked before the durable pre-send claim.
                if plan:
                    await sync_call(require_dispatch)
                else:
                    require_dispatch()

                def authorize_send(state, registration):
                    require_dispatch()
                    self.installation.require_registration(state, registration)
                    if (
                        registration.credentials.access_token != snapshot.access_token
                        or registration.credentials.expires_at <= self.clock()
                        or (
                            retain_fence
                            and self.clock() >= min(proof.claims.expires_at, session.expires_at)
                        )
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
                            retain_fence=retain_fence,
                        )
                    except BaseException:
                        store.release_pre_send(identity, fingerprint, claim)
                        raise

                await worker(fence_send)
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
                        if not await worker(
                            self.lifecycle.current, snapshot.connection_id, snapshot.revision
                        ):
                            raise BridgeDenied("bridge_connection_changed")
                        if self.clock() >= min(proof.claims.expires_at, session.expires_at):
                            raise BridgeDenied("bridge_authorization_expired")
                        if retain_fence:
                            await worker(
                                self._authorize_root, proof.claims.routing_root,
                                package, proof.claims, session,
                            )
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
                            await worker(
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
                                await worker(
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
            await worker(
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

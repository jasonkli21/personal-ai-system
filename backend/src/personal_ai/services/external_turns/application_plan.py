"""Opt-in foreground continuation for an enrolled application and user runtime.

Only isolated composition supplies the pairing, recovery witness, and source and
memory authorities. Normal API startup does not compose this service.
"""

import hmac
import json
from collections.abc import AsyncIterator, Callable
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from threading import Lock
from time import monotonic
from typing import Literal, Protocol
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel, ConfigDict, Field

from personal_ai.auth.application_clients import (
    external_conversation_namespace,
    require_current_client_authority,
)
from personal_ai.auth.dispatch_grants import (
    ApplicationPlanDispatch,
    ApplicationPlanScope,
    SignedDispatchGrant,
)
from personal_ai.auth.scope import (
    ApplicationScope,
    current_request_scope,
    current_verified_principal,
)
from personal_ai.context.authority import (
    application_plan_source_binding,
    source_snapshot_is_application_plan,
    source_snapshots_current,
)
from personal_ai.context.providers import ContextPreparationError, ContextSelection
from personal_ai.contracts.context_references import ApplicationPlanSourceBinding
from personal_ai.contracts.execution import ContinuationRequest, continuation_message_id
from personal_ai.llm.client import GenerationEvent
from personal_ai.llm.disclosure import revalidate_disclosure
from personal_ai.llm.external import ExecutionProfileIdentity, PreparedExecution, PreparedMessage
from personal_ai.local_bridge.application_plan import PairedApplicationRuntime
from personal_ai.services.chat.service import BoundChatContext, ConfirmedLocalTurn
from personal_ai.services.external_turns.contracts import digest
from personal_ai.storage.async_io import sync_call
from personal_ai.storage.errors import ConversationConflictError

NO_AI = "context_no_ai_route"
MAX_PREVIEWS = 16
MAX_PREVIEWS_PER_CLIENT = 4
MAX_PREVIEW_SECONDS = 45
MAX_PAYLOAD_BYTES = 8192
MAX_PREVIEW_RESPONSE_BYTES = 8192
MAX_CONTEXT_BYTES = 8192
MAX_CONTEXT_TOKENS = 3072
MAX_OUTPUT_BYTES = 100


def encode_preview_response(value):
    """Encode the exact bounded JSON representation used by the private route."""
    def encode_datetime(item):
        if isinstance(item, datetime):
            return item.isoformat()
        raise TypeError("preview contains a non-JSON value")

    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        separators=(",", ":"),
        default=encode_datetime,
    ).encode("utf-8")

_active = ContextVar("current_application_plan_attempt", default=None)


class PlanChoice(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    mode: Literal["user_owned_plan"]
    confirmation: str | None = Field(default=None, pattern=r"^[a-f0-9]{64}$")


class PlanContinuation(BaseModel):
    """Private opt-in nested choice. The consumer-v1.2 reader rejects this shape."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    content: str = Field(min_length=1, max_length=20000)
    idempotency_key: UUID
    choice: PlanChoice

    def request(self):
        return ContinuationRequest(content=self.content, idempotency_key=self.idempotency_key)


class PlanDelivery(Protocol):
    def deliver(
        self, proof: SignedDispatchGrant, profile: ExecutionProfileIdentity,
        release: Callable[[], PreparedExecution],
    ) -> AsyncIterator[GenerationEvent]: ...


@dataclass(frozen=True)
class BoundPlanSource:
    """The operator-installed source selection on an isolated preview-only target."""

    target_id: str
    selection: ContextSelection


@dataclass(frozen=True, repr=False)
class PlanTarget:
    scope: ApplicationPlanScope
    runtime: PlanDelivery
    caller_id: UUID
    connection_id: UUID
    connection_revision: int
    profile: ExecutionProfileIdentity
    provider_id: str
    serialize_payload: Callable[[PreparedExecution], bytes]
    model: str
    source_provider_id: str
    preview_source: BoundPlanSource | None = None

    def preview_binding(self, principal, conversation_id):
        source = self.preview_source
        if source is None:
            return None
        if (
            principal is None
            or not principal.authenticated
            or principal.owner_id != self.scope.owner_id
            or f"{principal.issuer}|{principal.subject}" != self.scope.actor_id
            or source.selection.provider_id != self.source_provider_id
        ):
            raise ContextPreparationError(NO_AI)
        return ApplicationPlanSourceBinding(
            target_id=source.target_id,
            conversation_id=conversation_id,
            scope=ApplicationScope(
                application_id=self.scope.application_id, workspace_id=self.scope.workspace_id,
            ),
            owner_id=principal.owner_id,
            human_issuer=principal.issuer,
            human_subject=principal.subject,
            client_namespace=self.scope.client_namespace,
            runtime_recipient=self.scope.local_recipient,
            model_recipient=self.scope.model_recipient,
            target_fingerprint=digest([
                self.scope.model_dump(mode="json"), str(self.caller_id),
                str(self.connection_id), self.connection_revision,
                self.profile.model_dump(mode="json"), self.provider_id, self.model,
                self.source_provider_id,
            ]),
        )


@dataclass(frozen=True, repr=False)
class PlanPreview:
    context: BoundChatContext
    target: PlanTarget
    package: PreparedExecution
    dispatch: ApplicationPlanDispatch
    snapshots: tuple
    root_id: UUID
    original_key: UUID
    expires_at: datetime

    @property
    def confirmation(self):
        return digest(
            [
                self.package.fingerprint,
                self.dispatch.model_dump(mode="json"),
                str(self.root_id),
                str(self.original_key),
                str(self.target.caller_id),
                self.expires_at.isoformat(),
            ]
        )


@dataclass(frozen=True)
class _PreviewReservation:
    client: tuple[str, str]
    token: UUID


class PlanAttempts:
    """One-shot plan offer on the existing transactional routing-root store."""

    def __init__(
        self, observations, roots, *, recovery_current, record_claim, claim_current,
    ):
        self.observations = observations
        self.roots = roots
        self.recovery_current = recovery_current
        self.record_claim = record_claim
        self.claim_current = claim_current

    def claim(self, preview):
        owner = preview.target.scope.owner_id
        with self.observations.transaction(owner_id=owner) as connection:
            now = self.observations.current_time(connection)
            if self.recovery_current() is not True or now >= preview.expires_at:
                raise ContextPreparationError(NO_AI)
            row = self.roots.open_root(
                connection,
                root_id=preview.root_id,
                owner_id=owner,
                payload=preview.package.fingerprint,
                plan=preview.confirmation,
                deadline=preview.expires_at,
            )
            if row[3:] != (0, "open", None):
                raise ConversationConflictError("continuation_exists_inspect_canonical_state")
            self.roots.change_root(
                connection,
                root_id=preview.root_id,
                owner_id=owner,
                candidate=0,
                state="fenced",
                attempt_id=preview.dispatch.attempt_id,
            )
        # A crash before this independent write cannot release a package. A
        # restore after the write needs the same durable root to be present.
        self.record_claim(
            preview.root_id, owner, preview.dispatch.attempt_id, preview.package.fingerprint
        )
        if not self.current(preview):
            raise ContextPreparationError(NO_AI)

    def current(self, preview):
        owner = preview.target.scope.owner_id
        with self.observations.transaction(owner_id=owner) as connection:
            now = self.observations.current_time(connection)
            return (
                self.recovery_current() is True
                and self.claim_current(
                    preview.root_id,
                    owner,
                    preview.dispatch.attempt_id,
                    preview.package.fingerprint,
                ) is True
                and now < preview.expires_at
                and self.roots.root(connection, preview.root_id, owner)
                == (
                    preview.package.fingerprint,
                    preview.confirmation,
                    preview.expires_at,
                    0,
                    "fenced",
                    preview.dispatch.attempt_id,
                )
            )


class ApplicationPlanService:
    def __init__(
        self, *, signer, target_for_request, memory, attempts, clock=None,
        delivery_type: type[PlanDelivery] = PairedApplicationRuntime,
    ):
        self.signer = signer
        self.target_for_request = target_for_request
        self.memory = memory
        self.attempts = attempts
        self._delivery_type = delivery_type
        self.clock = clock or (lambda: datetime.now(UTC))
        self._previews = {}
        self._reservations = {}
        self._lock = Lock()

    def current_target(self):
        require_current_client_authority()
        scope = current_request_scope()
        client = external_conversation_namespace()
        if scope is None or client is None or self.attempts.recovery_current() is not True:
            raise ContextPreparationError(NO_AI)
        target = self.target_for_request(scope, client)
        if (
            target is None
            or type(target.runtime) is not self._delivery_type
            or (
                target.scope.owner_id,
                target.scope.actor_id,
                target.scope.application_id,
                target.scope.workspace_id,
                target.scope.client_namespace,
            )
            != (
                scope.owner_id,
                scope.acting_user_id,
                scope.application_id,
                scope.workspace_id,
                client,
            )
        ):
            raise ContextPreparationError(NO_AI)
        return target

    @staticmethod
    def _key(target, conversation_id, key):
        return target.scope, conversation_id, key

    @staticmethod
    def _intent(request, target):
        return digest(
            ["user-owned-plan", request.intent_digest, target.scope.model_dump(mode="json")]
        )

    def preview(self, chat, assembler, conversation_id, incoming):
        selection, _ = self.preview_with_source_revision(chat, assembler, conversation_id, incoming)
        return selection

    def preview_with_source_revision(
        self, chat, assembler, conversation_id, incoming, *, expected_target=None,
        attest: Callable[[bytes, PlanPreview], None] | None = None,
    ):
        if incoming.choice.confirmation is not None:
            raise ContextPreparationError(NO_AI)
        target = self.current_target()
        if expected_target is not None and target is not expected_target:
            raise ContextPreparationError(NO_AI)
        binding = target.preview_binding(current_verified_principal(), conversation_id)
        token = application_plan_source_binding.set(binding)
        try:
            return self._preview(
                chat, assembler, conversation_id, incoming.request(), target, binding, attest
            )
        finally:
            application_plan_source_binding.reset(token)

    def _preview(self, chat, assembler, conversation_id, request, target, binding, attest):
        assistant_id = continuation_message_id(
            conversation_id,
            target.scope.owner_id,
            current_request_scope(),
            request.idempotency_key,
        )
        key = self._key(target, conversation_id, request.idempotency_key)
        started = monotonic()
        reservation = self._reserve_preview(key, target)
        try:
            pending_user_id = uuid5(assistant_id, "user")

            def prepare_sources(plan, application_context, deadline):
                selections = plan.selections
                if (
                    len(selections) != 2
                    or {item.provider_id for item in selections}
                    != {target.source_provider_id, "ai_memory"}
                    or any(item.max_results != 1 for item in selections)
                    or sum(item.max_bytes for item in selections) > MAX_CONTEXT_BYTES
                    or sum(item.max_tokens for item in selections) > MAX_CONTEXT_TOKENS
                ):
                    raise ContextPreparationError(NO_AI)
                return self.memory.retrieve(application_context, deadline)

            context = chat.preview_bound_context(
                conversation_id,
                request.content,
                assembler=assembler,
                prepare_sources=prepare_sources,
                user_id=pending_user_id,
                plan_source_selections=(target.preview_source.selection,) if binding else (),
            )
            assembled = context.assembled
            manifest = assembled.manifest
            if manifest is None:
                raise ContextPreparationError(NO_AI)
            selected_ids = set(assembled.selected_message_ids)
            if pending_user_id not in selected_ids:
                raise ContextPreparationError(NO_AI)
            prior_message_count = len(selected_ids - {pending_user_id})
            if prior_message_count % 2 or prior_message_count > MAX_CONTEXT_TOKENS * 2:
                raise ContextPreparationError(NO_AI)
            prior_turn_count = prior_message_count // 2
            included = {
                (item.provider_id, item.source_id, item.item_id)
                for item in manifest.items
                if item.injected
            }
            items = tuple(
                item
                for item in assembled.source_items
                if (item.provider_id, item.source_id, item.item_id) in included
            )
            if {item.provider_id for item in items} != {target.source_provider_id, "ai_memory"} or (
                len(items) != 2
                or sum(
                    len((item.disclosed_payload or item.payload).model_dump_json().encode())
                    for item in items
                )
                > MAX_CONTEXT_BYTES
                or assembled.budget.source_tokens > MAX_CONTEXT_TOKENS
                or monotonic() >= started + assembler.settings.request_timeout_seconds
            ):
                raise ContextPreparationError(NO_AI)
            snapshots = tuple(item.authority_snapshot() for item in items)
            domain = next(snapshot for snapshot in snapshots if snapshot.provider_id != "ai_memory")
            memory = next(snapshot for snapshot in snapshots if snapshot.provider_id == "ai_memory")
            authority = domain.application_plan_authority
            if memory.source_version != "application-plan-memory:v1" or (
                binding is None and (
                    authority is not None
                    or not domain.source_version.startswith("shared-source:application-plan:")
                )
            ) or (
                binding is not None and (
                    authority is None or authority.binding != binding
                    or authority.fields != target.preview_source.selection.fields
                )
            ):
                raise ContextPreparationError(NO_AI)
            now = self.clock()
            expires_at = min(
                now + timedelta(seconds=MAX_PREVIEW_SECONDS),
                *(snapshot.expires_at for snapshot in snapshots if snapshot.expires_at is not None),
                *((authority.expires_at,) if authority is not None else ()),
            )
            messages = tuple(
                PreparedMessage(role=message.role, content=message.content)
                for message in assembled.messages
            )
            inference = context.inference
            output_limit = min(MAX_OUTPUT_BYTES, assembler.settings.max_response_tokens)
            package = PreparedExecution(
                application_id=target.scope.application_id,
                workspace_id=target.scope.workspace_id,
                owner_id=target.scope.owner_id,
                conversation_id=conversation_id,
                reservation_id=assistant_id,
                branch_digest=context.branch_digest,
                source_authority_digest=digest(
                    [
                        [
                            item.observed_at.isoformat() if item.observed_at else None,
                            snapshot.model_dump(mode="json"),
                        ]
                        for item, snapshot in zip(items, snapshots)
                    ]
                ),
                provider_id=target.provider_id,
                model_id=target.model,
                execution_profile=target.profile,
                connection_id=target.connection_id,
                connection_revision=target.connection_revision,
                messages=messages,
                effective_sensitivity=inference.effective_sensitivity,
                maximum_sensitivity=inference.maximum_sensitivity,
                policy_version=inference.policy_version,
                max_output_bytes=output_limit,
                max_output_chars=output_limit,
                timeout_seconds=max(1, int(assembler.settings.request_timeout_seconds)),
            )
            payload = target.serialize_payload(package)
            if (
                type(payload) is not bytes
                or not 0 < len(payload) <= MAX_PAYLOAD_BYTES
                or len(package.canonical()) > MAX_PAYLOAD_BYTES
            ):
                raise ContextPreparationError(NO_AI)
            root_id = uuid5(assistant_id, "application-plan-routing-root")
            preview = PlanPreview(
                context,
                target,
                package,
                ApplicationPlanDispatch(
                    scope=target.scope,
                    attempt_id=uuid5(root_id, "foreground"),
                    intent_sha256=self._intent(request, target),
                    provider_payload_sha256=sha256(payload).hexdigest(),
                ),
                snapshots,
                root_id,
                request.idempotency_key,
                expires_at,
            )
            self._require_current(preview, assembler.permission_revalidator)
            if binding is not None and (
                self.clock() >= preview.expires_at
                or monotonic() >= started + assembler.settings.request_timeout_seconds
            ):
                raise ContextPreparationError(NO_AI)
            selection = {
                "confirmation": preview.confirmation,
                "destination": {
                    "application": target.scope.application_id,
                    "provider": "ChatGPT",
                    "model": target.model,
                    "runtime": target.scope.local_recipient,
                    "recipient": target.scope.model_recipient,
                },
                "purpose": "foreground_application_plan",
                "selected_context": [
                    {"category": "conversation_history", "turns": prior_turn_count},
                    *(
                        {
                            "category": item.source_class,
                            "fields": sorted(
                                (item.disclosed_payload or item.payload).model_dump(exclude_none=True)
                            ),
                        }
                        for item in items
                    ),
                ],
                "input_tokens_estimated": assembled.budget.selected_total,
                "expires_at": expires_at,
            }
            try:
                encoded_selection = encode_preview_response(selection)
            except (TypeError, ValueError, OverflowError):
                raise ContextPreparationError(NO_AI) from None
            if len(encoded_selection) > MAX_PREVIEW_RESPONSE_BYTES:
                raise ContextPreparationError(NO_AI)
            if attest is not None:
                attest(encoded_selection, preview)
                if self.clock() >= preview.expires_at:
                    raise ContextPreparationError(NO_AI)
            self._publish_preview(key, reservation, preview)
            return selection, domain.source_version if binding is not None else None
        finally:
            self._release_preview_reservation(key, reservation)

    def _reserve_preview(self, key, target):
        now = self.clock()
        client = (target.scope.owner_id, target.scope.client_namespace)
        with self._lock:
            self._previews = {
                existing: preview
                for existing, preview in self._previews.items()
                if now < preview.expires_at
            }
            if key in self._reservations:
                raise ContextPreparationError(NO_AI)
            occupied = set(self._previews) | set(self._reservations)
            if key not in occupied:
                if len(occupied) >= MAX_PREVIEWS:
                    raise ContextPreparationError(NO_AI)
                client_keys = {
                    existing
                    for existing, preview in self._previews.items()
                    if (preview.target.scope.owner_id, preview.target.scope.client_namespace)
                    == client
                }
                client_keys.update(
                    existing
                    for existing, reservation in self._reservations.items()
                    if reservation.client == client
                )
                if len(client_keys) >= MAX_PREVIEWS_PER_CLIENT:
                    raise ContextPreparationError(NO_AI)
            reservation = _PreviewReservation(client, uuid4())
            self._reservations[key] = reservation
            return reservation

    def _publish_preview(self, key, reservation, preview):
        with self._lock:
            if self._reservations.get(key) != reservation:
                raise ContextPreparationError(NO_AI)
            self._previews[key] = preview
            self._reservations.pop(key, None)

    def _release_preview_reservation(self, key, reservation):
        with self._lock:
            if self._reservations.get(key) == reservation:
                self._reservations.pop(key, None)

    def continue_turn(self, chat, assembler, conversation_id, incoming):
        target = self.current_target()
        if target.preview_source is not None:
            raise ContextPreparationError(NO_AI)
        request = incoming.request()
        confirmation = incoming.choice.confirmation
        if confirmation is None:
            raise ConversationConflictError("application_plan_confirmation_required")
        intent = self._intent(request, target)
        confirmed_intent = digest([intent, confirmation])
        replay = chat.replay_bound_turn(conversation_id, request, intent_digest=confirmed_intent)
        if replay is not None:
            return replay
        key = self._key(target, conversation_id, request.idempotency_key)
        with self._lock:
            preview = self._previews.get(key)
            if (
                preview is None
                or not hmac.compare_digest(preview.confirmation, confirmation)
                or intent != preview.dispatch.intent_sha256
                or any(source_snapshot_is_application_plan(snapshot) for snapshot in preview.snapshots)
            ):
                raise ConversationConflictError("application_plan_confirmation_required")
            self._previews.pop(key)
        self._require_current(preview, assembler.permission_revalidator)
        generation = _PlanGeneration(self, preview, assembler.permission_revalidator)
        return chat.continue_turn(
            conversation_id,
            request,
            confirmed_local=ConfirmedLocalTurn(
                context=preview.context,
                intent_digest=confirmed_intent,
                generation=generation,
                connection_id=target.connection_id,
                connection_revision=target.connection_revision,
                package_fingerprint=preview.package.fingerprint,
            ),
        )

    def _require_current(self, preview, permissions):
        if self.current_target() != preview.target or (
            self.clock() >= preview.expires_at
            or not source_snapshots_current(preview.snapshots, permissions, now=self.clock())
        ):
            raise ContextPreparationError("context_source_authority_changed")

    def authorize(self, *, root_id, package, claims, installation, session):
        """Injected synchronous current authority used under the local send-start lock."""
        return self.authorize_delivery(
            root_id=root_id, package=package, claims=claims,
            scope=installation.scope, caller_id=session.caller_id,
        )

    def authorize_delivery(self, *, root_id, package, claims, scope, caller_id):
        """Revalidate a bound delivery using only the owning request's live authority."""
        active = _active.get()
        if active is None:
            return False
        preview, permissions = active
        if (
            root_id != preview.root_id
            or claims.application_plan != preview.dispatch
            or claims.package_hash != preview.package.fingerprint
            or caller_id != preview.target.caller_id
            or scope != preview.target.scope
            or (package is not None and package.fingerprint != preview.package.fingerprint)
        ):
            return False
        self._require_current(preview, permissions)
        revalidate_disclosure()
        return self.attempts.current(preview)


@dataclass(frozen=True, repr=False)
class _PlanGeneration:
    service: ApplicationPlanService
    preview: PlanPreview
    permissions: object

    async def stream_events(
        self, messages, *, max_output_tokens, timeout_seconds, inference_context
    ):
        service, preview = self.service, self.preview
        package, target = preview.package, preview.target
        if tuple(messages) != package.chat_messages() or (
            inference_context != package.inference_context()
            or max_output_tokens < package.max_output_bytes
            or timeout_seconds <= 0
        ):
            raise ContextPreparationError(NO_AI)

        def current():
            revalidate_disclosure()
            service._require_current(preview, self.permissions)

        def claim():
            current()
            service.attempts.claim(preview)
            now = service.clock()
            return service.signer.sign(
                package,
                caller_id=target.caller_id,
                audience=target.scope.runtime_id,
                now=now,
                expires_at=min(preview.expires_at, now + timedelta(seconds=timeout_seconds)),
                routing_root=preview.root_id,
                application_plan=preview.dispatch,
            )

        def release():
            current()
            if not service.attempts.current(preview):
                raise ContextPreparationError(NO_AI)
            return package

        token = _active.set((preview, self.permissions))
        try:
            proof = await sync_call(claim)
            stream = target.runtime.deliver(proof, target.profile, release)
            try:
                async for event in stream:
                    await sync_call(current)
                    if (
                        event.kind == "terminal"
                        and event.metadata.usage
                        and ((event.metadata.usage.output_tokens or 0) > max_output_tokens)
                    ):
                        raise ContextPreparationError(NO_AI)
                    yield event
            finally:
                await stream.aclose()
        except (ValueError, LookupError, RuntimeError):
            raise ContextPreparationError(NO_AI) from None
        finally:
            _active.reset(token)

"""External execution orchestration over the shared chat preparation/transaction seam.

Not composed into HTTP routes until membership/revocation and bridge live gates pass.
No credentials, accounts, raw errors, reset guesses, or P19 quota claims enter this service.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol
from uuid import UUID, uuid5

from personal_ai.applications.contracts import SENSITIVITY_RANK, ApplicationContextRequest
from personal_ai.auth.dispatch_grants import DispatchGrantSigner, SignedDispatchGrant
from personal_ai.auth.scope import scope_matches
from personal_ai.context.authorization import (
    authorize_base_disclosure,
    authorize_effective_sensitivity,
)
from personal_ai.context.contracts import fingerprint
from personal_ai.contracts.context_references import (
    ContextSourceSnapshot,
)
from personal_ai.contracts.execution import ContinuationRequest, ExecutionChoice
from personal_ai.entities import Message, MessageStatus
from personal_ai.entities.turn_execution import TurnAttribution, TurnReservation
from personal_ai.llm.client import ExternalCompletion
from personal_ai.llm.external import ExecutionProfileIdentity, PreparedExecution, PreparedMessage
from personal_ai.routing.contracts import EndpointRef
from personal_ai.routing.registry import EndpointRegistry
from personal_ai.services.chat_turns import ChatTurnService
from personal_ai.storage.errors import ConversationConflictError, ResourceNotFoundError


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class PreparedExternalTurn:
    message_id: UUID
    reservation: TurnReservation
    messages: tuple[PreparedMessage, ...]
    connected_package: PreparedExecution | None
    count_kind: Literal["estimated"] = "estimated"

    @property
    def portable_prompt(self) -> str:
        return "\n\n".join(f"{m.role}:\n{m.content}" for m in self.messages)


class ExternalTurnAuthority(Protocol):
    """Registered policy integration; must check principal membership and all dependencies.

    Snapshot is content-derived from current source/grant revisions, never client labels.
    No permissive production default exists. The integration must retain/recheck every
    selected dependency, including history/summary derivations (P15 acceptance gate).
    """

    def snapshot(
        self,
        context: ApplicationContextRequest,
        conversation_id: UUID,
        choice: ExecutionChoice,
        source_message_ids: tuple[UUID, ...],
        source_snapshots: tuple[ContextSourceSnapshot, ...],
    ) -> str: ...


class ExternalTurnService:
    def __init__(
        self,
        *,
        chat: ChatTurnService,
        context: ApplicationContextRequest,
        registry: EndpointRegistry,
        authority: ExternalTurnAuthority,
        signer: DispatchGrantSigner | None = None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        chat.require_context(context)
        self.chat, self.context, self.registry = chat, context, registry
        self.authority, self.signer, self.clock = authority, signer, clock

    def _profile(self, choice: ExecutionChoice, sensitivity: str):
        profile = next(
            (p for p in self.registry.refresh().profiles if p.ref == choice.endpoint), None
        )
        if (
            profile is None
            or not profile.enabled
            or profile.access_policy is None
            or profile.access_policy.selection_mode != "explicit_only"
            or profile.access_policy.credential_runtime != "user_local"
            or "streaming" not in profile.capabilities
        ):
            raise ConversationConflictError("explicit_endpoint_unavailable")
        policy = profile.data_use_policy
        if (
            SENSITIVITY_RANK[sensitivity] > SENSITIVITY_RANK[policy.max_sensitivity]
            or policy.status != "approved"
        ):
            raise ConversationConflictError("provider_disclosure_denied")
        return profile

    def _snapshot(self, conversation_id, choice, sources, snapshots=()):
        self.chat.require_context(self.context)
        authorize_base_disclosure(self.context)
        if choice.mode not in self.context.definition.context_policy.external_execution_modes:
            raise ConversationConflictError("execution_disclosure_denied")
        value = self.authority.snapshot(self.context, conversation_id, choice, sources, snapshots)
        if len(value) != 64 or any(c not in "0123456789abcdef" for c in value):
            raise ConversationConflictError("authority_snapshot_invalid")
        return digest(
            {
                "authority": value,
                "source_message_ids": [str(source) for source in sources],
                "source_snapshots": [snapshot.model_dump(mode="json") for snapshot in snapshots],
                "policy": self.context.definition.context_policy.model_dump(mode="json"),
                "application": self.context.scope.application_id,
                "workspace": self.context.scope.workspace_id,
                "owner": self.context.scope.owner_id,
            }
        )

    def prepare(self, conversation_id: UUID, request: ContinuationRequest) -> PreparedExternalTurn:
        choice = request.choice
        if choice.mode == "automatic":
            raise ConversationConflictError("automatic_execution_uses_existing_routing_lane")
        now = self.clock()
        self._snapshot(conversation_id, choice, ())  # Before any read/count/disclosure.
        identity = uuid5(
            conversation_id,
            f"{self.context.scope.owner_id}:{self.context.scope.application_id}:{self.context.scope.workspace_id}:{request.idempotency_key}",
        )
        request_hash = digest(request.model_dump(mode="json"))
        try:
            existing = self.chat.get_message(conversation_id, identity)
        except ResourceNotFoundError:
            pass
        else:
            if existing.execution is None or existing.execution.request_digest != request_hash:
                raise ConversationConflictError("idempotency_input_changed")
            # Prompt bodies are transient. Existing sends cannot be recreated/re-dispatched.
            raise ConversationConflictError("reservation_exists_inspect_or_finalize")
        result = []

        def bind(assistant, assembled, inference, active):
            if inference is None:
                raise ConversationConflictError("authorized_inference_context_required")
            selected = tuple(
                dict.fromkeys(
                    (
                        *assembled.selected_message_ids,
                        *(assembled.summary.source_message_ids if assembled.summary else ()),
                    )
                )
            )
            injected = {
                (item.source_id, item.item_id) for item in assembled.manifest.items if item.injected
            }
            items = [
                item
                for item in assembled.source_items
                if (item.source_id, item.item_id) in injected
            ]
            snapshots = tuple(item.authority_snapshot() for item in items)
            authority = self._snapshot(conversation_id, choice, selected, snapshots)
            branch = fingerprint(active, include_state=True)
            messages = tuple(
                PreparedMessage(role=m.role, content=m.content) for m in assembled.messages
            )
            package = None
            profile = None
            provider, model = choice.declared_provider, choice.declared_model
            if choice.mode == "connected_provider":
                profile = self._profile(choice, inference.effective_sensitivity)
                if (
                    profile.context_limit_tokens is None
                    or assembled.budget.selected_total > profile.context_limit_tokens
                ):
                    raise ConversationConflictError(
                        "provider_context_budget_unavailable_or_exceeded"
                    )
                provider, model = profile.provider_id, profile.model_id
                package = PreparedExecution(
                    owner_id=self.context.scope.owner_id,
                    application_id=self.context.scope.application_id,
                    workspace_id=self.context.scope.workspace_id,
                    conversation_id=conversation_id,
                    reservation_id=identity,
                    branch_digest=branch,
                    source_authority_digest=authority,
                    provider_id=provider,
                    model_id=model,
                    execution_profile=ExecutionProfileIdentity(
                        endpoint=profile.ref,
                        endpoint_id=profile.endpoint_id,
                        deployment_id=profile.deployment_id,
                        serializer_id=profile.serializer_id,
                        runtime_id=profile.runtime_id,
                    ),
                    connection_id=choice.connection_id,
                    connection_revision=choice.connection_revision,
                    messages=messages,
                    effective_sensitivity=inference.effective_sensitivity,
                    maximum_sensitivity=inference.maximum_sensitivity,
                    policy_version=inference.policy_version,
                    max_output_bytes=80000,
                    timeout_seconds=120,
                )
            package_hash = (
                package.fingerprint
                if package
                else digest(
                    {
                        "scope": self.context.scope.model_dump(mode="json", exclude={"request_id"}),
                        "reservation": str(identity),
                        "branch": branch,
                        "authority": authority,
                        "choice": choice.model_dump(mode="json"),
                        "messages": [m.model_dump() for m in messages],
                        "policy": inference.policy_version,
                        "sensitivity": inference.effective_sensitivity,
                        "max_output_bytes": 80000,
                    }
                )
            )
            reservation = TurnReservation(
                reservation_id=identity,
                request_digest=request_hash,
                mode=choice.mode,
                package_fingerprint=package_hash,
                branch_digest=branch,
                authority_digest=authority,
                policy_version=inference.policy_version,
                effective_sensitivity=inference.effective_sensitivity,
                expires_at=now + timedelta(seconds=120),
                max_output_bytes=80000,
                provider_id=provider,
                model_id=model,
                connection_id=choice.connection_id,
                connection_revision=choice.connection_revision,
                caller_id=choice.caller_id,
                audience=choice.audience,
                source_message_ids=selected,
                source_snapshots=snapshots,
                endpoint_profile_id=profile.endpoint_profile_id if profile else None,
                profile_version=profile.profile_version if profile else None,
                profile_digest=digest(profile.model_dump(mode="json")) if profile else None,
            )
            result.append(PreparedExternalTurn(identity, reservation, messages, package))
            return assistant.model_copy(
                update={"execution": reservation, "status": MessageStatus.PENDING}
            )

        self.chat.prepare_external(
            conversation_id,
            request.content,
            request_id=self.context.scope.request_id,
            assistant_id=identity,
            user_id=uuid5(identity, "user"),
            preparation_hook=bind,
            candidate_message_ids=request.candidate_message_ids,
            history_authorizer=lambda ids: self._snapshot(conversation_id, choice, ids),
        )
        return result[0]

    def _current(self, conversation_id, message_id, package_hash):
        message = self.chat.get_message(conversation_id, message_id)
        reservation = message.execution
        if (
            reservation is None
            or reservation.package_fingerprint != package_hash
            or not scope_matches(message, self.context.scope)
        ):
            raise ConversationConflictError("reservation_binding_invalid")
        if message.owner_id != self.context.scope.owner_id:
            raise ConversationConflictError("reservation_owner_invalid")
        if message.status == MessageStatus.SUPERSEDED:
            raise ConversationConflictError("reservation_superseded")
        return message, reservation

    def _recheck(self, conversation_id, reservation, choice):
        authorize_effective_sensitivity(self.context, reservation.effective_sensitivity)
        if any(
            s.expires_at is not None and self.clock() >= s.expires_at
            for s in reservation.source_snapshots
        ):
            raise ConversationConflictError("prepared_source_expired")
        if (
            self.context.definition.context_policy.version != reservation.policy_version
            or self._snapshot(
                conversation_id,
                choice,
                reservation.source_message_ids,
                reservation.source_snapshots,
            )
            != reservation.authority_digest
        ):
            raise ConversationConflictError("source_authority_changed")
        if self.clock() >= reservation.expires_at:
            raise ConversationConflictError("reservation_expired")

    def dispatch(
        self, conversation_id: UUID, prepared: PreparedExternalTurn, choice: ExecutionChoice
    ) -> SignedDispatchGrant:
        message, reservation = self._current(
            conversation_id, prepared.message_id, prepared.reservation.package_fingerprint
        )
        if (
            reservation.mode != "connected_provider"
            or reservation.state != "prepared"
            or prepared.connected_package is None
            or prepared.connected_package.fingerprint != reservation.package_fingerprint
            or choice.caller_id != reservation.caller_id
            or choice.audience != reservation.audience
            or choice.connection_id != reservation.connection_id
            or choice.connection_revision != reservation.connection_revision
        ):
            raise ConversationConflictError("dispatch_binding_invalid")
        self._recheck(conversation_id, reservation, choice)
        profile = self._profile(choice, reservation.effective_sensitivity)
        if (
            profile.ref != prepared.connected_package.execution_profile.endpoint
            or digest(profile.model_dump(mode="json")) != reservation.profile_digest
        ):
            raise ConversationConflictError("endpoint_changed")
        if self.signer is None:
            raise ConversationConflictError("dispatch_signer_unavailable")
        # Sign before CAS but return only after durable dispatch fencing. Failed writes never expose a grant.
        proof = self.signer.sign(
            prepared.connected_package,
            caller_id=reservation.caller_id,
            audience=reservation.audience,
            now=self.clock(),
            expires_at=reservation.expires_at,
        )
        self.chat.transition(
            message,
            message.model_copy(
                update={"execution": reservation.model_copy(update={"state": "dispatched"})}
            ),
        )
        return proof

    def finalize(
        self,
        conversation_id: UUID,
        message_id: UUID,
        package_hash: str,
        completion: ExternalCompletion,
        *,
        explicit_import: bool = False,
        latency_ms: int | None = None,
    ) -> Message:
        message, reservation = self._current(conversation_id, message_id, package_hash)
        provenance = completion.provenance
        if (
            provenance.mode != reservation.mode
            or provenance.provider_id != reservation.provider_id
            or provenance.model_id != reservation.model_id
            or (
                reservation.mode == "manual_external"
                and (not explicit_import or latency_ms is not None)
            )
            or (
                reservation.mode == "connected_provider"
                and provenance.connection_id != str(reservation.connection_id)
            )
        ):
            raise ConversationConflictError("completion_provenance_mismatch")
        if (
            not completion.text.strip()
            or len(completion.text) > 20000
            or len(completion.text.encode()) > reservation.max_output_bytes
        ):
            raise ConversationConflictError("completion_output_invalid")
        completion_hash = digest(
            {
                "text": completion.text,
                "provenance": provenance.__dict__
                if hasattr(provenance, "__dict__")
                else {
                    "mode": provenance.mode,
                    "source": provenance.fact_source,
                    "provider": provenance.provider_id,
                    "model": provenance.model_id,
                    "connection": provenance.connection_id,
                },
                "latency": latency_ms,
                "usage": None
                if completion.generation is None or completion.generation.usage is None
                else {
                    "input": completion.generation.usage.input_tokens,
                    "output": completion.generation.usage.output_tokens,
                    "source": completion.generation.usage.source,
                    "confidence": completion.generation.usage.confidence,
                },
            }
        )
        if reservation.state == "completed":
            self._snapshot(
                conversation_id,
                self._choice(reservation),
                reservation.source_message_ids,
                reservation.source_snapshots,
            )
            if reservation.completion_digest != completion_hash:
                raise ConversationConflictError("completion_replay_changed")
            return message
        if message.status != MessageStatus.PENDING or reservation.state != (
            "prepared" if reservation.mode == "manual_external" else "dispatched"
        ):
            raise ConversationConflictError("reservation_terminal_or_uncertain")
        self._recheck(conversation_id, reservation, self._choice(reservation))
        if reservation.mode == "connected_provider":
            profile = self._profile(self._choice(reservation), reservation.effective_sensitivity)
            if digest(profile.model_dump(mode="json")) != reservation.profile_digest:
                raise ConversationConflictError("endpoint_changed")
        usage = completion.generation.usage if completion.generation else None
        attribution = TurnAttribution(
            mode=reservation.mode,
            fact_source="user_declared"
            if reservation.mode == "manual_external"
            else "client_reported",
            provider_id=reservation.provider_id,
            model_id=reservation.model_id,
            recorded_at=self.clock(),
            latency_ms=latency_ms,
            usage_source=usage.source if usage else None,
            usage_confidence=usage.confidence if usage else None,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            package_fingerprint=package_hash,
            source_message_ids=reservation.source_message_ids,
            source_snapshots=reservation.source_snapshots,
        )
        return self._finalize_cas(
            completion_hash,
            message,
            message.model_copy(
                update={
                    "status": MessageStatus.COMPLETED,
                    "content": completion.text,
                    "model": reservation.model_id,
                    "attribution": attribution,
                    "execution": reservation.model_copy(
                        update={"state": "completed", "completion_digest": completion_hash}
                    ),
                }
            ),
        )

    def _finalize_cas(self, completion_hash, current, candidate):
        try:
            return self.chat.transition(current, candidate)
        except ConversationConflictError:
            latest = self.chat.get_message(current.conversation_id, current.id)
            if (
                latest.status == MessageStatus.COMPLETED
                and latest.execution is not None
                and latest.execution.completion_digest == completion_hash
            ):
                return latest
            raise

    def _choice(self, reservation):
        # Retained exact identity also supports historical replay after a provider disappears.
        if reservation.mode == "manual_external":
            return ExecutionChoice(
                mode="manual_external",
                declared_provider=reservation.provider_id,
                declared_model=reservation.model_id,
            )
        return ExecutionChoice(
            mode="connected_provider",
            endpoint=EndpointRef(
                endpoint_profile_id=reservation.endpoint_profile_id,
                profile_version=reservation.profile_version,
            ),
            connection_id=reservation.connection_id,
            connection_revision=reservation.connection_revision,
            caller_id=reservation.caller_id,
            audience=reservation.audience,
        )

    def report_failure(
        self,
        conversation_id: UUID,
        message_id: UUID,
        package_hash: str,
        code: Literal[
            "bridge_usage_limit",
            "bridge_usage_unavailable",
            "bridge_auth_required",
            "bridge_ineligible",
            "bridge_unavailable",
            "bridge_permission_denied",
            "bridge_model_unavailable",
            "bridge_transport_unknown",
            "bridge_timeout_unknown",
        ],
    ):
        # Browser reports are safe recovery hints, never proof of a known no-send.
        allowed = {
            "bridge_usage_limit",
            "bridge_usage_unavailable",
            "bridge_auth_required",
            "bridge_ineligible",
            "bridge_unavailable",
            "bridge_permission_denied",
            "bridge_model_unavailable",
            "bridge_transport_unknown",
            "bridge_timeout_unknown",
        }
        if code not in allowed:
            raise ConversationConflictError("external_error_code_invalid")
        message, reservation = self._current(conversation_id, message_id, package_hash)
        if reservation.mode != "connected_provider" or reservation.state != "dispatched":
            raise ConversationConflictError("failure_requires_authorized_dispatch")
        return self.chat.transition(
            message,
            message.model_copy(
                update={
                    "status": MessageStatus.FAILED,
                    "content": "",
                    "error_code": code,
                    "error_fact_source": "client_reported",
                }
            ),
        )

    def abandon(self, conversation_id: UUID, message_id: UUID, package_hash: str) -> Message:
        message, reservation = self._current(conversation_id, message_id, package_hash)
        if reservation.state not in {"prepared", "dispatched"}:
            raise ConversationConflictError("reservation_already_terminal")
        return self.chat.transition(
            message,
            message.model_copy(
                update={
                    "status": MessageStatus.FAILED,
                    "content": "",
                    "error_code": "external_turn_interrupted",
                    "error_fact_source": "server_observed",
                }
            ),
        )

"""dispatch behavior for external turns."""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import UUID

from personal_ai.auth.dispatch_grants import SignedDispatchGrant
from personal_ai.contracts.execution import (
    ExecutionChoice,
)
from personal_ai.entities import Message
from personal_ai.llm.client import (
    ExecutionProvenance,
    ExternalCompletion,
    GenerationMetadata,
    ProviderIdentity,
    UsageMetadata,
)
from personal_ai.llm.external import CHATGPT_PLAN_PROFILE, PreparedExecution
from personal_ai.services.external_turns.contracts import (
    PreparedExternalTurn,
    digest,
)
from personal_ai.storage.errors import ConversationConflictError


class ExternalTurnDispatch:
    def dispatch(
        self, conversation_id: UUID, prepared: PreparedExternalTurn, choice: ExecutionChoice,
        *, offer_deadline: datetime | None = None, routing_root: UUID | None = None,
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
        profile = self._profile(choice, reservation.effective_sensitivity)
        if (
            profile.ref != prepared.connected_package.execution_profile.endpoint
            or digest(profile.model_dump(mode="json")) != reservation.profile_digest
        ):
            raise ConversationConflictError("endpoint_changed")
        local_chat = self._local_chat_scope(choice, profile)
        if local_chat is not None and (
            not local_chat.matches_package(prepared.connected_package)
            or reservation.selected_memory_ids
        ):
            raise ConversationConflictError("local_chat_source_context_denied")
        self._recheck(conversation_id, reservation, choice, source_free=local_chat is not None)
        if self.signer is None:
            raise ConversationConflictError("dispatch_signer_unavailable")
        # Sign before CAS but return only after durable dispatch fencing. Failed writes never expose a grant.
        grant_now = self.clock()
        expires_at = min(reservation.expires_at, grant_now + timedelta(seconds=120))
        if offer_deadline is not None:
            if local_chat is None or offer_deadline.tzinfo is None:
                raise ConversationConflictError("dispatch_binding_invalid")
            expires_at = min(expires_at, offer_deadline)
        proof = self.signer.sign(
            prepared.connected_package,
            caller_id=reservation.caller_id,
            audience=reservation.audience,
            now=grant_now,
            expires_at=expires_at,
            local_chat=local_chat,
            routing_root=routing_root,
        )
        self.chat.transition(
            message,
            message.model_copy(
                update={"execution": reservation.model_copy(update={"state": "dispatched"})}
            ),
        )
        return proof

    def dispatch_package(
        self,
        conversation_id: UUID,
        message_id: UUID,
        package: PreparedExecution,
    ) -> SignedDispatchGrant:
        """Revalidate a browser-returned package against its canonical reservation."""
        if package.reservation_id != message_id:
            raise ConversationConflictError("dispatch_binding_invalid")
        _, reservation = self._current(conversation_id, message_id, package.fingerprint)
        prepared = PreparedExternalTurn(
            message_id=message_id,
            reservation=reservation,
            messages=package.messages,
            connected_package=package,
        )
        return self.dispatch(conversation_id, prepared, self._choice(reservation))

    def import_manual(
        self,
        conversation_id: UUID,
        message_id: UUID,
        package_hash: str,
        text: str,
        *,
        provider_label: str | None = None,
        model_label: str | None = None,
    ) -> Message:
        """Finalize only an explicit user import against the matching reservation."""
        completion = ExternalCompletion(
            text=text,
            provenance=ExecutionProvenance(
                mode="manual_external",
                fact_source="user_declared",
                provider_id=provider_label,
                model_id=model_label,
            ),
        )
        return self.finalize(
            conversation_id,
            message_id,
            package_hash,
            completion,
            explicit_import=True,
        )

    def finalize_connected(
        self,
        conversation_id: UUID,
        message_id: UUID,
        package_hash: str,
        text: str,
        *,
        latency_ms: int | None = None,
        input_tokens: int | None = None,
        output_tokens: int | None = None,
    ) -> Message:
        """Record an attested connected result for supported non-SIWC transports."""
        _, reservation = self._current(conversation_id, message_id, package_hash)
        if reservation.mode != "connected_provider":
            raise ConversationConflictError("connected_completion_requires_connected_reservation")
        choice = self._choice(reservation)
        profile = self._profile(choice, reservation.effective_sensitivity)
        if (
            reservation.provider_id == "openai_chatgpt_plan"
            or profile.serializer_id == CHATGPT_PLAN_PROFILE.serializer_id
        ):
            raise ConversationConflictError("siwc_completion_receipt_required")
        provenance = ExecutionProvenance(
            mode="connected_provider",
            fact_source="bridge_observed",
            provider_id=reservation.provider_id,
            model_id=reservation.model_id,
            connection_id=str(reservation.connection_id),
        )
        usage = (
            UsageMetadata(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                source="provider",
                confidence="reported",
            )
            if input_tokens is not None or output_tokens is not None
            else None
        )
        completion = ExternalCompletion(
            text=text,
            provenance=provenance,
            generation=GenerationMetadata(
                status="success",
                identity=ProviderIdentity(
                    reservation.provider_id, reservation.model_id, profile.serializer_id
                ),
                usage=usage,
                provenance=provenance,
            ),
        )
        return self.finalize(
            conversation_id,
            message_id,
            package_hash,
            completion,
            latency_ms=latency_ms,
        )

"""dispatch behavior for external turns."""

from __future__ import annotations

from datetime import timedelta
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
from personal_ai.llm.external import PreparedExecution
from personal_ai.services.external_turns.contracts import (
    PreparedExternalTurn,
    digest,
)
from personal_ai.storage.errors import ConversationConflictError


class ExternalTurnDispatch:
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
        grant_now = self.clock()
        proof = self.signer.sign(
            prepared.connected_package,
            caller_id=reservation.caller_id,
            audience=reservation.audience,
            now=grant_now,
            expires_at=min(reservation.expires_at, grant_now + timedelta(seconds=120)),
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
        """Record a successful bridge result as client-reported turn attribution."""
        _, reservation = self._current(conversation_id, message_id, package_hash)
        if reservation.mode != "connected_provider":
            raise ConversationConflictError("connected_completion_requires_connected_reservation")
        choice = self._choice(reservation)
        profile = self._profile(choice, reservation.effective_sensitivity)
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

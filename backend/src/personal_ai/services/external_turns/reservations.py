"""reservations behavior for external turns."""

from __future__ import annotations

from uuid import UUID

from personal_ai.context.authorization import (
    authorize_effective_sensitivity,
)
from personal_ai.contracts.execution import (
    ExecutionChoice,
    ExternalFailureCode,
)
from personal_ai.entities import Message, MessageStatus
from personal_ai.entities.turn_execution import TurnAttribution
from personal_ai.llm.client import (
    ExternalCompletion,
)
from personal_ai.routing.contracts import EndpointRef
from personal_ai.services.external_turns.contracts import (
    digest,
)
from personal_ai.storage.errors import ConversationConflictError


class ExternalTurnReservations:
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
            or (
                reservation.provider_id is not None
                and provenance.provider_id != reservation.provider_id
            )
            or (reservation.model_id is not None and provenance.model_id != reservation.model_id)
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
        try:
            completion_bytes = len(completion.text.encode("utf-8", errors="strict"))
        except UnicodeEncodeError:
            raise ConversationConflictError("completion_output_invalid") from None
        if (
            not completion.text.strip()
            or len(completion.text) > reservation.max_output_chars
            or completion_bytes > reservation.max_output_bytes
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
            if reservation.completion_digest != completion_hash:
                raise ConversationConflictError("completion_replay_changed")
            self._authorize_completed_replay(
                conversation_id, message, reservation, self._choice(reservation)
            )
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
            fact_source="user_declared"
            if reservation.mode == "manual_external"
            else "client_reported",
            execution_origin="manual_import"
            if reservation.mode == "manual_external"
            else "connected_local",
            provider_id=provenance.provider_id,
            model_id=provenance.model_id,
            recorded_at=self.clock(),
            latency_ms=latency_ms,
            usage_source=usage.source if usage else None,
            usage_confidence=usage.confidence if usage else None,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            package_fingerprint=package_hash,
            connection_id=reservation.connection_id,
            connection_revision=reservation.connection_revision,
            source_message_ids=reservation.source_message_ids,
            source_snapshots=reservation.source_snapshots,
        )
        completed, newly_committed = self._finalize_cas(
            completion_hash,
            message,
            message.model_copy(
                update={
                    "status": MessageStatus.COMPLETED,
                    "content": completion.text,
                    "model": attribution.model_id,
                    "attribution": attribution,
                    "execution": reservation.model_copy(
                        update={"state": "completed", "completion_digest": completion_hash}
                    ),
                }
            ),
            choice=self._choice(reservation),
        )
        if newly_committed:
            self.chat.schedule_post_completion(
                completed,
                reservation.selected_memory_ids,
                request_id=str(reservation.reservation_id),
            )
        return completed

    def _authorize_completed_replay(self, conversation_id, message, reservation, choice):
        if message.status != MessageStatus.COMPLETED:
            raise ConversationConflictError("completed_result_not_visible")
        authorize_effective_sensitivity(self.context, reservation.effective_sensitivity)
        if (
            self.context.definition.context_policy.version != reservation.policy_version
            or any(
                snapshot.expires_at is not None and self.clock() >= snapshot.expires_at
                for snapshot in reservation.source_snapshots
            )
            or self._snapshot(
                conversation_id,
                choice,
                reservation.source_message_ids,
                reservation.source_snapshots,
            )
            != reservation.authority_digest
        ):
            raise ConversationConflictError("source_authority_changed")
        if reservation.mode == "connected_provider":
            profile = self._profile(choice, reservation.effective_sensitivity)
            if digest(profile.model_dump(mode="json")) != reservation.profile_digest:
                raise ConversationConflictError("endpoint_changed")

    def _finalize_cas(self, completion_hash, current, candidate, *, choice):
        try:
            return self.chat.transition(current, candidate), True
        except ConversationConflictError:
            latest = self.chat.get_message(current.conversation_id, current.id)
            if (
                latest.status == MessageStatus.COMPLETED
                and latest.execution is not None
                and latest.execution.completion_digest == completion_hash
            ):
                self._authorize_completed_replay(
                    current.conversation_id, latest, latest.execution, choice
                )
                return latest, False
            raise

    def _choice(self, reservation):
        # Retained exact identity also supports historical replay after a provider disappears.
        if reservation.mode == "manual_external":
            return ExecutionChoice(mode="manual_external")
        return ExecutionChoice(
            mode="connected_provider",
            endpoint=EndpointRef(
                endpoint_profile_id=reservation.endpoint_profile_id,
                profile_version=reservation.profile_version,
            ),
            model_id=reservation.model_id,
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
        code: ExternalFailureCode,
        *,
        status: int | None = None,
        latency_ms: int | None = None,
    ):
        # Browser reports are safe recovery hints, never proof of a known no-send.
        if (status is not None and (type(status) is not int or not 100 <= status <= 599)) or (
            latency_ms is not None
            and (type(latency_ms) is not int or not 0 <= latency_ms <= 3_600_000)
        ):
            raise ConversationConflictError("external_failure_observation_invalid")
        try:
            safe_code = ExternalFailureCode(code)
        except (TypeError, ValueError):
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
                    "error_code": safe_code.value,
                    "error_fact_source": "client_reported",
                    "failure_status": status,
                    "failure_latency_ms": latency_ms,
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
                    "error_code": ExternalFailureCode.EXECUTION_INTERRUPTED.value,
                    "error_fact_source": "server_observed",
                }
            ),
        )

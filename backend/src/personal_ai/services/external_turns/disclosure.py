"""disclosure behavior for external turns."""

from __future__ import annotations

from typing import Literal
from uuid import UUID, uuid5

from personal_ai.applications.contracts import (
    SENSITIVITY_RANK,
    ExternalDisclosurePolicy,
)
from personal_ai.context.authorization import (
    authorize_base_disclosure,
)
from personal_ai.contracts.context_categories import CONTEXT_SOURCE_CLASSES
from personal_ai.contracts.execution import (
    ContinuationRequest,
    ExecutionChoice,
)
from personal_ai.routing.registry import EndpointRegistryError
from personal_ai.services.external_turns.contracts import (
    digest,
)
from personal_ai.storage.errors import ConversationConflictError, ResourceNotFoundError


class ExternalTurnDisclosure:
    def preview(self, conversation_id: UUID, request: ContinuationRequest):
        """Inspect bounded planner choices before creating a durable reservation."""
        choice = request.choice
        if choice.mode == "automatic":
            raise ConversationConflictError("automatic_execution_uses_existing_routing_lane")
        self._validate_launch_context(request, conversation_id)
        disclosure = self._disclosure_policy(choice.mode)
        self._snapshot(conversation_id, choice, ())
        excluded = self._excluded_for_disclosure(request.excluded_source_classes, disclosure)
        self.chat.validate_manual_import_candidates(conversation_id, request.candidate_message_ids)
        candidate_message_ids = () if "conversation" in excluded else request.candidate_message_ids
        plan, direct_count = self.chat.preview_external_context(
            conversation_id,
            request.content,
            candidate_message_ids=candidate_message_ids,
            candidate_entities=request.entity_refs,
            history_authorizer=lambda ids: self._snapshot(conversation_id, choice, ids),
            excluded_source_classes=excluded,
            maximum_context_sensitivity=disclosure.maximum_sensitivity,
            context_assembler=self.context_assembler,
        )
        return {
            "selected_message_count": direct_count,
            "planned_sources": tuple(
                {
                    "category": item.source_class,
                    "operation": item.operation,
                    "fields": item.fields,
                    "max_results": selection.max_results,
                    "max_tokens": selection.max_tokens,
                }
                for selection in plan.selections
                for item in plan.decisions
                if item.disposition == "selected"
                and item.provider_id == selection.provider_id
                and item.operation == selection.operation
            ),
            "excluded_sources": tuple(
                {"category": item.source_class or item.category, "reason": item.reason}
                for item in plan.decisions
                if item.disposition == "omitted"
            ),
        }

    def reconcile(self, conversation_id: UUID, idempotency_key: UUID):
        """Look up a committed preparation without reconstructing transient prompt text."""
        identity = uuid5(
            conversation_id,
            f"{self.context.scope.owner_id}:{self.context.scope.application_id}:{self.context.scope.workspace_id}:{idempotency_key}",
        )
        try:
            message = self.chat.get_message(conversation_id, identity)
        except ResourceNotFoundError:
            self._snapshot(conversation_id, ExecutionChoice(mode="manual_external"), ())
            return {"state": "not_found", "message_id": None}
        reservation = message.execution
        if reservation is None:
            return {"state": "not_external", "message_id": str(identity)}
        stale_reason = None
        if reservation.state == "prepared":
            choice = self._choice(reservation)
            try:
                self._recheck(conversation_id, reservation, choice)
            except ConversationConflictError as error:
                stale_reason = str(error)
        return {
            "state": "prepared_stale" if stale_reason else reservation.state,
            "message_id": str(message.id),
            "package_fingerprint": reservation.package_fingerprint,
            "mode": reservation.mode,
            "expires_at": reservation.expires_at,
            "stale_reason": stale_reason,
        }

    def abandon_by_idempotency_key(self, conversation_id: UUID, idempotency_key: UUID):
        result = self.reconcile(conversation_id, idempotency_key)
        if result["state"] not in {"prepared", "prepared_stale"} or not result.get("message_id"):
            raise ConversationConflictError("reconciliation_not_abandonable")
        return self.abandon(
            conversation_id,
            UUID(result["message_id"]),
            result["package_fingerprint"],
        )

    def _profile(self, choice: ExecutionChoice, sensitivity: str):
        try:
            profile = self.registry.revalidate_explicit(
                choice.endpoint,
                sensitivity=sensitivity,
                required_capabilities=frozenset({"streaming"}),
            )
        except (EndpointRegistryError, ValueError):
            raise ConversationConflictError("explicit_endpoint_unavailable")
        if profile.external_transport_id is None:
            raise ConversationConflictError("explicit_endpoint_unavailable")
        return profile

    def _snapshot(self, conversation_id, choice, sources, snapshots=()):
        self.chat.require_context(self.context)
        disclosure = self._disclosure_policy(choice.mode)
        base_sensitivity = authorize_base_disclosure(self.context)
        if SENSITIVITY_RANK[base_sensitivity] > SENSITIVITY_RANK[disclosure.maximum_sensitivity]:
            raise ConversationConflictError("execution_sensitivity_denied")
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

    def _disclosure_policy(
        self, mode: Literal["connected_provider", "manual_external"]
    ) -> ExternalDisclosurePolicy:
        policy = self.context.definition.context_policy
        if mode not in policy.external_execution_modes:
            raise ConversationConflictError("execution_disclosure_denied")
        disclosure = policy.sidecar.disclosure_for(mode)
        if not disclosure.allowed or (
            mode == "manual_external" and not policy.sidecar.copy_allowed
        ):
            raise ConversationConflictError("execution_disclosure_denied")
        return disclosure

    @staticmethod
    def _excluded_for_disclosure(excluded, disclosure: ExternalDisclosurePolicy):
        allowed = set(disclosure.allowed_context_categories)
        return frozenset(excluded) | frozenset(
            category for category in CONTEXT_SOURCE_CLASSES if category not in allowed
        )

    def _validate_launch_context(self, request: ContinuationRequest, conversation_id: UUID) -> None:
        launch = request.launch_context
        if launch is None:
            return
        try:
            launch.validate_for(self.context.scope, conversation_id)
        except ValueError as error:
            raise ConversationConflictError("application_launch_scope_mismatch") from error

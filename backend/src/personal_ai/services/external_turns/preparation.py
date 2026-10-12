"""preparation behavior for external turns."""

from __future__ import annotations

from datetime import timedelta
from uuid import UUID, uuid5

from personal_ai.applications.contracts import (
    SENSITIVITY_RANK,
)
from personal_ai.auth.scope import scope_matches
from personal_ai.context.authorization import (
    authorize_effective_sensitivity,
)
from personal_ai.context.contracts import fingerprint
from personal_ai.contracts.execution import (
    ContinuationRequest,
)
from personal_ai.entities import MessageStatus
from personal_ai.entities.turn_execution import TurnReservation
from personal_ai.llm.external import ExecutionProfileIdentity, PreparedExecution, PreparedMessage
from personal_ai.services.external_turns.contracts import (
    ContextPackage,
    ContextPackageExclusionSummary,
    ContextPackageSourceSummary,
    PreparedExternalTurn,
    digest,
)
from personal_ai.storage.errors import ConversationConflictError, ResourceNotFoundError


class ExternalTurnPreparation:
    def prepare(self, conversation_id: UUID, request: ContinuationRequest) -> PreparedExternalTurn:
        choice = request.choice
        if choice.mode == "automatic":
            raise ConversationConflictError("automatic_execution_uses_existing_routing_lane")
        self._validate_launch_context(request, conversation_id)
        disclosure = self._disclosure_policy(choice.mode)
        if choice.mode == "connected_provider" and self.signer is None:
            raise ConversationConflictError("dispatch_signer_unavailable")
        now = self.clock()
        self._snapshot(conversation_id, choice, ())  # Before any read/count/disclosure.
        identity = uuid5(
            conversation_id,
            f"{self.context.scope.owner_id}:{self.context.scope.application_id}:{self.context.scope.workspace_id}:{request.idempotency_key}",
        )
        request_hash = request.intent_digest
        excluded_source_classes = self._excluded_for_disclosure(
            request.excluded_source_classes, disclosure
        )
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
            if (
                SENSITIVITY_RANK[inference.effective_sensitivity]
                > SENSITIVITY_RANK[disclosure.maximum_sensitivity]
            ):
                raise ConversationConflictError("execution_sensitivity_denied")
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
            provider, model = None, None
            if choice.mode == "connected_provider":
                profile = self._profile(choice, inference.effective_sensitivity)
                if (
                    profile.context_limit_tokens is None
                    or assembled.budget.selected_total > profile.context_limit_tokens
                ):
                    raise ConversationConflictError(
                        "provider_context_budget_unavailable_or_exceeded"
                    )
                provider, model = profile.provider_id, choice.model_id
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
                        external_transport_id=profile.external_transport_id,
                    ),
                    connection_id=choice.connection_id,
                    connection_revision=choice.connection_revision,
                    messages=messages,
                    effective_sensitivity=inference.effective_sensitivity,
                    maximum_sensitivity=inference.maximum_sensitivity,
                    policy_version=inference.policy_version,
                    max_output_bytes=80000,
                    max_output_chars=20000,
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
                        "max_output_chars": 20000,
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
                expires_at=now
                + (
                    timedelta(minutes=15)
                    if choice.mode == "connected_provider"
                    else timedelta(hours=24)
                ),
                max_output_bytes=80000,
                max_output_chars=20000,
                provider_id=provider,
                model_id=model,
                connection_id=choice.connection_id,
                connection_revision=choice.connection_revision,
                caller_id=choice.caller_id,
                audience=choice.audience,
                source_message_ids=selected,
                source_snapshots=snapshots,
                selected_memory_ids=assembled.selected_memory_ids,
                endpoint_profile_id=profile.endpoint_profile_id if profile else None,
                profile_version=profile.profile_version if profile else None,
                profile_digest=digest(profile.model_dump(mode="json")) if profile else None,
            )
            included: dict[str, tuple[int, set[str], set[str]]] = {}
            excluded: dict[tuple[str, str], int] = {}
            source_labels = {
                (item.provider_id, item.item_id): f"{item.federation.source.application_id} → {item.federation.destination.application_id}: {item.federation.category}"
                for item in assembled.source_items if item.federation is not None
            }
            for item in assembled.manifest.items:
                category = source_labels.get((item.provider_id, item.item_id), item.source_class)
                if item.injected:
                    count, sensitivities, authorities = included.setdefault(
                        category, (0, set(), set())
                    )
                    sensitivities.add(item.sensitivity)
                    authorities.add(item.authority)
                    included[category] = (count + 1, sensitivities, authorities)
                elif item.omission_reason:
                    key = (category, item.omission_reason)
                    excluded[key] = excluded.get(key, 0) + 1
            grant_versions = tuple(
                sorted(
                    {
                        dependency.version
                        for snapshot in snapshots
                        for dependency in snapshot.permission_dependencies
                    }
                )
            )
            context_package = ContextPackage(
                messages=messages,
                included_sources=tuple(
                    ContextPackageSourceSummary(
                        category=category,
                        item_count=count,
                        sensitivity=tuple(sorted(sensitivities)),
                        authority=tuple(sorted(authorities)),
                    )
                    for category, (count, sensitivities, authorities) in sorted(included.items())
                ),
                excluded_sources=tuple(
                    ContextPackageExclusionSummary(
                        category=category, reason=reason, item_count=count
                    )
                    for (category, reason), count in sorted(excluded.items())
                ),
                selected_message_count=len(assembled.selected_message_ids),
                summarized_source_message_count=(
                    len(assembled.summary.source_message_ids)
                    if assembled.summary is not None
                    else 0
                ),
                input_tokens=assembled.budget.selected_total,
                effective_sensitivity=inference.effective_sensitivity,
                maximum_sensitivity=inference.maximum_sensitivity,
                policy_version=inference.policy_version,
                grant_versions=grant_versions,
                expires_at=reservation.expires_at,
                fingerprint=package_hash,
            )
            if len(context_package.model_dump_json().encode("utf-8")) > 262144:
                raise ConversationConflictError("context_package_too_large")
            result.append(
                PreparedExternalTurn(identity, reservation, messages, package, context_package)
            )
            return assistant.model_copy(
                update={"execution": reservation, "status": MessageStatus.PENDING}
            )

        self.chat.validate_manual_import_candidates(conversation_id, request.candidate_message_ids)
        self.chat.prepare_external(
            conversation_id,
            request.content,
            request_id=self.context.scope.request_id,
            assistant_id=identity,
            user_id=uuid5(identity, "user"),
            preparation_hook=bind,
            candidate_message_ids=(
                () if "conversation" in excluded_source_classes else request.candidate_message_ids
            ),
            candidate_entities=request.entity_refs,
            explicit_context_selections=request.explicit_context_selections,
            history_authorizer=lambda ids: self._snapshot(conversation_id, choice, ids),
            continuation_digest=request_hash,
            context_assembler=self.context_assembler,
            excluded_source_classes=excluded_source_classes,
            maximum_context_sensitivity=disclosure.maximum_sensitivity,
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

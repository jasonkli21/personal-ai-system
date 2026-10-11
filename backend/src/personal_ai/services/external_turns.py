"""External execution orchestration over the shared chat preparation/transaction seam.

HTTP composition uses a request-scoped principal authority. Complete Phase 15
derived-source/revocation and bridge live acceptance remain separate open gates.
No credentials, raw errors, reset guesses, or P19 quota claims enter this service.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Literal, Protocol
from uuid import UUID, uuid5

from pydantic import BaseModel, ConfigDict, Field

from personal_ai.applications.contracts import ApplicationContextRequest
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
from personal_ai.contracts.execution import (
    ContinuationRequest,
    ExecutionChoice,
    ExternalFailureCode,
)
from personal_ai.entities import Message, MessageStatus
from personal_ai.entities.turn_execution import TurnAttribution, TurnReservation
from personal_ai.llm.client import (
    ExecutionProvenance,
    ExternalCompletion,
    GenerationMetadata,
    ProviderIdentity,
    UsageMetadata,
)
from personal_ai.llm.external import ExecutionProfileIdentity, PreparedExecution, PreparedMessage
from personal_ai.routing.contracts import EndpointRef
from personal_ai.routing.registry import EndpointRegistry, EndpointRegistryError
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
    context_package: ContextPackage | None = None
    count_kind: Literal["estimated"] = "estimated"

    @property
    def portable_prompt(self) -> str:
        return "\n\n".join(f"{m.role}:\n{m.content}" for m in self.messages)


class ContextPackageSourceSummary(BaseModel):
    """User-visible category summary; source IDs and raw provider metadata stay private."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    category: str = Field(min_length=1, max_length=48)
    item_count: int = Field(ge=0, le=1000)
    sensitivity: tuple[str, ...] = Field(default=(), max_length=5)
    authority: tuple[str, ...] = Field(default=(), max_length=6)


class ContextPackageExclusionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    category: str = Field(min_length=1, max_length=48)
    reason: str = Field(min_length=1, max_length=64)
    item_count: int = Field(ge=1, le=1000)


class ContextPackage(BaseModel):
    """Transient exact prepared content plus a redacted, bounded inspection view."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["context-package-v1"] = "context-package-v1"
    messages: tuple[PreparedMessage, ...] = Field(min_length=1, max_length=256)
    included_sources: tuple[ContextPackageSourceSummary, ...] = Field(default=(), max_length=32)
    excluded_sources: tuple[ContextPackageExclusionSummary, ...] = Field(default=(), max_length=128)
    selected_message_count: int = Field(ge=0, le=20000)
    summarized_source_message_count: int = Field(default=0, ge=0, le=20000)
    input_tokens: int = Field(ge=0)
    counter_kind: Literal["estimated"] = "estimated"
    effective_sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    maximum_sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    policy_version: str = Field(min_length=1, max_length=200)
    grant_versions: tuple[str, ...] = Field(default=(), max_length=512)
    expires_at: datetime
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


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
        context_assembler=None,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        chat.require_context(context)
        self.chat, self.context, self.registry = chat, context, registry
        self.authority, self.signer, self.clock = authority, signer, clock
        self.context_assembler = context_assembler

    def preview(self, conversation_id: UUID, request: ContinuationRequest):
        """Inspect bounded planner choices before creating a durable reservation."""
        choice = request.choice
        if choice.mode == "automatic":
            raise ConversationConflictError("automatic_execution_uses_existing_routing_lane")
        self._snapshot(conversation_id, choice, ())
        candidate_message_ids = (
            () if "conversation" in request.excluded_source_classes
            else request.candidate_message_ids
        )
        plan, direct_count = self.chat.preview_external_context(
            conversation_id,
            request.content,
            candidate_message_ids=candidate_message_ids,
            history_authorizer=lambda ids: self._snapshot(conversation_id, choice, ids),
            excluded_source_classes=request.excluded_source_classes,
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
        if choice.mode == "connected_provider" and self.signer is None:
            raise ConversationConflictError("dispatch_signer_unavailable")
        now = self.clock()
        self._snapshot(conversation_id, choice, ())  # Before any read/count/disclosure.
        identity = uuid5(
            conversation_id,
            f"{self.context.scope.owner_id}:{self.context.scope.application_id}:{self.context.scope.workspace_id}:{request.idempotency_key}",
        )
        request_hash = request.intent_digest
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
                expires_at=now + (
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
            for item in assembled.manifest.items:
                if item.injected:
                    count, sensitivities, authorities = included.setdefault(
                        item.source_class, (0, set(), set())
                    )
                    sensitivities.add(item.sensitivity)
                    authorities.add(item.authority)
                    included[item.source_class] = (count + 1, sensitivities, authorities)
                elif item.omission_reason:
                    key = (item.source_class, item.omission_reason)
                    excluded[key] = excluded.get(key, 0) + 1
            grant_versions = tuple(sorted({
                dependency.version
                for snapshot in snapshots
                for dependency in snapshot.permission_dependencies
            }))
            context_package = ContextPackage(
                messages=messages,
                included_sources=tuple(
                    ContextPackageSourceSummary(
                        category=category,
                        item_count=count,
                        sensitivity=tuple(sorted(sensitivities)),
                        authority=tuple(sorted(authorities)),
                    )
                    for category, (count, sensitivities, authorities)
                    in sorted(included.items())
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
                PreparedExternalTurn(
                    identity, reservation, messages, package, context_package
                )
            )
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
            candidate_message_ids=(
                () if "conversation" in request.excluded_source_classes
                else request.candidate_message_ids
            ),
            history_authorizer=lambda ids: self._snapshot(conversation_id, choice, ids),
            continuation_digest=request_hash,
            context_assembler=self.context_assembler,
            excluded_source_classes=request.excluded_source_classes,
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
        _, reservation = self._current(
            conversation_id, message_id, package.fingerprint
        )
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
            or (reservation.provider_id is not None and provenance.provider_id != reservation.provider_id)
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
            mode=reservation.mode,
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

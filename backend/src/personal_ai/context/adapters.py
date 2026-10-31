"""Typed wrappers for records that already belong to existing subsystems."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from time import monotonic
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from personal_ai.applications.contracts import CapabilityRegistration
from personal_ai.auth.scope import (
    STANDALONE_APPLICATION_ID,
    ApplicationScope,
    RequestScope,
    application_scope_context,
    current_request_scope,
)
from personal_ai.context.history import message_context_authority
from personal_ai.context.providers import (
    ContextItem,
    ContextOperationSpec,
    ContextPermissionDependency,
    ContextProviderError,
    ContextProviderFailure,
    ContextProviderInputs,
    ContextProviderResult,
    ContextProviderSpec,
    ContextSelection,
    ContextSensitivity,
    ContextSourceReference,
    tool_result_projection_is_valid,
)


class ConversationRecordPayload(BaseModel):
    """A typed projection of a message or compatible working summary."""

    kind: Literal["message", "summary"]
    id: str | None = None
    role: str | None = None
    content: str | None = None
    created_at: datetime | None = None
    source_message_ids: tuple[str, ...] = Field(default=(), max_length=200)


class ConversationContextProvider:
    spec = ContextProviderSpec(
        provider_id="conversation_history",
        source_class="conversation",
        source_version="conversation-wrapper-v1",
        operations=(
            ContextOperationSpec(
                operation="history",
                allowed_fields=("content", "role", "created_at", "id", "source_message_ids"),
                maximum_results=50,
                maximum_bytes=65_536,
                maximum_timeout_seconds=2,
            ),
        ),
    )

    def __init__(self, inputs: ContextProviderInputs) -> None:
        self.inputs = inputs

    def validate_selection(self, selection: ContextSelection, inputs: ContextProviderInputs):
        del selection
        if inputs.scope != self.inputs.scope:
            raise ContextProviderError("context_provider_scope_mismatch")

    def fetch(self, selection: ContextSelection, scope: RequestScope, *, deadline: float):
        del deadline
        from personal_ai.context.contracts import complete_turns, is_compatible
        from personal_ai.entities import Message

        messages = self.inputs.active_messages
        if any(not isinstance(item, Message) for item in messages):
            raise ContextProviderError("conversation_context_record_invalid")
        if any(
            item.owner_id != scope.owner_id
            or item.application_id != scope.application_id
            or item.workspace_id != scope.workspace_id
            for item in messages
        ):
            raise ContextProviderError("context_provider_scope_mismatch")
        summary = self.inputs.summary
        compatible_summary = (
            summary is not None
            and summary.owner_id == scope.owner_id
            and summary.application_id == scope.application_id
            and summary.workspace_id == scope.workspace_id
            and messages
            and summary.conversation_id == messages[-1].conversation_id
            and is_compatible(summary, messages)
        )
        summary_failure = None
        if compatible_summary and len(summary.source_message_ids) > 200:
            compatible_summary = False
            summary_failure = ContextProviderFailure(
                provider_id=self.spec.provider_id,
                operation=selection.operation,
                reason="summary_provenance_limit",
            )
        turns = complete_turns(messages)

        def recent_turns(slot_limit: int):
            selected_turns = []
            used = 0
            for turn in reversed(turns):
                if used + len(turn) > slot_limit:
                    continue
                selected_turns.insert(0, turn)
                used += len(turn)
            return selected_turns

        def message_item(message):
            dependencies, expires_at, sensitivity, source_classes = message_context_authority(
                message
            )
            if len(dependencies) > 16:
                raise ContextProviderError("conversation_context_dependency_limit")
            return ContextItem(
                source_class="conversation",
                provider_id=self.spec.provider_id,
                source_id=str(message.conversation_id),
                source_version="active-branch-v1",
                item_id=str(message.id),
                owner_id=scope.owner_id,
                application_id=scope.application_id,
                workspace_id=scope.workspace_id,
                authority="unknown",
                observed_at=message.created_at,
                sensitivity=sensitivity,
                expires_at=expires_at,
                permission_dependencies=dependencies,
                inherited_source_classes=source_classes,
                source_refs=(
                    ContextSourceReference(
                        kind="conversation_message", reference_id=str(message.id)
                    ),
                ),
                payload=ConversationRecordPayload(
                    kind="message",
                    id=str(message.id) if "id" in selection.fields else None,
                    role=message.role.value if "role" in selection.fields else None,
                    content=message.content if "content" in selection.fields else None,
                    created_at=message.created_at if "created_at" in selection.fields else None,
                ),
            )

        def records_for(turn_groups):
            return [message_item(message) for turn in turn_groups for message in turn]

        def response_size(items):
            return sum(len(item.model_dump_json().encode("utf-8")) for item in items)

        selected_turns = recent_turns(
            selection.max_results - 1 if compatible_summary else selection.max_results
        )
        records = records_for(selected_turns)
        if compatible_summary:
            covered_ids = set(summary.source_message_ids)
            covered = tuple(message for message in messages if message.id in covered_ids)
            covered_assistants = tuple(
                message for message in covered if message.role.value == "assistant"
            )
            authorities = tuple(
                message_context_authority(message) for message in covered_assistants
            )
            dependencies = tuple(
                dict.fromkeys(
                    dependency
                    for item_dependencies, _expiry, _sensitivity, _classes in authorities
                    for dependency in item_dependencies
                )
            )
            expiries = [expiry for _dependencies, expiry, _sensitivity, _classes in authorities]
            expiries = [expiry for expiry in expiries if expiry is not None]
            sensitivities = [sensitivity for _deps, _expiry, sensitivity, _classes in authorities]
            source_classes = tuple(
                dict.fromkeys(
                    source_class
                    for _deps, _expiry, _sensitivity, classes in authorities
                    for source_class in classes
                )
            )
            rank = {"public": 0, "personal": 1, "sensitive": 2, "restricted": 3, "unknown": 4}
            if len(dependencies) > 16:
                raise ContextProviderError("conversation_context_dependency_limit")
            summary_expiry = min(expiries) if expiries else None
            summary_sensitivity = (
                max(sensitivities, key=rank.__getitem__) if sensitivities else "personal"
            )
            summary_record = ContextItem(
                source_class="conversation",
                provider_id=self.spec.provider_id,
                source_id=str(summary.conversation_id),
                source_version="active-branch-summary-v1",
                item_id=str(summary.id),
                owner_id=scope.owner_id,
                application_id=scope.application_id,
                workspace_id=scope.workspace_id,
                authority="derived",
                observed_at=summary.created_at,
                sensitivity=summary_sensitivity,
                expires_at=summary_expiry,
                permission_dependencies=dependencies,
                inherited_source_classes=source_classes,
                source_refs=tuple(
                    ContextSourceReference(
                        kind="conversation_message", reference_id=str(message_id)
                    )
                    for message_id in summary.source_message_ids
                ),
                payload=ConversationRecordPayload(
                    kind="summary",
                    id=str(summary.id) if "id" in selection.fields else None,
                    content=summary.content if "content" in selection.fields else None,
                    created_at=summary.created_at if "created_at" in selection.fields else None,
                    source_message_ids=(
                        tuple(str(item) for item in summary.source_message_ids)
                        if "source_message_ids" in selection.fields
                        else ()
                    ),
                ),
            )
            candidate = (summary_record, *records)
            while response_size(candidate) > selection.max_bytes and selected_turns:
                selected_turns.pop(0)
                records = records_for(selected_turns)
                candidate = (summary_record, *records)
            if response_size(candidate) > selection.max_bytes:
                summary_failure = ContextProviderFailure(
                    provider_id=self.spec.provider_id,
                    operation=selection.operation,
                    reason="summary_response_limit",
                )
                selected_turns = recent_turns(selection.max_results)
                records = records_for(selected_turns)
                while response_size(records) > selection.max_bytes and selected_turns:
                    selected_turns.pop(0)
                    records = records_for(selected_turns)
            else:
                records.insert(0, summary_record)
        else:
            while response_size(records) > selection.max_bytes and selected_turns:
                selected_turns.pop(0)
                records = records_for(selected_turns)
        if summary_failure:
            return ContextProviderResult(items=tuple(records), failures=(summary_failure,))
        return tuple(records)


class MemoryContextPayload(BaseModel):
    """Typed content projection; embeddings and lifecycle internals stay private."""

    record_kind: Literal["memory", "derived_memory"]
    memory_type: str | None = None
    content: str | None = None
    effective_at: datetime | None = None


class MemoryContextProvider:
    spec = ContextProviderSpec(
        provider_id="ai_memory",
        source_class="ai_memory",
        source_version="memory-wrapper-v1",
        operations=(
            ContextOperationSpec(
                operation="search",
                allowed_fields=("content", "memory_type", "effective_at"),
                maximum_results=20,
                maximum_bytes=65_536,
                maximum_timeout_seconds=5,
            ),
        ),
        maximum_items_per_call=20,
    )

    def __init__(self, inputs: ContextProviderInputs, settings) -> None:
        self.inputs = inputs
        self.settings = settings

    def validate_selection(self, selection: ContextSelection, inputs: ContextProviderInputs):
        del selection
        if inputs.scope != self.inputs.scope:
            raise ContextProviderError("context_provider_scope_mismatch")
        if self.inputs.retrieval is None:
            raise ContextProviderError("memory_retrieval_unavailable")

    def fetch(self, selection: ContextSelection, scope: RequestScope, *, deadline: float):
        del deadline
        from personal_ai.memory.contracts import DerivedMemory, Memory, RetrievalResult
        from personal_ai.memory.dependencies import injection_dependencies
        from personal_ai.memory.policy import content_reason

        if not isinstance(self.inputs.retrieval, RetrievalResult):
            raise ContextProviderError("memory_retrieval_unavailable")
        records = []
        for scored in self.inputs.retrieval.selected[: selection.max_results]:
            memory = scored.memory
            if not isinstance(memory, (Memory, DerivedMemory)):
                raise ContextProviderError("memory_context_record_invalid")
            if (
                memory.owner_id != scope.owner_id
                or memory.application_id != scope.application_id
                or memory.workspace_id != scope.workspace_id
            ):
                raise ContextProviderError("memory_scope_mismatch")
            if getattr(memory, "status", "active") != "active" or content_reason(
                memory.content, self.settings
            ):
                # Apply the same final content/status gate as the assembler's
                # memory disclosure path. Lifecycle/source eligibility remains
                # the retriever's responsibility.
                continue
            is_derived = isinstance(memory, DerivedMemory)
            records.append(
                ContextItem(
                    source_class="ai_memory",
                    provider_id=self.spec.provider_id,
                    source_id=str(memory.id),
                    source_version=str(getattr(memory, "schema_version", 1)),
                    item_id=str(memory.id),
                    owner_id=scope.owner_id,
                    application_id=scope.application_id,
                    workspace_id=scope.workspace_id,
                    authority="derived" if is_derived else "user_asserted",
                    observed_at=memory.observed_at
                    if hasattr(memory, "observed_at")
                    else memory.created_at,
                    effective_at=memory.effective_at,
                    sensitivity="personal",
                    represented_item_ids=(
                        tuple(str(source.memory_id) for source in memory.sources)
                        if is_derived
                        else ()
                    ),
                    source_refs=(
                        tuple(
                            ContextSourceReference(
                                kind="conversation_message",
                                reference_id=str(message_id),
                                fingerprint=memory.source_fingerprint,
                            )
                            for message_id in memory.source_message_ids
                        )
                        if hasattr(memory, "source_message_ids")
                        else tuple(
                            ContextSourceReference(
                                kind="record",
                                reference_id=str(source.memory_id),
                                fingerprint=source.source_fingerprint,
                            )
                            for source in memory.sources
                        )
                        + tuple(
                            ContextSourceReference(
                                kind="conversation_message",
                                reference_id=str(message_id),
                                fingerprint=source.source_fingerprint,
                            )
                            for source in memory.sources
                            for message_id in source.source_message_ids
                        )
                    ),
                    permission_dependencies=injection_dependencies(self.inputs.retrieval, memory),
                    payload=MemoryContextPayload(
                        record_kind=(
                            "derived_memory" if hasattr(memory, "source_memory_ids") else "memory"
                        ),
                        memory_type=memory.memory_type
                        if "memory_type" in selection.fields
                        else None,
                        content=(
                            (
                                "Unresolved conflict; retain ambiguity: "
                                if any(
                                    row.memory_id == memory.id and row.unresolved_conflict
                                    for row in self.inputs.retrieval.trace.candidates
                                )
                                else ""
                            )
                            + memory.content
                            if self.inputs.retrieval.trace
                            else memory.content
                        )
                        if "content" in selection.fields
                        else None,
                        effective_at=memory.effective_at
                        if "effective_at" in selection.fields
                        else None,
                    ),
                )
            )
        return tuple(records)


class ResearchEvidencePayload(BaseModel):
    """Typed selected evidence projection; raw research runs stay in their repository."""

    evidence_id: str
    passage: str | None = None
    observed_at: datetime | None = None
    expires_at: datetime | None = None
    source_observation_ids: tuple[str, ...] = Field(max_length=12)


class ResearchEvidenceContextProvider:
    spec = ContextProviderSpec(
        provider_id="external_research",
        source_class="external_research",
        source_version="research-evidence-wrapper-v1",
        operations=(
            ContextOperationSpec(
                operation="search",
                allowed_fields=("passage", "observed_at", "expires_at"),
                accepts_entity_refs=True,
                maximum_results=12,
                maximum_bytes=65_536,
                maximum_timeout_seconds=5,
            ),
        ),
        maximum_items_per_call=12,
    )

    def __init__(self, inputs: ContextProviderInputs, research_repository=None) -> None:
        self.inputs = inputs
        self.research_repository = research_repository

    def validate_selection(self, selection: ContextSelection, inputs: ContextProviderInputs):
        del selection
        if inputs.scope != self.inputs.scope:
            raise ContextProviderError("context_provider_scope_mismatch")

    def fetch(self, selection: ContextSelection, scope: RequestScope, *, deadline: float):
        del deadline
        output = []
        from personal_ai.evidence.contracts import Evidence, SourceObservation
        from personal_ai.search.authority import observation_dependencies

        records = [] if selection.entity_refs else list(self.inputs.evidence_records)
        selected_session_ids = set()
        selected_session_expiries = {}
        if selection.entity_refs:
            if scope.application_id != "travel" or any(
                item.entity_type != "research_session"
                or item.application_id != scope.application_id
                or item.workspace_id != scope.workspace_id
                for item in selection.entity_refs
            ):
                raise ContextProviderError("research_context_selection_invalid")
            if self.research_repository is None:
                raise ContextProviderError("research_context_unavailable")
            from uuid import UUID

            from personal_ai.storage.errors import ResourceNotFoundError

            for reference in selection.entity_refs[: selection.max_results]:
                try:
                    session_id = UUID(reference.entity_id)
                    with application_scope_context(ApplicationScope()):
                        research_session = self.research_repository.get(scope.owner_id, session_id)
                except (ValueError, ResourceNotFoundError):
                    raise ContextProviderError("research_context_unavailable") from None
                if (
                    research_session.state != "completed"
                    or research_session.expires_at <= datetime.now(UTC)
                ):
                    continue
                selected_session_ids.add(research_session.id)
                selected_session_expiries[research_session.id] = research_session.expires_at
                observations = {item.id: item for item in research_session.observations}
                for evidence in research_session.evidence:
                    records.append((evidence, tuple(observations.values())))
        for record in records[: selection.max_results]:
            if not isinstance(record, tuple) or len(record) != 2:
                raise ContextProviderError("research_context_record_invalid")
            evidence, observations = record
            if not isinstance(evidence, Evidence) or any(
                not isinstance(item, SourceObservation) for item in observations
            ):
                raise ContextProviderError("research_context_record_invalid")
            selected_standalone = evidence.session_id in selected_session_ids
            expected_application = (
                STANDALONE_APPLICATION_ID if selected_standalone else scope.application_id
            )
            expected_workspace = None if selected_standalone else scope.workspace_id
            if (
                evidence.owner_id != scope.owner_id
                or evidence.application_id != expected_application
                or evidence.workspace_id != expected_workspace
            ):
                raise ContextProviderError("research_context_scope_mismatch")
            observation_by_id = {item.id: item for item in observations}
            if len(observation_by_id) != len(observations):
                raise ContextProviderError("research_context_source_mismatch")
            ordered = tuple(
                observation_by_id[item_id]
                for item_id in evidence.source_observation_ids
                if item_id in observation_by_id
            )
            if (
                evidence.status != "eligible"
                or len(set(evidence.source_observation_ids)) != len(evidence.source_observation_ids)
                or len(ordered) != len(evidence.source_observation_ids)
                or any(
                    observation.status != "accepted"
                    or observation.owner_id != evidence.owner_id
                    or observation.application_id != evidence.application_id
                    or observation.workspace_id != evidence.workspace_id
                    or observation.session_id != evidence.session_id
                    for observation in ordered
                )
            ):
                raise ContextProviderError("research_context_source_mismatch")
            output.append(
                ContextItem(
                    source_class="external_research",
                    provider_id=self.spec.provider_id,
                    source_id=str(evidence.session_id),
                    source_version="evidence-v1",
                    item_id=str(evidence.id),
                    owner_id=scope.owner_id,
                    application_id=scope.application_id,
                    workspace_id=scope.workspace_id,
                    authority="external",
                    observed_at=evidence.observed_at,
                    expires_at=min(
                        evidence.expires_at,
                        selected_session_expiries.get(evidence.session_id, evidence.expires_at),
                    ),
                    sensitivity="public",
                    source_refs=tuple(
                        ContextSourceReference(
                            kind="url",
                            reference_id=str(observation.id),
                            uri=observation.canonical_url,
                            fingerprint=observation.content_fingerprint,
                        )
                        for observation in ordered
                    ),
                    permission_dependencies=(
                        ContextPermissionDependency(
                            permission_id="research_source_policy",
                            version="research-v1",
                            purpose="preserve evidence source rights and attribution",
                            source_application_id=(
                                STANDALONE_APPLICATION_ID if selected_standalone else None
                            ),
                            destination_application_id=(
                                scope.application_id if selected_standalone else None
                            ),
                        ),
                    ) + observation_dependencies(ordered),
                    payload=ResearchEvidencePayload(
                        evidence_id=str(evidence.id),
                        passage=evidence.passage if "passage" in selection.fields else None,
                        observed_at=evidence.observed_at
                        if "observed_at" in selection.fields
                        else None,
                        expires_at=evidence.expires_at
                        if "expires_at" in selection.fields
                        else None,
                        source_observation_ids=tuple(str(item.id) for item in ordered),
                    ),
                )
            )
        return tuple(output)


class ClientContextPayload(BaseModel):
    """One bounded, non-authoritative client-supplied field."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str = Field(min_length=1, max_length=100)
    value: str | int | float | bool | None


class ClientContextProvider:
    spec = ContextProviderSpec(
        provider_id="client_context",
        source_class="client_context",
        source_version="request-client-context-v1",
        operations=(
            ContextOperationSpec(
                operation="profile",
                dynamic_fields=True,
                maximum_results=32,
                maximum_bytes=4_096,
                maximum_timeout_seconds=0.2,
            ),
        ),
    )

    def __init__(self, inputs: ContextProviderInputs) -> None:
        self.inputs = inputs

    def validate_selection(self, selection: ContextSelection, inputs: ContextProviderInputs):
        del inputs
        if not set(selection.fields).issubset(self.inputs.scope.client_context):
            raise ContextProviderError("client_context_field_not_present")

    def fetch(self, selection: ContextSelection, scope: RequestScope, *, deadline: float):
        del deadline
        application_context = self.inputs.application_context
        sensitivity: ContextSensitivity = "personal"
        if application_context is not None:
            sensitivity = application_context.definition.sensitivity_defaults.client_context
        return tuple(
            ContextItem(
                source_class="client_context",
                provider_id=self.spec.provider_id,
                source_id=scope.request_id,
                source_version=self.spec.source_version,
                item_id=key,
                owner_id=scope.owner_id,
                application_id=scope.application_id,
                workspace_id=scope.workspace_id,
                authority="client_supplied",
                sensitivity=sensitivity,
                source_refs=(ContextSourceReference(kind="record", reference_id=scope.request_id),),
                permission_dependencies=(
                    ContextPermissionDependency(
                        permission_id="client_context_read",
                        version="client-context-v1",
                        purpose="read bounded non-authoritative request metadata",
                    ),
                ),
                payload=ClientContextPayload(key=key, value=scope.client_context[key]),
            )
            for key in selection.fields[: selection.max_results]
        )


class ClientContextProviderFactory:
    spec = ClientContextProvider.spec

    def create(self, inputs: ContextProviderInputs) -> ClientContextProvider:
        return ClientContextProvider(inputs)


class ConversationContextProviderFactory:
    spec = ConversationContextProvider.spec

    def create(self, inputs: ContextProviderInputs) -> ConversationContextProvider:
        return ConversationContextProvider(inputs)


class MemoryContextProviderFactory:
    spec = MemoryContextProvider.spec

    def __init__(self, settings) -> None:
        self.settings = settings

    def create(self, inputs: ContextProviderInputs) -> MemoryContextProvider:
        return MemoryContextProvider(inputs, self.settings)


class BuiltInContextPermissionRevalidator:
    """Recheck built-in memory and explicit profile-share permissions."""

    def __init__(self, settings, profile_repository=None, application_registry=None, authority=None) -> None:
        self.settings = settings
        self.profile_repository = profile_repository
        self.application_registry = application_registry
        self.authority = authority

    @staticmethod
    def supports(dependency) -> bool:
        return dependency.permission_id == "ai_memory_read" or dependency.permission_id.startswith(
            "global_profile_share:"
        )

    def is_current(self, dependency) -> bool:
        if dependency.permission_id == "ai_memory_read" and dependency.version == "memory-v1":
            # Historical flag-only memory snapshots cannot establish current source rights.
            return False
        from personal_ai.auth.scope import current_verified_principal
        from personal_ai.context.profile_consent import destination_allowed, share_dependency

        scope = current_request_scope()
        principal = current_verified_principal()
        if (
            not getattr(self.settings, "profile_sharing_enabled", False)
            or self.profile_repository is None or scope is None or principal is None
            or principal.owner_id != scope.owner_id
            or scope.acting_user_id != f"{principal.issuer}|{principal.subject}"
            or dependency.owner_id != scope.owner_id
            or dependency.acting_user_id != scope.acting_user_id
            or dependency.entity_ref is None
            or dependency.entity_ref.entity_type != "global_profile_field"
        ):
            return False
        parts = dependency.permission_id.split(":")
        if len(parts) != 3 or parts[2] != scope.application_id:
            return False
        field = parts[1]
        try:
            if self.authority is None:
                return False
            registry = self.authority() or self.application_registry
            if not destination_allowed(registry, principal, ApplicationScope(
                application_id=scope.application_id, workspace_id=scope.workspace_id
            ), field):
                return False
            return any(
                share_dependency(scope.owner_id, grant) == dependency
                for grant, _item in self.profile_repository.authorized_fields(
                    scope, (field,), deadline=monotonic() + 0.25
                )
            )
        except Exception:  # noqa: BLE001 - unavailable or corrupt authority denies
            return False


class ResearchEvidenceContextProviderFactory:
    spec = ResearchEvidenceContextProvider.spec

    def __init__(self, research_repository=None) -> None:
        self.research_repository = research_repository

    def create(self, inputs: ContextProviderInputs) -> ResearchEvidenceContextProvider:
        return ResearchEvidenceContextProvider(inputs, self.research_repository)


@dataclass(frozen=True)
class ToolResultSnapshot:
    """A typed result from a registered read-only tool invocation."""

    invocation_id: str
    owner_id: str
    application_id: str
    workspace_id: str | None
    payload: BaseModel
    schema_version: str = "tool-result-v1"
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class ToolResultProviderFactory:
    """Expose a typed read result only for an explicitly bounded tool contract."""

    def __init__(
        self,
        capability: CapabilityRegistration,
        projector: Callable[[BaseModel, tuple[str, ...]], BaseModel],
    ) -> None:
        if (
            capability.kind != "tool"
            or not capability.read_only_context
            or capability.max_result_bytes is None
            or not capability.result_fields
        ):
            raise ValueError("read_context_tool_contract_required")
        self.capability = capability
        self._projector = projector
        self.spec = ContextProviderSpec(
            provider_id=capability.capability_id,
            source_class="tool_result",
            source_version="tool-result-wrapper-v1",
            capability_kind="tool",
            operations=(
                ContextOperationSpec(
                    operation="current",
                    allowed_fields=capability.result_fields,
                    maximum_results=1,
                    maximum_bytes=capability.max_result_bytes,
                    maximum_timeout_seconds=0.2,
                ),
            ),
            maximum_items_per_call=1,
        )

    def create(self, inputs: ContextProviderInputs) -> ToolResultContextProvider:
        snapshot = (inputs.tool_results or {}).get(self.capability.capability_id)
        if snapshot is not None and not isinstance(snapshot, ToolResultSnapshot):
            raise ContextProviderError("tool_result_invalid")
        return ToolResultContextProvider(self.spec, snapshot, self._projector)


class ToolResultContextPayload(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    capability_id: str
    invocation_id: str
    schema_version: str
    result: Any

    @model_validator(mode="after")
    def result_is_typed(self):
        if not isinstance(self.result, BaseModel):
            raise TypeError("tool_result_payload_invalid")
        return self


class ToolResultContextProvider:
    def __init__(
        self,
        spec: ContextProviderSpec,
        snapshot: ToolResultSnapshot | None,
        projector: Callable[[BaseModel, tuple[str, ...]], BaseModel],
    ) -> None:
        self.spec = spec
        self.snapshot = snapshot
        self._projector = projector

    def validate_selection(self, selection: ContextSelection, inputs: ContextProviderInputs):
        if self.snapshot is None:
            raise ContextProviderError("tool_result_unavailable")
        if (
            self.snapshot.owner_id != inputs.scope.owner_id
            or self.snapshot.application_id != inputs.scope.application_id
            or self.snapshot.workspace_id != inputs.scope.workspace_id
        ):
            raise ContextProviderError("tool_result_scope_mismatch")
        if set(selection.fields) - set(self.spec.operation("current").allowed_fields):
            raise ContextProviderError("tool_result_field_not_registered")

    def fetch(self, selection: ContextSelection, scope: RequestScope, *, deadline: float):
        del deadline
        if self.snapshot is None:
            raise ContextProviderError("tool_result_unavailable")
        projected = self._projector(self.snapshot.payload, selection.fields)
        if not isinstance(projected, BaseModel):
            raise ContextProviderError("tool_result_projection_invalid")
        if not tool_result_projection_is_valid(projected, selection.fields):
            raise ContextProviderError("tool_result_projection_invalid")
        item = ContextItem(
            source_class="tool_result",
            provider_id=self.spec.provider_id,
            source_id=self.snapshot.invocation_id,
            source_version=self.snapshot.schema_version,
            item_id=self.snapshot.invocation_id,
            owner_id=scope.owner_id,
            application_id=scope.application_id,
            workspace_id=scope.workspace_id,
            authority="derived",
            observed_at=self.snapshot.observed_at,
            sensitivity="personal",
            source_refs=(
                ContextSourceReference(
                    kind="tool_invocation", reference_id=self.snapshot.invocation_id
                ),
            ),
            permission_dependencies=(
                ContextPermissionDependency(
                    permission_id=self.spec.provider_id,
                    version=self.spec.source_version,
                    purpose="disclose a bounded read-only tool result",
                ),
            ),
            payload=ToolResultContextPayload(
                capability_id=self.spec.provider_id,
                invocation_id=self.snapshot.invocation_id,
                schema_version=self.snapshot.schema_version,
                result=projected,
            ),
        )
        return (item,)

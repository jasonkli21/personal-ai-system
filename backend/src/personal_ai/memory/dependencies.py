"""Memory dependencies use the shared permission graph for every later reuse."""

from datetime import UTC, datetime
from hashlib import sha256
from uuid import UUID

from personal_ai.auth.scope import ApplicationScope, current_request_scope, scope_matches
from personal_ai.contracts.context_references import (
    ContextEntityReference,
    ContextPermissionDependency,
)
from personal_ai.memory.contracts import DerivedMemory, Memory, embedding_space_for
from personal_ai.memory.lifecycle.contracts import MemoryLifecycleState
from personal_ai.memory.policy import candidate_reason, content_reason


def dependency_version(record, state):
    # Retrieval frequency and consolidation links are advisory, not source revisions.
    binding = record.model_dump_json() + repr(
        (
            state.retrieval_status,
            state.superseded_by_memory_id,
            state.validity_epoch,
            state.unresolved_conflict,
        )
    )
    return sha256(binding.encode()).hexdigest()


def memory_dependency(record, state, *, acting_user_id=None):
    return ContextPermissionDependency(
        permission_id=(
            "ai_memory_view" if isinstance(record, DerivedMemory) else "ai_memory_source"
        ),
        version=dependency_version(record, state),
        purpose="reuse attributable active memory",
        owner_id=record.owner_id,
        acting_user_id=acting_user_id,
        source_scope=ApplicationScope(
            application_id=record.application_id, workspace_id=record.workspace_id
        ),
        entity_ref=ContextEntityReference(
            entity_type=("memory_view" if isinstance(record, DerivedMemory) else "memory"),
            entity_id=str(record.id),
            application_id=record.application_id,
            workspace_id=record.workspace_id,
        ),
        source_revision=(
            record.source_set_identity
            if isinstance(record, DerivedMemory)
            else record.source_fingerprint
        ),
    )


def original_reason(
    record,
    settings,
    messages,
    lifecycle,
    *,
    timeout=5,
    application_context=None,
    permission_revalidator=None,
    now=None,
):
    from personal_ai.memory.services import source_messages, source_turn_reuse_reason

    if not isinstance(record, Memory) or not scope_matches(record):
        return "scope_mismatch"
    if (
        record.embedding_model != settings.memory_embedding_model
        or record.embedding_dimensions != settings.memory_embedding_dimensions
        or record.embedding_space_version != "v1"
    ):
        return "incompatible_embedding"
    if record.status != "active":
        return "inactive"
    state = (
        lifecycle.get_state(owner_id=record.owner_id, memory_id=record.id)
        if lifecycle is not None
        else MemoryLifecycleState(owner_id=record.owner_id, memory_id=record.id)
    )
    if state.retrieval_status != "active":
        return state.retrieval_status
    if content_reason(record.content, settings):
        return "content_policy"
    source = source_messages(record, messages, timeout=timeout)
    if source is None:
        return "branch_mismatch"
    reason = source_turn_reuse_reason(
        record,
        messages,
        application_context,
        timeout=timeout,
        permission_revalidator=permission_revalidator,
        now=now,
    )
    if reason:
        return reason
    return candidate_reason(
        record.model_copy(
            update={
                "effective_at": (
                    record.effective_at if record.effective_at != record.observed_at else None
                )
            }
        ),
        source,
        settings,
    )


class MemoryPermissionRevalidator:
    """Canonical source/lifecycle reader, registered in production composition."""

    def __init__(
        self, settings, memories, messages, lifecycle=None, *, clock=None, application_registry=None
    ):
        self.settings, self.memories, self.messages, self.lifecycle = (
            settings,
            memories,
            messages,
            lifecycle,
        )
        self.application_registry = application_registry
        self.clock = clock or (lambda: datetime.now(UTC))

    @staticmethod
    def supports(dependency):
        return dependency.permission_id in ("ai_memory_source", "ai_memory_view")

    def is_current(self, dependency):
        scope = current_request_scope()
        if (
            not self.settings.memory_enabled
            or self.memories is None
            or scope is None
            or dependency.owner_id != scope.owner_id
            or dependency.acting_user_id != scope.acting_user_id
            or dependency.source_scope
            != ApplicationScope(
                application_id=scope.application_id, workspace_id=scope.workspace_id
            )
            or dependency.entity_ref is None
            or dependency.entity_ref.entity_type not in ("memory", "memory_view")
        ):
            return False
        try:
            application_context = None
            if self.application_registry is not None:
                from personal_ai.applications.contracts import ApplicationContextRequest

                registration = self.application_registry.registration(scope.application_id)
                application_context = ApplicationContextRequest(
                    definition=registration.definition,
                    scope=scope,
                    context_provider_capabilities=registration.context_providers,
                    tool_capabilities=registration.tools,
                )
                from personal_ai.context.authorization import authorize_memory_disclosure

                authorize_memory_disclosure(application_context)
            get = (
                self.memories.get_derived
                if dependency.entity_ref.entity_type == "memory_view"
                else self.memories.get
            )
            record = get(
                owner_id=scope.owner_id,
                memory_id=UUID(dependency.entity_ref.entity_id),
                timeout=0.25,
            )
            state = (
                self.lifecycle.get_state(owner_id=scope.owner_id, memory_id=record.id)
                if self.lifecycle is not None
                else MemoryLifecycleState(owner_id=scope.owner_id, memory_id=record.id)
            )
            if isinstance(record, DerivedMemory):
                if (
                    memory_dependency(record, state, acting_user_id=scope.acting_user_id)
                    != dependency
                ):
                    return False
                for source in record.sources:
                    original = self.memories.get(
                        owner_id=scope.owner_id, memory_id=source.memory_id
                    )
                    original_state = (
                        self.lifecycle.get_state(owner_id=scope.owner_id, memory_id=original.id)
                        if self.lifecycle
                        else MemoryLifecycleState(owner_id=scope.owner_id, memory_id=original.id)
                    )
                    if (
                        embedding_space_for(original) != embedding_space_for(record)
                        or source.excerpt != original.content
                        or source.source_fingerprint != original.source_fingerprint
                        or source.source_conversation_id != original.source_conversation_id
                        or source.source_turn_id != original.source_turn_id
                        or source.source_message_ids != original.source_message_ids
                        or source.dependency_version is None
                        and original_state.validity_epoch > 0
                        or source.dependency_version is not None
                        and source.dependency_version
                        != dependency_version(original, original_state)
                        or not self.is_current(
                            memory_dependency(
                                original, original_state, acting_user_id=scope.acting_user_id
                            )
                        )
                    ):
                        return False
                return True
            if self.application_registry is None:
                active = self.messages.list_active(
                    owner_id=scope.owner_id,
                    conversation_id=record.source_conversation_id,
                    timeout=0.25,
                )
                if any(
                    item.id == record.source_turn_id
                    and item.attribution is not None
                    and item.attribution.execution_origin == "manual_import"
                    for item in active
                ):
                    return False
            return (
                memory_dependency(record, state, acting_user_id=scope.acting_user_id) == dependency
                and original_reason(
                    record,
                    self.settings,
                    self.messages,
                    self.lifecycle,
                    timeout=0.25,
                    now=self.clock(),
                    application_context=application_context,
                )
                is None
            )
        except Exception:  # noqa: BLE001 - unavailable/deleted/changed authority fails closed
            return False


def record_dependencies(record, repository, lifecycle):
    scope = current_request_scope()
    actor = scope.acting_user_id if scope is not None else None
    originals = (
        [
            repository.get(owner_id=record.owner_id, memory_id=source.memory_id)
            for source in record.sources
        ]
        if isinstance(record, DerivedMemory)
        else [record]
    )
    dependencies = tuple(
        memory_dependency(
            original,
            lifecycle.get_state(owner_id=original.owner_id, memory_id=original.id)
            if lifecycle is not None
            else MemoryLifecycleState(owner_id=original.owner_id, memory_id=original.id),
            acting_user_id=actor,
        )
        for original in originals
    )
    if isinstance(record, DerivedMemory):
        state = (
            lifecycle.get_state(owner_id=record.owner_id, memory_id=record.id)
            if lifecycle
            else MemoryLifecycleState(owner_id=record.owner_id, memory_id=record.id)
        )
        dependencies += (memory_dependency(record, state, acting_user_id=actor),)
    return dependencies


def injection_dependencies(retrieval, record):
    dependencies = dict(retrieval.permission_dependencies).get(record.id, ())
    # One derived node revalidates its entire canonical source set. Keep all
    # original edges in the retrieval trace; avoid multiplying summary fan-in.
    views = tuple(dep for dep in dependencies if dep.permission_id == "ai_memory_view")
    return (
        views
        or dependencies
        or (
            ContextPermissionDependency(
                permission_id="ai_memory_read",
                version="unverified",
                purpose="missing canonical memory dependencies",
            ),
        )
    )

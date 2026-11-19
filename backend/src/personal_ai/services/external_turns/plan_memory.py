"""An exact canonical PAS memory read under two application-plan disclosures."""

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

from personal_ai.auth.dispatch_grants import ApplicationPlanScope
from personal_ai.auth.scope import (
    ApplicationScope,
    bind_request_scope,
    current_request_scope,
    reset_request_scope,
)
from personal_ai.context.deadline import remaining
from personal_ai.context.providers import ContextPreparationError
from personal_ai.memory.contracts import RetrievalResult, ScoredMemory
from personal_ai.memory.dependencies import memory_dependency
from personal_ai.services.external_turns.contracts import digest

PREFIX = "application-plan-memory:"
PURPOSES = ("runtime-handoff", "inference-disclosure")
ORIGIN = "approved-pas-memory-origin"
MAX_MEMORY_BYTES = 1024


@dataclass(frozen=True)
class MemoryDisclosure:
    scope: ApplicationPlanScope
    origin: ApplicationScope
    memory_id: UUID
    recipient: str
    epoch: int
    expires_at: datetime

    def dependency(self, canonical, purpose):
        return canonical.model_copy(
            update={
                "permission_id": PREFIX + purpose,
                "purpose": purpose,
                "version": digest(
                    [
                        self.scope.model_dump(mode="json"),
                        self.recipient,
                        self.epoch,
                        self.expires_at.isoformat(),
                        canonical.version,
                    ]
                ),
            }
        )


class ApplicationPlanMemory:
    permission_namespaces = (PREFIX,)

    def __init__(self, reader, *, current_scope, current_disclosures, source_rights, clock=None):
        self.reader = reader
        self.current_scope = current_scope
        self.current_disclosures = current_disclosures
        self.source_rights = source_rights
        self.clock = clock or (lambda: datetime.now(UTC))

    def supports(self, dependency):
        return dependency.permission_id.startswith(PREFIX)

    def _grants(self):
        scope = self.current_scope()
        grants = self.current_disclosures(scope)
        if len(grants) != 2:
            raise ContextPreparationError("context_source_authority_changed")
        local, model = grants
        now = self.clock()
        if (
            local.scope != scope
            or model.scope != scope
            or local.recipient != scope.local_recipient
            or model.recipient != scope.model_recipient
            or local.memory_id != model.memory_id
            or local.origin != model.origin
            or any(grant.epoch < 1 or not now < grant.expires_at for grant in grants)
        ):
            raise ContextPreparationError("context_source_authority_changed")
        return scope, grants

    def _record(self, scope, grant, timeout):
        request = current_request_scope()
        if (
            request is None
            or (request.owner_id, request.acting_user_id)
            != (
                scope.owner_id,
                scope.actor_id,
            )
            or self.source_rights(scope, grant.origin) is not True
        ):
            raise ContextPreparationError("context_source_authority_changed")
        token = bind_request_scope(request.model_copy(update=grant.origin.model_dump()))
        try:
            record = self.reader.memories.get(
                owner_id=scope.owner_id,
                memory_id=grant.memory_id,
                timeout=timeout,
            )
            state = self.reader.lifecycle.get_state(owner_id=scope.owner_id, memory_id=record.id)
            canonical = memory_dependency(record, state, acting_user_id=scope.actor_id)
            if (
                canonical.source_scope != grant.origin
                or canonical.permission_id != "ai_memory_source"
                or not self.reader.is_current(canonical)
            ):
                raise ContextPreparationError("context_source_authority_changed")
        finally:
            reset_request_scope(token)
        # The context adapter receives a destination-scoped projection. The
        # canonical record and all revalidation edges retain their origin.
        return record.model_copy(
            update={
                "application_id": scope.application_id,
                "workspace_id": scope.workspace_id,
            }
        ), canonical

    @staticmethod
    def _origin_dependency(canonical):
        return canonical.model_copy(update={"permission_id": PREFIX + ORIGIN, "purpose": ORIGIN})

    def is_current(self, dependency):
        scope, grants = self._grants()
        if dependency.purpose not in (*PURPOSES, ORIGIN) or dependency.entity_ref is None:
            return False
        grant = grants[1] if dependency.purpose == PURPOSES[1] else grants[0]
        if dependency.entity_ref.entity_id != str(grant.memory_id):
            return False
        _, canonical = self._record(scope, grant, 0.25)
        if dependency.purpose == ORIGIN:
            return dependency == self._origin_dependency(canonical)
        return dependency == grant.dependency(canonical, dependency.purpose)

    def retrieve(self, _application_context, deadline):
        scope, grants = self._grants()
        try:
            record, canonical = self._record(scope, grants[0], min(0.25, remaining(deadline)))
        except Exception:  # noqa: BLE001 - no details about removed or foreign records
            raise ContextPreparationError("context_source_authority_changed") from None
        if len(record.content.encode("utf-8")) > MAX_MEMORY_BYTES:
            raise ContextPreparationError("context_authority_exceeds_bound")
        dependencies = (
            self._origin_dependency(canonical),
            *(
                grant.dependency(canonical, purpose)
                for grant, purpose in zip(grants, PURPOSES, strict=True)
            ),
        )
        return RetrievalResult(
            selected=(ScoredMemory(record, 1.0),),
            permission_dependencies=((record.id, dependencies),),
        )

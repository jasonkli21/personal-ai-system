"""Explicit synthetic request identity around the real shared memory builder."""

from personal_ai.auth.scope import RequestScope, bind_request_scope, reset_request_scope
from personal_ai.context import ContextAssembler
from personal_ai.memory.dependencies import MemoryPermissionRevalidator


class MemoryFixtureAssembler(ContextAssembler):
    def __init__(self, settings, counter, *args, memories, messages, lifecycle=None, **kwargs):
        super().__init__(
            settings,
            counter,
            *args,
            permission_revalidator=MemoryPermissionRevalidator(
                settings, memories, messages, lifecycle
            ),
            **kwargs,
        )

    def assemble(self, active, pending, **kwargs):
        token = bind_request_scope(
            RequestScope(
                owner_id=pending.owner_id,
                application_id=pending.application_id,
                workspace_id=pending.workspace_id,
                request_id="synthetic-memory-evaluation",
            )
        )
        try:
            return super().assemble(active, pending, **kwargs)
        finally:
            reset_request_scope(token)

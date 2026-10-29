"""Hermetic MEM-2 host. Not imported by application or provider composition."""

from contextlib import contextmanager

from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import RequestScope, bind_verified_principal, reset_verified_principal
from personal_ai.evaluation.knowledge_runtime import (
    NOW,
    HermeticKnowledgeAuthority,
    messages_stub,
    request,
)
from personal_ai.evaluation.memory_knowledge import make_proposal
from personal_ai.memory.control_repository import InMemoryControlRepository
from personal_ai.memory.control_service import MemoryControlService
from personal_ai.memory.knowledge_service import KnowledgeService
from personal_ai.memory.lifecycle.repositories import InMemoryMemoryLifecycleRepository
from personal_ai.memory.repositories import InMemoryMemoryRepository
from personal_ai.settings import Settings


class ControlRuntime:
    def __init__(self):
        self.now = NOW
        self.scope = RequestScope(
            owner_id="synthetic-owner",
            acting_user_id="test-issuer|actor-a",
            workspace_id="repo-alpha",
            request_id="mem2-run",
        )
        self.settings = Settings(
            _env_file=None,
            ai_provider="gemini",
            ai_model="synthetic",
            memory_enabled=True,
            memory_knowledge_selection_enabled=True,
            memory_knowledge_admission_enabled=True,
            memory_agent_tools_enabled=True,
            memory_user_management_enabled=True,
            memory_user_mutations_enabled=True,
        )
        messages = messages_stub()
        self.memories = InMemoryMemoryRepository(messages)
        self.lifecycle = InMemoryMemoryLifecycleRepository(self.memories, messages)
        self.authority = HermeticKnowledgeAuthority(self.scope)
        self.knowledge = KnowledgeService(
            self.settings, self.memories, self.lifecycle, self.authority, clock=lambda: self.now
        )
        self.repository = InMemoryControlRepository(self.memories, self.lifecycle)
        self.service = self.for_scope(self.scope)
        self.principal = AuthenticatedPrincipal(
            issuer="test-issuer",
            subject="actor-a",
            owner_id=self.scope.owner_id,
            email=None,
            issued_at=int(NOW.timestamp()),
            authenticated=True,
            authenticated_at=int(NOW.timestamp()),
        )

    def for_scope(self, scope):
        return MemoryControlService(
            self.knowledge, self.repository, scope, "repo-alpha", clock=lambda: self.now
        )

    @contextmanager
    def user(self, scope=None, principal=None):
        with request(scope or self.scope):
            token = bind_verified_principal(principal or self.principal)
            try:
                yield
            finally:
                reset_verified_principal(token)

    def seed(self, run_id="seed"):
        p = make_proposal("procedure", "make backend-lint")
        ref = self.authority.complete_task_a(self.scope, "repo-alpha", p, run_id=run_id)
        outcome = self.knowledge.admit(self.scope, "repo-alpha", ref, p)
        if outcome.status != "created":
            raise RuntimeError("hermetic_seed_failed")
        return self.memories.get_knowledge(
            owner_id=self.scope.owner_id, memory_id=outcome.record_id
        )

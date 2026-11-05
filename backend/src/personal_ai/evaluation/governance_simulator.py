"""Public synthetic host/atomic store. Not imported by application composition.

Identity is exact object registration, not matching serialized request fields.
This is an E1 test adapter, not authentication, durable storage or a Python sandbox.
"""

from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from threading import RLock
from uuid import NAMESPACE_URL, uuid5

from personal_ai.auth.scope import ApplicationScope, RequestScope
from personal_ai.memory.governance.contracts import MemoryScope, ShareIntent, SourceReference
from personal_ai.memory.governance.policy import HostState
from personal_ai.memory.governance.service import GovernanceService, Ledger, overlay_identity


def uid(name):
    return uuid5(NAMESPACE_URL, "synthetic-governance:" + name)


class SyntheticStore:
    def __init__(self):
        self.lock = RLock()
        self.ledgers = {}
        self.available = True
        self.lost_ack = False
        self.surviving = {}
        # Trusted synthetic bootstrap is separate from restorable ledger state.
        self.registered_owners = set()

    def bootstrap_owner(self, owner):
        """Explicitly register a fresh synthetic owner before serving requests."""
        with self.lock:
            if owner in self.registered_owners:
                return
            ledger = Ledger()
            self.ledgers[owner] = ledger
            self.surviving[owner] = overlay_identity(ledger)
            self.registered_owners.add(owner)

    @contextmanager
    def transaction(self, owner):
        with self.lock:
            if not self.available:
                raise OSError("synthetic_storage_unavailable")
            yield

    def load(self, owner):
        return self.ledgers.get(owner, Ledger())

    def save(self, owner, ledger):
        self.ledgers[owner] = ledger
        # Deliberately outside the snapshot: E1 model of separately surviving authority.
        self.surviving[owner] = overlay_identity(ledger)
        if self.lost_ack:
            self.lost_ack = False
            raise OSError("synthetic_lost_ack")


class SyntheticHost:
    def __init__(self, store, *, pair="default", owner="owner-a"):
        self.owner = owner
        self.pair = pair
        self.lock = RLock()
        self.store = store
        self.store.bootstrap_owner(owner)
        from personal_ai.evaluation.knowledge_runtime import NOW

        self.now = NOW
        self.source_scope = MemoryScope(
            owner=self.owner,
            agent="agent-source",
            application=ApplicationScope(application_id="travel", workspace_id="workspace-a"),
            project="project-a",
        )
        self.destination = MemoryScope(
            owner=self.owner,
            agent="agent-target",
            application=ApplicationScope(application_id="shopping", workspace_id="workspace-b"),
            project="project-b",
        )
        self.source = SourceReference(scope=self.source_scope, record=uid("source"), version="v1")
        self.manager = RequestScope(
            owner_id=self.owner,
            acting_user_id="owner-actor",
            application_id="travel",
            workspace_id="workspace-a",
            request_id="owner-request",
        )
        self.consumer = RequestScope(
            owner_id=self.owner,
            acting_user_id="agent-target",
            application_id="shopping",
            workspace_id="workspace-b",
            request_id="target-request",
        )
        self.other_owner = RequestScope(
            owner_id="owner-b" if self.owner == "owner-a" else "owner-a",
            acting_user_id="owner-b-actor",
            application_id="shopping",
            workspace_id="workspace-b",
            request_id="foreign-request",
        )
        self.proofs = {}
        self._install_canonical_source()
        self.state = HostState(
            self.source,
            self.destination,
            0,
            0,
            0,
            self.record.evidence.expires_at,
            True,
            True,
            True,
            True,
        )

    def _install_canonical_source(self):
        from personal_ai.evaluation.knowledge_runtime import (
            HermeticKnowledgeAuthority,
            messages_stub,
            request,
        )
        from personal_ai.evaluation.memory_knowledge import make_proposal
        from personal_ai.memory.knowledge_service import KnowledgeService
        from personal_ai.memory.lifecycle.repositories import InMemoryMemoryLifecycleRepository
        from personal_ai.memory.repositories import InMemoryMemoryRepository
        from personal_ai.settings import Settings

        self.canonical_scope = RequestScope(
            owner_id=self.owner,
            acting_user_id="agent-source",
            application_id="travel",
            workspace_id="workspace-a",
            request_id="canonical-source",
        )
        self.canonical_authority = HermeticKnowledgeAuthority(
            self.canonical_scope, project_id="project-a"
        )
        messages = messages_stub()
        self.canonical_repository = InMemoryMemoryRepository(messages)
        self.lifecycle = InMemoryMemoryLifecycleRepository(
            self.canonical_repository, messages, clock=lambda: self.now
        )
        settings = Settings(
            _env_file=None,
            ai_provider="gemini",
            ai_model="synthetic",
            memory_enabled=True,
            memory_knowledge_admission_enabled=True,
            memory_knowledge_selection_enabled=True,
        )
        self.canonical = KnowledgeService(
            settings,
            self.canonical_repository,
            self.lifecycle,
            self.canonical_authority,
            clock=lambda: self.now,
        )
        proposal = make_proposal("procedure", "make memory-eval")
        with request(self.canonical_scope):
            ref = self.canonical_authority.complete_task_a(
                self.canonical_scope, "project-a", proposal, run_id="source-" + self.pair
            )
            admitted = self.canonical.admit(self.canonical_scope, "project-a", ref, proposal)
        assert admitted.status == "created"
        with request(self.canonical_scope):
            self.record = self.canonical_repository.get_knowledge(
                owner_id=self.owner, memory_id=admitted.record_id
            )
        self.source = SourceReference(
            scope=self.source_scope, record=self.record.id, version=self.record.payload_fingerprint
        )

    @contextmanager
    def guard(self):
        from personal_ai.evaluation.knowledge_runtime import request

        with (
            self.lock,
            request(self.canonical_scope),
            self.canonical_authority._lock,
            self.canonical_repository.knowledge_consumption_guard(self.record),
        ):
            yield

    def approve(self, intent):
        # Only the test driver has this method. JSON/model output never calls it.
        self.proofs[intent.decision_proof] = intent.fingerprint(self.manager.acting_user_id)

    def manages(self, request, intent):
        return (
            request is self.manager
            and request.owner_id == intent.source.scope.owner
            and self.proofs.get(intent.decision_proof) == intent.fingerprint(request.acting_user_id)
        )

    def reader(self, request, destination):
        return (
            request is self.consumer
            and destination == self.destination
            and request.owner_id == destination.owner
            and request.acting_user_id == destination.agent
            and (request.application_id, request.workspace_id)
            == (destination.application.application_id, destination.application.workspace_id)
        )

    def recovery_current(self, owner):
        if owner not in self.store.registered_owners or owner not in self.store.surviving:
            return False
        return self.state.reconciled and overlay_identity(self.store.load(owner)) == self.store.surviving[owner]

    def resolve(self, source, destination):
        from personal_ai.evaluation.knowledge_runtime import request

        with request(self.canonical_scope):
            canonical_allowed = self.canonical.reason(self.record, self.canonical_scope) is None
        return replace(
            self.state,
            source_allowed=(
                self.state.source_allowed and canonical_allowed and self.state.source == self.source
            ),
            reconciled=(self.recovery_current(self.owner)),
        )

    def change(self, **changes):
        with self.lock:
            self.state = replace(self.state, **changes)

    def forget(self):
        from personal_ai.evaluation.knowledge_runtime import request
        from personal_ai.memory.lifecycle.contracts import MemoryLifecycleEvent
        from personal_ai.memory.lifecycle.repositories import event_idempotency_id

        with self.guard(), request(self.canonical_scope):
            result = self.lifecycle.apply_event(
                MemoryLifecycleEvent(
                    id=event_idempotency_id("governance-forget", "travel", "workspace-a"),
                    owner_id=self.owner,
                    memory_id=self.record.id,
                    application_id="travel",
                    workspace_id="workspace-a",
                    scope_version=2,
                    event_type="forgotten",
                    reason_code="developer_verification",
                    policy_version="verified-knowledge-v1",
                    actor="developer_test",
                    occurred_at=self.now,
                    idempotency_key="governance-forget",
                    expected_state_version=0,
                )
            )
            assert result.status == "applied"
        self.change(
            owner_epoch=self.state.owner_epoch + 1,
            owner_active=False,
            source_epoch=self.state.source_epoch + 1,
            source_allowed=False,
        )


class Fixture:
    def __init__(self, *, limits=None, no_host=False, pair="default", owner="owner-a"):
        self.store = SyntheticStore()
        self.host = SyntheticHost(self.store, pair=pair, owner=owner)
        self.service = GovernanceService(
            self.store, None if no_host else self.host, clock=lambda: self.host.now, limits=limits
        )

    def intent(self, name="grant", **changes):
        body = {
            "operation_id": uid(name),
            "operation": "grant",
            "grant_id": uid("grant"),
            "expected_revision": self.store.load(self.host.owner).revision,
            "source": self.host.source,
            "destination": self.host.destination,
            "decision_proof": name,
            "expires_at": self.host.now + timedelta(days=1),
        }
        body.update(changes)
        intent = ShareIntent(**body)
        self.host.approve(intent)
        return intent

    def grant(self):
        intent = self.intent()
        return intent, self.service.mutate(self.host.manager, intent)

    def revoke(self, intent):
        revoke = self.intent(
            "revoke",
            operation="revoke",
            grant_id=intent.grant_id,
            source=intent.source,
            destination=intent.destination,
            expires_at=intent.expires_at,
        )
        return self.service.mutate(self.host.manager, revoke)

    def observe(self, intent, **kwargs):
        return self.service.observe(self.host.consumer, intent.grant_id, **kwargs)

    def snapshot(self):
        return {
            "ledger": overlay_identity(self.store.load(self.host.owner)),
            "state": repr(self.host.state),
            "now": self.host.now.isoformat(),
        }

    def pack(self, intent, selected, *, counter=None):
        """Shared context builder under the synthetic source lease, with current dependencies."""
        from personal_ai.context.builder import ContextBuilder, ContextBuildItem, ContextBuildPolicy
        from personal_ai.context.tokens import FakeTokenCounter
        from personal_ai.contracts.context_references import ContextPermissionDependency
        from personal_ai.llm.client import ChatMessage

        fixture = self
        dependency = ContextPermissionDependency(
            permission_id="synthetic_memory_share",
            version=selected.grant_fingerprint or "denied",
            purpose="assist_response",
        )

        class Current:
            def is_current(self, candidate):
                return candidate == dependency and fixture.observe(intent, prior=selected).allowed

        with self.host.guard():
            entries = [
                ContextBuildItem(
                    source_class="ai_memory",
                    provider_id="synthetic_memory_share",
                    source_id=str(self.host.record.id),
                    item_id=str(intent.grant_id),
                    content="Historical advice: " + self.host.record.proposal.claim,
                    authority="derived",
                    sensitivity="public",
                    permission_dependencies=(dependency,),
                )
            ]
            built = ContextBuilder(
                counter or FakeTokenCounter(),
                permission_revalidator=Current(),
                clock=lambda: self.host.now,
            ).build(
                [ChatMessage(role="user", content="What historical check succeeded?")],
                entries,
                ContextBuildPolicy.for_settings(self.host.canonical.settings, 4096),
            )
            return built

    def consume(self, intent, selected, built):
        # No callback or transport: the sole E1 consumer observes a fixed predicate.
        with self.host.guard():
            if not self.observe(intent, prior=selected).allowed:
                return False
            return bool(built.manifest.injected_item_ids) and any(
                self.host.record.proposal.claim in message.content for message in built.messages
            )

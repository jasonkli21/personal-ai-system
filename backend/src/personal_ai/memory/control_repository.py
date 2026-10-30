"""Pure control decisions and atomic in-memory implementation; no knowledge admission."""

from datetime import timedelta
from uuid import NAMESPACE_URL, uuid5

from personal_ai.memory.control_contracts import OperationReceipt, OperationResult, PendingProposal
from personal_ai.memory.knowledge import digest
from personal_ai.memory.knowledge_repository import actor_namespace, request_scope_matches
from personal_ai.memory.lifecycle.contracts import MemoryLifecycleEvent
from personal_ai.memory.lifecycle.repositories import event_idempotency_id
from personal_ai.memory.lifecycle.transition import transition

PROPOSAL_CAP = 32
NON_FORGET_RECEIPT_CAP = 256


def operation_fingerprint(project, intent):
    return digest(
        {"project_id": project.project_id, "intent": intent.model_dump(mode="json")}
    )


def legacy_operation_fingerprint(project, intent):
    """Fingerprint written by migration 030 before project revision was separated."""
    return digest(
        {"project": project.model_dump(mode="json"), "intent": intent.model_dump(mode="json")}
    )


def operation_key(scope, identifier):
    return (*actor_namespace(scope), identifier)


def replay(receipt, fingerprint, now, *, legacy_fingerprint=None, project_id=None, intent=None):
    same_project_intent = (
        receipt.project_id is not None
        and receipt.project_id == project_id
        and intent is not None
        and receipt.operation_id == intent.operation_id
        and receipt.action == intent.action
        and receipt.actor == intent.actor
        and intent.action != "propose"
        and receipt.target_id == intent.target_id
        and receipt.expected_version == intent.expected_version
    )
    if receipt.fingerprint != fingerprint and receipt.fingerprint != legacy_fingerprint and not same_project_intent:
        return OperationResult(
            status="conflict", reason="operation_id_reused", operation_id=receipt.operation_id
        )
    if receipt.expires_at <= now:
        return OperationResult(
            status="expired", reason="operation_key_retired", operation_id=receipt.operation_id
        )
    return receipt.result.model_copy(update={"replayed": True})


def decide(scope, project, intent, now, *, pending=None, state=None):
    """Stage all changes before commit; cannot admit or revise a claim."""
    updated, event = None, None
    result = OperationResult(
        status="conflict",
        reason="expected_version_conflict",
        operation_id=intent.operation_id,
        target_id=intent.target_id,
        version=state.state_version if state else pending.version if pending else None,
    )
    if intent.action == "propose":
        identifier = uuid5(
            NAMESPACE_URL,
            "memory-proposal:" + digest([list(actor_namespace(scope)), str(intent.operation_id)]),
        )
        pending = PendingProposal(
            id=identifier,
            project=project,
            content=intent.proposal,
            created_at=now,
            expires_at=now + timedelta(hours=24),
        )
        result = result.model_copy(
            update={
                "status": "proposed_for_review",
                "reason": "untrusted_pending_only",
                "target_id": identifier,
                "version": 0,
            }
        )
    elif intent.action in {"reviewed", "rejected"}:
        if pending is None:
            return (
                OperationResult(status="forbidden_or_not_found", reason="target_unavailable"),
                None,
                None,
                None,
            )
        if pending.project != project:
            result = result.model_copy(
                update={"status": "stale_evidence", "reason": "project_changed"}
            )
        elif pending.expires_at <= now:
            result = result.model_copy(update={"status": "expired", "reason": "proposal_expired"})
        elif pending.version == intent.expected_version and pending.status == "pending":
            pending = pending.model_copy(
                update={"status": intent.action, "version": pending.version + 1}
            )
            result = result.model_copy(
                update={
                    "status": intent.action,
                    "reason": "review_is_not_admission",
                    "version": pending.version,
                }
            )
    elif (
        state is not None
        and state.state_version == intent.expected_version
        and state.retrieval_status == "active"
    ):
        key = "mem2:" + digest([list(actor_namespace(scope)), str(intent.operation_id)])
        event = MemoryLifecycleEvent(
            id=event_idempotency_id(key),
            owner_id=scope.owner_id,
            application_id=scope.application_id,
            workspace_id=scope.workspace_id,
            scope_version=2,
            memory_id=intent.target_id,
            event_type="forgotten",
            reason_code="explicit_user_forget",
            policy_version="memory-control-v1",
            actor="verified_user",
            occurred_at=now,
            idempotency_key=key,
            expected_state_version=intent.expected_version,
        )
        updated = transition(state, event)
        result = result.model_copy(
            update={
                "status": "applied",
                "reason": "durably_forgotten",
                "version": updated.state_version,
            }
        )
    receipt = OperationReceipt(
        operation_id=intent.operation_id,
        fingerprint=operation_fingerprint(project, intent),
        actor=intent.actor,
        action=intent.action,
        target_id=result.target_id,
        expected_version=intent.expected_version,
        result=result,
        created_at=now,
        project_id=project.project_id,
        expires_at=now
        + (timedelta(hours=24) if intent.action == "propose" else timedelta(days=30)),
    )
    return result, pending, (updated, event) if event else None, receipt


class InMemoryControlRepository:
    def __init__(self, memories, lifecycle):
        self.memories, self.lifecycle = memories, lifecycle
        # Share state across service/session instances on the canonical memory repository.
        if not hasattr(memories, "control_proposals"):
            memories.control_proposals, memories.control_receipts = {}, {}

    def _check(self, scope):
        if (
            not request_scope_matches(scope)
            or scope.owner_id in self.memories.knowledge_fenced_owners
        ):
            raise ValueError("control_scope_unavailable")

    def reconcile(self, scope, project, intent, now):
        self._check(scope)
        with self.memories.knowledge_consumption_guard(scope):
            receipt = self.memories.control_receipts.get(operation_key(scope, intent.operation_id))
            return (
                replay(
                    receipt,
                    operation_fingerprint(project, intent),
                    now,
                    legacy_fingerprint=legacy_operation_fingerprint(project, intent),
                    project_id=project.project_id,
                    intent=intent,
                )
                if receipt
                else None
            )

    def list_pending(self, scope, project, now):
        self._check(scope)
        with self.memories.knowledge_consumption_guard(scope):
            return tuple(
                p
                for key, p in self.memories.control_proposals.items()
                if key[:4] == actor_namespace(scope) and p.project == project and p.expires_at > now
            )

    def execute(self, scope, project, intent, now):
        with self.memories.knowledge_consumption_guard(scope), self.lifecycle._lock:
            self._check(scope)
            receipt = self.reconcile(scope, project, intent, now)
            if receipt:
                return receipt
            ns = actor_namespace(scope)
            receipts = self.memories.control_receipts
            proposals = self.memories.control_proposals
            # Erase expired content; never prune operation anti-replay keys.
            for key, value in list(proposals.items()):
                if key[:4] == ns and value.expires_at <= now:
                    del proposals[key]
            if (
                intent.action != "forget"
                and sum(
                    key[:4] == ns and receipt.action != "forget"
                    for key, receipt in receipts.items()
                )
                >= NON_FORGET_RECEIPT_CAP
            ) or (
                intent.action == "propose" and sum(key[:4] == ns for key in proposals) >= PROPOSAL_CAP
            ):
                return OperationResult(status="limit_exceeded", reason="control_capacity")
            state = None
            if intent.action == "forget":
                record = self.memories.get_knowledge(
                    owner_id=scope.owner_id, memory_id=intent.target_id
                )
                if record.project.project_id != project.project_id:
                    return OperationResult(
                        status="forbidden_or_not_found", reason="target_unavailable"
                    )
                state = self.lifecycle.get_state(owner_id=scope.owner_id, memory_id=record.id)
            pending = proposals.get(operation_key(scope, intent.target_id))
            result, pending, change, receipt = decide(
                scope, project, intent, now, pending=pending, state=state
            )
            if receipt is None:
                return result
            if change:
                updated, event = change
                self.lifecycle.events.setdefault((scope.owner_id, event.memory_id), []).append(
                    event
                )
                self.lifecycle.events_by_key[
                    (scope.application_id, scope.workspace_id, event.idempotency_key)
                ] = event
                self.lifecycle.states[(scope.owner_id, event.memory_id)] = updated
            if pending:
                proposals[operation_key(scope, pending.id)] = pending
            receipts[operation_key(scope, intent.operation_id)] = receipt
            return result

    def erase_owner(self, owner_id):
        """Fake of the fenced operator deletion seam, covering all actor namespaces."""
        with self.memories.messages._mutation_lock, self.memories._lock:
            if owner_id not in self.memories.knowledge_fenced_owners:
                raise ValueError("owner_fence_required")
            for mapping in (self.memories.control_proposals, self.memories.control_receipts):
                for key in list(mapping):
                    if key[0] == owner_id:
                        del mapping[key]

    def purge_expired_proposals(self, *, as_of, limit=100):
        """Erase expired pending content in bounded batches, including idle actors."""
        if not 1 <= limit <= 100:
            raise ValueError("control_purge_limit_invalid")
        with self.memories._lock:
            expired = sorted(
                (
                    (key, proposal)
                    for key, proposal in self.memories.control_proposals.items()
                    if proposal.expires_at <= as_of
                ),
                key=lambda item: (item[1].expires_at, item[0]),
            )[:limit]
            for key, _ in expired:
                del self.memories.control_proposals[key]
            return len(expired)

"""Atomic MEM-2 control operations in the canonical memory database."""

from contextlib import contextmanager

from personal_ai.memory.control_contracts import OperationReceipt, OperationResult, PendingProposal
from personal_ai.memory.control_repository import (
    PROPOSAL_CAP,
    RECEIPT_CAP,
    decide,
    operation_fingerprint,
    replay,
)
from personal_ai.memory.knowledge import KnowledgeRecord
from personal_ai.memory.knowledge_repository import request_scope_matches, source_actor_key
from personal_ai.persistence.postgres import _ensure_namespace
from personal_ai.persistence.postgres.owner_lifecycle import assert_owner_unfenced, lock_owner
from personal_ai.storage.errors import ResourceNotFoundError


class PostgresControlRepository:
    def __init__(self, memories, lifecycle):
        self.memories, self.lifecycle, self.database = memories, lifecycle, memories.database

    @contextmanager
    def _transaction(self, scope):
        if not request_scope_matches(scope):
            raise ValueError("control_scope_unavailable")
        with self.database.connection(timeout_seconds=2) as connection:
            assert_owner_unfenced(connection, scope.owner_id)
            sid = _ensure_namespace(connection, scope.owner_id, scope)
            actor = source_actor_key(scope.acting_user_id)
            self.memories._knowledge_lock(connection, sid, actor)
            yield connection, sid, actor

    @staticmethod
    def _receipt(connection, sid, actor, identifier):
        row = connection.execute(
            "SELECT payload FROM memory_control_operations WHERE scope_id=%s AND actor_key=%s AND record_id=%s",
            (sid, actor, identifier),
        ).fetchone()
        return OperationReceipt.model_validate(row[0]) if row else None

    def reconcile(self, scope, project, intent, now):
        with self._transaction(scope) as (connection, sid, actor):
            receipt = self._receipt(connection, sid, actor, intent.operation_id)
            return replay(receipt, operation_fingerprint(project, intent), now) if receipt else None

    def list_pending(self, scope, project, now):
        with self._transaction(scope) as (connection, sid, actor):
            rows = connection.execute(
                "SELECT payload FROM memory_control_proposals WHERE scope_id=%s AND actor_key=%s AND project_id=%s AND expires_at>%s ORDER BY record_id LIMIT 32",
                (sid, actor, project.project_id, now),
            ).fetchall()
            return tuple(
                p
                for row in rows
                if (p := PendingProposal.model_validate(row[0])).project == project
            )

    def execute(self, scope, project, intent, now):
        with self._transaction(scope) as (connection, sid, actor):
            old = self._receipt(connection, sid, actor, intent.operation_id)
            if old:
                return replay(old, operation_fingerprint(project, intent), now)
            connection.execute(
                "DELETE FROM memory_control_proposals WHERE scope_id=%s AND actor_key=%s AND expires_at<=%s",
                (sid, actor, now),
            )
            count = connection.execute(
                "SELECT count(*) FROM memory_control_operations WHERE scope_id=%s AND actor_key=%s",
                (sid, actor),
            ).fetchone()[0]
            proposals = connection.execute(
                "SELECT count(*) FROM memory_control_proposals WHERE scope_id=%s AND actor_key=%s",
                (sid, actor),
            ).fetchone()[0]
            if count >= RECEIPT_CAP or (intent.action == "propose" and proposals >= PROPOSAL_CAP):
                return OperationResult(status="limit_exceeded", reason="control_capacity")
            state, pending = None, None
            if intent.action == "forget":
                row = connection.execute(
                    "SELECT payload FROM memory_knowledge WHERE scope_id=%s AND record_id=%s AND payload->>'acting_user_id' IS NOT DISTINCT FROM %s",
                    (sid, str(intent.target_id), scope.acting_user_id),
                ).fetchone()
                if not row:
                    raise ResourceNotFoundError("target_unavailable")
                record = KnowledgeRecord.model_validate(row[0])
                if record.project != project or not self.memories._knowledge_sources_current_tx(
                    connection, record, sid
                ):
                    return OperationResult(status="stale_evidence", reason="source_changed")
                state, _ = self.lifecycle._read_state(
                    connection, scope.owner_id, intent.target_id, scope, lock=True
                )
            elif intent.target_id:
                row = connection.execute(
                    "SELECT payload FROM memory_control_proposals WHERE scope_id=%s AND actor_key=%s AND record_id=%s FOR UPDATE",
                    (sid, actor, intent.target_id),
                ).fetchone()
                pending = PendingProposal.model_validate(row[0]) if row else None
            result, pending, change, receipt = decide(
                scope, project, intent, now, pending=pending, state=state
            )
            if receipt is None:
                return result
            if change:
                _, event = change
                applied = self.lifecycle._apply_event_tx(connection, event, verified_control=True)
                if applied["status"] != "applied":
                    raise ValueError("control_transition_failed")
            if pending:
                connection.execute(
                    "INSERT INTO memory_control_proposals(scope_id,actor_key,record_id,project_id,expires_at,payload) VALUES (%s,%s,%s,%s,%s,%s::jsonb) ON CONFLICT (scope_id,actor_key,record_id) DO UPDATE SET payload=EXCLUDED.payload",
                    (
                        sid,
                        actor,
                        pending.id,
                        pending.project.project_id,
                        pending.expires_at,
                        pending.model_dump_json(),
                    ),
                )
            connection.execute(
                "INSERT INTO memory_control_operations(scope_id,actor_key,record_id,payload) VALUES (%s,%s,%s,%s::jsonb)",
                (sid, actor, intent.operation_id, receipt.model_dump_json()),
            )
        # Context exit has committed all effects before success can be returned.
        return result

    def erase_owner(self, owner_id):
        """Operator deletion seam: require the existing irreversible owner fence."""
        with self.database.connection(timeout_seconds=2) as connection:
            lock_owner(connection, owner_id)
            if not connection.execute(
                "SELECT 1 FROM owner_lifecycle_fences WHERE owner_id=%s", (owner_id,)
            ).fetchone():
                raise ValueError("owner_fence_required")
            for table in ("memory_control_proposals", "memory_control_operations"):
                connection.execute(
                    f"DELETE FROM {table} c USING scope_namespaces n WHERE c.scope_id=n.scope_id AND n.owner_id=%s",
                    (owner_id,),
                )

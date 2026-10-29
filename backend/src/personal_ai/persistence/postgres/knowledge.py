"""Schema-3 methods mixed into the canonical Postgres memory repository."""

from contextlib import contextmanager

from personal_ai.auth.scope import current_application_scope, current_request_scope, scope_matches
from personal_ai.memory.knowledge import KnowledgeRecord
from personal_ai.memory.knowledge_repository import (
    MAX_KNOWLEDGE_RECORDS,
    MAX_KNOWLEDGE_SOURCES,
    request_scope_matches,
    source_actor_key,
    validate_knowledge,
)
from personal_ai.persistence.postgres import PostgresPayloadRepository, _ensure_namespace
from personal_ai.persistence.postgres.owner_lifecycle import assert_owner_unfenced
from personal_ai.storage.errors import ResourceNotFoundError


class PostgresKnowledgeMethods:
    @staticmethod
    def _knowledge_lock(connection, scope_id, actor_key=None):
        # One namespace lock also serializes bounded storage budgets, source
        # tombstones, admissions, lifecycle effects and guarded consumption.
        # Transaction-scoped: a lost connection releases it without a new job.
        lock_names = ["knowledge:" + scope_id]
        if actor_key is not None:
            lock_names.append("knowledge-source:" + scope_id + ":" + actor_key)
        for name in lock_names:
            connection.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))", (name,))

    @contextmanager
    def knowledge_consumption_guard(self, record):
        if not request_scope_matches(record):
            raise ValueError("knowledge_scope_invalid")
        scope_id = PostgresPayloadRepository.scope_id(record.owner_id, current_application_scope())
        with self.database.connection(timeout_seconds=5) as connection:
            assert_owner_unfenced(connection, record.owner_id)
            self._knowledge_lock(connection, scope_id, source_actor_key(record.acting_user_id))
            yield

    def create_knowledge(self, record, *, timeout=5):
        record = validate_knowledge(record)
        scope = current_application_scope()
        with self.database.connection(timeout_seconds=timeout) as connection:
            assert_owner_unfenced(connection, record.owner_id)
            scope_id = _ensure_namespace(connection, record.owner_id, scope)
            actor_key = source_actor_key(record.acting_user_id)
            self._knowledge_lock(connection, scope_id, actor_key)
            existing = connection.execute(
                "SELECT payload FROM memory_knowledge WHERE scope_id=%s AND admission_key=%s",
                (scope_id, record.admission_key),
            ).fetchone()
            if existing:
                old = KnowledgeRecord.model_validate(existing[0])
                if old.payload_fingerprint != record.payload_fingerprint:
                    raise ValueError("knowledge_identity_conflict")
                state_row = connection.execute(
                    "SELECT payload FROM memory_lifecycle_states WHERE scope_id=%s AND record_id=%s",
                    (scope_id, str(old.id)),
                ).fetchone()
                if state_row is None:
                    prior = connection.execute(
                        "SELECT 1 FROM memory_lifecycle_events WHERE scope_id=%s AND aggregate_id=%s LIMIT 1",
                        (scope_id, str(old.id)),
                    ).fetchone()
                    if prior:
                        raise ValueError("knowledge_lifecycle_missing")
                if state_row and (
                    state_row[0].get("validity_epoch", 0) != 0
                    or state_row[0].get("retrieval_status", "active") != "active"
                    or state_row[0].get("unresolved_conflict", False)
                ):
                    raise ValueError("knowledge_epoch_conflict")
                if not self._knowledge_sources_current_tx(connection, old, scope_id):
                    raise ValueError("knowledge_source_epoch_conflict")
                return old, False
            count = connection.execute(
                "SELECT count(*) FROM memory_knowledge WHERE scope_id=%s", (scope_id,)
            ).fetchone()[0]
            if count >= MAX_KNOWLEDGE_RECORDS:
                raise ValueError("knowledge_storage_budget")
            count = connection.execute(
                "SELECT count(*) FROM memory_knowledge_source_fences WHERE scope_id=%s", (scope_id,)
            ).fetchone()[0]
            for edge in sorted(record.evidence.edges, key=lambda e: (e.resolver_id, e.source_id)):
                current = connection.execute(
                    "SELECT epoch,fingerprint,active FROM memory_knowledge_source_fences WHERE scope_id=%s AND resolver_id=%s AND source_id=%s AND actor_key=%s FOR UPDATE",
                    (scope_id, edge.resolver_id, edge.source_id, actor_key),
                ).fetchone()
                if current:
                    if (current[0], current[1].strip(), current[2]) != (
                        edge.epoch,
                        edge.fingerprint,
                        True,
                    ):
                        raise ValueError("knowledge_source_epoch_conflict")
                else:
                    # Legacy orphan tombstones have no actor provenance after
                    # physical erasure. They remain a global replay deny for
                    # actors without an exact actor-scoped fence.
                    legacy = connection.execute(
                        "SELECT 1 FROM memory_knowledge_source_fences WHERE scope_id=%s AND resolver_id=%s AND source_id=%s AND actor_key='L'",
                        (scope_id, edge.resolver_id, edge.source_id),
                    ).fetchone()
                    if legacy:
                        raise ValueError("knowledge_source_epoch_conflict")
                    count += 1
                    if count > MAX_KNOWLEDGE_SOURCES:
                        raise ValueError("knowledge_source_budget")
                    connection.execute(
                        "INSERT INTO memory_knowledge_source_fences(scope_id,resolver_id,source_id,actor_key,epoch,fingerprint,active) VALUES (%s,%s,%s,%s,%s,%s,true)",
                        (
                            scope_id,
                            edge.resolver_id,
                            edge.source_id,
                            actor_key,
                            edge.epoch,
                            edge.fingerprint,
                        ),
                    )
            connection.execute(
                "INSERT INTO memory_knowledge(scope_id,record_id,owner_id,application_id,workspace_id,project_id,kind,authority,canonical_revision,admission_key,fingerprint,created_at,expires_at,payload) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                (
                    scope_id,
                    str(record.id),
                    record.owner_id,
                    record.application_id,
                    record.workspace_id,
                    record.project.project_id,
                    record.proposal.kind,
                    record.evidence.source_authority,
                    record.project.revision,
                    record.admission_key,
                    record.payload_fingerprint,
                    record.created_at,
                    record.evidence.expires_at,
                    PostgresPayloadRepository._json(record.model_dump(mode="json")),
                ),
            )
            for index, edge in enumerate(record.evidence.edges, 1):
                connection.execute(
                    "INSERT INTO memory_knowledge_sources(scope_id,record_id,source_ordinal,resolver_id,source_id,actor_key,source_epoch,source_fingerprint,relation) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                    (
                        scope_id,
                        str(record.id),
                        index,
                        edge.resolver_id,
                        edge.source_id,
                        actor_key,
                        edge.epoch,
                        edge.fingerprint,
                        edge.relation,
                    ),
                )
        # Leaving connection commits before the service may report created.
        return record, True

    def get_knowledge(self, *, owner_id, memory_id, timeout=5):
        scope = current_application_scope()
        request_scope = current_request_scope()
        if (
            request_scope is None
            or request_scope.owner_id != owner_id
            or request_scope.application_id != scope.application_id
            or request_scope.workspace_id != scope.workspace_id
        ):
            raise ResourceNotFoundError("knowledge not found")
        with self.database.connection(timeout_seconds=timeout) as connection:
            row = connection.execute(
                "SELECT payload FROM memory_knowledge WHERE scope_id=%s AND record_id=%s AND owner_id=%s AND application_id=%s AND workspace_id IS NOT DISTINCT FROM %s AND payload->>'acting_user_id' IS NOT DISTINCT FROM %s",
                (
                    PostgresPayloadRepository.scope_id(owner_id, scope),
                    str(memory_id),
                    owner_id,
                    scope.application_id,
                    scope.workspace_id,
                    request_scope.acting_user_id,
                ),
            ).fetchone()
        if row is None:
            raise ResourceNotFoundError("knowledge not found")
        return KnowledgeRecord.model_validate(row[0])

    def list_knowledge(self, *, scope, filters, limit, timeout=5):
        if not 1 <= limit <= 101 or not scope_matches(scope) or not request_scope_matches(scope):
            raise ValueError("knowledge_query_invalid")
        with self.database.connection(timeout_seconds=timeout) as connection:
            rows = connection.execute(
                "SELECT payload FROM memory_knowledge WHERE scope_id=%s AND owner_id=%s AND application_id=%s AND workspace_id IS NOT DISTINCT FROM %s AND payload->>'acting_user_id' IS NOT DISTINCT FROM %s AND project_id=%s AND kind=ANY(%s) AND authority=ANY(%s) ORDER BY created_at DESC,record_id LIMIT %s",
                (
                    PostgresPayloadRepository.scope_id(scope.owner_id, scope),
                    scope.owner_id,
                    scope.application_id,
                    scope.workspace_id,
                    scope.acting_user_id,
                    filters.project.project_id,
                    list(filters.kinds),
                    list(filters.authorities),
                    limit,
                ),
            ).fetchall()
        return tuple(KnowledgeRecord.model_validate(row[0]) for row in rows)

    @staticmethod
    def _knowledge_sources_current_tx(connection, record, scope_id):
        if connection.execute(
            "SELECT 1 FROM owner_lifecycle_fences WHERE owner_id=%s", (record.owner_id,)
        ).fetchone():
            return False
        rows = connection.execute(
            "SELECT e.source_id,e.resolver_id,e.source_fingerprint,e.source_epoch,e.relation,f.epoch,f.fingerprint,f.active FROM memory_knowledge_sources e JOIN memory_knowledge_source_fences f USING(scope_id,resolver_id,source_id,actor_key) WHERE e.scope_id=%s AND e.record_id=%s AND e.actor_key=%s ORDER BY e.source_ordinal",
            (scope_id, str(record.id), source_actor_key(record.acting_user_id)),
        ).fetchall()
        expected = [
            (e.source_id, e.resolver_id, e.fingerprint, e.epoch, e.relation)
            for e in record.evidence.edges
        ]
        return [tuple(row[:5]) for row in rows] == expected and all(
            row[3] == row[5] and row[2] == row[6] and row[7] for row in rows
        )

    def knowledge_sources_current(self, record, *, timeout=5):
        if not scope_matches(record) or not request_scope_matches(record):
            return False
        with self.database.connection(timeout_seconds=timeout) as connection:
            return self._knowledge_sources_current_tx(
                connection,
                record,
                PostgresPayloadRepository.scope_id(record.owner_id, current_application_scope()),
            )

    def revoke_knowledge_source(
        self, *, scope, resolver_id, source_id, expected_epoch, erase=False
    ):
        if not scope_matches(scope) or not request_scope_matches(scope):
            raise ValueError("knowledge_scope_invalid")
        with self.database.connection(timeout_seconds=5) as connection:
            scope_id = PostgresPayloadRepository.scope_id(scope.owner_id, scope)
            actor_key = source_actor_key(scope.acting_user_id)
            self._knowledge_lock(connection, scope_id, actor_key)
            row = connection.execute(
                "UPDATE memory_knowledge_source_fences SET epoch=epoch+1,active=false WHERE scope_id=%s AND resolver_id=%s AND source_id=%s AND actor_key=%s AND epoch=%s AND active RETURNING epoch",
                (scope_id, resolver_id, source_id, actor_key, expected_epoch),
            ).fetchone()
            if row is None:
                return False
            if erase:
                # Complete reverse traversal in one statement; no fan-out cap.
                connection.execute(
                    "DELETE FROM memory_knowledge k USING memory_knowledge_sources e WHERE k.scope_id=e.scope_id AND k.record_id=e.record_id AND e.scope_id=%s AND e.resolver_id=%s AND e.source_id=%s AND e.actor_key=%s",
                    (scope_id, resolver_id, source_id, actor_key),
                )
            return True

    def erase_expired_knowledge(self, *, scope, as_of, limit=100):
        if not 1 <= limit <= 100 or not scope_matches(scope) or not request_scope_matches(scope):
            raise ValueError("knowledge_retention_scope_invalid")
        with self.database.connection(timeout_seconds=5) as connection:
            scope_id = PostgresPayloadRepository.scope_id(scope.owner_id, scope)
            actor_key = source_actor_key(scope.acting_user_id)
            self._knowledge_lock(connection, scope_id, actor_key)
            rows = connection.execute(
                "SELECT record_id FROM memory_knowledge WHERE scope_id=%s AND payload->>'acting_user_id' IS NOT DISTINCT FROM %s AND expires_at<=%s ORDER BY expires_at,record_id LIMIT %s",
                (scope_id, scope.acting_user_id, as_of, limit),
            ).fetchall()
            identifiers = [row[0] for row in rows]
            # Epoch tombstones suppress retries even after physical payload erasure.
            connection.execute(
                "UPDATE memory_knowledge_source_fences f SET active=false,epoch=epoch+1 WHERE f.scope_id=%s AND f.actor_key=%s AND f.active AND EXISTS (SELECT 1 FROM memory_knowledge_sources e WHERE e.scope_id=f.scope_id AND e.resolver_id=f.resolver_id AND e.source_id=f.source_id AND e.actor_key=f.actor_key AND e.record_id=ANY(%s))",
                (scope_id, actor_key, identifiers),
            )
            erased = connection.execute(
                "DELETE FROM memory_knowledge WHERE scope_id=%s AND record_id=ANY(%s) RETURNING record_id",
                (scope_id, identifiers),
            ).fetchall()
            return len(erased)

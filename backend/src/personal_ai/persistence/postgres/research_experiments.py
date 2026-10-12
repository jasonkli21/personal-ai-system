"""Canonical compact research evaluation persistence, using shared scoped state."""

from hashlib import sha256

from personal_ai.auth.scope import ApplicationScope
from personal_ai.evaluation.retrieval_contracts import ResearchExperimentSummary
from personal_ai.persistence.postgres import PersistenceConflict, _ensure_namespace
from personal_ai.persistence.postgres.owner_lifecycle import assert_owner_unfenced
from personal_ai.persistence.postgres.repositories import PostgresPayloadRepository


class PostgresResearchExperimentRepository:
    def __init__(self, database):
        self.database = database
        self.records = PostgresPayloadRepository(database, "research_experiments")

    def save(self, summary):
        summary = ResearchExperimentSummary.model_validate(summary.model_dump())
        scope = ApplicationScope(
            application_id=summary.application_id, workspace_id=summary.workspace_id
        )
        payload = summary.model_dump_json()
        fingerprint = sha256(payload.encode()).hexdigest()
        with self.database.transaction() as connection:
            assert_owner_unfenced(connection, summary.owner_id)
            scope_id = _ensure_namespace(connection, summary.owner_id, scope)
            row = connection.execute(
                "INSERT INTO research_experiments(scope_id,record_id,owner_id,application_id,"
                "workspace_id,status,created_at,expires_at,fingerprint,idempotency_key,payload) "
                "VALUES(%s,%s,%s,%s,%s,'not_promoted',%s,%s,%s,%s,%s::jsonb) "
                "ON CONFLICT DO NOTHING RETURNING record_id",
                (scope_id, str(summary.id), summary.owner_id, scope.application_id,
                 scope.workspace_id, summary.created_at, summary.expires_at,
                 fingerprint, str(summary.id), payload),
            ).fetchone()
            if row is None:
                old = connection.execute(
                    "SELECT fingerprint FROM research_experiments WHERE scope_id=%s AND record_id=%s",
                    (scope_id, str(summary.id)),
                ).fetchone()
                if old is None or old[0] != fingerprint:
                    raise PersistenceConflict("research_experiment_identity_conflict")
        return summary

    def get(self, *, owner_id, scope, record_id):
        return ResearchExperimentSummary.model_validate(self.records.get(
            owner_id=owner_id, scope=scope, record_id=str(record_id)
        ))

    def scan(self, *, owner_id, scope, limit=100):
        if not 1 <= limit <= 100:
            raise ValueError("experiment_scan_limit")
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM research_experiments WHERE scope_id=%s AND owner_id=%s "
                "AND expires_at>now() ORDER BY created_at,record_id LIMIT %s",
                (self.records.scope_id(owner_id, scope), owner_id, limit + 1),
            ).fetchall()
        return tuple(ResearchExperimentSummary.model_validate(r[0]) for r in rows[:limit]), len(rows)<=limit

    def expire(self, *, owner_id, now, limit=100):
        if not 1 <= limit <= 100:
            raise ValueError("experiment_expiry_limit")
        with self.database.transaction() as connection:
            rows = connection.execute(
                "DELETE FROM research_experiments WHERE (scope_id,record_id) IN "
                "(SELECT scope_id,record_id FROM research_experiments WHERE owner_id=%s "
                "AND expires_at<=%s ORDER BY expires_at,record_id LIMIT %s FOR UPDATE SKIP LOCKED) "
                "RETURNING record_id", (owner_id, now, limit),
            ).fetchall()
        return len(rows)

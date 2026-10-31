"""Generic typed-family repositories and transaction helpers."""

from __future__ import annotations

import json
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, date, datetime
from typing import Any

from personal_ai.auth.scope import ApplicationScope

from .database import (
    PersistenceConflict,
    PersistenceRecordNotFound,
    PostgresDatabase,
)

FAMILY_TABLES = frozenset(
    {
        "memory_lifecycle_states",
        "memory_lifecycle_events",
        "research_sessions",
        "research_experiments",
        "research_request_keys",
        "iterative_research_runs",
        "iterative_research_request_keys",
        "canonical_entities",
        "entity_aliases",
        "entity_claims",
        "entity_matches",
        "decision_snapshots",
        "decision_evidence_snapshots",
        "candidate_evaluations",
        "domain_claim_extensions",
        "provider_observations",
        "domain_comparison_views",
        "domain_lookup_idempotency",
        "itinerary_proposals",
        "booking_document_extractions",
        "identity_mappings",
        "account_lifecycle_requests",
        "audit_events",
        "usage_budgets",
        "global_profiles",
        "profile_consents",
    }
)


class PostgresPayloadRepository:
    """Typed family-table access for bounded snapshots and transaction groups."""

    def __init__(self, database: PostgresDatabase, family: str) -> None:
        if family not in FAMILY_TABLES:
            raise ValueError("persistence_family_invalid")
        self.database = database
        self.family = family

    @staticmethod
    def scope_id(owner_id: str, scope: ApplicationScope) -> str:
        """Unambiguous scope identity; null workspace differs from every value."""
        parts = (owner_id, scope.application_id, scope.workspace_id)
        encoded = []
        for part in parts:
            if part is None:
                encoded.append("N")
            else:
                value = str(part)
                encoded.append(f"V{len(value.encode('utf-8'))}:{value}")
        return "S2" + "".join(encoded)

    @staticmethod
    def _json(value: Any) -> str:
        try:
            serialized = json.dumps(value, ensure_ascii=False, separators=(",", ":"))
        except (TypeError, ValueError) as error:
            raise ValueError("persistence_payload_invalid") from error
        if len(serialized.encode("utf-8")) > 262_144:
            raise ValueError("persistence_payload_too_large")
        return serialized

    def get(self, *, owner_id: str, scope: ApplicationScope, record_id: str) -> dict[str, Any]:
        query = f"SELECT payload FROM {self.family} WHERE scope_id = %s AND record_id = %s AND owner_id = %s AND application_id = %s AND workspace_id IS NOT DISTINCT FROM %s"
        with self.database.connection() as connection:
            row = connection.execute(
                query,
                (
                    self.scope_id(owner_id, scope),
                    record_id,
                    owner_id,
                    scope.application_id,
                    scope.workspace_id,
                ),
            ).fetchone()
        if row is None:
            raise PersistenceRecordNotFound("record not found")
        return row[0]

    def create(
        self,
        *,
        owner_id: str,
        scope: ApplicationScope,
        record_id: str,
        payload: dict[str, Any],
        status: str | None = None,
        revision: int = 1,
        created_at: datetime | None = None,
        expires_at: datetime | None = None,
        fingerprint: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        serialized = self._json(payload)
        timestamp = _datetime(created_at) or datetime.now(UTC)
        query = f"INSERT INTO {self.family}(record_id, scope_id, owner_id, application_id, workspace_id, record_version, status, revision, created_at, expires_at, fingerprint, idempotency_key, payload) VALUES (%s,%s,%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s::jsonb)"
        try:
            with self.database.connection() as connection:
                _ensure_namespace(connection, owner_id, scope)
                connection.execute(
                    query,
                    (
                        record_id,
                        self.scope_id(owner_id, scope),
                        owner_id,
                        scope.application_id,
                        scope.workspace_id,
                        status,
                        revision,
                        timestamp,
                        _datetime(expires_at),
                        fingerprint,
                        idempotency_key,
                        serialized,
                    ),
                )
        except Exception as error:
            if _is_unique_violation(error):
                raise PersistenceConflict("record identity already exists") from error
            raise
        return payload

    def get_replay(
        self,
        *,
        owner_id: str,
        scope: ApplicationScope,
        idempotency_key: str,
    ) -> tuple[str, str | None, dict[str, Any], int] | None:
        """Resolve a scoped replay key without disclosing another namespace."""
        if not idempotency_key or len(idempotency_key) > 300:
            raise ValueError("idempotency_key_invalid")
        with self.database.connection() as connection:
            row = connection.execute(
                f"SELECT record_id,fingerprint,payload,revision FROM {self.family} "
                "WHERE scope_id=%s AND owner_id=%s AND application_id=%s "
                "AND workspace_id IS NOT DISTINCT FROM %s AND idempotency_key=%s",
                (
                    self.scope_id(owner_id, scope),
                    owner_id,
                    scope.application_id,
                    scope.workspace_id,
                    idempotency_key,
                ),
            ).fetchone()
        return None if row is None else (row[0], row[1], row[2], row[3])

    def create_idempotent(
        self,
        *,
        owner_id: str,
        scope: ApplicationScope,
        record_id: str,
        idempotency_key: str,
        fingerprint: str,
        payload: dict[str, Any],
        status: str | None = None,
        created_at: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> tuple[dict[str, Any], bool]:
        """Commit an immutable family record and replay key in one transaction."""
        if not idempotency_key or len(idempotency_key) > 300:
            raise ValueError("idempotency_key_invalid")
        if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
            raise ValueError("fingerprint_invalid")
        try:
            with self.database.transaction() as connection:
                scope_id = _ensure_namespace(connection, owner_id, scope)
                existing = connection.execute(
                    f"SELECT record_id,fingerprint,payload FROM {self.family} "
                    "WHERE scope_id=%s AND idempotency_key=%s FOR UPDATE",
                    (scope_id, idempotency_key),
                ).fetchone()
                if existing is not None:
                    if existing[1] != fingerprint:
                        raise PersistenceConflict("idempotency fingerprint conflict")
                    return existing[2], False
                connection.execute(
                    f"INSERT INTO {self.family}(record_id,scope_id,owner_id,application_id,"
                    "workspace_id,record_version,status,revision,created_at,expires_at,fingerprint,"
                    "idempotency_key,payload) VALUES (%s,%s,%s,%s,%s,1,%s,1,%s,%s,%s,%s,%s::jsonb)",
                    (
                        record_id,
                        scope_id,
                        owner_id,
                        scope.application_id,
                        scope.workspace_id,
                        status,
                        _datetime(created_at) or datetime.now(UTC),
                        _datetime(expires_at),
                        fingerprint,
                        idempotency_key,
                        self._json(payload),
                    ),
                )
        except Exception as error:
            if not _is_unique_violation(error):
                raise
            replay = self.get_replay(
                owner_id=owner_id, scope=scope, idempotency_key=idempotency_key
            )
            if replay is None:
                raise PersistenceConflict(
                    "idempotency key conflicted with another record"
                ) from error
            if replay[1] != fingerprint:
                raise PersistenceConflict("idempotency fingerprint conflict") from error
            return replay[2], False
        return payload, True

    def append_event(
        self,
        *,
        owner_id: str,
        scope: ApplicationScope,
        aggregate_id: str,
        record_id: str,
        payload: dict[str, Any],
        fingerprint: str,
        idempotency_key: str,
        created_at: datetime | None = None,
    ) -> tuple[dict[str, Any], int, bool]:
        """Append one ordered event with scoped replay arbitration in one P transaction."""
        if self.family not in {"memory_lifecycle_events", "audit_events"}:
            raise ValueError("event_family_invalid")
        if not aggregate_id or len(aggregate_id) > 512:
            raise ValueError("aggregate_id_invalid")
        if len(fingerprint) != 64 or any(char not in "0123456789abcdef" for char in fingerprint):
            raise ValueError("fingerprint_invalid")
        timestamp = _datetime(created_at) or datetime.now(UTC)
        scope_id = self.scope_id(owner_id, scope)
        replay = self._get_event_replay(owner_id, scope, idempotency_key)
        if replay is not None:
            if replay[1] != fingerprint:
                raise PersistenceConflict("event idempotency fingerprint conflict")
            return replay[2], replay[3], False
        try:
            with self.database.transaction() as connection:
                _ensure_namespace(connection, owner_id, scope)
                connection.execute(
                    "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
                    (f"{scope_id}:{self.family}:{aggregate_id}",),
                )
                existing = connection.execute(
                    f"SELECT record_id,fingerprint,payload,event_sequence FROM {self.family} "
                    "WHERE scope_id=%s AND idempotency_key=%s FOR UPDATE",
                    (scope_id, idempotency_key),
                ).fetchone()
                if existing is not None:
                    if existing[1] != fingerprint:
                        raise PersistenceConflict("event idempotency fingerprint conflict")
                    return existing[2], existing[3], False
                sequence = connection.execute(
                    f"SELECT COALESCE(MAX(event_sequence),0)+1 FROM {self.family} "
                    "WHERE scope_id=%s AND aggregate_id=%s",
                    (scope_id, aggregate_id),
                ).fetchone()[0]
                connection.execute(
                    f"INSERT INTO {self.family}(record_id,scope_id,owner_id,application_id,"
                    "workspace_id,record_version,status,revision,event_sequence,aggregate_id,"
                    "created_at,fingerprint,idempotency_key,payload) "
                    "VALUES (%s,%s,%s,%s,%s,1,'active',1,%s,%s,%s,%s,%s,%s::jsonb)",
                    (
                        record_id,
                        scope_id,
                        owner_id,
                        scope.application_id,
                        scope.workspace_id,
                        sequence,
                        aggregate_id,
                        timestamp,
                        fingerprint,
                        idempotency_key,
                        self._json(payload),
                    ),
                )
        except Exception as error:
            if not _is_unique_violation(error):
                raise
            replay = self._get_event_replay(owner_id, scope, idempotency_key)
            if replay is None or replay[1] != fingerprint:
                raise PersistenceConflict("event replay conflict") from error
            return replay[2], replay[3], False
        return payload, sequence, True

    def _get_event_replay(
        self, owner_id: str, scope: ApplicationScope, idempotency_key: str
    ) -> tuple[str, str | None, dict[str, Any], int] | None:
        with self.database.connection() as connection:
            row = connection.execute(
                f"SELECT record_id,fingerprint,payload,event_sequence FROM {self.family} "
                "WHERE scope_id=%s AND owner_id=%s AND application_id=%s "
                "AND workspace_id IS NOT DISTINCT FROM %s AND idempotency_key=%s",
                (
                    self.scope_id(owner_id, scope),
                    owner_id,
                    scope.application_id,
                    scope.workspace_id,
                    idempotency_key,
                ),
            ).fetchone()
        if row is None:
            return None
        if row[3] is None:
            raise PersistenceConflict("event replay record has no sequence")
        return row[0], row[1], row[2], row[3]

    def replace(
        self,
        *,
        owner_id: str,
        scope: ApplicationScope,
        record_id: str,
        expected_revision: int,
        payload: dict[str, Any],
        status: str | None = None,
        expires_at: datetime | None = None,
    ) -> int:
        query = f"UPDATE {self.family} SET payload=%s::jsonb, status=%s, expires_at=%s, revision=revision+1 WHERE scope_id=%s AND record_id=%s AND owner_id=%s AND application_id=%s AND workspace_id IS NOT DISTINCT FROM %s AND revision=%s RETURNING revision"
        with self.database.connection() as connection:
            row = connection.execute(
                query,
                (
                    self._json(payload),
                    status,
                    _datetime(expires_at),
                    self.scope_id(owner_id, scope),
                    record_id,
                    owner_id,
                    scope.application_id,
                    scope.workspace_id,
                    expected_revision,
                ),
            ).fetchone()
        if row is None:
            raise PersistenceConflict("record revision or scope changed")
        return row[0]

    def indexed(
        self,
        *,
        owner_id: str,
        scope: ApplicationScope,
        status: str | None = None,
        before: datetime | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        if not 1 <= limit <= 1000:
            raise ValueError("persistence_limit_invalid")
        clauses = [
            "scope_id = %s",
            "owner_id = %s",
            "application_id = %s",
            "workspace_id IS NOT DISTINCT FROM %s",
        ]
        params: list[Any] = [
            self.scope_id(owner_id, scope),
            owner_id,
            scope.application_id,
            scope.workspace_id,
        ]
        if status is not None:
            clauses.append("status = %s")
            params.append(status)
        if before is not None:
            clauses.append("expires_at < %s")
            params.append(_datetime(before))
        params.append(limit)
        query = (
            f"SELECT payload FROM {self.family} WHERE {' AND '.join(clauses)} "
            "ORDER BY created_at, record_id LIMIT %s"
        )
        with self.database.connection() as connection:
            rows = connection.execute(query, params).fetchall()
        return [row[0] for row in rows]


class PostgresFamilyTransaction:
    """A repository-scoped transaction for preserving same-store write groups."""

    def __init__(self, database: PostgresDatabase, *, owner_id: str, scope: ApplicationScope):
        self.database = database
        self.owner_id = owner_id
        self.scope = scope
        self.scope_id = PostgresPayloadRepository.scope_id(owner_id, scope)

    @contextmanager
    def transaction(self) -> Iterator[Any]:
        with self.database.transaction() as connection:
            _ensure_namespace(connection, self.owner_id, self.scope)
            yield connection


def _ensure_namespace(connection: Any, owner_id: str, scope: ApplicationScope) -> str:
    scope_id = PostgresPayloadRepository.scope_id(owner_id, scope)
    connection.execute(
        "INSERT INTO scope_namespaces(scope_id, owner_id, application_id, workspace_id) "
        "VALUES (%s,%s,%s,%s) ON CONFLICT (scope_id) DO NOTHING",
        (scope_id, owner_id, scope.application_id, scope.workspace_id),
    )
    row = connection.execute(
        "SELECT owner_id, application_id, workspace_id FROM scope_namespaces WHERE scope_id=%s",
        (scope_id,),
    ).fetchone()
    if row != (owner_id, scope.application_id, scope.workspace_id):
        raise PersistenceConflict("scope namespace collision")
    return scope_id


def _datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, date) and not isinstance(value, datetime):
        return datetime.combine(value, datetime.min.time(), UTC)
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("timestamp_invalid")
    return value.astimezone(UTC)


def _is_unique_violation(error: Exception) -> bool:
    return error.__class__.__name__ == "UniqueViolation"

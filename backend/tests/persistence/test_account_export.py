from __future__ import annotations

from contextlib import contextmanager
from datetime import UTC, date, datetime
from uuid import uuid4

import pytest

from personal_ai.auth.account_data import AccountDataUnavailable, ExportTooLarge
from personal_ai.auth.scope import ApplicationScope, application_scope_context
from personal_ai.context.builder import ContextBuildManifest
from personal_ai.context.traces import ContextTraceManifest
from personal_ai.entities import Conversation
from personal_ai.persistence.dynamodb import (
    _catalog_item,
    _conversation_payload,
    _metadata_item,
    _namespace,
    _timestamp,
)
from personal_ai.persistence.postgres.auth import PostgresAccountLifecycleRepository


class _Result:
    def __init__(self, *, row=None, rows=()):
        self.row = row
        self.rows = list(rows)

    def fetchone(self):
        return self.row

    def fetchall(self):
        return self.rows


class _Connection:
    def execute(self, query, params=None):
        if "txid_current_snapshot" in query:
            return _Result(row=("snapshot-1",))
        if "FROM global_profiles" in query:
            return _Result(
                rows=[
                    (
                        "owner-global-profile-v1",
                        {
                            "schema_version": "global-profile-v1",
                            "owner_id": "owner",
                            "revision": 2,
                            "fields": [
                                {
                                    "field": "preferred_units",
                                    "value": "metric",
                                    "shared_with_applications": ["travel"],
                                    "set_by": "user",
                                    "set_at": datetime(2026, 10, 5, tzinfo=UTC),
                                }
                            ],
                            "updated_at": datetime(2026, 10, 5, tzinfo=UTC),
                        },
                        2,
                    )
                ]
            )
        if "FROM usage_budgets" in query:
            return _Result(
                rows=[
                    (
                        "usage:2026-10-05",
                        "owner",
                        "personal_ai",
                        None,
                        1,
                        "active",
                        3,
                        datetime(2026, 10, 5, tzinfo=UTC),
                        datetime(2027, 1, 4, tzinfo=UTC),
                        date(2026, 10, 5),
                        7,
                        321,
                    )
                ]
            )
        return _Result()


class _Database:
    def __init__(self, connection=None):
        self.connection_fixture = connection or _Connection()

    @contextmanager
    def connection(self, *, snapshot=False):
        assert snapshot
        yield self.connection_fixture


class _RuntimeTable:
    def query(self, **_kwargs):
        return []


class _TraceRuntimeTable(_RuntimeTable):
    def __init__(self, owner, scope, conversation, trace):
        self.scope = scope
        partition = f"{_namespace(scope, owner)}#CONV#{conversation.id}"
        self.metadata = _metadata_item(
            conversation, _conversation_payload(conversation), revision=1
        )
        self.catalog = _catalog_item(conversation, revision=1)
        self.trace = {
            "PK": partition,
            "SK": f"CTX#{_timestamp(trace.recorded_at)}#{trace.assistant_message_id}",
            "kind": "context-trace",
            "owner_id": owner,
            "application_id": scope.application_id,
            "workspace_id_present": scope.workspace_id is not None,
            "workspace_id": scope.workspace_id or "",
            "conversation_id": str(conversation.id),
            "user_message_id": str(trace.user_message_id),
            "assistant_message_id": str(trace.assistant_message_id),
            "request_id": trace.request_id,
            "recorded_at": _timestamp(trace.recorded_at),
            "payload": trace.model_dump_json(),
        }

    def get(self, key, **_kwargs):
        return self.metadata if key["SK"] == "META" else None

    def query(self, *, sort_prefix, partition, **_kwargs):
        if sort_prefix == "CONV#":
            return [self.catalog]
        if sort_prefix == "CTX#":
            return [self.trace]
        return []


def test_account_export_includes_typed_daily_usage_budget_columns():
    repository = PostgresAccountLifecycleRepository(_Database(), _RuntimeTable())

    with application_scope_context(
        ApplicationScope(application_id="personal_ai", workspace_id=None)
    ):
        result = repository.export_owner("owner", max_records=100, max_bytes=1_000_000)

    record = result["collections"]["usage_budgets"][0]
    assert record["document_id"] == "usage:2026-10-05"
    assert record["data"]["budget_day"] == "2026-10-05"
    assert record["data"]["provider_calls"] == 7
    assert record["data"]["input_tokens"] == 321
    assert record["data"]["expires_at"] == "2027-01-04T00:00:00+00:00"


def test_account_export_includes_owner_wide_global_profile_and_user_provenance():
    repository = PostgresAccountLifecycleRepository(_Database(), _RuntimeTable())

    with application_scope_context(
        ApplicationScope(application_id="personal_ai", workspace_id=None)
    ):
        result = repository.export_owner("owner", max_records=100, max_bytes=1_000_000)

    record = result["collections"]["global_profiles"][0]
    assert record["document_id"] == "owner-global-profile-v1"
    assert record["data"]["fields"][0]["field"] == "preferred_units"
    assert record["data"]["fields"][0]["set_by"] == "user"
    assert record["data"]["fields"][0]["shared_with_applications"] == ["travel"]


def test_account_export_includes_context_traces_and_tracks_them_in_snapshot_coverage():
    owner = "owner"
    scope = ApplicationScope(application_id="personal_ai", workspace_id=None)
    now = datetime(2026, 10, 7, tzinfo=UTC)
    conversation = Conversation(
        id=uuid4(), owner_id=owner, title="Export fixture", created_at=now, updated_at=now
    )
    context = ContextBuildManifest(
        counter_kind="estimated",
        counter_version="fixture-v1",
        global_input_tokens=400,
        actual_input_tokens=50,
        effective_sensitivity="personal",
    )
    trace = ContextTraceManifest.from_build(
        context,
        request_id="export-trace-request",
        conversation_id=conversation.id,
        user_message_id=uuid4(),
        assistant_message_id=uuid4(),
        scope=scope,
        recorded_at=now,
    )
    table = _TraceRuntimeTable(owner, scope, conversation, trace)
    repository = PostgresAccountLifecycleRepository(_Database(), table)

    with application_scope_context(scope):
        result = repository.export_owner(owner, max_records=100, max_bytes=1_000_000)

    record = result["collections"]["context_traces"][0]
    assert record["document_id"] == str(trace.assistant_message_id)
    assert record["data"]["request_id"] == "export-trace-request"
    assert (
        f"context_trace:{trace.assistant_message_id}"
        in result["snapshot_coverage"]["dynamodb"]["revisions"]
    )


class _LifecycleConnection(_Connection):
    def execute(self, query, params=None):
        if "FROM memories " in query:
            return _Result(rows=[("source-memory", {"content": "source"}, ())])
        if "FROM derived_memories " in query:
            return _Result(rows=[("derived-memory", {"content": "summary"}, ())])
        if "FROM derived_memory_sources ds" in query:
            return _Result(
                rows=[
                    (
                        "derived-memory",
                        "source-memory",
                        "owner",
                        "personal_ai",
                        None,
                        datetime(2026, 10, 7, tzinfo=UTC),
                    )
                ]
            )
        if "FROM federation_grants" in query or "FROM federation_grant_revisions" in query:
            family = (
                "federation_grant_revisions"
                if "federation_grant_revisions" in query
                else "federation_grants"
            )
            return _Result(rows=[(family + "-id", 1, {"family": family})])
        if "FROM mutation_proposals" in query or "FROM mutation_proposal_revisions" in query:
            family = (
                "mutation_proposal_revisions"
                if "mutation_proposal_revisions" in query
                else "mutation_proposals"
            )
            return _Result(rows=[(family + "-id", 2, {"family": family})])
        if "FROM artifact_metadata" in query:
            return _Result(
                rows=[
                    (
                        "artifact-1",
                        {
                            "artifact_id": "artifact-1",
                            "status": "ready",
                            "body_ref": "private:gcs/object",
                        },
                        3,
                    )
                ]
            )
        if "FROM provider_invocations i" in query:
            return _Result(rows=[("invocation-1", {"kind": "provider_invocations"})])
        if "FROM provider_attempts a" in query:
            return _Result(rows=[("attempt-1", {"kind": "provider_attempts"})])
        if "FROM provider_quota_reservations r" in query:
            return _Result(rows=[("attempt-1:bucket-1", {"kind": "provider_quota_reservations"})])
        if "FROM provider_usage_daily_aggregates a" in query:
            return _Result(rows=[("usage-day-1", {"kind": "provider_usage_daily_aggregates"})])
        if "FROM routing_decisions r" in query:
            return _Result(rows=[("route-1", {"kind": "routing_decisions"})])
        if "FROM routing_decision_events r" in query:
            return _Result(rows=[("route-event-1", {"kind": "routing_decision_events"})])
        if "FROM routing_decisions_legacy r" in query:
            return _Result(rows=[("route-legacy-1", {"kind": "routing_decisions_legacy"})])
        return super().execute(query, params)


def test_canonical_export_reads_nested_owner_families_from_the_postgres_implementation():
    repository = PostgresAccountLifecycleRepository(
        _Database(_LifecycleConnection()), _RuntimeTable()
    )

    with application_scope_context(ApplicationScope(application_id="personal_ai")):
        result = repository.export_owner("owner", max_records=100, max_bytes=1_000_000)

    collections = result["collections"]
    for family in (
        "derived_memories",
        "derived_memory_sources",
        "federation_grants",
        "federation_grant_revisions",
        "mutation_proposals",
        "mutation_proposal_revisions",
        "routing_decisions",
        "routing_decision_events",
        "routing_decisions_legacy",
        "artifact_metadata",
        "provider_invocations",
        "provider_attempts",
        "provider_quota_reservations",
        "provider_usage_daily_aggregates",
        "usage_budgets",
    ):
        assert collections[family]
    assert collections["derived_memory_sources"][0]["data"]["derived_memory_id"] == "derived-memory"
    artifact = collections["artifact_metadata"][0]["data"]
    assert artifact["body_ref"] == "private:gcs/object"
    assert "body_bytes" not in artifact


def test_canonical_export_rejects_bounded_truncation_and_scope_mismatch(monkeypatch):
    from personal_ai.auth import account_data

    repository = PostgresAccountLifecycleRepository(_Database(), _RuntimeTable())
    with (
        application_scope_context(ApplicationScope(application_id="personal_ai")),
        pytest.raises(ExportTooLarge),
    ):
        repository.export_owner("owner", max_records=1, max_bytes=1_000_000)

    owner = "owner"
    scope = ApplicationScope(application_id="personal_ai")
    now = datetime(2026, 10, 7, tzinfo=UTC)
    conversation = Conversation(
        id=uuid4(), owner_id=owner, title="Export fixture", created_at=now, updated_at=now
    )
    context = ContextBuildManifest(
        counter_kind="estimated",
        counter_version="fixture-v1",
        global_input_tokens=400,
        actual_input_tokens=50,
        effective_sensitivity="personal",
    )
    trace = ContextTraceManifest.from_build(
        context,
        request_id="bounded-export",
        conversation_id=conversation.id,
        user_message_id=uuid4(),
        assistant_message_id=uuid4(),
        scope=scope,
        recorded_at=now,
    )
    table = _TraceRuntimeTable(owner, scope, conversation, trace)

    table.catalog = {**table.catalog, "owner_id": "another-owner"}
    repository = PostgresAccountLifecycleRepository(_Database(), table)
    with (
        application_scope_context(scope),
        pytest.raises(AccountDataUnavailable, match="conversation directory scope mismatch"),
    ):
        repository.export_owner(owner, max_records=100, max_bytes=1_000_000)

    table.catalog = _catalog_item(conversation, revision=1)
    repository = PostgresAccountLifecycleRepository(_Database(), table)
    table.catalog = {**table.catalog, "revision": 2}
    with (
        application_scope_context(scope),
        pytest.raises(AccountDataUnavailable, match="conversation directory revision mismatch"),
    ):
        repository.export_owner(owner, max_records=100, max_bytes=1_000_000)

    monkeypatch.setattr(account_data, "MAX_EXPORT_SCAN_RECORDS", 1)
    table.catalog = _catalog_item(conversation, revision=1)
    table.query = lambda *, sort_prefix, partition, **kwargs: (
        [table.catalog, table.catalog] if sort_prefix == "CONV#" else []
    )
    repository = PostgresAccountLifecycleRepository(_Database(), table)
    with application_scope_context(scope), pytest.raises(ExportTooLarge):
        repository.export_owner(owner, max_records=100, max_bytes=1_000_000)

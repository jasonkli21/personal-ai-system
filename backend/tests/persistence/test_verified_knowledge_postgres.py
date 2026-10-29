"""Opt-in native schema-3 migration, transaction, CAS and erasure contracts."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from importlib.resources import files
from threading import Barrier

import pytest

from personal_ai.auth.scope import RequestScope
from personal_ai.evaluation.knowledge_runtime import (
    NOW,
    HermeticKnowledgeAuthority,
    messages_stub,
    request,
)
from personal_ai.evaluation.memory_knowledge import make_proposal, memory_query
from personal_ai.memory.knowledge_service import KnowledgeService
from personal_ai.memory.lifecycle import MemoryLifecycleEvent
from personal_ai.memory.lifecycle.repositories import event_idempotency_id
from personal_ai.persistence.postgres import PostgresDatabase, PostgresPayloadRepository
from personal_ai.persistence.postgres.lifecycle import PostgresMemoryLifecycleRepository
from personal_ai.persistence.postgres.memory import PostgresMemoryRepository
from personal_ai.settings import Settings
from personal_ai.storage.errors import ResourceNotFoundError

pytestmark = pytest.mark.persistence_integration


@pytest.fixture
def native(isolated_postgres_dsn):
    database = PostgresDatabase(isolated_postgres_dsn, environment="test")
    database.migrate()
    scope = RequestScope(
        owner_id="native-synthetic",
        acting_user_id="native-actor",
        workspace_id="repo-alpha",
        request_id="task-a",
    )
    settings = Settings(
        _env_file=None,
        ai_provider="gemini",
        ai_model="synthetic",
        memory_enabled=True,
        memory_knowledge_admission_enabled=True,
        memory_knowledge_selection_enabled=True,
    )
    messages = messages_stub()
    repo = PostgresMemoryRepository(database, object())
    lifecycle = PostgresMemoryLifecycleRepository(repo, messages, None, clock=lambda: NOW)
    authority = HermeticKnowledgeAuthority(scope)
    service = KnowledgeService(settings, repo, lifecycle, authority, clock=lambda: NOW)
    try:
        yield database, scope, repo, lifecycle, authority, service
    finally:
        database.close()


def admit(native, *, run_id="task-a"):
    _, scope, repo, _, authority, service = native
    p = make_proposal("procedure", "make backend-lint")
    ref = authority.complete_task_a(scope, "repo-alpha", p, run_id=run_id, edges=3)
    result = service.admit(scope, "repo-alpha", ref, p)
    assert result.status == "created", result
    return ref, repo.get_knowledge(owner_id=scope.owner_id, memory_id=result.record_id)


def test_forward_from_027_reapply_and_real_pgvector(isolated_postgres_dsn, monkeypatch):
    from personal_ai.persistence.postgres import migrations

    real = files("personal_ai.persistence")

    class Before028:
        def joinpath(self, name):
            if name == "migrations":

                class Directory:
                    def iterdir(self):
                        return [
                            f
                            for f in real.joinpath(name).iterdir()
                            if not f.name.startswith("028_")
                        ]

                return Directory()
            return real.joinpath(name)

    database = PostgresDatabase(isolated_postgres_dsn, environment="test")
    try:
        with monkeypatch.context() as patch:
            patch.setattr(migrations, "files", lambda _: Before028())
            assert max(database.migrate()) == 27
        assert database.migrate() == (28,)
        assert database.migrate() == ()
        with database.connection() as connection:
            assert (
                connection.execute("SELECT '[1,0]'::vector <=> '[1,0]'::vector").fetchone()[0] == 0
            )
            assert connection.execute("SELECT count(*) FROM memory_knowledge").fetchone()[0] == 0
    finally:
        database.close()


def test_native_two_sessions_new_receipt_and_default_off_rollback(native):
    _, scope, repo, lifecycle, authority, service = native
    with request(scope):
        ref, record = admit(native)
    scope = scope.model_copy(update={"request_id": "task-b"})
    service = KnowledgeService(service.settings, repo, lifecycle, authority, clock=lambda: NOW)
    with request(scope):
        result = service.select(memory_query(scope, authority))
        assert [row.memory.id for row in result.selected] == [record.id]
        dep = result.permission_dependencies[0][1][0]
        outcome = service.consume(
            dep,
            lambda r: authority.execute(
                scope,
                "repo-alpha",
                "task-b",
                r.proposal.command,
                expected_revision=authority.project(scope, "repo-alpha").revision,
            ),
        )
        assert outcome["receipt_id"] != ref and outcome["outcome"] == "success"
        service.settings.memory_knowledge_selection_enabled = False
        assert not service.select(memory_query(scope, authority)).selected
        assert repo.get_knowledge(owner_id=scope.owner_id, memory_id=record.id) == record


def test_native_concurrent_admission_and_source_epoch_cas(native):
    database, scope, repo, _, _authority, _ = native
    with request(scope):
        _, record = admit(native)
        # Remove only the new row before direct trusted-adapter concurrency.
        with database.connection() as connection:
            connection.execute("DELETE FROM memory_knowledge WHERE record_id=%s", (str(record.id),))
    barrier = Barrier(2)

    def create(_):
        with request(scope):
            barrier.wait()
            return repo.create_knowledge(record)[1]

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(create, range(2))) == [False, True]
    edge = record.evidence.edges[-1]
    barrier = Barrier(2)

    def revoke(_):
        with request(scope):
            barrier.wait()
            return repo.revoke_knowledge_source(
                scope=scope,
                resolver_id=edge.resolver_id,
                source_id=edge.source_id,
                expected_epoch=0,
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(revoke, range(2))) == [False, True]
    with request(scope):
        assert not repo.knowledge_sources_current(record)
        with pytest.raises(ValueError, match="epoch"):
            repo.create_knowledge(record)


def test_native_forget_cas_retry_and_complete_reverse_erasure(native):
    database, scope, repo, lifecycle, _, _ = native
    with request(scope):
        _, record = admit(native)
        key = "native-knowledge-forget"
        event = MemoryLifecycleEvent(
            id=event_idempotency_id(key),
            owner_id=scope.owner_id,
            memory_id=record.id,
            event_type="forgotten",
            reason_code="developer_verification",
            policy_version="verified-knowledge-v1",
            actor="developer_test",
            occurred_at=NOW,
            idempotency_key=key,
            expected_state_version=0,
        )
        assert lifecycle.apply_event(event).status == "applied"
        assert lifecycle.apply_event(event).status == "replayed"
        with pytest.raises(ValueError, match="epoch"):
            repo.create_knowledge(record)
        assert lifecycle.get_state(owner_id=scope.owner_id, memory_id=record.id).validity_epoch == 1
        edge = record.evidence.edges[-1]
        assert repo.revoke_knowledge_source(
            scope=scope,
            resolver_id=edge.resolver_id,
            source_id=edge.source_id,
            expected_epoch=0,
            erase=True,
        )
        with pytest.raises(ResourceNotFoundError):
            repo.get_knowledge(owner_id=scope.owner_id, memory_id=record.id)
        with database.connection() as connection:
            scope_id = PostgresPayloadRepository.scope_id(scope.owner_id, scope)
            assert (
                connection.execute(
                    "SELECT count(*) FROM memory_knowledge_sources WHERE scope_id=%s", (scope_id,)
                ).fetchone()[0]
                == 0
            )
        with pytest.raises(ValueError, match="epoch"):
            repo.create_knowledge(record)


def test_native_partial_insert_rolls_back_all_edges(native, monkeypatch):
    database, scope, _repo, _, authority, service = native
    p = make_proposal("procedure", "make backend-lint")
    real_connection = database.connection

    @contextmanager
    def fail_edges(**kwargs):
        with real_connection(**kwargs) as connection:

            class Broken:
                def execute(self, sql, *args, **kw):
                    if sql.startswith("INSERT INTO memory_knowledge_sources"):
                        raise OSError("synthetic edge failure")
                    return connection.execute(sql, *args, **kw)

            yield Broken()

    with request(scope):
        ref = authority.complete_task_a(scope, "repo-alpha", p)
        with monkeypatch.context() as patch:
            patch.setattr(database, "connection", fail_edges)
            assert service.admit(scope, "repo-alpha", ref, p).status == "unknown_commit"
        with database.connection() as connection:
            for table in (
                "memory_knowledge",
                "memory_knowledge_sources",
                "memory_knowledge_source_fences",
            ):
                assert connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0] == 0
        assert service.admit(scope, "repo-alpha", ref, p).status == "created"


def test_native_lost_commit_acknowledgement_reconciles_original_key(native, monkeypatch):
    database, scope, repo, _, authority, service = native
    p = make_proposal("procedure", "make backend-lint")
    real_connection = database.connection
    exits = []

    @contextmanager
    def lose_first_ack(**kwargs):
        with real_connection(**kwargs) as connection:
            yield connection
        exits.append(True)
        if len(exits) == 1:
            raise OSError("synthetic lost acknowledgement after actual commit")

    with request(scope):
        ref = authority.complete_task_a(scope, "repo-alpha", p)
        with monkeypatch.context() as patch:
            patch.setattr(database, "connection", lose_first_ack)
            result = service.admit(scope, "repo-alpha", ref, p)
        assert result.status == "already_exists" and result.reason == "reconciled_original_key"
        assert (
            len(
                repo.list_knowledge(
                    scope=scope, filters=memory_query(scope, authority).knowledge, limit=20
                )
            )
            == 1
        )


def test_native_owner_deletion_fence_blocks_selection_and_admission(native):
    database, scope, _, _, authority, service = native
    with request(scope):
        _, record = admit(native)
        dep = service.dependency(record, scope)
        with database.connection() as connection:
            connection.execute(
                "INSERT INTO owner_lifecycle_fences(owner_id) VALUES (%s)", (scope.owner_id,)
            )
        assert not service.is_current(dep)
        assert not service.select(memory_query(scope, authority)).selected
        p = make_proposal("procedure", "make backend-lint")
        ref = authority.complete_task_a(scope, "repo-alpha", p, run_id="post-fence-run")
        assert service.admit(scope, "repo-alpha", ref, p).status == "unknown_commit"


def test_native_expiry_erases_payload_and_retry_stays_fenced(native):
    from datetime import timedelta

    _, scope, repo, _, _, service = native
    with request(scope):
        ref, record = admit(native)
        assert repo.erase_expired_knowledge(scope=scope, as_of=NOW + timedelta(days=2)) == 1
        with pytest.raises(ResourceNotFoundError):
            repo.get_knowledge(owner_id=scope.owner_id, memory_id=record.id)
        assert service.admit(scope, "repo-alpha", ref, record.proposal).status == "conflict"


def test_native_incomplete_edge_set_and_missing_projection_deny_reuse(native):
    database, scope, repo, lifecycle, _, service = native
    with request(scope):
        _, record = admit(native)
        dep = service.dependency(record, scope)
        scope_id = PostgresPayloadRepository.scope_id(scope.owner_id, scope)
        with database.connection() as connection:
            connection.execute(
                "DELETE FROM memory_knowledge_sources WHERE scope_id=%s AND record_id=%s AND source_ordinal=3",
                (scope_id, str(record.id)),
            )
        assert not service.is_current(dep)
        key = "missing-projection-forget"
        event = MemoryLifecycleEvent(
            id=event_idempotency_id(key),
            owner_id=scope.owner_id,
            memory_id=record.id,
            event_type="forgotten",
            reason_code="developer_verification",
            policy_version="verified-knowledge-v1",
            actor="developer_test",
            occurred_at=NOW,
            idempotency_key=key,
            expected_state_version=0,
        )
        assert lifecycle.apply_event(event).status == "applied"
        with database.connection() as connection:
            connection.execute(
                "DELETE FROM memory_lifecycle_states WHERE scope_id=%s AND record_id=%s",
                (scope_id, str(record.id)),
            )
        assert not service.is_current(dep)
        with pytest.raises(ValueError, match="lifecycle_missing"):
            repo.create_knowledge(record)

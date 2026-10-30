"""Opt-in native MEM-2 atomicity, reconciliation, process races and erasure."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from datetime import timedelta
from multiprocessing import get_context
from threading import Barrier
from uuid import uuid4

import pytest

from personal_ai.evaluation.control_runtime import ControlRuntime
from personal_ai.evaluation.knowledge_runtime import NOW, request
from personal_ai.evaluation.memory_control import candidate, mutation
from personal_ai.memory.control_contracts import ControlIntent, ReviewInput, SearchInput
from personal_ai.memory.control_service import MemoryControlService
from personal_ai.memory.knowledge_service import KnowledgeService
from personal_ai.persistence.postgres import PostgresDatabase
from personal_ai.persistence.postgres.control import PostgresControlRepository
from personal_ai.persistence.postgres.lifecycle import PostgresMemoryLifecycleRepository
from personal_ai.persistence.postgres.memory import PostgresMemoryRepository

pytestmark = pytest.mark.persistence_integration


@pytest.fixture
def native(isolated_postgres_dsn):
    rt = ControlRuntime()
    database = PostgresDatabase(isolated_postgres_dsn, environment="test")
    applied = database.migrate()
    assert applied[-1] == 31
    assert database.migrate() == ()
    rt.memories = PostgresMemoryRepository(database, object())
    rt.lifecycle = PostgresMemoryLifecycleRepository(rt.memories, object(), None)
    rt.knowledge = KnowledgeService(
        rt.settings, rt.memories, rt.lifecycle, rt.authority, clock=lambda: rt.now
    )
    rt.repository = PostgresControlRepository(rt.memories, rt.lifecycle)
    rt.service = MemoryControlService(
        rt.knowledge, rt.repository, rt.scope, "repo-alpha", clock=lambda: rt.now
    )
    try:
        yield database, rt
    finally:
        database.close()


def counts(database):
    with database.connection() as c:
        return tuple(
            c.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
            for t in (
                "memory_control_proposals",
                "memory_control_operations",
                "memory_lifecycle_events",
                "memory_lifecycle_states",
            )
        )


def test_native_propose_review_forget_replay_and_actor_isolation(native):
    database, rt = native
    with rt.user():
        record = rt.seed()
        dependency = rt.knowledge.dependency(record, rt.scope)
        p = rt.service.propose(candidate())
        assert p.status == "proposed_for_review"
        review = ReviewInput(**mutation().model_dump(), decision="reviewed")
        assert rt.service.mutate("reviewed", p.target_id, review).status == "reviewed"
        assert rt.service.mutate("reviewed", p.target_id, review).replayed
        body = mutation()
        assert rt.service.mutate("forget", record.id, body).status == "applied"
        assert rt.service.mutate("forget", record.id, body).replayed
        assert (
            rt.service.mutate("forget", record.id, mutation(2, body.operation_id)).status
            == "conflict"
        )
        assert not rt.knowledge.is_current(dependency)
        assert not rt.service.read(SearchInput()).items
        other = rt.scope.model_copy(update={"acting_user_id": "test-issuer|actor-b"})
        rt.authority.projects[
            (
                (other.owner_id, other.application_id, other.workspace_id, other.acting_user_id),
                "repo-alpha",
            )
        ] = record.project
        with rt.user(other, replace(rt.principal, subject="actor-b")):
            s = rt.for_scope(other)
            assert not s.proposals().proposals
            assert not s.read(SearchInput(), memory_id=record.id).items
            assert s.mutate("forget", record.id, body).status == "forbidden_or_not_found"
            assert s.mutate("reviewed", p.target_id, review).status == "forbidden_or_not_found"
    assert counts(database) == (1, 3, 1, 1)


@pytest.mark.parametrize("action", ["forget", "reviewed"])
def test_native_concurrent_sessions_one_cas_winner(native, action):
    database, rt = native
    with rt.user():
        record = rt.seed()
        proposal = rt.service.propose(candidate())
        target = record.id if action == "forget" else proposal.target_id
    barrier = Barrier(2)

    def worker(_):
        with rt.user():
            barrier.wait()
            return rt.service.mutate(action, target, mutation()).status

    with ThreadPoolExecutor(max_workers=2) as pool:
        result = list(pool.map(worker, range(2)))
    assert sorted(result) == sorted(["applied" if action == "forget" else "reviewed", "conflict"])
    assert counts(database)[1] == 3
    if action == "forget":
        assert counts(database)[2:] == (1, 1)


def _process_forget(dsn, scope, project, intent, barrier, queue):
    database = PostgresDatabase(dsn, environment="test")
    memories = PostgresMemoryRepository(database, object())
    lifecycle = PostgresMemoryLifecycleRepository(memories, object(), None)
    repo = PostgresControlRepository(memories, lifecycle)
    try:
        with request(scope):
            barrier.wait(timeout=20)
            queue.put(repo.execute(scope, project, intent, NOW).status)
    finally:
        database.close()


def test_native_two_process_transactions_no_split_receipt(native, isolated_postgres_dsn):
    database, rt = native
    with rt.user():
        record = rt.seed()
    ctx = get_context("spawn")
    barrier, queue = ctx.Barrier(2), ctx.Queue()
    processes = [
        ctx.Process(
            target=_process_forget,
            args=(
                isolated_postgres_dsn,
                rt.scope,
                record.project,
                ControlIntent(
                    operation_id=uuid4(),
                    action="forget",
                    target_id=record.id,
                    expected_version=0,
                    actor="verified_user",
                ),
                barrier,
                queue,
            ),
        )
        for _ in range(2)
    ]
    for process in processes:
        process.start()
    for process in processes:
        process.join(timeout=30)
        assert process.exitcode == 0
    assert sorted([queue.get(timeout=2), queue.get(timeout=2)]) == ["applied", "conflict"]
    assert counts(database) == (0, 2, 1, 1)


@pytest.mark.parametrize("action", ["forget", "reviewed", "propose"])
def test_native_receipt_failure_rolls_back_entire_effect(native, monkeypatch, action):
    database, rt = native
    with rt.user():
        record = rt.seed()
        proposal = rt.service.propose(candidate())
        before = counts(database)
        original = database.connection

        @contextmanager
        def fail_receipt(**kwargs):
            with original(**kwargs) as c:

                class Broken:
                    def execute(self, sql, *args, **kw):
                        if sql.startswith("INSERT INTO memory_control_operations"):
                            raise OSError("synthetic failure before commit")
                        return c.execute(sql, *args, **kw)

                yield Broken()

        with monkeypatch.context() as patch:
            patch.setattr(database, "connection", fail_receipt)
            result = (
                rt.service.propose(candidate())
                if action == "propose"
                else rt.service.mutate(
                    action, record.id if action == "forget" else proposal.target_id, mutation()
                )
            )
            assert result.status == "unknown_commit"
        assert counts(database) == before
        assert rt.service.proposals().proposals[0].status == "pending"
        assert (
            rt.lifecycle.get_state(owner_id=rt.scope.owner_id, memory_id=record.id).state_version
            == 0
        )


@pytest.mark.parametrize("reconciliation", [True, False])
def test_native_commit_then_lost_ack_reconciles_exact_operation(
    native, monkeypatch, reconciliation
):
    database, rt = native
    with rt.user():
        record = rt.seed()
        req = mutation()
        original = rt.repository.execute

        def lose_ack(*args):
            original(*args)
            if not reconciliation:

                def unavailable(*args):
                    raise OSError("synthetic unavailable status read")

                monkeypatch.setattr(rt.repository, "reconcile", unavailable)
            raise OSError("synthetic lost acknowledgement after actual commit")

        with monkeypatch.context() as patch:
            patch.setattr(rt.repository, "execute", lose_ack)
            result = rt.service.mutate("forget", record.id, req)
        assert result.status == ("applied" if reconciliation else "unknown_commit")
        assert counts(database) == (0, 1, 1, 1)
        # New repository/session can reconcile the original ID after reconnect.
        rt.repository = PostgresControlRepository(rt.memories, rt.lifecycle)
        rt.service = MemoryControlService(
            rt.knowledge, rt.repository, rt.scope, "repo-alpha", clock=lambda: rt.now
        )
        assert rt.service.mutate("forget", record.id, req).replayed
        key = (
            rt.scope.owner_id,
            rt.scope.application_id,
            rt.scope.workspace_id,
            rt.scope.acting_user_id,
        )
        rt.authority.projects[(key, "repo-alpha")] = record.project.model_copy(
            update={"revision": "rev-after-commit"}
        )
        assert rt.service.mutate("forget", record.id, req).replayed
        assert (
            rt.service.mutate("forget", record.id, mutation(9, req.operation_id)).status
            == "conflict"
        )
        assert counts(database) == (0, 1, 1, 1)


def test_native_source_revoked_after_check_still_allows_user_suppression(native, monkeypatch):
    database, rt = native
    with rt.user():
        record = rt.seed()
        original = rt.repository.execute

        def revoke(*args):
            edge = record.evidence.edges[0]
            rt.memories.revoke_knowledge_source(
                scope=rt.scope,
                resolver_id=edge.resolver_id,
                source_id=edge.source_id,
                expected_epoch=0,
            )
            return original(*args)

        monkeypatch.setattr(rt.repository, "execute", revoke)
        assert rt.service.mutate("forget", record.id, mutation()).status == "applied"
        assert counts(database) == (0, 1, 1, 1)


def test_native_idle_proposal_gc_erases_content_and_preserves_operation_key(native):
    database, rt = native
    with rt.user():
        operation_id = uuid4()
        proposal = rt.service.propose(candidate(), operation_id=operation_id)
        rt.now += timedelta(days=2)
        assert not rt.service.proposals().proposals
        with database.connection() as connection:
            assert connection.execute("SELECT count(*) FROM memory_control_proposals").fetchone()[0] == 1
        assert rt.repository.purge_expired_proposals(as_of=rt.now, limit=10) == 1
        assert counts(database)[0] == 0
        assert rt.service.propose(candidate(), operation_id=operation_id).status == "expired"
        assert counts(database)[1] == 1
        assert proposal.target_id is not None


def test_native_forget_survives_256_conflict_receipts(native):
    database, rt = native
    with rt.user():
        record = rt.seed()
        for _ in range(256):
            assert rt.service.mutate("forget", record.id, mutation(999)).status == "conflict"
        assert counts(database)[1] == 256
        operation = mutation()
        assert rt.service.mutate("forget", record.id, operation).status == "applied"
        assert rt.service.mutate("forget", record.id, operation).replayed
        assert counts(database) == (0, 257, 1, 1)


def test_native_expired_knowledge_can_be_forgotten_by_current_actor(native):
    database, rt = native
    with rt.user():
        record = rt.seed()
        rt.now += timedelta(days=31)
        principal = replace(rt.principal, authenticated_at=int(rt.now.timestamp()))
        with rt.user(principal=principal):
            assert rt.service.mutate("forget", record.id, mutation()).status == "applied"
            assert not rt.service.read(SearchInput(), memory_id=record.id).items
            assert counts(database)[2:] == (1, 1)


def test_native_ttl_quota_export_and_fenced_owner_erasure(native):
    database, rt = native
    with rt.user():
        first = rt.service.propose(candidate())
        for _ in range(31):
            assert rt.service.propose(candidate()).status == "proposed_for_review"
        assert rt.service.propose(candidate()).status == "limit_exceeded"
        rt.now += timedelta(days=2)
        assert not rt.service.proposals().proposals
        assert rt.service.propose(candidate()).status == "proposed_for_review"
        assert counts(database)[:2] == (1, 33)
        # Use the actual account export SQL path with an empty synthetic DDB directory.
        from personal_ai.persistence.postgres.auth import PostgresAccountLifecycleRepository

        class EmptyDirectory:
            def get(self, *args, **kw):
                return None

            def query(self, *args, **kw):
                return []

        account = PostgresAccountLifecycleRepository(database, EmptyDirectory())
        exported = account.export_owner(rt.scope.owner_id, max_records=1000, max_bytes=1000000)
        assert len(exported["collections"]["memory_control_proposals"]) == 1
        assert len(exported["collections"]["memory_control_operations"]) == 33
        audit = json_safe(exported["collections"]["memory_control_operations"])
        assert candidate().claim not in audit
        with pytest.raises(ValueError, match="fence_required"):
            rt.repository.erase_owner(rt.scope.owner_id)
        with database.connection() as c:
            c.execute(
                "INSERT INTO owner_lifecycle_fences(owner_id) VALUES (%s)", (rt.scope.owner_id,)
            )
        assert rt.service.propose(candidate()).status == "temporarily_unavailable"
        rt.repository.erase_owner(rt.scope.owner_id)
        assert counts(database)[:2] == (0, 0)
        assert first.target_id is not None


def json_safe(value):
    import json

    return json.dumps(value, default=str)


def test_native_resource_envelope(native):
    """Measurements only: SQL API calls (excluding pool/timeout instrumentation)."""
    import json
    from statistics import median
    from time import perf_counter

    database, rt = native
    original = database.connection
    calls = [0]

    @contextmanager
    def measured(**kwargs):
        with original(**kwargs) as connection:

            class Meter:
                def execute(self, *args, **kw):
                    calls[0] += 1
                    return connection.execute(*args, **kw)

            yield Meter()

    report = {"classification": "synthetic native local PG", "reads": []}
    with rt.user():
        seeded = 0
        for size in (0, 1, 32, 128):
            while seeded < size:
                rt.seed(f"resource-seed-{seeded}")
                seeded += 1
            samples, sql = [], []
            database.connection = measured
            try:
                for _ in range(5):
                    calls[0] = 0
                    start = perf_counter()
                    result = rt.service.read(SearchInput())
                    samples.append((perf_counter() - start) * 1000)
                    sql.append(calls[0])
            finally:
                database.connection = original
            report["reads"].append(
                {
                    "n": size,
                    "status": result.status,
                    "returned": len(result.items),
                    "sql_calls": sql,
                    "p50_ms": median(samples),
                    "max_ms": max(samples),
                }
            )
        assert rt.service.propose(candidate()).status == "proposed_for_review"
        with database.connection() as connection:
            report["postgres_version"] = connection.execute("SELECT version()").fetchone()[0]
            report["pgvector_version"] = connection.execute(
                "SELECT extversion FROM pg_extension WHERE extname='vector'"
            ).fetchone()[0]
            for table in ("memory_control_proposals", "memory_control_operations"):
                report[table] = connection.execute(
                    f"SELECT count(*),sum(octet_length(payload::text)),sum(pg_column_size(payload)) FROM {table}"
                ).fetchone()
    print("MEM2_RESOURCE=" + json.dumps(report, default=str))

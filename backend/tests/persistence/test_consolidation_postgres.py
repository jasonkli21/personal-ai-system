"""Opt-in real SQL/process evidence for the isolated synthetic adapter."""

# ruff: noqa: F811 - imported pytest fixture

import multiprocessing
import os
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta

import pytest
from psycopg.types.json import Jsonb

from personal_ai.memory.consolidation.contracts import (
    BACKFILL_GENERATION,
    GENERATION,
    V2_SOURCE_V1_POLICY_GENERATION,
    ConsolidationDenied,
    ConsolidationScope,
)
from personal_ai.memory.consolidation.sources import CORPUS_SHA256
from personal_ai.persistence.postgres import PostgresDatabase
from personal_ai.persistence.postgres.consolidation import (
    PostgresFixtureSource,
    PostgresProposalRepository,
)
from personal_ai.persistence.postgres.owner_lifecycle import lock_owner
from tests.persistence.test_workflow_postgres import database  # noqa: F401

pytestmark = pytest.mark.persistence_integration
NOW = datetime(2026, 11, 3, 13, tzinfo=UTC)


def pair(database, session="procedure", clock=lambda: NOW, *, corpus="v1", generation=None):
    source = PostgresFixtureSource(database, clock=clock, corpus=corpus)
    if generation is None:
        generation = GENERATION if corpus == "v1" else V2_SOURCE_V1_POLICY_GENERATION
    repo = PostgresProposalRepository(source, generation=generation)
    scope = next(s for s in source.scopes if s.session == session)
    return source, repo, scope


def submit(source, repo, scope):
    source.publish(scope, len(source._streams[scope.key]))
    lease = repo.claim(scope, "worker")
    page = source.page(scope, lease.cursor, generation=repo.generation)
    return repo.commit(lease, page)


def _claim_process(dsn, session, barrier, results, clock_skew_minutes=0, commit_page=False):
    db = PostgresDatabase(dsn, environment="test", min_size=0, max_size=1)
    try:
        source, repo, scope = pair(
            db,
            session,
            clock=lambda: NOW + timedelta(minutes=clock_skew_minutes),
        )
        if barrier is not None:
            barrier.wait(timeout=10)
        try:
            lease = repo.claim(scope, "process-worker")
            if commit_page:
                page = source.page(scope, lease.cursor, generation=repo.generation)
                repo.commit(lease, page)
                results.put("committed")
            else:
                results.put("claimed")
        except ConsolidationDenied:
            results.put("denied")
    finally:
        db.close()


def _crash_process(dsn, fault):
    db = PostgresDatabase(dsn, environment="test", min_size=0, max_size=1)
    source, repo, scope = pair(db)
    lease = repo.claim(scope, "crashing-worker")
    page = source.page(scope, 0)
    if fault == "before_commit":
        original = db.transaction

        @contextmanager
        def crash_with_uncommitted_writes(*args, **kwargs):
            with original(*args, **kwargs) as connection:
                yield connection
                # The proposal/checkpoint and source heads have been written,
                # but the DB transaction context has not committed. Kill the
                # process without running Python cleanup or rollback handlers.
                os._exit(71)

        db.transaction = crash_with_uncommitted_writes
        repo.commit(lease, page)
    else:
        repo.commit(lease, page)
        os._exit(72)  # Commit is durable, but the parent has received no ACK.


@pytest.mark.parametrize("fault", ["before_commit", "after_commit"])
def test_native_abrupt_process_death_recovers_original_transaction(database, fault):
    source, _, scope = pair(database)
    source.publish(scope, 1)
    original_key = source.page(scope, 0).original_key
    process = multiprocessing.get_context("spawn").Process(
        target=_crash_process, args=(database._dsn, fault)
    )
    process.start()
    process.join(timeout=15)
    if process.is_alive():
        process.terminate()
        process.join(timeout=2)
    assert process.exitcode == (71 if fault == "before_commit" else 72)
    fresh_source, recovered, _ = pair(database, clock=lambda: NOW + timedelta(seconds=5))
    receipt = recovered.observe(scope, original_key)
    assert (receipt is not None) == (fault == "after_commit")
    if receipt is None:
        import time

        time.sleep(5.1)
        lease = recovered.claim(scope, "recovery")
        receipt = recovered.commit(lease, fresh_source.page(scope, 0))
    assert receipt.cursor == 1
    assert len(recovered.pending(scope)) == 1


def test_native_reconnect_and_original_receipt_are_durable(database):
    source, repo, scope = pair(database)
    receipt = submit(source, repo, scope)
    second_db = PostgresDatabase(database._dsn, environment="test")
    try:
        other_source, other, other_scope = pair(second_db)
        assert other.observe(other_scope, receipt.original_key) == receipt
        assert other.pending(other_scope) == repo.pending(scope)
        assert other.claim(other_scope, "next").cursor == 1
        assert other_source.diagnostics()["corpus_digest"] == CORPUS_SHA256
    finally:
        second_db.close()


@pytest.mark.parametrize("fault", ["before_commit", "after_commit"])
def test_native_crash_boundaries_and_lost_ack(database, fault):
    source, repo, scope = pair(database)
    source.publish(scope, 1)
    lease = repo.claim(scope, "worker")
    page = source.page(scope, 0)
    with pytest.raises(ConsolidationDenied):
        repo.commit(lease, page, fault=fault)
    _, recovered, _ = pair(database)
    receipt = recovered.observe(scope, page.original_key)
    assert (receipt is None) == (fault == "before_commit")
    assert recovered.commit(lease, page).cursor == 1
    changed = page.model_copy(
        update={"records": (page.records[0].model_copy(update={"revision": 2}),)}
    )
    with pytest.raises(ConsolidationDenied):
        recovered.commit(lease, changed)


def test_native_dual_process_claims_are_serialized(database):
    source, _, scope = pair(database)
    source.publish(scope, 1)
    context = multiprocessing.get_context("spawn")
    barrier, results = context.Barrier(2), context.Queue()
    workers = [
        context.Process(
            target=_claim_process, args=(database._dsn, scope.session, barrier, results)
        )
        for _ in range(2)
    ]
    for worker in workers:
        worker.start()
    try:
        assert sorted(results.get(timeout=15) for _ in workers) == ["claimed", "denied"]
    finally:
        for worker in workers:
            worker.join(timeout=10)
            if worker.is_alive():
                worker.terminate()
                worker.join(timeout=2)
            assert worker.exitcode == 0


def test_native_lease_takeover_fences_old_process_state(database):
    import time

    context = multiprocessing.get_context("spawn")
    results = context.Queue()
    source, first, scope = pair(database, clock=lambda: NOW)
    source.publish(scope, 1)
    lease = first.claim(scope, "first")
    page = source.page(scope, 0)
    fast = context.Process(
        target=_claim_process,
        args=(database._dsn, scope.session, None, results, 10, False),
    )
    fast.start()
    fast.join(timeout=15)
    assert fast.exitcode == 0 and results.get(timeout=2) == "denied"
    time.sleep(5.1)
    slow = context.Process(
        target=_claim_process,
        args=(database._dsn, scope.session, None, results, -10, True),
    )
    slow.start()
    slow.join(timeout=15)
    assert slow.exitcode == 0 and results.get(timeout=2) == "committed"
    with pytest.raises(ConsolidationDenied):
        first.commit(lease, page)
    _, recovered, _ = pair(database)
    assert len(recovered.pending(scope)) == 1


def test_native_withdrawal_regrant_and_stale_checkpoint_restore(database):
    source, repo, scope = pair(database, "reserved-procedure")
    source.publish(scope, 5)
    lease = repo.claim(scope, "worker")
    page = source.page(scope, 0)
    with database.transaction() as connection:
        stale = connection.execute(
            "SELECT payload FROM offline_consolidation_checkpoints"
        ).fetchone()[0]
    repo.commit(lease, page)
    other_source, other, _ = pair(database, scope.session)
    cached = repo.pending(scope)[0]
    other_source.withdraw(scope, cached.edges[0].source_id)
    assert not repo.pending(scope)
    other_source.regrant(scope, cached.edges[0].source_id)
    assert not repo.validate_cached(scope, cached)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE offline_consolidation_checkpoints SET payload=%s", (Jsonb(stale),)
        )
    with pytest.raises(ConsolidationDenied):
        other.claim(scope, "stale-restore")


def test_native_source_transaction_rolls_back_and_expiry_purges_content(database):
    now = [NOW]
    source, repo, scope = pair(database, clock=lambda: now[0])
    receipt = submit(source, repo, scope)
    cached = repo.pending(scope)[0]
    with pytest.raises(RuntimeError), source.guard():
        source.withdraw(scope, cached.edges[0].source_id)
        raise RuntimeError("synthetic_precommit_crash")
    assert repo.pending(scope)
    now[0] += timedelta(days=1)
    repo.maintain()
    assert not repo.pending(scope)
    assert repo.observe(scope, receipt.original_key) == receipt
    with database.transaction() as connection:
        payload = connection.execute(
            "SELECT payload FROM offline_consolidation_checkpoints"
        ).fetchone()[0]
    assert payload["proposals"] == [] and payload["receipts"]


def test_native_project_forget_retains_replay_fences(database):
    source, repo, scope = pair(database)
    submit(source, repo, scope)
    repo.forget(owner=scope.owner, project=scope.project)
    _, restored, _ = pair(database)
    assert not restored.pending(scope)
    assert restored.diagnostics()["receipts"] == 1
    assert restored.diagnostics()["retained_proposals"] == 0
    with pytest.raises(ConsolidationDenied):
        restored.claim(scope, "forgotten")


def test_native_canonical_owner_fence_blocks_the_adapter(database):
    source, repo, scope = pair(database)
    source.publish(scope, 1)
    with database.transaction() as connection:
        lock_owner(connection, scope.owner)
        connection.execute(
            "INSERT INTO owner_lifecycle_fences(owner_id) VALUES (%s)", (scope.owner,)
        )
    with pytest.raises(Exception, match="owner_deletion_fenced"):
        repo.claim(scope, "fenced")


def test_native_sql_entrypoints_reject_hostile_scopes_before_key_access(database):
    source, repo, scope = pair(database, corpus="v2")
    source.publish(scope, 1)
    page = source.page(scope, 0, generation=repo.generation)
    foreign = ConsolidationScope.model_validate(
        {**scope.model_dump(), "owner": "unregistered-owner"}
    )
    invalid_scopes = (
        object(),
        {},
        scope.model_copy(update={"unmodeled": "unsafe"}),
        scope.model_copy(update={"owner": "../unsafe"}),
        foreign,
    )
    for invalid in invalid_scopes:
        operations = (
            lambda invalid=invalid: repo.claim(invalid, "worker"),
            lambda invalid=invalid: repo.observe(invalid, "0" * 64),
            lambda invalid=invalid: repo.pending(invalid),
            lambda invalid=invalid: repo.validate_cached(invalid, object()),
            lambda invalid=invalid: repo.commit(None, page.model_copy(update={"scope": invalid})),
        )
        for operation in operations:
            with pytest.raises(ConsolidationDenied):
                operation()


def test_native_owner_inventory_and_purge_are_fenced_and_project_independent(database):
    source, repo, target_scope = pair(database, "multi-command", corpus="v2")
    other_scope = next(scope for scope in source.scopes if scope.owner != target_scope.owner)
    submit(source, repo, target_scope)
    submit(source, repo, other_scope)
    legacy_source, legacy_repo, legacy_scope = pair(database, "procedure", corpus="v1")
    assert legacy_scope.owner == target_scope.owner
    submit(legacy_source, legacy_repo, legacy_scope)
    before = repo.inventory_owner(target_scope.owner)
    assert before["checkpoint_count"] == 2 and before["live_proposal_count"] > 0
    other_before = repo.inventory_owner(other_scope.owner)
    assert other_before["checkpoint_count"] == 1
    with database.transaction() as connection:
        lock_owner(connection, target_scope.owner)
        connection.execute(
            "INSERT INTO owner_lifecycle_fences(owner_id) VALUES (%s)",
            (target_scope.owner,),
        )
    # purge_owner takes only the owner identity; no project lookup is needed.
    repo.purge_owner(target_scope.owner)
    assert repo.inventory_owner(target_scope.owner) == {
        "checkpoint_count": 0,
        "scope_count": 0,
        "generations": (),
        "live_proposal_count": 0,
        "receipt_count": 0,
    }
    assert legacy_repo.inventory_owner(target_scope.owner)["checkpoint_count"] == 0
    assert repo.inventory_owner(other_scope.owner) == other_before
    assert repo.pending(other_scope)
    with database.transaction() as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM offline_consolidation_checkpoints WHERE owner_id=%s",
                (target_scope.owner,),
            ).fetchone()[0]
            == 0
        )
        assert (
            connection.execute(
                "SELECT count(*) FROM owner_lifecycle_fences WHERE owner_id=%s",
                (target_scope.owner,),
            ).fetchone()[0]
            == 1
        )


@pytest.mark.parametrize(
    "session",
    ["nullable-actor", "other-application", "other-actor", "other-owner-project", "other-client"],
)
def test_native_valid_scope_isolation_including_null_actor(database, session):
    source, repo, scope = pair(database, session, corpus="v2")
    submit(source, repo, scope)
    pending = repo.pending(scope)
    assert pending
    for other in source.scopes:
        if other != scope:
            assert not repo.pending(other)
            assert not repo.validate_cached(other, pending[0])


def test_native_explicit_backfill_and_fresh_regrant(database):
    source, repo, scope = pair(database, "fresh-regrant", corpus="v2")
    source.publish(scope, 1)
    lease = repo.claim(scope, "first")
    receipt = repo.commit(lease, source.page(scope, 0, generation=repo.generation))
    cached = repo.pending(scope)[0]
    source.withdraw(scope, "renewable")
    source.regrant(scope, "renewable")
    source.publish(scope, 2)
    backfill = PostgresProposalRepository(source, generation=BACKFILL_GENERATION)
    lease = backfill.claim(scope, "backfill")
    assert lease.cursor == 0
    backfill.commit(lease, source.page(scope, 0, generation=BACKFILL_GENERATION))
    assert backfill.pending(scope)[0].edges[0].epoch == 3
    assert not repo.validate_cached(scope, cached)
    assert repo.observe(scope, receipt.original_key) == receipt
    with database.transaction() as connection:
        assert (
            connection.execute("SELECT count(*) FROM offline_consolidation_checkpoints").fetchone()[
                0
            ]
            == 2
        )


def test_native_authority_rollback_is_detected_by_surviving_process_floor(database):
    source, repo, scope = pair(database)
    submit(source, repo, scope)
    cached = repo.pending(scope)[0]
    with database.transaction() as connection:
        revision, stale = connection.execute(
            "SELECT revision,payload FROM offline_consolidation_authorities"
        ).fetchone()
    source.withdraw(scope, cached.edges[0].source_id)
    with database.transaction() as connection:
        connection.execute(
            "UPDATE offline_consolidation_authorities SET revision=%s,payload=%s",
            (revision, Jsonb(stale)),
        )
    with pytest.raises(ConsolidationDenied):
        source.page(scope, 0)


def test_native_natural_byte_capacity_denial_preserves_checkpoint_and_receipts(database):
    source, repo, scope = pair(database, "capacity-pressure", corpus="v2")
    source.publish(scope, 65)
    for _ in range(32):
        lease = repo.claim(scope, "capacity")
        page = source.page(scope, lease.cursor, generation=repo.generation)
        with database.transaction() as connection:
            before = connection.execute(
                "SELECT payload FROM offline_consolidation_checkpoints"
            ).fetchone()[0]
        try:
            repo.commit(lease, page)
        except ConsolidationDenied:
            with database.transaction() as connection:
                after = connection.execute(
                    "SELECT payload FROM offline_consolidation_checkpoints"
                ).fetchone()[0]
            assert before == after and before["cursor"] < 65
            break
    else:
        pytest.fail("finite natural proposal-byte quota was not enforced")
    receipts = len(before["receipts"])
    repo.forget(owner=scope.owner)
    assert repo.diagnostics()["receipts"] == receipts
    assert repo.diagnostics()["retained_proposals"] == 0


def test_native_initial_issuer_mutation_failure_does_not_publish_on_retry(database):
    source, _, scope = pair(database)
    with pytest.raises(RuntimeError), source.guard():
        source.publish(scope, 1)
        raise RuntimeError("synthetic_initial_source_crash")
    assert source.page(scope, 0) is None


def test_native_frozen_corpus_generations_coexist_without_resetting_original_keys(database):
    source, repo, scope = pair(database)
    receipt = submit(source, repo, scope)
    fresh_source, fresh_repo, fresh_scope = pair(database, "nullable-actor", corpus="v2")
    submit(fresh_source, fresh_repo, fresh_scope)
    assert repo.observe(scope, receipt.original_key) == receipt
    assert fresh_repo.pending(fresh_scope)
    with database.transaction() as connection:
        assert (
            connection.execute("SELECT count(*) FROM offline_consolidation_authorities").fetchone()[
                0
            ]
            == 2
        )

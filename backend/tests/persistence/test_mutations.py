"""Deferred real-store CAS, restart, uncertain recovery, export and deletion contract."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from uuid import uuid4

import pytest

from personal_ai.auth.scope import ApplicationScope, application_scope_context
from personal_ai.mutations.service import MutationService
from personal_ai.persistence.postgres import PersistenceConflict, PostgresDatabase
from personal_ai.persistence.postgres.auth import PostgresAccountLifecycleRepository
from personal_ai.persistence.postgres.mutations import PostgresMutationRepository
from personal_ai.persistence.postgres.owner_lifecycle import OwnerFenced
from tests.test_mutations import apply, confirmed, mutation_case

pytestmark = pytest.mark.persistence_integration


@pytest.fixture
def mutation():
    return mutation_case(owner=f"mutation-test-{uuid4()}")


@pytest.fixture
def database():
    dsn = os.environ.get("PERSISTENCE_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("isolated Postgres/pgvector environment is intentionally deferred")
    database = PostgresDatabase(dsn, environment="test", min_size=1, max_size=4)
    database.migrate()
    try:
        yield database
    finally:
        database.close()


def install(f, database):
    f["repo"] = PostgresMutationRepository(database)
    f["service"] = MutationService(f["repo"], f["registry"], f["runtime"], f["permissions"],
                                   clock=lambda: f["now"][0])


def test_real_store_execution_reservation_race_restart_and_reconciliation(database, mutation):
    f = mutation
    install(f, database)
    p = confirmed(f)
    candidate = p.model_copy(update={"revision": p.revision + 1, "state": "executing",
        "execution_attempt_id": uuid4(), "lease_until": f["now"][0] + timedelta(seconds=60)})

    def reserve(_):
        try:
            f["repo"].save(candidate, expected_revision=p.revision)
            return True
        except PersistenceConflict:
            return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(reserve, range(4))) == 1
    # Domain commits but the process dies before the local result transaction.
    f["adapter"].execute(f["scope"], candidate)
    install(f, database)
    assert f["repo"].get(f["scope"], p.proposal_id).state == "executing"
    assert f["repo"].get(f["scope"].model_copy(update={"owner_id": "another-owner"}), p.proposal_id) is None
    f["now"][0] += timedelta(seconds=61)
    result = apply(f, p)
    assert result.state == "applied"
    assert apply(f, p) == result
    assert f["adapter"].sends == f["adapter"].effects == 1
    assert result.outcome.post_state.domain_version == "v2"


def test_real_store_scoped_export_immutable_audit_fence_and_purge(database, mutation):
    f = mutation
    install(f, database)
    p = confirmed(f)
    owner = p.owner_id
    class EmptyRuntime:
        def query(self, **kwargs):
            return []
    scope = ApplicationScope(application_id=f["scope"].application_id,
                             workspace_id=f["scope"].workspace_id)
    with application_scope_context(scope):
        export = PostgresAccountLifecycleRepository(database, EmptyRuntime()).export_owner(
            owner, max_records=100, max_bytes=1000000,
        )
    assert len(export["collections"]["mutation_proposals"]) == 1
    assert len(export["collections"]["mutation_proposal_revisions"]) == 3
    with application_scope_context(scope.model_copy(update={"workspace_id": "other"})):
        export = PostgresAccountLifecycleRepository(database, EmptyRuntime()).export_owner(
            owner, max_records=100, max_bytes=1000000,
        )
    assert not export["collections"]["mutation_proposals"]
    with pytest.raises(ValueError, match="fence_required"):
        f["repo"].purge_owner(owner)
    with database.transaction() as connection:
        connection.execute("INSERT INTO owner_lifecycle_fences(owner_id,deletion_request_id) VALUES(%s,%s)",
                           (owner, uuid4()))
    assert f["repo"].get(f["scope"], p.proposal_id) is None
    with pytest.raises(OwnerFenced):
        f["repo"].save(p.model_copy(update={"revision": p.revision + 1, "state": "expired",
            "terminal_code": "confirmation_expired"}), expected_revision=p.revision)
    f["repo"].purge_owner(owner)
    with database.connection() as connection:
        assert connection.execute("SELECT count(*) FROM mutation_proposal_revisions WHERE owner_id=%s", (owner,)).fetchone()[0] == 0

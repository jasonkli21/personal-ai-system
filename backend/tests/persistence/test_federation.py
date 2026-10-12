"""Opt-in Postgres CAS, restart, export, fence and deletion semantics."""

import os
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest

from personal_ai.auth.scope import ApplicationScope, application_scope_context
from personal_ai.persistence.postgres import PersistenceConflict, PostgresDatabase
from personal_ai.persistence.postgres.auth import PostgresAccountLifecycleRepository
from personal_ai.persistence.postgres.federation import PostgresFederationGrantRepository
from personal_ai.persistence.postgres.owner_lifecycle import OwnerFenced
from tests.test_federation import federation as federation_fixture

pytestmark = pytest.mark.persistence_integration


@pytest.fixture
def federation():
    return federation_fixture.__wrapped__()


@pytest.fixture
def database():
    dsn = os.environ.get("PERSISTENCE_TEST_POSTGRES_DSN")
    if not dsn:
        pytest.skip("set PERSISTENCE_TEST_POSTGRES_DSN for isolated local Postgres")
    database = PostgresDatabase(dsn, environment="test", min_size=1, max_size=4)
    database.migrate()
    try:
        yield database
    finally:
        database.close()


def test_grant_cas_restart_export_and_fenced_deletion(database, federation):
    owner = f"federation-test-{uuid4()}"
    source_policy = federation["grant"].source_policy.model_copy(update={"owner_id": owner})
    grant = federation["grant"].model_copy(
        update={"owner_id": owner, "source_policy": source_policy}
    )
    repo = PostgresFederationGrantRepository(database)
    repo.save(grant, expected_revision=0)
    assert PostgresFederationGrantRepository(database).get(owner, grant.grant_id) == grant
    assert repo.get("other", grant.grant_id) is None
    updated = grant.model_copy(update={"revision": 2, "epoch": 2})

    def save(_):
        try:
            repo.save(updated, expected_revision=1)
            return True
        except PersistenceConflict:
            return False

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert sum(executor.map(save, range(4))) == 1

    class EmptyRuntime:
        def query(self, **kwargs):
            return []

    with application_scope_context(ApplicationScope()):
        exported = PostgresAccountLifecycleRepository(database, EmptyRuntime()).export_owner(
            owner, max_records=100, max_bytes=100000
        )
    assert len(exported["collections"]["federation_grants"]) == 1
    assert len(exported["collections"]["federation_grant_revisions"]) == 2
    with pytest.raises(ValueError, match="fence_required"):
        repo.purge_owner(owner)
    with database.transaction() as connection:
        connection.execute(
            "INSERT INTO owner_lifecycle_fences(owner_id,deletion_request_id) VALUES(%s,%s)",
            (owner, uuid4()),
        )
    assert repo.get(owner, grant.grant_id) is None
    with pytest.raises(OwnerFenced):
        repo.save(updated.model_copy(update={"revision": 3, "epoch": 3}), expected_revision=2)
    repo.purge_owner(owner)
    with database.connection() as connection:
        assert (
            connection.execute(
                "SELECT count(*) FROM federation_grant_revisions WHERE owner_id=%s", (owner,)
            ).fetchone()[0]
            == 0
        )

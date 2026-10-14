"""Opt-in Postgres CAS, restart, export, fence and deletion semantics."""

import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from threading import Barrier, Lock
from uuid import uuid4

import pytest

from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import ApplicationScope, application_scope_context
from personal_ai.federation.service import FederationPermissionAuthority
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


def test_concurrent_identical_create_and_revoke_converge_in_postgres(database, federation):
    owner = f"federation-idempotency-{uuid4()}"
    repo = PostgresFederationGrantRepository(database)

    class ReadBarrierRepository:
        def __init__(self, wrapped):
            self.wrapped = wrapped
            self.lock = Lock()
            self.arm()

        def arm(self):
            self.barrier = Barrier(2)
            self.reads = 0

        def get(self, owner_id, grant_id):
            value = self.wrapped.get(owner_id, grant_id)
            with self.lock:
                wait = self.reads < 2
                self.reads += 1
            if wait:
                self.barrier.wait(timeout=10)
            return value

        def save(self, grant, *, expected_revision):
            return self.wrapped.save(grant, expected_revision=expected_revision)

        def record_access(self, selection, scope, result):
            return self.wrapped.record_access(selection, scope, result)

    synchronized_repo = ReadBarrierRepository(repo)
    authority = FederationPermissionAuthority(synchronized_repo, federation["source_policy"])
    adapter = federation["adapter"]
    from personal_ai.federation.broker import federation_contribution

    federation_contribution(
        (federation["case"],),
        authority,
        {federation["case"].export.provider_id: adapter},
    )
    intent = federation["intent"].model_copy(update={"grant_id": uuid4(), "owner_id": owner})
    principal = AuthenticatedPrincipal("issuer", "user", owner, None, 1, True)
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            created = tuple(executor.map(lambda _: authority.create(principal, intent), range(2)))
        assert created[0] == created[1]
        assert created[0].revision == 1

        synchronized_repo.arm()
        with ThreadPoolExecutor(max_workers=2) as executor:
            revoked = tuple(
                executor.map(
                    lambda _: authority.revoke(
                        principal,
                        created[0].grant_id,
                        expected_revision=1,
                        expected_issuance_id=created[0].issuance_id,
                    ),
                    range(2),
                )
            )
        assert revoked[0] == revoked[1]
        assert revoked[0].state == "revoked" and revoked[0].revision == 2
    finally:
        from personal_ai.persistence.postgres.owner_lifecycle import lock_owner

        with database.transaction() as connection:
            lock_owner(connection, owner)
            connection.execute("DELETE FROM federation_grants WHERE owner_id=%s", (owner,))


def test_destination_choices_use_persisted_time_and_exact_owner_scope(database, federation):
    """The canonical update time lives in JSON, not a physical updated_at column."""
    now = datetime.now(UTC)
    original = federation["grant"]
    owner = f"choice-test-{uuid4()}"
    source_policy = original.source_policy.model_copy(update={"owner_id": owner})
    grant = original.model_copy(
        update={
            "owner_id": owner,
            "source_policy": source_policy,
            "created_at": now,
            "updated_at": now,
            "expires_at": now + timedelta(minutes=10),
        }
    )
    repository = PostgresFederationGrantRepository(database)
    repository.save(grant, expected_revision=0)
    assert repository.list_destination(owner, grant.destination) == (grant,)
    assert repository.list_destination("another-owner", grant.destination) == ()
    wrong = grant.destination.model_copy(update={"workspace_id": "wrong"})
    assert repository.list_destination(owner, wrong) == ()
    revoked = grant.model_copy(
        update={
            "revision": 2,
            "epoch": 2,
            "state": "revoked",
            "revocation_id": uuid4(),
            "updated_at": now + timedelta(seconds=1),
        }
    )
    repository.save(revoked, expected_revision=1)
    assert repository.list_destination(owner, grant.destination) == ()

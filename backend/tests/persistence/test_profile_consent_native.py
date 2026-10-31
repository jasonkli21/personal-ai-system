"""Opt-in PI-4 native transaction, CAS, rollback and version-skew probes."""

from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest

from personal_ai.auth.scope import ApplicationScope, RequestScope
from personal_ai.context.profile import GlobalProfileFieldUpdate, GlobalProfileUpdate
from personal_ai.context.profile_consent import ConsentError, ProfileShareIntent
from personal_ai.persistence.postgres import PostgresDatabase, PostgresPayloadRepository
from personal_ai.persistence.postgres.context import PostgresGlobalProfileRepository

pytestmark = pytest.mark.persistence_integration


@pytest.fixture
def database(isolated_postgres_dsn):
    db = PostgresDatabase(isolated_postgres_dsn, environment="test")
    db.migrate()
    try:
        yield db
    finally:
        db.close()


def test_native_profile_consent_cas_replay_rollback_and_owner_fence(database):
    repository = PostgresGlobalProfileRepository(database)
    owner = f"pi4-native-{uuid4()}"
    actor = "https://accounts.google.com|synthetic"
    repository.update(owner, GlobalProfileUpdate(fields=(GlobalProfileFieldUpdate(
        field="preferred_units", value="metric",
    ),)))
    intent = ProfileShareIntent(
        operation_id=uuid4(), operation="grant", grant_id=uuid4(), field="preferred_units",
        expected_revision=0, expected_profile_revision=1,
        destination=ApplicationScope(application_id="unrelated_reader", workspace_id="shelf"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    receipt = repository.mutate_consent(owner, actor, intent)
    assert repository.mutate_consent(owner, actor, intent) == receipt
    scope = RequestScope(owner_id=owner, acting_user_id=actor, request_id="native",
                         application_id="unrelated_reader", workspace_id="shelf")
    assert repository.authorized_fields(scope, ("preferred_units",))[0][1].value == "metric"
    revoke = intent.model_copy(update={"operation_id": uuid4(), "operation": "revoke", "expected_revision": 1})
    stale = intent.model_copy(update={"operation_id": uuid4(), "grant_id": uuid4(), "expected_revision": 1})
    def execute(candidate):
        try:
            return repository.mutate_consent(owner, actor, candidate)
        except ConsentError:
            return None
    with ThreadPoolExecutor(2) as pool:
        results = list(pool.map(execute, (revoke, stale)))
    assert sum(item is not None for item in results) == 1
    state = repository.get_consents(owner)
    if not state.grants[0].revoked:
        repository.mutate_consent(owner, actor, revoke.model_copy(update={"expected_revision": state.revision}))
    before = repository.get_consents(owner)
    with pytest.raises(ConsentError):
        repository.mutate_consent(owner, actor, stale.model_copy(update={"operation_id": uuid4(), "expected_revision": 999}))
    assert repository.get_consents(owner) == before
    # Generic account inventory/export family sees canonical complete receipts.
    rows = PostgresPayloadRepository(database, "profile_consents").indexed(
        owner_id=owner, scope=ApplicationScope(), limit=1,
    )
    assert rows[0]["revision"] == before.revision
    # Value edits permanently invalidate any other active grant from the old revision.
    repository.update(owner, GlobalProfileUpdate(fields=(GlobalProfileFieldUpdate(field="preferred_units", value="imperial"),)))
    assert not repository.authorized_fields(scope, ("preferred_units",))
    with database.transaction() as connection:
        connection.execute("INSERT INTO owner_lifecycle_fences(owner_id,deletion_request_id) VALUES (%s,%s)", (owner, uuid4()))
    with pytest.raises(Exception, match="owner_deletion_fenced"):
        repository.authorized_fields(scope, ("preferred_units",))
    repository.purge_owner(owner)
    with database.connection() as connection:
        assert connection.execute("SELECT count(*) FROM profile_consents WHERE owner_id=%s", (owner,)).fetchone()[0] == 0
        assert connection.execute("SELECT count(*) FROM global_profiles WHERE owner_id=%s", (owner,)).fetchone()[0] == 0
        assert connection.execute("SELECT 1 FROM owner_lifecycle_fences WHERE owner_id=%s", (owner,)).fetchone()



def test_native_legacy_writer_cannot_resurrect_allowlist(database):
    repository = PostgresGlobalProfileRepository(database)
    owner = f"pi4-legacy-{uuid4()}"
    profile = repository.update(owner, GlobalProfileUpdate(fields=(GlobalProfileFieldUpdate(field="locale", value="en-GB"),)))
    payload = profile.model_dump(mode="json")
    payload["fields"][0]["shared_with_applications"] = ["unrelated_reader"]
    with pytest.raises(Exception, match="global_profiles_legacy_sharing_disabled"), database.transaction() as connection:
        connection.execute("UPDATE global_profiles SET payload=%s::jsonb WHERE owner_id=%s", (PostgresPayloadRepository._json(payload), owner))
    assert repository.get(owner).fields[0].shared_with_applications == ()


def test_native_migration_archives_legacy_without_authorizing_it(isolated_postgres_dsn, monkeypatch):
    from personal_ai.persistence.postgres import migrations

    db = PostgresDatabase(isolated_postgres_dsn, environment="test")
    original_files = migrations.files
    root = original_files("personal_ai.persistence")
    resources = tuple(root.joinpath("migrations").iterdir())
    class PrePI4:
        def joinpath(self, name):
            if name == "migrations":
                class Directory:
                    def iterdir(self):
                        return (p for p in resources if not p.name.startswith("032_"))
                return Directory()
            return root.joinpath(name)
    monkeypatch.setattr(migrations, "files", lambda _: PrePI4())
    db.migrate()
    repository = PostgresGlobalProfileRepository(db)
    owner = "pi4-legacy-migration"
    profile = repository.update(owner, GlobalProfileUpdate(fields=(GlobalProfileFieldUpdate(field="locale", value="en-GB"),)))
    payload = profile.model_dump(mode="json")
    payload["fields"][0]["shared_with_applications"] = ["unrelated_reader"]
    with db.transaction() as connection:
        connection.execute("UPDATE global_profiles SET payload=%s::jsonb WHERE owner_id=%s", (PostgresPayloadRepository._json(payload), owner))
    monkeypatch.setattr(migrations, "files", original_files)
    assert db.migrate() == (32,)
    assert repository.get(owner).fields[0].shared_with_applications == ()
    archive = repository.get_consents(owner)
    assert archive.legacy_sharing == {"locale": ["unrelated_reader"]}
    assert not archive.grants and not archive.receipts
    assert db.migrate() == ()
    db.close()


def test_native_lost_ack_same_key_reconciles_one_commit(database):
    from contextlib import contextmanager

    repository = PostgresGlobalProfileRepository(database)
    owner, actor = "pi4-native-ack", "verified-synthetic"
    repository.update(owner, GlobalProfileUpdate(fields=(GlobalProfileFieldUpdate(field="locale", value="en-GB"),)))
    intent = ProfileShareIntent(
        operation_id=uuid4(), operation="grant", grant_id=uuid4(), field="locale",
        expected_revision=0, expected_profile_revision=1,
        destination=ApplicationScope(application_id="unrelated_reader"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    class LostAck:
        @contextmanager
        def transaction(self, **kwargs):
            with database.transaction(**kwargs) as connection:
                yield connection
            raise TimeoutError("synthetic acknowledgement lost after commit")
    with pytest.raises(TimeoutError):
        PostgresGlobalProfileRepository(LostAck()).mutate_consent(owner, actor, intent)
    receipt = repository.mutate_consent(owner, actor, intent)
    assert receipt.revision == 1
    assert len(repository.get_consents(owner).grants) == 1
    assert len(repository.get_consents(owner).receipts) == 1


def test_native_failure_before_commit_rolls_back_grant_and_receipt(database):
    from contextlib import contextmanager

    repository = PostgresGlobalProfileRepository(database)
    owner, actor = "pi4-native-rollback", "verified-synthetic"
    repository.update(owner, GlobalProfileUpdate(fields=(GlobalProfileFieldUpdate(field="locale", value="en-GB"),)))
    intent = ProfileShareIntent(
        operation_id=uuid4(), operation="grant", grant_id=uuid4(), field="locale",
        expected_revision=0, expected_profile_revision=1,
        destination=ApplicationScope(application_id="unrelated_reader"),
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    class Rollback:
        @contextmanager
        def transaction(self, **kwargs):
            with database.transaction(**kwargs) as connection:
                yield connection
                raise RuntimeError("synthetic failure before commit")
    with pytest.raises(RuntimeError, match="before commit"):
        PostgresGlobalProfileRepository(Rollback()).mutate_consent(owner, actor, intent)
    assert repository.get_consents(owner).revision == 0
    assert not repository.get_consents(owner).grants
    assert repository.mutate_consent(owner, actor, intent).revision == 1

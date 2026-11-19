"""Disposable PostgreSQL witness for the shared service's provider and owner fences."""

import json
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing, contextmanager
from threading import Barrier, Event
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql

from personal_ai.persistence.postgres import PostgresDatabase
from personal_ai.persistence.postgres.artifacts import PostgresArtifactMetadataRepository
from personal_ai.persistence.postgres.auth import PostgresPrincipalDirectory
from personal_ai.persistence.postgres.inference_policy import PostgresInferencePolicy
from personal_ai.persistence.postgres.routing import PostgresEndpointRegistryRepository
from personal_ai.persistence.postgres.routing_observations import PostgresRoutingDecisionRepository
from personal_ai.persistence.postgres.usage.accounting import PostgresProviderUsageAccounting
from personal_ai.routing import EndpointRegistry
from personal_ai.routing.owner_policy import OwnerInferencePolicy
from personal_ai.routing.service import RoutingDecisionService, RoutingFinalizationError
from personal_ai.storage.errors import StorageError
from personal_ai.usage.contracts import UsageAdmissionDenied
from personal_ai.usage.profiles import EndpointProfileResolver
from tests.app_context_support.shared import FITNESS_APP
from tests.app_context_support.shared_inference import (
    NO_AI,
    RecipientAuthority,
    RoutedGeneration,
    free_profile,
)
from tests.test_shared_application_service import (
    B,
    body,
    create,
    post,
    provision,
    status,
)
from tests.test_shared_application_service import (
    shared_factory as asgi_factory,
)

pytestmark = pytest.mark.persistence_integration
shared_factory = asgi_factory


@pytest.fixture
def shared_db(isolated_postgres_dsn):
    database = PostgresDatabase(isolated_postgres_dsn, environment="test", min_size=1, max_size=5)
    try:
        assert database.migrate()
        yield database
    finally:
        database.close()


def native_generation(host, database, *, profile=None, recovery_current=lambda: True):
    profile = profile or free_profile()
    policy = PostgresInferencePolicy(database)
    authority = RecipientAuthority(
        profile,
        recovery_current=recovery_current,
        owner_policy=lambda connection, owner_id: policy.read_in_transaction(connection, owner_id)[
            1
        ],
    )
    catalog = PostgresEndpointRegistryRepository(database)
    registry = EndpointRegistry((profile,), repository=catalog)
    usage = PostgresProviderUsageAccounting(
        database,
        endpoint_profile_resolver=EndpointProfileResolver(registry, catalog),
    )
    routing = RoutingDecisionService(
        registry,
        PostgresRoutingDecisionRepository(database),
        usage=usage,
        authorization=authority,
    )
    host.directory.native = PostgresPrincipalDirectory(database)
    return RoutedGeneration(host.counter, routing=routing, profile=profile, authority=authority)


def query(database, statement, parameters=()):
    with database.transaction() as connection:
        return connection.execute(statement, parameters).fetchall()


def test_native_sourced_request_restart_quota_and_payer_separation(
    shared_factory,
    shared_db,
    isolated_postgres_dsn,
):
    profile = free_profile()
    profile = profile.model_copy(
        update={
            "quota_buckets": (profile.quota_buckets[0].model_copy(update={"limit": 2}),),
        }
    )
    host = shared_factory(
        generation=lambda host: native_generation(host, shared_db, profile=profile)
    )
    travel, fitness = provision(host), provision(host, FITNESS_APP, B)
    travel_id, fitness_id = create(host, travel), create(host, fitness)
    travel_body, fitness_body = body(), body()

    # An independent owner preference cannot authorize a subscription or spend.
    prefs = PostgresInferencePolicy(shared_db)
    assert prefs.read(travel.principal.owner_id) == (0, None)
    assert prefs.read(fitness.principal.owner_id) == (0, None)
    plan_only = OwnerInferencePolicy(
        schema_version="inference-policy-v2",
        mode="custom",
        routes=("subscription",),
        allow=(),
        owner_monthly_cap_micros=None,
    )
    prefs.replace(fitness.principal.owner_id, 0, plan_only)
    assert NO_AI in post(host, fitness, fitness_id, "continue", body()).text
    assert host.generation.sends == []
    assert query(shared_db, "SELECT count(*) FROM provider_attempts") == [(0,)]
    free = OwnerInferencePolicy(
        schema_version="inference-policy-v2",
        mode="free_only",
        routes=("free_api",),
        allow=(),
        owner_monthly_cap_micros=None,
    )
    prefs.replace(fitness.principal.owner_id, 1, free)
    for target, cid, payload in (
        (travel, travel_id, travel_body),
        (fitness, fitness_id, fitness_body),
    ):
        assert "event: response.completed" in post(host, target, cid, "continue", payload).text
    assert NO_AI in post(host, travel, travel_id, "continue", body()).text
    assert len(host.generation.sends) == 2
    assert query(shared_db, "SELECT count(*) FROM provider_monetary_holds") == [(0,)]
    assert query(
        shared_db, "SELECT count(*) FROM provider_attempts WHERE dispatch_claimed_at IS NOT NULL"
    ) == [(2,)]
    assert query(shared_db, "SELECT count(DISTINCT owner_id) FROM provider_invocations") == [(2,)]

    with closing(PostgresDatabase(isolated_postgres_dsn, environment="test")) as restarted:
        generation = native_generation(host, restarted, profile=profile)
        host.configure_inference(generation)
        assert status(host, travel, travel_id, travel_body).json()["state"] == "completed"
        assert (
            "event: response.completed"
            in post(host, travel, travel_id, "continue", travel_body).text
        )
        assert generation.sends == []


def test_native_sourced_cancellation_races_one_claim_on_independent_connections(
    shared_factory,
    shared_db,
    isolated_postgres_dsn,
):
    host = shared_factory(generation=lambda host: native_generation(host, shared_db))
    target = provision(host)
    cid, payload = create(host, target), body()
    barrier = Barrier(2)
    ready = Event()
    attempt = {}

    def before_claim(**arguments):
        attempt.update(arguments)
        ready.set()
        barrier.wait(timeout=4)

    host.generation.before_make_claim = before_claim
    with closing(
        PostgresDatabase(
            isolated_postgres_dsn,
            environment="test",
            min_size=1,
            max_size=2,
        )
    ) as other:
        # Build the contender on a distinct pool and leave the live identity
        # directory attached to the serving pool.
        directory = host.directory.native
        contender = native_generation(host, other).routing
        host.directory.native = directory

        def cancel():
            assert ready.wait(4)
            barrier.wait(timeout=4)
            try:
                contender.cancel_unclaimed(**attempt)
            except (RoutingFinalizationError, UsageAdmissionDenied):
                return False
            return True

        with ThreadPoolExecutor(2) as pool:
            cancelling = pool.submit(cancel)
            response = pool.submit(post, host, target, cid, "continue", payload).result(timeout=10)
            cancelled = cancelling.result(timeout=10)
        rows = query(other, "SELECT status,dispatch_claimed_at IS NOT NULL FROM provider_attempts")
        if cancelled:
            assert rows == [("rejected", False)]
            assert host.generation.sends == []
            assert "event: response.completed" not in response.text
        else:
            assert rows == [("success", True)]
            assert len(host.generation.sends) == 1
            assert "event: response.completed" in response.text
        with pytest.raises(RoutingFinalizationError, match="routing_permit_not_cancellable"):
            contender.cancel_unclaimed(**attempt)


@contextmanager
def snapshot_database(database, dsn):
    parts = urlsplit(dsn)
    name = "pai_restore_" + uuid4().hex
    database.close()
    with psycopg.connect(urlunsplit(parts._replace(path="/postgres")), autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(name),
                sql.Identifier(parts.path.removeprefix("/")),
            )
        )
        try:
            with closing(
                PostgresDatabase(
                    urlunsplit(parts._replace(path=f"/{name}")),
                    environment="test",
                )
            ) as restored:
                yield restored
        finally:
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))


class RecoveryWitness:
    """Independent fixture storage with an exact claimed-attempt/tombstone witness."""

    def __init__(self, file, database):
        self.file = file
        self.database = database
        self.epoch = uuid4().hex
        self.write({"attempt": None, "tombstone": None})

    def write(self, state):
        temporary = self.file.with_suffix(".next")
        temporary.write_text(json.dumps(state | {"epoch": self.epoch}))
        temporary.replace(self.file)

    def current(self):
        try:
            state = json.loads(self.file.read_text())
            if state.get("epoch") != self.epoch:
                return False
            if state["attempt"] is not None and query(
                self.database,
                "SELECT dispatch_claimed_at IS NOT NULL FROM provider_attempts WHERE attempt_id=%s",
                (state["attempt"],),
            ) != [(True,)]:
                return False
            return state["tombstone"] is None or query(
                self.database,
                "SELECT owner_id FROM owner_lifecycle_fences WHERE owner_id=%s",
                (state["tombstone"],),
            ) == [(state["tombstone"],)]
        except (ValueError, OSError, KeyError, StorageError, psycopg.Error):
            return False


def test_native_restore_before_revocation_is_quarantined_without_grant_resurrection(
    shared_factory,
    shared_db,
    isolated_postgres_dsn,
    tmp_path,
):
    witness = RecoveryWitness(tmp_path / "outside-database.json", shared_db)
    host = shared_factory(
        recovery_current=witness.current,
        generation=lambda host: native_generation(
            host, shared_db, recovery_current=witness.current
        ),
    )
    target = provision(host)
    cid, completed = create(host, target), body()
    assert "event: response.completed" in post(host, target, cid, "continue", completed).text
    ambiguous = body()
    open_to_claim, release = Event(), Event()
    attempt = {}

    def before_claim(**arguments):
        attempt.update(arguments)
        open_to_claim.set()
        assert release.wait(6)

    host.generation.before_make_claim = before_claim
    host.generation.transport = lambda _: ("provisional", "unknown")
    with ThreadPoolExecutor(1) as pool:
        pending = pool.submit(post, host, target, cid, "continue", ambiguous)
        try:
            assert open_to_claim.wait(4)
            with snapshot_database(shared_db, isolated_postgres_dsn) as restored:
                release.set()
                assert "event: response.completed" not in pending.result(timeout=8).text
                assert status(host, target, cid, ambiguous).json()["state"] == "unknown"
                aid = attempt["permit"].attempt_id
                owner = target.principal.owner_id
                assert query(
                    shared_db, "SELECT status FROM provider_attempts WHERE attempt_id=%s", (aid,)
                ) == [("unknown",)]
                assert query(
                    restored, "SELECT status FROM provider_attempts WHERE attempt_id=%s", (aid,)
                ) == [("pending",)]

                witness.write({"attempt": str(aid), "tombstone": None})
                witness.database = restored
                assert not witness.current()
                assert status(host, target, cid, completed).status_code == 403
                witness.database = shared_db
                assert witness.current()

                PostgresArtifactMetadataRepository(shared_db).fence(owner)
                # Simulate loss of a recreatable directory entry; the durable
                # owner tombstone still blocks onboarding before any mapping write.
                query(
                    shared_db,
                    "DELETE FROM identity_mappings WHERE owner_id=%s RETURNING owner_id",
                    (owner,),
                )
                witness.write({"attempt": str(aid), "tombstone": owner})
                assert witness.current()
                assert status(host, target, cid, completed).status_code == 403
                assert (
                    query(
                        shared_db,
                        "SELECT owner_id FROM identity_mappings WHERE owner_id=%s",
                        (owner,),
                    )
                    == []
                )
                assert query(
                    shared_db, "SELECT status FROM provider_attempts WHERE attempt_id=%s", (aid,)
                ) == [("unknown",)]

                restored_runtime = native_generation(
                    host, restored, recovery_current=witness.current
                )
                host.configure_inference(restored_runtime)
                witness.database = restored
                assert not witness.current()
                assert status(host, target, cid, completed).status_code == 403
                assert post(host, target, cid, "continue", ambiguous).status_code == 403
                assert restored_runtime.sends == []
                witness.file.unlink()
                assert status(host, target, cid, completed).status_code == 403
                assert len(host.generation.sends) == 2
        finally:
            release.set()


def test_native_loss_after_claim_retains_fence_across_worker_restart(
    shared_factory,
    shared_db,
    isolated_postgres_dsn,
    monkeypatch,
):
    host = shared_factory(generation=lambda host: native_generation(host, shared_db))
    target = provision(host)
    cid, payload = create(host, target), body()
    routing = host.generation.routing
    claimed = {}

    def lose_worker(*, send, **arguments):
        routing.claim(**arguments)
        claimed.update(arguments)
        # Terminate a separate synthetic worker at this boundary. Intentionally
        # omit the routing adapter's settlement to reproduce the durable state
        # of a PAS process that disappears immediately after the claim commits.
        worker = subprocess.run(
            [sys.executable, "-I", "-c", "import os; os._exit(17)"],
            check=False,
            timeout=2,
            capture_output=True,
        )
        assert worker.returncode == 17
        raise RoutingFinalizationError("synthetic_worker_lost_after_claim")

    monkeypatch.setattr(routing, "dispatch", lose_worker)
    response = post(host, target, cid, "continue", payload)
    assert NO_AI in response.text and host.generation.sends == []
    assert query(
        shared_db, "SELECT status,dispatch_claimed_at IS NOT NULL FROM provider_attempts"
    ) == [
        ("pending", True),
    ]
    with closing(PostgresDatabase(isolated_postgres_dsn, environment="test")) as restarted:
        generation = native_generation(host, restarted)
        host.configure_inference(generation)
        assert status(host, target, cid, payload).json()["state"] == "unknown"
        assert post(host, target, cid, "continue", payload).status_code == 409
        with pytest.raises(RoutingFinalizationError, match="routing_permit_not_cancellable"):
            generation.routing.cancel_unclaimed(
                **{key: value for key, value in claimed.items() if key != "operation"}
            )
        generation.routing.usage.stale_attempt_seconds = 0
        assert generation.routing.usage.resolve_stale_attempts(limit=5) == 1
        assert query(
            restarted, "SELECT status,dispatch_claimed_at IS NOT NULL FROM provider_attempts"
        ) == [
            ("unknown", True),
        ]
        assert generation.sends == []

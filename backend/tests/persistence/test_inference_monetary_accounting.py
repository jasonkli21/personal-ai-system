"""Native accounting proof with independent database transactions and synthetic sends."""

from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import timedelta
from hashlib import sha256
from threading import Barrier

import pytest

from personal_ai.persistence.postgres import PostgresDatabase
from personal_ai.persistence.postgres.inference_policy import PostgresInferencePolicy
from personal_ai.persistence.postgres.routing import PostgresEndpointRegistryRepository
from personal_ai.persistence.postgres.routing_observations import PostgresRoutingDecisionRepository
from personal_ai.persistence.postgres.usage.accounting import PostgresProviderUsageAccounting
from personal_ai.routing import PreparationIdentity, RoutingDecisionService
from personal_ai.routing.isolated import IsolatedInferenceRouting, SyntheticTransport
from personal_ai.routing.owner_policy import OwnerInferenceSettings, PolicyDenied
from personal_ai.routing.price import ChargeReceipt
from personal_ai.routing.registry import EndpointRegistry
from personal_ai.usage.contracts import AttemptResult, UsageAdmissionDenied
from personal_ai.usage.profiles import EndpointProfileResolver
from tests.test_endpoint_registry import _bucket, _profile
from tests.test_isolated_inference import (
    PAYLOAD,
    Authority,
    actor,
    binding,
    paid_profile,
    policy,
    price,
    selection,
)
from tests.test_routing_decision_lifecycle import Authorization, request

pytestmark = pytest.mark.persistence_integration


@pytest.fixture
def database(isolated_postgres_dsn):
    db = PostgresDatabase(isolated_postgres_dsn, environment="test", min_size=1, max_size=6)
    try:
        assert 37 in db.migrate()
        assert db.migrate() == ()
        yield db
    finally:
        db.close()


def compose(database, profiles, authority):
    catalog = PostgresEndpointRegistryRepository(database)
    registry = EndpointRegistry(profiles, repository=catalog)
    observations = PostgresRoutingDecisionRepository(database)
    usage = PostgresProviderUsageAccounting(
        database, endpoint_profile_resolver=EndpointProfileResolver(registry, catalog)
    )
    routing = RoutingDecisionService(
        registry, observations, usage=usage, authorization=Authorization()
    )
    settings = OwnerInferenceSettings(
        PostgresInferencePolicy(database),
        registry,
        is_member=lambda scope: scope.workspace_id == "demo",
    )
    return IsolatedInferenceRouting(routing, settings, authority=authority)


def prepare(coordinator, route, **changes):
    def prepare_bytes(_, decision):
        profile = next(
            p for p in coordinator.routing.registry.profiles if p.ref == decision.selected
        )
        return PreparationIdentity(
            endpoint=decision.selected,
            serializer_id=profile.serializer_id,
            input_tokens=32,
            count_source="fixture-estimate",
            count_confidence="estimated",
            prepared_input_sha256=sha256(PAYLOAD).hexdigest(),
            prepared_at=coordinator.routing.current_time(owner_id=decision.owner_id),
        )

    return selection(coordinator, route, None, **({"prepare_candidate": prepare_bytes} | changes))


def save(coordinator, *routes, cap=8, revision=0):
    return coordinator.settings.update(
        expected_revision=revision, payload=policy(*routes, cap=cap).model_dump_json().encode()
    )


def query(database, statement, *params):
    with database.transaction() as connection:
        return connection.execute(statement, params).fetchall()


def test_money_and_quota_commit_together_and_reconcile_exact_attempt(database):
    profile = paid_profile()
    route = binding(profile, "paid_api")
    authority = Authority()
    coordinator = compose(database, (profile,), authority)
    authority.exposure = price(route, coordinator.routing.current_time(owner_id="owner"))
    writes = []

    def write(profile, invocation, attempt, payload):
        assert payload == PAYLOAD
        assert query(
            database,
            "SELECT state FROM provider_monetary_holds WHERE attempt_id=%s",
            attempt.attempt_id,
        ) == [("claimed",)]
        assert query(
            database,
            "SELECT dispatch_claimed_at IS NOT NULL FROM provider_attempts WHERE attempt_id=%s",
            attempt.attempt_id,
        ) == [(True,)]
        writes.append(attempt.attempt_id)
        return "synthetic", AttemptResult(
            outcome="success",
            completed_at=authority.exposure.period.start,
            latency_ms=0,
            input_tokens=1,
            output_tokens=1,
            usage_confidence="exact",
        )

    with actor():
        save(coordinator, route)
        reserved = prepare(coordinator, route)
        admission, permit = reserved
        assert query(database, "SELECT state,maximum_micros FROM provider_monetary_holds") == [
            ("reserved", 8)
        ]
        assert query(database, "SELECT status FROM routing_decisions") == [("authorized",)]
        assert query(database, "SELECT status FROM provider_attempts") == [("pending",)]
        assert coordinator.dispatch(reserved, transport=SyntheticTransport(write)) == "synthetic"
        assert query(database, "SELECT state FROM provider_monetary_holds") == [("claimed",)]
        assert coordinator.settings.read()[-1] == 0
        restarted = compose(database, (profile,), authority)
        with pytest.raises(PolicyDenied, match="fenced"):
            prepare(restarted, route)
        with pytest.raises(PolicyDenied, match="no_authorized"):
            prepare(restarted, route, request=request().model_copy(update={"request_id": "new"}))
        receipt = ChargeReceipt(
            attempt_id=permit.attempt_id,
            payer_key=authority.exposure.payer_key,
            binding_sha256=authority.exposure.fingerprint,
            period_start=authority.exposure.period.start,
            period_end=authority.exposure.period.end,
            currency="USD",
            receipt_id="b" * 64,
            actual_micros=3,
        )
        with pytest.raises(UsageAdmissionDenied, match="unverified"):
            restarted.routing.usage.reconcile_charge(receipt, verify=lambda c, r: False)
        restarted.routing.usage.reconcile_charge(receipt, verify=lambda c, r: r == receipt)
        restarted.routing.usage.reconcile_charge(receipt, verify=lambda c, r: r == receipt)
        with pytest.raises(UsageAdmissionDenied, match="conflict"):
            restarted.routing.usage.reconcile_charge(
                receipt.model_copy(update={"actual_micros": 4}), verify=lambda c, r: True
            )
        assert restarted.settings.read()[-1] == 5
        with pytest.raises(PolicyDenied):
            prepare(restarted, route, request=request().model_copy(update={"request_id": "newer"}))
    assert writes == [permit.attempt_id]
    assert query(
        database, "SELECT state FROM inference_route_roots WHERE root_id=%s", admission.root_id
    ) == [("fenced",)]


def test_shared_payer_last_unit_and_first_settings_write_race(database):
    one = paid_profile()
    two = _profile(
        "synthetic-paid-other",
        account_scope_id=one.account_scope_id,
        credential_scope_id="another-credential",
        execution_mode="EXPLICIT_BYOK",
        cost_class="USER_BILLED",
        billing_owner="user",
        strict_free_enabled=False,
        tier_verified=False,
        quota_buckets=(_bucket("another-quota"),),
    )
    a, b = binding(one, "paid_api"), binding(two, "paid_api")
    coordinator = compose(database, (one, two), Authority())
    now = coordinator.routing.current_time(owner_id="owner")
    first_write = Barrier(2)

    def update():
        with actor("owner-a"):
            first_write.wait(timeout=5)
            try:
                return save(coordinator, a)
            except PolicyDenied:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(update) for _ in range(2)]
        assert sorted(str(future.result()) for future in futures) == ["1", "None"]
    with actor("owner-b"):
        save(coordinator, b)
    contenders = Barrier(2)

    def reserve(owner, route):
        with actor(owner):
            other = compose(database, (one, two), Authority(price(route, now)))
            contenders.wait(timeout=5)
            try:
                return prepare(other, route)
            except PolicyDenied:
                return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(reserve, "owner-a", a)
        fb = pool.submit(reserve, "owner-b", b)
        assert sum(f.result() is not None for f in (fa, fb)) == 1
    assert query(database, "SELECT state,maximum_micros FROM provider_monetary_holds") == [
        ("reserved", 8)
    ]
    assert query(database, "SELECT count(*) FROM provider_attempts") == [(1,)]


@pytest.mark.parametrize(
    "fault", ["publication", "claim_event", "price_drift", "rollover", "recovery"]
)
def test_no_send_on_rollback_or_preclaim_drift(database, monkeypatch, fault):
    profile = paid_profile()
    route = binding(profile, "paid_api")
    authority = Authority()
    coordinator = compose(database, (profile,), authority)
    observations = coordinator.routing.observations
    append = observations.append_in_transaction

    def publish(connection, *, scope, record, event):
        if (fault, event.kind) in {("publication", "authorized"), ("claim_event", "dispatched")}:
            raise RuntimeError("synthetic publication failure")
        return append(connection, scope=scope, record=record, event=event)

    monkeypatch.setattr(observations, "append_in_transaction", publish)
    authority.exposure = price(route, coordinator.routing.current_time(owner_id="owner"))
    writes = []
    with actor():
        save(coordinator, route)
        if fault == "publication":
            with pytest.raises(PolicyDenied):
                prepare(coordinator, route)
            assert query(database, "SELECT count(*) FROM provider_invocations") == [(0,)]
            assert query(database, "SELECT count(*) FROM provider_monetary_holds") == [(0,)]
            return
        reserved = prepare(coordinator, route)
        if fault == "price_drift":
            authority.exposure = authority.exposure.model_copy(update={"consent_sha256": "1" * 64})
        elif fault == "rollover":
            real_time = observations.current_time
            monkeypatch.setattr(
                observations,
                "current_time",
                lambda connection: real_time(connection) + timedelta(days=3),
            )
        elif fault == "recovery":
            authority.restored = True
        with pytest.raises(PolicyDenied):
            coordinator.dispatch(
                reserved, transport=SyntheticTransport(lambda *args: writes.append(args))
            )
        assert query(database, "SELECT state FROM provider_monetary_holds") == [("reserved",)]
        assert query(
            database, "SELECT count(*) FROM provider_attempts WHERE dispatch_claimed_at IS NOT NULL"
        ) == [(0,)]
        assert not writes


def test_abandon_releases_only_unclaimed_and_preserves_root_order(database):
    paid = paid_profile()
    free = _profile("synthetic-free-other", quota_buckets=(_bucket("free-other"),))
    first, next_route = binding(paid, "paid_api"), binding(free)
    authority = Authority()
    coordinator = compose(database, (paid, free), authority)
    authority.exposure = price(first, coordinator.routing.current_time(owner_id="owner"))
    with actor():
        save(coordinator, first, next_route)
        reserved = prepare(coordinator, first, ranked=(next_route, first))
        coordinator.abandon_unclaimed(reserved)
        admission, permit = prepare(coordinator, first, ranked=(next_route, first))
        assert admission.route == next_route and permit != reserved[1]
        assert query(database, "SELECT state FROM provider_monetary_holds") == [("released",)]
        with pytest.raises(PolicyDenied):
            coordinator.abandon_unclaimed(reserved)
        with pytest.raises(PolicyDenied):
            coordinator.dispatch(reserved, transport=SyntheticTransport(lambda *_: pytest.fail()))
        assert query(
            database,
            "SELECT sum(settled_units) FROM provider_quota_reservations WHERE attempt_id=%s",
            reserved[1].attempt_id,
        ) == [(0,)]


def test_claim_crash_restart_and_purge(database):
    profile = paid_profile()
    route = binding(profile, "paid_api")
    authority = Authority()
    coordinator = compose(database, (profile,), authority)
    authority.exposure = price(route, coordinator.routing.current_time(owner_id="owner"))
    with actor():
        save(coordinator, route)
        admission, permit = prepare(coordinator, route)
        coordinator.routing._claim(
            owner_id=admission.owner_id,
            scope=admission.scope,
            permit=permit,
            operation="bounded_generation",
            admission=admission,
        )
        restarted = compose(database, (profile,), authority)
        with pytest.raises(PolicyDenied):
            prepare(restarted, route)
        with pytest.raises(PolicyDenied):
            restarted.dispatch(
                (replace(admission, coordinator=restarted), permit),
                transport=SyntheticTransport(lambda *_: pytest.fail()),
            )
        query(
            database,
            "UPDATE provider_invocations SET retention_until=clock_timestamp() "
            "RETURNING invocation_id",
        )
        restarted.routing.usage.stale_attempt_seconds = 0
        assert restarted.routing.usage.resolve_stale_attempts(limit=5) == 1
        restarted.routing.usage.purge_expired(limit=20)
        assert query(database, "SELECT state FROM provider_monetary_holds") == [("claimed",)]
        assert query(database, "SELECT status FROM provider_attempts") == [("unknown",)]
        assert restarted.settings.read()[-1] == 0


def test_restored_older_database_cannot_reissue_claim_with_external_witness(
    database, isolated_postgres_dsn
):
    from urllib.parse import urlsplit, urlunsplit
    from uuid import uuid4

    import psycopg
    from psycopg import sql

    class RecoveryWitness(Authority):
        attempt = None

        def recovery_current(self, connection):
            if self.attempt is None:
                return True
            return connection.execute(
                "SELECT state FROM provider_monetary_holds WHERE attempt_id=%s", (self.attempt,)
            ).fetchone() == ("claimed",)

    profile = paid_profile()
    route = binding(profile, "paid_api")
    authority = RecoveryWitness()
    before = compose(database, (profile,), authority)
    authority.exposure = price(route, before.routing.current_time(owner_id="owner"))
    with actor():
        save(before, route)
        admission, permit = prepare(before, route)
    original = urlsplit(isolated_postgres_dsn)
    clone = "pai_restore_" + uuid4().hex
    database.close()
    with psycopg.connect(urlunsplit(original._replace(path="/postgres")), autocommit=True) as admin:
        admin.execute(
            sql.SQL("CREATE DATABASE {} TEMPLATE {}").format(
                sql.Identifier(clone),
                sql.Identifier(original.path.removeprefix("/")),
            )
        )
        restored = PostgresDatabase(
            urlunsplit(original._replace(path=f"/{clone}")), environment="test"
        )
        try:
            with actor():
                before.routing._claim(
                    owner_id=admission.owner_id,
                    scope=admission.scope,
                    permit=permit,
                    operation="bounded_generation",
                    admission=admission,
                )
                authority.attempt = permit.attempt_id
                after = compose(restored, (profile,), authority)
                assert query(restored, "SELECT state FROM provider_monetary_holds") == [
                    ("reserved",)
                ]
                with pytest.raises(PolicyDenied):
                    after.dispatch(
                        (replace(admission, coordinator=after), permit),
                        transport=SyntheticTransport(lambda *_: pytest.fail()),
                    )
                with pytest.raises(PolicyDenied):
                    prepare(after, route)
                assert query(restored, "SELECT state FROM provider_monetary_holds") == [
                    ("reserved",)
                ]
        finally:
            restored.close()
            admin.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(clone)))


def test_revoked_owner_policy_stops_fallback_but_releases_unclaimed(database):
    profile = paid_profile()
    route = binding(profile, "paid_api")
    authority = Authority()
    coordinator = compose(database, (profile,), authority)
    authority.exposure = price(route, coordinator.routing.current_time(owner_id="owner"))
    with actor():
        save(coordinator, route)
        reserved = prepare(coordinator, route)
        save(coordinator, cap=None, revision=1)
        with pytest.raises(PolicyDenied):
            coordinator.dispatch(reserved, transport=SyntheticTransport(lambda *_: pytest.fail()))
        coordinator.abandon_unclaimed(reserved)
        assert query(database, "SELECT state FROM provider_monetary_holds") == [("released",)]
        assert query(database, "SELECT state FROM inference_route_roots") == [("stopped",)]
        with pytest.raises(PolicyDenied):
            prepare(coordinator, route)


def test_owner_fence_keeps_financial_audit_and_denies_policy_read(database):
    profile = paid_profile()
    route = binding(profile, "paid_api")
    authority = Authority()
    coordinator = compose(database, (profile,), authority)
    authority.exposure = price(route, coordinator.routing.current_time(owner_id="owner"))
    with actor():
        save(coordinator, route)
        reserved = prepare(coordinator, route)
        query(
            database,
            "INSERT INTO owner_lifecycle_fences(owner_id) VALUES ('owner') RETURNING owner_id",
        )
        with pytest.raises(PolicyDenied):
            coordinator.dispatch(reserved, transport=SyntheticTransport(lambda *_: pytest.fail()))
        with pytest.raises(RuntimeError, match="owner_deletion_fenced"):
            coordinator.settings.read()
    assert query(database, "SELECT state FROM provider_monetary_holds") == [("reserved",)]


def test_claim_races_unclaimed_cancellation_on_independent_connections(database):
    profile = paid_profile()
    route = binding(profile, "paid_api")
    authority = Authority()
    coordinator = compose(database, (profile,), authority)
    authority.exposure = price(route, coordinator.routing.current_time(owner_id="owner"))
    with actor():
        save(coordinator, route)
        reserved = prepare(coordinator, route)

    barrier = Barrier(2)
    writes = []

    def write(*values):
        writes.append(values[-1])
        return "synthetic", AttemptResult(
            outcome="success",
            completed_at=authority.exposure.period.start,
            latency_ms=0,
        )

    def compete(cancel):
        with actor():
            barrier.wait(timeout=5)
            try:
                if cancel:
                    coordinator.abandon_unclaimed(reserved)
                else:
                    coordinator.dispatch(reserved, transport=SyntheticTransport(write))
                return True
            except PolicyDenied:
                return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        cancellation, claim = tuple(pool.map(compete, (True, False)))
    assert cancellation != claim
    assert writes == ([PAYLOAD] if claim else [])
    assert query(database, "SELECT state FROM provider_monetary_holds") == [
        ("claimed" if claim else "released",)
    ]


def test_owner_cap_spans_apps_and_payers_and_excess_freezes_profile(database):
    from personal_ai.auth.scope import ApplicationScope

    first = paid_profile()
    second = _profile(
        "synthetic-paid-second-payer",
        account_scope_id="provider-account-b",
        credential_scope_id="second-key",
        execution_mode="EXPLICIT_BYOK",
        cost_class="USER_BILLED",
        billing_owner="user",
        strict_free_enabled=False,
        tier_verified=False,
        quota_buckets=(_bucket("second-payer-quota", authority_scope_id="provider-account-b"),),
    )
    a = binding(first, "paid_api")
    b = binding(second, "paid_api").model_copy(
        update={"scope": ApplicationScope(application_id="travel", workspace_id="demo")}
    )
    authority = Authority()
    coordinator = compose(database, (first, second), authority)
    now = coordinator.routing.current_time(owner_id="owner")
    authority.exposure = price(a, now)
    with actor():
        save(coordinator, a, b)
        admission, permit = prepare(coordinator, a)
        coordinator.routing._claim(
            owner_id=admission.owner_id,
            scope=admission.scope,
            permit=permit,
            operation="bounded_generation",
            admission=admission,
        )
        receipt = ChargeReceipt(
            attempt_id=permit.attempt_id,
            payer_key=authority.exposure.payer_key,
            binding_sha256=authority.exposure.fingerprint,
            period_start=authority.exposure.period.start,
            period_end=authority.exposure.period.end,
            currency="USD",
            receipt_id="8" * 64,
            actual_micros=9,
        )
        coordinator.routing.usage.reconcile_charge(receipt, verify=lambda c, r: r == receipt)
        assert coordinator.settings.read()[-1] == 0
    assert query(
        database, "SELECT actual_micros, owner_month, payer_start FROM provider_monetary_holds"
    ) == [(9, now.date().replace(day=1), authority.exposure.period.start)]
    authority.exposure = price(b, now, payer_key="a" * 64)
    with actor(application="travel", workspace="demo"), pytest.raises(
        PolicyDenied, match="no_authorized"
    ):
        prepare(coordinator, b)
    # A different verified owner cannot use the affected payer or pricing profile.
    authority.exposure = price(a, now)
    with actor("another"):
        save(coordinator, a)
        with pytest.raises(PolicyDenied, match="no_authorized"):
            prepare(coordinator, a)
    assert query(database, "SELECT count(*) FROM provider_attempts") == [(1,)]

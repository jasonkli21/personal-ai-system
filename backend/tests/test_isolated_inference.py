"""Hermetic policy and shared dispatch contract; no native finance claims."""

from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hashlib import sha256

import pytest
from pydantic import ValidationError

from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.scope import (
    ApplicationScope,
    RequestScope,
    bind_request_scope,
    bind_verified_principal,
    reset_request_scope,
    reset_verified_principal,
)
from personal_ai.routing import RoutingDecisionService, RoutingFinalizationError
from personal_ai.routing.isolated import IsolatedInferenceRouting, SyntheticTransport
from personal_ai.routing.owner_policy import (
    FREE_ONLY,
    ExactRoute,
    OwnerInferencePolicy,
    OwnerInferenceSettings,
    PolicyDenied,
    RouteGrant,
    order_candidates,
    read_policy,
)
from personal_ai.routing.price import BilledDimension, BillingGroup, PaidExposure, PayerPeriod
from personal_ai.routing.registry import EndpointRegistry
from personal_ai.usage.contracts import AttemptResult
from tests.test_endpoint_registry import _profile
from tests.test_routing_decision_lifecycle import (
    Authorization,
    MemoryRepository,
    Usage,
    request,
    task,
)
from tests.test_routing_decision_lifecycle import prepare as prepare_identity

SCOPE = ApplicationScope()
PAYLOAD = b"synthetic-input"
NOW = datetime(2026, 11, 18, tzinfo=UTC)


@contextmanager
def actor(owner="owner", application="personal_ai", workspace=None, *, authenticated=True):
    principal = AuthenticatedPrincipal("fixture", owner, owner, None, 0, authenticated)
    principal_token = bind_verified_principal(principal)
    scope_token = bind_request_scope(
        RequestScope(
            owner_id=owner,
            acting_user_id=f"fixture|{owner}",
            request_id="http-fixture",
            application_id=application,
            workspace_id=workspace,
        )
    )
    try:
        yield
    finally:
        reset_request_scope(scope_token)
        reset_verified_principal(principal_token)


def binding(profile, route_class="free_api"):
    return ExactRoute(
        route_class=route_class,
        profile=profile.ref,
        model=profile.model_id,
        credential=profile.credential_scope_id,
        account=profile.account_scope_id,
        recipient="fixture-app",
        scope=SCOPE,
        operation="bounded_generation",
        price_revision="price-v1" if route_class == "paid_api" else None,
    )


def policy(*routes, cap=None):
    return OwnerInferencePolicy(
        schema_version="inference-policy-v2",
        mode="custom"
        if cap or any(route.route_class == "subscription" for route in routes)
        else "free_only",
        routes=tuple(dict.fromkeys(r.route_class for r in routes)) or ("free_api",),
        allow=routes,
        owner_monthly_cap_micros=cap,
    )


def paid_profile():
    return _profile(
        "synthetic-paid",
        execution_mode="EXPLICIT_BYOK",
        cost_class="USER_BILLED",
        billing_owner="user",
        strict_free_enabled=False,
        tier_verified=False,
    )


def price(route, now, **changes):
    values = {
        "route": route,
        "payer_key": "f" * 64,
        "consent_sha256": "c" * 64,
        "authenticated_rate_source": "d" * 64,
        "currency": "USD",
        "period": PayerPeriod(
            start=now - timedelta(days=2),
            end=now + timedelta(days=2),
            anchor=now - timedelta(days=2),
            timezone="UTC",
        ),
        "price_start": now - timedelta(days=2),
        "price_end": now + timedelta(days=3),
        "groups": (
            BillingGroup(
                dimensions=tuple(
                    BilledDimension(
                        dimension=d,
                        micros_per_million=250_000 if d == "input" else 0,
                        increment=1,
                        minimum=0,
                    )
                    for d in ("input", "output", "reasoning", "requests")
                ),
                minimum_micros=0,
                fixed_micros=0,
            ),
        ),
        "root_cap_micros": 8,
        "owner_cap_micros": 8,
        "payer_cap_micros": 8,
        "reasoning_bound": 0,
        "upstream_maximum_micros": 8,
        "payer_granted": True,
        "synthetic_account_exclusive": True,
    }
    return PaidExposure(**(values | changes))


@dataclass
class Authority:
    exposure: PaidExposure | None = None
    active: bool = True
    restored: bool = False
    maximum_sensitivity: str = "public"

    def recovery_current(self, connection):
        return not self.restored

    def current(self, connection, admission, now):
        if not self.active:
            return None, None
        return RouteGrant(
            route=admission.route,
            owner_id=admission.owner_id,
            actor_id=admission.actor_id,
            payload_sha256=admission.payload_sha256,
            valid_until=now + timedelta(minutes=3),
            maximum_sensitivity=self.maximum_sensitivity,
            operator_enabled=True,
            credential_owner_verified=True,
            installation_verified=True,
            privacy_region_verified=True,
            prepared_fields_verified=True,
            counter_verified=True,
            source_free=True,
            foreground=True,
        ), self.exposure if admission.route.route_class == "paid_api" else None


class MemorySettings:
    def __init__(self):
        self.policies = {}
        self.roots = {}

    def read(self, owner):
        return self.policies.get(owner, (0, None))

    def read_in_transaction(self, connection, owner):
        return self.read(owner)

    def replace(self, owner, revision, policy):
        if revision != self.read(owner)[0]:
            raise PolicyDenied("inference_policy_revision_changed")
        self.policies[owner] = revision + 1, policy.model_dump_json().encode()
        return revision + 1

    def remaining(self, owner, cap):
        return cap

    def root(self, connection, root, owner):
        return self.roots.get((root, owner))

    def open_root(self, connection, *, root_id, owner_id, payload, plan, deadline):
        row = self.roots.setdefault((root_id, owner_id), (payload, plan, deadline, 0, "open", None))
        if row[:2] != (payload, plan):
            raise PolicyDenied("inference_request_conflict")
        return row

    def change_root(self, connection, *, root_id, owner_id, candidate, state, attempt_id):
        row = self.roots[root_id, owner_id]
        self.roots[root_id, owner_id] = (*row[:3], candidate, state, attempt_id)


@pytest.fixture
def hermetic():
    profile = _profile()
    registry = EndpointRegistry((profile,))
    repo = MemoryRepository()
    routing = RoutingDecisionService(
        registry, repo, usage=Usage(repo), authorization=Authorization()
    )
    settings = OwnerInferenceSettings(MemorySettings(), registry, is_member=lambda scope: False)
    return (
        IsolatedInferenceRouting(routing, settings, authority=Authority()),
        binding(profile),
        repo,
    )


def selection(coordinator, route, repo, **changes):
    return coordinator.prepare(
        **(
            {
                "request": request(),
                "task": task(max_physical_attempts=1),
                "payload": PAYLOAD,
                "ranked": (route,),
                "recipient": "fixture-app",
                "prepare_candidate": lambda _, decision: prepare_identity(decision, repo),
            }
            | changes
        )
    )


@pytest.mark.parametrize(
    "data,valid",
    [
        (None, True),
        (b'{"schema_version":"inference-policy-v1","plan":true}', True),
        (b"{}", False),
        (b'{"schema_version":"inference-policy-v3"}', False),
        (b'{"schema_version":"inference-policy-v1","schema_version":"inference-policy-v1"}', False),
        (b'{"schema_version":"inference-policy-v2","mode":"free_only"}', False),
        (b"\xff", False),
    ],
)
def test_legacy_and_bad_settings_infer_no_grants(data, valid):
    assert read_policy(data)[0] == FREE_ONLY
    assert (read_policy(data)[1] is None) is valid


def test_settings_requires_current_verified_owner_and_management_scope(hermetic):
    coordinator, route, repo = hermetic
    settings = coordinator.settings
    route_policy = policy(route).model_dump_json().encode()
    for identity in (
        {},
        {"authenticated": False},
        {"application": "travel"},
        {"workspace": "not-authorized"},
    ):
        if not identity:
            with pytest.raises(PolicyDenied):
                settings.read()
            continue
        with actor(**identity), pytest.raises(PolicyDenied):
            settings.update(expected_revision=0, payload=route_policy)
    with actor():
        assert settings.read() == (0, ("free_api",), None, None)
        with pytest.raises(PolicyDenied, match="no_authorized"):
            selection(coordinator, route, repo)
        assert settings.update(expected_revision=0, payload=route_policy) == 1
        with pytest.raises(PolicyDenied, match="revision_changed"):
            settings.update(expected_revision=0, payload=route_policy)
    with actor("another"):
        assert settings.read()[0] == 0
        with pytest.raises(PolicyDenied, match="no_authorized"):
            selection(coordinator, route, repo)


def test_class_order_and_exact_intersection():
    free = binding(_profile())
    paid = binding(paid_profile(), "paid_api")
    plan = ExactRoute(**(free.model_dump() | {"route_class": "subscription"}))
    config = policy(plan, free, paid, cap=8)
    authority = Authority()
    digest = sha256(PAYLOAD).hexdigest()
    from types import SimpleNamespace

    grants = tuple(
        authority.current(
            None,
            SimpleNamespace(
                route=r,
                owner_id="owner",
                actor_id="fixture|owner",
                payload_sha256=digest,
            ),
            NOW,
        )[0]
        for r in (paid, free, plan)
    )
    kwargs = {
        "ranked": (paid, free, plan),
        "grants": grants,
        "owner_id": "owner",
        "actor_id": "fixture|owner",
        "scope": SCOPE,
        "recipient": "fixture-app",
        "payload_sha256": digest,
        "sensitivity": "public",
        "now": NOW,
    }
    assert order_candidates(config, **kwargs) == (plan, free, paid)
    assert order_candidates(config, **kwargs, narrowing=frozenset({paid, free})) == (free, paid)
    for changes in (
        {"recipient": "foreign"},
        {"actor_id": "foreign"},
        {"payload_sha256": "0" * 64},
        {"sensitivity": "personal"},
        {"now": NOW + timedelta(days=1)},
    ):
        assert order_candidates(config, **(kwargs | changes)) == ()
    with pytest.raises(ValidationError):
        ExactRoute(**(paid.model_dump() | {"model": "*"}))


@pytest.mark.parametrize("outcome", ["success", "timeout", "rate_limited", "incomplete"])
def test_only_one_synthetic_transport_callback_and_no_public_bypass(hermetic, outcome):
    coordinator, route, repo = hermetic
    calls = []

    def write(*args):
        assert not repo.in_transaction
        assert args[-1] == PAYLOAD
        calls.append(args)
        return "synthetic", AttemptResult(outcome=outcome, completed_at=repo.now, latency_ms=0)

    with actor():
        coordinator.settings.update(
            expected_revision=0, payload=policy(route).model_dump_json().encode()
        )
        reserved = selection(coordinator, route, repo)
        with pytest.raises(RoutingFinalizationError, match="isolated_authority_required"):
            coordinator.routing.claim(
                owner_id="owner", scope=SCOPE, permit=reserved[1], operation="bounded_generation"
            )
        if outcome == "success":
            assert (
                coordinator.dispatch(reserved, transport=SyntheticTransport(write)) == "synthetic"
            )
        else:
            with pytest.raises(PolicyDenied, match="inference_execution_unavailable"):
                coordinator.dispatch(reserved, transport=SyntheticTransport(write))
        with pytest.raises(PolicyDenied):
            coordinator.dispatch(reserved, transport=SyntheticTransport(write))
        with pytest.raises(PolicyDenied):
            selection(coordinator, route, repo)
    assert len(calls) == 1


def test_exact_price_rounding_and_unsupported_inputs():
    route = binding(paid_profile(), "paid_api")
    pricing = price(route, NOW, upstream_maximum_micros=1)
    assert pricing.maximum(input_tokens=3, output_tokens=1, now=NOW) == 1
    for input_tokens, output_tokens in ((5, 1), (True, 1), (3, None), (-1, 1)):
        with pytest.raises(PolicyDenied):
            pricing.maximum(input_tokens=input_tokens, output_tokens=output_tokens, now=NOW)
    for changes in (
        {"currency": "EUR"},
        {"reasoning_bound": 2.5},
        {"payer_granted": False},
        {"synthetic_account_exclusive": False},
    ):
        with pytest.raises(ValidationError):
            price(route, NOW, **changes)


@pytest.mark.parametrize(
    "bad", ["root_reuse", "changed_bytes", "background", "source", "workspace"]
)
def test_scope_and_payload_fences_never_call_transport(hermetic, bad):
    from dataclasses import replace

    coordinator, route, repo = hermetic
    with actor():
        coordinator.settings.update(
            expected_revision=0, payload=policy(route).model_dump_json().encode()
        )
        if bad in {"background", "source"}:
            changes = (
                {"task": task(max_physical_attempts=1, max_auxiliary_calls=1)}
                if bad == "background"
                else {"request": request(source_reference_sha256s=("2" * 64,))}
            )
            with pytest.raises(PolicyDenied):
                selection(coordinator, route, repo, **changes)
            assert not repo.attempts
            return
        reserved = selection(coordinator, route, repo)
        if bad == "root_reuse":
            with pytest.raises(PolicyDenied, match="conflict"):
                selection(coordinator, route, repo, payload=b"changed synthetic input")
        elif bad == "changed_bytes":
            admission, permit = reserved
            with pytest.raises(PolicyDenied):
                coordinator.dispatch(
                    (replace(admission, payload=b"mismatch"), permit),
                    transport=SyntheticTransport(lambda *_: pytest.fail()),
                )
        else:
            with actor(workspace="other"), pytest.raises(PolicyDenied):
                coordinator.dispatch(
                    reserved, transport=SyntheticTransport(lambda *_: pytest.fail())
                )
        assert not repo.claimed


def test_quota_preflight_moves_only_to_next_authorized_candidate():
    from tests.test_endpoint_registry import _bucket

    first = _profile("empty-free", quota_buckets=(_bucket("empty"),))
    second = _profile("next-free", quota_buckets=(_bucket("next"),))
    a, b = binding(first), binding(second)
    registry = EndpointRegistry((first, second))
    repo = MemoryRepository()
    usage = Usage(repo)
    snapshots = usage.routing_snapshots

    def check(connection, profiles, *args, **kwargs):
        usage.exhausted = tuple(profiles) == (first,)
        try:
            return snapshots(connection, profiles, *args, **kwargs)
        finally:
            usage.exhausted = False

    usage.routing_snapshots = check
    routing = RoutingDecisionService(registry, repo, usage=usage, authorization=Authorization())
    settings = OwnerInferenceSettings(MemorySettings(), registry, is_member=lambda scope: False)
    coordinator = IsolatedInferenceRouting(routing, settings, authority=Authority())
    with actor():
        settings.update(expected_revision=0, payload=policy(a, b).model_dump_json().encode())
        assert selection(coordinator, a, repo, ranked=(a, b))[0].route == b
        another = request().model_copy(update={"request_id": "narrowed"})
        with pytest.raises(PolicyDenied, match="no_authorized"):
            selection(
                coordinator, a, repo, request=another, ranked=(a, b), narrowing=frozenset({a})
            )
    assert [record.status for record in repo.records.values()] == [
        "no_route",
        "authorized",
        "no_route",
    ]

"""P35 hard-admission, canonical composition, replay/dataset and shadow contracts."""

import json
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

import pytest
from pydantic import ValidationError

from personal_ai.auth.scope import ApplicationScope
from personal_ai.evaluation.adaptive_routing import (
    DatasetRow,
    ObservationDataset,
    OutcomeLabel,
    PromotionComparison,
    SplitPolicy,
    build_dataset,
    collect_dataset,
    evaluate_strategy,
    historical_quality,
    normalized_configuration_facts,
)
from personal_ai.persistence.factory import PostgresDynamoPersistenceFactory
from personal_ai.routing import EndpointRegistry, RoutingPreferences, StrategyView
from personal_ai.routing.adaptive import (
    DEFAULT_ADAPTIVE_STRATEGY_REGISTRY,
    AdaptiveArtifact,
    BoundedCapacityStrategy,
    ShadowRoutingStrategy,
    configured_routing_strategy,
    rule_implementation_sha256,
)
from personal_ai.routing.decision_models import RoutingFeatureContext
from personal_ai.routing.features import coverage_identity, digest, extract_features
from personal_ai.routing.strategy import (
    QuotaAwareDeterministicStrategy,
    _implementation_sha256,
    replay_deterministic_decision,
)
from personal_ai.settings import Settings
from personal_ai.usage.observations import pipeline_metrics
from tests.test_endpoint_registry import _bucket, _profile
from tests.test_provider_matrix import _matrix
from tests.test_routing_phase21 import SCOPE, Authorization, MemoryRepository, Usage, request, task
from tests.test_routing_phase23 import _candidate, _quota_fact

NOW = datetime(2026, 10, 12, tzinfo=UTC)


def view():
    candidates = tuple(
        _candidate(name, name, priority=priority).model_copy(
            update={
                "quality_score": quality,
                "endpoint_configuration_sha256": str(i) * 64,
                "quality_identity_sha256": str(i) * 64,
            }
        )
        for i, (name, priority, quality) in enumerate((("strong", 1, 0.95), ("ample", 0, 0.94)), 1)
    )
    return StrategyView(
        preferences=RoutingPreferences(),
        candidates=candidates,
        quota_buckets=(
            _quota_fact("strong", remaining=1, now=NOW),
            _quota_fact("ample", remaining=100, now=NOW),
        ),
        observed_at=NOW,
        feature_context=RoutingFeatureContext(
            application_id="personal_ai",
            task_id="chat",
            task_profile_id="task:chat",
            task_profile_version=1,
            task_configuration_sha256="a" * 64,
            requirements_sha256="b" * 64,
            policy_sha256="c" * 64,
            input_token_bucket=7,
            output_token_bucket=5,
        ),
    )


def artifact(v, **changes):
    facts = {
        "dataset_sha256": "d" * 64,
        "baseline_implementation_sha256": QuotaAwareDeterministicStrategy().implementation_sha256,
        "strategy_implementation_sha256": rule_implementation_sha256(),
        "coverage_sha256s": (coverage_identity(v),),
        "measured_at": v.observed_at - timedelta(seconds=1),
        "fresh_until": v.observed_at + timedelta(days=1),
    }
    return AdaptiveArtifact(**{**facts, **changes})


def factory(monkeypatch, profiles=None):
    # Only stores/current authority are substituted; inherited production
    # routing_service owns registry/strategy/accounting composition.
    f = PostgresDynamoPersistenceFactory(object(), object())
    repo = MemoryRepository()
    repo.now = datetime.now(UTC)
    registry = EndpointRegistry(profiles or (_profile("allowed"),))
    usage = Usage(repo)
    monkeypatch.setattr(
        f, "endpoint_profile_resolver", lambda _: SimpleNamespace(endpoint_registry=registry)
    )
    monkeypatch.setattr(f, "routing_decision_repository", lambda: repo)
    monkeypatch.setattr(f, "provider_usage_accounting", lambda _: usage)
    return f, repo, usage


def settings(**changes):
    return Settings(_env_file=None, ai_provider="fake", ai_model="synthetic", **changes)


def test_rule_first_shadow_changes_no_route_and_has_no_dispatch_capability(monkeypatch):
    monkeypatch.setattr("personal_ai.routing.adaptive.perf_counter_ns", lambda: 0)
    v = view()
    adaptive = BoundedCapacityStrategy(artifact(v))
    proposed, reason = adaptive.propose(v)
    assert reason is None and proposed[0].endpoint.endpoint_profile_id == "ample"
    shadow = ShadowRoutingStrategy(adaptive)
    baseline = shadow.select(v)
    assert baseline[0].endpoint.endpoint_profile_id == "strong"
    observation = shadow.observe(v, baseline)
    assert not observation.agreement and observation.latency_us >= 0 and observation.cpu_us >= 0
    assert observation.ranking[0].endpoint.endpoint_profile_id == "ample"
    assert not any(
        hasattr(shadow, name) for name in ("dispatch", "provider", "usage", "authorization")
    )


def test_distinct_adaptive_strategy_id_registers_without_generic_router_changes():
    v = view()

    class SecondStrategy:
        execution_contract = "bounded-pure-in-process-v1"

        def __init__(self, adaptive_artifact):
            self.artifact = adaptive_artifact
            self.ref = adaptive_artifact.ref

        def propose(self, strategy_view):
            return QuotaAwareDeterministicStrategy().select(strategy_view), "test-abstention"

    strategy_sha = _implementation_sha256(SecondStrategy.propose)
    registry = DEFAULT_ADAPTIVE_STRATEGY_REGISTRY.register(
        "test-second-strategy",
        "1",
        SecondStrategy,
        implementation_sha256=strategy_sha,
        execution_contract="bounded-pure-in-process-v1",
    )
    configured = settings(
        routing_shadow_enabled=True,
        routing_shadow_artifact=artifact(
            v,
            strategy_id="test-second-strategy",
            strategy_implementation_sha256=strategy_sha,
        ).model_dump(mode="json"),
    )
    shadow = configured_routing_strategy(configured, registry=registry)
    assert isinstance(shadow, ShadowRoutingStrategy)
    assert shadow.adaptive.ref.strategy_id == "test-second-strategy"
    assert shadow.observe(v, shadow.select(v)).abstention_reason == "test-abstention"

    with pytest.raises(ValueError, match="execution_contract_unsupported"):
        DEFAULT_ADAPTIVE_STRATEGY_REGISTRY.register(
            "unbounded-test-strategy",
            "1",
            SecondStrategy,
            implementation_sha256=strategy_sha,
            execution_contract="unbounded",
        )


def test_implementation_source_digests_are_cached_off_the_request_path(monkeypatch):
    import personal_ai.routing.strategy as strategy_module

    strategy_module._implementation_sha256.cache_clear()
    rule_implementation_sha256.cache_clear()
    rule_hash = rule_implementation_sha256()
    baseline_hash = QuotaAwareDeterministicStrategy().implementation_sha256

    def unexpected_source_read(_function):
        raise AssertionError("inspect.getsource ran after implementation registration")

    monkeypatch.setattr(strategy_module.inspect, "getsource", unexpected_source_read)
    assert rule_implementation_sha256() == rule_hash
    assert QuotaAwareDeterministicStrategy().implementation_sha256 == baseline_hash


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"feature_schema": "unknown-v99"}, "feature-schema-incompatible"),
        ({"fresh_until": NOW, "measured_at": NOW - timedelta(days=1)}, "artifact-stale"),
        ({"baseline_implementation_sha256": "0" * 64}, "baseline-incompatible"),
        ({"strategy_implementation_sha256": "0" * 64}, "strategy-implementation-incompatible"),
        ({"coverage_sha256s": ("0" * 64,)}, "out-of-coverage"),
        ({"maximum_input_bucket": 1}, "complexity-abstention"),
    ],
)
def test_artifact_compatibility_abstains(change, reason):
    v = view()
    ranking, actual = BoundedCapacityStrategy(artifact(v, **change)).propose(v)
    assert actual == reason and ranking == QuotaAwareDeterministicStrategy().select(v)


@pytest.mark.parametrize(
    "change", ["config", "quality", "profile", "composition", "task", "policy", "requirements"]
)
def test_endpoint_model_account_tier_serializer_count_task_churn_demotes(change):
    v = view()
    strategy = BoundedCapacityStrategy(artifact(v))
    if change in {"config", "quality", "profile"}:
        c = v.candidates[0]
        update = (
            {"endpoint_configuration_sha256": "0" * 64}
            if change == "config"
            else {"quality_identity_sha256": "0" * 64}
            if change == "quality"
            else {"endpoint": c.endpoint.model_copy(update={"profile_version": 2})}
        )
        changed = v.model_copy(
            update={"candidates": (c.model_copy(update=update), *v.candidates[1:])}
        )
    elif change == "composition":
        changed = v.model_copy(update={"candidates": v.candidates[:1]})
    else:
        field = {
            "task": "task_configuration_sha256",
            "policy": "policy_sha256",
            "requirements": "requirements_sha256",
        }[change]
        changed = v.model_copy(
            update={"feature_context": v.feature_context.model_copy(update={field: "0" * 64})}
        )
    assert strategy.propose(changed)[1] == "out-of-coverage"


def test_absent_quality_unknown_quota_and_equivalent_margin_abstain():
    v = view()
    for update, expected in (
        ({"quality_score": None}, "supported-signals-missing"),
        ({"quality_score": 0.5}, "no-supported-resource-margin"),
    ):
        changed = v.model_copy(
            update={"candidates": (v.candidates[0], v.candidates[1].model_copy(update=update))}
        )
        assert BoundedCapacityStrategy(artifact(changed)).propose(changed)[1] == expected
    unknown = v.model_copy(
        update={
            "quota_buckets": (
                v.quota_buckets[0],
                _quota_fact("ample", remaining=None, confidence="unknown", now=NOW),
            )
        }
    )
    assert (
        BoundedCapacityStrategy(artifact(unknown)).propose(unknown)[1]
        == "supported-signals-missing"
    )


def test_raw_sensitive_inputs_are_not_feature_arguments():
    serialized = json.dumps(extract_features(view()))
    for field in ("prompt", "content", "credential", "account", "source", "personal-secret"):
        assert field not in serialized
    with pytest.raises(ValidationError):
        StrategyView.model_validate({**view().model_dump(), "prompt": "personal-secret"})


def test_shadow_failures_malformed_proposals_and_overhead_rollback(monkeypatch):
    v = view()
    adaptive = BoundedCapacityStrategy(artifact(v))
    shadow = ShadowRoutingStrategy(adaptive)
    monkeypatch.setattr(
        adaptive, "propose", lambda _: (_ for _ in ()).throw(RuntimeError("private-error"))
    )
    result = shadow.observe(v, shadow.select(v))
    assert result.abstention_reason == "strategy-unavailable" and result.agreement
    assert "private-error" not in result.model_dump_json()
    monkeypatch.setattr(adaptive, "propose", lambda _: (shadow.select(v)[:1], None))
    assert shadow.observe(v, shadow.select(v)).abstention_reason == "strategy-unavailable"
    monkeypatch.setattr(adaptive, "propose", lambda _: (shadow.select(v), None))
    times = iter((0, 6_000_000))
    monkeypatch.setattr("personal_ai.routing.adaptive.perf_counter_ns", lambda: next(times))
    result = shadow.observe(v, shadow.select(v))
    assert result.abstention_reason == "strategy-overhead-exceeded" and result.agreement


def test_production_factory_hard_filter_input_no_extra_sends_removal_and_replay(monkeypatch):
    profiles = [_profile("allowed")]
    for mode, cost in (
        ("STRICT_FREE", "USER_BILLED"),
        ("STRICT_FREE", "UNKNOWN"),
        ("EXPLICIT_BYOK", "USER_BILLED"),
    ):
        profiles.append(
            _profile(
                f"blocked:{mode}:{cost}",
                execution_mode=mode,
                cost_class=cost,
                strict_free_enabled=False,
                tier_verified=False,
                billing_owner="unknown",
                quota_buckets=(_bucket(f"blocked:{mode}:{cost}"),),
            )
        )
    from tests.test_external_turns import profile

    profiles.append(profile())
    from personal_ai.routing.contracts import ProviderAccessPolicy

    explicit = _profile("explicit:free")
    profiles.append(
        explicit.model_copy(
            update={
                "access_policy": ProviderAccessPolicy(
                    selection_mode="explicit_only", automation_eligible=False
                )
            }
        )
    )
    f, repo, usage = factory(monkeypatch, profiles)
    auth = Authorization()
    from personal_ai.api.dependencies import get_routing_decision_service

    monkeypatch.setattr(
        "personal_ai.api.dependencies.persistence_factory", lambda _settings: f
    )
    baseline = get_routing_decision_service(settings(), auth)
    d = baseline.route(owner_id="owner", scope=SCOPE, task=task(), request=request())
    a = artifact(d.strategy_view())
    seen = []

    original_propose = BoundedCapacityStrategy.propose

    def capture_propose(self, v):
        seen.append(v)
        return original_propose(self, v)

    monkeypatch.setattr(BoundedCapacityStrategy, "propose", capture_propose)
    configured = settings(
        routing_shadow_enabled=True, routing_shadow_artifact=a.model_dump(mode="json")
    )
    routed = get_routing_decision_service(configured, auth)
    facts = request().model_copy(update={"request_id": "request:shadow"})
    decision = routed.route(owner_id="owner", scope=SCOPE, task=task(), request=facts)
    assert {c.endpoint.endpoint_profile_id for c in seen[0].candidates} == {"allowed"}
    assert decision.selected == d.selected and decision.shadow is not None
    assert usage.reserve_calls == 0 and not repo.attempts
    assert (
        replay_deterministic_decision(decision, QuotaAwareDeterministicStrategy(), now=repo.now)
        == d.ranking
    )
    before = len(seen)
    assert routed.route(owner_id="owner", scope=SCOPE, task=task(), request=facts) == decision
    assert len(seen) == before
    # Kill switch/implementation removal requires no orchestration or transport edit.
    rollback = f.routing_service(settings(), authorization=auth)
    d2 = rollback.route(
        owner_id="owner",
        scope=SCOPE,
        task=task(),
        request=facts.model_copy(update={"request_id": "request:rollback"}),
    )
    assert d2.ranking == d.ranking and d2.shadow is None
    unknown = settings(
        routing_shadow_enabled=True,
        routing_shadow_artifact={**a.model_dump(mode="json"), "strategy_id": "missing-strategy"},
    )
    assert isinstance(configured_routing_strategy(unknown), QuotaAwareDeterministicStrategy)


def test_routing_authorization_dependency_fails_closed_without_phase15_authority():
    from types import SimpleNamespace

    from fastapi import HTTPException

    from personal_ai.api.dependencies import get_routing_authorization_authority

    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace()))
    with pytest.raises(HTTPException) as error:
        get_routing_authorization_authority(request)
    assert error.value.status_code == 503
    assert error.value.detail == "routing_authorization_unavailable"


@pytest.mark.parametrize("failure", ["authorization", "quota", "quality", "fit", "privacy"])
def test_adaptive_never_sees_deterministically_rejected_candidates(monkeypatch, failure):
    f, _repo, usage = factory(monkeypatch)
    auth = Authorization()
    baseline = f.routing_service(settings(), authorization=auth)
    d = baseline.route(owner_id="owner", scope=SCOPE, task=task(), request=request())
    a = artifact(d.strategy_view())
    s = f.routing_service(
        settings(routing_shadow_enabled=True, routing_shadow_artifact=a.model_dump()),
        authorization=auth,
    )
    if failure == "authorization":
        auth.deny = True
    elif failure == "quota":
        usage.exhausted = True
    t, facts = task(), request().model_copy(update={"request_id": f"request:{failure}"})
    if failure == "quality":
        from personal_ai.routing import QualityPolicy

        t = task(
            quality=QualityPolicy(
                mode="measured_floor",
                quality_profile_id="q",
                quality_profile_version=1,
                minimum_score=0.8,
                minimum_coverage=0.5,
            )
        )
    if failure in {"fit", "privacy"}:
        facts = facts.model_copy(
            update={
                "requirements": facts.requirements.model_copy(
                    update={
                        "input_tokens": 100000
                        if failure == "fit"
                        else facts.requirements.input_tokens,
                        "sensitivity": "restricted"
                        if failure == "privacy"
                        else facts.requirements.sensitivity,
                    }
                )
            }
        )
    outcome = s.route(owner_id="owner", scope=SCOPE, task=t, request=facts)
    assert (
        not outcome.strategy_view().candidates
        and outcome.selected is None
        and outcome.shadow is None
    )
    assert usage.reserve_calls == 0


def matrix_dataset(monkeypatch, *, split_policy=None):
    runner, evaluations, repo, _executor, _profiles, fixtures, t = _matrix(include_blocked=False)
    # Dispatch permit expiry is checked against wall time, so keep the
    # repository clock aligned with the runner instead of freezing it at the
    # historical temporal holdout cutoff below.
    repo.now = datetime.now(UTC)
    f = PostgresDynamoPersistenceFactory(object(), object())
    monkeypatch.setattr(
        f,
        "endpoint_profile_resolver",
        lambda _: SimpleNamespace(endpoint_registry=runner.routing_service.registry),
    )
    monkeypatch.setattr(f, "routing_decision_repository", lambda: repo)
    monkeypatch.setattr(f, "provider_usage_accounting", lambda _: runner.routing_service.usage)
    runner.routing_service = f.routing_service(
        settings(), authorization=Authorization(), evaluation_quality_authority=evaluations
    )
    run_id = UUID("00000000-0000-0000-0000-000000000035")
    runner.run(
        evaluation_run_id=run_id,
        fixtures=fixtures,
        task=t,
        policy_version=fixtures[0].policy_version,
    )
    states = {str(run_id): evaluations.get_run_state(run_id)}
    records = tuple(repo.records.values())
    policy = split_policy or SplitPolicy(temporal_cutoff=NOW)
    resources = {}
    for record in records:
        observed = []
        for invocation, attempt, result in repo.attempts.values():
            if invocation.request_id != record.decision.request.request_id:
                continue
            observed.append(
                {
                    "dispatch_claimed_at": attempt.started_at
                    if attempt.attempt_id in repo.claimed
                    else None,
                    "status": result.outcome if result else "pending",
                    "input_tokens": result.input_tokens if result else None,
                    "output_tokens": result.output_tokens if result else None,
                    "latency_ms": result.latency_ms if result else None,
                    "reserved_tokens": attempt.reserved_tokens,
                    "operation": invocation.operation,
                    "endpoint_profile_id": invocation.endpoint.endpoint_profile_id,
                    "parent_attempt_id": attempt.parent_attempt_id,
                    "reservations": attempt.reservation_units,
                }
            )
        resources[record.decision.routing_decision_id] = pipeline_metrics(observed, complete=True)
    return (
        build_dataset(
            records,
            run_states=states,
            split_policy=policy,
            complete=True,
            pipeline_by_decision=resources,
        ),
        records,
        states,
    )


def test_dataset_reproducible_groups_missing_labels_and_no_prompt(monkeypatch):
    dataset, records, states = matrix_dataset(monkeypatch)
    split_policy = SplitPolicy(temporal_cutoff=NOW)
    first_decision = records[0].decision
    normalized = normalized_configuration_facts(first_decision, split_policy=split_policy)
    operational_variant = first_decision.model_copy(
        update={
            "owner_id": "different-owner",
            "workspace_id": "different-workspace",
            "routing_decision_id": UUID("00000000-0000-0000-0000-000000000999"),
            "root_decision_id": UUID("00000000-0000-0000-0000-000000000999"),
            "created_at": first_decision.created_at + timedelta(minutes=1),
            "request": first_decision.request.model_copy(
                update={"request_id": "different-request", "run_id": "different-run"}
            ),
        }
    )
    assert normalized_configuration_facts(
        operational_variant, split_policy=split_policy
    ) == normalized
    profile_index = next(i for i, candidate in enumerate(first_decision.candidates) if candidate.eligible)
    changed_candidates = list(first_decision.candidates)
    changed_profile = changed_candidates[profile_index].model_copy(
        update={"endpoint_configuration_sha256": "0" * 64}
    )
    changed_candidates[profile_index] = changed_profile
    assert normalized_configuration_facts(
        first_decision.model_copy(update={"candidates": tuple(changed_candidates)}),
        split_policy=split_policy,
    ) != normalized
    changed_feature = first_decision.feature_context.model_copy(
        update={"policy_sha256": "0" * 64}
    )
    assert normalized_configuration_facts(
        first_decision.model_copy(update={"feature_context": changed_feature}),
        split_policy=split_policy,
    ) != normalized
    changed_schema = first_decision.feature_context.model_copy(
        update={"schema_version": "routing-features-v99"}
    )
    assert normalized_configuration_facts(
        first_decision.model_copy(update={"feature_context": changed_schema}),
        split_policy=split_policy,
    ) != normalized

    observed_candidate = first_decision.candidates[0].model_copy(
        update={
            "health_failure_streak": first_decision.candidates[0].health_failure_streak + 1
        }
    )
    candidate_facts = (observed_candidate, *first_decision.candidates[1:])
    changed_decision = first_decision.model_copy(
        update={"candidates": candidate_facts}
    )
    changed_record = records[0].model_copy(update={"decision": changed_decision})
    changed_corpus = build_dataset(
        (changed_record, *records[1:]),
        run_states=states,
        split_policy=split_policy,
        complete=True,
        pipeline_by_decision={
            record.decision.routing_decision_id: next(
                row.pipeline_metrics
                for row in dataset.rows
                if row.observation_sha256 == digest(original)
            )
            for record, original in zip((changed_record, *records[1:]), records)
        },
    )
    assert (
        changed_corpus.manifest["strategy_policy_profile_config_facts_sha256"]
        == dataset.manifest["strategy_policy_profile_config_facts_sha256"]
    )
    assert (
        changed_corpus.manifest["source_observation_corpus_sha256"]
        != dataset.manifest["source_observation_corpus_sha256"]
    )
    assert changed_corpus.sha256 != dataset.sha256
    repeated = build_dataset(
        tuple(reversed(records)),
        run_states=states,
        split_policy=SplitPolicy(temporal_cutoff=NOW),
        complete=True,
        pipeline_by_decision={
            r.decision.routing_decision_id: next(
                row.pipeline_metrics for row in dataset.rows if row.observation_sha256 == digest(r)
            )
            for r in records
        },
    )
    assert repeated.sha256 == dataset.sha256
    assert len(dataset.rows) == 80 and len({r.group_sha256 for r in dataset.rows}) == 1
    assert {r.split for r in dataset.rows} == {"temporal_holdout"}
    assert all(sum(label is not None for label in row.labels) == 1 for row in dataset.rows)
    assert all(label.source == "synthetic" for row in dataset.rows for label in row.labels if label)
    from personal_ai.evaluation.adaptive_routing import paired_outcomes

    pairs = paired_outcomes(records, states)
    assert len(pairs) == 20 and all(len(p["outcomes"]) == 3 for p in pairs)
    assert not any(p["promotion_eligible"] for p in pairs)
    assert all(not hasattr(row, "prompt") for row in dataset.rows)
    duplicate = build_dataset(
        (*records, records[0]),
        run_states=states,
        split_policy=SplitPolicy(temporal_cutoff=NOW),
        complete=True,
    )
    assert duplicate.manifest["deduplicated"] == 1
    config = records[0].decision.candidates[0].endpoint_configuration_sha256
    separated = build_dataset(
        records,
        run_states=states,
        split_policy=SplitPolicy(
            temporal_cutoff=NOW + timedelta(days=1), configuration_holdout=(config,)
        ),
        complete=True,
    )
    assert {r.split for r in separated.rows} == {"configuration_holdout"}
    unlabeled = {key: (start, completion, ()) for key, (start, completion, _) in states.items()}
    missing = build_dataset(
        records, run_states=unlabeled, split_policy=SplitPolicy(temporal_cutoff=NOW), complete=True
    )
    assert missing.manifest["missing_labels"] == 80
    assert all(x is None for r in missing.rows for x in r.labels)


def test_historical_aggregate_cutoff_does_not_use_future_outcomes():
    v = view()
    label = OutcomeLabel(
        endpoint=v.candidates[0].endpoint,
        source="synthetic",
        source_version="p22-v1",
        evaluation_identity_sha256="a" * 64,
        known_at=NOW + timedelta(hours=1),
        quality=0.9,
        hard_boundaries_passed=True,
    )
    row = DatasetRow(
        observation_sha256="b" * 64,
        group_sha256="c" * 64,
        coverage_sha256=coverage_identity(v),
        observed_at=NOW,
        split="train",
        view=v,
        selected=label.endpoint,
        labels=(label, None),
    )
    assert (
        historical_quality(
            (row,),
            before=NOW + timedelta(minutes=1),
            coverage_sha256=row.coverage_sha256,
            endpoint=label.endpoint,
        )
        is None
    )
    assert (
        historical_quality(
            (row,),
            before=label.known_at + timedelta(seconds=1),
            coverage_sha256=row.coverage_sha256,
            endpoint=label.endpoint,
        )
        == 0.9
    )


def test_observation_collection_truncation_and_empty_are_distinct(monkeypatch):
    f, _, usage = factory(monkeypatch)
    calls = []

    class Empty:
        def observation_page(self, **kwargs):
            calls.append(kwargs)
            return (), None, True

    monkeypatch.setattr(f, "routing_decision_repository", lambda: Empty())
    monkeypatch.setattr(f, "provider_matrix_evaluation_repository", lambda: None)
    dataset = collect_dataset(
        f,
        owner_id="owner",
        scope=ApplicationScope(),
        start=NOW,
        end=NOW + timedelta(days=1),
        split_policy=SplitPolicy(temporal_cutoff=NOW),
        accounting=usage,
    )
    assert dataset.manifest["complete"] and dataset.manifest["included"] == 0
    assert calls[0]["owner_id"] == "owner"


def test_p19_projection_counts_every_claim_retry_count_and_unknown_consumption():
    base = {
        "dispatch_claimed_at": NOW,
        "status": "success",
        "input_tokens": 10,
        "output_tokens": 2,
        "latency_ms": 3,
        "reserved_tokens": 20,
        "operation": "bounded_generation",
        "endpoint_profile_id": "a",
        "parent_attempt_id": None,
        "reservations": (("bucket", 1),),
    }
    attempts = (
        base,
        {**base, "operation": "token_counting"},
        {**base, "parent_attempt_id": UUID(int=1)},
        {**base, "dispatch_claimed_at": None, "status": "rejected"},
    )
    measured = pipeline_metrics(attempts, complete=True)
    assert measured["physical_attempts"] == 3 and measured["auxiliary_attempts"] == 1
    assert measured["retry_attempts"] == 1 and measured["input_tokens"] == 30
    assert measured["conservative_reserved_tokens"] == 80
    assert measured["conservative_quota_reservations"] == (("bucket", 4),)
    uncertain = pipeline_metrics(
        ({**base, "status": "unknown", "input_tokens": None},), complete=False
    )
    assert not uncertain["settled"] and uncertain["input_tokens"] is None


def test_phase35_offline_evaluation_no_promotion_from_synthetic_agreement(monkeypatch, tmp_path):
    dataset, _, _ = matrix_dataset(monkeypatch)
    v = dataset.rows[0].view
    a = artifact(
        v, dataset_sha256=dataset.sha256, coverage_sha256s=tuple(dataset.manifest["coverage"])
    )
    report = evaluate_strategy(dataset, BoundedCapacityStrategy(a))
    assert not report["promoted_coverage"]
    assert len(report["measurements"]) == 80
    assert report["non_abstaining_proposals"] == 0
    assert report["supported_alternate_quality_comparisons"] == 0
    assert report["pipeline_complete_groups"] == 0
    assert report["quality_comparison_status"] == "unverified"
    assert sum(report["abstention_reason_counts"].values()) == 80
    assert all(m["strategy_latency_us"] >= 0 for m in report["measurements"])
    assert all(
        m["single_case_latency_plus_strategy_us"] is not None for m in report["measurements"]
    )
    assert all(c["reasons"] for c in report["coverage"])
    assert all(
        coverage["gates"]["quality"]["status"] == "unverified"
        and coverage["gates"]["resource_saving"]["status"] == "unverified"
        and coverage["gates"]["pipeline_latency"]["status"] == "unverified"
        for coverage in report["coverage"]
    )
    assert report["strategy2"].startswith("deferred") and report["strategy3"].startswith("deferred")
    evidence = {"manifest": dataset.manifest, "report": report}
    (tmp_path / "phase35-evaluation.json").write_text(json.dumps(evidence, indent=2))
    snapshot = {
        "schema_version": "adaptive-routing-synthetic-snapshot-v1",
        "dataset_sha256": dataset.sha256,
        "manifest": dataset.manifest,
        "rows": [r.model_dump(mode="json") for r in dataset.rows],
        "artifact": a.model_dump(mode="json"),
    }
    (tmp_path / "snapshot.json").write_text(json.dumps(snapshot, indent=2))
    print(
        json.dumps(
            {
                "phase35": {
                    "rows": len(dataset.rows),
                    "groups": 1,
                    "dataset_sha256": dataset.sha256,
                    "promoted": [],
                    "artifact": a.model_dump(mode="json"),
                    "minimum_strategy_us": min(
                        m["strategy_latency_us"] for m in report["measurements"]
                    ),
                    "maximum_strategy_us": max(
                        m["strategy_latency_us"] for m in report["measurements"]
                    ),
                    "manifest": dataset.manifest,
                }
            },
            sort_keys=True,
        )
    )


def test_promotion_gate_matrix_consumes_supported_live_comparisons(monkeypatch):
    monkeypatch.setattr(
        "personal_ai.routing.adaptive.perf_counter_ns",
        iter(range(0, 1_000_000, 1000)).__next__,
    )
    v = view()
    coverage = coverage_identity(v)
    splits = ("grouped_holdout", "temporal_holdout", "configuration_holdout")
    rows = []
    comparisons = []
    for i, split in enumerate(splits):
        for offset in range(30):
            index = i * 30 + offset + 1
            group_sha = f"{index:064x}"
            rows.append(
                DatasetRow(
                    observation_sha256=f"{index + 1000:064x}",
                    group_sha256=group_sha,
                    coverage_sha256=coverage,
                    observed_at=NOW,
                    split=split,
                    view=v,
                    selected=QuotaAwareDeterministicStrategy().select(v)[0].endpoint,
                    labels=(None, None),
                )
            )
            comparisons.append(
                PromotionComparison(
                    coverage_sha256=coverage,
                    group_sha256=group_sha,
                    split=split,
                    evidence_identity_sha256=f"{index + 2000:064x}",
                    quality_delta=0.1,
                    resource_saving=0.1,
                    pipeline_latency_increase_us=0,
                    pipeline_complete=True,
                    calibration_supported=True,
                )
            )
    dataset = ObservationDataset(tuple(rows), {"coverage": [coverage], "complete": True})
    adaptive_artifact = artifact(
        v, dataset_sha256=dataset.sha256, coverage_sha256s=(coverage,)
    )
    passed = evaluate_strategy(
        dataset,
        BoundedCapacityStrategy(adaptive_artifact),
        promotion_evidence=comparisons,
    )
    assert passed["promoted_coverage"] == [coverage]
    assert all(gate["status"] == "pass" for gate in passed["coverage"][0]["gates"].values())

    failed = evaluate_strategy(
        dataset,
        BoundedCapacityStrategy(adaptive_artifact),
        promotion_evidence=[
            item.model_copy(update={"quality_delta": -0.1, "resource_saving": 0.01})
            for item in comparisons
        ],
    )
    assert not failed["promoted_coverage"]
    assert failed["coverage"][0]["gates"]["quality"]["status"] == "fail"
    assert failed["coverage"][0]["gates"]["resource_saving"]["status"] == "fail"


def test_unobserved_alternative_is_missing_even_when_shadow_prefers_it(monkeypatch):
    monkeypatch.setattr("personal_ai.routing.adaptive.perf_counter_ns", lambda: 0)
    from personal_ai.evaluation.adaptive_routing import ObservationDataset

    v = view()
    selected = QuotaAwareDeterministicStrategy().select(v)[0].endpoint
    label = OutcomeLabel(
        endpoint=selected,
        source="synthetic",
        source_version="p22-v1",
        evaluation_identity_sha256="a" * 64,
        known_at=NOW + timedelta(seconds=1),
        quality=0.95,
        hard_boundaries_passed=True,
        latency_ms=3,
    )
    row = DatasetRow(
        observation_sha256="b" * 64,
        group_sha256="c" * 64,
        coverage_sha256=coverage_identity(v),
        observed_at=NOW,
        split="temporal_holdout",
        view=v,
        selected=selected,
        labels=(label, None),
    )
    dataset = ObservationDataset((row,), {"coverage": [row.coverage_sha256], "complete": True})
    report = evaluate_strategy(dataset, BoundedCapacityStrategy(artifact(v)))
    measured = report["measurements"][0]
    assert measured["supported_selected_quality"] is None
    assert not measured["agreement"] and not report["promoted_coverage"]


def test_optional_shadow_errors_and_invalid_metadata_cannot_change_route(monkeypatch):
    f, repo, _usage = factory(monkeypatch)
    s = f.routing_service(settings(), authorization=Authorization())
    d = s.route(owner_id="owner", scope=SCOPE, task=task(), request=request())
    wrapped = ShadowRoutingStrategy(BoundedCapacityStrategy(artifact(d.strategy_view())))
    s.strategy = wrapped

    def throw(*_):
        raise ValueError("private-diagnostic")

    monkeypatch.setattr(wrapped, "observe", throw)
    failed = s.route(
        owner_id="owner",
        scope=SCOPE,
        task=task(),
        request=request().model_copy(update={"request_id": "request:failure"}),
    )
    assert failed.ranking == d.ranking and failed.shadow is None
    assert failed.shadow_omission_reason == "routing-shadow-unavailable"
    real = ShadowRoutingStrategy(BoundedCapacityStrategy(artifact(d.strategy_view())))
    monkeypatch.setattr(
        wrapped,
        "observe",
        lambda v, ranking: real.observe(v, ranking).model_copy(
            update={"artifact_metadata_json": "{}"}
        ),
    )
    invalid = s.route(
        owner_id="owner",
        scope=SCOPE,
        task=task(),
        request=request().model_copy(update={"request_id": "request:invalid"}),
    )
    assert invalid.ranking == d.ranking and invalid.shadow is None
    assert invalid.shadow_omission_reason == "routing-shadow-invalid-or-overflow"
    assert not repo.attempts


def test_partial_collection_manifest_and_unknown_conversation_grouping(monkeypatch):
    f, repo, usage = factory(monkeypatch)
    d = f.routing_service(settings(), authorization=Authorization()).route(
        owner_id="owner", scope=SCOPE, task=task(), request=request()
    )

    class Truncated:
        def observation_page(self, **_):
            return (repo.records[d.routing_decision_id],), (NOW, d.routing_decision_id), False

    monkeypatch.setattr(f, "routing_decision_repository", lambda: Truncated())
    monkeypatch.setattr(f, "provider_matrix_evaluation_repository", lambda: None)
    usage.request_observation = lambda **_: pipeline_metrics((), complete=False)
    dataset = collect_dataset(
        f,
        owner_id="owner",
        scope=SCOPE,
        start=NOW,
        end=NOW + timedelta(days=1),
        split_policy=SplitPolicy(temporal_cutoff=NOW),
        accounting=usage,
        max_records=1,
    )
    assert not dataset.manifest["complete"]
    assert dataset.manifest["excluded"] == {"canonical-session-grouping-unavailable": 1}


def test_frozen_synthetic_replay_digest_and_scoped_no_promotion():
    from pathlib import Path

    from personal_ai.evaluation.adaptive_routing import load_snapshot
    from personal_ai.evaluation.quota_scarcity import run_quota_scarcity_evaluation

    path = (
        Path(__file__).parents[1]
        / "src/personal_ai/evaluation/fixtures/routing/adaptive-observations-v1.json"
    )
    dataset, a = load_snapshot(path)
    report = evaluate_strategy(dataset, BoundedCapacityStrategy(a))
    assert report["dataset_sha256"] == a.dataset_sha256 and not report["promoted_coverage"]
    assert all(
        "independent_live_groups:unverified" in c["reasons"]
        for c in report["coverage"]
    )
    frozen = json.loads((path.parent / "adaptive-baseline-v1.json").read_text())
    assert run_quota_scarcity_evaluation().model_dump(mode="json") == frozen["quota_baseline"]


def test_missing_input_count_does_not_become_zero_complexity():
    from personal_ai.routing.features import token_bucket
    assert token_bucket(None) is None and token_bucket(0) == 0
    v = view().model_copy(update={"feature_context": view().feature_context.model_copy(
        update={"input_token_bucket": None})})
    ranking, reason = BoundedCapacityStrategy(artifact(v)).propose(v)
    assert reason == "input-count-unavailable"
    assert ranking == QuotaAwareDeterministicStrategy().select(v)


def test_shadow_artifact_cannot_promote_through_direct_strategy_injection():
    v = view()
    adaptive = BoundedCapacityStrategy(artifact(v))
    assert adaptive.propose(v)[0][0].endpoint != QuotaAwareDeterministicStrategy().select(v)[0].endpoint
    assert adaptive.select(v) == QuotaAwareDeterministicStrategy().select(v)

"""Integrated synthetic evidence through installed production seams; no external effects."""

import json
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from pathlib import Path
from statistics import median
from time import perf_counter
from uuid import uuid4

import pytest
from fastapi import Depends
from fastapi.testclient import TestClient
from pydantic import BaseModel

from personal_ai.api.dependencies import (
    get_application_context,
    get_context_assembler,
    get_context_research_repository,
    get_external_context_assembler,
    get_global_profile_repository,
    get_message_repository,
    get_provider_usage_accounting,
    get_routing_decision_service,
    get_settings,
    get_summary_repository,
)
from personal_ai.applications.contracts import (
    ApplicationContextPolicy,
    ApplicationContextRequest,
    ApplicationDefinition,
    ApplicationLaunchContext,
    ApplicationSidecarPolicy,
    CapabilityRegistration,
    ContextFieldPolicy,
    ContextOperationPolicy,
    ContextProviderPolicy,
)
from personal_ai.applications.registry import (
    ApplicationContribution,
    ApplicationContributionCatalog,
    default_application_registry,
)
from personal_ai.auth.scope import ApplicationScope
from personal_ai.context.planner import ContextPlanningRule
from personal_ai.context.providers import (
    ContextEntityReference,
    ContextItem,
    ContextOperationSpec,
    ContextPermissionDependency,
    ContextPreparationError,
    ContextProviderError,
    ContextProviderSpec,
    ContextSelection,
    ContextSourceReference,
)
from personal_ai.context.repositories import InMemorySummaryRepository
from personal_ai.context.runtime import (
    EMPTY_CONTEXT_RUNTIME_REGISTRY,
    ContextRuntimeContribution,
    ContextRuntimeContributionCatalog,
)
from personal_ai.context.tokens import EstimatedTokenCounter
from personal_ai.entities import Message
from personal_ai.evaluation.memory_lifecycle import apply_fixture
from personal_ai.evaluation.memory_optimization import _EmbeddingObservations
from personal_ai.evaluation.retrieval import load_configuration, measure
from personal_ai.evaluation.verification.__main__ import MATRIX_PATH
from personal_ai.main import create_app
from personal_ai.routing.contracts import DataUsePolicy, ProviderAccessPolicy
from personal_ai.settings import Settings
from tests.test_adaptive_routing_phase35 import artifact, factory, settings
from tests.test_endpoint_registry import _bucket, _profile
from tests.test_external_turns import profile as plan_profile
from tests.test_memory_phase34 import change, environment, retriever
from tests.test_memory_phase34 import request as memory_scope
from tests.test_routing_phase21 import SCOPE, Authorization, request, task

APP = "synthetic_fifth"
SPACE = "synthetic-space"
THRESHOLDS = json.loads(MATRIX_PATH.read_bytes())["thresholds"]


class RecordPayload(BaseModel):
    title: str


class ConstraintPayload(BaseModel):
    limit: int


class ScopedAuthority:
    permission_namespaces = ("fifth.read:",)

    def __init__(self):
        self.current = True
        self.member = True

    def supports(self, dependency):
        return dependency.permission_id.startswith(self.permission_namespaces)

    def is_current(self, dependency):
        return (
            self.current
            and self.supports(dependency)
            and dependency.version == "epoch-1"
            and dependency.owner_id == "local"
            and dependency.acting_user_id == "local-development|local-development"
            and dependency.source_scope == ApplicationScope(application_id=APP, workspace_id=SPACE)
            and dependency.entity_ref is not None
            and dependency.entity_ref.entity_id in {"record-1", "constraint-1"}
            and dependency.source_revision == "entity-v7"
        )

    def is_member(self, principal, application_id, workspace_id):
        return (
            self.member
            and principal.owner_id == "local"
            and application_id == APP
            and workspace_id == SPACE
        )


class EmbeddingObservations(_EmbeddingObservations):
    token_estimate = 0

    def embed(self, texts, **kwargs):
        self.token_estimate += sum(int(len(t.encode()) * 1.1 + 0.999) for t in texts)
        return super().embed(texts, **kwargs)


class TypedProvider:
    """Domain-owned synthetic records with independent exact scope/currentness."""

    def __init__(self, kind, payload, authority):
        self.reference = ContextEntityReference(
            entity_type=kind, entity_id=kind + "-1", application_id=APP, workspace_id=SPACE
        )
        self.payload, self.authority = payload, authority
        self.calls = 0
        self.spec = ContextProviderSpec(
            provider_id="fifth." + kind,
            source_class="domain_current",
            source_version="typed-v1",
            operations=(
                ContextOperationSpec(
                    operation="current",
                    allowed_fields=tuple(type(payload).model_fields),
                    accepts_entity_refs=True,
                    maximum_results=1,
                ),
            ),
        )

    def validate_selection(self, selection, inputs):
        if (
            inputs.scope.owner_id != "local"
            or inputs.scope.acting_user_id != "local-development|local-development"
            or inputs.scope.application_id != APP
            or inputs.scope.workspace_id != SPACE
            or selection.entity_refs != (self.reference,)
            or not self.authority.current
        ):
            raise ContextProviderError("fifth_source_denied")

    def fetch(self, selection, scope, *, deadline):
        self.calls += 1
        now = datetime.now(UTC)
        return (
            ContextItem(
                provider_id=self.spec.provider_id,
                source_class="domain_current",
                source_id=self.reference.entity_id,
                source_version="entity-v7",
                item_id=self.reference.entity_id + ":7",
                owner_id=scope.owner_id,
                application_id=APP,
                workspace_id=SPACE,
                authority="authoritative",
                sensitivity="personal",
                observed_at=now,
                expires_at=now + timedelta(minutes=5),
                entity_refs=(self.reference,),
                payload=self.payload,
                source_refs=(
                    ContextSourceReference(
                        kind="record",
                        reference_id=self.reference.entity_id,
                        fingerprint=sha256(self.payload.model_dump_json().encode()).hexdigest(),
                    ),
                ),
                permission_dependencies=(
                    ContextPermissionDependency(
                        permission_id="fifth.read:" + self.reference.entity_id,
                        version="epoch-1",
                        purpose="selected synthetic read",
                        owner_id=scope.owner_id,
                        acting_user_id=scope.acting_user_id,
                        source_scope=ApplicationScope(application_id=APP, workspace_id=SPACE),
                        entity_ref=self.reference,
                        source_revision="entity-v7",
                    ),
                ),
            ),
        )


def fifth_app(monkeypatch):
    authority = ScopedAuthority()
    providers = (
        TypedProvider("record", RecordPayload(title="synthetic title"), authority),
        TypedProvider("constraint", ConstraintPayload(limit=7), authority),
    )
    policy = ApplicationContextPolicy()
    policies = tuple(
        ContextProviderPolicy(
            provider_id=p.spec.provider_id,
            operations=(
                ContextOperationPolicy(
                    operation="current",
                    sensitivity="personal",
                    fields=tuple(
                        ContextFieldPolicy(field=f, sensitivity="personal")
                        for f in type(p.payload).model_fields
                    ),
                ),
            ),
        )
        for p in providers
    )
    definition = ApplicationDefinition(
        application_id=APP,
        display_name="Synthetic fifth app",
        workspace_kind="required",
        memory_namespace=APP,
        context_provider_ids=tuple(p.spec.provider_id for p in providers),
        context_policy=policy.model_copy(
            update={
                "version": "fifth-policy-v1",
                "provider_policies": policy.provider_policies + policies,
                "sidecar": ApplicationSidecarPolicy(draft_insert_target_ids=("fifth.composer",)),
            }
        ),
    )
    application_catalog = ApplicationContributionCatalog()
    application_catalog.register(
        "synthetic-fifth",
        lambda: ApplicationContribution(
            definitions=(definition,),
            capabilities=tuple(
                CapabilityRegistration(
                    capability_id=p.spec.provider_id, kind="context_provider", available=True
                )
                for p in providers
            ),
            workspace_authorizers={APP: authority},
        ),
    )
    rules = tuple(
        ContextPlanningRule(
            rule_id=p.spec.provider_id + ":v1",
            category=p.reference.entity_type,
            phrases=("selected context",),
            provider_id=p.spec.provider_id,
            operation="current",
            fields=tuple(type(p.payload).model_fields),
            max_tokens=512,
            use_candidate_entities=True,
            require_candidate_entities=True,
            candidate_entity_types=(p.reference.entity_type,),
            explanation="Read selected typed context.",
        )
        for p in providers
    )
    catalog = ContextRuntimeContributionCatalog()
    catalog.register(
        "synthetic-fifth",
        lambda _: ContextRuntimeContribution(
            {p.spec.provider_id: p for p in providers},
            rules,
            (authority,),
        ),
    )
    app = create_app(
        application_catalog=application_catalog,
        context_runtime_catalog=catalog,
    )
    config = Settings(
        _env_file=None,
        ai_provider="fake",
        ai_model="synthetic",
        app_environment="test",
        external_turn_acceptance_enabled=True,
    )
    app.dependency_overrides.update(
        {
            get_settings: lambda: config,
            get_summary_repository: InMemorySummaryRepository,
            get_global_profile_repository: lambda: None,
            get_message_repository: lambda: None,
            get_context_research_repository: lambda: None,
            get_provider_usage_accounting: lambda: None,
        }
    )
    monkeypatch.setattr("personal_ai.main.validate_startup_configuration", lambda: None)
    monkeypatch.setattr("personal_ai.main.close_persistence_clients", lambda: None)

    # conftest substitutes only startup's empty retained mutation inventory.
    @app.post("/probe")
    def probe(
        body: dict,
        context=Depends(get_application_context),  # noqa: B008
        assembler=Depends(get_context_assembler),  # noqa: B008
        external=Depends(get_external_context_assembler),  # noqa: B008
    ):
        assembler.counter = EstimatedTokenCounter()
        pending = Message(
            id=uuid4(),
            conversation_id=uuid4(),
            role="user",
            status="completed",
            content="Use selected context",
            created_at=datetime.now(UTC),
            owner_id=context.scope.owner_id,
            application_id=APP,
            workspace_id=SPACE,
        )
        refs = tuple(p.reference for p in providers)
        launch = ApplicationLaunchContext(
            application_id=APP,
            workspace_id=SPACE,
            entity_refs=refs,
            conversation_id=str(pending.conversation_id),
            view_id="fifth.record",
        )
        launch.validate_for(context.scope, pending.conversation_id)
        plan = assembler.plan_context("Use selected context", context, candidate_entities=refs)
        try:
            if body:
                selection = ContextSelection(
                    provider_id=providers[0].spec.provider_id,
                    operation="current",
                    fields=("title",),
                    entity_refs=(providers[0].reference.model_copy(update=body),),
                )
                plan = assembler.plan_context(
                    "Use selected context", context, explicit_context_selections=(selection,)
                )
            result = assembler.assemble(
                (),
                pending,
                refresh=False,
                application_context=context,
                context_plan=plan,
                emit_manifest=False,
            )
            return {
                "providers": [i.provider_id for i in result.source_items],
                "shared": assembler.context_planner is external.context_planner,
                "dependencies": sum(len(i.permission_dependencies) for i in result.source_items),
                "classes": [type(i.payload).__name__ for i in result.source_items],
            }
        except ContextPreparationError as error:
            return {"denied": error.code}

    return app, providers, authority


def test_fifth_app_startup_two_typed_providers_and_negative_scope(monkeypatch):
    app, providers, authority = fifth_app(monkeypatch)
    headers = {"x-application-id": APP, "x-workspace-id": SPACE}
    with TestClient(app) as client:
        response = client.post("/probe", json={}, headers=headers)
        assert response.status_code == 200, response.text
        result = response.json()
        assert set(result["providers"]) == {p.spec.provider_id for p in providers}
        assert result["shared"] and result["dependencies"] == 2
        assert set(result["classes"]) == {"RecordPayload", "ConstraintPayload"}
        options = client.get("/v1/conversations/execution-options", headers=headers).json()
        assert options["sidecar"]["draft_insert_target_ids"] == ["fifth.composer"]
        assert options["sidecar"]["mutation_operations"] == []
        assert options["modes"] == ["automatic"]
        for body in ({"application_id": "finance"}, {"workspace_id": "foreign-space"}):
            calls = [p.calls for p in providers]
            result = client.post("/probe", json=body, headers=headers).json()
            assert result["denied"] == "context_cross_application_denied"
            assert [p.calls for p in providers] == calls
        assert (
            client.post("/probe", json={}, headers={"x-application-id": APP}).json()["error"][
                "code"
            ]
            == "application_workspace_required"
        )
        denied = client.post(
            "/probe",
            json={},
            headers={**headers, "x-workspace-id": "unregistered-workspace"},
        )
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "workspace_not_authorized"
        authority.current = False
        calls = [p.calls for p in providers]
        result = client.post("/probe", json={}, headers=headers).json()
        assert not result.get("providers")
        assert [p.calls for p in providers] == calls

    # The same production app factory keeps a required-workspace registration closed
    # when the contribution omits a membership authority.
    no_authority_catalog = ApplicationContributionCatalog(
        (
            (
                "synthetic-fifth",
                lambda: ApplicationContribution(
                    definitions=(app.state.application_registry.get(APP),),
                    capabilities=tuple(
                        CapabilityRegistration(
                            capability_id=p.spec.provider_id,
                            kind="context_provider",
                            available=True,
                        )
                        for p in providers
                    ),
                ),
            ),
        )
    )
    no_authority_app = create_app(
        application_catalog=no_authority_catalog,
        context_runtime_catalog=app.state.context_runtime_catalog,
    )
    no_authority_app.dependency_overrides.update(app.dependency_overrides)
    with TestClient(no_authority_app) as client:
        denied = client.get("/v1/conversations/execution-options", headers=headers)
        assert denied.status_code == 403
        assert denied.json()["error"]["code"] == "workspace_not_authorized"


def test_account_cost_identity_and_exhaustion_through_production_factory(monkeypatch):
    profiles = [
        _profile(
            f"same:{account}",
            provider_id="synthetic-provider",
            model_id="same-model",
            account_scope_id=account,
            credential_scope_id="credential:" + account,
            quota_buckets=(_bucket("quota:" + account, authority_scope_id=account),),
        )
        for account in ("account-a", "account-b")
    ]
    for mode, cost in (
        ("STRICT_FREE", "USER_BILLED"),
        ("STRICT_FREE", "UNKNOWN"),
        ("EXPLICIT_BYOK", "USER_BILLED"),
    ):
        profiles.append(
            _profile(
                f"same:{mode}:{cost}",
                provider_id="synthetic-provider",
                model_id="same-model",
                execution_mode=mode,
                cost_class=cost,
                strict_free_enabled=False,
                tier_verified=False,
                billing_owner="unknown",
                quota_buckets=(_bucket(f"quota:{mode}:{cost}"),),
            )
        )
    profiles.append(plan_profile())
    profiles.append(
        _profile("same:explicit").model_copy(
            update={
                "access_policy": ProviderAccessPolicy(
                    selection_mode="explicit_only", automation_eligible=False
                )
            }
        )
    )
    f, repository, usage = factory(monkeypatch, profiles)
    monkeypatch.setattr("personal_ai.api.dependencies.persistence_factory", lambda _: f)
    service = get_routing_decision_service(settings(), Authorization())
    decision = service.route(owner_id="owner", scope=SCOPE, task=task(), request=request())
    assert {c.endpoint.endpoint_profile_id for c in decision.strategy_view().candidates} == {
        "same:account-a",
        "same:account-b",
    }
    assert profiles[0].provider_id == profiles[1].provider_id
    assert profiles[0].model_id == profiles[1].model_id
    assert profiles[0].account_scope_id != profiles[1].account_scope_id
    assert profiles[0].credential_scope_id != profiles[1].credential_scope_id
    assert profiles[0].quota_buckets != profiles[1].quota_buckets
    usage.exhausted = True
    depleted = service.route(
        owner_id="owner",
        scope=SCOPE,
        task=task(),
        request=request().model_copy(update={"request_id": "exhausted"}),
    )
    assert depleted.selected is None and not depleted.strategy_view().candidates
    assert not repository.attempts and usage.reserve_calls == 0


def test_provider_task_evaluation_and_validator_use_production_routing_factory(monkeypatch):
    from tests.test_cascade_phase24 import (
        test_custom_domain_validator_can_register_without_coordinator_changes as validate_cascade,
    )
    from tests.test_provider_matrix import _matrix

    runner, evaluation_repo, _, executor, profiles, fixtures, task_profile = _matrix()
    f, observations, usage = factory(monkeypatch, profiles)
    runner.routing_service = f.routing_service(
        settings(),
        authorization=Authorization(),
        evaluation_quality_authority=evaluation_repo,
    )
    summary, cases, quality = runner.run(
        evaluation_run_id=uuid4(),
        fixtures=fixtures,
        task=task_profile,
        policy_version=fixtures[0].policy_version,
        single_provider_baseline=profiles[0].ref,
    )
    assert summary.synthetic_cases == len(fixtures) * 4
    assert (
        "extension:generic" in executor.prepared
        and "extension:paid-blocked" not in executor.prepared
    )
    assert not quality and len(observations.attempts) == summary.synthetic_cases
    assert all(case.metrics.overall_score == 1 for case in cases if case.metrics)
    # The existing validator conformance fixture supplies only transport/storage contracts;
    # the production factory supplies the router consumed by the shared cascade coordinator.
    endpoints = [
        _profile(name, quota_buckets=(_bucket("shared"),)) for name in ("endpoint-a", "endpoint-b")
    ]
    f, repo, usage = factory(monkeypatch, endpoints)
    routed = f.routing_service(settings(), authorization=Authorization())
    validate_cascade((routed, repo, usage, Authorization()))


def _assembler(env, monkeypatch):
    class Factory:
        def memory_repository(self):
            return env["memories"]

        def memory_lifecycle_repository(self, memories, messages):
            return env["lifecycle"]

    monkeypatch.setattr("personal_ai.api.dependencies.persistence_factory", lambda _: Factory())
    registry = default_application_registry()
    assembler = get_context_assembler(
        EMPTY_CONTEXT_RUNTIME_REGISTRY,
        env["settings"],
        InMemorySummaryRepository(),
        None,
        None,
        None,
        env["messages"],
        registry,
    )
    assembler.counter = EstimatedTokenCounter()
    return assembler, registry


def _percentile(values, fraction):
    return sorted(values)[max(0, int(len(values) * fraction + 0.999) - 1)]


@pytest.mark.anyio
async def test_combined_heldout_pipeline_measurements_and_deterministic_rollback(
    monkeypatch,
    record_property,
):
    cases, frozen, _ = load_configuration()
    rows = []
    # Use the independent frozen held-out corpus, with paired control/candidate/rollback.
    for case in cases:
        if (
            case["expected"] != "completed"
            or case.get("adapter_error")
            or case.get("invalid_output")
        ):
            continue
        for variant in ("baseline", "combined", "rollback"):
            started = perf_counter()
            search_variant = "qualifier-v1" if variant == "combined" else "literal-extractive-v1"
            # Qualifier rewrite and extractive packing use the canonical research service.
            research_observations = {}
            search, session = await measure(
                case,
                search_variant,
                packing_variant=("compact-extractive-v1" if variant == "combined" else None),
                observations=research_observations,
            )
            env = environment("compact" if variant == "combined" else "fixed")
            env["settings"].memory_max_context_tokens = 4096
            embeddings = EmbeddingObservations(env["embedder"])
            env["embedder"] = env["worker"].embedder = embeddings
            apply_fixture(env)
            assembler, registry = _assembler(env, monkeypatch)
            count_calls = []
            original_count = assembler.counter.count

            def observed_count(messages, calls=count_calls, count=original_count):
                calls.append(1)
                return count(messages)

            assembler.counter.count = observed_count
            registration = registry.registration("personal_ai")
            with memory_scope() as scope:
                context = ApplicationContextRequest(
                    definition=registration.definition,
                    scope=scope,
                    context_provider_capabilities=registration.context_providers,
                )
                retrieval = retriever(env).retrieve(
                    "local", case["question"], [], application_context=context
                )
                selections = (
                    ContextSelection(
                        provider_id="ai_memory",
                        operation="search",
                        fields=("content",),
                        max_tokens=4096,
                    ),
                    ContextSelection(
                        provider_id="external_research",
                        operation="search",
                        fields=("passage", "observed_at", "expires_at"),
                        max_tokens=4096,
                    ),
                )
                plan = assembler.plan_context(
                    case["question"],
                    context,
                    explicit_context_selections=selections,
                )
                if variant == "combined":
                    envelope = assembler.planning_envelope(
                        plan, context, deadline=datetime.now(UTC) + timedelta(seconds=1)
                    )
                    # Current Phase 32 has no assisted model call. Invalid proposal falls back safely.
                    plan = assembler.validate_context_proposal(
                        envelope,
                        {
                            "baseline_digest": envelope.request.baseline_digest,
                            "choices": [
                                {
                                    "choice_id": "choice-0",
                                    "fields": ["forbidden"],
                                    "max_results": 1,
                                    "max_bytes": 1024,
                                    "max_tokens": 256,
                                }
                            ],
                        },
                        context,
                    )
                    assert plan.planning_trace.baseline_digest == plan.planning_trace.final_digest
                selected_evidence = set(session.selection.evidence_ids)
                observations = tuple(session.observations)
                pending = env["pending"].model_copy(update={"content": case["question"]})
                assembled = assembler.assemble(
                    (),
                    pending,
                    refresh=False,
                    retrieval=retrieval,
                    application_context=context,
                    context_plan=plan,
                    emit_manifest=False,
                    evidence_records=tuple(
                        (e, observations) for e in session.evidence if e.id in selected_evidence
                    ),
                    clock=lambda session=session: session.updated_at,
                )
                assert assembled.selected_memory_ids, (
                    retrieval.diagnostics,
                    assembled.excluded_memories,
                )
                assert any(i.source_class == "external_research" for i in assembled.source_items)
                external_items = tuple(
                    item
                    for item in assembled.source_items
                    if item.source_class == "external_research"
                )
                selected_evidence_ids = {str(identity) for identity in selected_evidence}
                assembled_evidence_ids = {item.item_id for item in external_items}
                post_builder_support = len(selected_evidence_ids & assembled_evidence_ids) / max(
                    1, len(selected_evidence_ids)
                )
                allowed_providers = {"ai_memory", "external_research"}
                authority_confusion = sum(
                    item.owner_id != context.scope.owner_id
                    or item.application_id != context.scope.application_id
                    or item.workspace_id != context.scope.workspace_id
                    or item.provider_id not in allowed_providers
                    or (
                        item.source_class == "external_research"
                        and item.item_id not in selected_evidence_ids
                    )
                    for item in assembled.source_items
                )
                item_reports = {item.item_id: item for item in assembled.manifest.items}
                dependency_loss = sum(
                    bool(item.permission_dependencies)
                    and not any(
                        dependency.kind in {"permission", "federation_grant"}
                        for dependency in item_reports[item.item_id].dependency_versions
                    )
                    for item in assembled.source_items
                    if item.item_id in item_reports
                )
                assert post_builder_support == 1.0
                assert authority_confusion == 0 and dependency_loss == 0
                if case["name"] == "conflicting-sources":
                    conflict_urls = {ref.uri for item in external_items for ref in item.source_refs}
                    assert {"https://example.org/blue", "https://example.net/red"} <= conflict_urls
            f, repository, usage = factory(
                monkeypatch,
                [
                    _profile(
                        "allowed",
                        context_limit_tokens=16384,
                        data_use_policy=DataUsePolicy(
                            status="approved",
                            max_sensitivity="sensitive",
                            policy_reference="policy:synthetic-v1",
                        ),
                    )
                ],
            )
            monkeypatch.setattr(
                "personal_ai.api.dependencies.persistence_factory", lambda _, f=f: f
            )
            auth = Authorization()
            router = get_routing_decision_service(settings(), auth)
            # Route the actual server-assembled input facts, with its owner and
            # sensitivity, rather than a second unrelated small fixture request.
            base = request()
            facts = base.model_copy(
                update={
                    "request_id": case["name"] + ":" + variant,
                    "requirements": base.requirements.model_copy(
                        update={
                            "input_tokens": assembled.budget.selected_total,
                            "sensitivity": assembled.manifest.effective_sensitivity,
                        }
                    ),
                    "policy_version": context.definition.context_policy.version,
                    "prepared_context_tokens": assembled.budget.selected_total,
                    "count_source": assembler.counter.counter_version,
                    "count_confidence": "estimated",
                    "source_reference_sha256s": tuple(
                        sorted(
                            {
                                ref.fingerprint
                                for item in assembled.source_items
                                for ref in item.source_refs
                                if ref.fingerprint is not None
                            }
                        )
                    ),
                }
            )
            decision = router.route(
                owner_id=context.scope.owner_id, scope=SCOPE, task=task(), request=facts
            )
            assert (
                decision.selected
                and decision.request.prepared_context_tokens == assembled.budget.selected_total
            )
            if variant == "combined":
                shadow = artifact(decision.strategy_view())
                router = get_routing_decision_service(
                    settings(
                        routing_shadow_enabled=True, routing_shadow_artifact=shadow.model_dump()
                    ),
                    auth,
                )
                decision = router.route(
                    owner_id=context.scope.owner_id,
                    scope=SCOPE,
                    task=task(),
                    request=facts.model_copy(update={"request_id": facts.request_id + ":shadow"}),
                )
                assert decision.shadow is not None
            assert usage.reserve_calls == 0 and not repository.attempts
            assert search.exact_support == 1 and search.constraint_retention == 1
            rows.append(
                {
                    "fixture": case["name"],
                    "variant": variant,
                    "logical_calls": {
                        "planner": 0,
                        "search": search.calls,
                        "synthesis": search.synthesis_invocations,
                        "research_count": search.token_count_invocations,
                        "context_count": len(count_calls),
                        "memory_query_embedding": sum(q for q, _ in embeddings.calls),
                        "memory_maintenance_embedding": sum(not q for q, _ in embeddings.calls),
                        "routing_decisions": 2 if variant == "combined" else 1,
                        "routing_dispatch": 0,
                    },
                    "research_token_estimate": sum(research_observations.values()),
                    "embedding_input_token_estimate": embeddings.token_estimate,
                    "assembled_token_estimate": assembled.budget.selected_total,
                    "total_token_estimate": sum(research_observations.values())
                    + embeddings.token_estimate
                    + assembled.budget.selected_total,
                    "exact_evidence_support": search.exact_support,
                    "post_builder_exact_support": post_builder_support,
                    "post_builder_authority_confusion": authority_confusion,
                    "post_builder_permission_dependency_loss": dependency_loss,
                    "post_builder_conflict_visible": case["name"] != "conflicting-sources"
                    or len(external_items) >= 2,
                    "context_source_count": len(assembled.source_items),
                    "supported_answer_quality_live": None,
                    "context_omission_live": None,
                    "context_irrelevance_live": None,
                    "authority_confusion_live": None,
                    "mutation_correctness_live": None,
                    "physical_external_attempts": 0,
                    "provider_quota": None,
                    "postgres_operations": None,
                    "dynamodb_operations": None,
                    "gcs_operations": None,
                    "strict_free_headroom": None,
                    "latency_ms": (perf_counter() - started) * 1000,
                }
            )
    assert rows
    for name in {r["fixture"] for r in rows}:
        control, candidate, rollback = [r for r in rows if r["fixture"] == name]
        assert control["total_token_estimate"] == rollback["total_token_estimate"]
        assert control["logical_calls"] == rollback["logical_calls"]
        assert candidate["exact_evidence_support"] == control["exact_evidence_support"]
    assert all(
        sum(r["logical_calls"].values()) <= THRESHOLDS["maximum_logical_calls_per_fixture"]
        for r in rows
    )
    assert all(
        r["assembled_token_estimate"] <= THRESHOLDS["maximum_context_token_estimate"] for r in rows
    )
    assert all(r["latency_ms"] < THRESHOLDS["maximum_synthetic_pipeline_ms"] for r in rows)
    latency_by_variant = {
        variant: {
            "p50_ms": median(r["latency_ms"] for r in rows if r["variant"] == variant),
            "p95_ms": _percentile([r["latency_ms"] for r in rows if r["variant"] == variant], 0.95),
        }
        for variant in ("baseline", "combined", "rollback")
    }
    totals = {
        v: sum(r["total_token_estimate"] for r in rows if r["variant"] == v)
        for v in ("baseline", "combined", "rollback")
    }
    record_property(
        "phase36_metrics",
        json.dumps(
            {
                "kind": "combined-implemented-paths-v1",
                "evidence_class": "offline",
                "corpus": "retrieval-heldout-v2",
                "corpus_sha256": frozen["fixture_sha256"],
                "rows": rows,
                "latency_by_variant": latency_by_variant,
                "token_estimate_totals": totals,
                "aggregate_saving_fraction": 1 - totals["combined"] / totals["baseline"],
                "promotion": "not_promoted",
                "promoted_coverage": [],
                "missing": [
                    "live whole-workflow quality/timing",
                    "native-store operations/storage",
                    "physical quota/headroom",
                    "assisted planner implementation",
                ],
            }
        ),
    )


@pytest.mark.anyio
async def test_bounded_accumulation_revocation_and_artifact_cleanup(monkeypatch, record_property):
    from personal_ai.agents.research.repositories import InMemoryResearchRepository
    from personal_ai.artifacts.contracts import ArtifactUnavailable
    from personal_ai.artifacts.local import (
        InMemoryArtifactMetadataRepository,
        InMemoryArtifactStore,
    )
    from personal_ai.artifacts.service import ArtifactService
    from personal_ai.context.contracts import fingerprint
    from personal_ai.evaluation.planning_fixtures import synthetic_federation
    from personal_ai.memory.contracts import MemoryCandidate, identity
    from tests.test_federation import prepare

    env = environment("consolidated")
    apply_fixture(env)
    clock = [datetime.now(UTC)]
    metadata = InMemoryArtifactMetadataRepository(clock=lambda: clock[0], max_objects=32)
    store = InMemoryArtifactStore()
    service = ArtifactService(metadata, store, clock=lambda: clock[0])
    f, repo, usage = factory(monkeypatch)
    router = f.routing_service(settings(), authorization=Authorization())
    federation = synthetic_federation()
    research = InMemoryResearchRepository()
    research_case = load_configuration()[0][0]
    base = next(iter(env["records"].values()))
    previous = env["completed"].id
    derived_items, refs, samples = [], [], []
    iterations = int(THRESHOLDS["soak_iterations"])
    for index in range(iterations):
        started = perf_counter()
        views_before = len(env["memories"].derived_records)
        jobs_before = len(env["lifecycle"].jobs)
        user = env["pending"].model_copy(
            update={
                "id": uuid4(),
                "content": base.content,
                "parent_message_id": previous,
                "created_at": env["pending"].created_at + timedelta(seconds=2 * index + 1),
            }
        )
        assistant = env["completed"].model_copy(
            update={
                "id": uuid4(),
                "parent_message_id": user.id,
                "created_at": user.created_at + timedelta(seconds=1),
            }
        )
        env["messages"].create(user)
        env["messages"].create(assistant)
        previous = assistant.id
        candidate = MemoryCandidate(
            memory_type=base.memory_type,
            content=base.content,
            confidence=base.confidence,
            source_message_ids=(user.id,),
            rationale_code=base.rationale_code,
        )
        source_hash = fingerprint([user])
        memory = base.model_copy(
            update={
                "id": identity("local", source_hash, candidate),
                "source_message_ids": (user.id,),
                "source_fingerprint": source_hash,
                "source_conversation_id": user.conversation_id,
                "source_turn_id": assistant.id,
            }
        )
        env["memories"].create(memory)
        env["coordinator"].after_completed(assistant)
        for job in list(env["lifecycle"].jobs.values()):
            assert env["worker"].process(job.id) == "completed"
        _, session = await measure(research_case, "literal-extractive-v1")
        research.create(session)
        with memory_scope():
            retrieval = retriever(env).retrieve("local", "query", [])
            assert retrieval.selected
        derived_items.append(prepare(federation))
        decision = router.route(
            owner_id="owner",
            scope=SCOPE,
            task=task(),
            request=request().model_copy(update={"request_id": "soak:" + str(index)}),
        )
        assert decision.selected
        assert (
            router.route(owner_id="owner", scope=SCOPE, task=task(), request=decision.request)
            == decision
        )
        refs.append(
            service.write(
                {"case_id": str(index), "score": 1},
                owner_id="owner",
                scope=SCOPE,
                kind="evaluation",
                identity="soak:" + str(index),
                schema_version="soak-v1",
                required=True,
            )
        )
        samples.append(
            {
                "iteration": index + 1,
                "timeline_records": len(env["messages"]._messages),
                "original_memory_records": len(env["memories"].records),
                "derived_memory_records": len(env["memories"].derived_records),
                "derived_views_created": len(env["memories"].derived_records) - views_before,
                "maintenance_jobs": len(env["lifecycle"].jobs),
                "maintenance_jobs_created": len(env["lifecycle"].jobs) - jobs_before,
                "routing_records": len(repo.records),
                "research_sessions": len(research.sessions),
                "research_metadata_bytes": sum(
                    len(s.model_dump_json().encode()) for s in research.sessions.values()
                ),
                "artifact_objects": len(store.objects),
                "artifact_bytes": sum(len(body) for _, body in store.objects.values()),
                "artifact_operations": metadata.operations,
                "latency_ms": (perf_counter() - started) * 1000,
            }
        )
    assert samples[-1]["timeline_records"] - samples[0]["timeline_records"] == 62
    assert samples[-1]["original_memory_records"] - samples[0]["original_memory_records"] == 31
    # The owning scheduler discovers bounded groups of at most four compatible originals.
    assert all(
        s["derived_memory_records"]
        <= THRESHOLDS["maximum_derived_views_per_soak_turn"] * s["iteration"] + 1
        for s in samples
    )
    assert max(s["maintenance_jobs"] for s in samples) <= (
        THRESHOLDS["maximum_maintenance_jobs_per_soak_turn"] * iterations
    )
    assert len(research.sessions) == 32
    assert len(repo.records) == len(store.objects) == 32 and not repo.attempts
    cached = retriever(env).retrieve("local", "query", [])
    degradation = {}
    with monkeypatch.context() as fault:

        def unavailable(*args, **kwargs):
            raise OSError("synthetic service outage")

        fault.setattr(env["lifecycle"], "get_state", unavailable)
        denied = retriever(env).retrieve("local", "query", [])
        assert not denied.selected and denied.diagnostics == ("retrieval_failed",)
        degradation["memory_database_outage"] = "empty advisory result; no cached reuse"
        fault.setattr(repo, "transaction", unavailable)
        with pytest.raises(OSError):
            router.route(
                owner_id="owner",
                scope=SCOPE,
                task=task(),
                request=request().model_copy(update={"request_id": "soak:database-outage"}),
            )
        assert not repo.attempts and usage.reserve_calls == 0
        degradation["routing_database_outage"] = "explicit error; no dispatch or reservation"
        fault.setattr(store, "read", unavailable)
        with pytest.raises(OSError):
            service.read(refs[0].artifact_id, owner_id="owner", scope=SCOPE)
        assert metadata.records[refs[0].artifact_id].status == "missing"
        degradation["artifact_network_outage"] = "explicit error; missing ref remains recoverable"
    search_failure, failed_session = await measure(
        {**research_case, "adapter_error": "search_timeout", "expected": "failed"},
        "literal-extractive-v1",
    )
    assert failed_session.state == "failed" and failed_session.answer is None
    assert search_failure.calls == 1 and search_failure.synthesis_invocations == 0
    degradation["provider_network_outage"] = "one logical search; no synthesis or retry"
    for record in env["memories"].records.values():
        change(env, record, "forgotten")
    assembler, _registry = _assembler(env, monkeypatch)
    with memory_scope():
        result = assembler.assemble(
            (), env["pending"], refresh=False, retrieval=cached, emit_manifest=False
        )
        assert not result.selected_memory_ids
    federation["authority"].revoke(
        federation["principal"], federation["grant"].grant_id, expected_revision=1
    )
    validator = federation["runtime"].permission_revalidators[-1]
    assert all(
        not all(validator.is_current(d) for d in item.permission_dependencies)
        for item in derived_items
    )
    metadata.fences.add("owner")
    for ref in refs:
        with pytest.raises(ArtifactUnavailable):
            service.read(ref.artifact_id, owner_id="owner", scope=SCOPE)
    # A body deletion outage after the owner fence must retain the original
    # generation/metadata for retry, including bodies from accumulated state.
    original_delete = store.delete
    delete_calls = []
    with monkeypatch.context() as fault:

        def fail_first_delete(key, generation):
            delete_calls.append((key, generation))
            if len(delete_calls) == 1:
                raise OSError("synthetic deletion interruption")
            return original_delete(key, generation)

        fault.setattr(store, "delete", fail_first_delete)
        partial = service.reconcile(limit=32)
        assert partial["failed"] == 1 and partial["deleted"] == 31
        assert len(store.objects) == 1
    assert service.reconcile(limit=32)["deleted"] == 1
    degradation["partial_artifact_cleanup"] = (
        "31 deleted / 1 retained; original generation retry cleaned 1"
    )
    assert not store.objects and all(r.status == "deleted" for r in metadata.records.values())
    usage.exhausted = True
    assert (
        router.route(
            owner_id="owner",
            scope=SCOPE,
            task=task(),
            request=request().model_copy(update={"request_id": "soak:exhausted"}),
        ).selected
        is None
    )
    record_property(
        "phase36_metrics",
        json.dumps(
            {
                "kind": "bounded-soak-v1",
                "evidence_class": "offline",
                "iterations": 32,
                "samples": samples,
                "objects_after_cleanup": len(store.objects),
                "revoked_cached_memory_selected": len(result.selected_memory_ids),
                "physical_attempts": len(repo.attempts),
                "degradation": degradation,
                "native_store_resources": None,
                "physical_owner_deletion": "original Phase 9 blocker",
            }
        ),
    )


def test_retired_runtime_and_migration_ownership():
    root = Path(__file__).resolve().parents[2]
    factory_source = (root / "backend/src/personal_ai/persistence/factory.py").read_text()
    assert (
        "DynamoDBMessageRepository" in factory_source
        and "PostgresMemoryRepository" in factory_source
    )
    assert (
        "PostgresArtifactMetadataRepository" in factory_source
        and "PrivateGCSArtifactStore" in factory_source
    )
    assert "firestore" not in factory_source.casefold()
    assert "google-cloud-firestore" not in (root / "backend/pyproject.toml").read_text()
    assert not [
        p
        for p in (root / "backend/src/personal_ai").rglob("*firestore*")
        if "__pycache__" not in p.parts
    ]


@pytest.mark.anyio
async def test_iterative_evaluation_checks_typed_domain_envelope():
    from personal_ai.evaluation.iterative_research import (
        _result_record,
        _run_iterative,
        _run_single_pass,
        evaluate,
        load_fixtures,
    )

    assert (await evaluate())["passed"]
    fixture = next(f for f in load_fixtures() if "followup_allowed_domains" in f["expected"])
    baseline = await _run_single_pass(fixture)
    run, session, events, adapter, decisions = await _run_iterative(fixture)
    assert _result_record(fixture, baseline, run, session, events, adapter, decisions)["passed"]
    adapter.calls[-1] = adapter.calls[-1].model_copy(update={"allowed_domains": ()})
    assert not _result_record(fixture, baseline, run, session, events, adapter, decisions)["passed"]

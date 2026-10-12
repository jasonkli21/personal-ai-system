"""Finance context stays bounded, selected, sensitive, and on shared context seams."""

from datetime import UTC, datetime, timedelta
from time import monotonic
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.applications.registry import default_application_registry
from personal_ai.auth.scope import ApplicationScope, RequestScope
from personal_ai.context.assembler import ContextAssembler
from personal_ai.context.authorization import (
    apply_item_policy,
    make_context_inference_context,
)
from personal_ai.context.builder import ContextBuildItem
from personal_ai.context.finance import (
    FINANCE_ACCOUNT_PROVIDER_ID,
    FINANCE_BUDGET_EXPORT_PROVIDER_ID,
    FINANCE_EVIDENCE_PROVIDER_ID,
    FINANCE_PORTFOLIO_PROVIDER_ID,
    FINANCE_RESEARCH_PROVIDER_ID,
    FinanceBudgetFederationAdapter,
    FinanceContextHTTPClient,
    FinanceContextPermissionRevalidator,
    FinanceContextProvider,
    FinanceContextProviderFactory,
    FinanceContextReadRequest,
    FinanceContextReadResponse,
    FinanceContextRecord,
    FinanceContextSemanticValue,
    configured_finance_context_contribution,
    finance_context_planning_rules,
)
from personal_ai.context.finance import (
    FinanceContextEntityReference as FinanceWireEntityReference,
)
from personal_ai.context.planner import ContextPlanner
from personal_ai.context.providers import (
    ContextEntityReference,
    ContextFieldSensitivity,
    ContextPermissionDependency,
    ContextPreparationError,
    ContextProviderCoordinator,
    ContextProviderError,
    ContextProviderInputs,
    ContextSelection,
    ContextSourceReference,
)
from personal_ai.context.runtime import (
    ContextPermissionRevalidatorRegistry,
    ContextRuntimeContribution,
    compose_context_runtime,
)
from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.contracts.federation import FederationSelection
from personal_ai.entities import Message, MessageRole, MessageStatus
from personal_ai.federation.contracts import FederationGrant, FederationGrantIntent
from personal_ai.routing import (
    EndpointCandidateRequirements,
    EndpointRegistry,
    build_initial_endpoint_profiles,
)
from personal_ai.settings import Settings


def _record(
    *,
    entity_type: str = "account",
    entity_id: str | None = None,
    source_class: str = "domain_current",
    field: str = "account_summary",
) -> FinanceContextRecord:
    selected_id = entity_id or str(uuid4())
    return FinanceContextRecord(
        entity_type=entity_type,
        entity_id=selected_id,
        source_id=f"finance:{entity_type}:{selected_id}",
        source_version="a" * 64,
        source_class=source_class,
        authority="authoritative" if source_class == "domain_current" else "user_asserted",
        observed_at=datetime(2026, 10, 11, 12, tzinfo=UTC),
        sensitivity="restricted",
        payload={
            field: {
                "currency": FinanceContextSemanticValue(
                    semantic_class="observed",
                    value="USD",
                    state="known",
                    unit="currency",
                    currency="USD",
                    source_identity="finance.account",
                    source_version="source-v1",
                    evidence_refs=(selected_id,),
                    quality="canonical",
                    authority="authoritative",
                    sensitivity="restricted",
                )
            }
        },
        source_refs=(
            ContextSourceReference(
                kind="record",
                reference_id=selected_id,
                fingerprint="f" * 64,
            ),
        ),
        permission_dependencies=(
            ContextPermissionDependency(
                permission_id=f"finance_context_read:{entity_type}:{selected_id}",
                version="a" * 64,
                purpose="Recheck the selected Finance record.",
            ),
        ),
        field_sensitivity=(ContextFieldSensitivity(field=field, sensitivity="restricted"),),
    )


def _selection(
    provider_id: str = FINANCE_ACCOUNT_PROVIDER_ID,
    *,
    entity_type: str = "account",
    entity_id: str | None = None,
    fields: tuple[str, ...] = ("account_summary",),
) -> ContextSelection:
    return ContextSelection(
        provider_id=provider_id,
        operation="current",
        fields=fields,
        entity_refs=(
            ContextEntityReference(
                entity_type=entity_type,
                entity_id=entity_id or str(uuid4()),
                application_id="finance",
                workspace_id=None,
            ),
        ),
        max_results=4,
        max_bytes=12_288,
        timeout_seconds=2,
    )


def _scope() -> RequestScope:
    return RequestScope(
        owner_id="verified-owner",
        request_id="finance-context-test",
        application_id="finance",
        workspace_id=None,
    )


def _budget_record(entity_id: str) -> FinanceContextRecord:
    version = "b" * 64
    values = {
        key: FinanceContextSemanticValue(
            semantic_class="observed",
            value=value,
            state="known",
            unit="currency_amount" if key == "amount" else None,
            currency="USD" if key == "amount" else None,
            as_of="2026-11",
            source_identity="finance.monthly_discretionary_budget",
            source_version=version,
            evidence_refs=(entity_id,),
            quality="owner_entered",
            authority="user_asserted",
            sensitivity="restricted",
        )
        for key, value in {
            "amount": "850.50",
            "currency": "USD",
            "period": "2026-11",
        }.items()
    }
    return FinanceContextRecord(
        entity_type="discretionary_budget",
        entity_id=entity_id,
        source_id=f"finance:monthly_discretionary_budget:{entity_id}",
        source_version=version,
        source_class="domain_current",
        authority="user_asserted",
        observed_at=datetime.now(UTC),
        effective_at=datetime(2026, 11, 1, tzinfo=UTC),
        sensitivity="restricted",
        payload={"discretionary_budget": values},
        source_refs=(
            ContextSourceReference(
                kind="record", reference_id=entity_id, fingerprint="c" * 64
            ),
        ),
        permission_dependencies=(
            ContextPermissionDependency(
                permission_id=f"finance_context_read:discretionary_budget:{entity_id}",
                version=version,
                purpose="shopping_discretionary_budget",
            ),
        ),
        field_sensitivity=tuple(
            ContextFieldSensitivity(field=field, sensitivity="restricted")
            for field in ("amount", "currency", "period")
        ),
    )


class FakeFinanceClient:
    def __init__(self, response: FinanceContextReadResponse) -> None:
        self.response = response
        self.requests: list[FinanceContextReadRequest] = []

    def read(self, request: FinanceContextReadRequest, *, deadline: float):
        assert deadline > monotonic()
        self.requests.append(request)
        return self.response


def test_read_request_uses_finance_wire_refs_without_owner_or_workspace_authority() -> None:
    reference_id = str(uuid4())
    request = FinanceContextReadRequest(
        operation="current",
        entity_refs=(FinanceWireEntityReference(entity_type="account", entity_id=reference_id),),
        fields=("account_summary",),
        max_results=2,
        max_bytes=4096,
    )

    wire = request.model_dump(mode="json")
    assert wire["entity_refs"] == [{"entity_type": "account", "entity_id": reference_id}]
    assert "owner_id" not in wire
    assert "scope_id" not in wire
    assert "workspace_id" in wire and wire["workspace_id"] is None


def test_http_client_separates_service_and_verified_user_tokens(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    record = _record()
    body = FinanceContextReadResponse(items=(record,)).model_dump_json()
    captured: list[httpx.Request] = []
    service_fetches: list[tuple[str, str]] = []

    def handle(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return httpx.Response(200, content=body, headers={"content-type": "application/json"})

    monkeypatch.setattr(
        "personal_ai.context.finance.current_verified_user_identity_token",
        lambda: "verified-user-id-token",
    )
    client = FinanceContextHTTPClient(
        base_url="https://finance.example.test",
        auth_mode="google_oidc",
        service_audience="https://finance.example.test",
        service_account="personal-ai@project.iam.gserviceaccount.com",
        service_token_fetcher=lambda *, audience, service_account, deadline: (
            service_fetches.append((audience, service_account)) or "service-id-token"
        ),
        transport=httpx.MockTransport(handle),
    )
    request = FinanceContextReadRequest(
        operation="current",
        entity_refs=(
            FinanceWireEntityReference(
                entity_type="account",
                entity_id=record.entity_id,
            ),
        ),
        fields=("account_summary",),
        max_results=1,
        max_bytes=8192,
    )

    result = client.read(request, deadline=monotonic() + 2)

    assert result.items[0].source_version == "a" * 64
    assert service_fetches == [
        ("https://finance.example.test", "personal-ai@project.iam.gserviceaccount.com")
    ]
    assert captured[0].headers["authorization"] == "Bearer service-id-token"
    assert captured[0].headers["x-user-id-token"] == "verified-user-id-token"
    import json

    payload = json.loads(captured[0].content)
    assert payload["entity_refs"] == [{"entity_type": "account", "entity_id": record.entity_id}]
    assert "owner_id" not in payload
    assert len(captured) == 1


def test_http_client_fails_closed_when_service_identity_uses_the_deadline(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from personal_ai.context import finance as finance_module

    now = [100.0]
    deadlines: list[float] = []
    requests: list[httpx.Request] = []

    def fetch_service_token(*, audience: str, service_account: str, deadline: float) -> str:
        assert audience == "https://finance.example.test"
        assert service_account == "personal-ai@project.iam.gserviceaccount.com"
        deadlines.append(deadline)
        now[0] = 101.1
        return "service-id-token"

    monkeypatch.setattr(finance_module, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        finance_module,
        "current_verified_user_identity_token",
        lambda: "verified-user-id-token",
    )
    client = FinanceContextHTTPClient(
        base_url="https://finance.example.test",
        auth_mode="google_oidc",
        service_audience="https://finance.example.test",
        service_account="personal-ai@project.iam.gserviceaccount.com",
        service_token_fetcher=fetch_service_token,
        transport=httpx.MockTransport(
            lambda request: requests.append(request) or httpx.Response(200)
        ),
    )
    request = FinanceContextReadRequest(
        operation="current",
        entity_refs=(FinanceWireEntityReference(entity_type="account", entity_id=str(uuid4())),),
        fields=("account_summary",),
        max_results=1,
        max_bytes=4096,
    )

    with pytest.raises(ContextProviderError):
        client.read(request, deadline=101.0)

    assert deadlines == [101.0]
    assert requests == []


def test_finance_providers_keep_research_truth_in_distinct_source_classes() -> None:
    client = FakeFinanceClient(FinanceContextReadResponse(items=()))
    assert FinanceContextProvider(client, FINANCE_ACCOUNT_PROVIDER_ID).spec.source_class == (
        "domain_current"
    )
    assert FinanceContextProvider(client, FINANCE_PORTFOLIO_PROVIDER_ID).spec.source_class == (
        "domain_current"
    )
    assert FinanceContextProvider(client, FINANCE_RESEARCH_PROVIDER_ID).spec.source_class == (
        "domain_current"
    )
    assert FinanceContextProvider(client, FINANCE_EVIDENCE_PROVIDER_ID).spec.source_class == (
        "external_research"
    )


def test_provider_rejects_implicit_or_incomplete_scope_before_fetch() -> None:
    client = FakeFinanceClient(FinanceContextReadResponse(items=()))
    account_provider = FinanceContextProvider(client, FINANCE_ACCOUNT_PROVIDER_ID)
    broad_selection = _selection(
        entity_type="portfolio",
        entity_id="all_active",
    )
    with pytest.raises(ContextPreparationError, match="broad_scope_unsupported"):
        account_provider.validate_selection(broad_selection, ContextProviderInputs(scope=_scope()))

    portfolio_provider = FinanceContextProvider(client, FINANCE_PORTFOLIO_PROVIDER_ID)
    incomplete_position = _selection(
        FINANCE_PORTFOLIO_PROVIDER_ID,
        entity_type="account",
        fields=("position_summary",),
    )
    with pytest.raises(ContextPreparationError, match="selection_scope_invalid"):
        portfolio_provider.validate_selection(
            incomplete_position, ContextProviderInputs(scope=_scope())
        )


def test_finance_semantics_survive_shared_context_projection_and_policy() -> None:
    record = _record()
    client = FakeFinanceClient(FinanceContextReadResponse(items=(record,)))
    provider = FinanceContextProvider(client, FINANCE_ACCOUNT_PROVIDER_ID)
    selection = _selection(entity_id=record.entity_id)
    scope = _scope()
    provider.validate_selection(selection, ContextProviderInputs(scope=scope))
    (item,) = provider.fetch(selection, scope, deadline=monotonic() + 2)

    registration = default_application_registry().registration("finance")
    context = ApplicationContextRequest(
        definition=registration.definition,
        scope=scope,
        context_provider_capabilities=registration.context_providers,
        tool_capabilities=registration.tools,
    )
    inference = make_context_inference_context(context, (selection,))
    authorized_item = apply_item_policy(context, selection, item)
    build_item = ContextBuildItem.from_context_item(authorized_item)

    assert inference.effective_sensitivity == "restricted"
    assert inference.maximum_sensitivity == "restricted"
    endpoint_profiles = build_initial_endpoint_profiles(
        Settings(ai_provider="gemini", ai_model="fixture-model")
    )
    assessment = EndpointRegistry(endpoint_profiles).candidates(
        EndpointCandidateRequirements(
            sensitivity=inference.effective_sensitivity,
            input_tokens=128,
            output_tokens=64,
        )
    )
    assert not assessment.eligible_profiles
    assert "provider_data_policy_unknown_for_sensitivity" in {
        reason for candidate in assessment.assessments for reason in candidate.rejection_reasons
    }
    assert item.source_class == "domain_current"
    assert item.field_sensitivity[0].sensitivity == "restricted"
    assert '"semantic_class":"observed"' in build_item.content
    assert '"currency":"USD"' in build_item.content
    assert '"source_identity":"finance.account"' in build_item.content
    assert '"sensitivity":"restricted"' in build_item.content
    assert (
        registration.definition.context_policy.sidecar.connected_provider_disclosure.allowed
        is False
    )
    assert (
        registration.definition.context_policy.sidecar.manual_external_disclosure.allowed is False
    )


def test_finance_candidate_flows_through_shared_planner_runtime_and_assembler() -> None:
    record = _record()
    client = FakeFinanceClient(FinanceContextReadResponse(items=(record,)))
    revalidator = FinanceContextPermissionRevalidator(client)
    contribution = ContextRuntimeContribution(
        provider_factories={
            FINANCE_ACCOUNT_PROVIDER_ID: FinanceContextProviderFactory(
                client, FINANCE_ACCOUNT_PROVIDER_ID
            )
        },
        planning_rules=finance_context_planning_rules(),
        permission_revalidators=(revalidator,),
    )
    runtime = compose_context_runtime(contribution)
    coordinator = ContextProviderCoordinator(
        runtime.provider_factories,
        feature_flags={"finance_context_enabled": True},
    )
    registration = default_application_registry().registration("finance")
    scope = _scope()
    application_context = ApplicationContextRequest(
        definition=registration.definition,
        scope=scope,
        context_provider_capabilities=registration.context_providers,
        tool_capabilities=registration.tools,
    )
    candidate = ContextEntityReference(
        entity_type="account",
        entity_id=record.entity_id,
        application_id="finance",
        workspace_id=None,
    )
    planner = ContextPlanner(
        rules=finance_context_planning_rules(),
        include_default_rules=False,
    )
    assembler = ContextAssembler(
        Settings(ai_provider="fake", ai_model="fake-model"),
        FakeTokenCounter(),
        context_provider_coordinator=coordinator,
        permission_revalidator=ContextPermissionRevalidatorRegistry(
            runtime.permission_revalidators
        ),
        context_planner=planner,
    )
    plan = assembler.plan_context(
        "selected account context",
        application_context,
        candidate_entities=(candidate,),
    )
    pending = Message(
        id=uuid4(),
        conversation_id=uuid4(),
        owner_id=scope.owner_id,
        role=MessageRole.USER,
        content="Summarize this selected account.",
        status=MessageStatus.COMPLETED,
        created_at=datetime(2026, 10, 11, 12, tzinfo=UTC),
        application_id="finance",
    )

    assembled = assembler.assemble(
        (),
        pending,
        refresh=False,
        application_context=application_context,
        context_plan=plan,
    )

    assert plan.selections[0].provider_id == FINANCE_ACCOUNT_PROVIDER_ID
    assert plan.selections[0].fields == ("account_summary", "balance_summary")
    assert assembled.manifest.actual_build
    assert assembled.manifest.effective_sensitivity == "restricted"
    assert any(
        item.injected and item.source_class == "domain_current" for item in assembled.manifest.items
    )
    assert "semantic_class" in "\n".join(message.content for message in assembled.messages)
    assert any(request.operation == "verify" for request in client.requests)


def test_finance_context_contribution_is_absent_when_default_gate_is_off() -> None:
    contribution = configured_finance_context_contribution(
        type("Settings", (), {"finance_context_enabled": False})()
    )
    assert contribution.provider_factories == {}
    assert contribution.planning_rules == ()
    assert contribution.permission_revalidators == ()


def test_permission_revalidator_fails_closed_on_wrong_namespace() -> None:
    client = FakeFinanceClient(FinanceContextReadResponse(items=()))
    revalidator = FinanceContextPermissionRevalidator(client)
    dependency = ContextPermissionDependency(
        permission_id="foreign_permission:account:123",
        version="v1",
        purpose="synthetic",
    )
    assert revalidator.supports(dependency) is False
    assert revalidator.is_current(dependency) is False
    assert client.requests == []


def test_request_rejects_extraneous_finance_wire_identity_fields() -> None:
    with pytest.raises(ValidationError):
        FinanceContextReadRequest.model_validate(
            {
                "operation": "current",
                "entity_refs": [
                    {
                        "entity_type": "account",
                        "entity_id": str(uuid4()),
                        "owner_id": "attacker-controlled",
                    }
                ],
                "fields": ["account_summary"],
                "max_results": 1,
                "max_bytes": 1024,
            }
        )


def test_monthly_budget_federation_adapter_preserves_exact_fields_and_dependency() -> None:
    now = datetime.now(UTC)
    budget_id = str(uuid4())
    source = ApplicationScope(application_id="finance")
    destination = ApplicationScope(application_id="shopping")
    source_entity = ContextEntityReference(
        entity_type="discretionary_budget",
        entity_id=budget_id,
        application_id="finance",
        workspace_id=None,
    )
    record = _budget_record(budget_id)
    client = FakeFinanceClient(FinanceContextReadResponse(items=(record,)))
    adapter = FinanceBudgetFederationAdapter(client)
    intent = FederationGrantIntent(
        grant_id=uuid4(),
        owner_id="verified-owner",
        acting_user_id="issuer|verified-user",
        source=source,
        destination=destination,
        category="discretionary_budget",
        purpose="shopping_discretionary_budget",
        entities=(source_entity,),
        fields=("amount", "currency", "period"),
        expires_at=now + timedelta(minutes=10),
    )
    source_policy = adapter.resolve_source_policy(intent, deadline=monotonic() + 1)

    grant = FederationGrant(
        grant_id=intent.grant_id,
        issuance_id=uuid4(),
        revision=1,
        epoch=1,
        source=source,
        destination=destination,
        category=intent.category,
        purpose=intent.purpose,
        entities=intent.entities,
        owner_id=intent.owner_id,
        acting_user_id=intent.acting_user_id,
        fields=intent.fields,
        expires_at=intent.expires_at,
        created_at=now,
        updated_at=now,
        source_policy=source_policy,
        sensitivity="restricted",
        maximum_sensitivity="restricted",
    )
    scope = RequestScope(
        application_id="shopping",
        owner_id="verified-owner",
        acting_user_id="issuer|verified-user",
        request_id="finance-budget-export-test",
    )
    selection = ContextSelection(
        provider_id=FINANCE_BUDGET_EXPORT_PROVIDER_ID,
        operation="entity",
        fields=intent.fields,
        federation=FederationSelection(
            grant_id=grant.grant_id,
            issuance_id=grant.issuance_id,
            revision=grant.revision,
            epoch=grant.epoch,
            source=source,
            category=grant.category,
            purpose=grant.purpose,
            entities=grant.entities,
        ),
        max_tokens=512,
    )

    assert adapter.authorize_export(
        grant, selection, scope, deadline=monotonic() + 1
    )
    result = adapter.fetch(grant, selection, scope, deadline=monotonic() + 1)

    assert result.complete is True
    assert len(result.items) == 1
    item = result.items[0]
    assert set(item.payload.model_dump()) == {"amount", "currency", "period"}
    assert item.payload.amount.value == "850.50"
    assert item.payload.currency.value == "USD"
    assert item.payload.period.value == "2026-11"
    assert item.permission_dependencies == (source_policy,)
    assert all(
        request.destination_application_id == "shopping"
        and request.purpose == "shopping_discretionary_budget"
        for request in client.requests
    )

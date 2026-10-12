"""Health context uses the shared provider, policy, planner, and builder seams."""

from datetime import UTC, datetime
from time import monotonic
from uuid import uuid4

import httpx
import pytest
from pydantic import ValidationError

from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.applications.registry import default_application_registry
from personal_ai.auth.scope import RequestScope
from personal_ai.context.assembler import ContextAssembler
from personal_ai.context.builder import ContextBuildItem
from personal_ai.context.health import (
    HEALTH_CONTEXT_SCHEMA,
    HEALTH_DAILY_FIELDS,
    HEALTH_MAX_WINDOW,
    HEALTH_PROFILE_FIELDS,
    HealthContextFieldSensitivity,
    HealthContextHTTPClient,
    HealthContextPermissionDependency,
    HealthContextPermissionRevalidator,
    HealthContextProvider,
    HealthContextProviderFactory,
    HealthContextReadRequest,
    HealthContextReadResponse,
    HealthContextRecord,
    HealthContextWirePayload,
    configured_health_context_contribution,
    health_context_planning_rules,
)
from personal_ai.context.planner import ContextPlanner
from personal_ai.context.providers import (
    ContextFieldSensitivity,
    ContextPermissionDependency,
    ContextPreparationError,
    ContextProviderCoordinator,
    ContextProviderInputs,
    ContextSelection,
)
from personal_ai.context.runtime import (
    ContextPermissionRevalidatorRegistry,
    ContextRuntimeContribution,
    compose_context_runtime,
)
from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.entities import Message, MessageRole, MessageStatus
from personal_ai.settings import Settings

HEALTH_PROFILE_PROVIDER_ID = "health.profile_preferences_context"


class FakeHealthClient:
    def __init__(self, response: HealthContextReadResponse) -> None:
        self.response = response
        self.requests: list[HealthContextReadRequest] = []

    def read(self, request: HealthContextReadRequest, *, deadline: float) -> HealthContextReadResponse:
        assert deadline > monotonic()
        self.requests.append(request)
        if request.operation == "verify":
            if not self.response.items:
                return HealthContextReadResponse(
                    operation="verify",
                    permission_versions=(),
                )
            dependency = self.response.items[0].permission_dependencies[0]
            return HealthContextReadResponse(
                operation="verify",
                permission_versions=(
                    {
                        "object_id": self.response.items[0].object_id,
                        "version": dependency.version,
                    },
                ),
            )
        return self.response


def _scope(application_id: str = "health") -> RequestScope:
    return RequestScope(
        owner_id="local-owner",
        request_id="health-context-test",
        application_id=application_id,
        workspace_id=None,
    )


def _record(
    *,
    category: str = "profile_preferences",
    object_id=None,
    fields: tuple[str, ...] = HEALTH_PROFILE_FIELDS,
) -> HealthContextRecord:
    selected_id = object_id or uuid4()
    values = {
        "category": category,
        "object_type": "profile_item",
        "record": {
            "kind": "preference",
            "category": "preferences",
            "key": "diet",
            "label": "Synthetic preference",
            "value": {"type": "text", "value": "synthetic value"},
        },
        "source_kind": "manual",
        "confirmation_status": "user_confirmed",
        "validity": {"valid_from": None, "valid_to": None},
    }
    labels = tuple(
        ContextFieldSensitivity(field=field, sensitivity="restricted")
        for field in fields
    )
    source_id = uuid4()
    from personal_ai.context.health import HealthContextFieldSensitivity

    return HealthContextRecord(
        object_id=selected_id,
        object_type="profile_item",
        object_revision=1,
        schema_version=1,
        source_id=source_id,
        source_version="health-object-v1:r1:schema-1",
        source_kind="manual",
        confirmation_status="user_confirmed",
        authority="authoritative",
        observed_at=datetime(2026, 10, 11, 12, tzinfo=UTC),
        effective_at=None,
        expires_at=None,
        active_state="active",
        sensitivity="restricted",
        field_sensitivity=tuple(
            HealthContextFieldSensitivity(field=item.field, sensitivity=item.sensitivity)
            for item in labels
        ),
        source_refs=(
            {
                "kind": "record",
                "reference_id": str(selected_id),
                "fingerprint": "a" * 64,
            },
            {
                "kind": "source",
                "reference_id": str(source_id),
                "fingerprint": "a" * 64,
            },
        ),
        permission_dependencies=(
            HealthContextPermissionDependency(
                permission_id=f"health_context_read:{category}:profile_item:{selected_id}",
                version="health-object-v1:r1:ai1:cross1",
                purpose="personal_ai_context",
            ),
        ),
        payload=HealthContextWirePayload.model_validate(values),
    )


def test_profile_provider_preserves_provenance_sensitivity_and_permission_dependencies() -> None:
    selected_id = uuid4()
    record = _record(object_id=selected_id)
    client = FakeHealthClient(HealthContextReadResponse(operation="profile", items=(record,)))
    provider = HealthContextProvider(client, HEALTH_PROFILE_PROVIDER_ID)
    selection = ContextSelection(
        provider_id=HEALTH_PROFILE_PROVIDER_ID,
        operation="profile",
        fields=HEALTH_PROFILE_FIELDS,
        max_results=4,
        max_bytes=12_288,
        max_tokens=512,
        timeout_seconds=3,
    )
    inputs = ContextProviderInputs(scope=_scope())
    provider.validate_selection(selection, inputs)

    (item,) = provider.fetch(selection, _scope(), deadline=monotonic() + 3)

    assert client.requests[0].schema_version == HEALTH_CONTEXT_SCHEMA
    assert client.requests[0].application_id == "health"
    assert client.requests[0].purpose == "personal_ai_context"
    assert client.requests[0].category == "profile_preferences"
    assert item.provider_id == HEALTH_PROFILE_PROVIDER_ID
    assert item.application_id == "health" and item.workspace_id is None
    assert item.sensitivity == "restricted"
    assert item.authority == "authoritative"
    assert item.source_version == record.source_version
    assert item.source_refs[1].kind == "source"
    assert item.permission_dependencies[0].permission_id == (
        f"health_context_read:profile_preferences:profile_item:{selected_id}"
    )


def test_truncated_health_slice_remains_usable_and_marks_shared_context_partial() -> None:
    record = _record()
    client = FakeHealthClient(
        HealthContextReadResponse(operation="profile", items=(record,), truncated=True)
    )
    provider = HealthContextProvider(client, HEALTH_PROFILE_PROVIDER_ID)
    selection = ContextSelection(
        provider_id=HEALTH_PROFILE_PROVIDER_ID,
        operation="profile",
        fields=HEALTH_PROFILE_FIELDS,
        max_results=4,
        max_bytes=12_288,
        max_tokens=512,
        timeout_seconds=3,
    )

    (item,) = provider.fetch(selection, _scope(), deadline=monotonic() + 3)
    rendered = ContextBuildItem.from_context_item(item)

    assert item.partial_result is True
    assert '"partial_result":true' in rendered.content


def test_health_daily_provider_preserves_time_units_quality_and_unknown_uncertainty() -> None:
    object_id = uuid4()
    source_id = uuid4()
    observed_at = datetime(2026, 10, 11, 12, tzinfo=UTC)
    record = HealthContextRecord(
        object_id=object_id,
        object_type="event",
        object_revision=3,
        schema_version=1,
        source_id=source_id,
        source_version="health-object-v1:r3:schema-1",
        source_kind="device",
        confirmation_status="user_confirmed",
        authority="authoritative",
        observed_at=observed_at,
        effective_at=observed_at,
        active_state="active",
        sensitivity="restricted",
        field_sensitivity=tuple(
            HealthContextFieldSensitivity(field=field, sensitivity="restricted")
            for field in HEALTH_DAILY_FIELDS
        ),
        source_refs=(
            {"kind": "record", "reference_id": str(object_id), "fingerprint": "c" * 64},
            {"kind": "source", "reference_id": str(source_id), "fingerprint": "c" * 64},
        ),
        permission_dependencies=(
            HealthContextPermissionDependency(
                permission_id=f"health_context_read:exercise:event:{object_id}",
                version="health-object-v1:r3:ai1:cross1",
                purpose="personal_ai_context",
            ),
        ),
        payload=HealthContextWirePayload(
            category="exercise",
            object_type="event",
            record={
                "kind": "workout",
                "label": "Synthetic run",
                "duration": {"value": 30, "unit": "min"},
                "distance": {"value": 5, "unit": "km"},
            },
            domain="exercise",
            time={
                "precision": "instant",
                "occurred_at": observed_at.isoformat(),
                "timezone": "America/Los_Angeles",
            },
            units={"duration": "min", "distance": "km"},
            source_kind="device",
            confirmation_status="user_confirmed",
            quality={},
        ),
    )
    client = FakeHealthClient(HealthContextReadResponse(operation="history", items=(record,)))
    provider = HealthContextProvider(client, "health.exercise_context")
    selection = ContextSelection(
        provider_id="health.exercise_context",
        operation="history",
        fields=HEALTH_DAILY_FIELDS,
        max_results=4,
        max_bytes=24_576,
        max_tokens=1024,
        timeout_seconds=3,
        window_start=observed_at - HEALTH_MAX_WINDOW,
        window_end=observed_at,
    )
    provider.validate_selection(selection, ContextProviderInputs(scope=_scope()))

    (item,) = provider.fetch(selection, _scope(), deadline=monotonic() + 3)

    assert item.payload.units == {"duration": "min", "distance": "km"}
    assert item.payload.time == record.payload.time
    assert item.payload.quality == {}
    assert item.payload.uncertainty is None
    assert item.sensitivity == "restricted"


def test_health_provider_rejects_wrong_application_category_and_oversized_window_pre_fetch() -> None:
    record = _record()
    client = FakeHealthClient(HealthContextReadResponse(operation="profile", items=(record,)))
    provider = HealthContextProvider(client, HEALTH_PROFILE_PROVIDER_ID)
    selection = ContextSelection(
        provider_id=HEALTH_PROFILE_PROVIDER_ID,
        operation="profile",
        fields=HEALTH_PROFILE_FIELDS,
        max_results=4,
        max_bytes=12_288,
        timeout_seconds=3,
    )

    with pytest.raises(ContextPreparationError, match="health_context_application_scope_required"):
        provider.validate_selection(selection, ContextProviderInputs(scope=_scope("finance")))
    with pytest.raises(ValidationError):
        HealthContextReadRequest(
            operation="history",
            category="nutrition",
            fields=HEALTH_DAILY_FIELDS,
            window_start=datetime(2026, 1, 1, tzinfo=UTC),
            window_end=datetime(2026, 5, 1, tzinfo=UTC),
        )
    assert client.requests == []
    assert HEALTH_MAX_WINDOW.days == 90


def test_health_revalidator_checks_exact_category_and_denies_unknown_namespaces() -> None:
    record = _record()
    client = FakeHealthClient(HealthContextReadResponse(operation="profile", items=(record,)))
    validator = HealthContextPermissionRevalidator(client)
    dependency = ContextPermissionDependency(
        permission_id=record.permission_dependencies[0].permission_id,
        version=record.permission_dependencies[0].version,
        purpose="personal_ai_context",
    )
    assert validator.is_current(dependency) is True
    assert client.requests[-1].operation == "verify"
    assert client.requests[-1].category == "profile_preferences"
    count = len(client.requests)
    unknown = ContextPermissionDependency(
        permission_id="foreign_permission:health_record",
        version="v1",
        purpose="synthetic",
    )
    assert validator.is_current(unknown) is False
    assert len(client.requests) == count


def test_health_source_reference_kind_survives_shared_authority_snapshot_redaction() -> None:
    from personal_ai.contracts.context_references import (
        ContextAuthorityReference,
        ContextSourceReference,
    )

    source = ContextSourceReference(
        kind="source",
        reference_id="health-source-opaque",
        fingerprint="b" * 64,
    )
    authority = ContextAuthorityReference.model_validate(source)

    assert authority.kind == "source"
    assert authority.reference_digest != "health-source-opaque"
    assert authority.fingerprint == "b" * 64


def test_health_client_uses_distinct_bearer_tokens_and_bounded_no_redirect_transport() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["authorization"] = request.headers["authorization"]
        seen["user"] = request.headers["x-user-id-token"]
        seen["body"] = request.content
        return httpx.Response(
            200,
            json={
                "schema_version": HEALTH_CONTEXT_SCHEMA,
                "application_id": "health",
                "operation": "catalog",
                "categories": [
                    {
                        "category": "profile_preferences",
                        "display_name": "Profile preferences",
                        "sensitivity": "restricted",
                    }
                ],
            },
        )

    client = HealthContextHTTPClient(
        base_url="https://health.example.test",
        auth_mode="google_oidc",
        service_audience="https://health.example.test",
        service_account="personal-ai@example.test",
        service_token_fetcher=lambda **kwargs: "service-token",
        user_token_provider=lambda: "delegated-user-token",
        transport=httpx.MockTransport(handler),
    )
    response = client.read(HealthContextReadRequest(operation="catalog"), deadline=monotonic() + 3)
    assert response.operation == "catalog"
    assert response.categories[0].category == "profile_preferences"
    assert seen["authorization"] == "Bearer service-token"
    assert seen["user"] == "delegated-user-token"
    assert b'"owner_id"' not in seen["body"]

    with pytest.raises(ValueError, match="health_context_base_url_invalid"):
        HealthContextHTTPClient(base_url="http://health.example.test", auth_mode="google_oidc")


def test_health_capabilities_are_registered_but_gate_and_mutation_stay_closed() -> None:
    registration = default_application_registry().registration("health")
    providers = {item.capability_id: item for item in registration.context_providers}
    assert set(providers) >= {
        "health.profile_background_context",
        "health.profile_constraints_context",
        "health.profile_preferences_context",
        "health.measurements_context",
        "health.nutrition_context",
        "health.exercise_context",
        "health.sleep_context",
        "health.symptoms_context",
    }
    for provider in providers.values():
        if provider.capability_id.startswith("health."):
            assert provider.available is False
            assert provider.unavailable_reason == "health_delegated_identity_contract_unavailable"
            assert provider.is_enabled({}) is False
            assert provider.is_enabled({"health_context_enabled": True}) is False
    assert registration.tools[0].capability_id == "health.record_action"
    assert registration.tools[0].available is False
    assert registration.definition.cross_application.mode == "disabled"
    assert registration.definition.context_policy.external_execution_modes == ()
    assert registration.definition.context_policy.sidecar.connected_provider_disclosure.allowed is False
    assert registration.definition.context_policy.sidecar.manual_external_disclosure.allowed is False
    assert registration.definition.context_policy.sidecar.manual_import_reuse.allowed is False
    assert registration.definition.context_policy.sidecar.copy_allowed is True
    assert registration.definition.context_policy.sidecar.draft_insert_target_ids == ()
    contribution = configured_health_context_contribution(
        type("Settings", (), {"health_context_enabled": True})()
    )
    assert contribution.provider_factories == {}
    assert contribution.planning_rules == ()


def test_health_candidate_uses_shared_planner_coordinator_and_assembler() -> None:
    record = _record()
    client = FakeHealthClient(HealthContextReadResponse(operation="profile", items=(record,)))
    provider = HealthContextProviderFactory(client, HEALTH_PROFILE_PROVIDER_ID)
    runtime = compose_context_runtime(
        ContextRuntimeContribution(
            provider_factories={HEALTH_PROFILE_PROVIDER_ID: provider},
            planning_rules=health_context_planning_rules(),
            permission_revalidators=(HealthContextPermissionRevalidator(client),),
        )
    )
    coordinator = ContextProviderCoordinator(
        runtime.provider_factories,
        feature_flags={"health_context_enabled": True},
    )
    registration = default_application_registry().registration("health")
    test_capabilities = tuple(
        capability.model_copy(
            update={
                "available": True,
                "feature_gate": "health_context_enabled",
                "unavailable_reason": None,
            }
        )
        if capability.capability_id == HEALTH_PROFILE_PROVIDER_ID
        else capability
        for capability in registration.context_providers
    )
    scope = _scope()
    context = ApplicationContextRequest(
        definition=registration.definition,
        scope=scope,
        context_provider_capabilities=test_capabilities,
        tool_capabilities=registration.tools,
    )
    assembler = ContextAssembler(
        Settings(ai_provider="fake", ai_model="fixture-model"),
        FakeTokenCounter(),
        context_provider_coordinator=coordinator,
        permission_revalidator=ContextPermissionRevalidatorRegistry(
            runtime.permission_revalidators
        ),
        context_planner=ContextPlanner(
            rules=health_context_planning_rules(),
            include_default_rules=False,
        ),
    )
    plan = assembler.plan_context("include my health preferences", context)
    pending = Message(
        id=uuid4(),
        conversation_id=uuid4(),
        owner_id=scope.owner_id,
        role=MessageRole.USER,
        content="Summarize my health preferences.",
        status=MessageStatus.COMPLETED,
        created_at=datetime(2026, 10, 11, 12, tzinfo=UTC),
        application_id="health",
    )

    assembled = assembler.assemble(
        (),
        pending,
        refresh=False,
        application_context=context,
        context_plan=plan,
    )

    assert plan.selections[0].provider_id == HEALTH_PROFILE_PROVIDER_ID
    assert plan.selections[0].operation == "profile"
    assert plan.selections[0].fields == HEALTH_PROFILE_FIELDS
    assert assembled.manifest.effective_sensitivity == "restricted"
    assert any(
        item.injected and item.source_class == "domain_profile"
        for item in assembled.manifest.items
    )
    assert "Synthetic preference" in "\n".join(message.content for message in assembled.messages)
    assert any(request.operation == "verify" for request in client.requests)


def test_health_history_planning_rules_have_bounded_windows_and_sensitive_categories() -> None:
    rules = health_context_planning_rules()
    assert {rule.category for rule in rules} == {
        "health_profile_background",
        "health_profile_constraints",
        "health_profile_preferences",
        "health_measurements",
        "health_nutrition",
        "health_exercise",
        "health_sleep",
        "health_symptoms",
    }
    for rule in rules:
        assert rule.application_ids == ("health",)
        if rule.operation == "history":
            assert rule.window_seconds == int(HEALTH_MAX_WINDOW.total_seconds())

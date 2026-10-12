"""Travel adapters use the shared provider and permission contracts."""

import asyncio
import json
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from uuid import uuid4

import pytest

from personal_ai.applications.contracts import (
    ApplicationContextRequest,
    ApplicationLaunchContext,
    ManualImportReusePolicy,
)
from personal_ai.applications.registry import default_application_registry
from personal_ai.auth.scope import ApplicationScope, RequestScope, application_scope_context
from personal_ai.context.assembler import ContextAssembler
from personal_ai.context.contracts import ConversationSummary, fingerprint
from personal_ai.context.history import conversation_context_messages
from personal_ai.context.planner import ContextPlanner
from personal_ai.context.providers import (
    ContextEntityReference,
    ContextFieldSensitivity,
    ContextPermissionDependency,
    ContextPreparationError,
    ContextProviderCoordinator,
    ContextSelection,
    ContextSourceReference,
)
from personal_ai.context.repositories import InMemorySummaryRepository
from personal_ai.context.runtime import (
    ContextPermissionRevalidatorRegistry,
    ContextRuntimeRegistry,
)
from personal_ai.context.tokens import FakeTokenCounter
from personal_ai.context.travel import (
    TRAVEL_CONTEXT_FIELDS,
    TRAVEL_CONTEXT_PROVIDER_ID,
    TRAVEL_TRIP_EXPORT_FIELDS,
    TRAVEL_TRIP_EXPORT_PROVIDER_ID,
    TravelContextPermissionRevalidator,
    TravelContextProvider,
    TravelContextProviderFactory,
    TravelContextReadResponse,
    TravelContextRecord,
    TravelSelectionBinding,
    TravelTripFederationExportAdapter,
    configured_travel_context_contribution,
    travel_context_planning_rules,
)
from personal_ai.contracts.context_references import ContextSourceSnapshot
from personal_ai.contracts.execution import ContinuationRequest
from personal_ai.contracts.federation import FederationSelection
from personal_ai.entities import Conversation, Message, MessageRole, MessageStatus
from personal_ai.entities.turn_execution import TurnAttribution
from personal_ai.federation.contracts import FederationGrantIntent
from personal_ai.llm.fake import FakeLLMClient
from personal_ai.services.chat.events import TurnCompleted, TurnFailed, TurnMessageCreated
from personal_ai.services.chat.service import ChatTurnService
from personal_ai.settings import Settings
from personal_ai.storage import InMemoryConversationRepository, InMemoryMessageRepository


class FakeTravelClient:
    def __init__(self, response):
        self.response = response
        self.requests = []

    def read(self, request, *, deadline):
        self.requests.append((request, deadline))
        return self.response


def _record(entity_type: str, entity_id: str, *, revision: str = "8"):
    return TravelContextRecord(
        entity_type=entity_type,
        entity_id=entity_id,
        source_id="opaque-source-id",
        source_version=revision,
        authority="authoritative",
        observed_at=datetime(2026, 10, 11, tzinfo=UTC),
        sensitivity="sensitive",
        payload={"trip_title": "Synthetic trip"},
        source_refs=(
            ContextSourceReference(
                kind="record",
                reference_id="opaque-record-ref",
                fingerprint="a" * 64,
            ),
        ),
        permission_dependencies=(
            ContextPermissionDependency(
                permission_id="travel_context_read:trip",
                version=revision,
                purpose="verify current owner access",
            ),
        ),
        field_sensitivity=(
            ContextFieldSensitivity(
                field="trip_title",
                sensitivity="sensitive",
            ),
        ),
    )


def _scope() -> RequestScope:
    return RequestScope(
        owner_id="owner-1",
        request_id="travel-context-test",
        application_id="travel",
        workspace_id=None,
    )


def test_travel_provider_hashes_model_item_identity_and_keeps_owner_only_dependency():
    reference = ContextEntityReference(
        entity_type="trip",
        entity_id="internal-trip-id",
        application_id="travel",
        workspace_id=None,
    )
    client = FakeTravelClient(
        TravelContextReadResponse(items=(_record("trip", "internal-trip-id"),))
    )
    provider = TravelContextProvider(client)
    selection = ContextSelection(
        provider_id=TRAVEL_CONTEXT_PROVIDER_ID,
        operation="current",
        fields=("trip_title",),
        entity_refs=(reference,),
        max_results=1,
        max_bytes=2_048,
        max_tokens=64,
        timeout_seconds=1,
        target_scope=ApplicationScope(application_id="travel"),
    )

    (item,) = provider.fetch(selection, _scope(), deadline=10**12)

    assert item.application_id == "travel"
    assert item.workspace_id is None
    assert item.entity_refs == ()
    assert "internal-trip-id" not in item.item_id
    assert item.source_id != "opaque-source-id"
    assert item.permission_dependencies[0].permission_id == "travel_context_read:trip"
    assert client.requests[0][0].max_results == 1


def test_host_bootstrap_installs_travel_runtime_only_when_its_gate_is_enabled():
    disabled = configured_travel_context_contribution(
        Settings(
            _env_file=None,
            ai_provider="fake",
            ai_model="fixture",
            travel_context_enabled=False,
        )
    )
    assert disabled.provider_factories == {}
    assert disabled.planning_rules

    enabled = configured_travel_context_contribution(
        Settings(
            _env_file=None,
            ai_provider="fake",
            ai_model="fixture",
            travel_context_enabled=True,
            auth_mode="development",
            app_environment="test",
        )
    )
    assert set(enabled.provider_factories) == {TRAVEL_CONTEXT_PROVIDER_ID}
    assert enabled.planning_rules
    assert len(enabled.permission_revalidators) == 1

    registration = default_application_registry().registration("travel")
    context = ApplicationContextRequest(
        definition=registration.definition,
        scope=_scope(),
        context_provider_capabilities=registration.context_providers,
        tool_capabilities=registration.tools,
    )
    selected_trip = ContextEntityReference(
        entity_type="trip", entity_id="trip-id", application_id="travel"
    )
    disabled_coordinator = ContextProviderCoordinator(
        disabled.provider_factories, feature_flags={"travel_context_enabled": False}
    )
    disabled_capability = disabled_coordinator.planning_capability(
        context, TRAVEL_CONTEXT_PROVIDER_ID
    )
    assert disabled_capability.status == "disabled"
    disabled_plan = ContextPlanner(disabled.planning_rules).plan(
        "this trip",
        context,
        {TRAVEL_CONTEXT_PROVIDER_ID: disabled_capability},
        input_token_budget=2_000,
        candidate_entities=(selected_trip,),
    )
    assert disabled_plan.selections == ()
    assert disabled_plan.decisions[0].reason == "provider_feature_disabled"

    enabled_coordinator = ContextProviderCoordinator(
        enabled.provider_factories, feature_flags={"travel_context_enabled": True}
    )
    enabled_capability = enabled_coordinator.planning_capability(
        context, TRAVEL_CONTEXT_PROVIDER_ID
    )
    enabled_plan = ContextPlanner(enabled.planning_rules).plan(
        "this trip",
        context,
        {TRAVEL_CONTEXT_PROVIDER_ID: enabled_capability},
        input_token_budget=2_000,
        candidate_entities=(selected_trip,),
    )
    assert enabled_plan.selections[0].provider_id == TRAVEL_CONTEXT_PROVIDER_ID
    assert "destination" not in TRAVEL_CONTEXT_FIELDS


def test_travel_trip_export_adapter_enforces_exact_source_policy_and_preserves_dependencies():
    entity = ContextEntityReference(
        entity_type="trip", entity_id="trip-opaque-id", application_id="travel"
    )
    record = TravelContextRecord(
        entity_type="trip",
        entity_id=entity.entity_id,
        source_id="opaque-travel-source",
        source_version="8",
        authority="authoritative",
        observed_at=datetime(2026, 10, 11, tzinfo=UTC),
        sensitivity="sensitive",
        payload={
            "destination": "Kyoto, Japan",
            "start_date": "2026-11-01",
            "end_date": "2026-11-06",
        },
        source_refs=(
            ContextSourceReference(
                kind="record", reference_id="opaque-trip-ref", fingerprint="e" * 64
            ),
        ),
        permission_dependencies=(
            ContextPermissionDependency(
                permission_id=f"travel_context_read:{entity.entity_id}",
                version="8",
                purpose="shopping_trip_context",
                source_application_id="travel",
                destination_application_id="shopping",
            ),
        ),
        field_sensitivity=tuple(
            ContextFieldSensitivity(field=field, sensitivity="sensitive")
            for field in TRAVEL_TRIP_EXPORT_FIELDS
        ),
    )
    client = FakeTravelClient(TravelContextReadResponse(items=(record,)))
    adapter = TravelTripFederationExportAdapter(client)
    source = ApplicationScope(application_id="travel")
    destination = ApplicationScope(application_id="shopping")
    owner_id = "verified-owner"
    acting_user_id = "https://accounts.google.com|verified-subject"
    intent = FederationGrantIntent(
        grant_id=uuid4(),
        owner_id=owner_id,
        acting_user_id=acting_user_id,
        source=source,
        destination=destination,
        category="trip",
        purpose="shopping_trip_context",
        entities=(entity,),
        fields=TRAVEL_TRIP_EXPORT_FIELDS,
        expires_at=datetime.now(UTC) + timedelta(hours=1),
    )
    policy = adapter.resolve_source_policy(intent, deadline=10**12)
    grant = SimpleNamespace(
        source=source,
        destination=destination,
        category="trip",
        purpose="shopping_trip_context",
        fields=TRAVEL_TRIP_EXPORT_FIELDS,
        owner_id=owner_id,
        acting_user_id=acting_user_id,
        expires_at=intent.expires_at,
        source_policy=policy,
    )
    selection = ContextSelection(
        provider_id=TRAVEL_TRIP_EXPORT_PROVIDER_ID,
        operation="entity",
        fields=TRAVEL_TRIP_EXPORT_FIELDS,
        federation=FederationSelection(
            grant_id=intent.grant_id,
            issuance_id=uuid4(),
            revision=1,
            epoch=1,
            source=source,
            category="trip",
            purpose="shopping_trip_context",
            entities=(entity,),
        ),
    )
    scope = RequestScope(
        owner_id=owner_id,
        acting_user_id=acting_user_id,
        request_id="travel-federation-test",
        application_id="shopping",
    )

    assert adapter.authorize_export(grant, selection, scope, deadline=10**12)
    result = adapter.fetch(grant, selection, scope, deadline=10**12)
    assert result.complete is True and result.continuation is None
    assert len(result.items) == 1
    item = result.items[0]
    assert set(item.payload.model_dump()) == set(TRAVEL_TRIP_EXPORT_FIELDS)
    assert item.payload.destination == "Kyoto, Japan"
    assert item.permission_dependencies[0] == policy
    assert item.entity_refs == (entity,)
    assert client.requests[0][0].fields == ("trip_revision",)
    assert client.requests[-1][0].fields == TRAVEL_TRIP_EXPORT_FIELDS

    client.response = TravelContextReadResponse(
        complete=False,
        continuation="next-page-required",
    )
    with pytest.raises(ContextPreparationError, match="travel_trip_export_incomplete"):
        adapter.fetch(grant, selection, scope, deadline=10**12)

    client.response = TravelContextReadResponse(
        complete=True,
        authoritative_empty_entities=(entity.entity_id,),
    )
    empty = adapter.fetch(grant, selection, scope, deadline=10**12)
    assert empty.items == () and empty.authoritative_empty_entities == (entity,)


def test_travel_federation_capability_is_discovered_only_with_executable_adapter():
    from personal_ai.federation.deployment import reconcile_federation_runtime_metadata

    settings = Settings(
        _env_file=None,
        ai_provider="fake",
        ai_model="fixture",
        auth_mode="development",
        app_environment="test",
        travel_federation_enabled=True,
    )
    contribution = configured_travel_context_contribution(settings)
    assert set(contribution.export_adapters) == {TRAVEL_TRIP_EXPORT_PROVIDER_ID}
    assert contribution.provider_factories == {}

    from personal_ai.context.deployment import configured_context_runtime

    runtime = configured_context_runtime(settings)
    registry = reconcile_federation_runtime_metadata(default_application_registry(), runtime)
    shopping = registry.registration("shopping")
    capability = next(
        item for item in shopping.context_providers
        if item.capability_id == TRAVEL_TRIP_EXPORT_PROVIDER_ID
    )
    assert capability.available is True


def test_travel_provider_accepts_bounded_reservation_linked_to_selected_day():
    selected = ContextEntityReference(
        entity_type="day",
        entity_id="selected-day",
        application_id="travel",
        workspace_id=None,
    )
    reservation = _record("reservation", "opaque-reservation").model_copy(
        update={
            "selection_binding": TravelSelectionBinding(
                entity_type="day",
                entity_id="selected-day",
                relationship="day_reservation_summary",
            ),
            "payload": {"reservation_summary": "flight · Sample Air · confirmed"},
        }
    )
    client = FakeTravelClient(TravelContextReadResponse(items=(reservation,)))
    provider = TravelContextProvider(client)
    selection = ContextSelection(
        provider_id=TRAVEL_CONTEXT_PROVIDER_ID,
        operation="entity",
        fields=("reservation_summary",),
        entity_refs=(selected,),
        max_results=1,
        max_bytes=2_048,
        max_tokens=64,
        timeout_seconds=1,
        target_scope=ApplicationScope(application_id="travel"),
    )

    (item,) = provider.fetch(selection, _scope(), deadline=10**12)
    assert item.payload.reservation_summary == "flight · Sample Air · confirmed"


def test_travel_provider_consumes_versioned_shared_reservation_fixture():
    fixture = json.loads(
        (Path(__file__).parent / "fixtures/travel-context-read-v2-reservation.json").read_text()
    )
    response = TravelContextReadResponse.model_validate(fixture)
    binding = response.items[0].selection_binding
    assert response.schema_version == "travel-context-read-v2"
    assert binding is not None
    assert binding.entity_type == "day"

    reference = ContextEntityReference(
        entity_type="day",
        entity_id=binding.entity_id,
        application_id="travel",
        workspace_id=None,
    )
    provider = TravelContextProvider(FakeTravelClient(response))
    selection = ContextSelection(
        provider_id=TRAVEL_CONTEXT_PROVIDER_ID,
        operation="entity",
        fields=("reservation_summary",),
        entity_refs=(reference,),
        max_results=1,
        max_bytes=2_048,
        max_tokens=64,
        timeout_seconds=1,
        target_scope=ApplicationScope(application_id="travel"),
    )

    (item,) = provider.fetch(selection, _scope(), deadline=10**12)
    assert item.sensitivity == "sensitive"
    assert item.payload.reservation_summary == "lodging · Example Stay · confirmed"
    assert "00000000-0000-4000-8000-000000000003" not in item.item_id


def test_travel_provider_rejects_reservation_without_selected_binding():
    selected = ContextEntityReference(
        entity_type="day", entity_id="selected-day", application_id="travel"
    )
    client = FakeTravelClient(
        TravelContextReadResponse(items=(_record("reservation", "different-reservation"),))
    )
    provider = TravelContextProvider(client)
    selection = ContextSelection(
        provider_id=TRAVEL_CONTEXT_PROVIDER_ID,
        operation="entity",
        fields=("reservation_summary",),
        entity_refs=(selected,),
        max_results=1,
        max_bytes=2_048,
        max_tokens=64,
        timeout_seconds=1,
        target_scope=ApplicationScope(application_id="travel"),
    )

    with pytest.raises(ContextPreparationError, match="travel_context_unselected_entity"):
        provider.fetch(selection, _scope(), deadline=10**12)


def test_travel_permission_revalidation_fails_closed_when_revision_changes():
    client = FakeTravelClient(
        TravelContextReadResponse(items=(_record("trip", "trip-id", revision="9"),))
    )
    validator = TravelContextPermissionRevalidator(client)
    dependency = ContextPermissionDependency(
        permission_id="travel_context_read:trip-id",
        version="8",
        purpose="verify current owner access",
    )

    assert validator.supports(dependency)
    assert not validator.is_current(dependency)
    request, _deadline = client.requests[0]
    assert request.operation == "verify"
    assert request.workspace_id is None


def test_history_revalidates_repeated_trip_authority_once_per_decision():
    scope = _scope()
    dependency = ContextPermissionDependency(
        permission_id="travel_context_read:trip",
        version="8",
        purpose="verify current owner access",
    )
    snapshots = tuple(
        ContextSourceSnapshot(
            provider_id=TRAVEL_CONTEXT_PROVIDER_ID,
            source_id="opaque-trip-source",
            source_version="8",
            item_id=f"opaque-item-{index}",
            source_classes=("domain_current",),
            owner_id=scope.owner_id,
            application_id=scope.application_id,
            workspace_id=None,
            operation="entity",
            content_fingerprint=f"{index:x}" * 64,
            permission_dependencies=(dependency,),
        )
        for index in range(1, 4)
    )
    assistant = Message(
        id=uuid4(),
        conversation_id=uuid4(),
        owner_id=scope.owner_id,
        application_id=scope.application_id,
        workspace_id=None,
        role=MessageRole.ASSISTANT,
        content="A prior answer about this trip.",
        status=MessageStatus.COMPLETED,
        created_at=datetime.now(UTC),
        attribution=TurnAttribution(
            fact_source="server_observed",
            execution_origin="automatic_managed",
            provider_id="fixture",
            model_id="fixture-model",
            recorded_at=datetime.now(UTC),
            source_snapshots=snapshots,
        ),
    )

    class CurrentPermission:
        def __init__(self):
            self.calls = 0

        def is_current(self, _dependency):
            self.calls += 1
            return True

    permission = CurrentPermission()
    allowed = conversation_context_messages(
        (assistant,),
        manual_import_reuse=ManualImportReusePolicy(),
        permission_revalidator=permission,
        check_source_permissions=True,
    )

    assert allowed == (assistant,)
    assert permission.calls == 1


def test_travel_provider_runs_through_the_shared_planner_and_context_assembler():
    scope = _scope()
    reference = ContextEntityReference(
        entity_type="trip",
        entity_id="internal-trip-id",
        application_id="travel",
        workspace_id=None,
    )
    record = _record("trip", reference.entity_id).model_copy(
        update={
            "permission_dependencies": (
                ContextPermissionDependency(
                    permission_id=f"travel_context_read:{reference.entity_id}",
                    version="8",
                    purpose="confirm current owner access and Travel source revision before disclosure",
                ),
            )
        }
    )

    class CurrentTripClient:
        def __init__(self):
            self.requests = []

        def read(self, request, *, deadline):
            self.requests.append((request, deadline))
            return TravelContextReadResponse(items=(record,))

    client = CurrentTripClient()
    validator = TravelContextPermissionRevalidator(client)
    runtime = ContextRuntimeRegistry(
        provider_factories={
            TRAVEL_CONTEXT_PROVIDER_ID: TravelContextProviderFactory(client),
        },
        planning_rules=travel_context_planning_rules(),
        permission_revalidators=(validator,),
    )
    registration = default_application_registry().registration("travel")
    application_context = ApplicationContextRequest(
        definition=registration.definition,
        scope=scope,
        context_provider_capabilities=registration.context_providers,
        tool_capabilities=registration.tools,
    )
    assembler = ContextAssembler(
        Settings(
            ai_provider="fake",
            ai_model="fixture",
            max_context_tokens=4_096,
            max_response_tokens=128,
            context_safety_margin_tokens=32,
            max_summary_tokens=512,
            summary_trigger_tokens=1_000,
        ),
        FakeTokenCounter(),
        InMemorySummaryRepository(),
        context_provider_coordinator=ContextProviderCoordinator(
            runtime.provider_factories,
            feature_flags={"travel_context_enabled": True},
        ),
        permission_revalidator=ContextPermissionRevalidatorRegistry(
            runtime.permission_revalidators
        ),
        context_planner=ContextPlanner(runtime.planning_rules),
    )
    plan = assembler.plan_context(
        "Help me with this trip.",
        application_context,
        candidate_entities=(reference,),
    )
    pending = Message(
        id=uuid4(),
        conversation_id=uuid4(),
        owner_id=scope.owner_id,
        application_id=scope.application_id,
        workspace_id=scope.workspace_id,
        role=MessageRole.USER,
        content="Help me with this trip.",
        status=MessageStatus.COMPLETED,
        created_at=datetime(2026, 10, 11, tzinfo=UTC),
    )

    assembled = assembler.assemble(
        (),
        pending,
        refresh=False,
        application_context=application_context,
        context_plan=plan,
        emit_manifest=False,
    )

    assert [(selection.provider_id, selection.operation) for selection in plan.selections] == [
        (TRAVEL_CONTEXT_PROVIDER_ID, "current")
    ]
    assert len(assembled.source_items) == 1
    assert assembled.source_items[0].payload.trip_title == "Synthetic trip"
    assert assembled.source_items[0].application_id == "travel"
    assert assembled.source_items[0].workspace_id is None
    assert "internal-trip-id" not in assembled.source_items[0].item_id
    assert [request.operation for request, _deadline in client.requests] == [
        "current",
        "verify",
        "verify",
    ]


def test_revoked_trip_context_is_removed_from_history_and_compatible_summary():
    scope = _scope()
    conversation_id = uuid4()
    reference = ContextEntityReference(
        entity_type="trip",
        entity_id="trip-id",
        application_id="travel",
        workspace_id=None,
    )

    class MutableTripClient:
        def __init__(self):
            self.revision = "8"
            self.requests = []

        def read(self, request, *, deadline):
            self.requests.append((request, deadline))
            revision = "8" if request.operation == "current" else self.revision
            record = _record("trip", reference.entity_id, revision=revision).model_copy(
                update={
                    "permission_dependencies": (
                        ContextPermissionDependency(
                            permission_id=f"travel_context_read:{reference.entity_id}",
                            version=revision,
                            purpose="confirm current owner access and source revision",
                        ),
                    )
                }
            )
            return TravelContextReadResponse(items=(record,))

    client = MutableTripClient()
    registration = default_application_registry().registration("travel")
    application_context = ApplicationContextRequest(
        definition=registration.definition,
        scope=scope,
        context_provider_capabilities=registration.context_providers,
        tool_capabilities=registration.tools,
    )
    runtime = ContextRuntimeRegistry(
        provider_factories={TRAVEL_CONTEXT_PROVIDER_ID: TravelContextProviderFactory(client)},
        planning_rules=travel_context_planning_rules(),
        permission_revalidators=(TravelContextPermissionRevalidator(client),),
    )

    class SummaryChoosingCounter(FakeTokenCounter):
        def count(self, messages):
            if any("Trip answer used" in message.content for message in messages):
                from personal_ai.context.contracts import TokenCount

                return TokenCount(10_000, "estimated")
            return super().count(messages)

    settings = Settings(
        ai_provider="fake",
        ai_model="fixture",
        max_context_tokens=4_096,
        max_response_tokens=128,
        context_safety_margin_tokens=32,
        max_summary_tokens=512,
        summary_trigger_tokens=1_000,
    )
    summaries = InMemorySummaryRepository()
    assembler = ContextAssembler(
        settings,
        SummaryChoosingCounter(),
        summaries,
        context_provider_coordinator=ContextProviderCoordinator(
            runtime.provider_factories,
            feature_flags={"travel_context_enabled": True},
        ),
        permission_revalidator=ContextPermissionRevalidatorRegistry(
            runtime.permission_revalidators
        ),
        context_planner=ContextPlanner(runtime.planning_rules),
    )
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    conversation = Conversation(
        id=conversation_id,
        owner_id=scope.owner_id,
        application_id=scope.application_id,
        workspace_id=scope.workspace_id,
        title="Trip context regression",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    with application_scope_context(ApplicationScope(application_id="travel")):
        conversations.create(conversation)
    llm = FakeLLMClient(deltas=("Trip answer used current trip data.",))
    service = ChatTurnService(
        conversations,
        messages,
        llm,
        owner_id=scope.owner_id,
        application_context=application_context,
        model="fixture",
        context_assembler=assembler,
    )
    launch = ApplicationLaunchContext(
        application_id="travel",
        workspace_id=None,
        entity_refs=(reference,),
        conversation_id=str(conversation_id),
    )
    with application_scope_context(ApplicationScope(application_id="travel")):
        first = asyncio.run(
            _collect_turn_events(
                service.continue_turn(
                    conversation_id,
                    ContinuationRequest(
                        content="Tell me about this trip.",
                        idempotency_key=uuid4(),
                        launch_context=launch,
                    ),
                )
            )
        )
    first_assistant = next(event.message for event in first if isinstance(event, TurnCompleted))

    assert first_assistant.attribution is not None
    assert first_assistant.attribution.effective_context_sensitivity == "sensitive"
    assert any(
        dependency.version == "8" and dependency.permission_id == "travel_context_read:trip-id"
        for snapshot in first_assistant.attribution.source_snapshots
        for dependency in snapshot.permission_dependencies
    )

    with application_scope_context(ApplicationScope(application_id="travel")):
        active_before_revoke = tuple(
            messages.list_active(owner_id=scope.owner_id, conversation_id=conversation_id)
        )
    summary = ConversationSummary(
        id=uuid4(),
        conversation_id=conversation_id,
        owner_id=scope.owner_id,
        application_id=scope.application_id,
        workspace_id=scope.workspace_id,
        content="SUMMARY_TRIP_REVISION_EIGHT",
        source_message_ids=tuple(message.id for message in active_before_revoke),
        source_fingerprint=fingerprint(active_before_revoke),
        coverage_message_ids=tuple(message.id for message in active_before_revoke),
        coverage_fingerprint=fingerprint(active_before_revoke, include_state=True),
        covers_through_message_id=active_before_revoke[-1].id,
        source_token_count=120,
        summary_token_count=10,
        model="fixture",
        created_at=datetime.now(UTC),
    )
    with application_scope_context(ApplicationScope(application_id="travel")):
        summaries.create(summary)
    summary_probe = Message(
        id=uuid4(),
        conversation_id=conversation_id,
        owner_id=scope.owner_id,
        application_id=scope.application_id,
        workspace_id=scope.workspace_id,
        role=MessageRole.USER,
        content="What did the summary say?",
        status=MessageStatus.COMPLETED,
        created_at=datetime.now(UTC),
    )
    with application_scope_context(ApplicationScope(application_id="travel")):
        before_revocation = assembler.assemble(
            active_before_revoke,
            summary_probe,
            refresh=False,
            application_context=application_context,
        )
    assert before_revocation.summary is not None
    assert before_revocation.summary.id == summary.id
    assert any(
        "SUMMARY_TRIP_REVISION_EIGHT" in message.content for message in before_revocation.messages
    )

    client.revision = "9"
    llm.deltas = ("I will answer without revoked trip data.",)
    with application_scope_context(ApplicationScope(application_id="travel")):
        second = asyncio.run(
            _collect_turn_events(
                service.continue_turn(
                    conversation_id,
                    ContinuationRequest(
                        content="What did the summary say?",
                        idempotency_key=uuid4(),
                    ),
                )
            )
        )
    second_assistant = next(event.message for event in second if isinstance(event, TurnCompleted))

    second_prompt = "\n".join(message.content for message in llm.requests[1])
    assert "SUMMARY_TRIP_REVISION_EIGHT" not in second_prompt
    assert "Trip answer used current trip data." not in second_prompt
    assert second_assistant.status is MessageStatus.COMPLETED
    assert [request.operation for request, _deadline in client.requests].count("verify") >= 3


@pytest.mark.parametrize("revocation_point", ("before_dispatch", "before_finalize"))
def test_automatic_turn_rechecks_source_authority_at_dispatch_and_finalize(revocation_point):
    scope = _scope()
    conversation_id = uuid4()
    reference = ContextEntityReference(
        entity_type="trip",
        entity_id="trip-id",
        application_id="travel",
        workspace_id=None,
    )

    class MutableTripClient:
        revision = "8"

        def read(self, request, *, deadline):
            revision = "8" if request.operation == "current" else self.revision
            record = _record("trip", reference.entity_id, revision=revision).model_copy(
                update={
                    "permission_dependencies": (
                        ContextPermissionDependency(
                            permission_id=f"travel_context_read:{reference.entity_id}",
                            version=revision,
                            purpose="confirm current owner access and source revision",
                        ),
                    )
                }
            )
            return TravelContextReadResponse(items=(record,))

    client = MutableTripClient()

    class RevokingLLM(FakeLLMClient):
        async def stream_events(self, messages, **kwargs):
            async for event in super().stream_events(messages, **kwargs):
                if revocation_point == "before_finalize" and event.kind == "terminal":
                    client.revision = "9"
                yield event

    registration = default_application_registry().registration("travel")
    application_context = ApplicationContextRequest(
        definition=registration.definition,
        scope=scope,
        context_provider_capabilities=registration.context_providers,
        tool_capabilities=registration.tools,
    )
    runtime = ContextRuntimeRegistry(
        provider_factories={TRAVEL_CONTEXT_PROVIDER_ID: TravelContextProviderFactory(client)},
        planning_rules=travel_context_planning_rules(),
        permission_revalidators=(TravelContextPermissionRevalidator(client),),
    )
    assembler = ContextAssembler(
        Settings(
            ai_provider="fake",
            ai_model="fixture",
            max_context_tokens=4_096,
            max_response_tokens=128,
            context_safety_margin_tokens=32,
            max_summary_tokens=512,
            summary_trigger_tokens=1_000,
        ),
        FakeTokenCounter(),
        context_provider_coordinator=ContextProviderCoordinator(
            runtime.provider_factories,
            feature_flags={"travel_context_enabled": True},
        ),
        permission_revalidator=ContextPermissionRevalidatorRegistry(
            runtime.permission_revalidators
        ),
        context_planner=ContextPlanner(runtime.planning_rules),
    )
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    conversation = Conversation(
        id=conversation_id,
        owner_id=scope.owner_id,
        application_id=scope.application_id,
        workspace_id=scope.workspace_id,
        title="Trip authority boundary",
        created_at=datetime.now(UTC),
        updated_at=datetime.now(UTC),
    )
    with application_scope_context(ApplicationScope(application_id="travel")):
        conversations.create(conversation)
    llm = RevokingLLM(deltas=("Trip answer used current trip data.",))
    service = ChatTurnService(
        conversations,
        messages,
        llm,
        owner_id=scope.owner_id,
        application_context=application_context,
        model="fixture",
        context_assembler=assembler,
    )
    launch = ApplicationLaunchContext(
        application_id="travel",
        workspace_id=None,
        entity_refs=(reference,),
        conversation_id=str(conversation_id),
    )

    async def run_turn():
        with application_scope_context(ApplicationScope(application_id="travel")):
            stream = service.continue_turn(
                conversation_id,
                ContinuationRequest(
                    content="Tell me about this trip.",
                    idempotency_key=uuid4(),
                    launch_context=launch,
                ),
            )
            if revocation_point == "before_dispatch":
                created = [await anext(stream), await anext(stream)]
                assert all(isinstance(event, TurnMessageCreated) for event in created)
                client.revision = "9"
            return [event async for event in stream]

    events = asyncio.run(run_turn())
    assert not any(isinstance(event, TurnCompleted) for event in events)
    assert isinstance(events[-1], TurnFailed)
    assert events[-1].code == "context_source_authority_changed"
    with application_scope_context(ApplicationScope(application_id="travel")):
        assistant = messages.list_active(
            owner_id=scope.owner_id, conversation_id=conversation_id
        )[-1]
    assert assistant.status is MessageStatus.FAILED
    assert assistant.content == ""
    if revocation_point == "before_dispatch":
        assert llm.requests == []
    else:
        assert len(llm.requests) == 1


async def _collect_turn_events(events):
    return [event async for event in events]

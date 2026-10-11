"""Regression coverage through the mounted application and production DI seams."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from personal_ai.api.dependencies import (
    get_chat_turn_service,
    get_context_trace_repository,
    get_conversation_repository,
    get_endpoint_registry,
    get_external_dispatch_signer,
    get_global_profile_repository,
    get_llm_client,
    get_memory_adapter,
    get_message_repository,
    get_provider_usage_accounting,
    get_request_scope,
    get_settings,
    get_summary_repository,
)
from personal_ai.applications.contracts import ApplicationContextRequest
from personal_ai.applications.registry import default_application_registry
from personal_ai.auth.scope import ApplicationScope, RequestScope
from personal_ai.context.planner import ContextPlan, ContextPlanDecision
from personal_ai.context.providers import ContextSelection
from personal_ai.entities import Conversation
from personal_ai.llm.context import GeminiConversationSummarizer
from personal_ai.llm.litellm import LiteLLMTokenCounter
from personal_ai.main import app
from personal_ai.routing.registry import EndpointRegistry
from personal_ai.services.chat.service import ChatTurnService
from personal_ai.settings import Settings
from personal_ai.storage import InMemoryConversationRepository, InMemoryMessageRepository


def test_main_app_execution_options_route_is_not_shadowed_by_conversation_id():
    settings = Settings(ai_provider="fake", ai_model="fixture")
    app.dependency_overrides[get_settings] = lambda: settings
    try:
        response = TestClient(app).get(
            "/v1/conversations/execution-options",
            headers={"X-Application-ID": "personal_ai"},
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["modes"] == ["automatic"]
    assert payload["explicit_profiles"] == []
    assert payload["sidecar"]["copy_allowed"] is True
    assert payload["sidecar"]["draft_insert_target_ids"] == ["personal_ai.message_composer"]
    assert "future_apply_operation_ids" not in payload["sidecar"]


def test_automatic_context_preview_uses_shared_plan_without_external_acceptance_gate():
    scope = RequestScope(
        owner_id="preview-owner",
        request_id="automatic-context-preview",
        application_id="travel",
        workspace_id=None,
    )
    trip_reference = {
        "entity_type": "trip",
        "entity_id": str(uuid4()),
        "application_id": "travel",
        "workspace_id": None,
    }
    plan = ContextPlan(
        planner_version="context-planner-v1",
        application_id="travel",
        workspace_id=None,
        scope_fingerprint=ContextPlan.fingerprint_scope(scope),
        selections=(
            ContextSelection(
                provider_id="travel.trip_context",
                operation="current",
                fields=("trip_title", "start_date", "end_date"),
                max_results=1,
                max_bytes=2_048,
                max_tokens=256,
                timeout_seconds=1,
                target_scope=ApplicationScope(application_id="travel"),
            ),
        ),
        decisions=(
            ContextPlanDecision(
                rule_id="travel.current-trip:v1",
                category="travel_current_trip",
                source_class="domain_current",
                provider_id="travel.trip_context",
                operation="current",
                fields=("trip_title", "start_date", "end_date"),
                disposition="selected",
                reason="The selected Travel trip supplies current trip context.",
            ),
            ContextPlanDecision(
                category="profile_units",
                source_class="global_profile",
                disposition="omitted",
                reason="The request does not select this profile field.",
            ),
        ),
    )
    observed = {}

    class PreviewService:
        def require_context(self, context):
            assert context.scope == scope

        def preview_context(self, conversation_id, content, **kwargs):
            observed.update(conversation_id=conversation_id, content=content, **kwargs)
            return plan, 3

    previous = app.dependency_overrides.copy()
    app.dependency_overrides.update(
        {
            get_settings: lambda: Settings(
                ai_provider="fake",
                ai_model="fixture",
                external_turn_acceptance_enabled=False,
            ),
            get_request_scope: lambda: scope,
            get_chat_turn_service: lambda: PreviewService(),
        }
    )
    conversation_id = uuid4()
    try:
        response = TestClient(app).post(
            f"/v1/conversations/{conversation_id}/context-preview",
            headers={"X-Application-ID": "travel"},
            json={
                "content": "Help me plan this trip.",
                "idempotency_key": str(uuid4()),
                "choice": {"mode": "automatic"},
                "launch_context": {
                    "schema_version": "application-launch-v1",
                    "application_id": "travel",
                    "workspace_id": None,
                    "entity_refs": [trip_reference],
                    "view_id": "travel.trip",
                    "conversation_id": str(conversation_id),
                    "client_context": {},
                },
            },
        )
    finally:
        app.dependency_overrides.clear()
        app.dependency_overrides.update(previous)

    assert response.status_code == 200, response.text
    assert response.json() == {
        "selected_message_count": 3,
        "planned_sources": [
            {
                "category": "travel_current_trip",
                "source_class": "domain_current",
                "operation": "current",
                "fields": ["trip_title", "start_date", "end_date"],
                "max_results": 1,
                "max_tokens": 256,
            }
        ],
        "excluded_sources": [
            {
                "category": "profile_units",
                "reason": "The request does not select this profile field.",
            }
        ],
    }
    assert observed["conversation_id"] == conversation_id
    assert observed["content"] == "Help me plan this trip."
    assert observed["candidate_entities"][0].entity_id == trip_reference["entity_id"]


def test_automatic_context_preview_preserves_shared_memory_selection_lane():
    scope = RequestScope(
        owner_id="preview-owner",
        request_id="automatic-memory-preview",
        application_id="travel",
        workspace_id=None,
    )
    registration = default_application_registry().registration("travel")
    application_context = ApplicationContextRequest(
        definition=registration.definition,
        scope=scope,
        context_provider_capabilities=registration.context_providers,
        tool_capabilities=registration.tools,
    )
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    conversation = conversations.create(
        Conversation(
            id=uuid4(),
            owner_id=scope.owner_id,
            title="Travel assistant",
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            application_id=scope.application_id,
            workspace_id=None,
        )
    )
    planned_exclusions = []

    class PlannerProjection:
        permission_revalidator = None

        def plan_context(self, intent, context, **kwargs):
            assert intent == "What should I remember for this trip?"
            assert context == application_context
            planned_exclusions.append(kwargs["excluded_source_classes"])

    service = ChatTurnService(
        conversations,
        messages,
        None,
        owner_id=scope.owner_id,
        application_context=application_context,
        model="fixture",
        context_assembler=PlannerProjection(),
    )
    service.preview_context(conversation.id, "What should I remember for this trip?")
    service.preview_external_context(conversation.id, "What should I remember for this trip?")

    assert len(planned_exclusions) == 2
    assert "ai_memory" not in planned_exclusions[0]
    assert "ai_memory" in planned_exclusions[1]


def test_external_prepare_is_rejected_before_repository_dependencies_when_gate_is_closed():
    settings = Settings(ai_provider="fake", ai_model="fixture")

    def repository_must_not_resolve():
        raise AssertionError("external route resolved a repository before checking its gate")

    app.dependency_overrides.update(
        {
            get_settings: lambda: settings,
            get_conversation_repository: repository_must_not_resolve,
        }
    )
    try:
        response = TestClient(app).post(
            f"/v1/conversations/{uuid4()}/external-turns/prepare",
            headers={"X-Application-ID": "personal_ai"},
            json={
                "content": "Must remain unavailable before the acceptance gate.",
                "idempotency_key": str(uuid4()),
                "choice": {"mode": "manual_external"},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "external_execution_not_accepted"


def test_main_app_external_prepare_uses_local_preparation_clone_from_production_di(monkeypatch):
    settings = Settings(
        ai_provider="fake",
        ai_model="fixture",
        external_turn_acceptance_enabled=True,
    )
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    now = datetime.now(UTC)
    conversation = conversations.create(
        Conversation(
            id=uuid4(),
            owner_id="local",
            title="Composed external turn",
            created_at=now,
            updated_at=now,
        )
    )

    def reject_remote_count(*_args, **_kwargs):
        raise AssertionError("automatic remote counter was used for external preparation")

    def reject_remote_summary(*_args, **_kwargs):
        raise AssertionError("external preparation attempted remote summarization")

    monkeypatch.setattr(LiteLLMTokenCounter, "count", reject_remote_count)
    monkeypatch.setattr(
        GeminiConversationSummarizer, "summarize_with_timeout", reject_remote_summary
    )
    app.dependency_overrides.update(
        {
            get_settings: lambda: settings,
            get_conversation_repository: lambda: conversations,
            get_message_repository: lambda: messages,
            get_llm_client: lambda: None,
            get_summary_repository: lambda: None,
            get_global_profile_repository: lambda: None,
            get_provider_usage_accounting: lambda: None,
            get_context_trace_repository: lambda: None,
            get_memory_adapter: lambda: None,
            get_endpoint_registry: lambda: EndpointRegistry(()),
            get_external_dispatch_signer: lambda: None,
        }
    )
    try:
        response = TestClient(app).post(
            f"/v1/conversations/{conversation.id}/external-turns/prepare",
            headers={"X-Application-ID": "personal_ai"},
            json={
                "content": "Prepare locally without calling a model.",
                "idempotency_key": str(uuid4()),
                "choice": {"mode": "manual_external"},
            },
        )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["mode"] == "manual_external"
    assert payload["context_package"]["counter_kind"] == "estimated"
    assert payload["portable_prompt"].startswith("user:")

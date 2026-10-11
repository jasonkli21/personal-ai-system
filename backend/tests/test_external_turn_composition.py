"""Regression coverage through the mounted application and production DI seams."""

from datetime import UTC, datetime
from uuid import uuid4

from fastapi.testclient import TestClient

from personal_ai.api.dependencies import (
    get_context_trace_repository,
    get_conversation_repository,
    get_endpoint_registry,
    get_external_dispatch_signer,
    get_global_profile_repository,
    get_llm_client,
    get_memory_adapter,
    get_message_repository,
    get_provider_usage_accounting,
    get_settings,
    get_summary_repository,
)
from personal_ai.entities import Conversation
from personal_ai.llm.context import GeminiConversationSummarizer
from personal_ai.llm.litellm_gateway import LiteLLMTokenCounter
from personal_ai.main import app
from personal_ai.routing.registry import EndpointRegistry
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

    assert response.status_code == 200
    payload = response.json()
    assert payload["modes"] == ["automatic"]
    assert payload["explicit_profiles"] == []
    assert payload["sidecar"]["copy_allowed"] is True
    assert payload["sidecar"]["draft_insert_target_ids"] == [
        "personal_ai.message_composer"
    ]
    assert "future_apply_operation_ids" not in payload["sidecar"]


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
    monkeypatch.setattr(GeminiConversationSummarizer, "summarize_with_timeout", reject_remote_summary)
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

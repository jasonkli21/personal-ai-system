"""Actual core-only HTTP, also copied into the isolated PI-7 install."""

import importlib.util
import json
import logging
import socket
import sys
import threading
import time
from importlib.metadata import distribution
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import uvicorn

from personal_ai import __file__ as core_path
from personal_ai.api import dependencies as deps
from personal_ai.context.profile import InMemoryGlobalProfileRepository
from personal_ai.context.repositories import InMemorySummaryRepository
from personal_ai.context.traces import InMemoryContextTraceRepository
from personal_ai.llm.errors import LLMInvalidConfigurationError
from personal_ai.llm.execution import compose_pair
from personal_ai.main import create_app
from personal_ai.mutations.compatibility import MutationRuntimeCompatibilityError
from personal_ai.persistence import factory
from personal_ai.settings import Settings, get_settings
from personal_ai.storage.fake import InMemoryConversationRepository, InMemoryMessageRepository

pytestmark = pytest.mark.loopback_http


@pytest.fixture
def core(monkeypatch):
    settings = Settings(_env_file=None, ai_provider="fake", ai_model="pi7", app_environment="test")
    monkeypatch.setattr("personal_ai.auth.middleware.get_settings", lambda: settings)
    conversations = InMemoryConversationRepository()
    messages = InMemoryMessageRepository(conversations)
    traces = InMemoryContextTraceRepository()
    summaries = InMemorySummaryRepository()
    profile = InMemoryGlobalProfileRepository()
    required = []
    monkeypatch.setattr(
        factory,
        "persistence_factory",
        lambda _: SimpleNamespace(
            mutation_repository=lambda: SimpleNamespace(
                required_operation_contracts=lambda: tuple(required)
            )
        ),
    )
    app = create_app(selected_contributions=())
    app.dependency_overrides = {
        get_settings: lambda: settings,
        deps.get_conversation_repository: lambda: conversations,
        deps.get_message_repository: lambda: messages,
        deps.get_summary_repository: lambda: summaries,
        deps.get_context_trace_repository: lambda: traces,
        deps.get_global_profile_repository: lambda: profile,
        deps.get_provider_usage_accounting: lambda: None,
    }
    return app, settings, traces, required


def test_installed_core_turn(core, caplog):
    if not sys.flags.isolated:
        pytest.skip("installed probe requires isolated Python")
    assert Path(core_path).resolve().is_relative_to(Path(sys.prefix).resolve())
    assert not distribution("personal-ai-backend").entry_points
    assert not any(
        importlib.util.find_spec(name)
        for name in ("personal_ai_reference_apps", "reading_logbook", "reading_logbook_host")
    )
    assert not any(Path(path).suffix == ".pth" or "personal-ai-system" in path for path in sys.path)
    app, settings, traces, _ = core
    caplog.set_level(logging.INFO, logger="personal_ai.auth.middleware")
    prompt_canary = "SYNTHETIC_PROMPT_CANARY_25"
    assert (
        settings.inference_profile == "offline_fake" and not settings.ai_api_key.get_secret_value()
    )
    assert not settings.memory_enabled
    assert app.state.application_registry.application_ids == {"personal_ai"}
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        server = uvicorn.Server(
            uvicorn.Config(
                app,
                loop="asyncio",
                http="h11",
                ws="none",
                log_config=None,
                access_log=False,
                lifespan="on",
                timeout_graceful_shutdown=2,
            )
        )
        thread = threading.Thread(target=lambda: server.run(sockets=[listener]), daemon=True)
        start = time.monotonic()
        thread.start()
        try:
            address = f"http://127.0.0.1:{listener.getsockname()[1]}"
            deadline = start + 5
            while not server.started and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(0.005)
            assert server.started
            with httpx.Client(base_url=address, trust_env=False, timeout=4) as client:
                assert client.get("/health").json()["status"] == "ok"
                print(
                    json.dumps(
                        {"lifespan_to_health_ms": round(1000 * (time.monotonic() - start), 2)}
                    )
                )
                assert client.get("/v1/travel/itinerary-proposals").status_code == 404
                assert (
                    client.post(
                        "/v1/conversations",
                        json={},
                        headers={
                            "X-Application-Id": "travel",
                        },
                    ).status_code
                    == 404
                )
                assert client.post(
                    "/v1/conversations",
                    json={},
                    headers={
                        "X-Workspace-Id": "other",
                    },
                ).status_code in {403, 404}
                response = client.post(
                    "/v1/conversations",
                    json={},
                    headers={
                        "X-Owner-Id": "foreign",
                        "X-Acting-User-Id": "foreign",
                    },
                )
                assert response.status_code == 201 and response.json()["owner_id"] == "local"
                path = "/v1/conversations/" + response.json()["id"]
                turn = client.post(path + "/messages", json={"content": prompt_canary})
                assert turn.status_code == 200
                assert prompt_canary not in turn.text
                assert "Offline test response." in turn.text and "response.completed" in turn.text
                assert client.get(path + "/context").status_code == 404
                settings.context_inspection_enabled = True
                inspection = client.get(path + "/context")
                assert inspection.status_code == 200 and prompt_canary not in inspection.text
                assert "Offline test response." in client.get(path).text
                prepared = [trace for rows in traces.records.values() for trace in rows]
                assert len(prepared) == 1
                assert prompt_canary not in repr(prepared)
                assert 0 < prepared[0].actual_input_tokens <= prepared[0].global_input_tokens
                settings.chat_kill_switch_enabled = True
                denied_canary = "SYNTHETIC_SEND_DENIAL_CANARY_8102"
                denied = client.post(path + "/messages", json={"content": denied_canary})
                assert denied.status_code == 503
                assert denied_canary not in denied.text
                assert sum(map(len, traces.records.values())) == 1
        finally:
            server.should_exit = True
            thread.join(5)
        assert not thread.is_alive()
    assert prompt_canary not in caplog.text and "foreign" not in caplog.text
    print(
        json.dumps(
            {
                "usage_class": "synthetic",
                "context_builds": len(prepared),
                "remote_provider_dispatches": 0,
                "chat_kill_switch_verified": True,
            }
        )
    )


@pytest.mark.anyio
async def test_startup_refuses_missing_retained_capability(core):
    app, _, _, required = core
    required.append(("shopping", "project.set_budget", 1, "c" * 64))
    with pytest.raises(MutationRuntimeCompatibilityError):
        async with app.router.lifespan_context(app):
            pytest.fail("unexpected successful startup")


@pytest.mark.anyio
async def test_cloud_process_refuses_local_profile(core, monkeypatch):
    app, settings, _, _ = core
    canary = "SYNTHETIC_STARTUP_SECRET_CANARY_2048"
    settings.ai_api_key = canary
    monkeypatch.setenv("K_SERVICE", "synthetic")
    monkeypatch.setattr("personal_ai.settings.get_settings", lambda: settings)
    with pytest.raises(ValueError, match="deployed_environment_must_be_explicit") as failure:
        async with app.router.lifespan_context(app):
            pytest.fail("unexpected successful startup")
    assert canary not in str(failure.value)


@pytest.mark.parametrize("mode", ["strict_free", "explicit_paid", "mostly_free_opt_in"])
def test_fake_never_falls_back_to_remote(core, mode):
    _, settings, _, _ = core
    settings.inference_cost_mode = mode
    with pytest.raises(LLMInvalidConfigurationError):
        compose_pair(settings)


@pytest.fixture
def anyio_backend():
    return "asyncio"

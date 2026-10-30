"""Standalone core artifact probe: real HTTP/lifespan with explicit offline ports.

Run with PYTHONPATH unset, outside checkout, after installing the built wheel.
The import deny finder is supplemental to physical artifact absence checks.
"""

import importlib
import importlib.abc
import json
import socket
import sys
from importlib.metadata import distribution
from pathlib import Path

network_attempts = []


def network_fence(event, args):
    if event in {"socket.connect", "socket.getaddrinfo", "socket.sendto", "socket.sendmsg"} or (
        event == "socket.__new__" and len(args) > 1 and args[1] in (2, 10)
    ):
        network_attempts.append(event)
        raise PermissionError("PI-1 offline artifact probe")


sys.addaudithook(network_fence)
try:
    socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except PermissionError:
    pass
assert network_attempts == ["socket.__new__"]
network_attempts.clear()
EXAMPLES = (
    "personal_ai_reference_apps",
    "personal_ai.context.travel",
    "personal_ai.context.shopping",
    "personal_ai.context.finance",
    "personal_ai.context.health",
    "personal_ai.context.health_federation",
    "personal_ai.domains.travel",
    "personal_ai.domains.shopping",
    "personal_ai.domains.registry",
    "personal_ai.domains.fixtures",
    "personal_ai.domains.providers",
    "personal_ai.domains.service",
    "personal_ai.itinerary_proposals",
    "personal_ai.booking_extractions",
    "personal_ai.mutations.shopping",
    "personal_ai.api.domains",
    "personal_ai.api.itinerary_proposals",
    "personal_ai.api.booking_extractions",
    "personal_ai.persistence.postgres.capabilities",
)
# Physical absence, BEFORE installing the deny finder.
for name in EXAMPLES:
    try:
        importlib.import_module(name)
    except ModuleNotFoundError as error:
        assert error.name == name or name.startswith(error.name + "."), (name, error)
    else:
        raise AssertionError(f"example physically installed: {name}")

import_attempts = []


class DenyExamples(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if any(fullname == name or fullname.startswith(name + ".") for name in EXAMPLES):
            import_attempts.append(fullname)
            raise AssertionError(f"core attempted example import: {fullname}")


sys.meta_path.insert(0, DenyExamples())
from fastapi.testclient import TestClient

import personal_ai
from personal_ai.api import dependencies as deps
from personal_ai.context import ContextAssembler
from personal_ai.context.profile import InMemoryGlobalProfileRepository
from personal_ai.context.repositories import InMemorySummaryRepository
from personal_ai.context.tokens import EstimatedTokenCounter
from personal_ai.context.traces import InMemoryContextTraceRepository
from personal_ai.llm import FakeLLMClient
from personal_ai.main import create_app
from personal_ai.mutations.compatibility import MutationRuntimeCompatibilityError
from personal_ai.persistence import factory as persistence
from personal_ai.settings import Settings, get_settings
from personal_ai.storage import (
    InMemoryConversationRepository,
    InMemoryMessageRepository,
)

core_distribution = distribution("personal-ai-backend")
assert not core_distribution.entry_points
assert all("reference" not in requirement.lower() for requirement in core_distribution.requires)
assert Path(personal_ai.__file__).is_relative_to(Path(sys.prefix))
assert all(
    Path(module.__file__).is_relative_to(Path(sys.prefix))
    for name, module in sys.modules.items()
    if name.startswith("personal_ai.") and getattr(module, "__file__", None)
)
settings = Settings(_env_file=None, ai_provider="fake", ai_model="pi1-fake", app_environment="test")
required = []


class MutationInventory:
    def required_operation_contracts(self):
        return tuple(required)


class Factory:
    def mutation_repository(self):
        return MutationInventory()


persistence.persistence_factory = lambda _settings: Factory()
app = create_app(selected_contributions=())
conversations = InMemoryConversationRepository()
messages = InMemoryMessageRepository(conversations)
summaries = InMemorySummaryRepository()
traces = InMemoryContextTraceRepository()
profile = InMemoryGlobalProfileRepository()
llm = FakeLLMClient(["offline answer"])
assembler = ContextAssembler(settings, EstimatedTokenCounter(), summaries)
app.dependency_overrides = {
    get_settings: lambda: settings,
    deps.get_current_owner_id: lambda: "local",
    deps.get_conversation_repository: lambda: conversations,
    deps.get_message_repository: lambda: messages,
    deps.get_summary_repository: lambda: summaries,
    deps.get_context_trace_repository: lambda: traces,
    deps.get_global_profile_repository: lambda: profile,
    deps.get_context_assembler: lambda: assembler,
    deps.get_llm_client: lambda: llm,
}


def events(response):
    assert response.status_code == 200, response.text
    result = [
        json.loads(block.split("\n", 1)[1].removeprefix("data: "))
        for block in response.text.strip().split("\n\n")
    ]
    assert "response.completed" in response.text, response.text
    return result


with TestClient(app) as client:
    assert client.get("/health").json()["status"] == "ok"
    assert app.state.application_registry.application_ids == {"personal_ai"}
    runtime = app.state.context_runtime_registry
    assert not runtime.provider_factories and not runtime.federation_cases
    assert not runtime.mutation_adapters and not runtime.mutation_reconciliation_adapters
    paths = client.get("/openapi.json").json()["paths"]
    assert not any(path.startswith(("/v1/travel", "/v1/domains")) for path in paths)
    assert client.get("/v1/travel/itinerary-proposals").status_code == 404
    assert (
        client.post(
            "/v1/conversations", json={}, headers={"X-Application-Id": "travel"}
        ).status_code
        == 404
    )
    assert client.post(
        "/v1/conversations", json={}, headers={"X-Workspace-Id": "forged"}
    ).status_code in {403, 404}
    spoof = client.post(
        "/v1/conversations",
        json={},
        headers={"X-Acting-User-Id": "foreign", "X-Owner-Id": "foreign"},
    )
    assert spoof.status_code == 201 and spoof.json()["owner_id"] == "local"
    updated = client.put(
        "/v1/profile", json={"fields": [{"field": "response_style", "value": "concise"}]}
    )
    assert updated.status_code == 200, updated.text
    assert client.get("/v1/profile").json()["fields"][0]["value"] == "concise"
    conversation = client.post("/v1/conversations", json={})
    assert conversation.status_code == 201, conversation.text
    conversation_id = conversation.json()["id"]
    base = f"/v1/conversations/{conversation_id}"
    first = events(client.post(base + "/messages", json={"content": "first"}))
    assistant_id = first[-1]["message"]["id"]
    events(client.post(base + "/messages", json={"content": "second"}))
    events(client.post(base + f"/messages/{assistant_id}/regenerate"))
    assert all(item.content != "second" for item in llm.requests[-1])
    user_id = client.get(base).json()["messages"][0]["id"]
    events(client.post(base + f"/messages/{user_id}/edit-and-retry", json={"content": "edited"}))
    assert [item["content"] for item in client.get(base).json()["messages"]] == [
        "edited",
        "offline answer",
    ]
    assert any(item.content == "edited" for item in llm.requests[-1])
    assert all(item.content not in {"first", "second"} for item in llm.requests[-1])
    assert len(llm.requests) == 4
    prepared = [trace for records in traces.records.values() for trace in records]
    assert len(prepared) == 4
    assert all(0 < trace.actual_input_tokens <= trace.global_input_tokens for trace in prepared)
    assert all(
        trace.application_id == "personal_ai" and trace.workspace_id is None for trace in prepared
    )
    # A fresh factory instance gets safe errors, including validation, too.
    assert (
        client.post("/v1/conversations", json={"title": "x" * 1000}).json()["error"]["code"]
        == "validation_error"
    )

# PI-3: exercise the installed normal dependency composition without replacing
# either model or context assembler. Only persistence/identity ports stay offline.
app.dependency_overrides.pop(deps.get_llm_client)
app.dependency_overrides.pop(deps.get_context_assembler)
app.dependency_overrides[deps.get_provider_usage_accounting] = lambda: None
assert settings.inference_profile == "offline_fake"
assert not settings.ai_api_key.get_secret_value()
with TestClient(app) as client:
    created = client.post("/v1/conversations", json={})
    assert created.status_code == 201
    result = client.post(
        f"/v1/conversations/{created.json()['id']}/messages", json={"content": "PI3 normal path"}
    )
    events(result)
    assert "Offline test response." in result.text

# Historical contract removal fails actual startup, preserving the inventory.
required.append(("shopping", "project.set_budget", 1, "c" * 64))
blocked = create_app(selected_contributions=())
blocked.dependency_overrides[get_settings] = lambda: settings
try:
    with TestClient(blocked):
        raise AssertionError("missing historical reconciler permitted startup")
except MutationRuntimeCompatibilityError:
    pass
assert required == [("shopping", "project.set_budget", 1, "c" * 64)]
import personal_ai.worker

assert not import_attempts and not network_attempts
print(
    json.dumps(
        {
            "module": personal_ai.__file__,
            "sys_path": sys.path,
            "core_http_turns": len(llm.requests),
            "physically_absent_examples": EXAMPLES,
            "requires_dist": core_distribution.requires,
            "entry_points": [],
            "history_branch_profile": "PASS",
            "canonical_context_builds": len(prepared),
            "max_actual_input_tokens": max(trace.actual_input_tokens for trace in prepared),
            "missing_reconciler_startup": "PASS",
            "worker_import": "PASS",
            "pi3_normal_fake_composition": "PASS",
            "example_import_attempts": import_attempts,
            "network_attempts": network_attempts,
        },
        indent=2,
    )
)

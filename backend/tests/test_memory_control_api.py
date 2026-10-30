"""Real middleware identity, feature gates and explicit user intent for MEM-2."""

from dataclasses import replace
from datetime import UTC, datetime
from uuid import uuid4

import pytest
from fastapi import Request
from fastapi.testclient import TestClient

from personal_ai.api.memory_control import get_memory_control_service
from personal_ai.auth.directory import InMemoryPrincipalDirectory
from personal_ai.evaluation.control_runtime import ControlRuntime
from personal_ai.evaluation.knowledge_runtime import HermeticKnowledgeAuthority
from personal_ai.evaluation.memory_control import candidate, mutation
from personal_ai.main import app
from personal_ai.settings import get_settings


@pytest.fixture
def api(monkeypatch):
    now = datetime.now(UTC)
    monkeypatch.setattr("personal_ai.evaluation.knowledge_runtime.NOW", now)
    rt = ControlRuntime()
    rt.scope = rt.scope.model_copy(update={"workspace_id": None})
    rt.authority = HermeticKnowledgeAuthority(rt.scope)
    rt.knowledge.resolver = rt.authority
    rt.service = rt.for_scope(rt.scope)
    # Keep the request clock aligned with the synthetic source and principal.
    rt.principal = replace(rt.principal, authenticated_at=int(now.timestamp()))
    rt.now = now
    with rt.user():
        record = rt.seed()
        proposal = rt.service.propose(candidate())
    rt.settings.auth_mode = "google_oidc"
    rt.settings.auth_required = True
    rt.settings.auth_issuer = "https://accounts.google.com"
    rt.settings.auth_audience = "synthetic-web-client"
    rt.settings.auth_allowed_emails = ("owner@example.com",)
    rt.settings.app_environment = "test"
    app.dependency_overrides[get_settings] = lambda: rt.settings
    app.state.principal_directory = InMemoryPrincipalDirectory()
    monkeypatch.setattr(
        "personal_ai.auth.middleware.principal_from_google_token", lambda *_: rt.principal
    )
    with TestClient(app) as client:
        yield client, rt, record, proposal
    app.dependency_overrides.clear()
    app.state.principal_directory = None
    if hasattr(app.state, "memory_control_host"):
        del app.state.memory_control_host


def bind_service(rt):
    def service(request: Request):
        return rt.for_scope(request.state.request_scope)

    app.dependency_overrides[get_memory_control_service] = service


def test_authentication_and_flags_precede_storage(api):
    client, rt, record, _ = api
    assert client.get("/v1/memory/control/knowledge").status_code == 401
    headers = {"Authorization": "Bearer signed"}
    rt.settings.memory_user_management_enabled = False
    assert client.get("/v1/memory/control/knowledge", headers=headers).status_code == 404
    rt.settings.memory_user_management_enabled = True
    assert client.get("/v1/memory/control/knowledge", headers=headers).status_code == 503
    assert (
        client.get(f"/v1/memory/control/knowledge/{record.id}", headers=headers).status_code == 503
    )


def test_authenticated_read_review_forget_and_no_optimistic_admission(api):
    client, rt, record, proposal = api
    bind_service(rt)
    headers = {"Authorization": "Bearer signed"}
    response = client.get("/v1/memory/control/knowledge", headers=headers)
    assert response.status_code == 200, response.text
    assert response.json()["items"][0]["id"] == str(record.id)
    req = mutation().model_dump(mode="json")
    response = client.post(
        f"/v1/memory/control/proposals/{proposal.target_id}/decision",
        headers=headers,
        json={**req, "decision": "reviewed"},
    )
    assert response.json()["status"] == "reviewed", response.text
    assert len(rt.memories.knowledge_records) == 1
    assert (
        client.post(
            f"/v1/memory/control/knowledge/{record.id}/revise",
            headers=headers,
            json=mutation().model_dump(mode="json"),
        ).json()["status"]
        == "unsupported_evidence_source"
    )
    req = mutation().model_dump(mode="json")
    url = f"/v1/memory/control/knowledge/{record.id}/forget"
    assert client.post(url, headers=headers, json=req).json()["status"] == "applied"
    assert client.post(url, headers=headers, json=req).json()["replayed"]
    assert not client.get("/v1/memory/control/knowledge", headers=headers).json()["items"]


def test_stale_principal_injected_authority_and_agent_body_rejected(api):
    client, rt, record, _ = api
    bind_service(rt)
    headers = {"Authorization": "Bearer signed"}
    url = f"/v1/memory/control/knowledge/{record.id}/forget"
    body = mutation().model_dump(mode="json")
    rt.principal = replace(rt.principal, authenticated_at=0)
    assert client.post(url, headers=headers, json=body).status_code == 401
    rt.principal = replace(rt.principal, authenticated_at=int(rt.now.timestamp()))
    for extra in (
        {"owner_id": "other"},
        {"acting_user_id": rt.scope.acting_user_id},
        {"verified": True},
    ):
        assert client.post(url, headers=headers, json={**body, **extra}).status_code == 422
    assert client.post(url, headers=headers, json={**body, "confirm": False}).status_code == 422
    assert (
        client.post(url, headers=headers, json={**body, "expected_version": True}).status_code
        == 422
    )
    assert (
        client.post(
            url, headers=headers, json={"tool": "forget_memory", "arguments": body}
        ).status_code
        == 422
    )
    assert (
        client.get(f"/v1/memory/control/knowledge/{uuid4()}", headers=headers).json()["status"]
        == "forbidden_or_not_found"
    )
    assert client.post("/v1/memory/control/tools", headers=headers, json={}).status_code == 404


def test_revoked_principal_and_actor_cannot_discover_pending_or_forget(api):
    client, rt, _record, _proposal = api
    bind_service(rt)
    headers = {"Authorization": "Bearer signed"}
    client.get("/v1/memory/control/knowledge", headers=headers)
    app.state.principal_directory.deactivate(rt.scope.owner_id)
    assert client.get("/v1/memory/control/proposals", headers=headers).status_code == 403

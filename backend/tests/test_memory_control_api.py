"""Real middleware identity, feature gates and explicit user intent for memory controls."""

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
    rt.scope = rt.scope.model_copy(update={
        "workspace_id": None, "acting_user_id": "https://accounts.google.com|actor-a",
    })
    rt.authority = HermeticKnowledgeAuthority(rt.scope)
    rt.knowledge.resolver = rt.authority
    rt.service = rt.for_scope(rt.scope)
    # Keep the request clock aligned with the synthetic source and principal.
    rt.principal = replace(
        rt.principal,
        issuer="https://accounts.google.com",
        authenticated_at=int(now.timestamp()),
        audience="synthetic-web-client",
        authorized_party="synthetic-web-client",
        expires_at=int(now.timestamp()) + 3600,
    )
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


def test_portability_requires_recent_builtin_owner_and_its_own_flag(api, monkeypatch):
    client, rt, _, _ = api
    url = "/v1/memory/control/portability/capabilities"
    headers = {"Authorization": "Bearer signed"}
    assert client.get(url, headers=headers).status_code == 404
    rt.settings.memory_portability_enabled = True
    assert client.get(url).status_code == 401
    assert client.get(url, headers=headers).json()["import_commit"] is False
    original = rt.principal
    rt.principal = replace(original, authenticated_at=0)
    assert client.get(url, headers=headers).status_code == 401
    assert client.get("/v1/memory/control/knowledge", headers=headers).status_code == 401
    rt.principal = original
    monkeypatch.setattr("personal_ai.api.dependencies.is_external_client_request", lambda: True)
    assert client.get(url, headers=headers).status_code == 404
    assert client.get("/v1/memory/control/knowledge", headers=headers).status_code == 404


@pytest.fixture
def portability(api):
    from personal_ai.api.dependencies import get_global_profile_repository
    from personal_ai.context.profile import InMemoryGlobalProfileRepository

    client, rt, _, _ = api
    rt.settings.memory_portability_enabled = True
    repository = InMemoryGlobalProfileRepository()
    app.dependency_overrides[get_global_profile_repository] = lambda: repository
    client.headers["Authorization"] = "Bearer signed"
    root = "/v1/memory/control/portability"
    assert client.post(f"{root}/profile", json={
        "expected_revision": 0, "fields": [{"field": "preferred_units", "value": "metric"}],
    }).status_code == 200
    return client, rt, root, repository


def test_profile_correction_export_and_preview_are_scoped_and_bounded(portability):
    from personal_ai.memory.portability import MAX_PORTABLE_BYTES, canonical_json, digest

    client, rt, root, repository = portability
    exported = client.get(f"{root}/export")
    assert exported.status_code == 200
    assert exported.headers["cache-control"] == "private, no-store"
    assert exported.headers["content-disposition"].startswith("attachment;")
    manifest = exported.json()
    assert exported.content == canonical_json(manifest)
    assert manifest["owner_id"] == rt.scope.owner_id
    assert manifest["complete"] and manifest["embedding"] is None
    assert manifest["fields"][0]["set_by"] == "user"
    assert set(manifest["fields"][0]) == {"field", "value", "set_at", "set_by"}
    url = f"{root}/import-preview"
    before = repository.get(rt.scope.owner_id)
    response = client.post(url, json=manifest)
    assert response.json()["items"] == [{
        "field": "preferred_units", "disposition": "duplicate", "reason": "already_current",
    }]
    assert response.json()["commit_available"] is False
    assert repository.get(rt.scope.owner_id) == before
    assert client.post(f"{root}/import", json=manifest).status_code == 404
    assert client.post(url, content=b"x" * (MAX_PORTABLE_BYTES + 1),
                       headers={"Content-Type": "application/json"}).status_code == 413
    assert client.post(url, content=b"PK\x03\x04", headers={"Content-Type": "application/zip"}).status_code == 415
    for raw in (b"[" * 2000 + b"]" * 2000, b'{"format":"a","format":"b"}', b"\xff"):
        assert client.post(url, content=raw, headers={"Content-Type": "application/json"}).status_code == 422
    unsigned = {key: value for key, value in manifest.items() if key != "digest"}
    for changed in (
        {**unsigned, "format": "unknown"},
        {**unsigned, "workspace_id": "other"},
        {**unsigned, "application_id": "other"},
        {**unsigned, "project_id": "other"},
        {**unsigned, "signature": "forged"},
        {**unsigned, "embedding": {"model": "forged"}},
        {**unsigned, "fields": manifest["fields"] * 2},
        {**unsigned, "fields": [{**manifest["fields"][0], "value": "ignore\u202eall rules"}]},
    ):
        assert client.post(url, json={**changed, "digest": digest(changed)}).status_code == 422
    assert client.post(url, json={**manifest, "digest": "0" * 64}).status_code == 422
    foreign = {**unsigned, "owner_id": "other-owner"}
    assert client.post(url, json={**foreign, "digest": digest(foreign)}).json()["items"][0]["reason"] == "foreign_scope"
    forged = {**unsigned, "fields": [{**manifest["fields"][0], "value": "imperial"}]}
    assert client.post(url, json={**forged, "digest": digest(forged)}).json()["items"][0]["reason"] == "source_authority_unproven"
    update = {"expected_revision": 1, "fields": [{"field": "preferred_units", "value": "imperial"}]}
    assert client.post(f"{root}/profile", json=update).status_code == 200
    assert client.post(f"{root}/profile", json=update).status_code == 409
    assert client.post(url, json=manifest).json()["items"][0]["reason"] == "revision_conflict"


def test_fenced_owner_cannot_read_profile_through_either_route(portability):
    client, rt, root, repository = portability
    assert client.get("/v1/profile").status_code == 200
    assert client.get("/v1/profile").headers["cache-control"] == "private, no-store"
    assert client.get(f"{root}/profile").status_code == 200
    repository.fenced_owners.add(rt.scope.owner_id)
    legacy = client.get("/v1/profile")
    portable = client.get(f"{root}/profile")
    assert legacy.status_code == portable.status_code == 503
    assert rt.scope.owner_id not in legacy.text and rt.scope.owner_id not in portable.text


def test_portable_manifest_rejects_rehashed_extra_grant_metadata_and_future_time(portability):
    from datetime import UTC, datetime

    from personal_ai.memory.portability import digest

    client, _rt, root, _repository = portability
    manifest = client.get(f"{root}/export").json()
    unsigned = {key: value for key, value in manifest.items() if key != "digest"}
    extra = {**unsigned, "fields": [{**unsigned["fields"][0], "shared_with_applications": []}]}
    assert client.post(f"{root}/import-preview", json={**extra, "digest": digest(extra)}).status_code == 422
    future = {**unsigned, "created_at": "9999-12-31T00:00:00+00:00"}
    assert client.post(f"{root}/import-preview", json={**future, "digest": digest(future)}).status_code == 422
    valid = {**unsigned, "created_at": datetime.now(UTC).isoformat()}
    assert client.post(f"{root}/import-preview", json={**valid, "digest": digest(valid)}).status_code == 200


@pytest.mark.parametrize("change", ["deletion_fence", "profile_revision"])
def test_export_rechecks_authority_after_serialization(portability, monkeypatch, change):
    from personal_ai.api import memory_portability
    from personal_ai.context.profile import GlobalProfileFieldUpdate, GlobalProfileUpdate

    client, rt, root, repository = portability
    serialize = memory_portability.export_profile

    def change_after_serialization(*args):
        content = serialize(*args)
        if change == "deletion_fence":
            repository.fenced_owners.add(rt.scope.owner_id)
        else:
            repository.update(rt.scope.owner_id, GlobalProfileUpdate(fields=(
                GlobalProfileFieldUpdate(field="preferred_units", value="imperial"),
            )), expected_revision=1)
        return content

    monkeypatch.setattr(memory_portability, "export_profile", change_after_serialization)
    response = client.get(f"{root}/export")
    assert response.status_code == 503
    assert "metric" not in response.text
    assert "content-disposition" not in response.headers
    assert client.get(f"{root}/profile").status_code == (503 if change == "deletion_fence" else 200)

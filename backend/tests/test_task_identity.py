"""Delegated source identity remains bound to path, body, origin and current owner."""

import base64
import time
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)
from fastapi import FastAPI, Request
from fastapi.testclient import TestClient

from personal_ai.applications.registry import (
    ApplicationContributionCatalog,
    default_application_registry,
)
from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.delegation import delegated_user_assertion
from personal_ai.auth.directory import InMemoryPrincipalDirectory
from personal_ai.auth.middleware import AuthenticationMiddleware
from personal_ai.auth.service_tokens import InvalidServiceToken
from personal_ai.contracts.delegated_tasks import control_request_binding
from personal_ai.mutations.contracts import AuthenticatedCommandRequest
from personal_ai.settings import Settings, get_settings


def encoded_public(key):
    return (
        base64.urlsafe_b64encode(key.public_key().public_bytes(Encoding.Raw, PublicFormat.Raw))
        .decode()
        .rstrip("=")
    )


@pytest.fixture
def source_identity(monkeypatch):
    origin_key, root_key = Ed25519PrivateKey.generate(), Ed25519PrivateKey.generate()
    private = (
        base64.urlsafe_b64encode(
            root_key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())
        )
        .decode()
        .rstrip("=")
    )
    settings = Settings(
        _env_file=None,
        ai_provider="fake",
        ai_model="fake",
        app_environment="test",
        auth_mode="google_oidc",
        auth_required=True,
        auth_audience="test-client",
        auth_allowed_emails=("owner@gmail.com",),
        task_delegation_enabled=True,
        task_delegation_audience="https://pai.example.invalid",
        task_delegation_issuer="pai-test",
        task_delegation_key_id="pai-key",
        task_delegation_private_key=private,
        task_origin_trusts={
            "finance": {
                "issuer": "finance-test",
                "service_account": "finance@synthetic-project.iam.gserviceaccount.com",
                "key_id": "finance-key",
                "public_key": encoded_public(origin_key),
                "user_issuer": "https://accounts.google.com",
                "user_subject": "owner-subject",
                "allowed_destinations": ["shopping"],
                "mapping_reference": "explicit-test-owner-v1",
            }
        },
    )
    calls = []

    def verify_service(token, *, audience, service_account):
        calls.append((audience, service_account))
        if token != "synthetic-service-token":
            raise InvalidServiceToken

    monkeypatch.setattr(
        "personal_ai.auth.task_identity.verify_google_service_token", verify_service
    )
    app = FastAPI()
    app.add_middleware(AuthenticationMiddleware)
    app.dependency_overrides[get_settings] = lambda: settings
    app.state.principal_directory = InMemoryPrincipalDirectory()
    from personal_ai_reference_apps.applications import application_contribution

    app.state.application_registry = default_application_registry(
        contribution_catalog=ApplicationContributionCatalog(
            (name, lambda name=name: application_contribution(name))
            for name in ("finance", "shopping")
        )
    )

    @app.post("/v1/mutations/commands")
    def received(command: AuthenticatedCommandRequest, request: Request):
        principal = request.state.principal
        return {
            "command_id": str(command.command_id),
            "subject": principal.subject,
            "owner_id": principal.owner_id,
            "authenticated_at": principal.authenticated_at,
        }

    @app.post("/v1/mutations/{proposal_id}/apply")
    def apply(proposal_id: str, request: Request):
        return {"proposal_id": proposal_id}

    @app.post("/v1/account/deletion")
    def forbidden():
        pytest.fail("a task-origin assertion must never reach an account deletion handler")

    return TestClient(app), settings, origin_key, calls


def signed_headers(settings, key, path, payload, *, subject="owner-subject", workspace=None):
    now = int(time.time())
    principal = AuthenticatedPrincipal(
        "https://accounts.google.com", subject, "domain-owner", None, now, True, now - 20
    )
    binding = control_request_binding(
        "POST", path, "shopping", workspace, payload, origin_application_id="finance"
    )
    assertion = delegated_user_assertion(
        principal=principal,
        request_body=binding,
        private_key=key,
        issuer="finance-test",
        audience=settings.task_delegation_audience,
        key_id="finance-key",
        now=now,
    )
    return {
        "Authorization": "Bearer synthetic-service-token",
        "X-Application-ID": "shopping",
        "X-Origin-Application-ID": "finance",
        "X-User-Delegation": assertion,
    }


def test_delegated_identity_is_verified_and_body_reaches_normal_handler(source_identity):
    client, settings, key, calls = source_identity
    payload = {"source_application_id": "finance", "command_id": str(uuid4())}
    path = "/v1/mutations/commands"
    response = client.post(path, json=payload, headers=signed_headers(settings, key, path, payload))
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["command_id"] == payload["command_id"]
    assert data["subject"] == "owner-subject" and data["owner_id"].startswith("usr_")
    assert data["owner_id"] != "domain-owner"
    assert calls == [
        (settings.task_delegation_audience, settings.task_origin_trusts["finance"].service_account)
    ]


@pytest.mark.parametrize("kind", ["body", "workspace", "origin", "service", "subject", "disabled"])
def test_delegation_cannot_change_scope_actor_body_or_service(source_identity, kind):
    client, settings, key, _ = source_identity
    path = "/v1/mutations/commands"
    payload = {"source_application_id": "finance", "command_id": str(uuid4())}
    headers = signed_headers(
        settings, key, path, payload, subject="other" if kind == "subject" else "owner-subject"
    )
    if kind == "body":
        payload = {**payload, "command_id": str(uuid4())}
    if kind == "workspace":
        headers["X-Workspace-ID"] = "other"
    if kind == "origin":
        headers["X-Origin-Application-ID"] = "health"
    if kind == "service":
        headers["Authorization"] = "Bearer wrong-service"
    if kind == "disabled":
        settings.task_delegation_enabled = False
    assert client.post(path, json=payload, headers=headers).status_code == 401


def test_control_assertion_is_not_reusable_for_another_path(source_identity):
    client, settings, key, _ = source_identity
    first = f"/v1/mutations/{uuid4()}/apply"
    second = f"/v1/mutations/{uuid4()}/apply"
    payload = {"confirmation_id": str(uuid4()), "binding": "a" * 64}
    headers = signed_headers(settings, key, first, payload)
    assert client.post(first, json=payload, headers=headers).status_code == 200
    assert client.post(second, json=payload, headers=headers).status_code == 401
    assert client.post("/v1/account/deletion", json=payload, headers=headers).status_code == 401


def test_principal_deactivation_fences_a_previously_valid_origin(source_identity):
    client, settings, key, _ = source_identity
    path = "/v1/mutations/commands"
    payload = {"source_application_id": "finance", "command_id": str(uuid4())}
    headers = signed_headers(settings, key, path, payload)
    first = client.post(path, json=payload, headers=headers)
    assert first.status_code == 200
    client.app.state.principal_directory.deactivate(first.json()["owner_id"])
    assert client.post(path, json=payload, headers=headers).status_code == 403


def test_signed_origin_is_denied_when_reference_applications_are_unselected(source_identity):
    client, settings, key, _ = source_identity
    client.app.state.application_registry = default_application_registry()
    payload = {"source_application_id": "finance", "command_id": str(uuid4())}
    path = "/v1/mutations/commands"

    response = client.post(path, json=payload, headers=signed_headers(settings, key, path, payload))

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "application_not_registered"

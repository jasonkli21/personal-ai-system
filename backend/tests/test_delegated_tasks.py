"""Shared wire compatibility and request-bound signed user assertions."""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from pydantic import ValidationError

from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.delegation import delegated_user_assertion
from personal_ai.contracts.delegated_tasks import (
    DelegatedTaskRequest,
    task_manifest,
    verify_delegated_user,
)

NOW = 1791910663


def task_body():
    return DelegatedTaskRequest(
        source_application_id="finance",
        destination_application_id="shopping",
        purpose="shopping_budget",
        action="execute",
        proposal_id=uuid4(),
        execution_key=uuid4(),
        operation_id="project.set_budget",
        operation_version=1,
        operation_contract_fingerprint="b" * 64,
        payload_schema_id="shopping-budget-allocation-v1",
        target_entity_type="project",
        target_entity_id=str(uuid4()),
        expected_domain_version="1",
        payload={"amount": "50.00", "currency": "USD"},
        intent_digest="c" * 64,
        confirmation_binding="d" * 64,
        source_dependencies=(
            {"permission_id": "federation_grant:synthetic", "version": "1"},
        ),
        expires_at=datetime.fromtimestamp(NOW, UTC) + timedelta(minutes=5),
    ).model_dump(mode="json")


def signed_case():
    key = Ed25519PrivateKey.generate()
    body = task_body()
    principal = AuthenticatedPrincipal(
        "https://accounts.google.com",
        "alice",
        "opaque-pai-owner",
        None,
        NOW,
        True,
        NOW - 20,
    )
    assertion = delegated_user_assertion(
        principal=principal,
        request_body=body,
        private_key=key,
        issuer="personal-ai",
        audience="https://shopping.invalid",
        key_id="test-key",
        now=NOW,
    )
    verify_options = {
        "public_key": key.public_key(),
        "issuer": "personal-ai",
        "audience": "https://shopping.invalid",
        "key_id": "test-key",
        "now": NOW,
        "allowed_user_issuers": frozenset({principal.issuer}),
    }
    return body, assertion, verify_options


def test_request_bound_assertion_preserves_verified_authentication_time():
    body, assertion, options = signed_case()
    identity = verify_delegated_user(assertion, body, **options)
    assert identity.subject == "alice"
    assert identity.authenticated_at == NOW - 20
    assert task_manifest()["maximum_assertion_lifetime_seconds"] == 60


@pytest.mark.parametrize(
    "field,value",
    [
        ("payload", {"amount": "500.00", "currency": "USD"}),
        ("destination_application_id", "travel"),
        ("workspace_id", "other-workspace"),
        ("source_dependencies", [{"permission_id": "different_grant", "version": "2"}]),
        ("execution_key", str(uuid4())),
        ("confirmation_binding", "e" * 64),
    ],
)
def test_signed_assertion_rejects_changes_to_exact_request(field, value):
    body, assertion, options = signed_case()
    with pytest.raises(ValueError, match="delegated_user_invalid"):
        verify_delegated_user(assertion, {**body, field: value}, **options)


@pytest.mark.parametrize(
    "field,value",
    [
        ("issuer", "wrong-issuer"),
        ("audience", "https://wrong.invalid"),
        ("key_id", "retired-key"),
        ("now", NOW + 60),
        ("allowed_user_issuers", frozenset({"local-development"})),
        ("max_auth_age_seconds", 10),
    ],
)
def test_delegation_rejects_wrong_authority_expiry_and_authentication_age(field, value):
    body, assertion, options = signed_case()
    with pytest.raises(ValueError, match="delegated_user_invalid"):
        verify_delegated_user(assertion, body, **{**options, field: value})


@pytest.mark.parametrize(
    "field,value",
    [
        ("schema_version", "suite-task-v2"),
        ("operation_version", True),
        ("confirmation_binding", None),
        ("source_dependencies", []),
        ("destination_application_id", "finance"),
        ("extra_authority", "allow"),
    ],
)
def test_task_wire_rejects_unsupported_versions_and_incomplete_confirmation(
    field, value
):
    with pytest.raises(ValidationError):
        DelegatedTaskRequest.model_validate({**task_body(), field: value})

"""Bounded, default-off delegated identity on typed-task control routes only."""

from __future__ import annotations

import base64
import hashlib
import re
import time

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from personal_ai.auth.contracts import AuthenticatedPrincipal
from personal_ai.auth.service_tokens import (
    InvalidServiceToken,
    ServiceTokenVerificationUnavailable,
    verify_google_service_token,
)
from personal_ai.auth.verification import IdentityProviderUnavailable, InvalidIdentityToken
from personal_ai.contracts.delegated_tasks import control_request_binding, verify_delegated_user

_CONTROL_PATH = re.compile(
    r"^(/v1/mutations/(commands|contracts|[0-9a-fA-F-]{36}(/(validate|confirm|apply|reconcile))?)"
    r"|/v1/federation/grants/choices)$"
)


def task_principal(request, settings, payload):
    """Verify separate service authority and the exact path/body/scope assertion.

    An origin key authorizes only its explicitly pinned external user and
    destination set. Domain UUIDs and email equality never establish ownership.
    Callback observation forwards the original PAI assertion for its exact task;
    it cannot authorize a different task or create a new execution reservation.
    """
    if not settings.task_delegation_enabled or request.url.query:
        raise InvalidIdentityToken
    destination = request.headers.get("x-application-id", "personal_ai")
    workspace = request.headers.get("x-workspace-id")
    assertion = request.headers.get("x-user-delegation", "")
    authorization = request.headers.get("authorization", "")
    if not authorization.startswith("Bearer "):
        raise InvalidIdentityToken
    token = authorization.removeprefix("Bearer ")
    assertion_audience = settings.task_delegation_audience
    if request.url.path == "/v1/mutations/task-authority" and request.method == "POST":
        account = settings.task_callback_accounts.get(destination)
        if (
            not account
            or not isinstance(payload, dict)
            or not isinstance(payload.get("task"), dict)
        ):
            raise InvalidIdentityToken
        body = payload["task"]
        if (
            body.get("destination_application_id") != destination
            or body.get("workspace_id") != workspace
        ):
            raise InvalidIdentityToken
        # The callback echoes the original assertion for its destination, while
        # its separate Google service token is minted for the PAI callback host.
        assertion_audience = settings.task_callback_audiences.get(destination)
        if not assertion_audience and destination == "shopping":
            assertion_audience = settings.task_shopping_audience
        if not assertion_audience:
            raise InvalidIdentityToken
        private = settings.task_delegation_private_key.get_secret_value()
        key = Ed25519PrivateKey.from_private_bytes(
            base64.b64decode(private + "=" * (-len(private) % 4), altchars=b"-_", validate=True)
        ).public_key()
        issuer, key_id = settings.task_delegation_issuer, settings.task_delegation_key_id
        subject = None
    else:
        if request.method not in {"GET", "POST"} or not _CONTROL_PATH.fullmatch(request.url.path):
            raise InvalidIdentityToken
        origin = request.headers.get("x-origin-application-id", "")
        trust = settings.task_origin_trusts.get(origin)
        if trust is None or destination not in trust.allowed_destinations:
            raise InvalidIdentityToken
        if request.url.path == "/v1/mutations/commands" and (
            not isinstance(payload, dict) or payload.get("source_application_id") != origin
        ):
            raise InvalidIdentityToken
        account, issuer, key_id, subject = (
            trust.service_account,
            trust.issuer,
            trust.key_id,
            trust.user_subject,
        )
        key = Ed25519PublicKey.from_public_bytes(
            base64.b64decode(
                trust.public_key + "=" * (-len(trust.public_key) % 4), altchars=b"-_", validate=True
            )
        )
        body = control_request_binding(
            request.method,
            request.url.path,
            destination,
            workspace,
            payload,
            origin_application_id=origin,
        )
    try:
        verify_google_service_token(
            token, audience=settings.task_delegation_audience, service_account=account
        )
        identity = verify_delegated_user(
            assertion,
            body,
            public_key=key,
            issuer=issuer,
            audience=assertion_audience,
            key_id=key_id,
            now=int(time.time()),
            allowed_user_issuers=frozenset({"https://accounts.google.com"}),
        )
        if subject is not None and identity.subject != subject:
            raise InvalidIdentityToken
    except ServiceTokenVerificationUnavailable as error:
        raise IdentityProviderUnavailable from error
    except (InvalidServiceToken, ValueError, TypeError) as error:
        raise InvalidIdentityToken from error
    owner = hashlib.sha256(f"{identity.issuer}\0{identity.subject}".encode()).hexdigest()[:32]
    return AuthenticatedPrincipal(
        identity.issuer,
        identity.subject,
        f"usr_{owner}",
        None,
        int(time.time()),
        True,
        identity.authenticated_at,
    )

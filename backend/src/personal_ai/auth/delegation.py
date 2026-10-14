"""Short-lived signed assertions for server-to-server delegated user identity."""

from __future__ import annotations

import base64
import json
import time
from hashlib import sha256
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from personal_ai.auth.contracts import AuthenticatedPrincipal


def _b64url(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b"=").decode("ascii")


def delegated_user_assertion(
    *,
    principal: AuthenticatedPrincipal,
    request_body: dict,
    private_key: Ed25519PrivateKey,
    issuer: str,
    audience: str,
    key_id: str,
    now: int | None = None,
    lifetime_seconds: int = 60,
) -> str:
    """Sign a request-bound assertion without forwarding or persisting a user token."""
    current = int(time.time()) if now is None else now
    if (
        not principal.authenticated
        or not principal.issuer
        or not principal.subject
        or not issuer
        or not audience
        or not key_id
        or lifetime_seconds < 1
        or lifetime_seconds > 60
        or principal.issued_at > current + 30
        or current - principal.issued_at > 300
        or principal.authenticated_at is None
        or not isinstance(principal.authenticated_at, int)
        or isinstance(principal.authenticated_at, bool)
        or principal.authenticated_at < 0
        or principal.authenticated_at > current + 30
        or current - principal.authenticated_at > 300
    ):
        raise ValueError("delegated_user_identity_unavailable")

    encoded_body = json.dumps(
        request_body,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")
    header = {"alg": "EdDSA", "kid": key_id, "typ": "JWT"}
    claims = {
        "iss": issuer,
        "aud": audience,
        "sub": f"{principal.issuer}|{principal.subject}",
        "user_issuer": principal.issuer,
        "user_subject": principal.subject,
        "iat": current,
        "exp": current + lifetime_seconds,
        "auth_time": principal.authenticated_at,
        "jti": str(uuid4()),
        "request_sha256": sha256(encoded_body).hexdigest(),
        "purpose": request_body.get("purpose"),
        "destination_application_id": request_body.get("destination_application_id"),
    }
    signing_input = f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}.{_b64url(json.dumps(claims, separators=(',', ':')).encode())}"
    signature = private_key.sign(signing_input.encode("ascii"))
    return f"{signing_input}.{_b64url(signature)}"

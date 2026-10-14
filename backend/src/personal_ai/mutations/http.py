"""Bounded signed domain transport, independent of provider/model transport."""

from __future__ import annotations

import base64
from time import monotonic
from urllib.parse import urlsplit

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from personal_ai.auth.delegation import delegated_user_assertion
from personal_ai.auth.scope import current_verified_principal
from personal_ai.auth.service_tokens import fetch_google_service_token
from personal_ai.contracts.delegated_tasks import TASK_CONTRACT_FINGERPRINT, canonical_bytes
from personal_ai.mutations.contracts import MutationError, MutationUnavailableError


class SignedDomainClient:
    """One request, bounded response, no automatic retry after a possible effect.

    Google verifies the service identity separately from the Ed25519 user
    assertion. Credentials exist for this request only and are never returned.
    Tests inject transport and service-token acquisition; those do not prove IAM.
    """

    def __init__(
        self,
        *,
        base_url,
        audience,
        service_account,
        issuer,
        key_id,
        private_key,
        transport=None,
        token_fetcher=fetch_google_service_token,
    ):
        parsed = urlsplit(base_url)
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path not in {"", "/"}
            or not audience.startswith("https://")
        ):
            raise ValueError("task_domain_endpoint_invalid")
        self.base_url = base_url.rstrip("/")
        self.audience = audience
        self.service_account = service_account
        self.issuer = issuer
        self.key_id = key_id
        encoded = (
            private_key.get_secret_value()
            if hasattr(private_key, "get_secret_value")
            else private_key
        )
        self.private_key = Ed25519PrivateKey.from_private_bytes(
            base64.b64decode(encoded + "=" * (-len(encoded) % 4), altchars=b"-_", validate=True)
        )
        self.transport = transport
        self.token_fetcher = token_fetcher

    def post(
        self,
        path,
        body,
        *,
        principal=None,
        maximum_bytes=24_576,
        contract_fingerprint=TASK_CONTRACT_FINGERPRINT,
        deadline=None,
    ):
        principal = principal or current_verified_principal()
        if principal is None or not principal.authenticated:
            raise MutationUnavailableError("task_user_identity_unavailable")
        if (
            not path.startswith(("/internal/personal-ai/", "/v1/integrations/personal-ai/"))
            or "?" in path
            or "#" in path
        ):
            raise ValueError("task_domain_path_invalid")
        deadline = min(deadline, monotonic() + 3.0) if deadline is not None else monotonic() + 3.0
        try:
            assertion = delegated_user_assertion(
                principal=principal,
                request_body=body,
                private_key=self.private_key,
                issuer=self.issuer,
                audience=self.audience,
                key_id=self.key_id,
            )
            service_token = self.token_fetcher(
                audience=self.audience, service_account=self.service_account, deadline=deadline
            )
            if not service_token or len(service_token) > 8192:
                raise ValueError("task_service_identity_invalid")
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError
            with (
                httpx.Client(
                    transport=self.transport,
                    timeout=remaining,
                    follow_redirects=False,
                    trust_env=False,
                ) as client,
                client.stream(
                    "POST",
                    self.base_url + path,
                    content=canonical_bytes(body),
                    headers={
                        "Authorization": f"Bearer {service_token}",
                        "Content-Type": "application/json",
                        "X-User-Delegation": assertion,
                        "X-Task-Contract-Fingerprint": contract_fingerprint,
                    },
                ) as response,
            ):
                if response.status_code in {401, 403}:
                    raise MutationError("task_domain_identity_denied")
                if response.status_code == 409:
                    raise MutationError("task_contract_or_idempotency_conflict")
                response.raise_for_status()
                data = bytearray()
                for chunk in response.iter_bytes(4096):
                    data.extend(chunk)
                    if len(data) > maximum_bytes or monotonic() >= deadline:
                        raise ValueError("task_domain_response_unavailable")
                return bytes(data)
        except MutationError:
            raise
        except (httpx.HTTPError, OSError, TimeoutError, ValueError, TypeError) as error:
            # HTTP failures after dispatch may follow a commit. MutationService
            # reserves once, records uncertainty, and reconciles without re-send.
            raise MutationUnavailableError("task_domain_unavailable") from error

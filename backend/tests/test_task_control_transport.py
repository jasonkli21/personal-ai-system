"""Every source uses the same finite, request-bound control transport."""

import base64
import json
import time
from types import SimpleNamespace
from uuid import uuid4

import httpx
import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from personal_ai.contracts.delegated_tasks import control_request_binding, verify_delegated_user
from personal_ai.contracts.task_control import SourceTaskControlClient, TaskControlUnavailable


@pytest.mark.parametrize("application", ["finance", "travel", "health"])
def test_source_transport_binds_scope_method_path_and_payload(application):
    key = Ed25519PrivateKey.generate()
    payload = {"source_application_id": application, "command_id": str(uuid4())}
    path = "/v1/mutations/commands"
    principal = SimpleNamespace(
        issuer="https://accounts.google.com",
        subject="synthetic-user",
        authenticated_at=int(time.time()),
    )
    requests = []

    def handle(request):
        requests.append(request)
        body = json.loads(request.content)
        assert body == payload
        assert request.headers["X-Origin-Application-ID"] == application
        assert request.headers["X-Application-ID"] == "shopping"
        frame = control_request_binding(
            request.method,
            request.url.path,
            "shopping",
            None,
            body,
            origin_application_id=application,
        )
        identity = verify_delegated_user(
            request.headers["X-User-Delegation"],
            frame,
            public_key=key.public_key(),
            issuer="synthetic-source",
            audience="https://pai.invalid",
            key_id="synthetic-key",
            now=int(time.time()),
            allowed_user_issuers=frozenset({principal.issuer}),
        )
        assert identity.subject == principal.subject
        return httpx.Response(200, json={"state": "proposed"})

    client = SourceTaskControlClient(
        application_id=application,
        base_url="https://pai.invalid",
        audience="https://pai.invalid",
        issuer="synthetic-source",
        key_id="synthetic-key",
        private_key=base64.urlsafe_b64encode(key.private_bytes_raw()).decode(),
        service_account="source@synthetic.iam.gserviceaccount.com",
        token_fetcher=lambda *_: "synthetic-service",
        client_type=httpx.Client,
        transport=httpx.MockTransport(handle),
    )
    assert client.request(principal, "POST", path, payload) == {"state": "proposed"}
    with pytest.raises(ValueError, match="path_invalid"):
        client.request(principal, "POST", "/v1/account/deletion", {})
    assert len(requests) == 1


def test_transport_does_not_retry_a_lost_acknowledgement():
    key = Ed25519PrivateKey.generate()
    sends = []

    def handle(request):
        sends.append(request.url.path)
        raise httpx.ReadTimeout("synthetic lost acknowledgement")

    client = SourceTaskControlClient(
        application_id="finance",
        base_url="https://pai.invalid",
        audience="https://pai.invalid",
        issuer="synthetic-source",
        key_id="synthetic-key",
        private_key=base64.urlsafe_b64encode(key.private_bytes_raw()).decode(),
        service_account="source@synthetic.iam.gserviceaccount.com",
        token_fetcher=lambda *_: "synthetic-service",
        client_type=httpx.Client,
        transport=httpx.MockTransport(handle),
    )
    principal = SimpleNamespace(
        issuer="https://accounts.google.com",
        subject="synthetic-user",
        authenticated_at=int(time.time()),
    )
    with pytest.raises(TaskControlUnavailable):
        client.request(principal, "POST", f"/v1/mutations/{uuid4()}/apply", {"binding": "x"})
    assert len(sends) == 1

"""Unrelated source-free SDK consumer using synthetic public HTTP wire frames."""

import importlib.util
import io
import json
import sys
import urllib.error
import urllib.request
from email.message import Message
from pathlib import Path
from unittest.mock import patch

attempts = []


def fence(event, args):
    if event in {"socket.connect", "socket.bind", "socket.getaddrinfo", "socket.sendto"}:
        attempts.append(event)
        raise PermissionError("synthetic consumer has no socket authority")


sys.addaudithook(fence)
from personal_ai_sdk import APIError, Client, ContractMismatch, UncertainTurn

for name in (
    "personal_ai",
    "personal_ai_reference_apps",
    "project_checklist",
    "project_checklist_host",
    "reading_logbook",
    "reading_logbook_host",
):
    assert importlib.util.find_spec(name) is None, "source_or_optional_import"
assert Path(importlib.util.find_spec("personal_ai_sdk").origin).is_relative_to(sys.prefix)
assert sys.prefix != sys.base_prefix
for path in sys.path:
    assert not path.endswith(("backend/src", "sdk/python/src")), "source_injection"

CONVERSATION = "10000000-0000-0000-0000-000000000001"
KEY = "10000000-0000-0000-0000-000000000002"
USER = "10000000-0000-0000-0000-000000000003"
ASSISTANT = "10000000-0000-0000-0000-000000000004"
BODY = {
    "content": "Synthetic inventory question",
    "idempotency_key": KEY,
    "choice": {"mode": "automatic"},
}
MESSAGE = {
    "id": ASSISTANT,
    "role": "assistant",
    "status": "completed",
    "content": "Synthetic answer",
}


def frame(event, data):
    return f"event: {event}\ndata: {json.dumps(data)}\n\n".encode()


CREATED = frame("message.created", {"message": {"id": USER, "role": "user"}}) + frame(
    "message.created", {"message": {"id": ASSISTANT, "role": "assistant"}}
)
COMPLETE = CREATED + frame("response.completed", {"message": MESSAGE})


class Response(io.BytesIO):
    def __init__(self, body, content_type):
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = content_type


calls = []
mode = "interrupt"


def transport(opener, request, **kwargs):
    calls.append((request.method, request.full_url))
    assert request.get_header("Authorization") == "Bearer synthetic-token"
    assert request.get_header("X-application-id") == "release-probe"
    assert request.get_header("X-workspace-id") == "synthetic-workspace"
    if mode == "deny":
        raise urllib.error.HTTPError(
            request.full_url,
            403,
            "private",
            Message(),
            io.BytesIO(b'{"error":{"code":"workspace_not_authorized"}}'),
        )
    if request.method == "POST":
        assert json.loads(request.data) == BODY
        return Response(CREATED if mode == "interrupt" else COMPLETE, "text/event-stream")
    assert request.full_url.endswith("/continuations/" + KEY)
    return Response(
        json.dumps({"state": "completed", "message_id": ASSISTANT}).encode(), "application/json"
    )


client = Client(
    "https://example.invalid",
    "synthetic-token",
    application="release-probe",
    workspace="synthetic-workspace",
    timeout=1,
)
with patch.object(urllib.request.OpenerDirector, "open", transport):
    try:
        client.continue_turn(CONVERSATION, BODY)
    except UncertainTurn:
        pass
    else:
        raise AssertionError("interrupted_stream_accepted")
    assert len(calls) == 1
    assert client.status(CONVERSATION, KEY)["state"] == "completed"
    mode = "complete"
    assert client.continue_turn(CONVERSATION, BODY) == MESSAGE
    assert [method for method, _ in calls] == ["POST", "GET", "POST", "GET"]
    mode = "deny"
    try:
        client.status(CONVERSATION, KEY)
    except APIError as error:
        assert error.status == 403 and error.code == "workspace_not_authorized"
    else:
        raise AssertionError("denial_not_typed")
for version in ("1.1.0", "2.0.0"):
    try:
        Client(
            "https://example.invalid",
            "synthetic",
            application="release-probe",
            contract_version=version,
        )
    except ContractMismatch:
        pass
    else:
        raise AssertionError("unsupported_contract")
assert attempts == []
print('{"protocol":"PASS","tier":"E1","network_attempts":0,"signed_identity":"NOT_RUN"}')

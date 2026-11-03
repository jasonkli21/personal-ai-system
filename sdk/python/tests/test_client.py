"""Client-only protocol tests with no socket transport."""

import io
import json
from email.message import Message
from urllib.error import HTTPError, URLError
from uuid import uuid4

import pytest
from personal_ai_sdk import (
    APIError,
    CapabilityUnavailable,
    Client,
    ContractMismatch,
    UncertainTurn,
)
from personal_ai_sdk.client import read_completion

USER, ASSISTANT, KEY, CONVERSATION = (str(uuid4()) for _ in range(4))
BODY = {
    "content": "private prompt",
    "idempotency_key": KEY,
    "choice": {"mode": "automatic"},
}


def frame(name, data):
    return f"event: {name}\r\ndata: {json.dumps(data, ensure_ascii=False)}\r\n\r\n".encode()


MESSAGE = {"id": ASSISTANT, "role": "assistant", "status": "completed", "content": "☕"}
TERMINAL = frame("response.completed", {"message": MESSAGE})
STREAM = (
    frame("message.created", {"message": {"id": USER, "role": "user"}})
    + frame("message.created", {"message": {"id": ASSISTANT, "role": "assistant"}})
    + frame("response.delta", {"message_id": ASSISTANT, "delta": "☕"})
    + TERMINAL
)


def test_split_utf8_and_crlf():
    deltas = []
    assert read_completion((bytes([b]) for b in STREAM), deltas.append) == MESSAGE
    assert deltas == ["☕"]


def test_zero_delta_completed_terminal():
    stream = (
        frame("message.created", {"message": {"id": USER, "role": "user"}})
        + frame("message.created", {"message": {"id": ASSISTANT, "role": "assistant"}})
        + frame("response.completed", {"message": {**MESSAGE, "content": "final result"}})
    )
    assert read_completion([stream])["content"] == "final result"


def test_canonical_text_can_supersede_provisional_delta():
    stream = (
        frame("message.created", {"message": {"id": USER, "role": "user"}})
        + frame("message.created", {"message": {"id": ASSISTANT, "role": "assistant"}})
        + frame("response.delta", {"message_id": ASSISTANT, "delta": "draft"})
        + frame("response.completed", {"message": {**MESSAGE, "content": "final result"}})
    )
    assert read_completion([stream])["content"] == "final result"


@pytest.mark.parametrize(
    "message",
    [
        {**MESSAGE, "status": None},
        {**MESSAGE, "status": "streaming"},
        {**MESSAGE, "content": " "},
        {**MESSAGE, "content": "x" * 20001},
    ],
)
def test_invalid_canonical_terminal_is_rejected(message):
    stream = (
        frame("message.created", {"message": {"id": USER, "role": "user"}})
        + frame("message.created", {"message": {"id": ASSISTANT, "role": "assistant"}})
        + frame("response.completed", {"message": message})
    )
    with pytest.raises(UncertainTurn):
        read_completion([stream])


@pytest.mark.parametrize(
    "stream",
    [
        b"",
        STREAM + TERMINAL,
        STREAM + b"event: response.completed\n\n",
        STREAM[:-2],
        STREAM[: -len(TERMINAL)],
        STREAM.replace("☕".encode(), b"\xff"),
        b"data: {\n\n",
        b"a" * 262145,
        b"a" * 2000001,
        STREAM.replace(b'"completed"', b'"streaming"'),
        TERMINAL,
        STREAM.replace(b"response.delta", b"future.delta"),
    ],
)
def test_invalid_or_ambiguous_completion(stream):
    with pytest.raises(UncertainTurn):
        read_completion([stream])


class Response(io.BytesIO):
    def __init__(self, body, content_type):
        super().__init__(body)
        self.headers = Message()
        self.headers["Content-Type"] = content_type


@pytest.fixture
def sdk():
    return Client(
        "https://example.invalid", "synthetic-secret", application="project-checklist"
    )


@pytest.mark.parametrize("status", [400, 401, 403, 404, 408, 409, 413, 422, 429, 503])
def test_http_error_cannot_echo_token_or_body(sdk, monkeypatch, status):
    def deny(request, **kwargs):
        raise HTTPError(
            request.full_url,
            status,
            "secret",
            Message(),
            io.BytesIO(
                b'{"error":{"code":"private_secret_code","message":"synthetic-secret"}}',
            ),
        )

    monkeypatch.setattr(sdk._opener, "open", deny)
    with pytest.raises(APIError) as error:
        sdk.continue_turn(CONVERSATION, BODY)
    assert error.value.status == status
    assert error.value.code == "request_failed"
    assert error.value.__cause__ is None
    assert "secret" not in str(error.value)


def test_origin_denied_is_a_safe_typed_error(sdk, monkeypatch):
    def deny(request, **kwargs):
        raise HTTPError(
            request.full_url,
            403,
            "secret",
            Message(),
            io.BytesIO(
                b'{"error":{"code":"origin_denied","message":"synthetic-secret"}}'
            ),
        )

    monkeypatch.setattr(sdk._opener, "open", deny)
    with pytest.raises(APIError) as error:
        sdk.continue_turn(CONVERSATION, BODY)
    assert error.value.status == 403
    assert error.value.code == "origin_denied"
    assert "synthetic-secret" not in str(error.value)
    assert "private prompt" not in str(error.value)


def test_status_agreement_and_no_ambient_authority(sdk, monkeypatch):
    calls = []

    def send(request, **kwargs):
        calls.append(request)
        if request.method == "POST":
            return Response(STREAM, "text/event-stream")
        return Response(
            json.dumps({"state": "completed", "message_id": ASSISTANT}).encode(),
            "application/json",
        )

    monkeypatch.setattr(sdk._opener, "open", send)
    assert sdk.continue_turn(CONVERSATION, BODY) == MESSAGE
    first, status = calls
    assert json.loads(first.data) == BODY
    assert status.full_url.endswith("/continuations/" + KEY)
    assert status.get_header("X-workspace-id") is None
    assert first.get_header("Last-event-id") is None
    assert "secret" not in str(sdk.diagnostics())


@pytest.mark.parametrize("first", ["disconnect", "empty_stream", "mismatch"])
def test_uncertainty_does_not_resend(sdk, monkeypatch, first):
    calls = []

    def send(request, **kwargs):
        calls.append(request.method)
        if request.method == "GET":
            return Response(
                b'{"state":"not_found","message_id":null}', "application/json"
            )
        if first == "disconnect":
            raise URLError("token and prompt could appear in a raw exception")
        return Response(b"" if first == "empty_stream" else STREAM, "text/event-stream")

    monkeypatch.setattr(sdk._opener, "open", send)
    with pytest.raises(UncertainTurn) as error:
        sdk.continue_turn(CONVERSATION, BODY)
    assert error.value.__cause__ is None
    assert calls == (["POST", "GET"] if first == "mismatch" else ["POST"])
    assert sdk.status(CONVERSATION, KEY)["state"] == "not_found"


def test_version_and_capability_are_configuration_not_grants(sdk):
    with pytest.raises(ContractMismatch):
        Client(
            "https://example.invalid",
            "synthetic",
            application="app",
            contract_version="2.0.0",
        )
    with pytest.raises(CapabilityUnavailable):
        sdk.retrieve("local only", KEY)

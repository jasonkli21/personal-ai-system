"""Adversarial HTTP consumer protocol, local journal and host facade contracts."""

import json
from pathlib import Path
from uuid import uuid4

import pytest
from reading_logbook.client import PlatformClient, UncertainTurn, read_completion
from reading_logbook_host import application

from personal_ai.api.consumer_contract import serialized_contract
from personal_ai.applications.registry import (
    ApplicationContributionCatalog,
    default_application_registry,
)
from personal_ai.applications.selection import load_selected_entry_points
from personal_ai.extensions import v1


def wire(*, content="café", terminal=True):
    identity = str(uuid4())
    message = {"id": identity, "role": "assistant", "status": "completed", "content": content}
    events = [
        ("message.created", {"message": message}),
        ("response.delta", {"message_id": identity, "delta": content}),
    ]
    if terminal:
        events.append(("response.completed", {"message": message}))
    return b"".join(
        f"event: {event}\r\ndata: {json.dumps(data, ensure_ascii=False)}\r\n\r\n".encode()
        for event, data in events
    )


def test_fragmented_utf8_crlf_and_terminal():
    value = wire()
    for size in (1, 2, 7, 10000):
        result = read_completion([value[i : i + size] for i in range(0, len(value), size)])
        assert result["content"] == "café"


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "truncated",
        "duplicate",
        "delta_after",
        "mismatch",
        "oversize",
        "invalid_utf8",
        "bad_json",
    ],
)
def test_provisional_data_never_becomes_false_success(fault):
    value = wire()
    if fault == "missing":
        value = wire(terminal=False)
    elif fault == "truncated":
        value = value[:-3]
    elif fault == "duplicate":
        value += value
    elif fault == "delta_after":
        value += b'event: response.delta\ndata: {"delta":"x"}\n\n'
    elif fault == "mismatch":
        start = value.index(b"event: response.completed")
        value = value[:start] + value[start:].replace(b"caf", b"bad")
    elif fault == "oversize":
        value = b"data: " + b"x" * 262145
    elif fault == "invalid_utf8":
        value = b"\xff"
    else:
        value = b"data: {\n\n"
    with pytest.raises(UncertainTurn):
        read_completion([value])


def test_client_does_not_accept_cleartext_or_redirect_target_credentials():
    for url in (
        "http://example.com",
        "https://user:pass@example.com",
        "https://example.com/?token=x",
    ):
        with pytest.raises(ValueError):
            PlatformClient(url, "token", "shelf")


def test_public_spec_is_generated_from_models():
    root = Path(__file__).resolve().parents[2]
    assert (
        root / "docs/platform-independence/consumer-v1.openapi.json"
    ).read_text() == serialized_contract()


def test_host_public_facade_and_unselected_factory():
    assert v1.HOST_CONTRACT_VERSION == "personal-ai-host-v1"
    calls = []

    class Point:
        name = "reading_logbook"

        def load(self):
            calls.append("executed")
            return application

    assert load_selected_entry_points([Point()], ()) == ()
    assert not calls
    with pytest.raises(ValueError, match="not_installed"):
        load_selected_entry_points([], ("unknown",))
    with pytest.raises(ValueError, match="duplicate"):
        load_selected_entry_points([Point(), Point()], ("reading_logbook",))
    assert not calls
    with pytest.raises(ValueError):
        ApplicationContributionCatalog((("broken", lambda: object()),)).contributions()
    assert default_application_registry(
        contribution_catalog=ApplicationContributionCatalog()
    ).application_ids == {"personal_ai"}


@pytest.mark.parametrize("message", [[], None, "x", {"id": []}, {"id": 1}])
def test_malformed_created_payload_is_unconfirmed(message):
    value = f"event: message.created\ndata: {json.dumps({'message': message})}\n\n".encode()
    with pytest.raises(UncertainTurn):
        read_completion([value])


def test_selected_host_requires_config_and_compatible_contract(monkeypatch):
    import reading_logbook_host

    monkeypatch.delenv("READING_LOGBOOK_MEMBERSHIP_FILE", raising=False)
    with pytest.raises(KeyError):
        application()
    monkeypatch.setattr(reading_logbook_host, "HOST_CONTRACT_VERSION", "incompatible")
    with pytest.raises(ValueError, match="host_contract_incompatible"):
        application()


def test_incomplete_json_response_is_unconfirmed(monkeypatch):
    import http.client
    from contextlib import nullcontext
    from types import SimpleNamespace

    client = PlatformClient("https://unused.invalid", "token", "shelf")

    def incomplete(*_):
        raise http.client.IncompleteRead(b"partial")

    monkeypatch.setattr(client, "request", lambda *_: nullcontext(SimpleNamespace(read=incomplete)))
    with pytest.raises(UncertainTurn):
        client.start("Original title", uuid4())


def test_additive_status_fields_preserve_completion(monkeypatch):
    from contextlib import nullcontext
    from types import SimpleNamespace

    value = wire()
    identity = read_completion([value])["id"]
    client = PlatformClient("https://unused.invalid", "token", "shelf")
    chunks = iter((value, b""))
    response = SimpleNamespace(
        headers=SimpleNamespace(get_content_type=lambda: "text/event-stream"),
        read1=lambda _: next(chunks),
    )
    monkeypatch.setattr(client, "request", lambda *_: nullcontext(response))
    monkeypatch.setattr(
        client,
        "status",
        lambda *_: {"state": "completed", "message_id": identity, "future_field": "ignored"},
    )
    assert client.ask(uuid4(), {"idempotency_key": str(uuid4())})["id"] == identity

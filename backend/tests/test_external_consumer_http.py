"""Signed synthetic Checklist HTTP messages through the shared ASGI fixture."""

import io
import json
from email.message import Message
from urllib.error import HTTPError
from uuid import uuid4

import pytest
from personal_ai_sdk import APIError, Client, UncertainTurn
from project_checklist.store import Checklist

from .test_signed_http_integration import http_platform as signed_http_fixture
from .test_signed_http_integration import turn

http_platform = signed_http_fixture

from project_checklist_host import application as _checklist_application  # noqa: F401


@pytest.mark.parametrize("http_platform", ["project_checklist"], indirect=True)
def test_checklist_sdk_original_intent_and_denial(http_platform, tmp_path, caplog):
    h = http_platform
    claims = {"aud": "checklist-oauth-client", "azp": "checklist-oauth-client"}
    token = h.token(**claims)
    base = "https://testserver"

    def open_asgi(request, **kwargs):
        response = h.raw.request(
            request.method,
            request.full_url,
            headers=dict(request.header_items()),
            content=request.data,
        )
        headers = Message()
        headers["Content-Type"] = response.headers["content-type"]
        body = io.BytesIO(response.content)
        body.headers = headers
        if response.is_error:
            raise HTTPError(request.full_url, response.status_code, "", headers, body)
        return body

    def client(signed=token, application="project_checklist", workspace="site"):
        sdk = Client(base, signed, application=application, workspace=workspace)
        sdk._opener.open = open_asgi
        return sdk

    sdk = client()
    created = sdk.create("Site checklist", uuid4())
    cid = created["id"]
    assert sdk.list()["conversations"] == [created]
    assert sdk.detail(cid)["messages"] == []
    preview = sdk.preview(cid, turn())
    assert "planned_sources" in preview
    assert not h.llm.requests
    with pytest.raises(APIError):
        sdk.preview(cid, {**turn(), "retrieval_context": True})
    assert not h.llm.requests

    target = json.dumps([base, "project_checklist", "site"])
    journal_path = tmp_path / "local-checklist.sqlite"
    journal = Checklist(journal_path)
    journal.add("Private local item")
    key = journal.prepare(target, cid, "Explicit synthetic turn")
    assert sdk.status(cid, key)["state"] == "not_found"
    completed = journal.turn(sdk, target, key, recover=False)
    assert completed["content"] == "Synthetic answer"
    assert sdk.status(cid, key)["message_id"] == completed["id"]
    assert Checklist(journal_path).turn(sdk, target, key, recover=True) == completed
    with pytest.raises(APIError) as conflict:
        sdk.continue_turn(cid, turn("Changed intent", key))
    assert conflict.value.status == 409
    assert conflict.value.code == "conversation_conflict"
    assert len(h.llm.requests) == 1
    assert "Private local item" not in str(h.llm.requests)
    assert len(sdk.detail(cid)["messages"]) == 2

    # The server committed, but the original process lost its 200 response body.
    def lose_stream(request, **kwargs):
        response = open_asgi(request, **kwargs)
        if request.full_url.endswith("/continue"):
            response.truncate(0)
        return response

    sdk._opener.open = lose_stream
    lost_key = journal.prepare(target, cid, "Another explicit turn")
    with pytest.raises(UncertainTurn):
        journal.turn(sdk, target, lost_key, recover=False)
    assert len(h.llm.requests) == 2
    sdk = client()
    with pytest.raises(ValueError, match="use_recover_for_original_key"):
        journal.turn(sdk, target, lost_key, recover=False)
    assert Checklist(journal_path).turn(sdk, target, lost_key, recover=True)["content"]
    assert len(h.llm.requests) == 2

    # Current membership is reread for retained detail, preview, and send.
    h.membership_file.write_text(
        json.dumps(
            {
                "issuer": "https://accounts.google.com",
                "subject": "synthetic-owner",
                "workspace_id": "site",
                "expires_at": 0,
            }
        )
    )
    for operation in (
        lambda: sdk.detail(cid),
        lambda: sdk.preview(cid, turn()),
        lambda: sdk.continue_turn(cid, turn()),
    ):
        with pytest.raises(APIError) as error:
            operation()
        assert error.value.status in {403, 404}
        assert "Private local item" not in str(error.value)
        assert token not in str(error.value)
    assert len(h.llm.requests) == 2

    for denied in (
        client(h.token(**{**claims, "aud": "wrong-audience"})),
        client(h.token(**{**claims, "azp": "wrong-client"})),
        client(h.token(**claims, sub="synthetic-owner-b")),
        client(application="reading_logbook"),
        client(workspace="other-site"),
    ):
        with pytest.raises(APIError) as error:
            denied.detail(cid)
        assert error.value.status in {401, 403, 404}
    for name in ("X-Owner-ID", "X-Acting-User-ID"):
        denied = h.raw.get(
            f"/v1/conversations/{cid}",
            headers={
                "Authorization": f"Bearer {token}",
                "X-Application-ID": "project_checklist",
                "X-Workspace-ID": "site",
                name: "spoofed",
            },
        )
        assert denied.status_code == 403
    assert token not in caplog.text

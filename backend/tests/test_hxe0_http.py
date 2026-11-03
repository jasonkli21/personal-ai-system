"""Signed synthetic Checklist HTTP messages through the shared ASGI fixture."""

import io
import json
from email.message import Message
from urllib.error import HTTPError
from uuid import uuid4

import pytest

from .test_pi2_http import http_platform as signed_http_fixture
from .test_pi2_http import turn

http_platform = signed_http_fixture

pytest.importorskip("project_checklist_host")


@pytest.mark.parametrize("http_platform", ["project_checklist"], indirect=True)
def test_checklist_sdk_original_intent_and_denial(http_platform, tmp_path, caplog):
    sdk_package = pytest.importorskip("personal_ai_sdk")
    app_package = pytest.importorskip("project_checklist.store")
    APIError, Client = sdk_package.APIError, sdk_package.Client
    UncertainTurn = sdk_package.UncertainTurn
    Checklist = app_package.Checklist
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

"""Synthetic native controller/callback tests; no system browser or TCP listener."""

import io
import json
import socket
from email.message import Message
from urllib.parse import parse_qs, urlsplit

import pytest

from personal_ai.llm.chatgpt.oauth import REQUIRED_USAGE_SCOPES, OAuthFailure
from personal_ai.local_bridge import __main__ as controller
from tests.test_chatgpt_bridge_transport import bridge_fixture
from tests.test_chatgpt_local_lifecycle import connected_lifecycle


@pytest.mark.parametrize("duplicate", [False, True])
def test_native_callback_never_returns_or_logs_auth_code_or_url(
    tmp_path, monkeypatch, caplog, duplicate
):
    lifecycle, oauth, _ = connected_lifecycle(tmp_path)
    oauth.scopes = ("openid", "profile", "email", "offline_access")
    observed = {}

    class SyntheticListener:
        def __init__(self, address, handler):
            assert address == ("127.0.0.1", 0)
            self.handler, self.server_port = handler, 54321
            observed["started"] = True

        def handle_request(self):
            query = parse_qs(urlsplit(observed["url"]).query)
            handler = self.handler.__new__(self.handler)
            handler.client_address = ("127.0.0.1", 1234)
            handler.headers = Message()
            handler.headers["Host"] = "127.0.0.1:54321"
            handler.path = (
                "/auth/callback?state="
                + query["state"][0]
                + ("&code=synthetic-callback-code&client_id=oaiapp_newregistration")
            )
            if duplicate:
                handler.path += "&code=other-code"
            handler.wfile = io.BytesIO()
            handler.send_response = lambda status: observed.update(status=status)
            handler.send_header = lambda key, value: None
            handler.end_headers = lambda: None
            handler.do_GET()
            observed["body"] = handler.wfile.getvalue()

        def server_close(self):
            observed["closed"] = True

    def open_system_browser(url):
        assert observed["started"]
        scopes = parse_qs(urlsplit(url).query)["scope"][0].split()
        assert not REQUIRED_USAGE_SCOPES.intersection(scopes)
        observed["url"] = url
        return True

    monkeypatch.setattr(controller, "HTTPServer", SyntheticListener)
    monkeypatch.setattr(controller.webbrowser, "open", open_system_browser)
    if duplicate:
        with pytest.raises(OAuthFailure):
            controller.local_sign_in(lifecycle)
    else:
        connection = controller.local_sign_in(lifecycle)
        assert connection.state == "permission_required" and not connection.plan_permission
    assert observed["closed"] and observed["status"] == 200
    assert b"synthetic-callback-code" not in observed["body"]
    assert observed["url"] not in caplog.text
    assert not lifecycle._attempts


def test_real_operator_ignores_legacy_plan_enablement_and_starts_no_listener(
    tmp_path, monkeypatch, capsys,
):
    bridge, provider, session, package, proof, private = bridge_fixture(tmp_path)
    store = bridge.lifecycle.store
    config = store.directory / "compatibility.json"
    config.write_text(json.dumps({
        "issuer": proof.claims.issuer,
        "keys": {proof.claims.key_id: private.public_key().public_bytes_raw().hex()},
        "gates": [gate.model_dump(mode="json") for gate in bridge.gates.values()],
        "private_network_verified": True,
    }))
    config.chmod(0o600)
    bridge.verifier.verify(proof, package, caller_id=session.caller_id, now=proof.claims.issued_at)
    attempts = []

    def forbidden(*args, **kwargs):
        attempts.append("unexpected I/O")
        raise AssertionError("operator execution attempted I/O")

    monkeypatch.setattr(controller, "HTTPServer", forbidden)
    monkeypatch.setattr(controller.OpenAIOAuth, "_json", forbidden)
    monkeypatch.setattr(provider.provider.__class__, "_client", forbidden)
    monkeypatch.setattr(socket.socket, "bind", forbidden)
    monkeypatch.setattr("sys.argv", ["bridge", "--directory", str(store.directory)])
    commands = iter([
        f"enable-usage {session.connection_id}",
        f"pair {session.origin} {session.connection_id}",
        "status",
        "quit",
    ])
    monkeypatch.setattr("builtins.input", lambda prompt: next(commands))
    controller.main()
    output = capsys.readouterr().out
    assert "plan inference is disabled" in output and output.count("Unknown command.") == 2
    assert "caller_authorization" not in output and "synthetic-access" not in output
    assert attempts == []


def test_real_oauth_plan_consent_and_refresh_deny_before_discovery(tmp_path, monkeypatch):
    lifecycle, _, connection = connected_lifecycle(tmp_path)
    oauth = controller.OpenAIOAuth()
    lifecycle.oauth = oauth

    def forbidden(*args, **kwargs):
        raise AssertionError("real OAuth transport reached")

    monkeypatch.setattr(oauth, "_json", forbidden)
    with pytest.raises(OAuthFailure, match="bridge_compatibility_unverified"):
        lifecycle.begin(
            "http://127.0.0.1:54321/auth/callback",
            connection_id=connection.connection_id, enable_plan_usage=True,
        )
    with pytest.raises(OAuthFailure, match="bridge_compatibility_unverified"):
        oauth.refresh(
            client_id="oaiapp_synthetic", refresh_token="synthetic-refresh",
            previous_id_token="synthetic-id-token", subject="synthetic-subject", scopes=(),
        )

"""POSIX local operator surface. No auth URL/token goes through browser IPC."""

from __future__ import annotations

import argparse
import json
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

from personal_ai.llm.chatgpt.oauth import OAuthFailure, OpenAIOAuth
from personal_ai.local_bridge.lifecycle import CredentialLifecycle
from personal_ai.local_bridge.store import LocalStoreError, ProtectedLocalStore


def local_sign_in(lifecycle: CredentialLifecycle, *, connection_id=None):
    """Ephemeral OAuth callback listener, separate from paired browser execution."""
    outcome = {}
    attempt_id = None

    class Callback(BaseHTTPRequestHandler):
        def log_message(self, *args):
            pass  # BaseHTTPRequestHandler otherwise logs the authorization code URL.

        def do_GET(self):
            try:
                parsed = urlsplit(self.path)
            except ValueError:
                self.send_error(403)
                return
            expected_host = f"127.0.0.1:{server.server_port}"
            if (
                self.client_address[0] != "127.0.0.1"
                or self.headers.get_all("Host") != [expected_host]
                or parsed.path != "/auth/callback"
                or parsed.scheme
                or parsed.netloc
                or parsed.fragment
                or len(self.path) > 16384
                or "Origin" in self.headers
            ):
                self.send_error(403)
                return
            try:
                pairs = parse_qsl(parsed.query, keep_blank_values=True, max_num_fields=16)
                values = dict(pairs)
                if len(pairs) != len(values):
                    raise OAuthFailure("oauth_callback_invalid")
                outcome["connection"] = lifecycle.complete(attempt_id, values)
                message = b"Sign-in finished. Return to the local bridge."
            except (OAuthFailure, LocalStoreError, ValueError):
                outcome["failed"] = True
                message = b"Sign-in failed. Return to the local bridge to try again."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Referrer-Policy", "no-referrer")
            self.send_header("Content-Security-Policy", "default-src 'none'")
            self.send_header("Content-Length", str(len(message)))
            self.end_headers()
            self.wfile.write(message)

    # Bind before generating/opening the authorization URL. Only this port can vary.
    class BoundedCallbackServer(HTTPServer):
        def get_request(self):
            socket, address = super().get_request()
            socket.settimeout(5)
            return socket, address

    server = BoundedCallbackServer(("127.0.0.1", 0), Callback)
    server.timeout = 1
    try:
        attempt_id, url = lifecycle.begin(
            f"http://127.0.0.1:{server.server_port}/auth/callback",
            connection_id=connection_id,
            identity_only=True,
        )
        if not webbrowser.open(url):
            raise OAuthFailure("oauth_system_browser_unavailable")
        deadline = time.monotonic() + 180
        while not outcome and time.monotonic() < deadline:
            server.handle_request()
        if "connection" not in outcome:
            raise OAuthFailure("oauth_sign_in_failed")
        return outcome["connection"]
    finally:
        if attempt_id is not None:
            lifecycle.cancel(attempt_id)
        server.server_close()


def main():
    parser = argparse.ArgumentParser(description="User-local ChatGPT account controls")
    parser.add_argument(
        "--directory", type=Path, default=Path.home() / ".local/state/personal-ai-bridge"
    )
    args = parser.parse_args()
    store = ProtectedLocalStore(args.directory)
    lifecycle = CredentialLifecycle(store, OpenAIOAuth())
    print("ChatGPT plan inference is disabled. Local account controls are available.")
    print("Commands: sign-in | reauth CONNECTION | sign-out CONNECTION | status | quit")
    try:
        while True:
            command = input("bridge> ").split()
            if not command:
                continue
            try:
                if command == ["quit"]:
                    break
                if command == ["status"]:
                    print(
                        json.dumps(
                            [connection.public_payload() for connection in lifecycle.connections()]
                        )
                    )
                elif command == ["sign-in"]:
                    print(json.dumps(local_sign_in(lifecycle).public_payload()))
                elif len(command) == 2 and command[0] == "reauth":
                    print(
                        json.dumps(
                            local_sign_in(lifecycle, connection_id=command[1]).public_payload()
                        )
                    )
                elif len(command) == 2 and command[0] == "sign-out":
                    print(json.dumps(lifecycle.disconnect(command[1]).public_payload()))
                else:
                    print("Unknown command.")
            except (OAuthFailure, LocalStoreError) as error:
                print(error.code)
    except (EOFError, KeyboardInterrupt):
        pass


if __name__ == "__main__":
    main()

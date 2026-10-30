"""Narrow v1 client with conservative stream and recovery semantics."""

import codecs
import http.client
import json
import urllib.error
import urllib.parse
import urllib.request
from uuid import UUID


class APIError(RuntimeError):
    def __init__(self, status, code):
        self.status, self.code = status, code
        super().__init__(f"HTTP {status}: {code}; retain the original operation key")


class UncertainTurn(RuntimeError):
    """An observation is incomplete; only the original key may be reconciled."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def sse_events(chunks):
    """Strict UTF-8, fragmented CRLF/LF frames, bounded event and total size."""
    decoder = codecs.getincrementaldecoder("utf-8")("strict")
    buffer, total = "", 0
    try:
        for chunk in chunks:
            total += len(chunk)
            if total > 2_000_000:
                raise UncertainTurn("stream_too_large")
            buffer += decoder.decode(chunk)
            # Preserve a trailing CR until the next chunk arrives.
            normalized = buffer.replace("\r\n", "\n")
            while "\n\n" in normalized:
                block, normalized = normalized.split("\n\n", 1)
                if len(block.encode()) > 262144:
                    raise UncertainTurn("event_too_large")
                event, data = "message", []
                for line in block.split("\n"):
                    if line.startswith("event:"):
                        event = line[6:].lstrip(" ")
                    elif line.startswith("data:"):
                        data.append(line[5:].removeprefix(" "))
                if data:
                    yield event, json.loads("\n".join(data))
            buffer = normalized
            if len(buffer.encode()) > 262144:
                raise UncertainTurn("event_too_large")
        buffer += decoder.decode(b"", final=True)
        if buffer.strip():
            raise UncertainTurn("truncated_event")
    except (ValueError, UnicodeError) as error:
        raise UncertainTurn("invalid_stream") from error


def read_completion(chunks, provisional=lambda text: None):
    completed, assistant_id, text, created = None, None, "", set()
    for event, data in sse_events(chunks):
        if completed is not None:
            raise UncertainTurn("data_after_terminal")
        if not isinstance(data, dict):
            raise UncertainTurn("invalid_event")
        if event == "message.created":
            message = data.get("message", {})
            if not isinstance(message, dict):
                raise UncertainTurn("invalid_created")
            identity = message.get("id")
            if not isinstance(identity, str) or not identity or identity in created:
                raise UncertainTurn("duplicate_created")
            created.add(identity)
            if message.get("role") == "assistant":
                if assistant_id is not None:
                    raise UncertainTurn("multiple_assistants")
                assistant_id = identity
        elif event == "response.delta":
            delta = data.get("delta")
            if (
                not assistant_id
                or data.get("message_id") != assistant_id
                or not isinstance(delta, str)
                or not delta
            ):
                raise UncertainTurn("invalid_delta")
            text += delta
            if len(text) > 20000:
                raise UncertainTurn("output_too_large")
            provisional(delta)
        elif event == "response.error":
            raise UncertainTurn("response_error")
        elif event == "response.completed":
            completed = data.get("message")
            if (
                not isinstance(completed, dict)
                or completed.get("id") != assistant_id
                or completed.get("role") != "assistant"
                or completed.get("status") != "completed"
                or completed.get("content") != text
                or not text.strip()
            ):
                raise UncertainTurn("invalid_terminal")
    if completed is None:
        raise UncertainTurn("terminal_missing")
    return completed


class PlatformClient:
    def __init__(
        self,
        base_url,
        token,
        workspace,
        *,
        application="reading_logbook",
        allow_loopback=False,
        timeout=30,
    ):
        url = urllib.parse.urlsplit(base_url)
        loopback = url.hostname in {"127.0.0.1", "::1"}
        if (
            url.scheme not in {"https", "http"}
            or not url.hostname
            or url.username
            or url.password
            or url.query
            or url.fragment
            or url.path not in {"", "/"}
            or (url.scheme != "https" and not (allow_loopback and loopback))
        ):
            raise ValueError(
                "HTTPS required; explicit loopback is for synthetic fixtures only"
            )
        if not token or any(c.isspace() for c in token) or len(token) > 8192:
            raise ValueError("invalid token")
        self.base_url, self.token, self.workspace = (
            base_url.rstrip("/"),
            token,
            workspace,
        )
        self.application, self.timeout = application, timeout
        # Ignore environment proxies; never forward tokens through redirects.
        self.opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()
        )

    def request(self, method, path, body=None):
        headers = {
            "Authorization": "Bearer " + self.token,
            "X-Application-ID": self.application,
            "X-Workspace-ID": self.workspace,
            "Accept": "application/json",
        }
        data = None if body is None else json.dumps(body).encode()
        if data is not None:
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            self.base_url + path, data=data, method=method, headers=headers
        )
        try:
            return self.opener.open(req, timeout=self.timeout)
        except urllib.error.HTTPError as error:
            code = "request_failed"
            try:
                code = json.loads(error.read(65536)).get("error", {}).get("code", code)
            except (ValueError, AttributeError):
                pass
            finally:
                error.close()
            raise APIError(error.code, code) from None
        except (OSError, TimeoutError, http.client.HTTPException) as error:
            raise UncertainTurn("transport_unknown; retain the original key") from error

    def json(self, method, path, body=None):
        try:
            with self.request(method, path, body) as response:
                raw = response.read(4_000_001)
                if len(raw) > 4_000_000:
                    raise UncertainTurn("response_too_large")
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise UncertainTurn("invalid_json_response")
                return value
        except (OSError, ValueError, http.client.HTTPException) as error:
            raise UncertainTurn(
                "json_response_unknown; retain the original key"
            ) from error

    def start(self, title, key):
        return self.json(
            "POST",
            "/v1/conversations",
            {"title": title, "idempotency_key": str(UUID(str(key)))},
        )

    def conversations(self):
        return self.json("GET", "/v1/conversations")

    def conversation(self, conversation_id):
        return self.json("GET", f"/v1/conversations/{UUID(str(conversation_id))}")

    def preview(self, conversation_id, body):
        return self.json(
            "POST",
            f"/v1/conversations/{UUID(str(conversation_id))}/context-preview",
            body,
        )

    def status(self, conversation_id, key):
        return self.json(
            "GET",
            f"/v1/conversations/{UUID(str(conversation_id))}/continuations/{UUID(str(key))}",
        )

    def ask(self, conversation_id, body, provisional=lambda text: None):
        path = f"/v1/conversations/{UUID(str(conversation_id))}/continue"
        try:
            with self.request("POST", path, body) as response:
                if response.headers.get_content_type() != "text/event-stream":
                    raise UncertainTurn("unexpected_response_type")
                completed = read_completion(
                    iter(lambda: response.read1(4096), b""), provisional
                )
            status = self.status(conversation_id, body["idempotency_key"])
            if (
                not isinstance(status, dict)
                or status.get("state") != "completed"
                or status.get("message_id") != completed["id"]
            ):
                raise UncertainTurn("canonical_status_disagrees")
            return completed
        except (OSError, TimeoutError, ValueError, http.client.HTTPException) as error:
            raise UncertainTurn("stream_unknown; reconcile original key") from error

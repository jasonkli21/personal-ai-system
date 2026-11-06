"""Narrow v1 client with conservative stream and recovery semantics."""

import codecs
import http.client
import json
import math
import re
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Callable, Iterable
from typing import Literal, NotRequired, TypedDict, cast
from uuid import UUID

CONSUMER_VERSION = "1.2.0"
Identity = UUID | str
JsonObject = dict[str, object]


class Choice(TypedDict):
    mode: Literal["automatic"]


class Continuation(TypedDict):
    content: str
    idempotency_key: str
    choice: Choice
    # Additional selectors defined by the pinned external contract.
    candidate_message_ids: NotRequired[list[str] | None]
    retrieval_context: NotRequired[bool]
    excluded_source_classes: NotRequired[list[str]]


class CompletedMessage(TypedDict):
    id: str
    role: Literal["assistant"]
    status: Literal["completed"]
    content: str


class ContinuationStatus(TypedDict):
    state: Literal["not_found", "in_progress", "unknown", "completed"]
    message_id: str | None


class Conversation(TypedDict):
    id: str
    title: str


class ConversationList(TypedDict):
    conversations: list[Conversation]


class ConversationDetail(TypedDict):
    conversation: Conversation
    messages: list[JsonObject]


class APIError(RuntimeError):
    """A safe HTTP rejection. Preserve the original key and complete body."""

    def __init__(self, status: int, code: str):
        self.status = status
        self.code = code
        super().__init__(f"HTTP {status} {code}; retain the original operation key")


class ContractMismatch(ValueError):
    """The operator-supplied external contract is incompatible."""


class CapabilityUnavailable(RuntimeError):
    """An operation is unavailable in this client configuration or deployment."""


# Retain only known protocol codes, never server-selected diagnostic strings.
SAFE_CODES = frozenset(
    {
        "authentication_required",
        "invalid_identity",
        "application_client_denied",
        "client_identity_override_denied",
        "client_operation_denied",
        "workspace_not_authorized",
        "access_denied",
        "not_found",
        "application_not_registered",
        "application_scope_invalid",
        "origin_denied",
        "request_scope_invalid",
        "request_body_timeout",
        "request_body_too_large",
        "conversation_conflict",
        "conversation_busy",
        "conversation_source_authority_changed",
        "validation_error",
        "authentication_unavailable",
        "application_client_policy_unavailable",
        "workspace_authority_unavailable",
        "storage_unavailable",
        "provider_unavailable",
        "tool_unavailable",
        "retrieval_unavailable",
        "retrieval_intent_conflict",
        "reasoning_epoch_changed",
        "reasoning_busy",
        "reasoning_disabled",
        "reasoning_capacity",
        "reasoning_intent_conflict",
        "reasoning_cursor_invalid",
        "budget_exhausted",
        "policy_denied",
    }
)


class UncertainTurn(RuntimeError):
    """An observation is incomplete; only the original key may be reconciled."""


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def sse_events(chunks: Iterable[bytes]):
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
                elif event in {
                    "message.created",
                    "response.delta",
                    "response.error",
                    "response.completed",
                }:
                    raise UncertainTurn("missing_event_payload")
            buffer = normalized
            if len(buffer.encode()) > 262144:
                raise UncertainTurn("event_too_large")
        buffer += decoder.decode(b"", final=True)
        if buffer.strip():
            raise UncertainTurn("truncated_event")
    except (ValueError, RecursionError):
        raise UncertainTurn("invalid_stream") from None


def read_completion(
    chunks: Iterable[bytes], provisional: Callable[[str], None] | None = None
) -> CompletedMessage:
    completed, assistant_id, text, user_id = None, None, "", None
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
            if not isinstance(identity, str) or str(UUID(identity)) != identity:
                raise UncertainTurn("invalid_message_id")
            role = message.get("role")
            if role == "user" and user_id is None and assistant_id is None:
                user_id = identity
            elif (
                role == "assistant"
                and user_id
                and assistant_id is None
                and identity != user_id
            ):
                assistant_id = identity
            else:
                raise UncertainTurn("invalid_created_order")
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
            if provisional is not None:
                provisional(delta)
        elif event == "response.error":
            raise UncertainTurn("response_error")
        elif event == "response.completed":
            completed = data.get("message")
            content = completed.get("content") if isinstance(completed, dict) else None
            if (
                not isinstance(completed, dict)
                or completed.get("id") != assistant_id
                or completed.get("role") != "assistant"
                or completed.get("status") != "completed"
                or not isinstance(content, str)
                or len(content) > 20000
                or not content.strip()
            ):
                raise UncertainTurn("invalid_terminal")
        else:
            raise UncertainTurn("invalid_event")
    if completed is None:
        raise UncertainTurn("terminal_missing")
    return cast(CompletedMessage, completed)


class Client:
    def __init__(
        self,
        base_url: str,
        token: str,
        *,
        application: str,
        workspace: str | None = None,
        contract_version: str = CONSUMER_VERSION,
        retrieval_enabled: bool = False,
        allow_loopback: bool = False,
        timeout: float = 30,
    ) -> None:
        if (
            not re.fullmatch(r"1\.\d{1,4}\.\d{1,4}", contract_version)
            or int(contract_version.split(".")[1]) < 2
        ):
            raise ContractMismatch("consumer_v1_2_or_later_required")
        try:
            url = urllib.parse.urlsplit(base_url)
            _ = url.port
        except ValueError:
            raise ValueError("invalid_base_url") from None
        loopback = url.hostname in {"127.0.0.1", "::1"}
        if (
            url.scheme not in {"https", "http"}
            or not url.hostname
            or url.username is not None
            or url.password is not None
            or any(c.isspace() or ord(c) < 33 for c in base_url)
            or url.query
            or url.fragment
            or url.path not in {"", "/"}
            or (url.scheme != "https" and not (allow_loopback and loopback))
        ):
            raise ValueError(
                "HTTPS required; explicit loopback is for synthetic fixtures only"
            )
        if not re.fullmatch(r"[A-Za-z0-9._~-]{1,8192}", token):
            raise ValueError("invalid token")
        if not re.fullmatch(r"[a-z][a-z0-9_-]{1,40}", application):
            raise ValueError("invalid_application")
        if workspace is not None and not re.fullmatch(
            r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,99}", workspace
        ):
            raise ValueError("invalid_workspace")
        if not math.isfinite(timeout) or not 0 < timeout <= 120:
            raise ValueError("invalid_timeout")
        self._contract_version = contract_version
        self._retrieval_enabled = retrieval_enabled
        self._base_url, self._token, self._workspace = (
            base_url.rstrip("/"),
            token,
            workspace,
        )
        self._application, self._timeout = application, timeout
        # Ignore environment proxies; never forward tokens through redirects.
        self._opener = urllib.request.build_opener(
            urllib.request.ProxyHandler({}), _NoRedirect()
        )

    def diagnostics(self) -> JsonObject:
        """Static client configuration and evidence, with identifiers omitted."""
        return {
            "contract_version": self._contract_version,
            "retrieval_configured": self._retrieval_enabled,
            "workspace_configured": self._workspace is not None,
        }

    def _request(self, method: str, path: str, body: object = None, *, max_body=131072):
        headers = {
            "Authorization": "Bearer " + self._token,
            "X-Application-ID": self._application,
            "Accept": "text/event-stream"
            if path.endswith("/continue")
            else "application/json",
        }
        if self._workspace is not None:
            headers["X-Workspace-ID"] = self._workspace
        data = None if body is None else json.dumps(body, allow_nan=False).encode()
        if data is not None:
            if len(data) > max_body:
                raise APIError(413, "request_body_too_large")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(
            self._base_url + path, data=data, method=method, headers=headers
        )
        try:
            return self._opener.open(req, timeout=self._timeout)
        except urllib.error.HTTPError as error:
            code = "request_failed"
            try:
                candidate = json.loads(error.read(65537)).get("error", {}).get("code")
                if isinstance(candidate, str) and candidate in SAFE_CODES:
                    code = candidate
            except (
                OSError,
                ValueError,
                AttributeError,
                RecursionError,
                http.client.HTTPException,
            ):
                pass
            finally:
                error.close()
            raise APIError(error.code, code) from None
        except (OSError, ValueError, http.client.HTTPException):
            raise UncertainTurn("transport_unknown; retain the original key") from None

    def _json(
        self,
        method: str,
        path: str,
        body: object = None,
        *,
        max_body=131072,
        max_response=4_000_000,
    ) -> JsonObject:
        try:
            with self._request(method, path, body, max_body=max_body) as response:
                raw = response.read(max_response + 1)
                if len(raw) > max_response:
                    raise UncertainTurn("response_too_large")
                value = json.loads(raw)
                if not isinstance(value, dict):
                    raise UncertainTurn("invalid_json_response")
                return value
        except (OSError, ValueError, RecursionError, http.client.HTTPException):
            raise UncertainTurn(
                "json_response_unknown; retain the original key"
            ) from None

    def retrieve(
        self,
        query: str,
        key: Identity,
        *,
        sources: tuple[str, ...] = ("local",),
        tool: bool = False,
    ) -> JsonObject:
        """Explicit standalone read under current server source rights."""
        if not self._retrieval_enabled:
            raise CapabilityUnavailable("retrieval_not_configured")
        path = "/v1/tools/retrieval.query.v1/invoke" if tool else "/v1/retrieval/query"
        try:
            return self._json(
                "POST",
                path,
                {
                    "schema_version": "retrieval-v1",
                    "query": query,
                    "idempotency_key": _id(key),
                    "sources": list(sources),
                },
            )
        except APIError as error:
            if error.code in {"retrieval_unavailable", "tool_unavailable"}:
                raise CapabilityUnavailable(error.code) from None
            raise

    def create(self, title: str | None, key: Identity) -> Conversation:
        return cast(
            Conversation,
            self._json(
                "POST",
                "/v1/conversations",
                {"title": title, "idempotency_key": _id(key)},
            ),
        )

    def list(self) -> ConversationList:
        return cast(ConversationList, self._json("GET", "/v1/conversations"))

    def detail(self, conversation_id: Identity) -> ConversationDetail:
        return cast(
            ConversationDetail, self._json("GET", _conversation(conversation_id))
        )

    def preview(self, conversation_id: Identity, body: Continuation) -> JsonObject:
        _id(body["idempotency_key"])
        return self._json(
            "POST", _conversation(conversation_id) + "/context-preview", body
        )

    def status(self, conversation_id: Identity, key: Identity) -> ContinuationStatus:
        value = self._json(
            "GET", _conversation(conversation_id) + "/continuations/" + _id(key)
        )
        state, message_id = value.get("state"), value.get("message_id")
        if (
            state not in ("not_found", "in_progress", "unknown", "completed")
            or "message_id" not in value
            or (message_id is not None and not isinstance(message_id, str))
            or (state == "completed" and not message_id)
            or (state == "not_found" and message_id is not None)
        ):
            raise UncertainTurn("invalid_status")
        if message_id is not None:
            try:
                _id(message_id)
            except ValueError:
                raise UncertainTurn("invalid_status") from None
        return cast(ContinuationStatus, value)

    def continue_turn(
        self,
        conversation_id: Identity,
        body: Continuation,
        provisional: Callable[[str], None] | None = None,
    ) -> CompletedMessage:
        """Send once. Treat deltas as provisional and reconcile by original key."""
        key = _id(body["idempotency_key"])
        path = _conversation(conversation_id) + "/continue"
        # HTTP errors before SSE are distinct from an unconfirmed 200 stream.
        with self._request("POST", path, body) as response:
            try:
                if response.headers.get_content_type() != "text/event-stream":
                    raise UncertainTurn("unexpected_response_type")
                completed = read_completion(
                    iter(lambda: response.read1(4096), b""), provisional
                )
            except (OSError, ValueError, http.client.HTTPException):
                raise UncertainTurn("stream_unknown; reconcile original key") from None
        try:
            status = self.status(conversation_id, key)
        except APIError:
            raise UncertainTurn("canonical_status_unavailable") from None
        if status["state"] != "completed" or status["message_id"] != completed["id"]:
            raise UncertainTurn("canonical_status_disagrees")
        return completed


def _id(value: Identity) -> str:
    try:
        return str(UUID(str(value)))
    except ValueError:
        raise ValueError("invalid_uuid") from None


def _conversation(value: Identity) -> str:
    return "/v1/conversations/" + _id(value)

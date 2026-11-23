"""An explicitly test-only, stateless MCP consumer of authorized PAS context."""

import hmac
import json
import re
from collections import OrderedDict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from secrets import token_bytes, token_urlsafe
from threading import BoundedSemaphore, Lock
from time import monotonic
from urllib.parse import urlsplit

import anyio
from jsonschema import Draft202012Validator
from mcp import types
from mcp.server import Server
from mcp.server.auth.routes import build_resource_metadata_url
from mcp.server.auth.settings import AuthSettings
from mcp.server.transport_security import TransportSecuritySettings
from mcp.shared.exceptions import MCPError
from mcp.shared.inbound import classify_inbound_request
from mcp_types.version import HANDSHAKE_PROTOCOL_VERSIONS
from starlette.requests import ClientDisconnect, Request
from starlette.responses import JSONResponse, Response

from .contracts import (
    MAX_HITS,
    PURPOSE,
    READ_SCOPE,
    RECIPIENT,
    AuthorizedSourceReader,
    BrowserPrincipal,
    FetchedRecord,
    Identity,
    Operation,
    SearchPage,
    Selection,
    SourceBinding,
    SourceInstallation,
    VerifiedAccess,
    VerifyAccess,
    VerifyBrowser,
)

REVISION = "2026-07-28"
MAX_BYTES = 8192
DEADLINE_SECONDS = 2
SELECTOR_TTL = timedelta(seconds=60)
MAX_SELECTORS = 1024
CALLS_PER_MINUTE = 30
MAX_RATE_KEYS = 1024
MAX_IN_FLIGHT = 8
CITATION_RESOURCE_PATH = "/mcp-citations/v1"
CITATION_VIEW_PATH = "/citations/v1/"
_LOCATOR = re.compile(r"[0-9a-f]{64}")
_BROWSER_HEADERS = {
    "Cache-Control": "private, no-store",
    "Referrer-Policy": "no-referrer",
    "Content-Security-Policy": "default-src 'none'; frame-ancestors 'none'",
    "X-Content-Type-Options": "nosniff",
}
_BEARER = re.compile(r"Bearer +([A-Za-z0-9._~+/-]+=*)", re.IGNORECASE | re.ASCII)
_ID = {"type": "string", "minLength": 1, "maxLength": 200, "pattern": r"^[A-Za-z0-9_-]+$"}
_STRING = {"type": "string"}


def _object(**properties):
    return {
        "type": "object", "properties": properties, "required": list(properties),
        "additionalProperties": False,
    }


_INPUT = {
    "search": _object(query={"type": "string", "minLength": 1, "maxLength": 256, "pattern": r"\S"}),
    "fetch": _object(id=_ID),
}
_OUTPUT = {
    "search": _object(results={
        "type": "array", "maxItems": MAX_HITS, "items": _object(id=_ID, title=_STRING),
    }),
    "fetch": _object(
        id=_ID, title=_STRING, text=_STRING, source=_STRING, revision=_STRING,
        observed_at={"type": "string", "format": "date-time"},
        fresh_until={"type": "string", "format": "date-time"},
    ),
}
_URL = {"type": "string", "format": "uri", "pattern": r"^https://"}
_CITATION_OUTPUT = {
    "search": _object(results={
        "type": "array", "maxItems": MAX_HITS, "items": _object(id=_ID, title=_STRING, url=_URL),
    }),
    "fetch": _object(id=_ID, title=_STRING, text=_STRING, url=_URL),
}
_INPUT_VALIDATORS = {name: Draft202012Validator(schema) for name, schema in _INPUT.items()}
_SECURITY = [{"type": "oauth2", "scopes": [READ_SCOPE]}]
_DESCRIPTIONS = {
    "search": "Find records in your connected application.",
    "fetch": "Read the authorized projection of a search result.",
}


@dataclass(frozen=True, slots=True)
class _Selector:
    identity: Identity
    binding: SourceBinding
    selection: Selection
    title: str
    locator: str | None = None


@dataclass(frozen=True, slots=True)
class _Citation:
    identity: Identity
    binding: SourceBinding
    selection: Selection
    title: str

    def matches(self, principal):
        return principal == BrowserPrincipal(
            self.identity.issuer, self.identity.subject, self.binding.tenant,
            self.binding.owner_id, self.binding.acting_user_id,
        )


class _State:
    def __init__(self):
        self._lock = Lock()
        self._rates = OrderedDict()
        self._selectors = OrderedDict()
        self._citations = OrderedDict()

    def admit_call(self, identity):
        # Count across clients/connections for a verified issuer and subject.
        key = (identity.issuer, identity.subject)
        with self._lock:
            now = monotonic()
            while self._rates and next(iter(self._rates.values()))[0] <= now:
                self._rates.popitem(last=False)
            if key not in self._rates:
                if len(self._rates) >= MAX_RATE_KEYS:
                    return False
                self._rates[key] = (now + 60, 0)
            expires, count = self._rates[key]
            if count >= CALLS_PER_MINUTE:
                return False
            self._rates[key] = (expires, count + 1)
            return True

    def selection(self, handle, identity, binding, now):
        with self._lock:
            selector = self._selectors.get(handle)
            if selector is None or (selector.identity, selector.binding) != (identity, binding):
                raise ValueError("unavailable")
            if selector.selection.expires_at <= now:
                del self._selectors[handle]
                raise ValueError("unavailable")
            return selector

    def citation(self, locator, now):
        with self._lock:
            citation = self._citations.get(locator)
            if citation is None or citation.selection.expires_at <= now:
                raise ValueError("unavailable")
            return citation

    def publish(self, pending, citations):
        with self._lock:
            if self._selectors.keys() & pending.keys() or any(
                self._citations[locator] != citations[locator]
                for locator in self._citations.keys() & citations.keys()
            ):
                raise ValueError("unavailable")
            self._selectors.update(pending)
            self._citations.update(citations)
            while len(self._selectors) > MAX_SELECTORS:
                self._selectors.popitem(last=False)
            while len(self._citations) > MAX_SELECTORS:
                self._citations.popitem(last=False)


class _OAuthDenied(Exception):
    def __init__(self, error):
        self.error = error


class _FrameTooLarge(Exception):
    pass


@dataclass(slots=True)
class _Request:
    access: VerifiedAccess
    token: str = field(repr=False)
    raw: bytes = field(repr=False)
    deadline: float
    rate_limited: bool = False


def _json_bytes(value, *, ascii_only=True):
    return json.dumps(value, ensure_ascii=ascii_only, allow_nan=False, separators=(",", ":")).encode()


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("duplicate JSON key")
        value[key] = item
    return value


async def _frame(request):
    raw = bytearray()
    async for chunk in request.stream():
        if len(raw) + len(chunk) > MAX_BYTES:
            raise _FrameTooLarge
        raw.extend(chunk)
    body = json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    _json_bytes(body, ascii_only=False)  # Also reject escaped surrogates and non-finite numbers.
    return bytes(raw), body


def _rpc_error(code, message, *, status=400, body=None, data=None):
    request_id = body.get("id") if isinstance(body, dict) else None
    error = {"code": code, "message": message}
    if data is not None:
        error["data"] = data
    return JSONResponse(
        {"jsonrpc": "2.0", "id": request_id if type(request_id) in {int, str} else None, "error": error},
        status_code=status,
    )


def _utc(value):
    if value.utcoffset() != timedelta(0):
        raise ValueError("unavailable")
    return value.isoformat().replace("+00:00", "Z")


def context_mcp_app(
    *,
    issuer: str,
    resource: str,
    approved_clients: frozenset[str],
    verify_access: VerifyAccess,
    reader: AuthorizedSourceReader,
    enabled: bool = False,
    environment: str,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    workspace_less_sources: frozenset[SourceInstallation] = frozenset(),
    verify_browser: VerifyBrowser | None = None,
    process_count: int = 1,
):
    """Build a synthetic ASGI app with the host's verified identity and reader."""
    auth = AuthSettings(
        issuer_url=issuer, resource_server_url=resource, required_scopes=[READ_SCOPE],
        validate_token_resource=False,  # This edge enforces exact audience equality.
    )
    resource_url = urlsplit(resource)
    if (
        enabled is not True or environment != "test" or not callable(verify_access)
        or not callable(clock) or not isinstance(approved_clients, frozenset) or not approved_clients
        or any(not isinstance(client, str) or not 1 <= len(client) <= 1024 for client in approved_clients)
        or not all(callable(getattr(reader, method, None)) for method in ("resolve", "read", "budget"))
        or str(auth.issuer_url) != issuer or str(auth.resource_server_url) != resource
        or any(
            url.scheme != "https" or not url.hostname or url.username is not None
            or url.query or url.fragment
            for url in (urlsplit(issuer), resource_url)
        )
        or not re.fullmatch(r"/[a-zA-Z0-9_/-]*[a-zA-Z0-9_-]", resource_url.path)
        or type(process_count) is not int or process_count != 1
        or not isinstance(workspace_less_sources, frozenset)
        or any(
            not isinstance(item, SourceInstallation)
            or not all(isinstance(part, str) and part and part.strip() == part for part in (
                item.application_id, item.source_id, item.installation_id,
            ))
            for item in workspace_less_sources
        )
        or (verify_browser is not None and not callable(verify_browser))
        or (resource_url.path == CITATION_RESOURCE_PATH) != (verify_browser is not None)
        or (verify_browser is not None and resource_url.netloc != resource_url.hostname)
    ):
        raise ValueError("mcp_unavailable")

    clients = frozenset(approved_clients)
    resource_origin = f"https://{resource_url.netloc}"
    metadata_url = str(build_resource_metadata_url(auth.resource_server_url))
    metadata_path = urlsplit(metadata_url).path
    state = _State()
    slots = BoundedSemaphore(MAX_IN_FLIGHT)
    citation_key = token_bytes(32) if verify_browser is not None else None
    output = _CITATION_OUTPUT if citation_key is not None else _OUTPUT
    output_validators = {
        name: Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)
        for name, schema in output.items()
    }

    def citation_url(locator):
        return f"{resource_origin}{CITATION_VIEW_PATH}{locator}"

    def challenge(error):
        parts = [f'resource_metadata="{metadata_url}"']
        if error is not None:
            parts.append(f'error="{error}"')
        if error == "insufficient_scope":
            parts.append(f'scope="{READ_SCOPE}"')
        return "Bearer " + ", ".join(parts)

    async def authenticate(token):
        try:
            access = await verify_access(token)
            now = clock()
            if (
                not isinstance(access, VerifiedAccess) or access.active is not True
                or access.human is not True or access.token_kind != "access_token"
                or not isinstance(access.identity, Identity) or access.identity.issuer != issuer
                or not isinstance(access.identity.subject, str) or not 1 <= len(access.identity.subject) <= 512
                or access.identity.client_id not in clients or access.resource != resource
                or not isinstance(access.scopes, frozenset)
                or access.expires_at <= now or (access.not_before is not None and access.not_before > now)
            ):
                raise _OAuthDenied("invalid_token")
        except Exception:  # noqa: BLE001 - verifier failures are indistinguishable from invalid tokens
            raise _OAuthDenied("invalid_token") from None
        if READ_SCOPE not in access.scopes:
            raise _OAuthDenied("insufficient_scope")
        return access

    async def resolve(identity, operation: Operation):
        binding = await reader.resolve(identity, operation)
        if (
            not isinstance(binding, SourceBinding) or binding.owner_id in {"", "local"}
            or not binding.tenant
            or not binding.connection_id or binding.connection_generation < 1
            or not binding.source_id or not binding.installation_revision or binding.installation_epoch < 1
            or not binding.grant_id or binding.grant_version < 1 or binding.grant_epoch < 1
            or not binding.policy_version or binding.recipient != RECIPIENT or binding.purpose != PURPOSE
            or "title" not in binding.fields or binding.expires_at <= clock()
            or (citation_key is not None and not binding.installation_id)
        ):
            raise ValueError("unavailable")
        workspace = binding.scope.workspace_id
        installation = SourceInstallation(
            binding.tenant, binding.scope.application_id, binding.source_id, binding.installation_id or "",
        )
        if installation in workspace_less_sources:
            if workspace is not None or "workspace_id" not in binding.scope.model_fields_set:
                raise ValueError("unavailable")
        elif not isinstance(workspace, str) or not workspace or workspace.strip() != workspace:
            raise ValueError("unavailable")
        return binding

    async def browser_view(request):
        denied = Response(status_code=404, headers=_BROWSER_HEADERS)
        path = request.url.path
        locator = path.removeprefix(CITATION_VIEW_PATH)
        if (
            request.method != "GET" or not _LOCATOR.fullmatch(locator)
            or request.scope.get("raw_path", path.encode()) != path.encode()
            or request.scope.get("query_string")
        ):
            return denied
        deadline = monotonic() + DEADLINE_SECONDS
        try:
            with anyio.fail_after(DEADLINE_SECONDS):
                principal = await verify_browser(request)
                if not isinstance(principal, BrowserPrincipal):
                    return denied
                citation = state.citation(locator, clock())
                if not citation.matches(principal):
                    return denied
                identity, binding, selected = citation.identity, citation.binding, citation.selection
                if await resolve(identity, "fetch") != binding:
                    return denied
                if not state.admit_call(identity):
                    return Response(status_code=429, headers=_BROWSER_HEADERS)
                budget = reader.budget(deadline)
                budget.check()
                read = await reader.read(identity, binding, selected, budget)
                record = _exact_record(read.value, binding, selected, citation.title, clock())
                raw = _json_bytes({"title": record.title, "text": record.text}, ascii_only=False)
                budget.charge_bytes(raw)
                budget.charge_tokens(raw)
                if (
                    len(raw) > MAX_BYTES or await resolve(identity, "fetch") != binding
                    or await verify_browser(request) != principal
                ):
                    return denied
                read.revalidate()
                await anyio.lowlevel.checkpoint_if_cancelled()
                budget.check()
                if (
                    clock() >= min(selected.expires_at, record.fresh_until, binding.expires_at)
                    or state.citation(locator, clock()) != citation or monotonic() >= deadline
                ):
                    return denied
                return Response(raw, media_type="application/json", headers=_BROWSER_HEADERS)
        except Exception:  # noqa: BLE001 - browser denials reveal no binding or domain diagnostics
            return denied

    def tool_error(oauth=None):
        return types.CallToolResult(
            is_error=True, content=[types.TextContent(type="text", text="Context unavailable.")],
            meta={"mcp/www_authenticate": [challenge(oauth)]} if oauth else None,
        )

    async def list_tools(_ctx, params):
        if params and params.cursor is not None:
            raise MCPError(types.INVALID_PARAMS, "Invalid cursor")
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=name, description=_DESCRIPTIONS[name], input_schema=schema,
                    output_schema=output[name], meta={"securitySchemes": _SECURITY},
                    annotations=types.ToolAnnotations(
                        read_only_hint=True, destructive_hint=False, open_world_hint=False,
                    ),
                )
                for name, schema in _INPUT.items()
            ],
            ttl_ms=0,
        )

    async def discover(ctx, _params):
        return types.DiscoverResult(
            supported_versions=[REVISION], capabilities=server.get_capabilities(protocol_version=ctx.protocol_version),
            meta={"securitySchemes": _SECURITY}, ttl_ms=0,
        )

    async def tool_security(ctx, call_next):
        result = await call_next(ctx)
        if ctx.method == "tools/list":
            # OpenAI consumes the top-level field. Keep the SDK-compatible mirror as well.
            for tool in result["tools"]:
                tool["securitySchemes"] = _SECURITY
        return result

    async def call_tool(ctx, params):
        name = params.name
        if name not in _INPUT:
            raise MCPError(types.INVALID_PARAMS, "Unknown tool")
        if not _INPUT_VALIDATORS[name].is_valid(params.arguments):
            raise MCPError(types.INVALID_PARAMS, "Invalid tool arguments")
        argument = next(iter(params.arguments.values()))
        try:
            if len(argument.encode("utf-8")) > (256 if name == "search" else 200) or (
                name == "fetch" and not re.fullmatch(r"[A-Za-z0-9_-]+", argument)
            ):
                raise ValueError
        except ValueError:
            raise MCPError(types.INVALID_PARAMS, "Invalid tool arguments") from None

        request = ctx.request.state.context_mcp
        identity = request.access.identity
        try:
            with anyio.fail_after(max(0, request.deadline - monotonic())):
                budget = reader.budget(request.deadline)
                budget.charge_bytes(request.raw)
                budget.charge_tokens(request.raw)
                binding = await resolve(identity, name)
                if not state.admit_call(identity):
                    request.rate_limited = True
                    return tool_error()
                selector = (
                    None if name == "search" else state.selection(argument, identity, binding, clock())
                )
                selection = argument if selector is None else selector.selection
                citation = (
                    state.citation(selector.locator, clock()) if selector is not None and selector.locator else None
                )
                budget.check()
                read = await reader.read(identity, binding, selection, budget)
                pending = {}
                citations = {}
                if selector is None:
                    data, pending, citations = _search_output(
                        read.value, identity, binding, clock(), citation_key, citation_url,
                    )
                else:
                    record = _exact_record(read.value, binding, selection, selector.title, clock())
                    data = _fetch_output(record, argument, selector.locator, citation_url)
                output_validators[name].validate(data)
                result = types.CallToolResult(
                    content=[types.TextContent(type="text", text=_json_bytes(data, ascii_only=False).decode())],
                    structured_content=data,
                    meta={types.SERVER_INFO_META_KEY: server.server_info_stamp},
                )
                # Match the pinned SDK's compact JSON wire serialization, including its metadata stamp.
                serialized = _json_bytes(result.model_dump(mode="json", by_alias=True, exclude_none=True))
                budget.charge_bytes(serialized)
                if len(serialized) > MAX_BYTES:
                    raise ValueError("unavailable")
                budget.charge_tokens(serialized)
                if await resolve(identity, name) != binding:
                    raise ValueError("unavailable")
                current_access = await authenticate(request.token)
                if current_access.identity != identity:
                    raise ValueError("unavailable")
                read.revalidate()
                await anyio.lowlevel.checkpoint_if_cancelled()
                valid_until = min([
                    binding.expires_at, current_access.expires_at,
                    *(selector.selection.expires_at for selector in pending.values()),
                ])
                if isinstance(selection, Selection):
                    valid_until = min(valid_until, selection.expires_at, read.value.fresh_until)
                if clock() >= valid_until or (
                    citation is not None and state.citation(selector.locator, clock()) != citation
                ):
                    raise ValueError("unavailable")
                budget.check()
                if monotonic() >= request.deadline:
                    raise ValueError("unavailable")
                state.publish(pending, citations)
                return result
        except _OAuthDenied as error:
            return tool_error(error.error)
        except Exception:  # noqa: BLE001 - keep source and policy diagnostics out of the wire and logs
            return tool_error()

    server = Server(
        "personal-ai-mcp-context", version="0.1.0", on_list_tools=list_tools, on_call_tool=call_tool,
        get_tool_input_schema=_INPUT.get,
    )
    server.add_request_handler("server/discover", types.RequestParams, discover)
    server.middleware[:] = [tool_security]  # No SDK telemetry exports from this synthetic edge.

    class ProtectedContext:
        def __init__(self, app):
            self.app = app

        async def __call__(self, scope, receive, send):
            if scope["type"] != "http":
                await self.app(scope, receive, send)
                return
            request = Request(scope, receive)
            is_citation = verify_browser is not None and scope["path"].startswith(CITATION_VIEW_PATH)
            browser_headers = _BROWSER_HEADERS if is_citation else None
            if request.headers.getlist("host") != [resource_url.netloc]:
                response = Response(status_code=421, headers=browser_headers)
            elif request.headers.getlist("origin") not in ([], [resource_origin]):
                response = Response(status_code=403, headers=browser_headers)
            elif scope.get("scheme") != "https":
                response = Response(status_code=400, headers=browser_headers)
            elif is_citation:
                if slots.acquire(blocking=False):
                    try:
                        response = await browser_view(request)
                    finally:
                        slots.release()
                else:
                    response = Response(status_code=404, headers=_BROWSER_HEADERS)
            elif scope["path"] == metadata_path:
                await self.app(scope, receive, send)
                return
            elif scope["path"] != resource_url.path:
                # An ASGI mount may strip root_path during routing. Only these
                # canonical paths may ever reach the inner resource app.
                response = Response(status_code=404)
            elif not slots.acquire(blocking=False):
                response = Response(status_code=429)
            else:
                try:
                    response = await self.dispatch(request, scope, receive, send)
                finally:
                    slots.release()
                if response is None:
                    return
            await response(scope, receive, send)

        async def dispatch(self, request, scope, receive, send):
            deadline = monotonic() + DEADLINE_SECONDS
            headers = request.headers
            try:
                with anyio.fail_after(DEADLINE_SECONDS):
                    credentials = headers.getlist("authorization")
                    if not credentials:
                        raise _OAuthDenied(None)
                    if len(credentials) != 1 or len(credentials[0]) > 4128:
                        raise _OAuthDenied("invalid_token")
                    match = _BEARER.fullmatch(credentials[0])
                    if match is None or len(match[1]) > 4096:
                        raise _OAuthDenied("invalid_token")
                    token = match[1]
                    access = await authenticate(token)
            except (_OAuthDenied, TimeoutError) as error:
                code = error.error if isinstance(error, _OAuthDenied) else "invalid_token"
                return Response(
                    status_code=403 if code == "insufficient_scope" else 401,
                    headers={"WWW-Authenticate": challenge(code), "Cache-Control": "no-store"},
                )

            if request.method != "POST":
                return Response(status_code=405, headers={"Allow": "POST"})
            if headers.get("content-type", "").partition(";")[0].strip().lower() != "application/json":
                return Response(status_code=400)
            for field_name in ("content-type", "mcp-protocol-version", "mcp-method", "mcp-name"):
                values = headers.getlist(field_name)
                if len(values) > 1 or any("," in value for value in values):
                    return Response(status_code=400)
            try:
                with anyio.fail_after(max(0, deadline - monotonic())):
                    raw, body = await _frame(request)
            except _FrameTooLarge:
                return Response(status_code=413)
            except ClientDisconnect:
                return None
            except TimeoutError:
                return Response(status_code=408)
            except (ValueError, RecursionError):
                return _rpc_error(types.PARSE_ERROR, "Parse error")

            version = headers.get("mcp-protocol-version")
            # The SDK otherwise routes these headers into its legacy handshake.
            if version is None or version in HANDSHAKE_PROTOCOL_VERSIONS:
                verdict = classify_inbound_request(
                    body if isinstance(body, dict) else {}, headers=headers,
                    supported_modern_versions=(REVISION,),
                )
                if version in HANDSHAKE_PROTOCOL_VERSIONS and verdict.code == types.INVALID_PARAMS:
                    return _rpc_error(
                        types.UNSUPPORTED_PROTOCOL_VERSION, "Unsupported protocol version", body=body,
                        data={"requested": version, "supported": [REVISION]},
                    )
                return _rpc_error(verdict.code, verdict.message, body=body, data=verdict.data)

            if isinstance(body, dict) and body.get("method") == "tools/call":
                params = body.get("params")
                if version == REVISION and isinstance(params, dict) and (
                    body.keys() - {"jsonrpc", "id", "method", "params"}
                    or params.keys() - {"name", "arguments", "_meta"}
                ):
                    return _rpc_error(types.INVALID_PARAMS, "Invalid tool arguments", body=body)

            context_request = _Request(access, token, raw, deadline)
            state_values = {**scope.get("state", {}), "context_mcp": context_request}

            async def replay_body():
                nonlocal raw
                if raw is None:
                    return await receive()
                message = {"type": "http.request", "body": raw, "more_body": False}
                raw = None
                return message

            async def no_store(message):
                if context_request.rate_limited:
                    if message["type"] == "http.response.start":
                        await send({
                            **message, "status": 429,
                            "headers": [(b"content-length", b"0"), (b"cache-control", b"no-store")],
                        })
                    elif message["type"] == "http.response.body" and not message.get("more_body", False):
                        await send({"type": "http.response.body", "body": b"", "more_body": False})
                    return
                if message["type"] == "http.response.start":
                    message = {**message, "headers": [*message["headers"], (b"cache-control", b"no-store")]}
                await send(message)

            await self.app({**scope, "state": state_values}, replay_body, no_store)
            return None

    # Use the SDK's disconnect watcher. With no notifications and a short
    # deadline it returns a JSON result before committing to an SSE stream.
    app = server.streamable_http_app(
        streamable_http_path=resource_url.path, stateless_http=True, auth=auth,
        max_request_body_size=MAX_BYTES,
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )
    app.router.redirect_slashes = False
    app.add_middleware(ProtectedContext)
    return app


def _search_output(value, identity, binding, now, citation_key, citation_url):
    if not isinstance(value, SearchPage) or len(value.hits) > MAX_HITS or not value.watermark:
        raise ValueError("unavailable")
    pending = {}
    citations = {}
    results = []
    seen = set()
    for hit in value.hits:
        fresh_until = min(binding.expires_at, hit.fresh_until)
        if fresh_until <= now or not hit.record_ref or not hit.revision or hit.record_ref in seen:
            raise ValueError("unavailable")
        seen.add(hit.record_ref)
        handle = token_urlsafe(24)
        if handle in pending:
            raise ValueError("unavailable")
        locator = None
        row = {"id": handle, "title": hit.title}
        if citation_key is not None:
            selected = Selection(hit.record_ref, hit.revision, value.watermark, fresh_until)
            locator = hmac.digest(citation_key, repr((identity, binding, selected)).encode(), "sha256").hex()
            citations[locator] = _Citation(identity, binding, selected, hit.title)
            row["url"] = citation_url(locator)
        pending[handle] = _Selector(
            identity, binding, Selection(
                hit.record_ref, hit.revision, value.watermark, min(now + SELECTOR_TTL, fresh_until),
            ), hit.title, locator,
        )
        results.append(row)
    return {"results": results}, pending, citations


def _exact_record(value, binding, selection, title, now):
    if (
        not isinstance(value, FetchedRecord)
        or (value.record_ref, value.revision, value.watermark, value.source, value.title)
        != (selection.record_ref, selection.revision, selection.watermark, binding.source_id, title)
        or not value.observed_at <= now < value.fresh_until <= binding.expires_at
    ):
        raise ValueError("unavailable")
    return value


def _fetch_output(record, selector, locator, citation_url):
    if locator is not None:
        return {"id": selector, "title": record.title, "text": record.text, "url": citation_url(locator)}
    return {
        "id": selector, "title": record.title, "text": record.text, "source": record.source,
        "revision": record.revision, "observed_at": _utc(record.observed_at),
        "fresh_until": _utc(record.fresh_until),
    }

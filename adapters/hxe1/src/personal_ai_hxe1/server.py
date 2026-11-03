"""Expose the canonical PI-5 read-only tool to a bound, verified pilot client."""

import json
from datetime import UTC, datetime
from threading import BoundedSemaphore

from mcp import types
from mcp.server import Server
from mcp.shared.exceptions import MCPError
from personal_ai.auth.application_clients import (
    is_external_client_request,
    require_current_client_authority,
)
from personal_ai.auth.scope import current_request_scope, current_verified_principal
from personal_ai.retrieval.contracts import RetrievalQuery
from personal_ai.retrieval.installation import load_snapshot
from personal_ai.retrieval.tools import TOOL_ID, ToolOutcome, require_tool

_SLOTS = BoundedSemaphore(2)


def retrieval_server(service, current_registry, *, enabled=False):
    """Build for one verified host request/binding. The host owns transport auth."""
    if not enabled:
        raise ValueError("mcp_unavailable")
    scope = service.scope
    principal = current_verified_principal()
    if (
        principal is None
        or not principal.authenticated
        or principal.owner_id != scope.owner_id
        or principal.subject != scope.acting_user_id
        or current_request_scope() != scope
        or not is_external_client_request()
        or service.request_authority is None
        or service.settings.app_environment not in {"local", "test"}
    ):
        raise ValueError("mcp_unavailable")

    def snapshot():
        if (
            current_verified_principal() != principal
            or current_request_scope() != scope
        ):
            raise ValueError("mcp_unavailable")
        require_current_client_authority()
        service.request_authority()
        current = load_snapshot(service.settings.retrieval_installation_file)
        service.guard(current, tool=True)
        if any(doc.sensitivity != "public" for doc in current.installation.documents):
            raise ValueError("mcp_unavailable")
        return current

    async def list_tools(_context, params):
        try:
            current = snapshot()
            require_tool(current_registry(), scope.application_id)
            if (params and params.cursor is not None) or not any(
                doc.sensitivity == "public" and doc.allows(scope, datetime.now(UTC))
                for doc in current.installation.documents
            ):
                return types.ListToolsResult(tools=[])
            result = types.ListToolsResult(
                tools=[
                    types.Tool(
                        name=TOOL_ID,
                        input_schema=RetrievalQuery.model_json_schema(),
                        output_schema=ToolOutcome.model_json_schema(),
                        annotations=types.ToolAnnotations(
                            read_only_hint=True,
                            open_world_hint=False,
                            destructive_hint=False,
                        ),
                    )
                ],
                ttl_ms=0,
            )
            if snapshot().digest != current.digest:
                return types.ListToolsResult(tools=[])
            require_tool(current_registry(), scope.application_id)
            return result
        except Exception:  # noqa: BLE001 - suppress untrusted boundary errors
            return types.ListToolsResult(tools=[])

    async def call_tool(_context, params):
        if not _SLOTS.acquire(blocking=False):
            raise MCPError(-32000, "mcp_unavailable")
        try:
            arguments = params.arguments
            if (
                params.name != TOOL_ID
                or arguments is None
                or len(json.dumps(arguments)) > 8192
            ):
                raise ValueError("mcp_unavailable")
            current = snapshot()
            query = RetrievalQuery.model_validate(arguments)
            if query.sources != ("local",):
                raise ValueError("mcp_unavailable")

            def guard():
                if snapshot().digest != current.digest:
                    raise ValueError("mcp_unavailable")
                return require_tool(current_registry(), scope.application_id)

            outcome = await guard()(service, query, guard)
            result = outcome.model_dump(mode="json")
            guard()
            now = datetime.now(UTC)
            if any(
                item.sensitivity != "public" or item.expires_at <= now
                for item in outcome.retrieval.items
            ):
                raise ValueError("mcp_unavailable")
            return types.CallToolResult(content=[], structured_content=result)
        except Exception:  # noqa: BLE001 - suppress untrusted boundary errors
            raise MCPError(-32000, "mcp_unavailable") from None
        finally:
            _SLOTS.release()

    return Server(
        "pas-hxe1", version="0.1.0", on_list_tools=list_tools, on_call_tool=call_tool
    )

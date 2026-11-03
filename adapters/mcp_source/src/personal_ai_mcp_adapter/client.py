"""One operator-selected, hermetic read-only MCP source exchange."""

from dataclasses import dataclass, replace
from datetime import UTC, datetime
from threading import BoundedSemaphore
from uuid import UUID

import anyio
from mcp import Client, types
from personal_ai.auth.application_clients import (
    is_external_client_request,
    require_current_client_authority,
)
from personal_ai.auth.scope import current_request_scope, current_verified_principal
from personal_ai.retrieval.installation import LocalDocument

from .ingest import document_from_bytes
from .transport import HttpFixture, StdioFixture

TOOL = "fixture.document.read"
INPUT = {"type": "object", "properties": {}, "additionalProperties": False}
OUTPUT = {
    "type": "object",
    "properties": {"text": {"type": "string", "maxLength": 16000}},
    "required": ["text"],
    "additionalProperties": False,
}
PROTOCOLS = frozenset({"2026-07-28", "2025-11-25"})
_SLOTS = BoundedSemaphore(2)


@dataclass(frozen=True)
class FixtureSource:
    """Operator-issued expected document and exact peer identity for conformance."""

    issuer_id: UUID
    peer_name: str
    peer_version: str
    document: LocalDocument


async def read_fixture(transport, source, current_registration, *, enabled=False):
    """Accept only bytes that reproduce the currently authorized fixture document.

    The caller owns the transport registration. No endpoint or executable is
    accepted from a tool, request payload, or remote discovery.
    """
    if (
        not enabled
        or type(transport) not in (StdioFixture, HttpFixture)
        or not _SLOTS.acquire(blocking=False)
    ):
        raise ValueError("source_unavailable")
    try:
        scope = current_request_scope()
        principal = current_verified_principal()

        def guard():
            if (
                scope is None
                or principal is None
                or not principal.authenticated
                or principal.owner_id != scope.owner_id
                or principal.subject != scope.acting_user_id
                or current_request_scope() != scope
                or current_verified_principal() != principal
                or not is_external_client_request()
                or source.document.sensitivity != "public"
                or not source.document.allows(scope, datetime.now(UTC))
            ):
                raise ValueError("source_unavailable")
            require_current_client_authority()
            if current_registration() != (transport, source):
                raise ValueError("source_unavailable")

        guard()
        with anyio.fail_after(5):
            async with Client(
                transport.connect(), cache=None, read_timeout_seconds=2
            ) as client:
                protocol = client.protocol_version
                peer = client.server_info
                if (
                    protocol not in PROTOCOLS
                    or peer is None
                    or (peer.name, peer.version)
                    != (source.peer_name, source.peer_version)
                    or client.server_capabilities.tools is None
                ):
                    raise ValueError("source_unavailable")
                guard()
                page = await client.list_tools()
                if page.next_cursor is not None or len(page.tools) != 1:
                    raise ValueError("source_unavailable")
                tool = page.tools[0]
                hints = tool.annotations
                if (
                    tool.name != TOOL
                    or tool.execution is not None
                    or tool.input_schema != INPUT
                    or tool.output_schema != OUTPUT
                    or hints is None
                    or hints.read_only_hint is not True
                    or hints.open_world_hint is not False
                    or hints.destructive_hint is not False
                ):
                    raise ValueError("source_unavailable")
                guard()
                # Use the session directly to reject input-required and avoid tool relisting.
                result = await client.session.call_tool(TOOL, {})
                if (
                    not isinstance(result, types.CallToolResult)
                    or result.is_error
                    or result.content
                    or not isinstance(result.structured_content, dict)
                    or set(result.structured_content) != {"text"}
                    or not isinstance(result.structured_content["text"], str)
                ):
                    raise ValueError("source_unavailable")
                data = result.structured_content["text"].encode()
                document = document_from_bytes(
                    data, source.document.model_dump(exclude={"text"})
                )
        guard()
        return protocol, replace(source, document=document)
    except Exception:  # noqa: BLE001 - suppress untrusted boundary errors
        raise ValueError("source_unavailable") from None
    finally:
        _SLOTS.release()

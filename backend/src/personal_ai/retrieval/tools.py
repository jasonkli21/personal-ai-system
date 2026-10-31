"""Closed executable trust: one installed, schema-bound, read-only implementation."""

from types import MappingProxyType
from typing import Literal

from personal_ai.evidence.contracts import ResearchRecord
from personal_ai.retrieval.contracts import RetrievalOutcome

TOOL_ID = "retrieval.query.v1"
MAX_TOOL_BYTES = 32768


class ToolOutcome(ResearchRecord):
    schema_version: Literal["read-only-tool-v1"] = "read-only-tool-v1"
    retrieval: RetrievalOutcome


async def _retrieval(service, query, guard):
    value = ToolOutcome(retrieval=await service.query(query, tool=True, tool_guard=guard))
    guard()
    if len(value.model_dump_json().encode()) > MAX_TOOL_BYTES:
        raise ValueError("tool_result_oversized")
    return value


# Client data and manifest metadata cannot add executable registrations.
EXECUTABLE_TOOLS = MappingProxyType({TOOL_ID: _retrieval})


def require_tool(registry, application_id, tool_id=TOOL_ID):
    executable = EXECUTABLE_TOOLS.get(tool_id)
    if executable is None:
        raise ValueError("tool_unavailable")
    metadata = registry.capability(application_id, tool_id, kind="tool")
    if (
        not metadata.is_enabled()
        or not metadata.read_only_context
        or metadata.result_fields != ("retrieval",)
        or metadata.max_result_bytes != MAX_TOOL_BYTES
    ):
        raise ValueError("tool_unavailable")
    return executable

"""Operator-owned immutable read-only registrations; no client executable data."""

import asyncio
import re
from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType
from typing import Literal

from personal_ai.evidence.contracts import ResearchRecord
from personal_ai.retrieval.contracts import RetrievalOutcome, RetrievalQuery

TOOL_ID = "retrieval.query.v1"
MAX_TOOL_BYTES = 32768


class ToolOutcome(ResearchRecord):
    schema_version: Literal["read-only-tool-v1"] = "read-only-tool-v1"
    retrieval: RetrievalOutcome


async def _retrieval(service, query, guard):
    return ToolOutcome(retrieval=await service.query(query, tool=True, tool_guard=guard))


@dataclass(frozen=True)
class ReadOnlyToolRegistration:
    tool_id: str
    input_model: type[ResearchRecord]
    output_model: type[ResearchRecord]
    handler: object
    result_fields: tuple[str, ...]
    max_result_bytes: int
    timeout_seconds: float
    effect: Literal["read_only"] = "read_only"

    def __post_init__(self):
        if (
            not re.fullmatch(r"[a-z][a-z0-9_.]{1,70}\.v[1-9][0-9]{0,2}", self.tool_id)
            or self.effect != "read_only"
            or not callable(self.handler)
            or not issubclass(self.input_model, ResearchRecord)
            or not issubclass(self.output_model, ResearchRecord)
            or set(self.result_fields) != set(self.output_model.model_fields) - {"schema_version"}
            or len(self.result_fields) != len(set(self.result_fields))
            or not 1 <= self.max_result_bytes <= MAX_TOOL_BYTES
            or not 0 < self.timeout_seconds <= 10
        ):
            raise ValueError("tool_registration_invalid")


@dataclass(frozen=True, init=False)
class ReadOnlyToolRegistry:
    """Only trusted startup code can supply handlers. Manifests grant no execution."""

    registrations: Mapping[str, ReadOnlyToolRegistration]

    def __init__(self, registrations):
        rows = tuple(registrations)
        if len(rows) > 32 or any(not isinstance(row, ReadOnlyToolRegistration) for row in rows):
            raise ValueError("tool_registration_invalid")
        if len({row.tool_id for row in rows}) != len(rows):
            raise ValueError("tool_registration_duplicate")
        object.__setattr__(self, "registrations", MappingProxyType({row.tool_id: row for row in rows}))

    def require(self, application_registry, application_id, tool_id):
        row = self.registrations.get(tool_id)
        if row is None:
            raise ValueError("tool_unavailable")
        metadata = application_registry.capability(application_id, tool_id, kind="tool")
        if (
            not metadata.is_enabled()
            or not metadata.read_only_context
            or metadata.result_fields != row.result_fields
            or metadata.max_result_bytes != row.max_result_bytes
        ):
            raise ValueError("tool_unavailable")

        async def invoke(service, query, guard):
            # Validate before any handler work, and enforce current metadata at both ends.
            body = row.input_model.model_validate(query)
            guard()
            async with asyncio.timeout(row.timeout_seconds):
                result = await row.handler(service, body, guard)
            result = row.output_model.model_validate(result)
            guard()
            if len(result.model_dump_json().encode()) > row.max_result_bytes:
                raise ValueError("tool_result_oversized")
            return result

        return invoke


DEFAULT_TOOLS = ReadOnlyToolRegistry(
    (
        ReadOnlyToolRegistration(
            TOOL_ID,
            RetrievalQuery,
            ToolOutcome,
            _retrieval,
            ("retrieval",),
            MAX_TOOL_BYTES,
            10,
        ),
    )
)


def require_tool(registry, application_id, tool_id=TOOL_ID, *, tools=None):
    tools = DEFAULT_TOOLS if tools is None else tools
    if not isinstance(tools, ReadOnlyToolRegistry):
        raise TypeError("tool_unavailable")
    return tools.require(registry, application_id, tool_id)

"""Explicit host registration only. Never installed in a provider execution loop."""

import json
from threading import RLock
from time import monotonic
from uuid import uuid4

from pydantic import ValidationError

from personal_ai.memory.control_contracts import (
    FetchInput,
    OperationResult,
    ProposalInput,
    SearchInput,
)

TOOL_INPUTS = {
    "search_memory": SearchInput,
    "fetch_memory": FetchInput,
    "list_memory_topics": SearchInput,
    "propose_memory": ProposalInput,
}


def tool_definitions():
    return tuple(
        {"name": name, "input_schema": contract.model_json_schema()}
        for name, contract in TOOL_INPUTS.items()
    )


class MemoryToolRun:
    """Trusted host constructs this capability; model JSON cannot register a run.

    Serialized invocations, ten total calls, ten-second lifetime, no caller keys.
    Host retains result/operation ID across delivery retries; a repeated model
    invocation is a distinct proposal, bounded by the queue/run quotas.
    """

    def __init__(self, service):
        if not service.enabled("agent_tools"):
            raise ValueError("memory_tools_disabled")
        self.service, self.deadline = service, monotonic() + 10
        self.calls, self.cancelled, self._lock = 0, False, RLock()

    def cancel(self):
        with self._lock:
            self.cancelled = True

    def invoke(self, name, arguments):
        with self._lock:
            if self.cancelled:
                return OperationResult(status="cancelled", reason="run_cancelled")
            if self.calls >= 10 or monotonic() >= self.deadline:
                return OperationResult(status="limit_exceeded", reason="run_budget")
            self.calls += 1
            if not self.service.enabled("agent_tools"):
                return OperationResult(status="disabled", reason="feature_disabled")
            try:
                if (
                    len(
                        (
                            arguments if isinstance(arguments, str) else json.dumps(arguments)
                        ).encode()
                    )
                    > 4096
                ):
                    raise ValueError("tool_input_budget")
                model = TOOL_INPUTS[name]
                parsed = (
                    model.model_validate_json(arguments)
                    if isinstance(arguments, str)
                    else model.model_validate(arguments)
                )
            except (KeyError, ValidationError, TypeError, ValueError, RecursionError):
                return OperationResult(status="rejected", reason="invalid_tool_arguments")
            if name == "propose_memory":
                return self.service.propose(parsed, operation_id=uuid4())
            if name == "fetch_memory":
                return self.service.read(
                    SearchInput(), memory_id=parsed.memory_id, channel="agent_tools"
                )
            return self.service.read(
                parsed, topics=name == "list_memory_topics", channel="agent_tools"
            )

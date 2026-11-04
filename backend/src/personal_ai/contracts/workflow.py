"""Versioned internal workflow contract shared by future strategy callers."""

from hashlib import sha256
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from personal_ai.contracts.delegated_tasks import canonical_bytes
from personal_ai.retrieval.contracts import RetrievalQuery

# These profiles share a vocabulary, but the operator seam admits foreground only.
WorkflowProfile = Literal["foreground", "background", "native", "effect"]
StepName = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,39}$")]
RunState = Literal["queued", "running", "succeeded", "failed", "canceled", "uncertain"]
TERMINAL = frozenset({"succeeded", "failed", "canceled", "uncertain"})


class WorkflowRecord(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, hide_input_in_errors=True)


class StepSpec(WorkflowRecord):
    name: StepName
    tool: Literal["retrieval.query.v1"]
    effect: Literal["read_only"] = "read_only"
    dependencies: tuple[StepName, ...] = Field(default=(), max_length=4)
    query: RetrievalQuery
    timeout_ms: int = Field(default=1000, ge=50, le=2000, strict=True)
    result_bytes: int = Field(default=8192, ge=256, le=16384, strict=True)

    @model_validator(mode="after")
    def local_only(self):
        if self.query.sources != ("local",):
            raise ValueError("workflow_local_sources_required")
        if len(set(self.dependencies)) != len(self.dependencies):
            raise ValueError("workflow_duplicate_dependency")
        return self


class RunSpec(WorkflowRecord):
    schema_version: Literal["workflow-v1"] = "workflow-v1"
    purpose: Literal["interactive_retrieval"] = "interactive_retrieval"
    original_key: UUID
    steps: tuple[StepSpec, ...] = Field(min_length=1, max_length=8)
    deadline_ms: int = Field(default=10000, ge=100, le=30000, strict=True)
    result_bytes: int = Field(default=32768, ge=256, le=65536, strict=True)

    @model_validator(mode="after")
    def bounded_graph(self):
        self.ordered_steps()
        if len(self.canonical_body()) > 16384:
            raise ValueError("workflow_spec_oversized")
        if sum(step.result_bytes for step in self.steps) > self.result_bytes:
            raise ValueError("workflow_result_budget_exceeded")
        return self

    def ordered_steps(self) -> tuple[StepSpec, ...]:
        remaining = {step.name: step for step in self.steps}
        if len(remaining) != len(self.steps):
            raise ValueError("workflow_duplicate_step")
        if any(set(step.dependencies) - remaining.keys() for step in self.steps):
            raise ValueError("workflow_missing_dependency")
        ordered = []
        while remaining:
            ready = next(
                (
                    step
                    for step in remaining.values()
                    if not remaining.keys() & set(step.dependencies)
                ),
                None,
            )
            if ready is None:
                raise ValueError("workflow_dependency_cycle")
            ordered.append(remaining.pop(ready.name))
        return tuple(ordered)

    def canonical_body(self) -> bytes:
        return canonical_bytes(self.model_dump(mode="json"))

    def intent_digest(self, scope_digest: str) -> str:
        return sha256(scope_digest.encode("ascii") + self.canonical_body()).hexdigest()


class AttemptOperationBinding(WorkflowRecord):
    """Nonsecret fingerprints that bind an attempt to its validated operation."""

    tool_id: Literal["retrieval.query.v1"]
    effect_class: Literal["read_only"]
    step_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    source_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    intent_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


class AttemptReceipt(WorkflowRecord):
    attempt_id: UUID
    step: StepName
    state: Literal["reserved", "dispatched", "succeeded", "failed", "abandoned", "uncertain"]
    operation_binding: AttemptOperationBinding | None = None


class ProgressEvent(WorkflowRecord):
    sequence: int = Field(ge=1)
    kind: Literal[
        "queued",
        "claimed",
        "requeued",
        "reserved",
        "dispatched",
        "step_succeeded",
        "step_failed",
        "step_abandoned",
        "cancel_requested",
        "succeeded",
        "failed",
        "canceled",
        "uncertain",
    ]
    attempt_id: UUID | None = None


class RunProgress(WorkflowRecord):
    run_id: UUID
    state: RunState
    cancel_requested: bool
    reason: str | None
    cursor: int
    gap: bool
    events: tuple[ProgressEvent, ...]
    attempts: tuple[AttemptReceipt, ...]

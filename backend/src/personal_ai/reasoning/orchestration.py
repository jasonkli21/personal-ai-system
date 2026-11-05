"""Closed, source-free reasoning plans and objective synthetic predicates."""

import json
from hashlib import sha256
from operator import add, mul, sub
from types import MappingProxyType
from typing import Annotated, Literal
from uuid import UUID

from pydantic import ConfigDict, Field, ValidationError, model_validator

from personal_ai.contracts.delegated_tasks import canonical_bytes
from personal_ai.contracts.workflow import StepName

from .policy import EFFORTS, Effort, RequestedEffort
from .proposed_request import Closed

CATALOG = "reasoning-finite-catalog-v1"
POLICY = "reasoning-finite-policy-v1"
Strategy = Literal["direct", "decompose", "critique_refine", "tool_verify"]
Role = Literal["answer", "subanswer", "synthesis", "check", "revision", "recheck"]
Verifier = Literal["arithmetic.v1", "typed_constraints.v1"]
Digest = Annotated[str, Field(pattern=r"^[0-9a-f]{64}$")]
Value = Annotated[int, Field(ge=-1_000_000, le=1_000_000)]
INPUT_BYTES = 1024
OUTPUT_BYTES = 128
COUNTS = 8
STEP_MS = 2000


class ReasoningRecord(Closed):
    model_config = ConfigDict(hide_input_in_errors=True)


def digest(value):
    return sha256(canonical_bytes(value)).hexdigest()


class Requirement(ReasoningRecord):
    operation: Literal["add", "subtract", "multiply"]
    left: Annotated[int, Field(ge=-1000, le=1000)]
    right: Annotated[int, Field(ge=-1000, le=1000)]


class Task(ReasoningRecord):
    kind: Literal["simple", "independent", "correctable", "arithmetic", "unknown"]
    requirements: tuple[Requirement, ...] = Field(max_length=3)
    sensitivity: Literal["public_synthetic"] = "public_synthetic"
    ambiguity: Literal["resolved", "missing", "conflicting"] = "resolved"

    @model_validator(mode="after")
    def validate_slots(self):
        if len(set(self.requirements)) != len(self.requirements):
            raise ValueError("duplicate_requirement")
        if self.kind == "independent" and len(self.requirements) < 2:
            raise ValueError("independent_requirements_missing")
        return self


class Limits(ReasoningRecord):
    model_calls: int = Field(default=0, ge=0, le=4)
    verifier_calls: int = Field(default=0, ge=0, le=2)
    count_calls: int = Field(default=0, ge=0, le=64)
    count_input_bytes: int = Field(default=0, ge=0, le=65536)
    input_bytes: int = Field(default=0, ge=0, le=4096)
    output_bytes: int = Field(default=0, ge=0, le=512)
    result_bytes: int = Field(default=0, ge=0, le=512)
    deadline_ms: int = Field(default=0, ge=0, le=30000)
    concurrency: int = Field(default=0, ge=0, le=1)
    external_sources: int = Field(default=0, ge=0, le=0)
    provider_cost_usd: Literal["0.00"] = "0.00"


HARD_LIMIT = Limits(
    model_calls=4, verifier_calls=2, count_calls=64, count_input_bytes=65536,
    input_bytes=4096, output_bytes=512, result_bytes=512, deadline_ms=30000, concurrency=1,
)


class ScopeCeilings(ReasoningRecord):
    operator: Limits = HARD_LIMIT
    application: Limits = Limits()
    workspace: Limits = Limits()
    user: Limits = Limits()
    endpoint: Limits = HARD_LIMIT
    operator_effort: Effort = "low"
    application_effort: Effort = "low"
    workspace_effort: Effort = "low"
    user_effort: Effort = "low"
    endpoint_effort: Effort = "low"
    allow_direct_pin: bool = False


class Request(ReasoningRecord):
    schema_version: Literal["reasoning-run-request-v1"]
    original_key: UUID
    task: Task
    effort: RequestedEffort = "auto"
    strategy: Literal["auto", "direct"] = "auto"
    limits: Limits = Limits()


class Step(ReasoningRecord):
    name: StepName
    tool: Literal["reasoning.inference.v1", "reasoning.verify.v1"]
    role: Role
    effect: Literal["read_only"] = "read_only"
    dependencies: tuple[StepName, ...] = Field(default=(), max_length=3)
    slot: int | None = Field(default=None, ge=0, le=2)
    verifier: Verifier | None = None
    timeout_ms: int = Field(default=STEP_MS, ge=STEP_MS, le=STEP_MS)
    input_bytes: int = Field(default=0, ge=0, le=INPUT_BYTES)
    output_bytes: int = Field(default=0, ge=0, le=OUTPUT_BYTES)
    count_calls: int = Field(default=0, ge=0, le=COUNTS)
    output_schema: Literal["integer-vector-v1"] = "integer-vector-v1"
    result_bytes: int = Field(default=OUTPUT_BYTES, ge=OUTPUT_BYTES, le=OUTPUT_BYTES)


def _inference(name, role, dependencies=(), *, slot=None):
    return Step(
        name=name, tool="reasoning.inference.v1", role=role, dependencies=dependencies, slot=slot,
        input_bytes=INPUT_BYTES, output_bytes=OUTPUT_BYTES, count_calls=COUNTS,
    )


def _check(name, role, target, verifier):
    return Step(
        name=name, tool="reasoning.verify.v1", role=role, dependencies=(target,), verifier=verifier,
    )


# Versioned executable templates. The historical proposal-only tool_verify entry is independent.
STRATEGY_VERSIONS = MappingProxyType({
    "direct": "direct-verified.v1",
    "decompose": "decompose-typed.v1",
    "critique_refine": "critique-refine-objective.v1",
    "tool_verify": "tool-verify-pure.v1",
})


def template(task: Task, strategy: Strategy, *, repair=False):
    verifier = "arithmetic.v1" if strategy == "tool_verify" else "typed_constraints.v1"
    if strategy == "decompose":
        slots = tuple(
            _inference(f"slot_{index}", "subanswer", slot=index)
            for index in range(len(task.requirements))
        )
        return (*slots, _inference("synthesis", "synthesis", tuple(s.name for s in slots)),
                _check("check", "check", "synthesis", verifier))
    initial = (_inference("answer", "answer"), _check("check", "check", "answer", verifier))
    if repair:
        return (*initial, _inference("revision", "revision", ("check",)),
                _check("recheck", "recheck", "revision", verifier))
    return initial


def fits(limits: Limits, steps: tuple[Step, ...], *, prior_counts=0, prior_count_bytes=0):
    models = sum(step.tool == "reasoning.inference.v1" for step in steps)
    return (
        limits.concurrency == 1
        and limits.deadline_ms >= sum(step.timeout_ms for step in steps)
        and limits.model_calls >= models
        and limits.verifier_calls >= len(steps) - models
        and limits.input_bytes >= sum(step.input_bytes for step in steps)
        and limits.output_bytes >= sum(step.output_bytes for step in steps)
        and limits.result_bytes >= models * OUTPUT_BYTES
        and limits.count_calls >= prior_counts + sum(step.count_calls for step in steps)
        and limits.count_input_bytes >= prior_count_bytes + sum(step.count_calls * step.input_bytes for step in steps)
    )


class Plan(ReasoningRecord):
    schema_version: Literal["reasoning-run-v1"] = "reasoning-run-v1"
    purpose: Literal["synthetic_reasoning"] = "synthetic_reasoning"
    policy: Literal["reasoning-finite-policy-v1"] = POLICY
    catalog: Literal["reasoning-finite-catalog-v1"] = CATALOG
    scope_digest: Digest
    endpoint_digest: Digest
    fixture_digest: Digest
    request_digest: Digest
    original_key: UUID
    strategy: Strategy
    strategy_version: Literal[
        "direct-verified.v1", "decompose-typed.v1", "critique-refine-objective.v1",
        "tool-verify-pure.v1",
    ]
    selection: Literal["simple", "typed_slots", "objective_defect", "pure_verifier",
                       "effort_ceiling", "budget_narrowed", "trusted_direct_pin"]
    requested_effort: RequestedEffort
    effort: Effort
    task: Task
    limits: Limits
    steps: tuple[Step, ...] = Field(min_length=2, max_length=8)

    @model_validator(mode="after")
    def validate_template(self):
        repair = len(self.steps) == 4 and self.strategy in {"critique_refine", "tool_verify"}
        if (
            self.strategy_version != STRATEGY_VERSIONS[self.strategy]
            or self.steps != template(self.task, self.strategy, repair=repair)
            or self.task.ambiguity != "resolved"
            or not self.task.requirements
            or self.task.kind == "unknown"
            or self.strategy != "direct" and self.strategy != _CHOICES.get(self.task.kind, (None,))[0]
            or self.strategy != "direct" and self.effort == "low"
            or not fits(self.limits, self.steps)
        ):
            raise ValueError("reasoning_plan_invalid")
        return self

    def ordered_steps(self):
        return self.steps

    @property
    def deadline_ms(self):
        return self.limits.deadline_ms

    def intent_digest(self, scope_digest):
        if scope_digest != self.scope_digest:
            raise ValueError("reasoning_scope_mismatch")
        return original_intent(scope_digest, self.request_digest)



def original_intent(scope_digest, request_digest):
    return digest({"scope": scope_digest, "request": request_digest})


_CHOICES = MappingProxyType({
    "independent": ("decompose", "typed_slots"),
    "correctable": ("critique_refine", "objective_defect"),
    "arithmetic": ("tool_verify", "pure_verifier"),
})


class Stop(ValueError):
    """Closed policy refusal or execution stop."""


def effective_effort(ceilings, requested):
    return min((
        "medium" if requested == "auto" else requested,
        ceilings.operator_effort, ceilings.application_effort, ceilings.workspace_effort,
        ceilings.user_effort, ceilings.endpoint_effort,
    ), key=EFFORTS.index)


def effective_limits(ceilings, requested):
    caps = (
        requested, HARD_LIMIT, ceilings.operator, ceilings.application,
        ceilings.workspace, ceilings.user, ceilings.endpoint,
    )
    return Limits(**{
        field: min(getattr(cap, field) for cap in caps)
        for field in Limits.model_fields
    })


def compile_plan(request, ceilings, *, scope_digest, endpoint_digest, fixture_digest):
    if request.task.kind == "unknown" or request.task.ambiguity != "resolved" or not request.task.requirements:
        raise Stop("evidence_insufficient")
    if request.strategy != "auto" and not ceilings.allow_direct_pin:
        raise Stop("policy_denied")
    effort = effective_effort(ceilings, request.effort)
    limits = effective_limits(ceilings, request.limits)
    strategy, selection = _CHOICES.get(request.task.kind, ("direct", "simple"))
    if request.strategy == "direct":
        strategy, selection = "direct", "trusted_direct_pin"
    elif strategy != "direct" and effort == "low":
        strategy, selection = "direct", "effort_ceiling"
    steps = template(request.task, strategy)
    if strategy in {"critique_refine", "tool_verify"}:
        expanded = template(request.task, strategy, repair=True)
        if fits(limits, expanded):
            steps = expanded
    if strategy == "decompose" and not fits(limits, steps):
        strategy, selection = "direct", "budget_narrowed"
        steps = template(request.task, strategy)
    if not fits(limits, steps):
        raise Stop("budget_exhausted")
    return Plan(
        original_key=request.original_key, request_digest=digest(request.model_dump(mode="json")),
        task=request.task, scope_digest=scope_digest, endpoint_digest=endpoint_digest,
        fixture_digest=fixture_digest, strategy=strategy, strategy_version=STRATEGY_VERSIONS[strategy],
        selection=selection, requested_effort=request.effort, effort=effort, limits=limits, steps=steps,
    )


class Answer(ReasoningRecord):
    values: tuple[Value, ...] = Field(min_length=1, max_length=3)


class Checkpoint(ReasoningRecord):
    step: StepName
    values: tuple[Value, ...] = Field(default=(), max_length=3)
    verdict: Literal["pass", "fail", "inconclusive"] | None = None
    defects: tuple[Annotated[int, Field(ge=0, le=2)], ...] = Field(default=(), max_length=3)


def _unique_fields(pairs):
    fields = dict(pairs)
    if len(fields) != len(pairs):
        raise ValueError("reasoning_duplicate_output_field")
    return fields


def decode(text: str, slots: int):
    if len(text.encode()) > OUTPUT_BYTES:
        return ()
    try:
        raw = json.loads(text, object_pairs_hook=_unique_fields)
        if isinstance(raw, dict) and type(raw.get("values")) is list:
            raw["values"] = tuple(raw["values"])
        answer = Answer.model_validate(raw)
        if len(answer.values) == slots:
            return answer.values
    except (ValidationError, ValueError):
        pass
    return ()


_ARITHMETIC = MappingProxyType({"add": add, "subtract": sub, "multiply": mul})


def _arithmetic(requirements, values):
    return tuple(
        index for index, (requirement, value) in enumerate(zip(requirements, values, strict=True))
        if _ARITHMETIC[requirement.operation](requirement.left, requirement.right) != value
    )


# Both versions currently share typed integer equality. Neither has a tool or source port.
VERIFIERS = MappingProxyType({"arithmetic.v1": _arithmetic, "typed_constraints.v1": _arithmetic})


def verify(step, task, values):
    if len(values) != len(task.requirements):
        return Checkpoint(step=step.name, verdict="inconclusive")
    defects = VERIFIERS[step.verifier](task.requirements, values)
    return Checkpoint(
        step=step.name, verdict="fail" if defects else "pass", values=values, defects=defects,
    )

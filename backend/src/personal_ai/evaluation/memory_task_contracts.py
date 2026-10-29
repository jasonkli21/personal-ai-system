"""Versioned synthetic benchmark data; none of these records confer runtime rights."""

from datetime import UTC, datetime, timedelta
from functools import cache
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from personal_ai.auth.scope import ApplicationScope
from personal_ai.memory.contracts import MemoryType

Arm = Literal["none", "fixed", "full_eligible_history", "gold_authorized"]
ARMS: tuple[Arm, ...] = ("none", "fixed", "full_eligible_history", "gold_authorized")
Family = Literal["workflow", "project", "correction", "temporal", "authorization", "irrelevant"]
FAMILIES = ("workflow", "project", "correction", "temporal", "authorization", "irrelevant")
Action = Literal[
    "inspect",
    "check_revision",
    "read_current",
    "reuse_workflow",
    "avoid_failed",
    "reconcile",
    "answer",
    "abstain",
    "write",
    "deploy",
    "follow_instruction",
]
Status = Literal["passed", "failed", "unsupported", "truncated", "unverified", "blocked", "timeout"]


class Record(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, allow_inf_nan=False)

    @field_validator("*", mode="before")
    @classmethod
    def explicit_timestamp(cls, value, info):
        if (
            info.field_name in ("observed_at", "effective_at", "expires_at", "clock_utc", "as_of")
            and value is not None
            and not isinstance(value, (str, datetime))
        ):
            raise ValueError("explicit_timestamp_required")
        return value


class Scope(ApplicationScope):
    owner_id: str = Field(min_length=1, max_length=100)
    branch: str = Field(min_length=1, max_length=100)


def utc(value: datetime) -> datetime:
    if value.tzinfo is None or value.utcoffset() != timedelta(0):
        raise ValueError("explicit_utc_required")
    return value.astimezone(UTC)


class Fact(Record):
    subject: str = Field(min_length=1, max_length=80)
    value: str = Field(min_length=1, max_length=200)
    kind: Literal["fact", "workflow", "failure_lesson"] = "fact"


class Receipt(Record):
    receipt_id: str = Field(min_length=1, max_length=100)
    run_id: str = Field(min_length=1, max_length=100)
    issuer: Literal["synthetic-tool"]
    revision: str = Field(min_length=1, max_length=100)
    command: str = Field(min_length=1, max_length=200)
    outcome: Literal["success", "failure", "uncertain", "partial"]
    observed_at: datetime
    _utc = field_validator("observed_at")(utc)


class Source(Record):
    source_id: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_-]{0,79}$")
    scope: Scope
    session_id: str = Field(min_length=1, max_length=80)
    authority: Literal[
        "user_asserted",
        "tool_receipt_verified",
        "canonical_domain_version",
        "model_proposed",
        "historical_derived",
        "untrusted_external",
    ]
    content: str = Field(min_length=1, max_length=8000)
    fact: Fact | None = None
    observed_at: datetime
    effective_at: datetime
    revision: str = Field(min_length=1, max_length=100)
    permission_epoch: int = Field(default=1, ge=1, le=1000, strict=True)
    granted: bool = True
    privacy: Literal["synthetic_public", "sensitive"] = "synthetic_public"
    current: bool = False
    fixed_type: MemoryType | None = None
    support_ids: tuple[str, ...] = Field(default=(), max_length=16)
    receipt: Receipt | None = None
    expires_at: datetime | None = None
    similarity: float = Field(default=0.95, ge=0, le=1)
    _utc = field_validator("observed_at", "effective_at")(utc)

    @field_validator("expires_at")
    @classmethod
    def expiry(cls, value):
        return utc(value) if value is not None else value

    @model_validator(mode="after")
    def source_contract(self):
        if self.fixed_type and (
            self.authority != "user_asserted"
            or self.fact is not None
            or len(self.content) > 1000
            or self.current
            or self.receipt is not None
            or self.support_ids
        ):
            raise ValueError("v1_user_assertion_only")
        if self.authority == "tool_receipt_verified" and self.receipt is None:
            raise ValueError("missing_receipt")
        if self.receipt and (
            self.receipt.revision != self.revision
            or self.receipt.observed_at > self.observed_at
            or self.fact is None
            or self.receipt.command != self.fact.value
        ):
            raise ValueError("receipt_binding_invalid")
        if len(set(self.support_ids)) != len(self.support_ids):
            raise ValueError("duplicate_support")
        return self


class Change(Record):
    stage: Literal["before_query", "before_pack", "before_use"]
    source_id: str
    kind: Literal["revoke", "forget", "supersede", "branch"]


class Task(Record):
    instruction: str = Field(min_length=1, max_length=2000)
    operation: Literal["recall", "workflow", "current", "as_of", "reconcile", "compute"]
    subject: str = Field(min_length=1, max_length=80)
    revision: str = Field(min_length=1, max_length=100)
    as_of: datetime
    use_memory: bool = True
    operands: tuple[int, int] | None = None
    allowed_actions: tuple[Action, ...] = Field(min_length=1, max_length=11)
    _utc = field_validator("as_of")(utc)

    @model_validator(mode="after")
    def task_contract(self):
        if len(set(self.allowed_actions)) != len(self.allowed_actions):
            raise ValueError("duplicate_actions")
        if (self.operation == "compute") != (self.operands is not None):
            raise ValueError("compute_operands_required")
        if self.operands and any(abs(v) > 10000 for v in self.operands):
            raise ValueError("operands_too_large")
        return self


class Rubric(Record):
    required_actions: tuple[Action, ...] = Field(min_length=1, max_length=11)
    prohibited_actions: tuple[Action, ...] = Field(default=(), max_length=11)
    answer: str | None = Field(default=None, max_length=200)
    abstain: bool
    citation_ids: tuple[str, ...] = Field(default=(), max_length=16)

    @model_validator(mode="after")
    def valid_actions(self):
        if set(self.required_actions) & set(self.prohibited_actions):
            raise ValueError("contradictory_rubric")
        if any(
            len(set(v)) != len(v)
            for v in (self.required_actions, self.prohibited_actions, self.citation_ids)
        ):
            raise ValueError("duplicate_rubric_entry")
        if self.abstain and self.answer is not None or not self.abstain and self.answer is None:
            raise ValueError("answer_abstention_invalid")
        return self


class Review(Record):
    reviewed: Literal[True]
    reviewer: Literal["implementation-source-rubric-review"]
    rationale: str = Field(min_length=30, max_length=1200)


class Case(Record):
    schema_version: Literal["mem0-task-case-v1"]
    case_id: str = Field(pattern=r"^MEM0-(WF|PR|CO|TF|AU|IR)-0[1-5]$")
    family: Family
    split: Literal["development", "calibration", "frozen_holdout"]
    difficulty: Literal["medium", "hard"]
    privacy_class: Literal["synthetic_public"]
    tags: tuple[str, ...] = Field(min_length=1, max_length=12)
    clock_utc: datetime
    scope: Scope
    sources: tuple[Source, ...] = Field(max_length=160)
    changes: tuple[Change, ...] = Field(default=(), max_length=16)
    task: Task
    expected: Rubric
    gold_evidence_ids: tuple[str, ...] = Field(max_length=16)
    maximum_context_tokens: int = Field(ge=256, le=4096, strict=True)
    history_tokens: int = Field(ge=64, le=2048, strict=True)
    review: Review
    _utc = field_validator("clock_utc")(utc)

    @model_validator(mode="after")
    def references(self):
        sources = {s.source_id: s for s in self.sources}
        if len(sources) != len(self.sources):
            raise ValueError("duplicate_source_id")
        if self.history_tokens > self.maximum_context_tokens - 64:
            raise ValueError("invalid_history_budget")
        if self.task.as_of > self.clock_utc:
            raise ValueError("future_target_task")
        prefix = dict(zip(FAMILIES, ("WF", "PR", "CO", "TF", "AU", "IR"), strict=True))
        if self.case_id.split("-")[1] != prefix[self.family]:
            raise ValueError("family_id_mismatch")
        if not set(self.expected.required_actions) <= set(self.task.allowed_actions):
            raise ValueError("impossible_rubric_action")
        refs = (
            *self.gold_evidence_ids,
            *self.expected.citation_ids,
            *(c.source_id for c in self.changes),
        )
        if set(refs) - sources.keys() or len(set(self.gold_evidence_ids)) != len(
            self.gold_evidence_ids
        ):
            raise ValueError("source_reference_invalid")
        if any(sources[c.source_id].current for c in self.changes):
            raise ValueError("current_context_is_immutable_snapshot")
        for source in self.sources:
            if set(source.support_ids) - sources.keys() or source.source_id in source.support_ids:
                raise ValueError("support_reference_invalid")
            if source.current and (
                source.scope != self.scope
                or not source.granted
                or source.privacy != "synthetic_public"
                or source.observed_at > self.clock_utc
                or source.effective_at > self.clock_utc
                or source.effective_at > self.task.as_of
                or source.authority != "canonical_domain_version"
                or source.support_ids
                or source.expires_at is not None
                and source.expires_at <= self.clock_utc
            ):
                raise ValueError("invalid_current_context")
        visited = set()

        def visit(key, stack):
            if key in stack:
                raise ValueError("cyclic_support")
            if len(stack) > 16:
                raise ValueError("support_depth_limit")
            if key in visited:
                return
            for support in sources[key].support_ids:
                visit(support, stack | {key})
            visited.add(key)

        for key in sources:
            visit(key, set())
        for key in self.gold_evidence_ids:

            @cache
            def gold_valid(item):
                return (
                    item.scope == self.scope
                    and item.granted
                    and not item.current
                    and item.privacy == "synthetic_public"
                    and item.observed_at <= self.clock_utc
                    and item.effective_at <= self.task.as_of
                    and (item.expires_at is None or item.expires_at > self.clock_utc)
                    and all(gold_valid(sources[k]) for k in item.support_ids)
                )

            if not gold_valid(sources[key]):
                raise ValueError("gold_not_initially_authorized")
        return self


class Corpus(Record):
    benchmark_version: Literal["mem0-v1"]
    rubric_version: Literal["mem0-rubric-v1"]
    cases: tuple[Case, ...] = Field(min_length=30, max_length=100)

    @model_validator(mode="after")
    def coverage(self):
        if len({c.case_id for c in self.cases}) != len(self.cases):
            raise ValueError("duplicate_case_id")
        for family in FAMILIES:
            cases = [c for c in self.cases if c.family == family]
            if len(cases) < 5 or sorted(c.split for c in cases) != sorted(
                ["development"] * 3 + ["calibration", "frozen_holdout"]
            ):
                raise ValueError("family_split_coverage_invalid")
        return self


class ActionTrace(Record):
    action: Action
    arguments: dict[str, str] = Field(default_factory=dict, max_length=4)
    evidence_ids: tuple[str, ...] = Field(default=(), max_length=160)
    revision: str
    receipt_id: str | None = None
    verification: Literal["verified", "failed", "unknown", "not_applicable"]
    answer: str | None = Field(default=None, max_length=200)

    @field_validator("arguments")
    @classmethod
    def bounded_arguments(cls, value):
        if any(len(k) > 80 or len(v) > 200 for k, v in value.items()):
            raise ValueError("action_arguments_too_large")
        return value

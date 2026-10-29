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
    effect_key: str | None = Field(default=None, min_length=1, max_length=100)
    issuer: Literal["synthetic-tool"]
    revision: str = Field(min_length=1, max_length=100)
    command: str = Field(min_length=1, max_length=200)
    outcome: Literal["success", "failure", "uncertain", "partial"]
    observed_at: datetime
    _utc = field_validator("observed_at")(utc)


class EffectObservation(Record):
    """Evaluation-only canonical observation bound to one original effect."""

    scope: Scope
    effect_key: str = Field(min_length=1, max_length=100)
    run_id: str = Field(min_length=1, max_length=100)
    command: str = Field(min_length=1, max_length=200)
    original_revision: str = Field(min_length=1, max_length=100)
    outcome: Literal["success", "failure", "uncertain", "partial"]
    observation_id: str = Field(min_length=1, max_length=100)
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
    support_recipe: Literal["exact_all_v1", "eligibility_only_unverified"] | None = None
    receipt: Receipt | None = None
    observation: EffectObservation | None = None
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
            self.authority != "tool_receipt_verified"
            or self.receipt.revision != self.revision
            or self.receipt.observed_at > self.observed_at
            or self.fact is None
            or self.receipt.command != self.fact.value
        ):
            raise ValueError("receipt_binding_invalid")
        if self.observation and (
            self.authority != "canonical_domain_version"
            or not self.current
            or self.observation.scope != self.scope
            or self.observation.observed_at > self.observed_at
        ):
            raise ValueError("effect_observation_binding_invalid")
        if self.authority == "historical_derived":
            if not self.support_ids:
                raise ValueError("derived_support_required")
            if self.support_recipe is None:
                object.__setattr__(self, "support_recipe", "eligibility_only_unverified")
        elif self.support_recipe is not None:
            raise ValueError("support_recipe_only_for_derived")
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
    effect_key: str | None = Field(default=None, min_length=1, max_length=100)
    effect_run_id: str | None = Field(default=None, min_length=1, max_length=100)
    effect_command: str | None = Field(default=None, min_length=1, max_length=200)
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
        identity = (self.effect_key, self.effect_run_id, self.effect_command)
        if self.operation != "reconcile" and any(value is not None for value in identity):
            raise ValueError("effect_identity_only_for_reconcile")
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
    schema_version: Literal["mem0-task-case-v1", "mem0-task-case-v2"]
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
            if source.authority == "historical_derived" and source.support_recipe == "exact_all_v1":
                if source.fact is None:
                    raise ValueError("derived_fact_required")
                support_claims = [diagnostic_claim(sources[key]) for key in source.support_ids]
                if any(claim is None for claim in support_claims) or any(
                    claim != (source.fact.subject, source.fact.value) for claim in support_claims
                ):
                    raise ValueError("derived_exact_support_mismatch")
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
        if self.schema_version == "mem0-task-case-v2" and self.task.operation == "reconcile" and any(
            value is None
            for value in (
                self.task.effect_key,
                self.task.effect_run_id,
                self.task.effect_command,
            )
        ):
            raise ValueError("reconcile_effect_identity_required")
        if self.task.operation == "reconcile" and self.task.effect_key is not None:
            matching_receipts = [
                source.receipt
                for source in self.sources
                if source.receipt
                and source.authority == "tool_receipt_verified"
                and source.scope == self.scope
                and not source.current
                and source.receipt.effect_key == self.task.effect_key
                and source.receipt.run_id == self.task.effect_run_id
                and source.receipt.command == self.task.effect_command
                and source.receipt.revision == self.task.revision
            ]
            if len(matching_receipts) != 1:
                raise ValueError("reconcile_original_receipt_identity_invalid")
        return self


class Corpus(Record):
    benchmark_version: Literal["mem0-v1", "mem0-v2"]
    rubric_version: Literal["mem0-rubric-v1", "mem0-rubric-v2"]
    cases: tuple[Case, ...] = Field(min_length=30, max_length=100)

    @model_validator(mode="after")
    def coverage(self):
        expected_case_version = "mem0-task-case-v1" if self.benchmark_version == "mem0-v1" else "mem0-task-case-v2"
        expected_rubric_version = "mem0-rubric-v1" if self.benchmark_version == "mem0-v1" else "mem0-rubric-v2"
        if self.rubric_version != expected_rubric_version or any(
            case.schema_version != expected_case_version for case in self.cases
        ):
            raise ValueError("corpus_version_mismatch")
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
    result: dict[str, str] = Field(default_factory=dict, max_length=5)
    scope: Scope | None = None

    @field_validator("arguments")
    @classmethod
    def bounded_arguments(cls, value):
        if any(len(k) > 80 or len(v) > 200 for k, v in value.items()):
            raise ValueError("action_arguments_too_large")
        return value

    @field_validator("result")
    @classmethod
    def bounded_result(cls, value):
        if any(len(key) > 80 or len(item) > 200 for key, item in value.items()):
            raise ValueError("action_result_too_large")
        return value

    @model_validator(mode="after")
    def action_payload_contract(self):
        empty = not self.arguments and not self.evidence_ids and self.receipt_id is None
        if self.action == "inspect":
            valid = empty and self.answer is None and not self.result and self.verification == "not_applicable" and self.scope is None
        elif self.action == "read_current":
            valid = (
                not self.arguments and len(self.evidence_ids) in (0, 1) and self.answer is None
                and self.receipt_id is None and set(self.result) == {"subject", "value"}
                and self.verification == "verified"
                and (self.result.get("value") == "not_found") == (not self.evidence_ids)
                and self.scope is None
            )
        elif self.action == "check_revision":
            valid = (
                set(self.arguments) == {"expected_revision"} and len(self.evidence_ids) in (0, 1)
                and self.answer is None and self.receipt_id is None
                and set(self.result) == {"observed_revision"}
                and self.verification in ("verified", "failed")
                and (self.result.get("observed_revision") == "not_found") == (not self.evidence_ids)
                and self.scope is None
            )
        elif self.action in ("reuse_workflow", "avoid_failed"):
            outcome = "success" if self.action == "reuse_workflow" else "failure"
            valid = (
                set(self.arguments) == {"command"} and len(self.evidence_ids) == 1
                and self.receipt_id is not None and self.answer is None
                and set(self.result) == {"outcome", "run_id"}
                and self.result.get("outcome") == outcome
                and self.verification == ("verified" if outcome == "success" else "failed")
                and self.scope is None
            )
        elif self.action == "reconcile":
            valid = (
                set(self.arguments) == {"effect_key", "run_id", "command"}
                and len(self.evidence_ids) in (0, 1) and self.answer is None
                and self.verification in ("verified", "failed", "unknown")
                and set(self.result) == {"effect_key", "run_id", "command", "outcome", "observation_id"}
                and self.result.get("outcome") in ("success", "failure", "uncertain", "partial", "unknown")
                and (self.result.get("outcome") == "unknown") == (not self.evidence_ids)
                and (self.receipt_id is not None) == bool(self.evidence_ids)
                and self.scope is not None
            )
        elif self.action == "answer":
            valid = (
                not self.arguments and self.answer is not None and self.receipt_id is None
                and not self.result and self.verification == "not_applicable"
                and self.scope is None
            )
        elif self.action == "abstain":
            valid = (
                empty and self.answer is None and not self.result and self.verification == "unknown"
                and self.scope is None
            )
        else:
            # Prohibited actions remain representable so the independent grader
            # can report them, but they carry no claims of successful authority.
            valid = self.answer is None and self.receipt_id is None and not self.result and self.scope is None
        if not valid:
            raise ValueError("action_payload_contract_invalid:" + self.action)
        return self


def diagnostic_claim(source: Source) -> tuple[str, str] | None:
    """Return the exact structured claim available to the finite harness."""
    if source.fact is not None:
        return source.fact.subject, source.fact.value
    if source.fixed_type:
        import re

        match = re.fullmatch(r"(?:Correction: I now prefer|I prefer) (.+)\.", source.content)
        if match:
            return "response_format", match[1]
    return None

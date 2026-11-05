"""Closed inputs and observations for the frozen synthetic benchmark."""

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Family = Literal[
    "extraction",
    "planning",
    "citations",
    "debugging",
    "numeric",
    "uncertainty",
    "scope",
    "resources",
]
Arm = Literal["direct", "direct_plus_check"]
Status = Literal[
    "scored",
    "failed",
    "denied",
    "ineligible",
    "unsupported",
    "timed_out",
    "internal_error",
]
Reason = Literal[
    "answered",
    "insufficient",
    "scope_denied",
    "revoked",
    "stale",
    "quota",
    "cancelled",
    "deadline",
    "uncertain_effect",
    "intent_conflict",
    "diagnostic_unavailable",
    "check_disagreed",
    "internal_failure",
]
Scenario = Literal[
    "normal",
    "wrong_app",
    "revoke_at_send",
    "stale_revision",
    "quota",
    "cancel",
    "deadline",
    "lost_ack",
]
Text = Annotated[str, Field(min_length=1, max_length=160)]
Code = Annotated[str, Field(pattern=r"^[a-z][a-z0-9_]{0,31}$")]
SmallInt = Annotated[int, Field(ge=-100, le=100)]
Slots = Annotated[tuple[Code, ...], Field(max_length=4)]
Numbers = Annotated[tuple[SmallInt, ...], Field(max_length=8)]


class Closed(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, frozen=True, revalidate_instances="always"
    )


class Record(Closed):
    key: Code
    value: Text
    tags: Slots = ()


class Task(Closed):
    family: Family
    operation: Code
    records: Annotated[tuple[Record, ...], Field(max_length=4)] = ()
    constraints: Slots = ()
    numbers: Numbers = ()


class Answer(Closed):
    value: Annotated[str, Field(min_length=1, max_length=160)] | None = None
    citations: Slots = ()


class Oracle(Closed):
    status: Status
    reason: Reason
    calls: Literal[0, 1]
    value: Text | None = None
    citations: Slots | None = None
    replay: Literal["unused", "uncertain_and_conflict"] = "unused"


class Case(Closed):
    id: Code
    split: Literal["development", "holdout"]
    task: Task
    scenario: Scenario = "normal"
    foreign_slots: Slots = ()
    oracle: Oracle


class Corpus(Closed):
    version: Literal["reasoning-offline-v2"]
    cases: Annotated[tuple[Case, ...], Field(min_length=32, max_length=32)]


class Observation(Closed):
    status: Status
    reason: Reason
    answer: Answer | None = None
    claimed_calls: Literal[0, 1] = 0
    replay: Literal["unused", "uncertain_and_conflict"] = "unused"

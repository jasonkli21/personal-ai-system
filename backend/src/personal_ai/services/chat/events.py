"""Transport-neutral events emitted by chat-turn orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias
from uuid import UUID

from personal_ai.entities import Message
from personal_ai.reasoning.policy import Observation


@dataclass(frozen=True, slots=True)
class TurnMessageCreated:
    message: Message


@dataclass(frozen=True, slots=True)
class TurnDelta:
    message_id: UUID
    delta: str


@dataclass(frozen=True, slots=True)
class TurnCompleted:
    message: Message
    reasoning: Observation | None = None


@dataclass(frozen=True, slots=True)
class TurnFailed:
    message_id: UUID
    code: str
    message: str
    reasoning: Observation | None = None


TurnEvent: TypeAlias = TurnMessageCreated | TurnDelta | TurnCompleted | TurnFailed

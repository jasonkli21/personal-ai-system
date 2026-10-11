"""Transport-neutral events emitted by chat-turn orchestration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TypeAlias
from uuid import UUID

from personal_ai.entities import Message


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


@dataclass(frozen=True, slots=True)
class TurnFailed:
    message_id: UUID
    code: str
    message: str


TurnEvent: TypeAlias = TurnMessageCreated | TurnDelta | TurnCompleted | TurnFailed

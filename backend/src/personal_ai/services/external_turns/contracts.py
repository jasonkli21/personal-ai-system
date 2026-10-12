"""Stable external-turn contracts and bounded context-package records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from personal_ai.applications.contracts import (
    ApplicationContextRequest,
)
from personal_ai.contracts.context_references import (
    ContextSourceSnapshot,
)
from personal_ai.contracts.execution import (
    ExecutionChoice,
)
from personal_ai.entities.turn_execution import TurnReservation
from personal_ai.llm.external import PreparedExecution, PreparedMessage


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


@dataclass(frozen=True)
class PreparedExternalTurn:
    message_id: UUID
    reservation: TurnReservation
    messages: tuple[PreparedMessage, ...]
    connected_package: PreparedExecution | None
    context_package: ContextPackage | None = None
    count_kind: Literal["estimated"] = "estimated"

    @property
    def portable_prompt(self) -> str:
        return "\n\n".join(f"{m.role}:\n{m.content}" for m in self.messages)


class ContextPackageSourceSummary(BaseModel):
    """User-visible category summary; source IDs and raw provider metadata stay private."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    category: str = Field(min_length=1, max_length=168)
    item_count: int = Field(ge=0, le=1000)
    sensitivity: tuple[str, ...] = Field(default=(), max_length=5)
    authority: tuple[str, ...] = Field(default=(), max_length=6)


class ContextPackageExclusionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    category: str = Field(min_length=1, max_length=168)
    reason: str = Field(min_length=1, max_length=64)
    item_count: int = Field(ge=1, le=1000)


class ContextPackage(BaseModel):
    """Transient exact prepared content plus a redacted, bounded inspection view."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    schema_version: Literal["context-package-v2"] = "context-package-v2"
    messages: tuple[PreparedMessage, ...] = Field(min_length=1, max_length=256)
    included_sources: tuple[ContextPackageSourceSummary, ...] = Field(default=(), max_length=32)
    excluded_sources: tuple[ContextPackageExclusionSummary, ...] = Field(default=(), max_length=128)
    selected_message_count: int = Field(ge=0, le=20000)
    summarized_source_message_count: int = Field(default=0, ge=0, le=20000)
    input_tokens: int = Field(ge=0)
    counter_kind: Literal["estimated"] = "estimated"
    effective_sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    maximum_sensitivity: Literal["public", "personal", "sensitive", "restricted"]
    policy_version: str = Field(min_length=1, max_length=200)
    expires_at: datetime
    fingerprint: str = Field(pattern=r"^[a-f0-9]{64}$")


class ExternalTurnAuthority(Protocol):
    """Registered policy integration; must check principal membership and all dependencies.

    Snapshot is content-derived from current source/grant revisions, never client labels.
    No permissive production default exists. The integration must retain/recheck every
    selected dependency, including history/summary derivations (P15 acceptance gate).
    """

    def snapshot(
        self,
        context: ApplicationContextRequest,
        conversation_id: UUID,
        choice: ExecutionChoice,
        source_message_ids: tuple[UUID, ...],
        source_snapshots: tuple[ContextSourceSnapshot, ...],
    ) -> str: ...

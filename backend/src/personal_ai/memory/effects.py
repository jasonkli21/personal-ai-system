"""Neutral contracts for guarding cross-store memory effects."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from personal_ai.auth.scope import ApplicationScope
from personal_ai.memory.contracts import DerivedMemory, Memory


@dataclass(frozen=True)
class EffectGuardToken:
    owner_id: str
    operation_id: str
    attempt_id: str
    fingerprint: str
    execution_deadline: datetime
    scope: ApplicationScope
    coordination_conversation_id: UUID | None = None
    coordination_job_id: UUID | None = None
    lease_generation: int | None = None


class MemorySourceGuard(Protocol):
    """Storage guard used to fence durable memory effects across stores."""

    def acquire(self, record: Memory | DerivedMemory, *, timeout: float) -> EffectGuardToken: ...

    def acquire_lifecycle_event(
        self,
        record: Memory | DerivedMemory,
        *,
        operation_id: str,
        fingerprint: str,
        completed_assistant_id: UUID | None,
        completed_assistant_conversation_id: UUID | None,
        timeout: float,
    ) -> EffectGuardToken: ...

    def acknowledge(
        self,
        token: EffectGuardToken,
        *,
        outcome: str,
        result_refs: dict[str, Any],
    ) -> None: ...

    def acquire_job(
        self,
        job: Any,
        lease_token: UUID,
        record: Memory | DerivedMemory,
        *,
        operation_id: str,
        timeout: float,
    ) -> EffectGuardToken: ...

    def recover_pending_job(
        self, *, owner_id: str, job_id: UUID, scope: ApplicationScope, receipts
    ) -> int: ...

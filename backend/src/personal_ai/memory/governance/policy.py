"""Pure intersection policy. HostState is never decoded from an untrusted request."""

from dataclasses import dataclass
from datetime import datetime

from personal_ai.memory.governance.contracts import (
    DependencyEpochs,
    EffectiveGrantDecision,
    GrantRecord,
    MemoryScope,
    SourceReference,
)
from personal_ai.memory.knowledge import digest


@dataclass(frozen=True)
class HostState:
    """Server adapter observation under its lease, not proof supplied by a client.

    Source adapters must derive this from canonical knowledge/lifecycle and current
    project/owner/target policy. Only the E1 adapter exists in this repository.
    """

    source: SourceReference
    destination: MemoryScope
    owner_epoch: int
    source_epoch: int
    target_epoch: int
    source_expires_at: datetime
    source_allowed: bool
    target_allowed: bool
    owner_active: bool
    reconciled: bool
    classification: str = "public"
    verification: str = "verified"
    origin: str = "canonical_knowledge"


def effective(record: GrantRecord, state: HostState, now: datetime):
    epochs = DependencyEpochs(
        owner=state.owner_epoch,
        source=state.source_epoch,
        target=state.target_epoch,
        generation=record.epochs.generation,
    )
    allowed = (
        not record.revoked
        and state.reconciled
        and state.owner_active
        and state.source_allowed
        and state.target_allowed
        and state.classification == "public"
        and state.verification == "verified"
        and state.origin == "canonical_knowledge"
        and record.intent.source == state.source
        and record.intent.destination == state.destination
        and state.source.scope.owner == state.destination.owner
        and record.epochs == epochs
        and record.issued_at <= now < min(record.intent.expires_at, state.source_expires_at)
    )
    return EffectiveGrantDecision(
        allowed=allowed,
        reason="ok" if allowed else "policy_denied",
        epochs=epochs if allowed else None,
        grant_fingerprint=digest(record) if allowed else None,
    )

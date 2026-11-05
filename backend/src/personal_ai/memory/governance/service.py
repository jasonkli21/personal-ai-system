"""Unregistered host-fenced overlay seam; never reads content or dispatches a send."""

from contextlib import AbstractContextManager
from dataclasses import dataclass
from datetime import timedelta
from typing import Protocol

from personal_ai.auth.scope import RequestScope
from personal_ai.memory.governance.contracts import (
    DependencyEpochs,
    EffectiveGrantDecision,
    GrantReceipt,
    GrantRecord,
    MemoryScope,
    QuotaSnapshot,
    ResourceLimits,
    ShareIntent,
)
from personal_ai.memory.governance.policy import HostState, effective
from personal_ai.memory.knowledge import digest


@dataclass(frozen=True)
class Ledger:
    revision: int = 0
    grants: tuple[GrantRecord, ...] = ()
    receipts: tuple[GrantReceipt, ...] = ()


class GrantRepository(Protocol):
    """Adapter owns atomic original-key/CAS and owner-deletion exclusion.

    All calls occur inside transaction; save must commit before a reply. A native
    implementation must use canonical owner locks and retained recovery fences.
    No native implementation or persistence guarantee is provided here.
    """

    def transaction(self, owner: str) -> AbstractContextManager[None]: ...
    def load(self, owner: str) -> Ledger: ...
    def save(self, owner: str, ledger: Ledger) -> None: ...


class GrantAuthority(Protocol):
    """Host-only dependency; no wire model, fallback or installed implementation."""

    def guard(self) -> AbstractContextManager[None]: ...
    def manages(self, request: RequestScope, intent: ShareIntent) -> bool: ...
    def reader(self, request: RequestScope, destination: MemoryScope) -> bool: ...
    def resolve(self, source, destination) -> HostState: ...
    def recovery_current(self, owner: str) -> bool: ...


class GovernanceService:
    def __init__(
        self,
        repository: GrantRepository,
        authority: GrantAuthority | None = None,
        *,
        clock,
        limits: ResourceLimits | None = None,
    ):
        self.repository, self.authority, self.clock = repository, authority, clock
        self.limits = limits or ResourceLimits()

    def mutate(self, request: RequestScope, intent: ShareIntent) -> GrantReceipt:
        # Revalidate even Python model instances: model_copy/construct are not proof.
        intent = ShareIntent.model_validate(intent.model_dump(mode="python"))
        fingerprint = intent.fingerprint(request.acting_user_id or "")

        def reply(outcome, revision=0, reason="policy_denied"):
            return GrantReceipt(
                operation_id=intent.operation_id,
                fingerprint=fingerprint,
                outcome=outcome,
                revision=revision,
                grant_id=intent.grant_id,
                reason=reason,
            )

        if self.authority is None:
            return reply("unavailable", reason="storage_unavailable")
        try:
            with self.authority.guard(), self.repository.transaction(request.owner_id):
                # Original-key reconciliation still requires the original owner/actor.
                if not self.authority.manages(request, intent):
                    return reply("denied")
                ledger = self.repository.load(request.owner_id)
                if not self.authority.recovery_current(request.owner_id):
                    return reply("unavailable", reason="storage_unavailable")
                for receipt in ledger.receipts:
                    if receipt.operation_id == intent.operation_id:
                        if receipt.fingerprint != fingerprint:
                            return reply("conflict", ledger.revision, "conflict")
                        return receipt.model_copy(update={"outcome": "replayed"})
                if intent.expected_revision != ledger.revision:
                    return reply("conflict", ledger.revision, "conflict")
                current = next(
                    (g for g in ledger.grants if g.intent.grant_id == intent.grant_id), None
                )
                revision = ledger.revision + 1
                if intent.operation == "revoke":
                    # Source loss/expiry/target removal must never prevent revocation.
                    if (
                        current is None
                        or current.revoked
                        or current.actor != request.acting_user_id
                        or current.intent.source != intent.source
                        or current.intent.destination != intent.destination
                        or current.intent.purpose != intent.purpose
                        or current.intent.expires_at != intent.expires_at
                    ):
                        return reply("conflict", ledger.revision, "conflict")
                    updated = current.model_copy(update={"revoked": True, "revision": revision})
                    grants = tuple(updated if g == current else g for g in ledger.grants)
                else:
                    if current is not None:
                        return reply("conflict", ledger.revision, "conflict")
                    # Grant IDs and original keys remain retained, even after revoke.
                    if len(ledger.grants) >= min(self.limits.grants, self.limits.source_fences):
                        return reply("denied", ledger.revision, "capacity")
                    state = self.authority.resolve(intent.source, intent.destination)
                    now = self.clock()
                    if not now < intent.expires_at <= now + timedelta(days=30):
                        return reply("denied", ledger.revision)
                    slot = lambda g: (
                        g.intent.source.scope,
                        g.intent.source.record,
                        g.intent.destination,
                        g.intent.purpose,
                    )
                    key = (
                        intent.source.scope,
                        intent.source.record,
                        intent.destination,
                        intent.purpose,
                    )
                    generation = (
                        max(
                            (g.epochs.generation for g in ledger.grants if slot(g) == key),
                            default=0,
                        )
                        + 1
                    )
                    updated = GrantRecord(
                        intent=intent,
                        actor=request.acting_user_id,
                        revision=revision,
                        epochs=DependencyEpochs(
                            owner=state.owner_epoch,
                            source=state.source_epoch,
                            target=state.target_epoch,
                            generation=generation,
                        ),
                        issued_at=now,
                    )
                    if not effective(updated, state, now).allowed:
                        return reply("denied", ledger.revision)
                    # A replacement permanently suppresses older coverage of this slot.
                    grants = tuple(
                        g.model_copy(update={"revoked": True, "revision": revision})
                        if slot(g) == key and not g.revoked
                        else g
                        for g in ledger.grants
                    ) + (updated,)
                receipt = reply("committed", revision, "ok")
                self.repository.save(
                    request.owner_id,
                    Ledger(
                        revision,
                        grants,
                        (*ledger.receipts, receipt),
                    ),
                )
                return receipt
        except Exception:  # noqa: BLE001 - ACK may be lost after commit; reconcile original key
            return reply("uncertain", reason="storage_unavailable")

    def observe(
        self,
        request: RequestScope,
        grant_id,
        *,
        purpose="assist_response",
        prior: EffectiveGrantDecision | None = None,
        external=False,
    ):
        """Use at selection, packing and final internal observation.

        Returns no memory content or send permit. Prior observations cannot restore
        authority. A host must hold its guard across actual internal content use;
        runtime integration is intentionally absent until independently reviewed.
        """
        denied = lambda reason: EffectiveGrantDecision(allowed=False, reason=reason)
        if external:
            return denied("external_delivery_blocked")
        if self.authority is None:
            return denied("unavailable")
        try:
            with self.authority.guard(), self.repository.transaction(request.owner_id):
                ledger = self.repository.load(request.owner_id)
                if not self.authority.recovery_current(request.owner_id):
                    return denied("unavailable")
                record = next((g for g in ledger.grants if g.intent.grant_id == grant_id), None)
                if (
                    record is None
                    or purpose != record.intent.purpose
                    or not self.authority.reader(request, record.intent.destination)
                ):
                    return denied("policy_denied")
                state = self.authority.resolve(record.intent.source, record.intent.destination)
                decision = effective(record, state, self.clock())
                if prior is not None and (not prior.allowed or prior != decision):
                    return denied("policy_denied")
                return decision
        except Exception:  # noqa: BLE001 - unavailable authority/storage cannot release content
            return denied("unavailable")

    def quota(self, request: RequestScope) -> QuotaSnapshot | None:
        if self.authority is None:
            return None
        try:
            with self.authority.guard(), self.repository.transaction(request.owner_id):
                ledger = self.repository.load(request.owner_id)
                # Quota metadata is private; a reader alone has no management authority.
                if not ledger.grants or not self.authority.manages(
                    request, ledger.grants[0].intent
                ):
                    return None
                return QuotaSnapshot(
                    limits=self.limits,
                    grants=len(ledger.grants),
                    original_keys=len(ledger.receipts),
                    tombstones=sum(g.revoked for g in ledger.grants),
                    source_fences=len(ledger.grants),
                    maintenance_backlog=0,
                    serialized_bytes=len(str(ledger).encode()),
                    reserved_revoke_keys=sum(not g.revoked for g in ledger.grants),
                )
        except Exception:  # noqa: BLE001 - do not expose partial inventory
            return None


def overlay_identity(ledger: Ledger):
    """Content-free digest for E1 replay and no-effect checks, never authorization."""
    return digest(
        {
            "revision": ledger.revision,
            "grants": [digest(g) for g in ledger.grants],
            "receipts": [digest(r) for r in ledger.receipts],
        }
    )

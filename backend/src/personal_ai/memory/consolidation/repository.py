"""Single-process atomic reference adapter. No persistence or runtime consumers."""

from contextlib import contextmanager
from dataclasses import dataclass, replace
from datetime import timedelta
from time import monotonic

from personal_ai.memory.consolidation.contracts import (
    BACKFILL_GENERATION,
    GENERATION,
    MAX_BYTES,
    MAX_CLAIMS,
    MAX_PROPOSALS,
    MAX_RECEIPTS,
    BatchReceipt,
    ConsolidationDenied,
    DerivedProposal,
    Lease,
    SourcePage,
    checked,
)
from personal_ai.memory.consolidation.policy import extract, proposal_current
from personal_ai.memory.consolidation.sources import FrozenFixtureSource
from personal_ai.memory.knowledge import digest


@dataclass(frozen=True, repr=False)
class _Stream:
    cursor: int = 0
    fence: int = 0
    claims: int = 0
    lease: Lease | None = None
    proposals: tuple[DerivedProposal, ...] = ()
    receipts: tuple[BatchReceipt, ...] = ()


class OfflineProposalRepository:
    """All transitions are staged before one state assignment under issuer lock.

    Exceptions before assignment leave the checkpoint/proposals/receipt unchanged;
    exceptions after assignment must reconcile by the original key. This contract
    intentionally does not serialize snapshots, register jobs or write knowledge.
    """

    def __init__(self, source, *, generation=GENERATION):
        if not isinstance(source, FrozenFixtureSource):
            raise ConsolidationDenied()
        if generation not in {GENERATION, BACKFILL_GENERATION}:
            raise ConsolidationDenied()
        self.generation = generation
        self.source = source
        # Multiple session/worker facades share one disposable simulation store.
        # Constructing a new facade must never rewind its cursor or replay ledger.
        with source.guard():
            if not hasattr(source, "_proposal_generations"):
                source._proposal_generations = {}
            self._states = source._proposal_generations.setdefault(
                generation, {scope.key: _Stream() for scope in source.scopes}
            )

    @contextmanager
    def _transaction(self, scope=None):
        with self.source.guard():
            yield

    def claim(self, scope, worker):
        with self._transaction(scope):
            key = self.source._scope(scope)
            state = self._states[key]
            now = self.source.clock()
            if state.claims >= MAX_CLAIMS or state.lease and state.lease.expires_at > now:
                raise ConsolidationDenied()
            try:
                lease = Lease(
                    scope_key=key,
                    worker=worker,
                    fence=state.fence + 1,
                    cursor=state.cursor,
                    expires_at=now + timedelta(seconds=5),
                    generation=self.generation,
                )
            except (TypeError, ValueError):
                raise ConsolidationDenied() from None
            self._states[key] = replace(
                state, lease=lease, fence=lease.fence, claims=state.claims + 1
            )
            return lease

    def _live(self, state, scope_key):
        return tuple(
            p
            for p in state.proposals
            if p.scope.key == scope_key
            and p.generation == self.generation
            and proposal_current(p, self.source)
        )

    def commit(self, lease, page, *, original_key=None, fault=None):
        """One attempt, one bounded page, zero provider calls; no automatic retry."""
        started = monotonic()
        try:
            # model_copy/construct can bypass Pydantic; every boundary revalidates.
            page = checked(page, SourcePage)
            lease = checked(lease, Lease)
            if fault not in (None, "before_commit", "after_commit"):
                raise ConsolidationDenied()
        except (AttributeError, TypeError, ValueError):
            raise ConsolidationDenied() from None
        key = original_key if original_key is not None else page.original_key
        payload_digest = digest(page)
        with self._transaction(page.scope):
            scope_key = self.source._scope(page.scope)
            state = self._states[scope_key]
            if (
                key != page.original_key
                or lease.scope_key != scope_key
                or page.generation != self.generation
                or lease.generation != self.generation
            ):
                raise ConsolidationDenied()
            prior = next((r for r in state.receipts if r.original_key == key), None)
            if prior:
                if prior.payload_digest != payload_digest:
                    raise ConsolidationDenied()
                # A content-free historical receipt never re-discloses proposals.
                return prior
            if (
                state.lease != lease
                or lease.expires_at <= self.source.clock()
                or state.cursor != lease.cursor
                or page.after != state.cursor
                or self.source.page(page.scope, page.after, generation=self.generation) != page
            ):
                raise ConsolidationDenied()
            if len(state.receipts) >= MAX_RECEIPTS:
                raise ConsolidationDenied()
            proposals = list(self._live(state, scope_key))
            reasons = []
            for record in page.records:
                if monotonic() - started >= 2 or not self.source.authentic(record, page.scope):
                    raise ConsolidationDenied()
                candidate, reason = extract(
                    record, proposals, self.source, generation=self.generation
                )
                reasons.append(reason)
                if candidate:
                    if candidate.kind == "conflict":
                        # Contradictory assertions are withheld, never silently
                        # resolved or resurrected after a conflict expires.
                        proposals = [
                            p
                            for p in proposals
                            if (p.fact.command, p.fact.revision)
                            != (candidate.fact.command, candidate.fact.revision)
                        ]
                    proposals.append(candidate)
            if (
                len(proposals) > MAX_PROPOSALS
                or sum(len(p.model_dump_json().encode()) for p in proposals) > MAX_BYTES
            ):
                raise ConsolidationDenied()
            receipt = BatchReceipt(
                original_key=key,
                payload_digest=payload_digest,
                cursor=page.records[-1].sequence,
                proposal_count=len(proposals),
                reasons=tuple(reasons),
            )
            staged = replace(
                state,
                cursor=receipt.cursor,
                lease=None,
                proposals=tuple(proposals),
                receipts=(*state.receipts, receipt),
            )
            if monotonic() - started >= 2 or lease.expires_at <= self.source.clock():
                raise ConsolidationDenied()
            if fault == "before_commit":
                raise ConsolidationDenied()
            # Eligibility can expire while staging, even under a source-mutation
            # lock. Recheck after constructing the entire transaction payload.
            if any(not proposal_current(p, self.source) for p in proposals):
                raise ConsolidationDenied()
            self._states[scope_key] = staged
        if fault == "after_commit":
            raise ConsolidationDenied()
        return receipt

    def observe(self, scope, original_key):
        """Original-key reconciliation returns counters/hashes only."""
        with self._transaction(scope):
            self.source._scope(scope)
            return next(
                (r for r in self._states[scope.key].receipts if r.original_key == original_key),
                None,
            )

    def pending(self, scope):
        with self._transaction(scope):
            try:
                self.source._scope(scope)
                return self._live(self._states[scope.key], scope.key)
            except ConsolidationDenied:
                return ()

    def validate_cached(self, scope, candidate):
        """Cached or restored objects cannot become fresh source authority."""
        with self._transaction(scope):
            try:
                candidate = checked(candidate, DerivedProposal)
                return candidate.scope == scope and candidate in self.pending(scope)
            except (AttributeError, TypeError, ValueError):
                return False

    def maintain(self):
        """Bounded explicit purge; original keys and deletion fences are retained."""
        with self._transaction():
            for key, state in self._states.items():
                try:
                    live = self._live(state, key)
                except ConsolidationDenied:
                    live = ()
                self._states[key] = replace(state, proposals=live)

    def forget(self, *, owner, project=None):
        with self._transaction():
            self.source.forget(owner=owner, project=project)
            self.maintain()

    def diagnostics(self):
        with self._transaction():
            return {
                "streams": len(self._states),
                "checkpoints": sum(s.cursor for s in self._states.values()),
                "receipts": sum(len(s.receipts) for s in self._states.values()),
                "retained_proposals": sum(len(s.proposals) for s in self._states.values()),
                "provider_calls": 0,
                "provider_tokens": 0,
                "automatic_retries": 0,
            }

    def __repr__(self):
        return f"OfflineProposalRepository({digest(self.diagnostics())})"

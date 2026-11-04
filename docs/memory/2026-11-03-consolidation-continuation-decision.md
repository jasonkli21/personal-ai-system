# MEM-4 continuation: in-session reassessment

Entry: `08dd5f0f1d61b29491e02095501515ce49a0bddf`, 2026-11-03.
No tracked user changes; the same seven untracked user plans are preserved.
This is a second in-session author assessment, not independent acceptance.

The first implementation over-deferred isolated database and review work. Missing
production authority forbids enablement, not local implementation or native
synthetic testing. PostgreSQL binaries and pgvector are installed; an unset DSN
alone is insufficient reason to omit a durable adapter or opt-in tests.

Complete a canonical PostgreSQL adapter using the same proposal/checkpoint
transition as the in-memory adapter. Persist synthetic source authority separately
from derived checkpoints, fence both in one bounded transaction, reuse canonical
owner-deletion locks, and test independent connections/processes, rollback,
lost ACK and stale checkpoint restoration. No runtime factory/worker registration.
The synthetic authority still authenticates only exact frozen fixture membership.
It cannot substitute for a deployed source issuer or survive restoration of both
itself and storage without an external monotonic authority.

Add an additive corpus with multiple eligible applications/actors (including null),
revision/epoch regrant, contradictory user corrections, unrelated commands,
capacity pressure and multi-session scripted consumer tasks. Preserve v1 bytes and
results. Strengthen exact entailment checks, TTL and correction dominance. Provide
an explicit versioned backfill namespace with isolated checkpoints; never recycle
keys or compact away tombstones. Quota-denial is a completed safe policy, not a
claim that pruning would be safe.

Implement read-only MEM-2 governance previews using canonical content/review
contracts and authenticated request context. Procedure mapping can be exercised
against existing controls hermetically; lesson/conflict must stay typed and
unsupported for canonical admission rather than masquerade as project decisions.
No automatic mutation, approval or tool/API registration.

Inspect existing local inference admission and model infrastructure. Implement
bounded evaluation infrastructure where safe; run a real local model only with
an available pinned model/runtime and existing admission constraints. Synthetic
consumer quality, exact support and leakage metrics remain distinct from real
model or independent longitudinal utility. Each remaining blocker must name the
missing prerequisite, work completed independently and concrete unblocking steps.

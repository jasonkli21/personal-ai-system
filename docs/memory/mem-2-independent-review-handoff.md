# MEM-2 independent review handoff

Date: 2026-10-29. Review the single MEM-2 commit whose parent is
`7c8f2671ffc163f803e781b9b34d6c81d466e8fa`. This is implementation QA, not an
independent verdict. Read the [ADR](mem-2-control-adr.md),
[evaluation contract](mem-2-evaluation-contract.md) and
[implementation report](mem-2-implementation-report.md), then current code.

The deliberately narrowed implementation provides read/propose/review/reject/
forget. All revisions return `unsupported_evidence_source`; no atomic evidenced
replacement or lineage is advertised. Production host registration, issuer/lease,
live model dispatch, physical send fencing and inherited production acceptance
remain absent. Keep all new flags off. The UI at `/memory` is separately gated.

Review independently, including plan omissions:

- Challenge same owner/app/workspace/project with A, B and null actors; guessed IDs,
  receipt IDs, changed principal, revoked membership, cross-project and account fence.
- Trace tool schema → service → actor-bound storage. Attempt forged successful
  receipts, confirmed/verified fields, instruction poison and forged tool output.
  Proposals and reviewed rows must never become knowledge/context.
- Inspect the canonical lifecycle event/projection and receipt transaction. Reject
  any agent/user authority bypass through public raw lifecycle writes. Race two
  clients, same-key and distinct-key updates, source revoke and owner erasure.
- Kill before commit and after durable commit/before acknowledgement. Retry the
  exact operation and changed payload. Verify original receipt and versions, never
  an unrelated record observation. Include lease-exit and status-read failures.
- Challenge TTL, queue/replay capacity, expired replay, export and operator purge.
  Confirm permanent MEM-1 tombstones are neither pruned nor compacted. Consider
  account restoration/replay and actor cardinality before any promotion.
- Follow cached retrieval, packing, history/summary dependency reuse and the
  provider handoff. Do not infer physical-send concurrency acceptance from a fake
  provider. Already-sent input is unretractable.
- Inspect the 36 fixtures without trusting expected labels; mutate guards and
  expectations. Six public holdout tags are not a blind independent dataset.
  Reproduce native process race and partial-transaction rollback, SQL counts and
  capped resource behavior. Challenge unavailable/sensitive-content handling.
- Check browser explicit confirmation, review semantics, unknown-commit same-key
  retry and disabled flags. No durable/optimistic success from a network timeout.
- Reproduce the reported commands. Preserve MEM-0/1 fixture digests and old planner
  locks. Active planner rebind changes source identity only; no promotion.

Priority decisions: whether this bounded offline slice is acceptable; what trusted
source and atomic replacement contract is needed for correction; how to close the
physical-send/lease and account deletion gates; and safe receipt/source replay
capacity. Do not authorize MEM-3 production episodic capture from this evidence.
Rollback is flag disablement plus forward schema retention. Do not undo lifecycle
forget or remove anti-replay rows. Existing v1/v2 behavior remains separately gated.

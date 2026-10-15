# Stabilization archive — 2026-10-14

These files preserve the evidence and review snapshots from the stabilization
cycle that preceded the fresh re-review. They are historical records, not the
current implementation status or current acceptance result.

Use the live [verification record](../../VERIFICATION.md),
[fresh review handoff](../../FRESH-REVIEW-HANDOFF.md),
[cross-repository contracts](../../CROSS-REPO-CONTRACTS.md),
[operations](../../OPERATIONS.md), and [blockers](../../BLOCKERS.md) for the
current behavior and remaining gates.

## Contents

- `evidence/` contains generated inventories, command/check summaries, isolated
  contract manifests, and publication/CI snapshots from the earlier cycle.
  These files are historical snapshots. `scripts/inventory.py` and
  `scripts/check_isolated_contracts.py` write fresh, ignored output under the
  active `stabilization/evidence/` directory so reruns cannot replace this
  archive. The inventory stores baseline revisions and SHA-256 source-tree
  digests; the contract report stores each runtime's manifest and Pydantic
  version.
- `reports/` contains the dated per-repository status, quality, review, QA, and
  external-acceptance snapshots.
- The archived root Markdown files contain superseded transition, resume,
  backlog, status, and independent-review material.

No archived evidence was deleted. Raw records stay out of the default docs
router; the live verification file records which current checks ran and where
their temporary logs were written.

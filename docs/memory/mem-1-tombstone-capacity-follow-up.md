# MEM-1 source-fence capacity follow-up

Date: 2026-10-29. Status: **open production-promotion blocker**.

## Current bound and exhaustion case

MEM-1 permits at most 1,024 source-fence rows per owner/application/workspace
namespace. Actor-specific fences introduced by migration 029 share this
namespace-wide quota. A source fence remains after source revocation or
knowledge erasure so the same receipt and epoch cannot resurrect deleted
knowledge. There is no supported compactor or issuer watermark today.

For the common three-edge admission shape, assume every new record has three
previously unseen `(actor, resolver, source)` identities. Then 341 admissions
use 1,023 fence rows. The 342nd would need 1,026 rows and is rejected atomically
by `knowledge_source_budget`; one unused row cannot fit a three-edge record.
Source sharing can slow growth, while more edges can exhaust the quota sooner.
After exhaustion, new unique sources remain unavailable even when their prior
knowledge payloads have been revoked, expired, or physically erased.

The in-memory cap test reduces the limit to two rows: it admits and erases one
source while preserving its replay tombstone, admits a new source into the
remaining row, then confirms that a third unique source is rejected. This is a
fast correctness check, not a long-churn or safe-compaction proof.

## Why compaction is deferred

Deleting old tombstones would reopen an admission path for a stale receipt if
an issuer can still present the original source identity and epoch. Current
resolvers do not provide a durable monotonic non-replay watermark or a
versioned namespace epoch that lets the repository reject every pre-compaction
reference. Migration 029 keeps orphaned pre-migration fences as global legacy
replay denies for the same reason. No tombstones are pruned by this change.

## Required design and acceptance

Before either knowledge flag can be enabled in a production host, a separately
reviewed design must choose and prove one of these mechanisms:

1. A durable issuer watermark that establishes an old source identity can never
   be issued again, with explicit coverage across issuer recovery and restore.
2. A versioned source namespace epoch that rejects all receipts from an older
   epoch after compaction, including delayed requests and restored backups.
3. A separately capacity-managed replay ledger with monitoring and an explicit
   admission-stop policy before it fills.

The design must preserve account deletion, actor boundaries, complete reverse
erasure, unknown-commit reconciliation, and rejection of stale receipts. Native
PostgreSQL stress tests must churn beyond the current 1,024-row limit, verify
old receipts remain denied after compaction or rollover, admit new valid
identities, and measure ledger growth and recovery behavior. A runtime metric
and an operator-visible threshold are required before production use.

Until those criteria pass independent review, the 1,024-row source-fence limit
and permanent tombstones remain a hard production-promotion blocker. Both MEM-1
flags stay false by default; this follow-up does not authorize a new issuer,
public mutation path, or rollout.

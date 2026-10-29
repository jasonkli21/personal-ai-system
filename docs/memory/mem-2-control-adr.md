# MEM-2 control ADR

Date: 2026-10-29. Entry revision: `7c8f2671ffc163f803e781b9b34d6c81d466e8fa`.
Status: implementation decision, pending independent review.

## Preflight gates

| Capability | Implemented | Independently accepted | Production verified |
| --- | --- | --- | --- |
| MEM-0 remediation | yes, offline | fresh closure unclaimed | no |
| MEM-1 schema 3, source fences, final disclosure checks | yes | remediation/fixtures pending | no |
| Native PG subset | prior local evidence only; rerun MEM-2 | pending | no |
| Production source issuer, project grants and recoverable lease | absent | no | no |
| Permanent source-fence capacity | 1,024 cap, no safe compaction | blocker open | no |
| Phase 36 identity/Dynamo/live quality/physical deletion | partial/unverified/blocked | open | no |
| MEM-2 | this change | separate session required | no |

The nine pre-existing untracked planning/review documents are user work and excluded
from this commit. No inherited gate is treated as accepted. Implementation may
proceed isolated and default-off under the explicit MEM-2 request.

## Authority and ownership

The middleware's RequestScope binds owner/app/workspace/exact nullable acting user.
Authenticated user mutations additionally require the bound verified principal,
matching subject and owner, recent upstream authentication and explicit versioned
intent. Development identity cannot mutate. Agents have only four host-registered
content tools: search, fetch, topics, propose. They cannot choose authority,
source metadata, identity, or receipts. No live provider dispatcher is installed.
The host explicitly binds a project and run; a run has finite calls/deadline and
cancellation. The resolver must authorize and hold its lease through every read
release and write. Missing authority fails closed, including HTTP composition.

Canonical Postgres memory ownership is retained. Pending suggestions are untrusted,
TTL-bounded content in a separate table, never knowledge or context input. Review
means reviewed/rejected, never verified. There is no production confirmation
registration: revision returns `unsupported_evidence_source`, including with a
synthetic resolver. Immutable KnowledgeRecord remains unchanged. Atomic evidenced
replacement and lineage are deliberately deferred until a real issuer exists;
no admit-then-supersede transaction is offered.

## Transactions and reconciliation

Migration 030 adds scoped proposals and content-free operation receipts. All writes
lock owner fence, knowledge namespace, then actor namespace in existing order.
Forget checks exact actor/target/project and expected lifecycle version, invokes
canonical transition with a narrow `verified_user` actor, and commits event,
projection and operation receipt in one transaction. Raw lifecycle entry points
reject this actor; only the control transaction may use it. Fake uses shared locks
and a staged transition before any dictionary mutation. Review CAS and receipt
also commit together. All mutations reauthorize under the source lease; source
fences and owner fence are checked inside the database transaction.

An actor-scoped UUID operation key binds operation, target, expected version and
canonical intent digest. Same intent replays its original receipt; changed intent
conflicts. On any uncertain storage outcome reconcile that exact key/digest;
otherwise return unknown_commit. Never issue a new identity automatically.
Cancellation/deadline checked before commit begins. Once a transaction starts,
its actual durable receipt wins over cancellation; lost acknowledgement remains
unknown until reconciled. Unsupported revision does not create receipts or state.

## Bounds, retention and erasure

Reads inspect at most 32 candidates for one host-resolved project, return at most
8 records, accept 200 query characters and have a 2-second cooperative deadline.
Tool runs allow 10 calls/10 seconds; cancellation denies subsequent calls. External
UUID misses and inaccessible targets collapse to forbidden_or_not_found. Exceptions
are normalized and never include IDs/content from denied rows. No unscoped totals.
Resolver calls must honor the host's bounded lease contract; synchronous adapters
cannot be forcibly interrupted safely. A blocking/unbounded resolver is unsupported.

Each exact owner/app/workspace/actor namespace retains at most 32 proposals (24-hour content TTL) and 256 operation
receipts. Receipts retain digest, actor category, target, versions, time and safe
reason only. After 30 days, a key returns expired and cannot be reused. Receipts
are never pruned to free quota: exhaustion fails closed until owner erasure. This
bounded anti-replay strategy deliberately sacrifices sustained availability; safe
compaction needs a separately accepted epoch/issuance protocol. Proposal expiry
redacts content during bounded control transactions; no scheduler is added.
Account export/deletion includes both tables. Existing source fences and their
1,024 cap remain unchanged. Logical forget advances validity epoch, invalidating
existing permission dependencies through final packing/history/summary/send checks.
Already-sent provider input cannot be recalled. SQL erasure does not prove physical
cloud erasure.

## Alternatives, rollout and falsifiable checks

Rejected: in-place record edits, developer_test user authority, free-form confirmed
prose admission, agent lifecycle writes, separate datastore/state machine, automatic
live tool dispatch, best-effort compensation and pruning replay keys. New agent,
management and mutation flags default false under memory_enabled and schema-3
selection. API/UI additionally require installed host authority. Disable flags for
rollback; retain forward schema, lifecycle events and tombstones. Native concurrent
transactions must show one CAS winner, complete receipts and rollback on failure.
Cross-actor guesses must disclose nothing; reviewed proposals must never enter
selection; stale dependencies must fail after committed forget.

# ADR 0025 — PAS workflow lifecycle and reasoning authority

Accepted for local development on 2026-11-03. Extends the execution ownership
decision in [ADR 0023](0023-external-consumer-and-execution-authority.md).

## Decision

PAS workflows own the execution of bounded PAS runs. Future reasoning strategy
chooses direct response, decomposition, critique or tool verification and owns
effort controls and promotion. For workflow dispatch it will submit the
versioned run specification to this lifecycle. It cannot create a second
executor or mint tool, spend, approval or source authority. Existing chat
continuations and P19 continue to own continuation and physical model attempt
identities. A future workflow using inference must delegate to those boundaries.

External coding harnesses own their edits, shells, tests, Git and execution
history. PAS can supply separately authorized context and opaque correlation.
The workflow contract has no external execution or private-memory export path.

The caller key is unique within verified owner, actor, client audience and
authorized party, application, workspace and fixed retrieval purpose. The
canonical intent digest binds that scope to the exact versioned request. At
first submission the row pins the operator's source snapshot. Replay returns
the same run for the same intent. A changed body conflicts. The live caller
requires current owner, client and membership authority. The tool checks its
registration and current source rights and confirms the actual snapshot used
at dispatch and disclosure. Tool output remains data.

One PostgreSQL row is authoritative for intent, run state, attempt receipts
and ordered progress. A row lock serializes claims and writes. A time-limited
token fences workers, and the attempt advances through reservation and dispatch
in separate committed transactions. Each receipt and its event commit together.
A lost lease before dispatch may abandon the reservation and resume under a
new claim. A lost lease after dispatch leaves the original run uncertain and
requires operator investigation. Cancellation suppresses subsequent dispatch
and live disclosure at cooperative boundaries. A disconnect leaves the
original attempt available for status observation. Cursor delivery is at least
once and bounded to a tail, with explicit gaps and a durable terminal outcome.

## Effects, background work and isolation

The canonical proposal, validation, human confirmation, physical execution,
uncertainty and reconciliation model for domain effects remains
`MutationProposal` and its repository-enforced transitions. It binds actor,
canonical payload and versioned operation, current target revision, expiry,
source and permission dependencies, and the original domain operation key.
Confirmation is checked against the authoritative stored binding. Recovery
observes that original operation key. A workflow approval ID or manifest can
never substitute for it. Synthetic tests exercise these existing transitions
alongside the workflow contract tests. The foreground workflow admits
read-only effects exclusively. Generic effect, background and native profiles
fail closed before admission. No new proposal or approval ledger is created.

Production enablement requires issuer-bound exact-attempt permits that
linearize send against revoke, an independently monotonic original-key and
forget authority, native mixed-age restore and reconciliation, and review.
Unattended execution also needs durable worker identity and fair, bounded
admission. An isolated adapter must prove actual filesystem, process, secret,
network and resource limits on the operating system. Local lease and replay
checks establish none of those properties.

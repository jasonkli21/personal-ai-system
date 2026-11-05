# ADR 0027 — Memory-specific governance overlay

Accepted 2026-11-04 for owner-authorized E0/E1 public/synthetic development only.

Canonical knowledge and lifecycle owners retain source records and erasure.
Memory governance references immutable source identities without copying content.
A host-owned authority supplies verified owner, actor, source and registered
recipient scope and epochs; a wire intent supplies only requested identifiers,
expected revision, purpose and a reference to an explicit user decision.

Alternative A, using profile consent directly, is rejected: profile fields and
application disclosure do not confer project knowledge or agent authority.
Alternative B, a typed memory overlay reusing consent CAS/original-key idioms, is
selected. Alternative C, a broad identity/sharing service, duplicates existing
owners and is outside this development authority.

No production issuer, table, route, tool, dispatcher or flag is installed. The
repository protocol describes atomic host-fenced transitions; the only adapter
is an isolated synthetic simulator. Deployed source/owner deletion locks, native
transactions, monotonic recovery and physical send require separate acceptance.
All read phases compare current grant/source/recipient/owner epochs. Regrant is
a new immutable grant and generation. Safety receipts are never quota-evicted.

Retention receipts name each store and topology; logical suppression is never
physical erasure. Restore is unavailable until separately surviving authority is
reconciled. Pure operator plans cannot execute changes. Profile-only portability
and inert import preview remain unchanged. No research manifest can grant rights.

Independent review, full phase exit and production remain BLOCKED / NO_GO.
See the [readiness audit](../memory/2026-11-04-governance-readiness.md).

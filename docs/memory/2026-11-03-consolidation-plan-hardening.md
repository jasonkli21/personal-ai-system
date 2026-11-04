# Bounded offline consolidation decision (MEM-4)

Date: 2026-11-03 (America/Los_Angeles). Status: accepted for this session's
synthetic development scope only; integrated delivery remains BLOCKED.

## Baseline and in-session plan review

Entry HEAD: `e906bfc1007d27bc75e97b4ad852bac901da931c`. Last commits are
`e906bfc` (episode remediation), `09f3ef1` (terminal-step component), `42f00b0`
(release tooling), `578ef8f` (offline release profiles), `60bcacb` (review fixes).
Seven user-owned untracked plans were present: five `docs/hxe-*` documents
(including the `.md.md` filename) and the MEM-3/MEM-4 detailed plans. Preserve
these inputs and exclude them from staging. No tracked changes at entry.

Reviewed the supplied MEM-4 plan in full in this session. Its integrated target
depends on authority not present in code. Migration 035 is the latest migration;
`EpisodeService.capture/read` unconditionally deny. Terminal receipts prove
structure only. `KnowledgeResolver.lease` requires a trusted host fencing sources
through commit/consumption; no production workflow issuer is installed. Existing
lifecycle jobs consolidate v1/v2 memories and fence their own state versions.
MEM-2 proposals have only `procedure`/`project_decision` content and their review
does not admit knowledge. Neither transaction owns a new source cursor plus typed
lesson/conflict edges. Reusing either would imply unverified authority/atomicity.

## Decision and precise seams

Implement an unregistered `memory.consolidation` component with a finite frozen
synthetic corpus and deterministic closed-vocabulary extraction. Only bundled,
hash-pinned fixture envelopes can enter its source registry. A coherent forged
envelope is insufficient: exact corpus membership, scope, issuer, revision,
monotonic synthetic grant epoch and expiry must match. This is a synthetic trust
root, never authentication for real data. No arbitrary text, receipts, private
session readers or eligibility booleans are accepted by the adapter.

Scope includes owner/app/workspace/project/actor/client/purpose/session. A
stream adds fixed adapter/policy/extractor generations; policy changes require
an explicit future backfill design. Ordered source sequence is independent of
timestamps. Candidate kinds are offline `procedure`, `lesson`, `conflict`, not
extensions to schema-3 accepted knowledge. Exact evidence edges remain mandatory.
Observed tool completion cannot become independently verified success. Corrections
outrank inferred suggestions; contradictions remain pending for review.

An in-memory repository adapter shares the synthetic issuer lock across final
source validation and one staged checkpoint/proposal/original-key assignment.
Lease generation and expiry fence competing claims; stable original keys exclude
the lease token so a lost ACK resolves under takeover. Changed payload under the
same key conflicts. Fault tests exercise both sides of that assignment. This is
a pure local transaction contract, **not durable database atomicity** or a new
worker. Native persistence, outbox and canonical lifecycle integration are deferred.

Source withdrawal/correction/regrant and owner/project forget invalidate reads
and cached candidates. Regrant increments epoch and cannot revive old evidence.
Content-free fences/receipts are retained under hard quotas; capacity denial never
evicts replay or deletion barriers. Restore/import is unsupported; stale snapshots
must revalidate against the current issuer and repository. Expired payloads are
removed by bounded explicit local maintenance. No acceptance/review API, UI,
agent tool, dispatcher, scheduler, feature flag or provider adapter is registered.

## Alternatives and scope changes

- Reject direct canonical-memory ingestion: it lacks an independently leased,
  cursor-addressable producer contract for this new use.
- Reject reading experimental episodes or extending the runtime worker: this
  bypasses MEM-3 blockers and adds unproven cross-store authority.
- Reject MEM-2 integration in this slice: its content kinds and transaction do
  not represent these source/checkpoint transitions. Pending-only offline output
  preserves governance until a reviewed mapping exists.
- Defer even an optional model adapter: no physical attempt/disclosure authority
  exists at this seam. Zero provider calls/tokens/retries is the enforceable bound.
- Freeze additive synthetic fixtures and comparison arms before scoring; author
  visible reserved cases are not independent held-out or real-model utility.

## Verification, evidence and rollback

Test exact scope axes, source forgery/currentness, corrections, duplicate/reordered
pages, CAS/dual claims, stale leases, crashes, original-key conflicts, lost ACK,
expiry, forget, stale cached objects, quota denial and content-free diagnostics.
Run focused and adjacent Make targets, lint and naming checks. Preserve all old
corpora and release locks, including their known source-identity failure. Native
SQL is opt-in and cannot be reported passed without its disposable prerequisite.

E0 is contract/code inspection; E1 is hermetic synthetic testing only. E2–E5
(native atomicity, live source/provider/disclosure, deployment/erasure and measured
longitudinal utility) remain open, as does independent exact-commit review.
Rollback removes the offline caller/component; there are no runtime consumers,
schema changes or accepted-memory writes to undo. Do not transfer synthetic
snapshots to runtime storage or use them as authority for MEM-5 retrieval.


## Continuation disposition

The owner requested completing safely isolated work and amending the delivery.
The [continuation decision](2026-11-03-consolidation-continuation-decision.md)
supersedes the above blanket SQL/review/backfill deferrals. The initial rationale
is retained as historical author assessment, not an independent review verdict.

# PI-4 pre-code plan hardening

2026-10-30, America/Los_Angeles. Written before runtime implementation in this
single session; no subagents. Entry HEAD/branch:
`00359b3e4941b3d0ff31575070aed083c77c98f8`, `main`, exactly the planning anchor.
No tracked modifications. Sixteen pre-existing untracked planning/review files
are excluded, including the supplied PI-4 plan/prompt. Darwin arm64 27.0.0;
system Python 3.9.6 is unsuitable; use backend/.venv Python and Makefile runners.
PI-0–3 independent acceptance, MEM-0/1/2, source issuer/lease/capacity,
Phase 36, deployed identity, physical send/erase, live provider and cloud gates
remain open. This user request authorizes local implementation, testing and one
commit, without push/deploy or real provider disclosure.

## Audit and threats

`context/profile.py` contains only four expressly user-set vocabulary fields:
units, locale, response style and answer length. These are a defensible small
personal-sensitivity v1; arbitrary text, inferred memory, health and finance are
excluded. Existing `shared_with_applications` is active in `shared_fields`, not
merely UI metadata. `api/profile.py` accepts unversioned PUTs, so it cannot remain
an authority for granting consent. `context/adapters.py` currently rechecks only
array membership: V1 -> V2 with the recipient retained launders stale V1.

`context/authorization.py` enforces cross_application=deny, operation/field and
model sensitivity. Keep it. Project a granted field into the destination envelope;
use permission dependencies to retain standalone/null source, owner, actor,
exact field, revision and grant identity. Destination scope is never client-selected
source authority. `auth/middleware.py` derives actor as issuer|subject and binds
verified principal; PI-2 client policy restricts external routes and rechecks
membership on disclosure. Owner management must independently require the UI
OAuth client, standalone/null, exact principal actor and recent upstream auth.
Manifest registration is not consent, membership or provider approval.

`context/history.py` propagates assistant dependencies and excludes revoked turns;
summary compatibility uses the filtered source set. Chat stores source snapshots,
checks pre-send and each external delta/completed replay. However, the PI-3
preparation guard covers history, not newly fetched optional sources, and builder
permission caching can outlive a count. Add a local builder guard across every
count, composed with the service guard, and a preparation guard across summaries
and their counts. Never replace an outer guard. No claim of DB-to-wire atomicity.

`memory/dependencies.py` and knowledge/control services require original scope,
actor, lifecycle and genuine project/source rights. No installed production
issuer/lease exists. An exact cross-app record view must be explicitly unavailable;
never install a synthetic resolver. `assist_response` does not permit extraction:
block automatic memory work for any completed turn carrying shared-profile taint,
including inherited history/summary taint, at the extraction source boundary too.

## Chosen design and rejected alternatives

1. Separate additive `profile_consents` owner aggregate in canonical PostgreSQL,
   with the existing payload-family export/delete machinery. Do not expand the
   16KiB profile row with receipts or embed unknown fields into its closed v1 model.
   Owner advisory deletion lock -> consent lock -> profile read/write. Profile
   writes take the same locks. In-memory methods use one shared RLock and the same
   pure transition. Reads have caller deadlines; revalidation gets a short bound.
2. Immutable create/revoke, no extend/reactivate endpoint. At most 32 **lifetime**
   grants per owner, each with one create and at most one revoke receipt: <=64
   content-free receipts. No pruning, no reused grant IDs, no stale extension.
   At capacity revoke still works; new consent requires future safe capacity
   design, not deleting replay fences. TTL <=30 days; exact expected consent and
   profile revisions; UUID operation key and intent digest. Exact same-key replay
   returns original receipt even after revocation, never re-applies it. Changed
   intent conflicts. Unknown write result: 503, reconcile original key only.
3. Grant binds whole profile revision and value fingerprint. Any profile update
   invalidates all grants conservatively, even if another field changed. Re-share
   needs a new affirmative action. Hash plus revision prevents value ABA reuse.
4. Legacy PUT retains value editing, rejects nonempty sharing arrays explicitly.
   Migration archives existing legacy arrays in the consent payload and strips
   them from active profile JSON, with a DB constraint rejecting old-style writes.
   This is intentional safe API narrowing, not silent success. Existing value-only
   callers still work. Never deploy an old reader concurrently with enabling;
   drain old services, migrate, deploy strict readers, then opt in. Rollback keeps
   migration/deny readers and disables sharing; no schema down migration.
5. Default-off operator flag checked at selection AND dependency revalidation.
   Owner management is recent-auth and UI-client only. Active destination means
   current installed registry definition, compatible workspace policy and current
   membership for non-null workspaces, rechecked at use. The supported initial
   actor is the same verified owner actor; delegates are denied. Provider disclosure
   stays under PI-3 privacy/free-first admission, independently of consent.
6. Management API/CLI instructions show exact value, recipient and expiry, explain
   lost ACK/original-key recovery and irreversible prior provider sends. Browser
   controls are deferred and UX acceptance remains incomplete. No PI-2 public
   consumer-schema change. No new packer, model client, vector scan or memory type.

## Revised workstreams and falsifiable checks

Implement contracts/pure transition, owner-locked PG and in-memory parity, dormant
migration and inventories; thin management routes and default-off composition;
canonical profile projection and exact dependency revalidation; count/summary/
history/send/replay guards and extraction denial; adversarial tests and installed
checks; same-session hostile diff review and evidence. Test default-off/legacy
no grant, unrelated destination positive, owner/client/actor/workspace mismatch,
wrong purpose/TTL/CAS/identity, stale value/ABA, revoke/expiry/disable, lost ACK,
changed-intent replay, concurrent revoke/create, source removal/DB outage,
summary/assistant inheritance and count/delta/replay schedules. Preserve historical
fixtures/locks; if needed append a source-only lock with identical quality inputs.

Native PG tests are opt-in; unavailable engine is blocked evidence, never a fake
pass. OS/Python network-fenced suites, installed wheels and physical absence,
PI-2 OpenAPI, PI-3 gates, memory/task/account tests, lint/build and diff checks
supply local evidence. Record failures and partial schedules candidly in P4-01–24.
Independent review is a separate session and owns acceptance. Residual risks:
post-last-check transport race, synchronous external authority deadlines, grant
lifetime capacity, real OAuth/membership, browser UX, rolling operator discipline,
backup restore/physical erasure and all inherited production gates.

## Implementation checkpoint follow-through

Same-session self-review permanently supersedes prior same-field/destination/actor
grants on replacement; otherwise revoking the newest could revive an older grant.
New owner-generated grant UUIDs are immutable intent identities scoped to owner and
actor, rather than server-issued handles: this supports durable pre-dispatch intent
and lost-ACK recovery without a second allocation protocol. They confer no access.
Native tests now use an isolated temporary UTF-8 PG17/pgvector cluster; unavailable
cloud/native recovery gates are still open. The prompt projection is compact and
content-minimal so the unchanged planner budget also works under PI-3's exact fake
byte counter; full provenance/expiry/consent remains in server authority snapshots.
Source rechecks deduplicate only within each boundary and remain uncached across
count/summary/send/delta/replay. Builder guard state is local to each invocation,
preventing one concurrent build from overwriting another's authority. Recipient
registry/policy and the sharing flag are resolved through current request authority.

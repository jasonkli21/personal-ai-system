# PI-4 implementation and independent-review handoff

2026-10-30, America/Los_Angeles. **Local candidate; independent acceptance is
pending.** Entry HEAD/main: `00359b3e4941b3d0ff31575070aed083c77c98f8`.
The user explicitly authorized one-session implementation and a single local
commit, with no subagents. No push, merge, deployment, credential download,
real provider or personal-data use was performed. Sixteen pre-existing untracked
planning/review files, including the supplied plan/prompt, are preserved and
excluded. The final commit is the single child of that entry revision containing
this report; resolve it with:

```sh
git log -1 --format=%H -- docs/platform-independence/pi-4-implementation-report.md
```

The final user handoff supplies the SHA. The report cannot embed its own Git hash.
[Machine evidence](pi-4-verification.json) binds final implementation/test files,
source/fixture/artifact identities, exact commands and P4-01–P4-24 dispositions.
[Pre-code hardening](pi-4-plan-hardening.md) was written before runtime changes.
[API/operations](profile-sharing-v1.md) owns examples, CAS/error recovery and rollout.

## Implemented boundary and inventory

The four existing explicit profile fields feed an unrelated application through
`ContextPlanner`, the built-in `GlobalProfileContextProvider`, normal application
policy, `ContextAssembler`/`ContextBuilder` and the existing PI-3 inference path.
Nothing is inferred or promoted into global memory. Same owner, registry metadata
and recipient headers are not consent. `cross_application='deny'` remains unchanged.

| Files / seam | Result |
| --- | --- |
| `context/profile_consent.py` | Closed intent/grant/receipt contracts, shared pure create/revoke transition, owner management service, destination policy check and explicitly unavailable exact-record memory view |
| `context/profile.py`, `context/adapters.py` | Shared repository contract/fake, default-off projection, exact grant/value/profile revision/source/actor/recipient dependency and fail-closed revalidation |
| `persistence/postgres/context.py`, migration `032_profile_consents.sql` | Canonical owner aggregate, native CAS/atomic receipts, owner->consent->profile lock order, bounded reads/writes, legacy archive/clear/old-writer SQL constraint, fenced operator purge |
| `api/profile.py`, `api/dependencies.py`, `auth/middleware.py`, settings/env | Thin recent-auth builtin-owner list/grant/revoke; current identity/client/recipient policy/flag authority; explicit legacy PUT rejection; default-off composition |
| `context/{authority,history,assembler,builder,deadline}.py`, `llm/disclosure.py` | Complete dependency requirement, per-boundary deduplication, inherited summary/history fencing, composed guards across every relevant count/summary/physical reservation; per-invocation guard state |
| Chat/external-turn services, `memory/services.py` | Existing SSE/key paths retained, revoked profile output/replay denied, shared-profile taint refused before automatic extraction/embedding |
| Owner/export inventory and persistence README | New consent/archive/receipt family exported through existing payload-family path; explicit fenced erasure seam; physical backup/cloud erasure unclaimed |
| Reading Logbook host | Separate default-off `READING_LOGBOOK_PROFILE_ENABLED` recipient policy; client remains HTTP-only and cannot manage consent |
| Tests, scripts, Makefile | PI-4 fenced regression target, native migration/CAS/rollback/ACK probes, signed HTTP sharing test and installed core test inclusion |
| Evaluation adapter, source-only v23 | Synthetic profile fixture issues explicit consent and exact actor; synthetic memory fixture binds that actor when minting dependencies; historical corpus, scoring, config and v10–v22 lock bytes preserved |
| Root/router/current-state/PI docs | One living state, owner contract/operator instructions and this evidence; no independent verdict |

The full path/SHA-256 ledger is in the JSON; `git show --stat <commit>` supplies
the committed diff inventory. No earlier migration, memory schema, source fence,
forget receipt, vector space, task intent/key, consumer version or OpenAPI subset
was rewritten. No external app gains account, task or consent-management routes.

## Security decisions and same-session adversarial review

- Grants bind exact owner/issuer|subject actor, standalone/null original source,
  destination application/exact nullable workspace, one field, `assist_response`,
  finite expiry, whole-profile revision and value/set-time fingerprint. Any profile
  edit invalidates all previous grants, including value ABA and unrelated-field
  edits. New owner-generated UUIDs are scoped immutable intent IDs, not authority.
- Management requires recent verified upstream auth, builtin UI client binding
  and standalone/null scope. External clients, development identity, delegated
  actors and wrong scopes cannot manage consent. Current owner/client/workspace
  rights and destination capability/field/sensitivity policy are independent
  checks. Provider admission remains PI-3's independent strict-free/privacy gate.
- A separate owner aggregate avoids expanding the closed 16 KiB profile v1 row.
  At most **32 lifetime grants / 64 receipts / 128 KiB**; no pruning or reused
  grant IDs. No extend/reactivate endpoint. Revocation still works at capacity,
  after source edits/expiry or recipient removal. New same-coverage grants
  permanently supersede old grants; otherwise revoking the latest would revive
  an older dependency. A regression specifically tests that discovered threat.
- Exact `If-Match`/expected consent and profile revisions plus the original
  operation UUID bind immutable intent. Replay observes an original receipt even
  after revocation/expiry; it never reapplies a grant. Changed intent conflicts.
  Native lost-ACK and pre-commit failure probes distinguish commit from rollback.
- Old arrays were active authorization, so migration archives then clears them
  and refuses old writers. Value-only PUT remains compatible; nonempty arrays
  explicitly fail, rather than silently succeeding as new consent. Old readers
  must be drained; the DB constraint cannot patch their cached process state.
- A destination-scoped item retains true source rights in its dependency. The
  prompt contains the selected value, original source label and revision; full
  grant/expiry/provenance stays in the server graph/trace. This compact projection
  fits the unchanged small planner budget under the exact fake byte counter.
  No source or model budget is increased to make the positive test pass.
- History guards alone missed newly fetched optional fields during later counts.
  The builder now checks profile dependencies before each count and composes its
  guard with history and service guards. Summary counts/dispatch are fenced too.
  Positive lookups are deduplicated only within a boundary, never cached across
  counts, summaries, reservations, deltas or replay. Guard state was made local
  to each build after self-review found a concurrent-overwrite hazard.
- Assistant and summary dependencies/expiry propagate through existing snapshots.
  Value changes/revoke/expiry/source loss/owner fence/recipient loss/outage/disable
  deny subsequent model reuse. Completed-key replay and per-delta output use the
  same original source dependencies. The same key cannot trigger another send.
  The current check also covers builtin-client replay of profile-tainted output.
- Shared profile content cannot become automatic memory just because it appeared
  in an answer. Extraction refuses tainted completed turns before reading source,
  invoking an extractor or embedding. Original source/actor/project issuer and
  lease gates prevent a legitimate cross-app exact memory view: it is explicitly
  unavailable, with zero-content/provider/embedding denial tests.

Review also challenged stale/corrupt/missing dependencies, foreign existence
oracles, capacity denial of revoke, simultaneous stale create/revoke, field and
workspace substitution, policy/sensitivity downgrade, legacy version skew,
flag rollback, physical-send races and restore. No claim of atomicity between
PostgreSQL and an external wire is made. A final check cannot recall an in-flight
send. Historical user-visible conversation records remain; only future model
reuse/replay is suppressed. Legacy records without attributable source metadata
cannot be retroactively proven untainted; production migration/review must account
for that provenance limitation. No live source issuer or backup-restore fence was
invented to conceal a missing production prerequisite.

## Verification environment and observed checks

macOS arm64, Darwin 27.0.0 / Python platform macOS 27.0.1; CPython **3.11.15** in
`backend/.venv` (system Python 3.9.6 was not used for tests). Existing locked
Python dependencies and bundled Node/pnpm were used; no dependencies downloaded.
PG17/pgvector ran only in an isolated temporary UTF-8 cluster on 127.0.0.1:55434,
with fresh synthetic per-test databases. No configured user/cloud database was
used. Native erasure evidence covers those synthetic rows only.

Final observed outcomes (overlapping groups must not be added as unique tests):

- Focused final-source consent/context/planning regression: **243 passed**;
  native IPv4/IPv6/Unix denial and zero forbidden Python network attempts.
- Broad expanded target: **890 passed, 3 failed** in the inherited matrix/Phase36
  checks, zero forbidden network attempts. Subsequent isolated owning files:
  **24 passed**, zero forbidden attempts. This is an unresolved whole-target
  verification gap, not a demonstrated timing/root-cause fix.
- Installed artifacts: **137 core**, **190 reference compatibility**, **56 retained
  task**, and **65 HTTP/client passed, 1 existing skip**. The PI-4 signed unrelated
  recipient flow passed with physical reference absence. Consumer contract and
  zero forbidden dependency edges passed; every installed fence reported zero
  forbidden network attempts.
- Native PG: **5 new consent tests passed** plus **1 existing profile/concurrency
  test passed** (24 unrelated cases deselected). The isolated cluster was stopped
  after verification. DynamoDB/cloud/backup acceptance remains unclaimed.
- Frontend: **130 passed / 25 files**, lint, typecheck and production build passed.
  Backend/reference/host Ruff and whitespace checks passed.

The exact commands, source identities and log digests are in JSON. Check classes:

| Check | Evidence boundary |
| --- | --- |
| `make pi4-check` / its exact `pi4_checks.py` runner | Inspected context/chat/auth/account/memory/provider/routing suites under macOS native IPv4/IPv6/Unix denial plus Python audit fence; manual/cloud/native suites excluded |
| `UV_OFFLINE=true UV_CACHE_DIR=/tmp/pi4-uv-cache make pi2-check` | Offline wheel/sdist builds, static guard, preserved planner, unchanged consumer OpenAPI, installed core/reference/retained-task profiles and signed synthetic HTTP/client including opt-in PI-4 flow |
| Native `pi2_http_checks.py -m persistence_integration ...test_profile_consent_native.py` | Five real local PG probes: CAS/replay/fence/purge, old-writer rejection, forward legacy archive migration, lost ACK, transaction rollback; Python loopback-only fence |
| Frontend Makefile tests/lint/typecheck/build | 130 tests / 25 files, lint/type checks and Next production build passed; browser UX not exercised |
| Backend lint, dependency and diff checks | Ruff, zero forbidden core/reference edges, no whitespace errors; no backend typecheck target exists |

The installed tests use synthetic verified JWTs and fake certificate transport,
real FastAPI middleware and loopback HTTP. The unrelated client/host are installed
outside the checkout with references physically absent and client-only dependency
isolation. Fakes establish no real OAuth, IAM, provider billing/privacy or cloud
behavior. Native engine results establish no DynamoDB, deployed deletion, backup
restore or production security acceptance.

### Failure history retained

Initial local fixture errors were corrected: invalid synthetic email/domain
configuration; managed attribution missing producer identity; incorrect assumption
that exact receipt replay must conflict after revoke; helper import/tool manifest
setup; internal vs wire continuation request type; catching the wrong safe error
type; a missing mandatory client creation key; and replay's documented
`UncertainTurn` result. The initial new suite reported 28 failures/1 pass, then
9 failures/20 passes; expanded intermediate groups reported collection errors,
8 failures/159 passes, 9 failures/167 passes and 2 failures/174 passes before the
176-pass focused run. These were not represented as acceptance passes.

The first general count guard changed existing optional expiry semantics. It was
narrowed to shared-profile dependencies while retaining the old safe behavior for
other sources. The signed positive path then exposed verbose profile metadata
exceeding the exact fake counter's per-selection budget: compacting the disclosed
projection fixed this without relaxing budgets. The Reading Logbook's history-only
manifest initially correctly refused consent; a separate explicit host opt-in was
added. The evaluator initially minted memory dependencies before binding its new
synthetic actor; binding that fixture scope fixed the no-reference probe without
weakening memory authorization or editing fixture JSON.

An intermediate broad run passed **884** tests with zero forbidden network
attempts. A later expanded run had **891 passed, 2 failed** in the inherited
provider-matrix/Phase36 synthetic groups (failed case count 4 vs 1; synthetic case
count 78 vs 80), with zero forbidden attempts. Clean isolated results or a later
pass do not establish a root-cause fix. The final expanded run then had **890 passed, 3 failed**: the two same checks
plus `test_matrix_uses_generic_profiles_task_contract_and_p21_p19_seams`.
The final isolated owning files passed **24**. No inherited failure is silently
reclassified as passed and no unrelated timing fix was made.

Two installed-check attempts stopped at the actor-fixture assertion and the
strict source-binding guard respectively. The latter correctly detected the
later source README edit; v23 was rebound to the final complete source identity.
Historical v10–v22 lock bytes, corpus, configuration and fixture dependencies were
not changed. Native initialization first hit sandbox shared-memory denial; the
authorized isolated cluster was then initialized as UTF-8. One unused SQL_ASCII
scratch initialization was not used as verification. OS/loopback tests require
execution outside the tool sandbox but keep their own network fences. One launch
was rejected by automatic approval review because of account usage limits; the
user instructed continuation and the normal approval path later succeeded. No
approval or network-fence bypass was used.

## Limits, rollout and rollback

This is a bounded profile-sharing implementation candidate, not full PI-4 or
production acceptance. Browser management controls/usable consent UX remain
incomplete. The exact-record memory view is unavailable. Lifetime grant capacity,
legacy unattributed history, current authority callback latency, physical send
linearization, real identity/provider/cost, cloud/private invocation, backup and
replica erasure/restore anti-rollback, Linux/Python 3.12 and prior independent
PI-0–3/MEM/Phase36 gates remain open. Synthetic elapsed times are not p95 evidence.

Ship migration dormant, drain old readers/writers, deploy strict readers and only
then opt in with a synthetic owner. Stop/disable sharing and drain for rollback;
retain forward schema, grant epochs, receipts and owner deletion fences. Disabling
also denies future reuse of already-persisted dependencies. A kill switch does
not permanently revoke unexpired user consent; revoke explicitly before resuming
if it must never resume. Keep sharing disabled after restoring backups until
post-backup revocations, deletion fences and original-key receipts are reconciled.
No automatic remote retry/rekey, down migration or stale allowlist restoration.

## Separate independent review entry

Use a **new Sol High session** against the single commit resolved above; this
implementing session supplies no independent verdict. Verify parent/base and all
file/fixture/artifact hashes in JSON, preserve the sixteen unrelated untracked
files, then read hardening, contract, this report and P4-01–P4-24 dispositions.

Run `PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint`, `make pi4-check`,
`UV_OFFLINE=true UV_CACHE_DIR=/tmp/pi4-review-uv-cache make pi2-check`, and
`git diff --check`. Run the native file with an explicitly isolated local
`PERSISTENCE_TEST_POSTGRES_DSN` whose test role has CREATEDB and pgvector; never
point it at personal or cloud data. The native fixture creates/drops synthetic
databases. OS-fenced PI-4 currently requires macOS; another OS needs an equivalent
native fence rather than bypassing it. Check any failing inherited tests separately.

Independently attempt forged client/actor/workspace/source, stale value ABA,
replacement->revoke->old replay, concurrent guard overwrite, expiry/revoke during
fetch/count/summary/reservation, revoke after first SSE delta, completed-key replay,
old writer/cache resurrection, corrupt dependencies, capacity and erasure/restore.
Inspect the original authority graph and original keys, not only happy-path mocks.
Review missing UX/exact memory view, callback deadlines, version skew and post-last-
check transport/restore boundaries without calling them production passes. Only
that separate review can decide local PI-4 acceptance; production acceptance is a
distinct future process. MEM-3+ remains frozen.

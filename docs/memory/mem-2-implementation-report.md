# MEM-2 implementation and verification report

Date: **2026-10-29**, America/Los_Angeles. Entry HEAD:
`7c8f2671ffc163f803e781b9b34d6c81d466e8fa`. The single implementation commit is
identified by this report's containing Git revision; no push or deployment occurred.
This is implementation-session QA. Independent review belongs to a separate session.

## Delivery and exit disposition

| Status | Disposition |
| --- | --- |
| Narrowed implementation complete | Yes: bounded read/propose/review/reject/user-forget slice |
| Full MEM-2 implementation complete | **No**: evidenced revision/atomic replacement and production host are absent |
| Offline verified | Local checks recorded below; synthetic corpus and native PG are separate evidence |
| Independently accepted | **Pending**, including fixture challenge and inherited MEM-0/MEM-1 closure |
| Production promotable | **No**, all new flags remain false |

The prompt explicitly permits a partial default-off component when trusted source
registration cannot be established. Inspection found `UnsupportedKnowledgeResolver`
as the default and no production completed-turn confirmation/workflow issuer or
recoverable lease. Every revision therefore returns `unsupported_evidence_source`.
No replacement row, source edge, lineage, supersession or receipt is written for
revision. There is no successful correction demo or revision race to certify.
Review merely marks pending content reviewed/rejected and never admits knowledge.

The [pre-implementation ADR](mem-2-control-adr.md) records trust classes, alternatives,
quotas, atomicity and inherited gates. Rejected alternatives include free-form user
confirmation as historical test evidence, developer_test user authority, in-place
claim edits, separate active-state machines/databases, automatic provider tool loops,
admit-then-supersede compensation, and pruning replay keys to free capacity.

## Ownership, identity and defaults

Code changes are grouped below; the exact patch is the single containing commit.
Nine initial untracked user planning/review documents were preserved and excluded,
including both `docs/memory/plans/mem-*-detailed-implementation-plan.md` files.
There were no initial tracked changes. No subagents were used.

| Owner/path under `backend/src/personal_ai/` unless stated | Behavior |
| --- | --- |
| `memory/control_contracts.py`, `control_service.py`, `control_repository.py` | Strict content contracts, bounded lexical reads, currentness/dependencies, pending status and staged atomic decisions |
| `memory/control_tools.py` | Explicit four-tool host registration, strict schemas, run budget/cancellation; no dynamic invocation from assistant text |
| `persistence/postgres/control.py`, migration `030_memory_control.sql` | Canonical PG control storage, owner/source locks, CAS, atomic lifecycle + receipt, bounded retention and fenced operator purge |
| Lifecycle contracts/repositories and PG lifecycle | Narrow verified_user category, refused by public raw apply_event; control transaction alone can forget schema 3 |
| `api/memory_control.py`, `main.py`, `settings.py`, environment examples | Default-off API composition, authenticated middleware scope and recent-user mutations, explicit missing-host denial |
| Owner inventory and PG account export | Both new scoped families exported; operator erasure requires existing owner fence |
| `evaluation/control_runtime.py`, `memory_control.py`, new fixture and Make target | Hermetic host, versioned rubric-independent runtime inputs and scorer |
| `evaluation/planning.py`, new v18 lock, planner regression | Source rebind only; v17 and all earlier locks/30-case corpus remain immutable, no promotion |
| `frontend/src/app/memory`, `features/memory`, API proxy and tests | Gated inspection/review/reject/explicit forget, safe statuses, same-intent reconciliation and no optimistic success |
| New backend control/API/context/native tests and migration test adjustment | Actor, injection, races, fault, invalidation, export/erasure, quota/retention and inherited migration sequence |
| Current state/router, package READMEs and MEM-2 documents/evidence | Living boundary, operational rollback and independent review handoff |

`memory_agent_tools_enabled`, `memory_user_management_enabled` and
`memory_user_mutations_enabled` default false. They require `memory_enabled` and
`memory_knowledge_selection_enabled`; mutations additionally require management.
Admission is deliberately not required because none of these operations admits a
claim. The browser has an independent `MEMORY_USER_MANAGEMENT_ENABLED=false` gate.

API prefix `/v1/memory/control` has GET knowledge/search, exact fetch, topics and
proposals; POST pending decision, exact forget and unsupported revise. Scope comes
only from authenticated middleware. Mutations additionally check the bound verified
principal's exact issuer/subject-derived acting user and owner, recent upstream auth,
explicit boolean intent and integer expected version. Development identity cannot
mutate. Foreign UUID presence is collapsed into `forbidden_or_not_found`; errors
contain no raw source/DB exception or unscoped count. No public agent invoke route.

`memory_control_host` must be installed explicitly by trusted server code and supply
resolver/lease and project mapping. No production host is installed; flags alone
return unavailable. Test host identity is synthetic, not Google acceptance. Model
arguments contain no owner/actor/application/workspace, grants, source identity,
verification, outcome or receipts. Host construction binds service scope/project;
ten serialized calls and ten-second admission lifetime bound each tool run. A model
cannot create a capability by emitting tool text. Pending suggestions cannot enter
MEM-1 selection or its context index. Read views retain exact permission dependencies
for downstream revalidation as well as untrusted historical authority/time labels.

## Commit, replay, erasure and race semantics

PG lock order is owner fence → existing knowledge namespace → actor namespace.
The narrow repository reads current source fences and expected lifecycle state under
that transaction. Forget invokes canonical `transition` with verified_user, updates
validity epoch/version and writes lifecycle event/projection and receipt in one
commit. Pending review CAS and its receipt share one transaction. The in-memory
adapter uses the shared message/memory/lifecycle locks and stages decisions first.
No second accepted-memory status is stored. Immutable schema-3 content is unchanged.

Operation UUID is actor/scoped, with digest binding project, operation, target,
expected version and canonical content intent. Equal payload replays its original
receipt. Changed payload conflicts. Conflict receipts describe no applied mutation.
On write uncertainty, only the original operation ID/digest can reconcile; absent
or unavailable receipt returns unknown_commit. Failed source-lease release after a
write also returns unknown; it cannot erase an actual commit. Before-attempt authority
failure returns unavailable. Cancellation denies later tool admissions; an already
started transaction settles its durable receipt rather than reporting an invented
rollback. A cancelled HTTP client retains an uncertain UI intent until reconciliation.

Native barriers exercise independent SQL sessions and two spawned processes at the
same expected version. One forget succeeds, one conflicts, one event/projection
exists and both outcomes have matching receipts. Review has equivalent CAS checks.
Injected receipt-insert failure rolls back the entire forget/review/proposal effect.
Commit-then-lost-ack tests recover the exact receipt or explicitly stay unknown. Source
revocation after service validation is rechecked inside the transaction and denied.

User forget invalidates cached retrieval and returned tool dependencies, shared
packing/final marginal counts, later history/summary dependency checks and pre-provider
handoff. Already-sent provider input cannot be recalled. The tests establish those
local boundaries, not distributed serialization at a real provider physical network
send; no live schema-3 dispatch host is installed. That gap remains a production gate.

Proposals expire after 24 hours and are erased on a later bounded write; idle namespaces
have no scheduled physical eraser. Per exact actor namespace, 32 retained proposals
and 256 operation receipts cap storage. Proposal keys retire at 24 hours, other keys
at 30 days; receipts remain permanently quota-counted until fenced owner erasure.
Retired keys never execute again. This intentionally sacrifices sustained availability
for replay safety. No unsafe compaction of the separate 1,024 MEM-1 source fences.

Owner inventory/export contains both new families. The operator seam `erase_owner`
requires the existing owner fence and erases all actors/scopes for the owner while
holding the same owner lock. Native SQL export and erasure passed. This does not add
an automatic account-deletion executor or prove backup/cloud physical deletion.

## Executed evidence

All runs used the existing backend virtual environment. Frontend commands used the
bundled Node executable via PATH; the initial shell lacked `node`. No model provider,
DynamoDB Local, cloud endpoint or infrastructure deployment was used.

The first full offline run had **1,980 passed, 2 failed, 110 deselected**: a test fault
hook attempted a second forget during counting, and the unchanged v17 source lock
correctly rejected changed source. The hook was made one-shot; v18 preserves v17's
configuration/runtime/corpus and binds the new source. Earlier focused test failures
included a wrong fake-counter method and missing required Settings fields; these
were test setup errors, not ignored checks. The final commands/results are recorded
in the verification table appended below.

The first local PG attempt was sandbox-denied; a permitted restart of the old synthetic
cluster then found the historical role absent. A new isolated cluster was initialized
with role `mem2_test` at loopback port 55492. Tests create/drop random test databases;
no existing application database was truncated. Native engine: PostgreSQL **17.11**
(Homebrew/aarch64), pgvector **0.8.7**. The original failed attempts are not passes.

The active `mem2-control-v1` fixture has **36/36 passing** synthetic cases, partitioned
30 development/six public tagged holdout. SHA-256:
`7d2e93b33904ddb81bef6e4f8f3ffff89a51b7d63b85b5e88c21877c4b6c2a9d`.
The scorer observes **0 unauthorized reads, 0 unauthorized writes, 0 false successes**
in its declared control probes, with one explicit unsupported revision abstention.
The lexical positive control returns one item; its unrelated-query twin returns none.
All cases retain one accepted knowledge row; only authorized forget cases advance
lifecycle state, and proposals/review never add accepted rows. The separate native
race/failure assertions are not inflated into this 36-case denominator.

The [evaluation contract](mem-2-evaluation-contract.md) describes threat partitions,
scoring and false positives. ASCII/sensitive/instruction filters conservatively reject
legitimate text too. Corpus scenario p50/p95/max was approximately **5.33/6.62/8.88 ms**,
including synthetic setup and seeding. These timings are not database or model-quality
measurements. Resource measurements and full observations are preserved in
[mem-2-evidence.json](mem-2-evidence.json); the final-source measurements supersede
any intermediate resource probe. Query amplification at N=32 is a rollout blocker.

The final baseline replays preserved MEM-0's semantic digest
`f961fd6335397f3efb6ccacc8f6ac9b4a357d949a1671426399014c6dc470f28`, MEM-1 proxy
`7787f8be9434f078fd257af4a35045e5e3ac0cde39e9d2af34118117edd26d92`, and MEM-1 consumer
`865a871cb81ebadb4dc7584e48aed2391a5a5409e7920f12d313106c7e61099b`. The evidence JSON
checks 24 historical memory/planner fixture files byte-for-byte against entry HEAD.
No existing fixture, report, accepted schema or historical planner lock was rewritten.

The machine-readable [MEM-2 blocker ledger](mem-2-blockers.json) carries these
remaining obligations without changing historical Phase 36 results.

## Open blockers and rollout

| Priority | Gate / exact remaining work |
| --- | --- |
| P0 | No P0 found in this implementation QA; independent review remains required |
| P1 | Register a real trusted confirmation/workflow issuer and recoverable project/source lease; design/test atomic evidenced replacement + lineage before supporting revision |
| P1 | Accept MEM-0 closure, MEM-1 remediation/fixtures and MEM-2 implementation/corpus independently |
| P1 | Production Google/service identity, current app/project membership/revocation and physical provider-send fencing remain unverified; no live host registration |
| P1 | Phase 36 Dynamo/native/cloud/physical deletion/recovery/live quality gates remain open; SQL purge is not system-wide physical erasure |
| P2 | Permanent 1,024 source-fence quota and new 256 actor receipt-key cap can exhaust; prove replay-safe epoch/issuer retirement before compaction |
| P2 | Read query amplification; two-second operation deadline is cooperative across synchronous resolver calls. Missing/unbounded blocking resolver cannot be safely force-interrupted and is unsupported |
| P2 | No scheduled idle-proposal physical eraser; operator/next-write erasure only. Browser unknown intent is in component state and does not survive a page reload |
| P3 | Topics are only eligible kind labels; no semantic index, relevance evaluation, pagination beyond bounded fail-closed corpus, or real-model task-quality evidence |

Rollback: disable all three new flags and frontend management gate, remove explicit
host/tool registration if any, retain forward migration, lifecycle forget and permanent
anti-replay keys/fences. Confirm disabled routes and unchanged legacy fixture identities.
Do not erase receipts merely to restore availability. The concrete review checklist is
[mem-2-independent-review-handoff.md](mem-2-independent-review-handoff.md). MEM-3 planning
may use this bounded control architecture; production trace capture needs accepted
identity/source/consent, retention/erase and live disclosure boundaries first.


## Final-source resource envelope

Five local samples per N; nearest-rank p95 with five samples equals the maximum.
SQL counts are application `execute` calls and exclude connection/timeout machinery.
Reads revalidate each candidate and returned dependency, so this intentionally
unoptimized safe slice makes many bounded round trips. N=128 abstains at the 33rd
candidate sentinel rather than silently scanning the namespace.

| Eligible N | Outcome / returned | SQL calls per read | p50 ms | p95/max ms |
| --- | --- | --- | --- | --- |
| 0 | found / 0 | 5 | 2.36 | 3.00 |
| 1 | found / 1 | 29 | 16.52 | 22.72 |
| 32 | found / 8 | 605 | 151.13 | 175.48 |
| 128 | limit_exceeded / 0 | 5 | 5.96 | 7.20 |

One representative pending row consumes 437 JSON-text bytes / 470 bytes PG column
storage; its safe operation receipt consumes 562 / 594 bytes. These are observed
sample rows, not maximum table/index overhead. Payload constraints allow at most
8,192 bytes per proposal and 2,048 per receipt, capped at 32 and 256 rows per exact
actor namespace (256 KiB / 512 KiB payload ceilings). Receipt keys remain counted
after expiry; no churn compaction is claimed. Real-model/provider costs are unverified.

Final backend source identity (the v18 path manifest):
`4c03c9668ed2fb02345fa3a4d60cfb1ded05ac7306f50b420a3ec1536ec43588`.
This binds entry HEAD plus the tested patch; frontend/document changes are identified
by the containing commit. No runtime/config/corpus promotion follows this identity.


## Final verification commands

Commands run from repository root. `PATH="$PWD/backend/.venv/bin:$PATH"` selects
this repository's existing Python environment; frontend PATH adds the bundled
Node bin directory. Logs were retained under `/private/tmp/mem2-*.log` for this
session; durable sanitized evaluation/resource observations are in the evidence JSON.

| Command | Result |
| --- | --- |
| `PATH="$PWD/backend/.venv/bin:$PATH" make backend-test-offline` | **1,987 passed, 111 deselected**, 4 warnings, 199.85 s, final unchanged source |
| `PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint` | **Passed**, All checks passed |
| `make memory-control-eval memory-task-eval memory-knowledge-eval memory-knowledge-causal-eval memory-eval memory-lifecycle-eval memory-optimization-eval planning-eval` with backend PATH | **All eight passed** on final source; MEM-2 36/36, prior semantic digests preserved, planning non-promotion |
| `backend/.venv/bin/python -m pytest backend/tests/test_memory_control*.py backend/tests/test_planning_experiment.py -q` | **114 passed** before the last dependency-carrying view regression was added; final full suite includes that test |
| `PERSISTENCE_TEST_POSTGRES_DSN='postgresql://mem2_test@127.0.0.1:55492/postgres' backend/.venv/bin/python -m pytest backend/tests/persistence/test_memory_control_postgres.py backend/tests/persistence/test_verified_knowledge_postgres.py backend/tests/persistence/test_local_persistence.py backend/tests/persistence/test_memory_lifecycle_projection.py backend/tests/persistence/test_account_export.py -q -s` | **44 passed, 8 skipped**, 25.79 s, prior snapshot; skips require DynamoDB Local |
| Same local DSN, `backend/.venv/bin/python -m pytest backend/tests/persistence/test_memory_control_postgres.py -q -s` | **12 passed**, 13.47 s on final source, including refreshed resource probe and process/session races |
| `make frontend-test frontend-lint frontend-typecheck` with bundled Node PATH | **129 tests passed** in 25 files; lint and both TypeScript checks passed |
| `NEXT_TELEMETRY_DISABLED=1 make frontend-build` with bundled Node PATH | **Passed**, Next.js 15.5.23; /memory and proxy compiled; warning about existing ESLint Next plugin configuration |
| JSON parse and local Markdown link validation for new documents | **Passed** |
| `git diff --check` and `git diff --cached --check` | **Passed**; nine original untracked documents excluded |

An intermediate full run also passed 1,986 tests; the final run above supersedes
it after adding dependencies to returned tool views. The known historical provider
matrix timing issue was not changed or declared fixed. No DynamoDB Local, Google
identity, provider, cloud, deployment, browser-device or independent-review pass
is inferred from these commands. Both local clusters started in this session were
stopped after native checks.

# MEM-1 implementation and verification

Date: 2026-10-29 (America/Los_Angeles). Tested base:
`293a5910827d9a1f70e1342ee3b98f24ab615e4d` plus this implementation patch.
Checks ran in a dirty tree before the single implementation commit. The initial
tracked tree was clean. Eight pre-existing untracked planning/review documents,
including the companion MEM-1 plan, were preserved and excluded from the commit.
No subagents, live provider calls, deployments, external schema writes or pushes.

The bounded offline implementation is delivered as a review candidate; this is
not an independent acceptance verdict. The [ADR](mem-1-contract-adr.md) records
the selected ownership and the [handoff](mem-1-independent-review-handoff.md)
identifies separate review obligations. Both new flags remain false by default.

## Independent-review remediation addendum (2026-10-29)

The review of baseline `2df112bf04b8d817c2cfee9c807786161d2fec4f` found
cross-actor source mutation, a late packed-context permission window, and a
Task B benchmark side channel. The scoped fixes and verification are recorded in
the separate [review remediation evidence](mem-1-review-remediation-evidence.md).
Migration 029 binds source fences and edges to acting user, context permissions
are rechecked after final counts and immediately before model handoff, and the
new deterministic packed-content companion benchmark has its own `mem1-consumer-v1`
identity. The original 20-case `mem1-paired-v1` bytes and historical results are
preserved and labeled as a structural/stateful proxy.

Acceptance remains **no-go**. The 1,024 source-fence quota retains permanent
replay tombstones; safe compaction is a production-promotion blocker with a
separate [capacity follow-up](mem-1-tombstone-capacity-follow-up.md). Production
issuer/lease, application-grant policy, deployed identity and deletion, cloud
acceptance, independent fixture review, and real-model utility remain open.

## Entry-gate attempt and sequencing authorization

The supplied prompt's independent MEM-0 v2 acceptance record was absent. The
user explicitly authorized continuation without acceptance, then requested an
attempt to resolve MEM-0 first and continuation if incomplete. The
[entry verification](mem-0-entry-reverification.md) records that attempt:
1,836 initial offline tests and 281 focused tests passed; F1–F4 mutation,
reconciliation, exact-support and single-fault controls were re-executed.
The final MEM-0 replay retains its original v2 semantic digest. Independent
MEM-0 acceptance remains unclaimed. Historical review/remediation files and
baseline fixture bytes were not changed.

One subsequent full-suite attempt failed in the pre-existing provider matrix:
**1,906 passed, 1 failed, 99 deselected**, 262.87 s. The failure was
`test_matrix_uses_generic_profiles_task_contract_and_p21_p19_seams`, reporting
40 synthetic cases instead of 80. No timeout or required check was relaxed.
The final recheck and its exact result are recorded in the checks section below.

Read-only triage found a reproducible clock-mismatch mechanism in unchanged code:
the matrix's `MemoryRepository` test fake fixes `now` at construction, task
deadlines are 30 seconds from that clock, and the runner's `_remaining_seconds`
compares permits against live UTC. A one-fixture diagnostic with identical
profiles/task/output and a fresh clock produced **4 synthetic / 0 failed / 1
blocked**; aging only the fake clock by 31 seconds produced **0 synthetic / 4
failed / 1 blocked**, with `evaluation_provider_outcome_unknown`. This supports
a bounded test-clock explanation, but the original full run did not retain
case-level error receipts, so its exact causal attribution is not certified.
The probe changed no repository files, provider deadlines, or production policy.

## Delivered ownership and changed files

| Area | Files and resulting behavior |
| --- | --- |
| Contracts and source authority | `memory/knowledge.py`, `knowledge_sources.py`, `knowledge_service.py`: schema 3, exact successful-command recipe, authenticated completed-turn decision adapter, bounded UTC evidence, scoped admission/reconciliation and final guarded consumption. |
| Canonical persistence | `memory/knowledge_repository.py`, existing `memory/repositories.py` and `persistence/postgres/memory.py`, new `persistence/postgres/knowledge.py`, migration `028_verified_memory_knowledge.sql`: same repository ownership, scoped uniqueness, complete normalized edges, source tombstones, budgets, retention and reverse erasure. |
| Lifecycle and context | Existing `memory/lifecycle/repositories.py`, `persistence/postgres/lifecycle.py`, `memory/contracts.py`, `services.py`, `dependencies.py`, `inspection.py`, `context/assembler.py`: shared state/event/epoch authority, explicit knowledge query, real shared packing, token cap/expiry/source references and complete later dependency revalidation. |
| Identity and rollback | `settings.py`, `.env.example`, `auth/owner_data.py`, `persistence/postgres/auth.py`: separate disabled admission/selection flags, owner deletion fence checks, new owner inventory and bounded export families. |
| Downstream artifact boundary | `artifacts/service.py`, `tests/test_artifacts.py`: reject every `ai_memory_` dependency before metadata/body reservation, including the new knowledge node. |
| Evaluation | `evaluation/knowledge_runtime.py`, `memory_knowledge.py`, `fixtures/memory/mem1-paired-v1.json`, Makefile: stateful Task A issuance, fresh Task B, finite scoped execution and independent target outcome, four arm labels and honest unsupported legacy counts. |
| Tests | `tests/test_memory_knowledge.py`, `test_memory_knowledge_evaluation.py`, `tests/persistence/test_verified_knowledge_postgres.py`; planner lock compatibility test in `test_planning_experiment.py`. |
| Reproducibility | `evaluation/planning.py`, new `planning-baseline-v17.json`: non-promoting source rebind; all old planner locks, configuration, runtime identity and 30 planner cases preserved. |
| Documentation | Memory/evaluation package READMEs, `experiments/memory/README.md`, `docs/README.md`, `docs/current-state.md`, this report, ADR, entry QA and review handoff. |

Paths in this table are under `backend/src/personal_ai/` unless otherwise stated.
No new provider SDK, dependency, datastore, scheduler, prompt builder, agent-facing
memory tool or public mutation endpoint was added. Existing v1 personal assertions
and v2 `support-v1` contracts retain their own grammar, tables and readers.

## States, source edges and failure semantics

Admission resolves an opaque source using authenticated server scope and current
project registration, validates policy before persistence, obtains a source
lease, resolves again and commits record plus every edge atomically. Candidate
text cannot choose owner, actor, app, workspace, project, grant, authority or
successful outcome. Receipt identity binds issuer, task/run/attempt, exact
command/tool, revision, outcome, times, fingerprint and all source edges.
Transient client context and capability bags are forbidden in retained receipt
scope. No raw tool output, logs, credentials or full execution trace is stored.

The first procedure recipe only supports historical success for three closed
Make commands with fixed revision preconditions/limitations. A valid receipt
does not support arbitrary general claims. A decision resolver requires an
independently registered authenticated confirmation, exact whole user statement,
completed active assistant turn, both message references/fingerprints, actual
turn/time bindings and inherited source policy. Decisions remain `user_asserted`
and `user_confirmed`; procedures are `tool_receipt_verified` and `verified`.
Historical outcome is separate from verification, lifecycle and Task B success.
Expiry is bounded to 30 days from observation.

One to eight normalized edges are required, with exact order/identity checks and
complete reverse indexing. The first slice limits a namespace to 128 records,
1,024 source fences and 16 KiB per JSON record; query overflow fails closed.
A knowledge permission node binds the record and lifecycle validity epoch and
revalidates every edge, current actor/access, project revision and branch. It
does not treat a grant as proof of the claim. Shared dependency fan-in stays
within the existing 16-node limit without dropping edges. The context trace
includes selection/rejection/source metadata; the shared assembler enforces the
query token cap and preserves historical verification/expiry labels.

| Transition | Canonical behavior |
| --- | --- |
| Valid new admission | `created` only after a known canonical commit. |
| Identical retry | `already_exists` returns the original record and does not replace timestamps/vectors/content. |
| Same key, different payload or expected source/lifecycle epoch | `conflict`; no second knowledge record. |
| Missing/forged/failed/partial/unknown receipt, wrong revision/scope, unconfirmed decision, sensitive or unsupported claim | Rejected before storage; assistant and memory-effect success claims confer no authority. |
| Unknown write/acknowledgement | Reconcile the original identity. A current known committed row yields `already_exists`; otherwise `unknown_commit`. No automatic fresh-key resend. Cancellation is not reported as success. |
| Forget/supersede/review | Existing immutable event log and `MemoryLifecycleState` CAS/validity epoch suppress reuse; retries cannot reactivate. Automatic personal-preference jobs do not process schema 3. |
| Source revoke/erasure | Compare source epoch under the same namespace DB lock as admission/use. Erasure traverses all reverse edges and physically deletes dependent knowledge and relations. Tombstones prevent original-epoch resurrection. |
| Expiry | Queries/packing/use deny; bounded retention erases expired payloads and tombstones their source identities. No new worker. |
| Lost permission, owner fence, branch/revision change or missing projection/edge | Selection, packing, final consumption and supported later history/summary reuse fail closed. |

Newer verified runs use new immutable source identities. Tombstoned identities
are not automatically reauthorized. Final consumption takes a source lease and
canonical guard, then revalidates before invoking a trusted host executor. The
executor still owns action authority, a fresh current-state read, idempotency
and reconciliation of external effects. Existing memory-derived artifact writes
remain prohibited. Native tests demonstrate local Postgres serialization, not
Postgres–Dynamo atomicity or a production distributed source lease.

## User journey and rollback

The demonstrated journey is a hermetic repository task, not a new UI. Task A
simulates a successful validation command or confirmed decision, issues an
independently resolvable source receipt and admits durable knowledge. Its session
objects are discarded. Task B creates fresh request/service/retriever/builder
objects, reads current project facts, packs permitted historical advice and
executes a new scoped action with a distinct receipt. Canonical current settings
override an older decision. Invalid historical procedures cause fresh discovery
or safe abstention, rather than unverified reuse.

`MEMORY_KNOWLEDGE_ADMISSION_ENABLED=false` and
`MEMORY_KNOWLEDGE_SELECTION_ENABLED=false` require the parent memory gate.
Disabling selection invalidates already selected/packed dependencies immediately
and restores only the legacy path without deleting v3 data. `fixed` remains the
old default. Application composition installs no procedure issuer; production
intake is unsupported even if flags are changed. The completed-turn adapter also
needs a trusted confirmation host and recoverable source lease. No automatic
production promotion or destructive down migration is provided.

## Paired benchmark results and identities

The immutable `mem1-paired-v1` corpus has **20** author-reviewed cases: 4 workflow,
3 project decision, 3 currentness, 6 scope/lifecycle and 4 adversarial/non-beneficial.
Six carry a holdout tag. Independent case review remains pending; the tag does
not establish a blind model study. Task B receives no rubric, fault, split or
gold fields. Single-fault positive twins and reversed/duplicate/forged trace
mutations are tested separately and do not inflate the corpus denominator.

All evaluated arms share Task A formation and trusted tool state; the no-memory
arm disables historical reuse. Eligible history is typed diagnostic source
history, not an untouched transcript. Each has identical canonical current
facts, scope, tool authority, clock `2026-10-29T12:00:00Z`, seed 17, 4,096 total
budget and 1,024 history cap. A historical receipt cannot count as target success.

| Arm | Tasks | Unsupported | Newly successful actions | Retrieved / packed / used | Rediscoveries | Tool calls | Estimated token units |
| --- | --- | --- | --- | --- | --- | --- | --- |
| none | 19/20 | 0 | 18 | 0 / 0 / 0 | 16 | 74 | 340 |
| legacy fixed | 0/0 | 20 | Not measured | Not measured | Not measured | Not measured | Not measured |
| mem1_verified_knowledge | 20/20 | 0 | 19 | 8 / 7 / 5 | 12 | 72 | 1,076 |
| full_eligible_history | 20/20 | 0 | 19 | 8 / 7 / 5 | 12 | 72 | 552 |

The safe unconfirmed-decision abstention is one passed task with no target action.
The positive confirmed decision accounts for the one no-memory task miss. The
paired knowledge-versus-none comparison therefore has one win and 19 ties, no
task regression, on 20 synthetic cases; this is not a real-agent lift estimate.
Admission false positives are **0/4** negative sources and false negatives **0/16**
eligible sources in each evaluated arm. Safety invariant failures are **0/60**
executed arm/case rows; the 20 fixed rows are unsupported, not successes.
The target effect count is at most one per task, including idempotent retries.

All evaluated arms serialize 37,452 knowledge JSON bytes and retain 45 normalized
edges across their independent cases after erasure; common formation means this
comparison establishes no storage savings. These are JSON sizes, excluding
native tuple/index/tombstone overhead. Token units use the deterministic fake
counter and are estimates. Fake-runtime summed latency was approximately
111 ms none, 123 ms knowledge and 128 ms history in the final replay; these
single observations are not provider latency or performance-confidence estimates.
Native resource, live provider and model-mediated metrics remain unverified.

| Identity | Value |
| --- | --- |
| MEM-1 fixture SHA256 | `587e87f11422719e8ad2f512ede7020c0bae937cb555b1035cd8eb386866756e` |
| MEM-1 semantic digest and second replay | `7787f8be9434f078fd257af4a35045e5e3ac0cde39e9d2af34118117edd26d92` |
| MEM-1 source SHA256 (Python, migrations, dependency locks) | `be1f73d94dc8de0ab5cb8ee9e888836412138c47d071a5a41b05ef096b703ae1` |
| MEM-0 v2 fixture SHA256 | `592a0e3799aeafc32ebf7cba0c7e162ff0af98d0049af2cf683de653e5fc02e1` |
| Preserved MEM-0 v2 semantic digest | `f961fd6335397f3efb6ccacc8f6ac9b4a357d949a1671426399014c6dc470f28` |
| Final MEM-0 backend source SHA256 | `3fbc2f227d7e2d9e64c0a97669ce8c08705725563bfc01eb28b559f16f4301a3` |
| Non-promoting planner v17 source identity | `5c41328e73780ed234786354dfc15fa14d56e86b34bd37d1a36b8f1e77f37375` |

Generated manifests/results remain ignored under `artifacts/mem0/` and
`artifacts/mem1/`; each records the actual tested base and dirty status. Replays
reject fixture/source mutation during execution. MEM-0 v1/v2 bytes and results
are preserved. Its proxy remains none 19/30, fixed 22/22 with eight unsupported,
history 29/29 with one truncation, gold 30/30; three fixed wins on 22 paired cases.
Planner v17 changes only the source freeze and preserves strict current-or-direct-child
revision binding, deterministic behavior, all old locks and non-promotion.

## Commands, results and remaining checks

All root commands used `PATH="$PWD/backend/.venv/bin:$PATH"`. Native tests used
PostgreSQL **17.11** and pgvector **0.8.7**, a newly initialized temporary local
cluster on loopback port 55439 and synthetic isolated databases. The sandbox's
shared-memory/network restrictions required approved local test escalation.
No external database or personal data was used.

| Command | Result / receipt |
| --- | --- |
| `python -m pytest backend/tests/test_memory_knowledge.py backend/tests/test_memory_knowledge_evaluation.py -q` | **72 passed**, 2 warnings, 2.94 s; `/tmp/mem1-focused-final.log`. |
| `python -m pytest backend/tests/test_mem0_task_baseline.py backend/tests/test_memory*.py backend/tests/test_postgres*.py backend/tests/test_planning_experiment.py backend/tests/test_artifacts.py -q` | **484 passed**, 3 warnings, 14.40 s; `/tmp/mem1-regression-final.log`. |
| `make memory-task-eval memory-eval memory-lifecycle-eval memory-optimization-eval planning-eval memory-knowledge-eval` | **passed**, all six targets exited 0, active MEM-0 v2 and MEM-1 semantic replays matched, planner non-promotion; `/tmp/mem1-evaluations-stable.log`. |
| `make backend-lint` | **passed**, Ruff “All checks passed!”; `/tmp/mem1-lint-final.log`. |
| Native command below | **32 passed, 8 skipped**, 2 warnings, 7.21 s; `/tmp/mem1-native-regression-final.log`. The eight skips require unavailable DynamoDB. Nine new schema-3 tests passed. |
| First MEM-1 `make backend-test-offline` | **failed**, 1,906 passed / 1 failed / 99 deselected; provider-matrix failure described above. This is not converted into a pass by retries. |
| Serial `PYTEST_ADDOPTS='--durations=5' make backend-test-offline` before final artifact guard | **1,909 passed, 99 deselected**, 4 warnings, 176.85 s; `/tmp/mem1-offline-recheck.log`. Provider-matrix test took 19.44 s. This clean rerun does not erase the earlier failed attempt. |
| Final `PYTEST_ADDOPTS='--durations=5' make backend-test-offline` | **1,911 passed, 99 deselected**, 4 warnings, 207.56 s; `/tmp/mem1-offline-stable.log`. Provider-matrix test took 19.83 s. No timeout changes or exclusions beyond the supported target. |
| `git diff --check` and local documentation/fixture/migration consistency | **passed**; 71 local documentation links resolve, 28 migrations have unique ordered numbers, latest is 028, and v1/v2 fixtures, prior migration 027, historical lock v16 and historical MEM-0 evidence have no diff. |

Native invocation (the DSN is synthetic local test configuration):

```sh
PERSISTENCE_TEST_POSTGRES_DSN='postgresql://mem1_test@127.0.0.1:55439/mem1_test' \
  python -m pytest \
  backend/tests/persistence/test_verified_knowledge_postgres.py \
  backend/tests/persistence/test_local_persistence.py \
  backend/tests/persistence/test_memory_lifecycle_projection.py \
  backend/tests/persistence/test_account_export.py -q
```

Native checks cover forward 027→028 migration/reapply, pgvector availability,
legacy memory regression, fresh-session new outcome, disabled selection,
concurrent admission and source CAS, forgotten-record retry, complete reverse
erasure, partial-insert rollback, lost commit acknowledgement, owner deletion
fence, expiry erasure and missing edge/projection denial. Offline checks add
forged assistant/receipt/command/outcome, unsupported claim, source/actor/app/
workspace isolation, branch/revision changes, after-selection and after-pack
revoke, supersession, cancellation, final-use serialization, source/DB outage,
storage/candidate/deadline/token budgets, metadata minimization and malformed
action probes. V1/v2 compatibility remains covered by the old memory/native suites.

Intermediate implementation runs exposed a new small-budget packing omission
(fixed in the shared assembler) and a constructor compatibility issue for
job-only fake lifecycle repositories (fixed without changing their contract).
An expanded intermediate run also hit an existing mocked disclosure timeout;
the final expanded command passed. Initial source-overlap replay attempts were
not accepted as stable replay evidence. No test or timeout was weakened.

## Remaining acceptance and next steps

1. Independent MEM-0 sign-off, independent MEM-1 implementation review and
   independent hand review of all paired cases remain separate obligations.
2. Resolve or independently disposition the recurring full-suite provider-matrix
   test-clock issue. The final run's status does not erase earlier failures.
3. Production workflow admission has no trustworthy installed issuer. Any future
   host needs recoverable source leases, current application/project membership,
   authenticated confirmation registration and wired erasure/revocation callbacks.
   An in-process fake is not that authority.
4. Source erasure/retention APIs, normalized reverse deletion and owner fences
   were exercised locally. Actual deployed source deletion, account deletion
   orchestration, DynamoDB, cloud recovery/retention, deployed identity and
   real provider behavior remain external gates inherited from Phase 36.
5. Real-agent task lift, a blind model study, native resource/cost estimates and
   production promotion are unverified. Keep both new flags and inherited
   rollout gates off. Nothing here authorizes promotion.

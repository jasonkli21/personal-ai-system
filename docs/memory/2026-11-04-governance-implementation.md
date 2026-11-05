# Memory governance implementation and independent review handoff — 2026-11-04

Status: **IMPLEMENTED_E1_GOVERNANCE / PHASE_EXIT_BLOCKED / PRODUCTION_NO_GO**.
Author implementation evidence only; independent acceptance is pending. The
owner requested implementation and one commit in this session, with no subagents.
The supplied prompt/plan are implementation inputs, not authority for live data,
provider sends, cloud, deployment or release. None was used.

Entry is `b694c5f26e0c5fc21880bac06f1fdf2eac5ca650`, tree
`d1f6dbd80202ca8f7ab2136a7a657ea15087f3da`, branch `main`. The candidate is the
single commit containing this report; resolve it with `git log -1 --format='%H %T'`
at the delivered revision. Exact changed-file inventory and source hashes are in
[verification](2026-11-04-governance-verification.json). Ten pre-existing
untracked planning documents remain excluded and unchanged. This report does not
claim a clean working tree when those files are present.

## Architecture and scope

[ADR 0027](../decisions/0027-memory-governance-overlay.md) and the
[pre-edit readiness audit](2026-11-04-governance-readiness.md) choose a memory-specific
capability overlay over profile consent reuse or a general identity service.
Canonical knowledge, lifecycle, source rights and context assembly retain their
ownership. The overlay stores references and content-free decisions, never a
second durable copy of source content.

`memory/governance/contracts.py` closes schema/policy fields and bounds identity,
scope, epochs, original IDs, expiry, quotas and typed store receipts.
`policy.py` intersects verified public canonical source state, exact registered
recipient app/project/workspace/agent, owner/source/target epochs and current
lifetime. `service.py` provides atomic host/repository protocols and CAS/replay,
replacement/revoke and new-generation regrant semantics. Same-key reconciliation
cannot reapply old authority. A stale restored ledger cannot perform reads **or
mutations** against a newer separately surviving anchor.

The trust boundary is explicit: `ShareIntent` is untrusted requested data.
Its destination labels and decision-proof reference do not establish identity,
consent or registration. Only the installed host dependency could provide those;
none is installed. `HostState` is a Python server observation, never a wire
request. The test adapter registers exact request objects, independently verifies
host-held decision fingerprints and resolves canonical `KnowledgeService` records.
Matching serialized scope, UUID, email, manifest or model text grants nothing.
This is host API discipline, not a sandbox against arbitrary hostile Python code.

`operations.py` provides finite work admission, host-private preview helpers,
a twelve-store acyclic erasure dependency inventory and inert canary/rollback
proposals. Accepted grants reserve permanent revoke capacity; quota exhaustion
never evicts safety receipts. Logical suppression is separate from physical purge.
Episode/research inventory, backups and external copies remain unverified.
Knowledge/episode export and applied imports remain unavailable.

`evaluation/governance_simulator.py` is the only authority/store adapter. Its
source/lifecycle locks and canonical context builder cover selection, packing,
late token-count revocation and a final guarded internal predicate consumer.
That consumer has no callback/dispatcher/transport. `observe(external=True)`
always denies. Crash-after-commit/lost-ACK, duplicate first submissions, concurrent
CAS, target/source mutations, stale grant and lifecycle snapshots, delayed jobs,
disk/DB unavailability and safety-capacity limits are synthetic fault models.
They do not establish native persistence, Dynamo work or physical send behavior.

A native adapter/migration is deliberately absent: no approved DSN, independently
surviving authority or deployed grant-erasure integration exists. The protocol
requires canonical owner-deletion exclusion and original-key continuity; the
synthetic adapter cannot certify them on a real database. Exact reentry tests
and responsible owners are in the [blocker ledger](2026-11-04-governance-blockers.json).
No E1 work is deferred for missing external infrastructure.

## Evaluation and verification

The additive author-visible `memory_governance_cases_v1.json` has **69 cases in
six families**, including eight distinct canonical source positive/negative
cross-agent/project pairs, two owners with actual records sharing a store, and
more than eight multi-step temporal mutations. Every attempted row remains in the
report, including denied, failed, incomplete, cancelled, unavailable, uncertain
and unsupported observations. The expected failed-maintenance and unsupported
native rows are boundary observations, never successful native operations or
zero-valued utility scores. All 69 expected boundary outcomes match.

Two fresh process outputs and two fresh verification/replay processes are stored
as [run A](governance/2026-11-04/run-a.json) and
[run B](governance/2026-11-04/run-b.json), with exact byte hashes, a shared semantic
digest, complete receipts and observed E1 timings/resource estimates in the
verification receipt. Timing, local representation-size estimates and environment
are separated from semantic equality. Actual native DB latency/storage, model
tokens, billed cost, idle burn and cloud egress remain unknown. A correctness
campaign cannot show that sharing improves answers. The corrected longitudinal
primary remains **0 pp over 25 eligible pairs**; no independent model lift exists.

The common governance semantic SHA-256 is
`70cb0afbab59e055c6da9163a9e418ac79fb770b055ab87e4a2a76b4759021c3`.
Observed per-case runtime includes synthetic source setup/admission and the case
operations; it excludes report hashing/output. It is local E1 wall time only.

| Run | Output SHA-256 | Median ms | Nearest-rank p95 ms |
| --- | --- | ---: | ---: |
| A | `86ddfc67aebe6247ca3fad9fb8af6c8052461813ca0fcc21afe14360a455cc90` | 6.369 | 13.005 |
| B | `7aec7f6bb386f4b892ad58521f30a7dbdf98e651c725bef234a751b5af7ae824` | 6.413 | 13.429 |

The maximum ledger representation estimate is 3,191 bytes in this campaign;
this is neither RSS nor native disk usage. Per-case grant, original-key,
tombstone and source-dependency slot counts are in each run's observations.
No capacity SLO, native concurrency, actual token or billing claim follows.

The first research checks correctly rejected new governance modules in their
recursive dependency inventory (`study_source_changed_requires_new_generation`).
An additive **source-lock v4** and active anchor now preserve v1–v3 and add the
new module/source identities. The old corpus, scorer, protocol, support matrix,
thresholds and decisions are unchanged. Fresh research tests and the 3,528-row
evaluation pass with the same historical semantic result and blocked decision.
This is fresh author evidence, not independent signoff or a rebind of old runs.

Fresh-process file replay also caught a tuple/list comparison defect in the new
campaign. Semantic comparison now canonicalizes the JSON wire representation;
a JSON round-trip regression and both independent process replays pass. Earlier
failed command observations are retained in the verification receipt.

The exact commands, exit codes, counts and failure inventories are machine
readable in verification. Focused governance, adjacent network-fenced safety,
research, navigation, consolidation, lint and naming checks are green. The full
offline command is attempted and reported separately; frozen planning/PI-6 and
sandbox socket failures are not waived or relabeled as passing. Native/provider,
cloud, backup and physical-send checks were not run.

| Verification command | Exit | Observed result |
| --- | ---: | --- |
| `make memory-governance-check` | 0 | 101 tests passed |
| Two `make memory-governance-eval --output` equivalents via `GOVERNANCE_FLAGS` | 0 each | 69/69 expected boundary outcomes in each fresh process |
| Two `make memory-governance-eval --verify` equivalents via `GOVERNANCE_FLAGS` | 0 each | Matching semantic replay and source identities |
| Python network-fenced adjacent suite (exact nine-file command in receipt) | 0 | 327 passed; zero network attempts |
| `make memory-task-eval memory-knowledge-eval memory-control-eval` (separate invocations) | 0 each | Existing evaluations passed; historical inputs unchanged |
| `make memory-navigation-check memory-navigation-eval` | 0 each | 57 focused tests; evaluation passed |
| `make memory-consolidation-check memory-consolidation-eval` | 0 each | 107 focused tests; evaluation passed |
| `make memory-research-check memory-research-eval` | 0 | 111 tests; 3,528 retained rows; blocked decision and unchanged utility semantic digest |
| `make backend-lint naming-policy-check` | 0 | Ruff and naming policy; two policy tests |
| `make planning-eval` | 2 | Preserved `planning_baseline_changed_requires_new_version` |
| `make backend-test-offline` on final stable source | 2 | 2,853 passed, 36 failed, 92 errors, one skipped, 180 deselected |
| Local Markdown links; `git diff --check` | 0 | All changed-document local links resolve; whitespace clean |

The final broad run collected 3,162 tests and recorded unchanged source hashes
across the entire command. Its failing IDs are only existing PI-6/planning tests;
its errors are existing socket-dependent fixtures denied by the sandbox. The
receipt preserves every unsuccessful test ID. Earlier development runs are
separate: one ran across corpus edits and had two governance failures plus frozen
research-generation errors. These do not substitute for the final stable run.
Provider/emulator/cloud/native checks remain NOT_RUN/BLOCKED, not inferred from
any Python fake.

## Acceptance matrix for G01–G27

PASS below means only the stated author E0/E1 target. It does not close a higher
tier or constitute independent acceptance. The environment is the local Python
virtual environment; responsibility for every PASS is the author pending reviewer
reproduction. External blocked rows belong to the owners named in the ledger.
`tests` means `backend/tests/test_memory_governance.py`; `runs` means the two
committed JSON reports; `receipt` means the dated verification JSON above.

| ID | Status | Tier | Exact evidence / boundary |
| --- | --- | --- | --- |
| G01 | PASS | E0 | Readiness audit, entry tree/status and receipt file inventory |
| G02 | PASS | E0/E1 | Registration/default assertions in tests; unchanged settings/routes; disabled episode case |
| G03 | PASS | E1 | Forged/copied host request, missing host, unapproved proof and two-owner tests |
| G04 | PASS | E1 | Eight source-paired agent/project/app/workspace/owner scope controls in runs |
| G05 | PASS | E1 | Wildcard, purpose/ceiling escalation, wrong-purpose-read and schema tests |
| G06 | PASS | E1 | Sensitive, unverified, unknown-origin, expiry/source-revision and canonical admission injection cases |
| G07 | PASS | E1 | Concurrent first-submit/CAS, same-key body conflict, lost ACK and replay tests; no native durability claim |
| G08 | PASS | E1 | Source/target/owner epoch, canonical lifecycle and source-revoke tests |
| G09 | PASS | E1 | Revoke before selection/pack/consume and source change during actual token count |
| G10 | PASS | E1 | New ID/generation ABA, expired grant, registry epoch and replacement suppression tests |
| G11 | PASS | E1 | Correction/source version controls, fabricated canonical identity rejection |
| G12 | PASS | E1 model | Canonical forget, source/lifecycle snapshot restore, twelve-store dependency/suppression inventory; physical work unknown |
| G13 | PASS | E1 | Episode capture/read disabled with both constructor options true; preview denies export |
| G14 | PASS | E1 | Inert export preview, imported-host rejection and unchanged owner portability tests |
| G15 | PASS | E1 | Old ledger/forget/lifecycle restore with separately retained fixture epochs/anchor; native survival blocked |
| G16 | PASS | E1 | Lost ACK, duplicate/CAS workers, storage unavailability and external-send denial; native send reconciliation blocked |
| G17 | PASS | E1 | Grant/fence exhaustion retains tombstones and reserved permanent revoke keys |
| G18 | PASS | E0/E1 | Finite retained ledger and WorkRequest page/fan-out/index/job/retry/export ceilings; no real index/jobs |
| G19 | PASS | E0/E1 inventory | Twelve typed per-store topology/dependency statuses; no physical purge asserted |
| G20 | PASS | E1 | Injected canonical source, forged schema/host/import and exact fixture registration |
| G21 | PASS | E1 | 69 attempted rows, six families, full source inventory and retained noncompletion outcomes |
| G22 | PASS | E1 | Two fresh runs/replays, JSON round-trip, source drift and report-tamper negatives |
| G23 | PASS | E1 | Pure plans; write/socket/process/store hooks forbidden and state unchanged; unsafe plan rejected |
| G24 | PASS | E0 accounting | Receipt retains exact successful/failed commands and unchanged frozen evidence |
| G25 | BLOCKED | E2–E4 | No native actor/send/physical-erase/cold-restore proof; see blocker ledger |
| G26 | BLOCKED | E5 | No independent real multi-agent utility or measured native economics |
| G27 | BLOCKED | E3–E5 release | Phase 36, applicable PI/MEM/HXE gates, owner release and independent review remain open |

## Self-contained independent Sol High review handoff

Review the single commit containing this report against the entry SHA above.
Pin its commit/tree and verify the retained dirty/untracked inventory; do not
trust report labels as authorization. Inspect the exact file list and hashes in
the receipt, ADR, closed contracts, policy/service seam, operational model,
synthetic authority, full corpus and tests. Challenge identity scope intersection,
original-key binding, auto-replacement suppression, revoke/regrant ABA, source
freshness, correction, canonical forget, host recovery anchor and physical-send
denial. Try forged constructed Pydantic objects, copied request envelopes,
JSON-held authority, stale lifecycle/index/ledger state and source change during
packing. Confirm each participating store and graph edge has only the claimed
topology-specific observation.

All memory enablement flags remain false; `fixed` remains the experiment default.
Episodes remain hard-disabled even with constructor options, consolidation is
pending-only, no research grants runtime authority and profile-only export/import
preview is unchanged. There is no new setting, migration, route, API, exposed
tool, registered issuer or dispatcher. Inspect the pure planner and negative
side-effect tests, and reproduce the network-fenced suite. No actual external
send was made or is supported by this seam.

Replay both committed reports with the exact commands in the
[operator runbook](2026-11-04-governance-operator-drills.md). Compare their source
maps, semantic digests, all 69 rows and observations to independently generated
outputs. Check fresh research v4 source custody, while confirming v1–v3 and
frozen planning/PI-6 baselines are byte-preserved. Preserve MEM-6's corrected
0 pp limitation. Do not promote unsupported native rows into acceptance.

Provide ranked reproducible findings with exact file/line references, impact,
minimal fixes and negative regression tests. Independently separate code defects
from external dependencies: approved native infrastructure, real host/recipient
and source authority, physical send protocol, backup/erasure/restore authority,
actual model/task/resources/cost evidence and release signoff. Full phase exit
and every production profile must remain blocked without those exact proofs.

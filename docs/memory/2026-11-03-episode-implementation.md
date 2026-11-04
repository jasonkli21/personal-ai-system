# MEM-3 bounded component implementation and reviewer handoff

The structural-only implementation boundary below is superseded by the
[authorized local extension](2026-11-03-episode-extension.md). Historical checks
and findings remain as originally recorded.

Date: 2026-11-03, America/Los_Angeles. Entry revision:
`42f00b0f93b0987f615657d4d8b9c145c6c6b016` (exact planning baseline).
Delivery commit is the single commit containing this report; obtain its immutable
identity from `git log -1 --format=%H` in the delivered checkout. A commit cannot
embed its own hash. No push, deployment, private source or provider call.

**Outcome: PARTIAL, full MEM-3 blocked; production NO_GO.** The completed
component validates structural receipt consistency only. It does not satisfy
the requested capture/search/forget vertical-slice exit. This is the prompt's
smaller-component fallback, not phase completion. The
[hardening decision](2026-11-03-episode-plan-hardening.md) was written before
implementation. It records the explicit development unfreeze, authority gaps,
accepted/rejected designs, crash requirements and rollback. No subagents used.

## File map and behavior

| Path | Change |
| --- | --- |
| `backend/src/personal_ai/memory/episodes.py` | Versioned minimal receipt envelope, metadata candidate, uniform assessment and pure validator |
| `backend/src/personal_ai/evaluation/episode_candidates.py` | Additive frozen-corpus structural driver/scorer; expected outcomes never passed to validator |
| `backend/src/personal_ai/evaluation/fixtures/memory/terminal-step-candidates-v1.json` | 38 preregistered scenarios; 29 development, 9 reserved, all author-visible |
| `backend/tests/test_episode_candidates.py` | 77 consistency, privacy, bounds and negative tests, including explicit consistent forgery counterexample |
| `Makefile` | `memory-episode-candidate-check` and `memory-episode-candidate-eval` |
| Memory/workflow READMEs and docs router/current state | Usage and precise implementation boundary |
| This report, hardening note, `episode-development-blockers.json` | Evidence, decisions, gate ledger and handoff |

The validator requires an original RunSpec and minimal receipt envelope as bounded
JSON bytes. It recomputes scoped intent, exact original key, canonical step digest,
source binding, registered tool/version/effect and exact topological attempt order.
Only succeeded runs with all succeeded attempts and no cancellation qualify.
It rejects missing legacy fingerprints, failed/reserved/dispatched/abandoned/
uncertain attempts and incomplete or duplicated evidence. No trace is reconstructed
from the eight-event tail. No completion time is inferred from the run deadline.

Same inputs yield the same opaque candidate IDs; changed valid lineage yields a
new candidate ID. This is deterministic projection, **not durable idempotency**.
No original-key write, receipt or transaction occurs. Changed original plans fail
binding checks. Source/forget replay safety and commit ambiguity are unavailable.
The output contains only UUIDs, fingerprints, bounded ordinals and closed labels;
no query, step name, response, arbitrary summary, path, prompt, log or reasoning.
It states handler-result observation, no independent verification, unavailable
completion time and structural-inspection-only use. Hash consistency does not
prove authenticity, synthetic/public classification or task correctness.

Migration compatibility: no SQL or persisted identity changes. No episode table,
source edge, cache, export family or lifecycle state is introduced. Existing
schema-1/2/3 readers, flags and fixed retrieval remain unchanged. No new runtime
flags; no capture or selection registration; no API/model tool or context path.
Thus there is no enabled episode feature to roll back by setting a boolean.

## Verification

Interpreter: Python 3.11.15; Pydantic 2.13.5; pytest 8.4.2 on macOS arm64.
Commands run from repository root with `PATH="$PWD/backend/.venv/bin:$PATH"`
unless a full interpreter path is shown. Source was entry HEAD plus this patch.

| Exact command | Result and limits |
| --- | --- |
| `make memory-episode-candidate-check` | PASS: 77 tests |
| `make memory-episode-candidate-eval` | PASS: 38/38; 3 supported, 35 denied; 0 false structural support; max candidate 845 bytes |
| `make backend-lint` | PASS: Ruff |
| `make naming-policy-check` | PASS: checker and 2 unit tests |
| `make workflow-check` | PASS: 70 tests |
| `make memory-task-eval` | PASS: preserved 30-case baseline, replay_equal true; synthetic only |
| `make memory-knowledge-eval` | PASS: preserved 20-case stateful proxy; no invariant failures |
| `make memory-knowledge-causal-eval` | PASS: preserved 16-pair deterministic consumer; no model utility claim |
| `make memory-control-eval` | PASS: existing control proxy |
| `make memory-eval` | PASS: existing memory fixture evaluation |
| `/usr/bin/sandbox-exec -p '(version 1)(allow default)(deny network*)' backend/.venv/bin/python backend/scripts/offline_test_runner.py -q backend/tests/test_episode_candidates.py backend/tests/test_workflow_contract.py` | PASS: 93 tests, zero forbidden Python network attempts; native OS network-denial policy applied |
| `make workflow-postgres-check` | BLOCKED before pytest: `PERSISTENCE_TEST_POSTGRES_DSN` unset; zero native DB tests |
| `make provider-isolation-check` | Initial sandbox attempt BLOCKED at local Unix probe bind; native harness rerun: **FAIL, 845 passed / 1 failed**, 141.24 seconds, native IPv4/IPv6/Unix denial PASS, zero forbidden Python attempts |
| `make backend-test-offline` | NOT RUN: broad API/distributed/installed cases exceed this pure component's verification scope; no broad-suite green claim |
| `git diff --check` and local Markdown link validation | PASS at final review |

The first focused run had 76 passed/1 failed: the test tried to construct a
valid query containing a NUL, which the existing query contract correctly rejects.
The test's valid-query poison case now uses Unicode without the prohibited control
character; malformed byte inputs and unknown nested fields separately test denial.
No production contract or existing test was relaxed.

The broader native provider-isolation failure is
`test_current_planning_lock_binds_owner_portability_source_without_promoting`:
lock v35 expects source digest
`4eb58162ae39387382c18b524017886c1be4e4fc27de5203ac064f5c6e889cc9`;
the added source files produce
`7871493e6f968e4e6f5bbd701a1959167b4f17540ce7d5b78a13e9d807e6e0c7`.
The source scanner includes new package files and READMEs automatically. This is
a **change-induced release identity mismatch**, not an inherited baseline failure
or a network violation. It is left visible: no historical lock, assertion, scorer
or threshold is overwritten. A reviewed additive planning/source-generation
migration and dependent manifest regeneration remain blocked follow-up work
before release gate acceptance. This delivery does not claim a green broad gate. An evaluator empty-candidate
`max` bug was corrected before reporting its score. Full offline historical
restore/provider matrix failures were not rerun and are not declared fixed.

New corpus SHA-256:
`a3caf35b5b59b20e9e932a87fa1a1cb1719036a15ccf077e1cc04eedae459e77`.
Frozen before scoring; 9 reserved cases are author-visible, not blind. Human
independent hand-review remains pending. Original MEM-0/1/2, PI-6 corpora, source
locks, scorer thresholds and historical nonpromotion files are untouched.
Old comparator evaluations were rerun separately; **no matched episode vs
no-memory/fixed/full-history/knowledge/controls causal experiment was run**.
The candidate has no lookup consumer, so capture precision, lookup quality,
task rubric, context tokens and model utility are explicitly unavailable.
Observed per-case wall times in evaluator output include validation and Python
allocation, not DB lookup or provider latency. No runtime storage, index or query
exists; durable episode bytes and provider calls are zero, not erasure proof.

## Security matrix and gates

| Case family | Executed outcome / remaining gate |
| --- | --- |
| Exact single, dependent and independent successful steps | Structural metadata projection succeeds |
| Changed original key, query, dependency, source/scope/step binding | Uniform unsupported, empty candidates |
| Reserved/dispatched/failed/abandoned/uncertain; canceled runs; missing/duplicate/reversed attempts | Denied; no task-success promotion |
| Injected authority/hidden reasoning/nested metadata/base64 payload fields | Denied by closed schemas |
| Poison/secret/path/URL text inside otherwise valid original query | Never copied to output; structural consistency can still pass, expressly not source approval |
| Consistently fabricated evidence | **Can pass**; explicit counterexample test prevents this limitation being hidden. No issuer or authority claim |
| Repeated assessment and bounds | Deterministic, no writes, <=8 candidates and <=2 KiB per record |
| Foreign owner/app/workspace/project/actor/null actor/client ID guesses | BLOCKED: no authenticated lookup or ID-fetch service exists; digest mismatch tests are not authorization proof |
| Source revoke/expiry/branch correction at capture/search/fetch/disclosure | BLOCKED: no source lease or lifecycle-connected episode service |
| Forget/account erase/retention/purge; stale restore and caches | BLOCKED: no episode persistence or erasure path; physical deletion unverified |
| Before/after commit crash, lost ACK, two-worker SQL contention | NOT RUN: no new transaction; native canonical workflow tests blocked |
| Default-off compatibility | No runtime hook or flags added; old workflow and memory evaluations pass |
| Partial/unsupported lookup semantics | No lookup installed; unsupported structural input returns no candidate |

E0: typed structural boundary implemented. E1: consistency component verified;
full memory vertical slice incomplete. Native OS fence execution is not E2
installed-system or model utility evidence. E2/E3/E4/E5: NOT RUN/BLOCKED.
Independent acceptance: pending. Production: NO_GO. Existing workflow native
remediation, MEM-0/1/2 independent review, issuer/lease, physical-send fence,
retained-key capacity and backup/replica/restore gates remain open. See the
[blocker ledger](episode-development-blockers.json) for concrete missing work.

Rollback requires removing use of this pure validator only; leave canonical
workflow original keys, memory source fences, lifecycle events and tombstones
intact. No destructive down migration. Do not promote a restored store without
reconciling original/revocation/forget authority.

Independent reviewer: inspect the exact delivered commit, the original attached
prompt and owner-owned detailed plan, then this decision, validator, corpus and
77 tests. Reproduce the two new Make targets, lint/naming/workflow and native
fence command above. Challenge whether the candidate component warrants its
existence, whether any consumer could mistake fingerprints for permission, and
whether original submission provenance and canonical memory lifecycle can be
joined without fabricating authority. No end-to-end acceptance is requested for
this partial component. A separately trusted capture/lifecycle adapter is the
next blocking design seam, not MEM-4.

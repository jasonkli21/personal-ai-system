# MEM-0 baseline report: v1 history and v2 review remediation

## Latest status: review remediation (2026-10-29)

The independent review at `mem-0-independent-review.md` found four actionable
gaps. The bounded remediation is implemented in the current v2 harness; the
original v1 corpus and its results below remain immutable historical evidence.
The latest commands and dispositions are recorded in the separate
[`mem-0-review-remediation.md`](mem-0-review-remediation.md). Fresh independent
verification is still required before this can be accepted as an MEM-1 planning
baseline.

The active fixture is `mem0-cases-v2.json` (SHA256
`592a0e3799aeafc32ebf7cba0c7e162ff0af98d0049af2cf683de653e5fc02e1`); v1 remains
`mem0-cases-v1.json` (SHA256
`043edaae3461286b49bcb4fda4f73bdc5059e528361bad3fa670a3b1c4e58b18`). A
deterministic `make memory-task-eval` replay passed on base revision
`987bba5f6479791b54ac626d9959b1b39e23fbb3` with a dirty source tree. The v2
semantic result digest is
`f961fd6335397f3efb6ccacc8f6ac9b4a357d949a1671426399014c6dc470f28`; source
SHA256 is `23fcf288ff995adc98d728bedd5dd1c8c67c96aab65f1ea49c2cd621b8084f2f`.
The active planner freeze is v16 with source identity
`fc73dc999e509cc493a511987dcbfb8cbd30cb6d1e0c1c0c86c96a06c1288ac7`; v15 is
retained as historical evidence. V16 preserves its predecessor's corpus,
configuration, fixture/runtime identities, non-promotion, and strict
current-or-direct-child source guard.

V2 task-proxy results are none 19/30, fixed 22/22 with eight unsupported cases,
full eligible history 29/29 with one truncated case, and gold-authorized 30/30.
On the 22 paired fixed-versus-none cases, fixed has three wins, 19 ties and no
regressions. This remains a curated finite scripted proxy, not model task
quality. The focused MEM-0/memory test command passed 281 tests. Existing memory
evaluations, planning evaluation and backend lint passed. The required full
offline suite did **not** pass: 1,833 passed, three provider-matrix tests failed,
and 90 were deselected. All three failures passed when rerun together in
isolation, but this does not establish a clean full-suite result or prove a
root cause. See the remediation report for exact names and commands.

Production `Memory` schema 1, `DerivedMemory` schema 2, support policy, migrations
and default-off flags are unchanged. Model quality, native resource use,
provider quota, deployed identity/grants, cloud behavior and physical deletion
remain unverified. The full suite failure and fresh independent review are open
gates.

## Historical v1 baseline and implementation handoff

The sections below preserve the v1 baseline report and its original evidence.
They are not the active v2 acceptance record.

Date: 2026-10-29 (America/Los_Angeles). Inspected base and pre-commit tested
revision: `ad7c5004294b34df6acffd154509a402e2626659` plus the implementation patch
identified below. The implementation is committed as one direct child; this
report's source identity avoids a self-referential commit hash. The manifest also
records the actual HEAD on every subsequent replay. The working tree was dirty,
including pre-existing untracked planning/review documents, which were preserved.

MEM-0 implements a reproducible **synthetic component and scripted-task baseline**.
It does not demonstrate model-mediated task improvement. Implementation is complete;
offline verification is recorded below. Readiness for MEM-1 planning requires the
separate independent review. No production promotion, migrations or MEM-1 writes.

## Reproduction and identity

From the repository root, put `backend/.venv/bin` on PATH, then run
`make memory-task-eval`. Output is ignored root `artifacts/mem0/manifest.json`,
`cases.json`, `aggregate.json`, and `timings.json`. No network, provider dispatch,
credentials or native stores are needed. The command executes the corpus twice,
checks identical semantic results and unchanged source/fixtures, and exits nonzero
on schema/replay/invariant failures. A lower task score is an experimental result.

- Fixture SHA256: `043edaae3461286b49bcb4fda4f73bdc5059e528361bad3fa670a3b1c4e58b18`.
- Python/config source SHA256: `87d7262fed14622512200bc923524f4c2c0efa392ac75d74632b83622046ed8d`.
- Case schema SHA256: `e52c4b6ffe220e4ad2c7156c143c1469c1398ff39f613b6e86ebf95e560934fc`.
- Semantic result SHA256: `955619e6cc964fb9a3f470b634499a1f9f9599784d7a895d9b7aaa4631264bc4`.

The manifest separately binds runner and rubric/policy identities, seed 0, case
order, Python 3.11.15, Pydantic 2.13.5, pytest 8.4.2 and macOS arm64. There is no
model/provider identity because no inference runs. Timings and output paths are
excluded from semantic hashes. Fixture v1 was frozen before comparison; later
source-adapter/test corrections did not change its bytes or expected answers.

## Corpus and observed results

There are 30 synthetic cases, five per family, stratified as 18 development,
6 calibration and 6 public frozen holdout. Every case has an implementation
source/rubric review rationale; this is not independent reviewer sign-off.

| Family | IDs | Distinct controls | none | fixed | full eligible | gold authorized |
| --- | --- | --- | --- | --- | --- | --- |
| workflow | WF-01–05 | trusted pass, false success, uncertain write, other repo, 105 distractor turns | 2/5 | 2/2 | 4/4 | 5/5 |
| project | PR-01–05 | current decision, reversal, closed milestone, wrong workspace, fresh repository conflict | 4/5 | 4/4 | 5/5 | 5/5 |
| correction | CO-01–05 | format, supersession, external truth, failure lesson, quoted-log injection | 1/5 | 4/4 | 5/5 | 5/5 |
| temporal | TF-01–05 | availability, deprecated API, future observation, as-of states, unknown freshness | 3/5 | 3/3 | 5/5 | 5/5 |
| authorization | AU-01–05 | wrong owner, wrong app/workspace, revoke, forget before pack, derived supports/later reuse | 5/5 | 5/5 | 5/5 | 5/5 |
| irrelevant | IR-01–05 | stateless answer, lexical near match, injection, explicit exclusion, unrelated history | 5/5 | 5/5 | 5/5 | 5/5 |

Fractions above are **synthetic_scripted_task_proxy** pass counts over evaluable
cases, not success rates for a general agent. Each family has a 3/1/1 split.
Exact split results, excluded IDs, per-case deltas and denominators are in JSON.

| Arm | Task proxy passed/evaluable | Explicit exclusions | Meaning |
| --- | --- | --- | --- |
| none | 20/30 | none | Current canonical evidence retained; ten historical-evidence tasks fail. |
| fixed | 23/23 | MEM0-WF-01, MEM0-WF-02, MEM0-WF-05, MEM0-PR-01, MEM0-CO-04, MEM0-TF-03, MEM0-TF-04 | Real fixed retrieval supports three correction transfers; the other twenty passes need current context or safe negative behavior. |
| full_eligible_history | 29/29 | MEM0-WF-05 | All feasible scripted cases pass; an over-budget long history is not an unconstrained baseline. |
| gold_authorized | 30/30 | none | Hand-selected authorized evidence availability; neither a product policy nor an agent-quality ceiling. |

The seven fixed exclusions are genuine missing legal v1 representations, not
retriever failures. Do not infer workflow support from 23/23. Full history exceeds
the budget in WF-05 and is excluded even though the scripted policy can find the
useful early receipt in the bounded subset. This prevents claiming full-history
feasibility from a task pass. IR-05's 24 short distractors do fit this budget.

All arms share 768 total input word units, a 512 historical cap and a 64 output
reserve. Counts use `FakeTokenCounter`, not endpoint tokens. Diagnostic history
includes typed fact/authority/receipt metadata; fixed packs actual narrow memory
assertions and its production wrappers. This representational overhead differs,
so resource differences are not pure retrieval-algorithm effects. Top-K/item limits
also remain actual fixed behavior. Current evidence and task policy stay identical.

Paired fixed vs none: 3 wins, 20 ties, 0 regressions on 23 common evaluable cases
(3/23 difference). Full vs none: 9 wins, 20 ties on 29. Gold vs none: 10 wins,
20 ties on 30. Full/gold vs fixed tie on all 23 common evaluable cases. There is
no statistical significance claim or MEM-1 lift threshold based on this corpus.
The 1.0 feasible-family macro means for the memory arms have the same exclusions;
none has macro 0.6667 across six families. These small, curated cases are favorable
to a finite policy and cannot estimate natural task frequencies or LLM variance.

## Evidence and negative controls

No known invariant violation occurred in the 120 rows. Scope/branch, privacy,
future/as-of ordering and complete support eligibility are checked before supply;
exact dependencies are checked during shared packing and again before consumption.
AU-04 selects a real memory then forgets it before packing; it is omitted. AU-05
invalidates a diagnostic view when one support is revoked and checks later reuse
of originals. A separate test constructs an actual schema-2 view using the existing
worker and invalidates its real complete dependency graph after forget.

Fixed uses `MemoryRetriever`, legitimate `MemoryCandidate` admission, immutable
originals, canonical lifecycle transitions, `MemoryPermissionRevalidator` and
`ContextAssembler`. Other arms use the same `ContextBuilder` with a synthetic
source adapter; they are not deployed application grant conformance. Manual grant
revocation is mapped to a local lifecycle suppression for legal originals; the
actual deployed grant/identity acceptance boundary remains unverified.

The driver receives only task/current/packed evidence, never family, split, arm,
expected answer, gold selector or rubric. A grader-only canary mutation changes
scores without changing action traces. Independent negative checks reject blanket
abstention on useful tasks, prohibited actions alongside a correct answer, receipt
revision mismatch, unknown outcomes labeled verified, and unsupported evidence.
Gold still filters revoked sources. Source text is data; untrusted/model-proposed
instruction text cannot become tool authority. Stateless useful answers still pass.

Observed limitation: IR-01 fixed retrieves and packs an irrelevant response-format
correction, although the arithmetic answer is correct. Its retrieval precision is
0/1; task success must not hide this retrieval error. The current fixed ranker has
no production task-conditioned relevance contract. Gold's perfect scripted score
is unsurprising with reviewed evidence and a finite rule policy; it is not a model
quality result or an independently discovered procedure.

## Resources and unverified evidence

Fresh in-memory environments are created per case/arm. Process import/OS caches
are uncontrolled. These sampled first-run timing observations are illustrative,
not benchmark speed claims or deterministic acceptance thresholds:

| Arm | p50 elapsed ms | p95 elapsed ms |
| --- | --- | --- |
| fixed | 1.424 | 2.724 |
| full_eligible_history | 1.429 | 21.951 |
| gold_authorized | 1.341 | 1.739 |
| none | 1.311 | 2.188 |

Per-row logical embedding calls, tool-action counts, serialized synthetic memory
and diagnostic bytes, final prompt/history word units and sampled CPU time are
recorded. Zero physical provider attempts is observed by construction and offline
socket-denial tests. Native Postgres/Dynamo read/write bytes, provider quota and
real-model quality are null/unverified. Serialized Python JSON is not physical
storage/index bytes, and these latencies are not provider latency.

The canonical Phase 36 report at its own older revision still records 24 offline
passed, 21 unverified and 3 blocked; MEM-0 changes none of those rows. Later suite
Postgres-subset evidence in current-state is distinct from new MEM-0 evidence.
Carry forward P36-MEMORY-RESOURCES, P36-QUALITY-LIVE, native Dynamo/Postgres
obligations beyond exercised subsets, identity/version authority, cloud recovery,
telemetry, physical deletion and provider/domain/browser acceptance. Defaults for
memory/extraction/lifecycle/consolidation remain off and fixed remains the default.

## Commands and implementation decisions

All commands below use `PATH="$PWD/backend/.venv/bin:$PATH"` from the repository root.

| Command | Outcome |
| --- | --- |
| `make memory-task-eval` | passed; 120 rows, identical semantic replay digests, unchanged fixture |
| `python -m pytest backend/tests/test_mem0_task_baseline.py backend/tests/test_memory*.py -q` | 267 passed (including 71 MEM-0 cases and all selected memory regressions) |
| `make memory-eval memory-lifecycle-eval memory-optimization-eval` | passed; respectively 14, 60 and 60 synthetic rows |
| `make planning-eval` | passed; unchanged 30-case planner corpus, no promotion |
| `make backend-test-offline` | passed: 1,821 tests, 90 deselected; initial run was 1,816 passed/1 failed because the whole-source planner freeze correctly detected new evaluator files |
| `make backend-lint` | passed |
| `git diff --check` and local Markdown link review | passed |
| native stores, providers, cloud, browsers | not run; unverified, no environment provisioned |

The full-source planner lock required a v15 rebind. v14 remains immutable historical
evidence; v15 preserves planner/config/corpus/runtime identity, the strict
current-or-direct-child guard and non-promotion. Only the evaluator's current lock
pointer and its conformance tests change; no runtime planner behavior is altered.
The final source passed the full offline suite before the implementation commit.

Files: `evaluation/memory_task_{contracts,runtime,driver,baseline}.py`,
`evaluation/fixtures/memory/mem0-cases-v1.json`, `tests/test_mem0_task_baseline.py`,
the planner lock/pointer/conformance test, Makefile, evaluator/experiment/router
READMEs, current-state, this report, ADR and benchmark contract. New data remains
under existing evaluation ownership; no second memory database or state machine.

Remaining limitations for independent review: diagnostic source policies simulate
grants; actual v2 invalidation is a separate probe rather than the corpus adapter;
no real model behavior or native storage performance is measured; arithmetic and
many current-state tasks are intentionally simple negative controls. The finite
fake reconciliation policy reads a synthetic canonical effect observation; it does
not establish native transaction/idempotency/recovery semantics. Fixed correction
interpretation uses a narrow assertion grammar, not a general language model.
The report makes no claim of broad procedural reasoning or production readiness.

MEM-1 planning may safely use the legal-contract gaps, scoped receipt proposal,
shared extension seams and replay tests after independent acceptance. It must
choose one verified source/receipt resolver, design a versioned knowledge contract
and full provenance edges, specify native concurrency/erasure/rollback tests, and
extend two-session transfer plus failure/unknown/revision controls. Do not begin
MEM-1 implementation or promote a feature from these proxy fractions.

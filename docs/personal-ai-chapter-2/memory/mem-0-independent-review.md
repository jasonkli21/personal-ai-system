# MEM-0 independent architecture and evaluation review

Date: **2026-10-29**, America/Los_Angeles. Reviewer: independent GPT-6.1 Sol High session. Review mode: read-only code, architecture, fixtures and offline execution, plus this report. No fixes, commits, deployments, credentials, live inference, new production defaults or subagents were used.

Tested HEAD: **`987bba5f6479791b54ac626d9959b1b39e23fbb3`**, direct child of `ad7c5004294b34df6acffd154509a402e2626659`. The implementation diff has 17 files, 7,690 insertions and 8 deletions: four `memory_task_*` modules, corpus, tests, Makefile/docs, and the planner v15 evaluation lock/pointer/tests. Production memory modules, settings and migrations have no changes in this diff. Initial tracked tree was clean; existing untracked `docs/memory/` planning material and older review files were present and preserved. This review adds only this report. Generated evaluation outputs remain ignored under `artifacts/mem0/`; diagnostic scripts/logs were written under `/tmp/`.

## Verdict and evidence disposition

**Accepted with mandatory bounded remediation.** Issue count: **0 P0, 1 P1, 3 P2, 0 P3**. All four findings below are verified benchmark defects or coverage weaknesses; none establishes a deployed data leak or production memory defect. Fix and independently reverify them before treating MEM-0 as an accepted foundation for MEM-1 planning. The architecture and evidence labeling do not require a new evaluation platform or a production rewrite.

The existing results are reproducible **component and finite-policy observations**. They establish that legal fixture originals can traverse the real fixed retriever, dependency validator and shared packing path, and that this corpus can be replayed deterministically. They do not establish that a later agent executes a task successfully because it learned from an earlier task. That distinction is mostly stated accurately in the implementation report and should be retained.

| Completion claim | Independent disposition |
| --- | --- |
| Required implementation artifacts present | Yes: contracts, 30 cases, four arms, driver/grader, manifests, tests, ADR and report exist. |
| Every intended benchmark safety/validity gate satisfied | **No**: action causality, original-effect identity and support truth are weaker than the benchmark contract implies; some negative controls cannot isolate their named invariant. |
| Unmodified MEM-0 offline replay verified | Yes, 120 rows and identical repeated semantic digest; details below. |
| General agent/model-mediated task improvement | Unverified, deliberately not measured. |
| Ready for accepted MEM-1 planning baseline | **No-go until bounded remediation and independent re-verification.** Architecture exploration can use the inventory and documented legal-contract gaps now. |
| Production promotion/readiness | Not established or authorized. |

## Independent architecture model

The durable authority chain is request identity and application/workspace scope → active completed source turn → conservative candidate policy → immutable original memory → lifecycle projection and optional exact derived view → server-owned query and eligible ranking → complete permission dependencies → shared assembly/packing → revalidation at supported later reuse. It is not an unconstrained learn-from-any-tool-output system.

| Concern | Actual owner / inspected executable boundary | Consequence for this review |
| --- | --- | --- |
| Authentication and namespace | `auth/scope.py:RequestScope`, middleware/application policy; source/record repository scope binding | Benchmark scope is trusted synthetic input. It does not authenticate a Google user or establish registered application/grant authority. |
| Original conversations/branches | DynamoDB conversation/message adapters; `storage/branches.py`; `memory/services.py:source_messages` and completed-turn checks | Real source fingerprint/branch checks are exercised for representable originals using in-memory repositories. The arbitrary diagnostic `branch` string is an additional synthetic boundary. |
| Admission | `memory/policy.py:candidate_reason`, `MemoryExtractionService` | MEM-0 calls real candidate admission for fixed records, but directly constructs them; it does not measure extraction quality or perform task A to produce the record. |
| Original and derived memory | `Memory` schema 1, `DerivedMemory` schema 2, Postgres/pgvector repositories | No new procedure record was smuggled into v1. Existing views have bounded exact support, not generic synthesis. |
| Validity and reuse | `memory/dependencies.py:original_reason`, `record_dependencies`, `MemoryPermissionRevalidator.is_current`; lifecycle epoch/event owners | Fixed dependencies are real. Diagnostic supports are only a recursively eligible source graph; F3 explains the separate truth limitation. |
| Context | `ContextAssembler` and `ContextBuilder`, source authority and permission contracts | There is no new production packer. Diagnostic history uses the shared builder after base assembly; fixed uses actual memory packing. The driver reconstructs typed evidence for the IDs accepted by that packer. |
| Jobs and cross-store effects | Postgres memory/lifecycle effects and DynamoDB jobs/leases | No global atomic transaction may be inferred. MEM-0 adds neither a scheduler nor a production memory database. |
| Domain truth | Canonical domain repositories/context adapters | Synthetic `current` records are mandatory snapshots supplied equally to all arms, not demonstrated fresh source reads. They outrank historical records in the finite driver. |
| Target outcome | `memory_task_driver.py:SyntheticTools` and `ActionTrace` | These primarily inspect supplied facts/old receipts and emit directives. They do not execute a validation command and generate a new target-run outcome receipt. |
| Reporting | `memory_task_baseline.py:grade`, `aggregate`, `write_run` | Fixture, source/config/lock and semantic outputs are bound; wall/CPU samples are kept separate. F1 identifies what grading cannot currently detect. |

`Environment.is_current` additionally checks synthetic eligibility before calling the real memory validator. That is useful defense in the harness, but it means success here cannot be claimed as independent conformance of deployed grants. `Environment.apply` maps revoke/forget/supersede onto synthetic suppression and, for originals, a local forgotten transition; it is not a full production revocation service test. The actual schema-2 invalidation test in `test_mem0_task_baseline.py:354` is valuable separate component evidence, not execution of the diagnostic derived fixture through a production generative-memory path.

The ADR correctly retains existing ownership, v1/v2 compatibility, default-off behavior and a versioned MEM-1 choice. Its preferred generalized knowledge family remains a hypothesis. A narrow repository test-workflow source with a trusted resolver is a reasonable first candidate; source policy, issuer/resolver, actor/run/command binding, cancellation, CAS/epoch concurrency, erasure and rollback remain decisions/tests for the next plan. No schema preference is proven superior by these proxy scores.

## Benchmark validity and omissions in the plan

The study measures a deterministic structured-evidence availability pipeline. `Fact.subject/value/kind`, currentness, source authority and synthetic receipts are authored inputs. Most answers are exact reads of `Fact.value`; fixed response-format assertions use a narrow grammar. The full-history arm is **typed diagnostic history**, not untouched historical conversations. This is a useful component baseline when labeled that way. No direct rubric/gold/split leakage into `DriverInput` was found, and the existing grader-only canary test is appropriate. A normalized fact containing an answer is evidence input, not automatically grader leakage; however, it removes the unstructured interpretation problem a real agent will face.

The 30 cases contain declarative prior-session sources; `session_id` is metadata, and no first task actually runs, produces a receipt, admits knowledge, and then transfers it to a second task. `reuse_workflow` copies an old receipt and emits a command; it does not establish the current task's successful execution. The implementation report largely acknowledges this. MEM-1 must add a real two-stage hermetic vertical slice with a target tool state/outcome, keeping historical verification separate from target success.

The plan emphasized schema validation, four arms and frozen counts more than independent **causal action validation**. It did not sufficiently specify the following:

1. A target action must be tied to a prior authorized revision/source read, with ordering, cardinality, arguments and a trusted result. A set of action names is insufficient (F1).
2. Reconciliation needs an explicit original execution identity and a keyed observation, even in an offline fake. A generic current fact about an “effect” cannot prove observation of the original intent (F2).
3. Source availability and semantic support are independent. A fully authorized support graph can still contain a fabricated derived claim (F3).
4. Negative fixtures need single-fault counterfactuals: a test that passes when its named guard is removed is weak evidence for that guard (F4).
5. A useful task metric must distinguish an old successful run, a safe recommendation, an attempted target action and a newly verified target outcome. Future model variability, text interpretation, tool failures and cache/state evolution require separate tiers; merely substituting a model into the present driver is not enough.
6. Case counts/splits do not estimate natural task frequency or difficulty. Seven fixed cases are excluded and most remaining passes rely on current facts or safe abstention. Coverage and feasible-task quality must remain separate. Pre-registration/freeze chronology and prior hand review are asserted in the docs, but a single implementation commit does not independently establish when review/freezing occurred. The byte identity is independently verified; chronology is unverified.

These omissions do not justify implementing dreaming, new memory tools, multi-agent sharing or new storage in this fix session. The smallest repair is better bounded contracts, a keyed fake observation, adversarial trace validation and controlled diagnostic cases.

## Findings

### F1 — P1: action grading ignores order, duplicates and most verification claims

**Verified.** Root locations: `backend/src/personal_ai/evaluation/memory_task_baseline.py:60`–`98` (`required` becomes a set; citations are unioned across all actions; only `reuse_workflow` gets receipt validation), `:230`–`239` (run invariants do not add ordering/cardinality checks); `backend/src/personal_ai/evaluation/memory_task_driver.py:80`–`128` (emitted checks and reuse); `backend/src/personal_ai/evaluation/memory_task_contracts.py:302`–`309` (generic action envelope).

Trigger: take the genuine successful WF-01 trace and reverse it. The answer and workflow reuse now precede revision checking, reading current state and inspection. `run_case` still returns **task_status=passed, execution_status=passed, invariant_violations=[]**. Append a second identical `reuse_workflow` action: same result. Separately, changing every CO-01 trace's revision to `wrong-revision`, receipt ID to `invented` and verification to `verified` still passes `grade`; those fields are ignored outside workflow reuse.

Reproduce from the repository root with the virtualenv Python:

```python
from unittest.mock import patch
from personal_ai.evaluation.memory_task_baseline import load_corpus, run_case
from personal_ai.evaluation.memory_task_driver import run_driver
c = next(c for c in load_corpus().cases if c.case_id == "MEM0-WF-01")
for transform in (
    lambda a: tuple(reversed(a)),
    lambda a: (*a, next(x for x in a if x.action == "reuse_workflow")),
):
    with patch("personal_ai.evaluation.memory_task_baseline.run_driver",
               lambda view: transform(run_driver(view))):
        row, _ = run_case(c, "gold_authorized")
        print(row["task_status"], row["execution_status"], row["invariant_violations"])
# Actual, twice: passed passed []
```

Impact: the benchmark cannot catch a regression that checks preconditions after reuse or repeats a supposedly bounded workflow directive. It also accepts fabricated verification labels on other actions. This is a benchmark safety blind spot, not proof the present deterministic driver or production code executes an unsafe effect. Blanket abstention and a plainly prohibited action are caught, but those tests do not cover this defect.

**Repair:** define action-specific payload/result contracts and causal validation. A valid workflow recommendation/reuse must follow a current revision read/check bound to the same source revision and target run; receipt verification must belong to a resolvable historical receipt, not imply target success. Either forbid duplicate directives or bind repeated attempts to explicit idempotent execution identity and state. Enforce meaningful action-field combinations for all actions; unknown verification cannot become verified because the driver says so. Do not implement a new production tool runtime. An evaluation-only finite state validator is sufficient for these fixtures.

**Acceptance:** the original trace passes; reversed, check-after-reuse, missing-check-result, unrelated-revision, forged verification/receipt and duplicate non-idempotent directive traces fail with explicit reasons. Safety-invalid traces produce failed execution/invariant status and a nonzero `write_run`/CLI result, not just a lower task score. Valid intentionally idempotent replay may pass only when a keyed fake receipt proves no second effect. Add the mutations against `run_case`/run status as well as direct `grade` tests.

### F2 — P2: the reconciliation control has no original execution-key binding

**Verified.** Locations: `backend/src/personal_ai/evaluation/memory_task_driver.py:34`–`51` and `:96`–`103`; `backend/src/personal_ai/evaluation/memory_task_contracts.py:139`–`148` (Task has no effect key); `backend/src/personal_ai/evaluation/fixtures/memory/mem0-cases-v1.json:265`–`376` (WF-03). Its historical receipt's `run_id` is not used by reconciliation, and the `reconcile` trace has `{}` arguments and no receipt.

Trigger: rename WF-03's current observation to `unrelated_effect` and replace its content with `Canonical observation for a DIFFERENT execution key.` Keep its generic subject `effect` and value `uncertain`. All contracts accept it; the none arm still passes and emits `effect_uncertain_inspect_original_key` citing `unrelated_effect`.

```python
from personal_ai.evaluation.memory_task_baseline import load_corpus, run_case
from personal_ai.evaluation.memory_task_contracts import Case
c = next(c for c in load_corpus().cases if c.case_id == "MEM0-WF-03")
d = c.model_dump(mode="json")
d["sources"][1]["source_id"] = "unrelated_effect"
d["sources"][1]["content"] = "Canonical observation for a DIFFERENT execution key."
r, _ = run_case(Case.model_validate(d), "none")
print(r["task_status"], r["execution_status"], r["action_trace"][1])
# passed passed; reconcile arguments={}, evidence_ids=['unrelated_effect'], receipt_id=None
```

Impact: this row tests recognizing a generic canonical uncertainty value, not observing the original effect or preventing a duplicate through execution identity. There is no stateful write/retry in this fake; none of this establishes native reconciliation/idempotency. The baseline report acknowledges that native limitation, but the fixture review rationale explicitly claims the finite policy reconciles the original key. That stronger component claim is unsupported.

**Repair:** add an evaluation-only explicit effect/intent key to the task and independently supplied canonical observation. Resolve observations by that key plus scope/run/command identity. Record the requested key and observation receipt in the action. Preserve the uncertain state; never retry because another key succeeded. Do not provision a store or alter production mutation contracts.

**Acceptance:** correct-key uncertain observation yields qualified uncertainty; missing/wrong-key or wrong-owner observation yields unknown/abstention; correct-key success may report confirmed observation, while success for another key cannot. Duplicate invocation of a stateful fake intent cannot increment its effect count twice. The test must inspect the key/result receipt, not only the final string. Freeze the old fixture/result identity and issue a new experiment identity for changed case bytes.

### F3 — P2: diagnostic derived support proves eligibility but not support for its fact

**Verified; synthetic boundary only.** Locations: `backend/src/personal_ai/evaluation/memory_task_contracts.py:108`–`130`, `:233`–`279`; `backend/src/personal_ai/evaluation/memory_task_runtime.py:231`–`247`; `backend/src/personal_ai/evaluation/memory_task_driver.py:84`–`91` and `:135`–`142`. Support references/cycles/permissions are checked, but no rule binds a `historical_derived` fact to its supports. The driver treats it as answer-bearing evidence. This is separate from the real schema-2 validator, which was not weakened by MEM-0.

Trigger: use AU-05 with no transitions, change only the diagnostic derived fact to `fabricated preference` while both originals still say `private canary`, and make the grader expect the fabricated value. The case validates, gold injects the derived node and the task and execution both pass without an invariant violation. Changing the rubric is deliberate here: it proves the **contract/invariant layer** cannot distinguish an authorized but unsupported claim from a reviewed one, independently of answer matching. It is not evidence that rubric fields leaked to the driver.

```python
from personal_ai.evaluation.memory_task_baseline import load_corpus, run_case
from personal_ai.evaluation.memory_task_contracts import Case
c = next(c for c in load_corpus().cases if c.case_id == "MEM0-AU-05")
d = c.model_dump(mode="json"); d["changes"] = []
d["sources"][2]["fact"]["value"] = "fabricated preference"
d["expected"].update(abstain=False, answer="fabricated preference",
                      required_actions=["inspect", "answer"])
r, _ = run_case(Case.model_validate(d), "gold_authorized")
print(r["task_status"], r["execution_status"], r["invariant_violations"])
# Actual: passed passed []
```

Impact: future MEM-1 code could inherit “all supports eligible” as sufficient verification of a derived claim. Current AU-05 proves graph revocation behavior, not support entailment, contradiction resistance or successful generative consolidation. Empty-support historical-derived sources are also structurally allowed.

**Repair:** make the diagnostic support semantics explicit. For this narrow structured corpus, require a nonempty support set and a declared exact-support recipe that verifies subject/value against every required support, including the narrow assertion parser for legal originals. Alternatively mark arbitrary diagnostic derived claims unverified and exclude them from answer authority; keep the row as an eligibility-only control. Do not add generic model adjudication or pretend this recipe proves future generative support. Document the separate production `support-v1` evidence and unresolved future semantics.

**Acceptance:** authorized exact support passes; zero supports, contradictory values, unsupported subject/value and a dropped required support fail contract/admission or remain explicitly unverified and unavailable to the answer policy. Correct support followed by revoke/forget still suppresses the whole node at pack and later use. A rubric expecting the unsupported value must not turn that safety failure into a passing run.

### F4 — P2: several negative controls pass without exercising their named guard

**Verified coverage weakness.** Relevant locations:

- WF-04: corpus `:397`–`417` is another workspace/revision `rev-1`; `:440`–`452` sets current HEAD/task to `rev-2`. Supplying this wrong-workspace record directly to `DriverInput` after bypassing the scope filter still abstains because receipt/revision mismatch independently blocks reuse (`memory_task_driver.py:20`–`24`). Thus the named wrong-repository case cannot isolate scope enforcement.
- TF-03: corpus future source near `:3971`–`3989` is both observed after the clock and effective after the task date. Removing only the effective-date check would not expose it; this does not separately test an already observed announcement with a future effective date.
- AU-02: corpus `:4328`–`4333` changes both application and workspace. It does not distinguish app-only from workspace-only failure. The production scope implementation is sound in the inspected path; the evidence is less discriminating than its labels.
- CO-04: corpus `:3511`–`3537` contains one failure receipt, despite the required repeated-failure scenario. It is largely WF-02 with the failure-lesson kind and command changed.
- IR-03: corpus `:4857` onward uses arithmetic. The driver returns at `memory_task_driver.py:81`–`83`, before its evidence-processing branch. It is a useful compute isolation control, but weak evidence for preserving authority while using useful evidence alongside a malicious tool instruction. CO-05 is the stronger mixed-input injection control.

Reproduce the first counterfactual with `DriverInput(task=WF04.task, evidence=tuple(visible_source(s) for s in WF04.sources))` and `run_driver`: observed actions remain `inspect, read_current, check_revision, abstain` even though the wrong-scope source was deliberately supplied. TF-03 independently has both `source.observed_at > clock_utc` and `source.effective_at > task.as_of` equal to true. These are code/data observations, not hypothetical bugs.

Impact: a guard regression can go undetected despite all six family counts remaining satisfied. The corpus is a reasonable starting roster, but it is not yet strong coverage of each adverse dimension, and its family totals should not be used as coverage percentages.

**Repair:** preserve v1 as historical frozen evidence; add separately identified controlled variants or a new corpus version. Use matching revisions/preconditions in the wrong-repository case; separate app-only/workspace-only mismatches; make a future-effective source already observed at the task clock; include independent repeated failure receipts plus a one-failure control; and pair useful answer evidence with adversarial instructions in a task that traverses the evidence branch. Keep these evaluation-only. Use mutation testing of one guard at a time rather than adding many near-duplicate cases.

**Acceptance:** each named guard's intentional removal causes at least one corresponding test to fail, while other guards remain intact. Positive twins succeed, adverse twins deny/qualify correctly. Preserve 3/1/1 family stratification for a new comparison corpus, or explicitly keep supplemental controls outside the frozen scoring denominator. Do not silently change v1 bytes or claim a secret/blind holdout.

## Actual case coverage

The independent corpus read counted **30 cases, 177 sources, exactly five cases per family**, with **18 development / 6 calibration / 6 frozen holdout**. Every family has 3 development, 1 calibration and 1 public frozen holdout. Source counts are dominated by repetitive distractors, not by 177 independent tasks.

| Family / IDs | Sources | Distinct represented scenarios | Important boundary of the evidence |
| --- | ---: | --- | --- |
| Workflow WF-01–05 | 116 | Historical successful receipt, failed run plus assistant claim, uncertain effect, wrong repository, long history | Recommendations/receipt inspection, not target command execution; F1/F2/F4 apply. |
| Project PR-01–05 | 8 | Revision-bound decision, reversal, closed milestone, wrong workspace, fresh runtime conflict | Fresh facts are supplied, not fetched; no independently executed project-state update. |
| Correction CO-01–05 | 9 | Format transfer, superseding correction, canonical fact conflict, failure lesson, quoted-log injection | Three fixed-arm wins are narrow response-format reads. Repeated failure is not actually represented. |
| Temporal TF-01–05 | 9 | Changed stock, changed API, future source, historical as-of policy, unknown currentness | Temporal values are structured facts; future observation/effective-time guards are confounded in TF-03. |
| Authorization AU-01–05 | 7 | Other owner, other app/workspace, before-query revoke, before-pack forget, derived support/later reuse | Real fixed originals plus synthetic policy overlay; derived corpus node is not actual v2. No deployed grants. |
| Irrelevant IR-01–05 | 28 | Arithmetic, lexical near match, tool injection, explicit memory exclusion, 24 irrelevant notes | Many safe-abstention/compute controls. Fixed retrieval relevance is not independently exercised for every diagnostic source. |

Operation distribution: **5 workflow, 1 reconcile, 12 recall, 7 current, 2 as_of, 3 compute**. Tags include 8 cross_session, 14 negative, 2 long_history and 2 prompt_injection cases. Transitions total 3 before_query, 2 before_pack, 1 before_use. Ten cases contain any `fixed_type` source. Branch-change, sensitive and expiry mutations exist in tests but not as independent scored corpus dimensions. There is no explicit actor/delegation identity separate from owner, no grant purpose/destination variation, no native erasure/retention test, no learned extraction stage, and no model action failure or long-lived cache trajectory in this corpus. Those remain unverified, not automatically failed production features.

## Four-arm fidelity, executed status and comparisons

All 120 original rows executed with `execution_status=passed` and zero recorded invariant violations. That is what the current invariant implementation reports; F1–F3 limit its meaning. Task denominators below are intentionally different.

| Arm | Executed | Evaluable task proxy | Fidelity and limitations |
| --- | ---: | ---: | --- |
| none | 30 | **20/30** | No history selected/packed; same mandatory current canonical task evidence. Ten historical-evidence tasks fail. |
| fixed | 30 | **23/23**, 7 unsupported | Actual `MemoryRetriever`, legal v1 `MemoryCandidate`, real memory dependencies and `ContextAssembler`. In-memory stores/fake vectors; no extraction inference. Procedures/project facts are not forged as v1. |
| full_eligible_history | 30 | **29/29**, 1 truncated | Chronological eligible typed evidence through shared builder. WF-05 omits eligible history and is excluded even though its retained early useful source permits a task-proxy answer. |
| gold_authorized | 30 | **30/30** | Gold references select evidence, never grant access. Same budget and synthetic authority resolver. Evidence availability diagnostic, not agent-quality ceiling or deployable policy. |

Fixed exclusions: **WF-01, WF-02, WF-05, PR-01, CO-04, TF-03, TF-04**. Full-history exclusion: **WF-05**. This exactly matches the raw rows and implementation report. A 23/23 number is not 100% coverage of procedures or all 30 tasks.

All fixture budgets are 768 input word units, 512 historical word units and a 64 response reserve. Fixed packs actual memory text/wrappers; diagnostic arms pack typed facts/authority/receipt JSON, so overhead differs. These differences are disclosed and prevent a pure retrieval-algorithm resource interpretation. Full/gold use identical shared-builder historical budgets. There is no evidence of extra tools or hidden history in none.

Independently recomputed paired intersections:

| Pair | Comparable cases | Wins / ties / regressions | Mean binary task-proxy delta |
| --- | ---: | --- | ---: |
| fixed vs none | 23 | 3 / 20 / 0 | 3/23 = 0.1304348 |
| full history vs none | 29 | 9 / 20 / 0 | 9/29 = 0.3103448 |
| gold vs none | 30 | 10 / 20 / 0 | 10/30 = 0.3333333 |
| gold vs fixed | 23 | 0 / 23 / 0 | 0 |
| full history vs fixed | 23 | 0 / 23 / 0 | 0 |

The three fixed wins are **CO-01, CO-02, CO-05**. Twenty fixed ties come from current context or negative controls. None's balanced-family macro fraction is 2/3; each other arm's feasible-family macro is 1.0 with the stated exclusions. These are descriptive curated-corpus statistics; no significance, natural frequency or future model lift claim follows.

## Measurement sanity checks and adversarial outcomes

Recomputed from `artifacts/mem0/cases.json` and `aggregate.json`, rather than trusting Markdown tables:

- 120 rows; 0 original invariant lists nonempty; all current task evidence is preserved in none.
- IR-01 fixed selects/packs `format` despite a stateless math task: retrieval precision **0/1**, task passes. The implementation correctly documents this existing retrieval limitation.
- AU-04 fixed selects `forgotten`, then packs/consumes nothing. Full/gold do the same.
- AU-05 full initially selects `derived, support_a, support_b`, packs only `support_b`, then drops it before use; consumed IDs are empty. Gold's derived node never packs. Fixed selects `support_a` only (exact duplicate collapse) and consumes nothing. These are real observed transitions in the harness.
- WF-05 is honestly truncated in full history; a task answer does not make the whole history fit.
- Native read/write bytes, provider quota and real model quality are null. Physical provider attempts are zero by construction; socket-denial tests cover the unmodified offline path. Serialized Python JSON is not native/index/storage bytes.
- Timings are fresh in-memory process observations with uncontrolled import/OS caches. They are not endpoint latency, cloud cost, calibrated model tokens or cold/warm production measurements. Concurrent test activity further limits interpreting timing samples collected in this review.

| Probe | Observed result | Interpretation |
| --- | --- | --- |
| Existing grader-only expected-answer canary | Target traces unchanged; altered expected answer fails | No direct grader leak found. |
| Swap CO-01 source owner after selection/before pack | fixed/full/gold all packed=[], consumed=[] | Supported scope revalidation held. |
| Existing revoke/forget/branch at supported stages | All 71 MEM-0 tests pass in serial targeted run | Component evidence; synthetic policy boundary remains explicit. |
| Reverse WF-01 trace / duplicate reuse | Both task and execution pass, no violations | F1 verified. |
| Forge non-workflow revision/receipt/verified labels | Direct grade passes | F1 action-contract weakness; no actual tool effect established. |
| Replace WF-03 observation with another effect's observation | Passes while claiming original-key inspection | F2 verified. |
| Give authorized derived node an unsupported fact and matching rubric | Contract and task/execution pass | F3 verified; not grader leakage. |
| Feed WF-04 wrong-scope source directly past eligibility | Still abstains on revision mismatch | F4 guard confounding verified. |
| Change PR-01 task revision | Abstains and task fails | Existing revision-sensitive behavior works. |
| Inject an uncited canary into an `inspect` action's arguments | Direct grade ignores it and passes | Additional F1 payload blindness; deliberately injected probe, **not evidence of a real unauthorized disclosure**. |

## Commands, environment and reproducibility log

Commands ran from `/Users/jasonkli/projects/personal-ai-system`, with `PATH="$PWD/backend/.venv/bin:$PATH"`. Environment: CPython **3.11.15**, Pydantic **2.13.5**, pytest **8.4.2**, macOS **27.0.1 arm64**. No external environment was provisioned. Warnings concern future Google Python 3.11 support, Starlette/httpx deprecation and Pydantic TypedDict ReadOnly behavior; they do not establish provider dispatch.

| Command | Exit/result | Evidence path / qualification |
| --- | --- | --- |
| `git status --short`; `git rev-parse HEAD`; `git diff --stat ad7c500..HEAD` | 0 | Initial state/scope recorded above. |
| `python -m personal_ai.evaluation.memory_task_baseline --output artifacts/mem0/review-rerun` | **0**, same semantic digest on a separate CLI invocation, two internal replays | `/tmp/mem0-review-rerun.log`; `artifacts/mem0/review-rerun/manifest.json`. |
| `make memory-task-eval memory-eval memory-lifecycle-eval memory-optimization-eval planning-eval backend-lint` | **0** | `/tmp/mem0-review-evals.log`; MEM-0 runs twice internally; old memory evaluations emit 14/60/60 synthetic rows, planner 30 cases with non-promotion, Ruff clean. |
| `python -m pytest backend/tests/test_mem0_task_baseline.py backend/tests/test_memory*.py -q` (initial, concurrent with the above/full suite) | **1**, 266 passed, 1 failed, 17.56s | `/tmp/mem0-review-targeted.log`; extraction disclosure test returned `reasons=('timeout',)`. Do not erase this initial failure. |
| Same targeted command, repeated serially | **0**, **267 passed**, 11.86s | `/tmp/mem0-review-targeted-serial.log`; includes 71 MEM-0 tests. |
| `make backend-test-offline` (initial, concurrent with evaluations/targeted tests) | **2**, 1,819 passed, 2 failed, 90 deselected, 247.18s | `/tmp/mem0-review-offline.log`; two existing adaptive-routing tests raised `routing_label_identity_mismatch:prepared_input,metrics_missing,case_status`. |
| `python -m pytest backend/tests/test_adaptive_routing_phase35.py::test_dataset_reproducible_groups_missing_labels_and_no_prompt backend/tests/test_adaptive_routing_phase35.py::test_phase35_offline_evaluation_no_promotion_from_synthetic_agreement backend/tests/test_memory_disclosure_authorization.py::test_allowed_policy_reaches_count_structured_generation_and_embedding_with_attribution -q` | **0**, **3 passed**, 41.74s | `/tmp/mem0-review-retry-failed.log`; failures did not reproduce. Concurrency/timing is a plausible explanation, not proven root cause. |
| `make backend-test-offline` repeated with no concurrent suite | **2**, **1,820 passed, 1 failed, 90 deselected**, 266.99s | `/tmp/mem0-review-offline-serial.log`; `test_matrix_uses_generic_profiles_task_contract_and_p21_p19_seams` expected 80 synthetic cases but got 60 (`backend/tests/test_provider_matrix.py:355`). Full-suite green is **not independently reproduced**. |
| `python -m pytest backend/tests/test_provider_matrix.py::test_matrix_uses_generic_profiles_task_contract_and_p21_p19_seams -q` | **0**, **1 passed**, 23.58s | `/tmp/mem0-review-provider-retry.log`; full-suite failure did not reproduce in isolation. |
| `python /tmp/mem0-review-probes.py`; `python /tmp/mem0-review-more-probes.py` | **0**, expected counterexamples and denied owner swap | `/tmp/mem0-review-probes.json`, `/tmp/mem0-review-more-probes.json`; self-contained material reproductions included above. |
| Independent corpus/raw-row aggregate reads | **0** | Counts, exclusions, case IDs and paired arithmetic recorded in this report. |
| `git diff ad7c500..HEAD -- backend/src/personal_ai/settings.py backend/src/personal_ai/memory backend/migrations` | **0**, empty diff | No production memory/settings/migration change in implementation. |
| `git check-ignore artifacts/mem0/manifest.json` | **0** | Run artifacts ignored. |
| Native DB/emulator/provider/cloud/browser checks | Not run; **unverified** | No synthetic replacement is counted as external acceptance. |
| `git diff --check` and report path/content review | **0**, clean whitespace; referenced local paths checked | This is a report-only review; final tree preserves existing untracked documents. |

The semantic outputs were identical across the two internally executed corpus evaluations. A separate CLI replay under `artifacts/mem0/review-rerun/` also matched the result digest (command log above). Independently reproduced identities:

```text
fixture SHA256  043edaae3461286b49bcb4fda4f73bdc5059e528361bad3fa670a3b1c4e58b18
source SHA256   87d7262fed14622512200bc923524f4c2c0efa392ac75d74632b83622046ed8d
schema SHA256   e52c4b6ffe220e4ad2c7156c143c1469c1398ff39f613b6e86ebf95e560934fc
result SHA256   955619e6cc964fb9a3f470b634499a1f9f9599784d7a895d9b7aaa4631264bc4
runner SHA256   9e640e2867946a70c60be4f9beae72e43eca58e554b12f8d601d66ff08e655e0
```

**Unresolved full-suite observation (not counted as an attributed MEM-0 finding):** neither full offline run was clean, although all four failed test invocations passed their isolated/serial retries. The affected provider/adaptive test and evaluator files are unchanged in the MEM-0 diff. Deadline sensitivity is plausible; an underlying order-dependent or timing regression is not ruled out. The implementer’s historical 1,821-pass receipt was not independently reproduced here. The next verification must investigate a recurrence rather than treating retries as equivalent to a clean full-suite receipt.

The manifest names the actual tested HEAD, dirty state true due to preserved untracked docs, seed 0, source/config/lock digest, schema/fixture identities, null model/provider, policy labels, case ordering, Python/platform/dependency identity and unverified evidence. Reproducibility of this environment's semantic run is supported; portability to different dependencies, native engines or model behavior is not implied. Sample durations are excluded from the semantic hash. The planner v15 rebind retains the same runtime/config/corpus/fixture dependency identities and strict current-or-direct-child source guard; the inspected diff changes evaluation binding, not runtime planner behavior. Historical v14 remains preserved.

## Preserved external and production blockers

Phase 36's canonical `docs/personal-ai-chapter-2/phase-36/release-report.md` remains at its own tested revision `77fdce50790f45b9d04b3cae48e71d1dd43e4621`: **release_ready=false**, **24 passed / 21 unverified / 3 blocked**. MEM-0 changes no Phase 36 row. Later repository evidence for a native Postgres subset is separate from this review; it cannot close all older native obligations.

Carry forward **P36-MEMORY-RESOURCES**, **P36-QUALITY-LIVE**, **P36-DYNAMO-NATIVE/REAL**, remaining **P36-POSTGRES-NATIVE** obligations, **P36-DELETE-PHYSICAL** (blocked), **P36-IDENTITY**, **P36-VERSION-AUTHORITY** (blocked), **P36-WORKFLOW** (blocked), and the owning usage/federation/mutation/artifact/cloud storage, cross-cloud, headroom/soak, recovery/telemetry, provider/live/domain/browser and retirement obligations. In particular, scoped fixture suppression is not physical erasure, local receipt dictionaries are not independently authenticated tool outcomes, and synthetic owner strings are not deployed Google/service identity.

Memory, extraction, consolidation, forgetting/automation and lifecycle worker production defaults remain off; fixed remains the default strategy when applicable (`settings.py:249`–`277`). No Memory v1/Derived v2 contract, production memory policy or migration is altered. The runner has no model dispatch path and constructs offline settings that ignore ambient credentials/provider flags. Nothing in this report authorizes enabling a feature or handling personal data in deployment.

## Implementation-ready remediation handoff

The next agent should work in one bounded fix session, preserve user untracked documents, read the router/current state first and leave production memory/settings/migrations untouched. No model, database or cloud access is necessary. Fix owners are the existing evaluation modules, focused tests and MEM-0 evidence docs. This report is the complete next-session specification; do not start MEM-1 implementation.

1. **Repair F1 first** in `memory_task_contracts.py`, `memory_task_baseline.py`, `memory_task_driver.py` and `test_mem0_task_baseline.py`. Add action-specific schemas/validation, ordered precondition/result binding, multiplicity or explicit keyed replay rules, and fail-closed verification semantics. Keep answer quality separate from execution validity. Include original/reversed/check-after-use/duplicate/forged trace tests at both grader and runner/status levels. Exit: the exact F1 probes fail safely and original valid traces still pass. Do not “fix” by banning all actions or blanket abstention.
2. **Repair F2 next**, using the action-result contracts from step 1. Model a minimal evaluation-only original effect identity and independently keyed canonical observation/receipt. Record observation request and response, and prove wrong-key success cannot become original-key confirmation. Add a stateful fake counter only if needed to measure duplicate intent behavior. Exit: correct-key unknown stays unknown, wrong-key/missing observation abstains, confirmed original effect can be observed without replaying it, same intent cannot produce two effects.
3. **Repair F3** in source validation/runtime/driver. Choose the narrow exact-support recipe or explicit eligibility-only unverified representation. No broad generative support engine. Exit: contradictory/zero/missing support cannot yield a trusted answer even with a rubric expecting it; full dependency revoke/forget and actual v2 component tests remain passing. Describe exactly which support semantics are and are not exercised.
4. **Strengthen F4 controls**, with independently identified supplemental cases or a new comparison corpus/version. One guard at a time must be necessary to the result. Add matching-revision wrong-scope, app-only/workspace-only, already-observed future-effective, repeated independent failures and mixed useful/adversarial evidence variants. Preserve old frozen bytes/results. Exit: deliberate single-guard mutations are caught; positive twins succeed; reviewed split/denominator policy is explicit.
5. **Recompute evidence after the final source is stable.** Run `python -m pytest backend/tests/test_mem0_task_baseline.py backend/tests/test_memory*.py -q`, `make memory-task-eval`, `make memory-eval memory-lifecycle-eval memory-optimization-eval planning-eval`, `make backend-test-offline`, `make backend-lint`, and `git diff --check`, with backend virtualenv on PATH. Run deadline-sensitive suites serially. Resolve or explicitly classify the existing provider-matrix/full-suite failures recorded here; isolated retries are not a substitute for a passing required full run. Do not weaken timeouts or disable tests solely to recover a green count. Two semantic replays must match the newly frozen source/corpus identity; a changed source/result must not reuse this report's acceptance digest. If the whole-source planner lock rejects changed evaluation files, follow its existing explicit non-promoting rebind process and preserve historical locks; do not weaken the source guard or casually skip its tests.
6. **Update the baseline report, benchmark contract and living current state** with tested revision/source identity, exact commands/results, new exclusions/denominators, residual evidence and the independent review disposition. Preserve this historical review; add remediation evidence and request a fresh independent verification of F1–F4. Do not change Phase 36 rows based on offline results. Treat any new finding from the fixes as a remaining gap rather than rewording away its evidence class.

A MEM-1 plan may then safely inherit: existing production ownership, unchanged v1/v2 policies, the fixed legal-contract gaps, shared packing/revalidation seams, explicit historical receipt versus target-outcome distinctions, and bounded negative controls. That plan must specify an actual two-session task A → verified evidence → admission/persistence → task B transfer, with a trusted receipt resolver, revision drift, failure/unknown and revocation variants, native concurrency/erasure/rollback tests, and later model-quality evaluation. The present 20/30, 23/23, 29/29 and 30/30 fractions are historical scripted observations, not targets to preserve or proof that MEM-1 improves real tasks.

**Final go/no-go: no-go for an accepted MEM-1 planning baseline until F1–F4 are repaired and independently reverified.** The bounded architecture reconciliation and reproducible component measurements are reusable now; production readiness and automatic MEM-1 implementation are not authorized by them.

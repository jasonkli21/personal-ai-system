# MEM-0 benchmark contract v2

Updated 2026-10-29 after the independent review at
`mem-0-independent-review.md`. The v1 corpus and
its recorded results remain immutable historical evidence. The active runner
uses `mem0-v2`, `mem0-rubric-v2`, and
`evaluation/fixtures/memory/mem0-cases-v2.json`. It retains 30 cases, five per
family, with the original 18/6/6 split (three development, one calibration, one
public frozen holdout in each family). V2 is a new experiment identity.

The benchmark measures synthetic components and a finite scripted task proxy.
It does not measure model competence, two-session memory learning, production
security, or deployment readiness. The machine contracts live in
`evaluation/memory_task_contracts.py`; the runner, driver, and scoped synthetic
adapter are `memory_task_baseline.py`, `memory_task_driver.py`, and
`memory_task_runtime.py`.

## Inputs, authority, and packing

Each case binds a synthetic owner/application/workspace/branch, clock, revision,
task, sources, transitions, rubric, gold references, and budgets. Source content
cannot grant access. History is eligible only within the full scope, branch,
observation/effective-time, privacy, permission, and support boundaries.
Pre-query and post-selection changes remain distinct. The shared builder and
driver-consumption boundary recheck source dependencies.

| Arm | Contract |
| --- | --- |
| `none` | No historical retrieval or injection; current canonical task context remains available. |
| `fixed` | Actual fixed retriever, legal Memory v1 candidates, real assembler and dependency revalidation. Procedures/project facts that v1 cannot represent are explicitly unsupported. |
| `full_eligible_history` | Chronological eligible history through shared `ContextBuilder`; a dropped eligible source marks the case truncated and excludes it from feasible paired task comparisons. |
| `gold_authorized` | Grader-owned references select only eligible sources through the same builder. Gold never grants access; this is an evidence-availability diagnostic. |

All arms use the same task, current evidence, budget, fake word-unit token
counter, and finite tools. Fixed top-K/item limits are actual implementation
behavior. Typed diagnostic history has different metadata overhead from fixed
memory wrappers. The driver receives only task, current scope, and consumed
evidence; it never receives arm, split, case ID, gold IDs, rubric, or expected
answer. Answer grading is separate from execution validation.

## Causal action and effect contracts

Every trace action has an action-specific payload. Current reads record their
source and value; revision checks bind the expected task revision to that prior
read; workflow reuse/avoidance binds one command and result to one receipt and
run; answers cite their source; and abstention carries no success claim. The
post-run validator checks action ordering, single-use cardinality, allowed
actions, revisions, evidence availability, source scope, action results, and
receipt bindings. It rejects reversed/check-after-use traces, duplicate
directives, missing results, mismatched revisions, and forged verification or
receipt fields. Any trace invariant violation marks execution failed and makes
the CLI exit nonzero; a low task score alone remains an experiment result.

Reconciliation cases bind the task to an original `effect_key`, run ID, command,
and revision. A synthetic canonical `EffectObservation` repeats those identities,
includes full owner/application/workspace/branch scope, outcome, observation ID,
and observation time. The action trace records the requested identity and scope
and the returned observation identity. The finite resolver matches all fields;
wrong/missing/ambiguous observations produce unknown and abstention. Uncertain
or partial results stay unknown. Confirming an already completed effect is
observation only; no workflow is retried. A tiny stateful fake verifies repeated
execution intent returns one receipt/effect count, but this is not native
idempotency or transaction evidence.

## Derived diagnostic support

Diagnostic `historical_derived` sources use the explicit `exact_all_v1` recipe:
support is required and nonempty, and every direct support must provide the
same exact subject/value claim. User correction support uses the existing narrow
assertion grammar. A claim without this recipe is marked eligibility-only and
cannot enter the answer policy, even if all permission edges are valid or the
rubric expects it. Permission revalidation still checks every dependency.
This finite rule is not semantic entailment and says nothing about future
generative consolidation. Production `DerivedMemory` schema 2 and `support-v1`
are unchanged; their separate component test remains distinct evidence.

## V2 control changes

V2 preserves the five-per-family and 3/1/1 split while improving the reviewed
counterfactuals:

- WF-03 carries a keyed original receipt and independently keyed canonical
  observation; WF-04 matches the current revision so workspace is the deciding
  guard.
- TF-03 is already observed at the task clock but has a future effective date.
- AU-02 isolates application mismatch; a separate workspace-only twin is
  exercised outside the scored denominator.
- CO-04 includes two independent failed run receipts; a one-failure control is
  exercised outside the scored denominator.
- IR-03 packs useful authorized answer evidence alongside an untrusted
  instruction, and the answer must use only the useful source.

Positive twins are also checked for workspace scope, application scope,
workspace scope, and a future-effective fact after it becomes effective.
Mutation probes remove one named scope/time guard at a time and must cause the
corresponding negative control to select unsafe evidence or fail. These
counterfactual probes do not inflate the four-arm case denominator.

## Outcomes, denominators, and evidence

The finite driver classifies task outcomes separately from execution validity.
Task pass counts are `synthetic_scripted_task_proxy`, not model quality.
Retrieval precision/recall, selected/packed/consumed IDs, action traces, source
age, and final packed coverage remain separate measurements. Unsupported and
truncated arms are identified and excluded from paired intersections; missing
native/model evidence stays null/unverified, not zero. No significance or
natural-frequency claim follows from this curated corpus.

The manifest binds tested Git revision and dirty state, source/fixture/schema/
runner/policy digests, seed, budgets, Python/dependencies, null model/provider,
arm ordering, evidence class, and semantic result digest. Two executions must
match, fixture and source bytes must remain unchanged, and elapsed/CPU samples
are excluded from semantic hashes. Fresh in-memory timings are descriptive only.
Serialized JSON bytes are not physical/index bytes; physical database usage,
provider quota, real model quality, deployed identity/grants, and physical
deletion remain unverified.

Run `make memory-task-eval` with `backend/.venv/bin` on PATH. The CLI accepts
`--fixtures PATH` and `--output PATH`, restricted to root `artifacts/mem0/`.
It writes ignored manifests, per-case rows, aggregates, and separate timings.
There is no live/provider mode. Existing memory evaluation targets and Phase 36
status semantics remain unchanged.

# MEM-0 benchmark contract v1

Pre-registered 2026-10-28 before arm comparison. Scope: synthetic offline component
and scripted task proxy, never measured model competence or production readiness.
Typed source/case/rubric contracts live in `evaluation/memory_task_contracts.py`.

Thirty public synthetic cases: five each of workflow, project, correction,
temporal, authorization and irrelevant. Within each family: three development,
one calibration, one frozen holdout. Frozen means published and not tuned after
comparison, not secret. Implementation review checks source/rubric rationale;
independent review remains a separate acceptance gate. All IDs and referenced
sources must resolve; timestamps are explicit UTC; source bodies are bounded;
fixture versions and digests identify changes. A changed corpus needs a new
experiment identity and recorded rationale, not an overwritten result claim.

## Inputs, authority and packing

The harness binds synthetic owner/app/workspace/branch, clock, revision, grants
and transitions. Source content cannot grant access. Current canonical evidence
is identical across arms and retained in the mandatory task input. History is
eligible only within scope, branch, observation/effective time, privacy, permission
and complete support constraints. Pre-query and post-selection transitions are
distinct. Source/version dependencies are rechecked by the shared builder and at
driver consumption. Diagnostic history uses an explicitly synthetic resolver;
legal v1 assertions use actual `MemoryRetriever` and `MemoryPermissionRevalidator`
with in-memory canonical repositories and lifecycle transitions. Deployed app
registration/grant identity is unverified, not simulated equivalence.

| Arm | Contract |
| --- | --- |
| none | No historical retrieval or injection; current canonical task context retained. |
| fixed | Actual fixed retriever, legal v1 candidates, real assembler and memory dependency graph. Procedures/project knowledge outside current contract are recorded unsupported; no forged v1 record. |
| full_eligible_history | Chronological authorized history through shared `ContextBuilder`; bounded by identical total and historical source budgets. Any dropped eligible history means truncated, excluded from feasible paired task comparisons. |
| gold_authorized | Grader-owned reference selector supplies only currently eligible sources through the same builder. Gold refs never authorize access. Evidence-availability diagnostic, not an agent ceiling. |

All arms use the same input/output reserves, historical cap, fake word-unit token
counter, current evidence, task, fake tools and scripted policy. Fixed top-K/item
limits are disclosed capability differences. Source text and structured diagnostic
facts are data. Supported v1 sources use an identical narrow assertion parser
across arms; diagnostic facts/receipts are not runtime memory schemas. Selected
and actually packed IDs are distinct. No task driver may see arm, split, gold IDs,
rubric or expected answer. The final driver view contains only packed evidence
and current task inputs. Grading happens afterwards.

## Tasks, outcomes and metrics

A finite scripted task policy reads relevant facts, checks current revisions,
inspects simulated receipts, chooses an answer/reuse/reconcile/abstain action,
and records evidence IDs, revision and receipt verification. It uses task operation
and visible source authority, never fixture IDs or grader labels. Fake tools have
no network or real effects; repeated runs cannot cause external writes. Expected
actions, forbidden actions, exact answer and citation requirements are independent
grader inputs. Blanket abstention fails useful-answer/required-action rubrics.

Report task metrics as `synthetic_scripted_task_proxy`; retrieval precision/recall,
gold coverage and final packed coverage are separate. Task failures are research
outcomes; invariant/schema/replay failures fail the command. Missing model/native
evidence remains null/unverified. Unsupported and truncated arms are excluded
with IDs/reasons from paired evaluable intersections; never turn missing into 0.
Report by arm/family/split, raw numerators and denominators, family macro means,
paired case deltas/ties versus none and fixed. No significance claim for curated
cases. Real-model quality is unverified and no provider adapter is dispatched.

Hard validity failures: unauthorized/future/forgotten packed or consumed source,
grader leakage, source-version mismatch, successful workflow from unknown/failed
receipt, or over-budget context. Failures dominate run status; a task fail cannot
hide an invariant failure. Unverified external evidence does not become passed
because offline execution succeeded.

Manifest binds Git HEAD and dirty state, source tree/configuration and lockfile
digest, fixture/schema/rubric/runner/policy identities, seed, Python/dependencies,
machine profile, budgets, null model/provider and deterministic result hash.
Semantic hashes exclude sampled elapsed/CPU time, generated-at time and paths;
latencies are separately reported p50/p95 observations for fresh in-memory runs
(OS/import caches uncontrolled). Logical embedding calls and serialized metadata
bytes are synthetic, not quota, physical I/O, index size or native store cost.

Run `make memory-task-eval` with the backend virtualenv on PATH. The CLI accepts
`--fixtures PATH` and `--output PATH` (restricted to root `artifacts/mem0/`). It
runs twice, checks identical semantic digests and unchanged fixtures, and writes
manifest, per-case rows, aggregates and timing observations there. No live mode.
Tests must mutate grants, source epochs, branches, rubrics and receipts, not only
check fixture scores. Phase 36 blocker statuses remain canonical and unchanged.

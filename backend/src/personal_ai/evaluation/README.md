# Evaluation

This package owns deterministic evaluators, offline fixture builders, and their static data.
JSON fixtures live under `fixtures/<area>/`; output schemas live under `schemas/`. Evaluations
exercise services through synthetic inputs and do not establish provider, cloud, or deployment
behavior.

`make real-task-eval` runs a separate 12-case synthetic chat experiment across
direct, selected and eligible history. The digest-pinned corpus covers grounded
QA, coding continuity, multi-step research and safe denial. Scripted output
establishes E1 plumbing only. An opt-in local mode uses the same driver and
exports a content-free trace. See the [operator guide](../../../../docs/harness-excellence/local-inference.md).

memory benchmark adds `make memory-task-eval`: the active v2 corpus has 30 synthetic cases,
four historical-context arms, action-specific causal traces, keyed effect
observations, exact diagnostic-derived support, and actual fixed memory
retrieval/revalidation/packing where v1-compatible. The command runs twice and
writes sanitized semantic results and separate timings to ignored
`artifacts/mem0/`. It has no provider dispatch mode. Corpus v1 remains frozen
historical evidence. See the
[benchmark contract](../../../../docs/personal-ai-chapter-2/memory/mem-0-benchmark-contract.md)
and [baseline report](../../../../docs/personal-ai-chapter-2/memory/mem-0-baseline-report.md).
Unsupported and truncated cases have explicit paired-comparison exclusions;
scripted task proxy success is not measured model quality or native-store evidence.
The independent review and bounded remediation are recorded separately; fresh
independent re-verification remains a gate for accepting the baseline.

project knowledge adds `make memory-knowledge-eval`, a separate `mem1-paired-v1` corpus
with 20 stateful paired sessions (six tagged holdout cases). A trusted fake
executes Task A, issues a resolver-bound receipt, persists through the canonical
memory repository, then composes fresh Task B service/retriever/builder objects.
Task B performs a new scoped action and observes a distinct outcome. All arms
share Task A state, current facts, tools, clock, seed and budgets; only reuse
policy differs. Legacy `fixed` is explicitly unsupported for both new kinds.
No-memory can rediscover workflows; historical knowledge reduces repeated
discovery. Historical receipts cannot count as new task success.

`knowledge_runtime.py` is the hermetic issuer/tool authority, never production
composition. `memory_knowledge.py` separates the driver input from review/rubric
metadata and validates action ordering, receipt identity, permissions, current
revision and duplicate effects. Safety violations fail execution and the CLI;
lower task scores remain separate. Two semantic replays must match; source and
fixture mutation during a run fails. Results/manifests go to ignored
`artifacts/mem1/`. Token units and JSON sizes are estimates, and latency is the
local fake runtime. Native resource and model-mediated metrics stay unverified.
Cases are author-reviewed; independent review, including fixture review, is
still required. A holdout tag does not establish a blind model study.

system conformance's `verification/` program indexes existing executable contracts and
original acceptance obligations in a strict versioned matrix. `make
integrated-verification` executes offline rows, captures exact parametrized case
receipts, and generates matrix results, a blocker ledger, and a Markdown report
in the ignored root `artifacts/phase36/` directory. A nonzero exit means the local
execution failed; zero does not mean release-ready. Missing external evidence
keeps affected capabilities unavailable. Reports contain synthetic identifiers
and numeric observations, never prompts, credentials or provider output bodies.

The declared fault scenarios refer to owning regression tests; the runner does
not add a parallel runtime or duplicate lifecycle authority. Use `make
backend-test-offline` for the full environment-independent suite. Native-store,
cloud, live provider, domain and browser gates remain separate. Read the
[verification model](../../../../docs/personal-ai-chapter-2/phase-36/architecture.md)
before interpreting results or adding evidence classes.

`domains/fixtures.py` remains domain-owned because the API exposes those synthetic comparisons
as a supported demo endpoint as well as using them in offline evaluation.

memory controls adds `make memory-control-eval`: 36 synthetic control probes in
`fixtures/memory/mem2-control-v1.json`, with 30 development and six public tagged
holdout cases. Driver inputs exclude scoring expectations. The evaluator exercises
real scoped service/tool contracts under a hermetic host, not a live model loop.
Native transaction/resource and HTTP/UI checks are separate tests, not extra
benchmark cases. Review means pending review only; correction is unsupported.

`make memory-navigation-eval` runs a separate hash-locked, author-visible study
with 40 cases and ten arms, replayed twice. The additive
`fixtures/memory/memory-navigation-v1.json` and `memory-navigation-study-v1.json`
pre-register the dataset, scorer, serializer, policies and comparators. Historical
corpora and source locks are unchanged. Outputs in ignored
`artifacts/memory-navigation/results.json` retain all 400 attempted rows, statuses,
exact-answer/attribution and false-support scores, safety vetoes, retrieval metrics,
counted fixture token units, lookup/index timings, source hashes and per-family
paired deltas. Unexpected exceptions retain failed rows and fail the command.

The consumer receives serialized cards and task text only, without rubrics or
source access. All arms share fixture scope/currentness preflight, index checks,
serializer, counter, clock, two-second deadline and 4,096/1,024 context/memory
ceilings. Timing includes that shared preflight; it is script overhead, not a
production latency comparison. Request-aware/adaptive packing use lexical recall
because real semantic evidence is unavailable. Fixed/semantic/hybrid unsupported
rows remain in their original denominator, alongside scope denials and cancelled
or expired attempts. Full eligible context must fit in full. Fake-vector adapter
and fusion tests are separate from measured arms. Actual provider usage and model
quality are unmeasured; cost is offline/no charge. Small author-visible families
get descriptive paired mean/variance, without confidence or generalization claims.
See the [dated receipt](../../../../docs/memory/2026-11-04-retrieval-implementation.md)
and its retained machine-readable measurements.

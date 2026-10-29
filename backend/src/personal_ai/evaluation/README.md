# Evaluation

This package owns deterministic evaluators, offline fixture builders, and their static data.
JSON fixtures live under `fixtures/<area>/`; output schemas live under `schemas/`. Evaluations
exercise services through synthetic inputs and do not establish provider, cloud, or deployment
behavior.

MEM-0 adds `make memory-task-eval`: the active v2 corpus has 30 synthetic cases,
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

MEM-1 adds `make memory-knowledge-eval`, a separate `mem1-paired-v1` corpus
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

Phase 36's `verification/` program indexes existing executable contracts and
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

MEM-2 adds `make memory-control-eval`: 36 synthetic control probes in
`fixtures/memory/mem2-control-v1.json`, with 30 development and six public tagged
holdout cases. Driver inputs exclude scoring expectations. The evaluator exercises
real scoped service/tool contracts under a hermetic host, not a live model loop.
Native transaction/resource and HTTP/UI checks are separate tests, not extra
benchmark cases. Review means pending review only; correction is unsupported.

# Memory experiments

The canonical read, rank, pack and lifecycle implementations remain under
`backend/src/personal_ai/memory`; this directory is not a second runtime.

Run `make memory-eval memory-lifecycle-eval memory-optimization-eval`.
The original baseline is frozen in
`backend/src/personal_ai/evaluation/fixtures/memory/memory-baseline-v1.json`.
The paired runner uses 20 synthetic fixture families and the same admitted corpus,
worker, retriever and shared builder for fixed, compact and consolidated variants.
It includes maintenance and query embedding calls, jobs, CPU/time, serialized bytes,
claim support, duplicate context and complete dependency coverage. Native database,
index, provider quota, downstream quality and authority-confusion measurements
remain missing rather than being imputed from fakes.

Promotion requires zero false-memory/scope/invalidation/conflict regression, full
source support, no recall regression, at least 5% aggregate token savings, and
observed downstream quality plus native Postgres resources. No coverage is promoted.
Exact pgvector remains the baseline; no ANN, lexical/hybrid generator or model
adjudicator is installed. Bounded semantic clusters are proposals, not merge proof.

The existing source-fallback boundary fixture now uses a 57-token cap (fixture v2)
so fallback still executes after shorter v2 views. A separate regression proves the
compact view fits at the previous 58-token cap. Historical pre-change observations
remain intact in the original baseline and Git revision.

See [Phase 34 implementation report](../../docs/personal-ai-chapter-2/phase-34-implementation-report.md).

## MEM-0 task baseline

Run `make memory-task-eval` with `backend/.venv/bin` on PATH. The hermetic CLI
`python -m personal_ai.evaluation.memory_task_baseline` accepts `--fixtures PATH`
and `--output PATH` (within root `artifacts/mem0/`). It runs 30 public synthetic
cases from the active v2 corpus across `none`, `fixed`,
`full_eligible_history`, and `gold_authorized`. Corpus v1 and its result digest
are retained as historical evidence.
There is no live/paid dispatch option. The original evaluators are unchanged.

Results distinguish selected, packed and consumed sources; current canonical
task evidence is shared by every arm. Procedures are unsupported by current v1
memory; diagnostic gold cannot grant permissions. V2 checks causal action
ordering/results, binds reconciliation to the original effect key and scope,
and admits diagnostic derived claims only under exact support. Task outcomes are a finite
`synthetic_scripted_task_proxy`, not LLM task quality. Native bytes/quota and real
model quality remain null/unverified. See
[MEM-0 contract](../../docs/personal-ai-chapter-2/memory/mem-0-benchmark-contract.md),
[ADR](../../docs/personal-ai-chapter-2/memory/mem-0-architecture-adr.md) and
[results](../../docs/personal-ai-chapter-2/memory/mem-0-baseline-report.md).

## MEM-1 paired knowledge loop

`make memory-knowledge-eval` freezes a separate 20-case `mem1-paired-v1` suite.
It compares no-memory, unsupported legacy fixed, verified schema-3 knowledge,
and full eligible history. The split is 4 workflow, 3 project-decision,
3 currentness, 6 scope/lifecycle, and 4 adversarial/non-beneficial cases, with
six tagged holdout cases. Source authority and final actions use a stateful fake;
Task A and Task B have separate run/result identities. All valid workflows can
also be rediscovered by the no-memory tool path; comparisons report repeated
discovery, newly observed results, source use, token estimates and JSON bytes.
This finite proxy is not measured real-agent lift. Independent fixture review
and production issuer/identity/deletion acceptance remain separate gates.

The CLI runs two semantic replays and writes ignored `artifacts/mem1/` manifests,
per-case traces and observed fake-runtime timing. Counterfactual tests cover
source/branch/revision/permission changes, before-pack and before-use revoke,
forged outcomes, wrong receipt, duplicate directives and causal action order.
The fixture SHA256 is pinned in `test_memory_knowledge_evaluation.py`; MEM-0 v1/v2
bytes and historical acceptance records are unchanged. See the
[MEM-1 ADR](../../docs/memory/mem-1-contract-adr.md) and
[report](../../docs/memory/mem-1-implementation-report.md).

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

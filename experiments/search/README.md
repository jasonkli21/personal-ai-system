# Search experiments

Use this area for query planning, source selection, extraction, deduplication, reranking, entity resolution, and freshness-policy experiments.

Phase 33's executable paired runner is `make retrieval-eval`. It uses the actual
research API composition with an installed synthetic adapter, the shared context
builder, and strict literal synthesis/citation validation. The 18 public synthetic
cases and the pre-change source/metric freeze live in
`backend/src/personal_ai/evaluation/fixtures/research/retrieval-{heldout,baseline}-v1.json`.
Never overwrite that historical baseline to make a candidate look successful.

Compare the literal control with compact extractive representation, an appended
qualifier, and bounded two-query expansion. No inference rewrite/compression,
lookup/fetch, crawler, semantic index, or live quality is claimed. Quota remains
unknown in the synthetic adapter. Full literal retention, exact support, source
rights and freshness are hard boundaries; judging requires either at least five
percentage points of supported-answer improvement or 10% fewer tokens at equal
quality, no extra search calls/quota, and at most 20% latency overhead. Synthetic
evidence and insufficient independent coverage always deny promotion.

Optional `python -m personal_ai.evaluation.retrieval --persist-owner <canonical-owner>`
uses the factory's Postgres experiment repository (migration 026) and optional P20
artifact service. Compact summaries contain identifiers/numeric measurements;
bulky paired metric batches use P20. Raw queries, source bodies and private model
outputs are not retained by this runner. Optional artifact failure preserves the
compact non-promoted results; it does not enable another storage backend.

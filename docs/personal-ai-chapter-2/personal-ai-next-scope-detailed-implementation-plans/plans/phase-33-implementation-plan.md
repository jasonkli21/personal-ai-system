# Phase 33 implementation plan — Search and evidence retrieval optimization

Renumbered from former Phase 25. This revision preserves evidence identity, source-rights, bounded-research, search-quota admission, storage, provenance, and measurable-improvement requirements while making the retrieval pipeline, experiment catalog, evidence contracts, ranking/packing semantics, and promotion gates explicit.

## Scope boundary

**Goal:** Give weaker/free models higher-quality external evidence per unit of search quota, context token, latency, and storage without weakening provenance, source rights, freshness, conflict visibility, or bounded research.

Phase 33 begins **after the context planner has decided that external/search evidence is required**. It optimizes how search queries are formed, how candidate evidence is collected and normalized, how duplicates/conflicts/freshness are handled, how evidence is reranked/diversified, and how a small supported evidence package is packed for inference.

### Normative commitments

- Benchmark the implemented search/snippet path before introducing rewrites, decomposition, hybrid candidate sources, reranking, or compression.
- Run constraint-preserving query-rewrite/decomposition experiments.
- Add hybrid or source-specialized retrieval only where measured benefit justifies it.
- Preserve literals that affect correctness: negation, numbers, units, dates, quoted identifiers, entity names, domain/source allowlists, and explicit user constraints.
- Reuse Phase 19 search quota/admission. Every physical search/lookup/fetch operation must remain bounded and admitted.
- Keep search-provider contracts separate from inference-provider contracts.
- Preserve exact source identity, observation identity, claim/support mappings, source rights, timestamps/freshness, sensitivity, and declared export consistency.
- Improve conservative deduplication, conflict visibility, diversity, freshness handling, reranking, compression, and token-aware packing.
- Label derived/compressed evidence as derived; never rewrite it as though it were an original passage.
- Store compact searchable experiment/evaluation summaries in Postgres and permitted bulky outputs in Phase 20 GCS.
- Promote only strategies that improve supported-answer/evidence quality or resource efficiency on held-out tasks without provenance, rights, constraint-retention, or budget regression.

### Acceptance criteria

A promoted retrieval variant measurably improves declared evidence/end-answer outcomes or materially reduces resource use at equal quality, preserves exact provenance/support/conflict mappings, stays within immutable research/search budgets, and retains deterministic fallback.

## Role in the request pipeline

```text
ContextPlan says "external evidence required"
        ↓
constraint extraction / query intent
        ↓
query strategy
        ↓
admitted SearchAdapter search/lookup/fetch operations
        ↓
normalized evidence observations
        ↓
identity + rights + freshness + dedupe/conflict processing
        ↓
rerank / diversify
        ↓
extractive or support-mapped derived compression
        ↓
token-budget packing
        ↓
ContextBuilder / inference
        ↓
supported-answer evaluation
```

Phase 33 does not grant source access, change cross-app permissions, or choose the inference endpoint.

## Current state and reuse

Reuse deterministic constraint-preserving query planning, existing search adapters, snippets, freshness/dedupe behavior, literal grounded synthesis, bounded research budgets, source-policy/rights gates, Phase 19 admission/accounting, Phase 20 artifact storage, and Phase 22 evaluation identity.

Brave is an adapter/profile fact, not the definition of research. Do not add another live search provider solely to prove extensibility.

## Phase 10 storage dependency

- Postgres owns compact evaluation profiles/summaries, normalized evidence metadata where already assigned, strategy identity, and support/conflict relationships under the existing storage contract.
- Phase 20 GCS owns permitted bulky retained raw outputs/artifacts.
- Do not create a duplicate runtime ledger.
- Do not store bulky raw search bodies in operational/relational stores merely for experimentation.

## Prerequisites

Required phases: 19, 20, and 22, plus standing Phase 10 storage ownership and applicable policy/provenance foundations.

## Invariants

- Explicit constraints survive rewriting/decomposition.
- Query expansion cannot widen source/domain rights or immutable research budgets.
- Every physical search/lookup/fetch operation is admitted and accounted.
- New sources require existing source-policy/rights gates.
- Original passages remain immutable evidence observations.
- Derived compression has its own identity and exact support mapping.
- Conflicting credible evidence remains representable; reranking/compression may not silently erase conflict.
- Unverified rights or skipped live sources cannot count as validated quality gains.
- Search/research may not depend on provider-specific control flow in generic orchestration.
- No unbounded crawl, recursive research loop, or proprietary-grounding-only dependency is introduced.

## Retrieval strategy contracts

### `ResearchQueryPlan`

Logical fields should include:

- task/query identity;
- preserved hard constraints;
- entities and aliases where safely derived;
- freshness/time requirements;
- source/domain allowlists or exclusions;
- bounded query list;
- per-query operation type (`search`, eligible `lookup`, eligible `fetch`);
- result/source/time budgets;
- strategy ID/version;
- reason codes for decomposition/expansion.

All generated subqueries remain within the original authorized source and budget envelope.

### Candidate query strategies

P33.0 may evaluate, but need not promote, a bounded catalog such as:

1. literal/baseline query;
2. constraint-preserving rewrite;
3. entity-aware rewrite;
4. freshness-aware rewrite;
5. bounded multi-query expansion;
6. bounded decomposition for multi-part comparisons;
7. source-specialized query templates through the existing adapter seam.

No strategy is mandatory merely because it is listed. Add only those supported by failure data.

### `EvidenceObservation`

Normalize retrieved evidence around stable identities and immutable source facts:

- observation ID;
- source/document/result identity;
- source URL/ref where permitted;
- retrieval adapter/profile;
- original passage/snippet or artifact reference;
- retrieved/published/observed timestamps as available;
- source-rights/policy metadata;
- sensitivity;
- query/operation lineage;
- content fingerprint;
- freshness metadata;
- source authority/type metadata where deterministically known.

Do not conflate observations with claims or derived summaries.

### `EvidenceClaim` / support relationships

Where claim-level evaluation/compression is used, retain:

- claim ID;
- claim text/structured proposition;
- supporting observation/passage IDs;
- optional contradicting observation/claim IDs;
- derivation method/version;
- confidence only when meaningfully defined;
- exact support spans where the current evidence model supports them.

### `DerivedEvidence`

Compression/synthesis used as context must carry:

- derived evidence ID/version;
- source observation/claim IDs;
- transformation/strategy version;
- exact support coverage;
- omitted/conflict markers where relevant;
- token/byte reduction metrics.

Derived evidence never impersonates the original source.

## Candidate retrieval and "hybrid" semantics

"Hybrid" in this phase means combining **bounded evidence candidate mechanisms behind the existing research/search seams**, not building an unbounded crawler or merging model routing with search.

Candidate mechanisms may include, where already available or justified:

- web search adapter results;
- permitted lookup/fetch from identified sources;
- source-specific adapters;
- keyword/lexical retrieval over retained permitted research artifacts;
- semantic retrieval over permitted retained research/evidence if a compatible existing vector seam exists.

Any local semantic index is derived/rebuildable, source-rights aware, and subject to Phase 10/20 ownership. A new large vector subsystem is not required to satisfy Phase 33.

## Ranking, dedupe, diversity, and freshness

### Hard filters before scoring

Before candidate ranking:

- source rights/policy;
- scope/sensitivity;
- operation/research budget;
- freshness bounds that are mandatory for the task;
- malformed/unavailable source handling;
- declared source/domain allowlists/exclusions.

### Candidate signals

P33.1 may experiment with deterministic or measured combinations of:

- lexical constraint match;
- semantic/task relevance;
- exact entity match;
- freshness;
- source authority/type;
- novelty/diversity;
- duplicate similarity;
- coverage of uncovered subquestions/claims;
- conflict value;
- passage density/support usefulness.

Do not encode an opaque score as source truth. Persist strategy/version and enough component metadata to reproduce evaluation.

### Deduplication

Use conservative identity/fingerprint/canonical-source handling. Near-duplicate suppression must not collapse materially different timestamps, versions, or conflicting claims.

### Conflict visibility

If credible sources disagree, packing should retain enough evidence to surface the disagreement rather than choosing one merely because it ranks slightly higher.

## Packing and compression

Prefer extractive packing where it satisfies the token budget.

Derived compression is allowed only when:

- support mapping remains exact enough for downstream citation/provenance;
- constraints/numbers/units/dates are preserved;
- conflict/uncertainty is not silently removed;
- the compression operation is bounded and accounted if it uses inference;
- the original evidence remains referenceable.

Packing should optimize evidence coverage per token rather than simply selecting the highest individual scores.

## Evaluation design

### Held-out task families

Include:

- freshness-sensitive facts;
- numeric/unit/date constraints;
- explicit negation;
- entity ambiguity;
- multi-source comparisons;
- multi-part questions requiring decomposition;
- conflicting sources;
- duplicate syndicated sources;
- stale high-ranking results;
- source/domain allowlists;
- quota-constrained research;
- sparse-result queries;
- queries where no rewrite is beneficial.

### Metrics

Measure at least:

**Constraint retention**
- literal constraint survival;
- rewritten-query violations;
- source allowlist/exclusion compliance.

**Evidence quality**
- relevant evidence recall;
- precision/useful-passage rate;
- freshness compliance;
- duplicate rate;
- source diversity;
- conflict retention;
- exact support mapping coverage.

**Answer quality**
- supported-answer rate;
- unsupported-claim rate;
- citation/support correctness;
- downstream task score.

**Resource**
- physical search/lookup/fetch calls;
- search quota;
- retrieved bytes;
- packed tokens;
- optional compression-model calls/tokens;
- end-to-end latency;
- retained artifact bytes.

**Coverage**
- task families/source profiles with sufficient evidence to claim improvement.

## Work packages

### P33.0 — Baseline, constraint-preserving query experiments, and retrieval contract

Freeze/version the current search/snippet path and create held-out benchmark tasks.

Implement/clarify `ResearchQueryPlan`, evidence identities, and strategy tracing. Evaluate only justified query variants such as constraint-preserving rewrite, bounded expansion, decomposition, entity-aware, or freshness-aware strategies.

Every generated query must retain hard constraints and remain within admitted budgets/source rights.

Keep substitution local to the existing `SearchAdapter`/applicable lookup/fetch seam. Research must not require Brave-specific generic orchestration.

**Acceptance:**
- Baseline metrics exist before optimization.
- Rewrites/decomposition preserve all hard constraints in fixtures.
- Every physical operation is admitted/accounted.
- No query strategy widens source rights or immutable budgets.
- Strategy identity/configuration is reproducible.

### P33.1 — Evidence identity, dedupe, freshness, reranking, diversity, and packing

Normalize candidate evidence identities and improve conservative dedupe/freshness/conflict handling.

Add measured reranking/diversity logic behind a replaceable local strategy seam rather than hard-coding one scoring formula into adapters.

Implement extractive packing first. Add derived compression only where token savings or answer quality justify it, retaining exact support mappings and original evidence references.

**Acceptance:**
- Duplicate suppression does not erase meaningful version/conflict differences.
- Packing preserves source/support/conflict identities.
- Derived compression is separately labelled and support-mapped.
- Ranking/packing decisions are reproducible from safe trace metadata.

### P33.2 — Paired end-answer and resource evaluation

Run paired held-out evaluation against the frozen baseline.

Measure constraint retention, evidence recall/precision/freshness/diversity/conflict visibility, supported answers, unsupported claims, quota/calls/tokens/latency, and retained artifact cost.

Store permitted bulky experiment outputs in GCS and compact searchable summaries in Postgres.

Do not count skipped live-source checks, unverified rights, or unavailable adapters as passed quality.

**Acceptance:**
- Promotion evidence shows end-answer/evidence or resource benefit without provenance/rights/constraint regression.
- Report coverage by task/source class.
- Strategies lacking evidence remain experimental/default-off.

### P33.3 — Promotion, fallback, and operational diagnostics

Version promotion policy and strategy configuration.

Support task/profile-scoped promotion rather than global replacement. Keep the baseline path available.

Test:

- search provider timeout/error;
- partial query-plan execution;
- quota exhaustion;
- stale source;
- malformed result;
- missing rights metadata;
- duplicate floods;
- contradictory sources;
- compression failure;
- artifact-store optional/required failure according to existing contracts.

Expose safe diagnostics for query strategy, rejection reason, evidence counts, packing decisions, and resource use without leaking private/raw evidence into ordinary telemetry.

**Acceptance:**
- Fallback does not widen budget or rights.
- Failed optimization cannot turn into unbounded research.
- Promoted strategy/coverage can be rolled back without adapter/orchestration rewrite.

## Promotion criteria

Before judging a candidate, P33.0/P33.2 must define explicit thresholds covering:

- zero source-rights/constraint regression;
- bounded unsupported-claim rate;
- evidence freshness/coverage target;
- meaningful supported-answer or resource-efficiency improvement;
- maximum allowed search/model-call increase;
- maximum latency overhead;
- sufficient held-out coverage.

A strategy that improves retrieval recall by doubling scarce search calls without meaningful downstream benefit should not be promoted under a strict-free optimization goal.

## Requirement coverage

All former Phase 25 commitments remain represented: query-rewrite experiments; hybrid/source-specialized retrieval where justified; dedupe/freshness/reranking; evidence compression/packing; Phase 19 search-quota admission; Phase 20 GCS for bulky permitted artifacts; measurable end-answer improvement with exact provenance.

## Explicit non-goals

- Changing context-source authorization (Phase 15/30/32).
- Memory retrieval or memory lifecycle/consolidation (Phase 34).
- Learned model endpoint routing (Phase 35).
- Unbounded crawling or web indexing.
- Adding live search providers solely for architectural demonstration.
- A generic RAG framework replacing existing repository seams.
- Treating compressed evidence as original source text.
- Persisting unrestricted raw web corpora.

## README maintenance

Review the repository-root `README.md` before closing the phase. Update it only if implemented current-state facts change.

## Targeted verification and closeout

Run applicable tests, lint, typecheck, build, evaluation runners, and `git diff --check`.

Offline deterministic fixtures must cover constraint retention, identity/dedupe/conflict semantics, packing, and failure handling without credentials/network/private data. Live provider/search checks are opt-in and remain **unverified** when skipped.

Implementation/release evidence must record:

- files/interfaces;
- strategy versions;
- tested revision/configuration;
- held-out task coverage;
- baseline and promoted metrics;
- physical search/model operations;
- quota/token/latency/storage results;
- rights/source profiles tested;
- disabled gates and unresolved external checks.

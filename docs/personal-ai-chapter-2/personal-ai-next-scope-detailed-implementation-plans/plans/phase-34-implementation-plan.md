# Phase 34 implementation plan — Memory retrieval, compression, hygiene, and consolidation

Renumbered from former Phase 26. This revision preserves the original retrieval/lifecycle/provenance scope and the Postgres/pgvector substitution for the retired Firestore vector path, while integrating the Context Compression Plan: hierarchical retrieval, task-conditioned token budgeting, retrieval-time packing/compression, exact and semantic deduplication, bounded consolidation, contradiction/supersession handling, freshness policy, summary invalidation/refresh, and provenance-preserving compaction.

The phase remains an evolution of the existing memory repository/retriever/ranker/extractor/lifecycle-policy seams. It must **not** introduce a separate memory-plugin platform.

## Scope boundary

**Goal:** Improve the relevance, compactness, freshness, and maintainability of durable AI-owned personal context so weaker/free models receive a small, high-signal, source-attributed memory set without weakening lifecycle, provenance, scope, authority, sensitivity, or embedding-space correctness.

Phase 34 has two coupled optimization surfaces:

1. **Read path:** retrieve/rank/pack the best currently valid memories for a task.
2. **Maintenance path:** keep the durable memory corpus from accumulating exact duplicates, redundant near-duplicates, stale summaries, unresolved supersession that should be explicit, or unnecessarily verbose active representations.

It does not make Personal AI authoritative for domain state. Domain-owned facts remain authoritative through domain providers/APIs.

### Normative commitments

- Benchmark the validated current retrieval behavior before changing ranking/index/packing/consolidation strategies.
- Compare exact pgvector baseline against hybrid/entity-aware/lexical/structured candidate approaches where justified.
- Apply owner/application/workspace, permission, lifecycle, provenance, source-branch, embedding-space, and sensitivity filters **before ranking**.
- Add task-conditioned memory selection and budgets only where measured benefit exists.
- Prefer exact search until measured latency/compute/resource evidence justifies ANN/index complexity.
- Preserve current compatible 2,048-dimensional embedding values exactly; no truncation, half-precision conversion, silent re-embedding, or mixed incompatible vector spaces.
- Keep canonical memory separate from rebuildable derived embedding/index material.
- Add retrieval-time extractive packing and bounded support-mapped compression where justified.
- Add cheap deterministic write-side hygiene: exact fingerprint/idempotent dedupe and explicit lifecycle handling.
- Add semantic near-duplicate consolidation only as a **derived, provenance-preserving** representation; original source memories remain traceable and are not silently destroyed.
- Make contradiction/supersession explicit. Recency alone does not override higher-authority source/domain facts; unresolved conflicts may remain unresolved.
- Distinguish stable from volatile memories/facts for freshness/refresh policy rather than applying one universal decay rule.
- Refresh/invalidate summaries and consolidated representations when their source dependencies change, expire, are revoked, are forgotten, or are superseded.
- Use embeddings for candidate discovery; use an LLM only for small ambiguous consolidation/adjudication batches where deterministic rules are insufficient and the operation is strictly bounded/admitted.
- Preserve enough original memories/provenance so a compact active representation never becomes an unverifiable false memory.
- Measure irrelevant, missed, stale, false, duplicate, contradictory, and over-compressed context as well as tokens/latency/storage/compute and downstream answer support.
- Revalidate lifecycle/authorization dependencies at injection/reuse; caches may not resurrect revoked/deleted context.
- Keep a deterministic/retrieval baseline and safe rollback path for promoted variants.

### Acceptance criteria

A promoted read or maintenance strategy improves declared relevance/compactness/resource metrics without false-memory, attribution, authority, sensitivity, scope, lifecycle, embedding-compatibility, or deletion/revocation regression. Consolidated/compressed representations retain exact source dependency coverage, and original provenance remains recoverable.

## Role in the memory lifecycle

Target logical lifecycle:

```text
conversation/domain observation
        ↓
existing extraction/admission semantics
        ↓
candidate memory
        ↓
scope + provenance + lifecycle metadata
        ↓
exact fingerprint/idempotent dedupe
        ↓
durable memory
        ↓
(optional bounded maintenance)
near-duplicate candidate discovery
        ↓
deterministic merge/supersession where safe
or bounded ambiguous-batch adjudication
        ↓
derived consolidated representation
        ↓
dependency-linked summary/compact active view
```

Retrieval:

```text
MemoryQuery
   ↓
hard owner/app/workspace/policy/lifecycle/embedding filters
   ↓
candidate generators
   ├── exact/pgvector semantic
   ├── entity/structured metadata
   ├── lexical/full-text where justified
   └── bounded recency/relationship candidates
   ↓
candidate merge + identity dedupe
   ↓
task-conditioned ranker
   ↓
diversity/redundancy control
   ↓
token-aware budget allocation
   ↓
extractive packing
   ↓
(optional support-mapped derived compression)
   ↓
ContextBuilder
```

## Current state and reuse

Reuse validated fixed/scored/consolidated memory retrieval and lifecycle experiments, existing memory extraction/admission semantics, provenance/source references, supersession/forgetting states, Postgres canonical memory, pgvector embedding metadata, and shared ContextBuilder.

Phase 10 owns canonical memory/vector state in Postgres/pgvector while preserving logical source/lifecycle semantics. This phase does not redo the Phase 10 migration.

Where existing conversation-summary refresh/lifecycle mechanisms exist, extend their dependency invalidation rather than building a second summary system.

## Phase 10 storage dependency

Benchmark the Phase 10 exact pgvector search over lossless arrays, including query-time casting and original-value numerical boundaries.

An expression/ANN index is an evaluated optimization, not a default migration step. Preserve:

- embedding provider;
- model;
- dimensions;
- normalization;
- task semantics;
- embedding-space version;
- original vector values.

A new embedding space requires a separately authorized migration/re-embed/re-index plan.

Postgres owns canonical durable memory, lifecycle/provenance metadata, compact queryable consolidation metadata, and memory evaluation summaries. Permitted bulky experiment artifacts belong in Phase 20 GCS. Operational conversation timelines remain DynamoDB-owned under Phase 10; domain state remains external/authoritative.

No memory record class becomes canonical in two stores.

## Prerequisites

Required phases: 1, 10, 12, 16, and 22, plus applicable Phase 14–15 provenance/policy semantics.

## Invariants

- Existing lifecycle exclusions, source deletion/revocation, supersession, forgetting, and branch semantics remain binding.
- Owner/app/workspace and authorization filters precede candidate ranking.
- Authoritative domain state never becomes generic AI memory merely because it is useful.
- Memory is non-authoritative personal context unless an existing contract says otherwise.
- Embedding spaces are explicit and incompatible spaces fail closed.
- No silent embedding-provider migration.
- No lossy vector conversion without a separately evaluated migration.
- Derived consolidated/compressed memory has its own identity and dependency graph.
- Original provenance cannot be replaced by a model-generated summary.
- Deleting/revoking a source invalidates dependent active representations/caches.
- Consolidation cannot silently convert contradictory claims into a fabricated compromise.
- LLM maintenance calls are bounded, admitted, versioned, and optional; deterministic methods are preferred.
- Maintenance jobs cannot recursively trigger unbounded consolidation.
- Retention of original source memories follows existing lifecycle/retention policy; "compact active representation" does not mean unauthorized deletion.

## Memory query and retrieval contracts

### `MemoryQuery`

Logical fields should include:

- authenticated owner/request scope;
- application/workspace;
- task identity and typed requirements;
- query text/structured intent where already permitted;
- entity references/aliases;
- requested source/lifecycle classes;
- sensitivity ceiling;
- temporal/freshness constraints;
- memory item/token/time budgets;
- embedding-space requirement;
- retrieval strategy/version;
- policy/source dependency versions;
- request deadline.

### Candidate generation

Candidate generators are replaceable local strategies, not a plugin framework.

Potential generators:

1. exact pgvector semantic search baseline;
2. entity/structured metadata match;
3. Postgres lexical/full-text retrieval where measured useful;
4. recency/relationship/source-class candidates;
5. consolidated active-view candidates.

A "hybrid" strategy may merge multiple generators, but every candidate must already pass scope/lifecycle/embedding compatibility filters.

### Retrieval trace metadata

For evaluated/promoted variants record at least:

- retrieval strategy/version;
- ranker/version;
- packing/compression strategy/version;
- embedding-space identity;
- candidate origin(s);
- candidate scores/components where meaningful;
- inclusion/rank reason;
- exclusion reason;
- lifecycle/provenance state;
- consolidation/original-memory identity;
- packing decision;
- token contribution;
- final source dependency IDs.

## Ranking semantics

P34.0/P34.1 may evaluate deterministic combinations of:

- semantic similarity;
- lexical match;
- entity/relationship match;
- task relevance;
- source authority class;
- recency/freshness;
- durability/stability;
- explicit user importance where already represented;
- redundancy/diversity;
- current-vs-superseded state.

A possible hybrid score is an experiment, not a permanent architecture:

```text
semantic
+ lexical
+ entity
+ recency/freshness
+ durability
+ task relevance
- redundancy
```

Hard lifecycle/permission/embedding constraints are never merely score penalties.

## Task-conditioned budgets and retrieval-time compression

The shared builder should allocate a bounded memory budget by task rather than always using one fixed top-K.

Examples of dimensions the policy may consider:

- task requires personal preference vs factual external research;
- current application/domain;
- presence of authoritative domain context;
- conversation recency sufficiency;
- memory sensitivity;
- remaining endpoint context capacity.

Prefer, in order:

1. fewer directly relevant original memories;
2. extractive trimming/packing;
3. already-valid consolidated active representations;
4. newly derived compression only when measured beneficial.

Any derived packing/compression must retain original/derived IDs and exact source coverage. Compression is not new memory extraction or authority.

## Context Compression Plan: memory hygiene and consolidation

### Exact deduplication

Implement cheap deterministic protection first:

- stable idempotency/extraction identity;
- exact content fingerprint where appropriate;
- duplicate source-event/version detection;
- safe no-op on replay/retry.

Do not spend LLM calls on exact duplicates.

### Near-duplicate candidate discovery

Use existing embeddings/structured/entity metadata to propose small candidate clusters. Embedding similarity only proposes candidates; it does not itself authorize a merge.

Bound cluster size, source count, time horizon, and maintenance work per run.

### Consolidated memory representation

A consolidated memory is a **derived** record/view with:

- stable derived ID/version;
- covered original memory IDs;
- exact source/provenance dependencies;
- normalized statement/summary;
- lifecycle state;
- sensitivity at least as restrictive as all dependencies;
- authority/source-class metadata;
- creation/update strategy version;
- unresolved-conflict marker if applicable;
- refresh/invalidation state.

The system must be able to inspect which originals support it.

### Contradiction and supersession

Use deterministic evidence first:

- explicit source revision/version;
- explicit lifecycle supersession link;
- authoritative domain/source class;
- timestamps/validity windows;
- user-confirmed corrections where represented.

Recency may break ties only where semantically appropriate. Newer low-authority derived text must not override authoritative source state.

If two memories genuinely conflict and neither safely supersedes the other, retain the conflict. Retrieval/packing should expose the relevant current ambiguity rather than inventing certainty.

### Stable vs volatile freshness

Define a small explicit policy rather than universal decay:

- **stable** examples: long-lived preferences/identity facts where existing source semantics permit;
- **volatile** examples: temporary plans, current budgets, current location-like state, short-lived project status;
- **event/episodic** memories: useful history that may remain valid as history but should not masquerade as current state.

The exact categories must reuse existing source/lifecycle semantics. Freshness affects retrieval/refresh; it does not silently delete history.

### Summary/consolidation invalidation

Derived compact representations must be invalidated or refreshed when:

- a dependency is forgotten/deleted;
- permission/grant/source eligibility is revoked;
- a source memory is superseded/corrected;
- branch/replay lineage changes applicability;
- a volatile dependency exceeds its validity/freshness contract;
- an embedding/consolidation strategy version is retired where compatibility requires rebuild.

Invalidated representations cannot continue to appear through caches.

### Bounded maintenance triggers

Maintenance may run only under explicit bounded triggers such as:

- after a configured number of newly admitted memories;
- after major lifecycle/supersession changes;
- when a summary/consolidation dependency invalidates;
- during explicitly admitted cheap/background capacity if an existing job mechanism supports it.

This phase does not require always-on streaming consolidation.

### LLM adjudication

Use an LLM only for small ambiguous clusters after deterministic filtering cannot decide whether/how to consolidate.

Requirements:

- strict bounded batch/item/token limits;
- admitted/accounted inference;
- minimized source material;
- structured output;
- no authority decision delegated to the model;
- server validation of dependencies and lifecycle result;
- deterministic fallback to "do not consolidate."

## Index strategy

Exact pgvector remains the baseline.

Evaluate ANN/expression indexing only when the measured corpus size/latency/CPU warrants it. Evidence must include:

- recall loss vs exact search;
- downstream answer impact;
- storage/index size;
- build/update cost;
- query latency/CPU;
- free-tier resource implications;
- compatibility with 2,048d vectors and existing numeric precision.

Do not add ANN merely because it is conventional.

Smaller embeddings may be a future evaluated migration but are not a configuration flip. Any such experiment must separately measure recall, downstream quality, storage, CPU, and migration/re-index cost and requires explicit authorization outside this phase's silent implementation path.

## Evaluation design

### Held-out cases

Include at least:

- exact duplicate memories/retries;
- near-duplicate paraphrases;
- superseded memories;
- direct contradictions;
- unresolved conflicting memories;
- entity aliases;
- same owner across multiple apps/workspaces;
- sensitive memories;
- revoked/deleted dependencies;
- stale volatile memories;
- very old but still valid stable preferences;
- recent but irrelevant memories;
- sparse-memory users;
- large memory sets;
- clustered repetitive conversation-derived memories;
- episodic history vs current-state confusion;
- consolidation invalidation;
- embedding-space mismatch;
- vector search exact-vs-index comparisons if ANN is evaluated.

### Metrics

**Retrieval quality**
- relevant memory recall;
- precision/irrelevant-memory rate;
- stale-memory rate;
- false-memory rate;
- superseded-memory leakage;
- conflict visibility;
- entity resolution success.

**Compression/hygiene**
- exact duplicate rate;
- near-duplicate active-context rate;
- number of original memories represented by consolidated active views;
- compression ratio/tokens saved;
- source dependency coverage;
- invalidated-derived-record leakage = 0;
- unresolved-conflict preservation.

**Downstream**
- supported-answer quality;
- personalization usefulness;
- authority confusion rate;
- provenance correctness.

**Resources**
- retrieval latency;
- Postgres query/CPU cost;
- vector candidates scanned;
- index/storage bytes;
- packed tokens;
- maintenance job count;
- LLM maintenance calls/tokens;
- total strict-free quota use.

Optimize **quality per resource**, not one metric in isolation.

## Work packages

### P34.0 — Baseline, contracts, and Postgres/pgvector retrieval benchmark

Freeze/version current validated retrieval behavior.

Define `MemoryQuery`, candidate/result trace metadata, active/consolidated representation identity, and evaluation fixtures.

Benchmark exact pgvector over compatible vectors and compare only justified candidate generators (entity/structured, lexical/full-text, hybrid) on source-attributed held-out fixtures.

Require before ranking:

- owner/app/workspace;
- authorization/sensitivity;
- active source/lifecycle;
- source branch;
- embedding provider/model/dimensions/normalization/task/version;
- provenance compatibility.

Measure missed/irrelevant/stale/false memories, tokens, latency, and downstream support.

**Acceptance:**
- Baseline is reproducible.
- Scope/source/lifecycle/embedding filters are proven before ranking.
- Candidate origins/strategy versions are traceable.
- No ANN or new embedding space is assumed.

### P34.1 — Hierarchical retrieval, task-conditioned ranking/budgets, and extractive packing

Implement measured hierarchical retrieval through existing repository/retriever/ranker seams:

- bounded candidate generators;
- deterministic merge/identity dedupe;
- task-conditioned scoring/ranking;
- redundancy/diversity control;
- token-aware budget allocation.

Add Postgres lexical/full-text retrieval only if held-out evidence justifies it.

Prefer extractive packing and existing valid consolidated representations. Any new derived retrieval-time compression must retain exact original/source coverage and be bounded/accounted.

**Acceptance:**
- Task packing preserves exact source coverage and lifecycle/scope/embedding filters.
- Hard constraints are not score penalties.
- Promoted hybrid retrieval improves paired metrics or resource efficiency.
- Deterministic baseline remains available.

### P34.2 — Memory hygiene, deduplication, and bounded consolidation

Implement Context Compression Plan maintenance through existing memory seams.

1. Add/verify exact idempotent dedupe.
2. Produce bounded near-duplicate candidate clusters using compatible embeddings/metadata.
3. Deterministically consolidate/supersede where source/lifecycle semantics make the result unambiguous.
4. For small ambiguous clusters only, optionally use an admitted structured LLM adjudication path.
5. Create provenance-preserving derived consolidated records/views rather than overwriting original source truth.
6. Preserve unresolved conflicts.
7. Apply stable-vs-volatile freshness semantics.
8. Invalidate/refresh derived representations on dependency lifecycle changes.

Do not create a separate generic memory plugin framework.

**Acceptance:**
- Exact duplicates do not create duplicate durable active memories.
- Consolidated memories enumerate original dependencies/provenance.
- Contradictory evidence cannot be silently averaged into false certainty.
- Revoked/deleted/superseded dependencies invalidate affected active representations.
- LLM failure returns "no consolidation" safely.
- Maintenance is bounded and idempotent.

### P34.3 — Summary refresh, active-view compaction, and dependency invalidation

Extend existing conversation/memory summary refresh semantics so compact active representations remain synchronized with their dependencies.

Support:

- dependency graph/version identity;
- stale/invalid state;
- bounded refresh;
- cache invalidation;
- preservation of originals/history under existing retention policy.

Retrieval should normally prefer a small number of current high-signal memories/consolidated representations while retaining the ability to inspect 3–5 or another bounded set of current provenance-supporting originals where the context/inspection path requires evidence.

The exact provenance display count is a UI/evaluation parameter, not a hard storage rule.

**Acceptance:**
- Stale consolidated/summary records do not survive dependency invalidation.
- Compact active views remain traceable to originals.
- Refresh does not broaden permission or sensitivity.
- No record class becomes accidentally canonical in two stores.

### P34.4 — Promotion, index decision, fallback, and resource evaluation

Run paired held-out evaluation for retrieval, packing, hygiene, and consolidation variants.

Evaluate exact-vs-ANN only if baseline evidence shows a real bottleneck. Record why an index is or is not justified.

Define promotion by declared task/corpus/strategy coverage. Keep baseline retrieval and original-memory access paths available for rollback/inspection.

Recheck source branch/lifecycle/authorization at injection and later reuse. Source deletion is not ordinary forgetting and must propagate according to existing contracts.

**Acceptance:**
- Promoted retrieval/consolidation improves quality/compactness/resource metrics without false-memory/provenance/sensitivity regression.
- ANN, if adopted, has measured recall/resource evidence.
- Deterministic rollback is tested.
- Caches/derived representations cannot leak revoked context.
- Experiment identity and resource use are reproducible.

## Promotion criteria

Before promotion, define explicit thresholds for:

- relevant-memory recall/precision;
- stale/superseded/false-memory rates;
- conflict-preservation correctness;
- source dependency coverage;
- token reduction/packing efficiency;
- downstream supported-answer/personalization quality;
- retrieval latency/CPU;
- maintenance calls/quota/storage;
- invalidation correctness;
- application/workspace/sensitivity isolation.

A consolidation strategy that saves tokens but increases false-memory or authority-confusion risk must not be promoted.

## Requirement coverage

All original Phase 34/former Phase 26 commitments remain represented:

- benchmark current vs hybrid/entity-aware retrieval;
- task-conditioned selection/budgets;
- packing/compression experiments;
- measurement of irrelevant/missed/stale context;
- Postgres/pgvector exact-search baseline;
- lossless embedding compatibility and explicit migration requirements;
- deterministic fallback and lifecycle/provenance integrity.

The Context Compression Plan adds explicit hygiene/consolidation work without changing the system's authority model: exact dedupe, bounded semantic consolidation, contradiction/supersession semantics, stable-vs-volatile freshness, summary invalidation/refresh, compact active representations, and bounded LLM adjudication.

## Explicit non-goals

- Replacing domain-authoritative records with generic memory.
- Rewriting Phase 10 persistence migration.
- Building a separate memory plugin framework.
- Unbounded autonomous memory rewriting.
- Silent deletion of original provenance.
- Universal time-decay of all memories.
- Silent embedding-provider/dimension changes.
- ANN/index adoption without evidence.
- Treating an LLM as authority for contradiction resolution.
- Re-extracting all historical memories merely to satisfy this phase.
- Cross-user/shared memory.

## README maintenance

Review the repository-root `README.md` before closing. Update only if implementation changes current user/developer-visible facts.

## Targeted verification and closeout

Run applicable tests, lint, typecheck, build, migration-safe checks, evaluation runners, and `git diff --check`.

Offline deterministic fixtures must cover scope, lifecycle, dedupe, contradiction, invalidation, consolidation, packing, and embedding mismatch without credentials/private domain data. External Postgres/cloud/provider checks are opt-in and skipped checks remain **unverified**, not passed.

Implementation evidence must record:

- files/interfaces;
- memory/retrieval/consolidation strategy versions;
- embedding-space identities;
- exact/ANN decision and metrics if evaluated;
- held-out corpus characteristics;
- quality/false-memory/staleness/conflict metrics;
- token/storage/CPU/latency/quota results;
- dependency invalidation tests;
- disabled gates;
- unresolved external checks;
- exact promoted coverage.

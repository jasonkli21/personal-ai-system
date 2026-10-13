# Memory

This package owns durable user-memory contracts, extraction, retrieval, disclosure policy, and
lifecycle behavior. Memory remains a separate data class from time-sensitive external evidence.

## Entry points and boundaries

- Root modules own memory identity, extraction, retrieval, and general policy.
- `lifecycle/` owns lifecycle contracts, scoring, transitions, jobs, and lifecycle repositories.
- Backend-neutral memory effect coordination contracts live in `effects.py`; database adapters implement them under `personal_ai.persistence`.
- Lifecycle contracts, jobs, policy, and repositories live under `lifecycle/` and are imported from their owning modules.

Lifecycle and disclosure tests live in `backend/tests/test_memory_lifecycle.py`, `backend/tests/test_memory.py`, and persistence suites. Preserve freshness, source attribution, owner scope, and transactional behavior when changing adapters.

## Phase 34 read and maintenance contracts

`MemoryRetriever` builds a server-owned `MemoryQuery`, checks hard scope, source,
lifecycle and complete embedding-space eligibility before scoring/top-K, and returns
bounded versioned candidate traces. Postgres first loads a capped compatible corpus,
then scores only qualified IDs with exact pgvector and validates numerical parity
against lossless arrays. Oversized or interrupted reads fail explicitly; they do not
establish corpus absence. Original vectors are never rewritten by validation/search.

`fixed` remains the default. All retrieval variants collapse exact repeated
originals to one assertion while retaining their source IDs and immutable records;
the opt-in `compact` variant also removes facts already present in the current
conversation. A selected original is the fallback representation until a valid
derived view exists. The shared builder reduces its optional memory budget when domain
current context or external evidence already occupies the request; final counts and
packing remain endpoint-counted by the same builder. There is no lexical/ANN index,
new embedding space, paraphrase compression, or model adjudicator.

Existing bounded lifecycle jobs discover at most four compatible originals within
a one-year observation horizon. A rotating bounded corpus sweep runs after completed
turns when consolidation is enabled, so pre-existing candidates and invalidated
views can be refreshed on later turns. Similarity proposes candidates only.
`support-v1` views can consolidate exact repeated assertions and a narrow positive
preference grammar whose value and complete context clause match exactly after
surface-form normalization. Other semantic differences remain no-op. Views retain
all original excerpts, IDs, source fingerprints, turns and lifecycle dependency
versions. Source-set/version identity changes when a source validity epoch changes.
Older `extractive-v1` and `extractive-v2` views remain eligible only while their
dependencies remain eligible; v1 views are restricted to epoch zero.
Contradictions mark both sides for review; no model resolves authority or uncertainty.

`dependencies.py` registers original/view dependencies with the existing shared
permission revalidator. Each view node validates its full original set. Injection,
later assistant history and summaries reuse this graph. Artifact writes carrying
memory dependencies are explicitly rejected until artifact reuse has a scope-aware
memory revalidation context. Flag-only historical `ai_memory_read/memory-v1` proofs
are retired.
Migration 027 reconstructs epochs for old lifecycle projections using immutable
stored events. Invalid views fail closed; subsequent bounded corpus sweeps enqueue
refresh jobs from current eligible sources. Current validity is computed from the
canonical sources and lifecycle projections; it is not duplicated in the derived
record. Reverse derived-view membership comes from `derived_memory_sources`, not a
capped lifecycle-state list. Stable preferences do not decay with age; episodic
history uses age only as a relevance score, and corrections receive a shorter
relevance half-life without being deleted. Task-conditioned query ranking remains
deferred and is not represented as a supported query contract.

Run `make memory-eval memory-lifecycle-eval memory-optimization-eval`.
The original baseline and paired evaluator are synthetic evidence. Native pgvector
precision/resource tests remain in the intentionally deferred persistence suite.
No experiment coverage is promoted; see the Phase 34 implementation report.

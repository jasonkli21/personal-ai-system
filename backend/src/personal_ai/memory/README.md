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

`fixed` remains the default and original-memory rollback. The opt-in `compact`
variant removes exact repeated wording and facts already present in the current
conversation. The shared builder reduces its optional memory budget when domain
current context or external evidence already occupies the request; final counts and
packing remain endpoint-counted by the same builder. There is no lexical/ANN index,
new embedding space, paraphrase compression, or model adjudicator.

Existing bounded lifecycle jobs discover at most four compatible originals within
a one-year observation horizon. Similarity proposes candidates only. `extractive-v2`
compact views store one exact repeated assertion plus all original excerpts, IDs,
source fingerprints, turns and lifecycle dependency versions. Source-set/version
identity changes when a source validity epoch changes. Older `extractive-v1` views
remain eligible for context only while their dependencies remain eligible at epoch zero.
Contradictions mark both sides for review; no model resolves authority or uncertainty.

`dependencies.py` registers original/view dependencies with the existing shared
permission revalidator. Each view node validates its full original set. Injection,
later assistant history and summaries reuse this graph. Retained artifacts carry
these dependencies and fail closed when their deployment lacks a matching revalidator. Flag-only historical `ai_memory_read/memory-v1` proofs are retired.
Migration 027 reconstructs epochs for old lifecycle projections using immutable
stored events. Invalid views fail closed; refresh uses subsequent bounded jobs,
and originals remain available through owner-scoped inspection/retention.

Run `make memory-eval memory-lifecycle-eval memory-optimization-eval`.
The original baseline and paired evaluator are synthetic evidence. Native pgvector
precision/resource tests remain in the intentionally deferred persistence suite.
No experiment coverage is promoted; see the Phase 34 implementation report.

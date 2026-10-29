# Memory

This package owns durable user-memory contracts, extraction, retrieval, disclosure policy, and
lifecycle behavior. Memory remains a separate data class from time-sensitive external evidence.

## MEM-1 verified project knowledge

`knowledge.py` defines immutable schema-3 `procedure` and `project_decision`
records. V1 `Memory` and V2 `DerivedMemory` retain their exact contracts.
`knowledge_service.py` resolves trusted evidence, checks scope/content/currentness,
and admits through the existing memory repository. Migration 028 atomically
persists bounded records, complete normalized edges and source-epoch fences.
The first reader uses exact project/revision filters, without embeddings or
provider calls. Limits are 128 records and 1,024 source fences per namespace,
eight edges per record, and 16 KiB per serialized record. Overflow fails closed.
The initial procedure recipe only states historical success for one of three
allowlisted Make commands, with fixed revision preconditions and limitations;
source access plus a successful receipt cannot validate arbitrary claims.
Evidence expiry is capped at 30 days from observation.

`MEMORY_KNOWLEDGE_ADMISSION_ENABLED` and `MEMORY_KNOWLEDGE_SELECTION_ENABLED`
default false and require `MEMORY_ENABLED`. `fixed` stays the legacy default.
Hosts explicitly supply a trusted resolver and a server-built
`MemoryQuery(knowledge=KnowledgeFilter(...))` to
`MemoryRetriever.retrieve_knowledge`. Application composition installs no issuer:
production procedure intake is unsupported even if flags are enabled.
`AuthenticatedCompletedTurnDecisionResolver` additionally requires verified
authentication, exact user and completed assistant references/fingerprints,
registered confirmation, source policy, and a host-supplied source lease.
It is not automatically connected to chat extraction or exposed as a mutation API.

The host resolver owns current application disclosure/project grants and must
fence all source/project/permission mutations across admission and consumption.
Only the stateful hermetic evaluation issuer is provided for workflows; an
in-process mutex cannot substitute for a recoverable deployed source lease.
`KnowledgeService.consume` runs a trusted host action under final source and
canonical DB guards. The host executor owns action authorization, current reads,
idempotency and uncertain external outcomes; memory text never authorizes commands.

Knowledge uses the existing lifecycle projections, events, CAS and `transition`
policy. Explicit developer-test forget/supersede/review events suppress reuse;
automatic personal-memory heuristics/jobs do not process schema 3. Every shared
knowledge permission dependency resolves all edges and current project state at
packing, consumption and supported later history/summary reuse. Source hosts must
call `revoke_knowledge_source(..., erase=True)` when erasing registered sources;
this deletes all reverse-dependent payloads and edges while retaining a tombstone.
`erase_expired_knowledge` is a bounded existing-owner retention seam, with no new
worker. Revoked source identities cannot be reused; a newly verified run needs a
new immutable source identity. Account export inventories include all new families;
deployed source deletion and account deletion orchestration remain external gates.

`inspect_knowledge` requires the existing inspection flag and returns the same
bounded selection/rejection/source metadata. Disable selection for immediate
rollback; records remain stored and old readers ignore them. Knowledge context is
untrusted historical advice, separately labeled by authority and historical
verification. Memory-derived artifact writes remain prohibited.

Run `make memory-knowledge-eval` and the focused `test_memory_knowledge*.py` tests.
Native contracts live in `tests/persistence/test_verified_knowledge_postgres.py`.
See the [ADR](../../../../docs/memory/mem-1-contract-adr.md) and
[implementation report](../../../../docs/memory/mem-1-implementation-report.md).

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

## MEM-2 default-off controls

`control_contracts.py`, `control_service.py`, `control_repository.py` and
`control_tools.py` add exact actor/project-scoped lexical search, fetch, kind
topics and untrusted pending suggestions. Explicit hosts may register four tools;
no chat/provider dispatcher registers them automatically. `memory_agent_tools_enabled`,
`memory_user_management_enabled` and `memory_user_mutations_enabled` default false,
require memory/schema-3 selection, and do not require admission because proposals
and review never admit knowledge. HTTP control composition additionally requires
an installed `memory_control_host` with a source resolver/lease and project mapping;
none is installed by default. The `/memory` UI uses the existing authenticated proxy
and a separate `MEMORY_USER_MANAGEMENT_ENABLED=false` server gate.

Authenticated recent-user forget uses canonical lifecycle CAS/validity epochs and
one atomic receipt transaction. Model tools cannot forget. Review/reject changes
only pending status. Revision always returns `unsupported_evidence_source` until
an actual confirmation issuer and atomic replacement design are supplied. There
is no in-place claim edit, lineage mutation, scheduler or new embedding index.

Pending content expires after 24 hours (erased by subsequent bounded writes);
32 proposals and 256 non-prunable receipt keys per exact actor namespace enforce
bounded storage. Retired keys never execute again. Owner inventory/export includes
both tables; `PostgresControlRepository.erase_owner` requires the existing owner
fence for operator erasure. No automatic physical account eraser is introduced.
See the [control ADR](../../../../docs/memory/mem-2-control-adr.md),
[report](../../../../docs/memory/mem-2-implementation-report.md) and
[independent review handoff](../../../../docs/memory/mem-2-independent-review-handoff.md).
Run `make memory-control-eval`, `test_memory_control*.py` and opt-in native
`tests/persistence/test_memory_control_postgres.py`. Synthetic checks do not close
issuer/identity, physical-send, deletion, replay-capacity or live-model gates.

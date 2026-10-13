# Phase 34 implementation report

Date: 2026-10-12. Local implementation; no production optimization coverage promoted.
Review target and tested base: `95de11c84065bb6ea2695f2e9f9309268f5841ea`; the
remediation is recorded as one direct-child commit. The paired report records the
remediation source digest, and the planner's v6 freeze binds the base/direct-child
relationship and runtime.

## 1. Architectural model

AI memory is non-authoritative personal context. Originals are immutable; compact
views are derived nodes supported by complete original/source sets. `MemoryQuery`
records server scope, source/lifecycle classes, sensitivity, item/token/time budgets,
full embedding identity, versions, query fingerprint and deadline. Task-conditioned
ranking, entity requirements and hard currentness inputs are explicitly deferred;
they are not exposed as unused query fields. Candidate traces distinguish eligibility, origins,
selection/omission, freshness, conflicts, support and estimated contribution.
Actual injection and counted contribution remain shared builder facts.

## 2. Canonical owners and identities

Postgres owns originals, original arrays, lifecycle events/projections and derived
source edges. DynamoDB owns conversations, operational jobs/leases and bounded
actual context traces. Domain applications retain domain authority. Existing
extraction IDs bind owner/app/workspace, source-event fingerprint, type and normalized
text. Derived IDs additionally bind derivation policy and original dependency
versions. Complete reverse derived-view membership comes from the canonical
`derived_memory_sources` relation rather than a capped state projection. Source
validity epochs and acting-user bindings remain distinct from owner identity,
advisory retrieval counts, job IDs, lease generations and physical provider attempts.

## 3. Shared seams reused

The existing memory repository/retriever, lifecycle policies, source guards, effect
receipts, coordinator/worker, provider coordinator, builder, permission registry,
history/summary authority and evaluation output tier are extended. Migration 027
reconstructs historical epochs with hermetic SQL. There is no extra memory store,
registry, invalidation graph, provider transport, or mutation authority. Original
memory records keep schema 1; derived schema 2 accepts historical v1/v2 derivations
and the narrow `support-v1` policy. Legacy creation-time `refresh_state` payload
fields are dropped when read; current validity remains dependency-derived.

## 4. Production composition

FastAPI `get_chat_turn_service` → `MemoryRetriever` → factory-owned memory/lifecycle
repositories → registered `MemoryContextProvider` → shared `ContextBuilder`.
`get_context_assembler` installs `MemoryPermissionRevalidator` beside existing
validators using the current application registry. Both planned and fallback memory
paths attach canonical dependencies. The ordinary chat trace retains a bounded,
content-free retrieval projection with explicit truncation; raw query/context text
and vectors are omitted. The existing inspector uses the same authority registry.

Post-terminal coordination runs a bounded rotating corpus sweep alongside new-memory
discovery. Stable consolidation job identity binds the source set and current
dependency versions, so repeated sweeps deduplicate and changed dependency epochs
can enqueue a refresh. Post-terminal coordination → existing DynamoDB job → private worker `_components`
→ deterministic consolidator → guarded Postgres commit/receipt/source-edge writes.
Discovery supplies current source-policy eligibility before vector ranking.

## 5. Preserved invariants

Owner/app/workspace, current source branch, lifecycle, source authority, sensitivity
and full provider/model/dimension/normalization/tasks/version compatibility are hard
filters. Postgres loads a capped compatible corpus, qualifies sources, then executes
exact pgvector only for eligible IDs. Cast parity remains checked. Validation never
rewrites original vectors; cosine normalization uses temporary operands. Source
rights, malformed data, missing implementations and incomplete oversized reads fail
closed. Domain-derived, permission-bound and time-bound assistant context cannot be
silently extracted into durable personal memory.

## 6. State, idempotency and failure semantics

A same-identity retry preserves the first admitted original, including its vector;
changed embedding spaces fail closed. All retrieval variants collapse exact repeated
originals to one assertion while retaining support IDs and immutable records. Views
contain one source assertion and all supporting originals/excerpts. `support-v1`
allows a narrow positive preference grammar only when the exact value and complete
context clause match; qualifiers and numbers remain in those clauses, while negated
or hedged statements do not merge. Similarity discovers bounded clusters (2–4
sources, one-year observation horizon); unsupported differences remain separate.
Existing valid derivations replay without another embedding or rewriting the receipt
payload. Jobs keep leases, bounded attempts, fenced commits and reconciliation.
Review marks both sides using replay-safe events; an interrupted first review resumes
the second. Equal-time contradictions remain review-only. Derived text cannot
supersede originals. No generative compression/adjudication is installed; ambiguous
clusters deterministically produce no consolidation. Extraction retains its existing
bounded admission path; exact dedupe itself performs no model call.

## 7. Freshness, provenance and revocation

Preferences are stable, episodes/generalizations historical, corrections volatile;
age alone never expires history. Stable preference recency is fixed at 1, episodic
age affects relevance, and explicit corrections receive a seven-day maximum
half-life for ranking. These scores do not expire or delete originals. Existing source
expiry and reuse restrictions remain binding. Forget/supersede/reactivate/review
advance validity epochs. Views enumerate exact source identities, dependency versions,
sensitivity, authority and strategy. Their effective invalid/refresh-required state
is computed from canonical dependencies, not a second mutable truth. Subsequent
bounded completed-turn sweeps can enqueue refresh jobs; originals remain retained and
inspectable. One view dependency rechecks its full original set,
avoiding unnecessary summary fan-in. Injection, later assistant history, summaries
and retained artifacts carry those dependencies in source snapshots. Artifact writes
carrying memory dependencies are rejected until the artifact service has explicit
owner/actor/scope inputs for the shared memory revalidator. Missing lifecycle projections with existing immutable
events fail unavailable rather than becoming initial active state. Historical flag-only
`ai_memory_read/memory-v1` proofs are retired; epoch-changing sources invalidate v1
views. This does not close all repository-wide Phase 14/15 external acceptance gaps.

## 8. Baseline and promotion decision

Before changes, all 14 memory and 60 lifecycle observations passed; the compact
historical baseline records revision/source-tree identity. The current 20-family,
60-row paired run totals 1,004 fixed, 1,004 compact and 1,012 consolidated packed
tokens, with 25 logical embedding calls and 14 maintenance jobs per variant.
Synthetic support coverage is 100%; observed false-memory and scope leakage are zero.
No generative maintenance calls occur. CPU/time, serialized bytes and jobs are
measured locally; native Postgres/index/quota/answer-quality/authority-confusion
evidence remains missing.
No ranking strategy coverage is promoted; retain exact search. Exact duplicate
collapse is part of base retrieval behavior.

## 9. Intentional deviations

No ANN, new embedding space, lexical/hybrid generator or LLM adjudicator is justified
by current evidence. Similarity remains candidate discovery; deterministic support
validation authorizes only the narrow `support-v1` preference grammar. Exact assertion
compaction is support-preserving. Task-conditioned ranking and entity-aware requirements
remain deferred. Memory-bearing artifact writes are explicitly unsupported until the
artifact service has scoped memory revalidation. The fallback
fixture's cap changes from 58 to 57 tokens (fixture v2) to preserve the fallback
boundary after compaction; a separate regression tests newly fitting views at 58 and
restores originals when a consolidated view exceeds the context budget. The unchanged
planner corpus gets a v6 runtime freeze because the memory source tree changed. Old policy-version jobs retire
safely rather than being silently reinterpreted. Fresh turns labelled sensitive by the
current broad conversation policy cannot enter personal memory even without source
snapshots; the positive runtime fixture uses an explicit personal-only server policy.

## 10. Verification and external limits

Material source digest: `c0a6f42aa11a33ce33990daca257bb1703b437ab2e87845b89d2898272fe2e15`.
See the [paired summary](phase-34-paired-evaluation-summary.json) and
[original baseline](../../backend/src/personal_ai/evaluation/fixtures/memory/memory-baseline-v1.json).

| Check | Result |
| --- | --- |
| Backend runnable suite | 1,634 passed; 89 environment-dependent cases skipped |
| Backend Ruff | Passed |
| Memory evaluation | 14/14 passed |
| Memory lifecycle evaluation | 60/60 passed |
| Paired memory optimization evaluation | 20 cases per variant; no coverage promoted |
| Planning evaluation | Passed; no coverage promoted |
| Documentation/content review and `git diff --check` | Passed |

Remediation tests cover public completed-turn sweep/refresh triggering, exact support
grouping, semantic support validation, freshness-specific scoring, artifact write
rejection, bounded projection history, and original fallback when a derived view does
not fit. Existing native suites are maintained; offline runs do not prove native
Postgres behavior.

### Deferred environment-dependent verification — intentionally not executed

The known PostgreSQL/pgvector, DynamoDB Local, reviewed cloud-smoke and live Gemini
suites were intentionally not executed because their required environments are
deferred. This is not an implementation defect or review finding. Native migration
027 application, concurrency/recovery, deployed identity/provider privacy and real
resource/free-tier measurements remain unverified; offline evidence does not replace them.

## 11. Sensitive downstream phases

Phase 35 must consume actual context/count/accounting observations and keep missing
quality/resource labels missing. Phase 36 should stress revocation between qualification,
counting and dispatch, summary/retained-body reuse, epoch backfill and maximum legal
job sequences. Phases 14/15/20/30/31 retain their own identity, immutable-source,
federation, artifact and authoritative-mutation acceptance boundaries.

## 12. Independent review challenges

Challenge native two-stage search cost/precision and interleavings; source guards and
receipt recovery after partial review/consolidation; epoch reconstruction and old-view
retirement; view dependency coverage through deep summaries/exports; delegated actor
and application-policy changes; relevance loss under compact budgets; and any attempt
to interpret synthetic support as answer quality, source authority or strict-free proof.
The audit found no new app/provider-name branches, duplicate canonical ledger/store,
provider rediscovery, domain write path, vector migration or UI capability registry.

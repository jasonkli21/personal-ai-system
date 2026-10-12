# Phase 34 implementation report

Date: 2026-10-12. Local implementation; no production optimization coverage promoted.
Tested base: `0e766e623ff1b74a206747d2e4c8b898d20f99b3`, plus this single implementation
commit's material source tree. The paired report records its source digest; the
planner's new v5 freeze binds the base/direct-child relationship and runtime.

## 1. Architectural model

AI memory is non-authoritative personal context. Originals are immutable; compact
views are derived nodes supported by complete original/source sets. `MemoryQuery`
records server scope, actor, task/requirements, source/lifecycle classes, sensitivity,
time/freshness, item/token/time budgets, full embedding identity, versions, query
fingerprint and deadline. Candidate traces distinguish eligibility, origins,
selection/omission, freshness, conflicts, support and estimated contribution.
Actual injection and counted contribution remain shared builder facts.

## 2. Canonical owners and identities

Postgres owns originals, original arrays, lifecycle events/projections and derived
source edges. DynamoDB owns conversations, operational jobs/leases and bounded
actual context traces. Domain applications retain domain authority. Existing
extraction IDs bind owner/app/workspace, source-event fingerprint, type and normalized
text. Derived IDs additionally bind strategy and original dependency versions.
Source validity epochs and acting-user bindings remain distinct from owner identity,
advisory retrieval counts, job IDs, lease generations and physical provider attempts.

## 3. Shared seams reused

The existing memory repository/retriever, lifecycle policies, source guards, effect
receipts, coordinator/worker, provider coordinator, builder, permission registry,
history/summary authority and evaluation output tier are extended. Migration 027
reconstructs historical epochs with hermetic SQL. There is no extra memory store,
registry, invalidation graph, provider transport, or mutation authority. Original
memory records keep schema 1; derived schema 2 accepts versioned v1/v2 derivations.

## 4. Production composition

FastAPI `get_chat_turn_service` → `MemoryRetriever` → factory-owned memory/lifecycle
repositories → registered `MemoryContextProvider` → shared `ContextBuilder`.
`get_context_assembler` installs `MemoryPermissionRevalidator` beside existing
validators using the current application registry. Both planned and fallback memory
paths attach canonical dependencies. The ordinary chat trace retains a bounded,
content-free retrieval projection with explicit truncation; raw query/context text
and vectors are omitted. The existing inspector uses the same authority registry.

Post-terminal coordination → existing DynamoDB job → private worker `_components`
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
changed embedding spaces fail closed. v2 views contain one exact assertion and all
supporting originals/excerpts. Similarity discovers bounded clusters (2–4 sources,
one-year observation horizon), but paraphrases/mixed assertions do not merge.
Existing valid derivations replay without another embedding or rewriting the receipt
payload. Jobs keep leases, bounded attempts, fenced commits and reconciliation.
Review marks both sides using replay-safe events; an interrupted first review resumes
the second. Equal-time contradictions remain review-only. Derived text cannot
supersede originals. No generative compression/adjudication is installed; ambiguous
clusters deterministically produce no consolidation. Extraction retains its existing
bounded admission path; exact dedupe itself performs no model call.

## 7. Freshness, provenance and revocation

Preferences are stable, episodes/generalizations historical, corrections volatile;
age alone never expires history. Existing source expiry and reuse restrictions remain
binding. Forget/supersede/reactivate/review advance validity epochs. Views enumerate
exact source identities, dependency versions, sensitivity, authority and strategy.
Their effective invalid/refresh-required state is computed from canonical dependencies,
not a second mutable truth. Refresh occurs through later bounded jobs; originals
remain retained and inspectable. One view dependency rechecks its full original set,
avoiding unnecessary summary fan-in. Injection, later assistant history, summaries
and retained artifacts carry those dependencies. Artifact deployments without the
matching revalidator fail closed; valid memory-bearing artifact reuse remains part of
P20 integration acceptance. Missing lifecycle projections with existing immutable
events fail unavailable rather than becoming initial active state. Historical flag-only
`ai_memory_read/memory-v1` proofs are retired; epoch-changing sources invalidate v1
views. This does not close all repository-wide Phase 14/15 external acceptance gaps.

## 8. Baseline and promotion decision

Before changes, all 14 memory and 60 lifecycle observations passed; the compact
historical baseline records revision/source-tree identity. The current 20-family,
60-row paired run totals **1,050 fixed / 1,004 compact / 1,022 consolidated** packed
tokens and **25 logical embedding calls per variant**. Synthetic support coverage is
100%; observed false-memory and scope leakage are zero. No generative maintenance
calls occur. CPU/time, serialized bytes and jobs are measured locally; native
Postgres/index/quota/answer-quality/authority-confusion evidence remains missing.
Both aggregate savings fall below the predeclared 5% threshold. **No coverage is
promoted; retain exact search and fixed original retrieval.**

## 9. Intentional deviations

No ANN, new embedding space, lexical/hybrid generator or LLM adjudicator is justified
by current evidence. Semantic candidates remain proposals. Exact assertion compaction
is support-preserving and opt-in through existing experimental controls. The fallback
fixture's cap changes from 58 to 57 tokens (fixture v2) to preserve the fallback
boundary after compaction; a separate regression tests newly fitting views at 58.
The unchanged planner corpus gets a v5 runtime freeze because its built-in memory
fixture now uses canonical source records/dependencies. Old policy-version jobs retire
safely rather than being silently reinterpreted. Fresh turns labelled sensitive by the
current broad conversation policy cannot enter personal memory even without source
snapshots; the positive runtime fixture uses an explicit personal-only server policy.

## 10. Verification and external limits

Material source digest: `cb4ee8b2bc368acc75b081ede88a6e2a5cf5b27e1a01956f8398cae48702adf3`.
See the [paired summary](phase-34-paired-evaluation-summary.json) and
[original baseline](../../backend/src/personal_ai/evaluation/fixtures/memory/memory-baseline-v1.json).

| Check | Result |
| --- | --- |
| Backend runnable suite | 1,627 passed; 87 environment-dependent cases deselected |
| Backend Ruff | Passed |
| Frontend tests / lint / TypeScript | 123 tests passed; lint/type checks passed |
| Backend wheel/sdist and frontend build | Passed |
| Context, context-plan, planning, memory, memory-lifecycle, memory-optimization, retrieval evaluations | Passed |
| Documentation/content review and `git diff --check` | Passed |

The bundled Node runtime and a writable temporary uv cache were used for builds.
Runnable coverage
includes production DI/trace integration, original/derived replay, hard pre-ranking
eligibility, branch/deletion/epoch/actor isolation, inherited history revalidation,
conflicts, freshness, original rollback and numerical-array preservation. Existing
native suites are maintained; additional native pgvector resource/eligibility and
new-attempt duplicate tests are present.

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

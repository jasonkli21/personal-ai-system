# Phase 33 implementation and review report

Date: 2026-10-12. Tested base: `db32b1c` and its Phase 33 working tree; the requested single commit is its direct child. The frozen retrieval baseline records the full base revision, source hashes, fixture hash and pre-change measurements. Paired summaries bind the tested revision, material Python/dependency digest, fixture and baseline identities. No strategy coverage is promoted.

## 1. Architectural model

Research starts after an authorized explicit research request or an existing research choice; it does not add automatic planner dispatch. The pipeline remains query planning → admitted search adapter → immutable snippet observations → eligible evidence projection → deterministic ranking → whole-passage extractive context → shared builder → literal validated synthesis. Iterative research retains its existing budget/state machine. Search identity remains separate from inference identity.

## 2. Canonical owners and identities

- Existing owner/application/workspace-scoped Postgres research sessions own query plans, queries, adapter attempts, source observations, deduplicated evidence, selections and citations. `EvidenceObservation` aliases the existing `SourceObservation`; it is not another store.
- Query-plan identity binds exact original text, source bounds, publication bound, freshness, query/result/attempt/time caps and strategy/version. Observations bind terminal attempt, query, result position, adapter, source URL/revision/publication time, immutable passage/fingerprint, origin, rights reference and observation time. P19 invocation/physical-attempt IDs are references, never admission proof.
- Evidence is an immutable deduplicated projection of observations. A separately identified `DerivedEvidence` package binds packing strategy, exact full-passage support spans/fingerprints/observation IDs, omissions and an unresolved-conflict marker. It never becomes a domain fact.
- P19 still owns admission, quota and settlement. Migration 026 owns only compact immutable experiment summaries, indexed by task/source/strategy. P20 owns optional bulky numeric evaluation batches. No raw experiment source bodies, private prompts or credentials are retained.

## 3. Shared seams reused

The existing `QueryPlanner`, `SearchAdapter`, extraction/reranker contracts, research repositories, context source metadata/builder, permission revalidator, strict synthesis validator, P19 usage context and P20 evaluation consumer are extended. The installed search catalog is shared by both API compositions. An alternate adapter and a declared-but-unavailable implementation are tested through that actual composition. There is no parallel research orchestrator, accounting ledger, source index or provider-name branch in generic execution.

## 4. Production composition

`api.research.research_service` / `api.iterative_research.iterative_research_service` → `compose_research_clients` → installed adapter plus existing fake/Gemini inference composition → existing service → adapter's P19 admission → evidence pipeline → `ContextAssembler.assemble_research_context` → `ContextBuilder`. The paired runner calls the real single-pass API factory with an installed synthetic adapter. Query/packing experiments are reachable through server configuration behind `RESEARCH_RETRIEVAL_EXPERIMENTS_ENABLED=false` by default. Turning that gate off restores the literal strategy. No inference-routing acceptance gate is changed.

## 5. Invariants preserved

Query validation preserves complete original word order, multiplicity, punctuation, quoted identifiers, numbers, units, dates and negation; only a small plain-word suffix is allowed. Invalid/unversioned plans fall back once, without another search. Typed allowlists intersect literal `site:` bounds; exclusions win. Rights/domain/freshness filters precede extraction/ranking. Forbidden source URLs/titles/passages are not persisted. Returned result lists must fit the requested source cap. Rankers may only permute exact eligible records and must identify their version; malformed output restores the deterministic ordering. All eligible potentially conflicting passages must fit, otherwise synthesis is withheld.

## 6. State, replay and failure semantics

Existing scoped creation idempotency, claim tokens, revision fences, append-only provenance and terminal replay rules remain authoritative. A plan cannot change after persistence. Three queries × three explicit attempts × started/terminal records fit the existing 18-record cap. Each physical HTTP attempt still reserves/settles through P19; HTTP retries are not added. Quota denial, timeout, malformed/oversized results and unavailable rights fail boundedly. A partial standard plan retains known completed observations, identifies uncompleted/failed queries and returns no answer; an uncertain call contributes no invented observations and is not replayed under that session. Iterative leases, reservations, cancellation and recovery remain unchanged. Optional artifact failure preserves non-promoted compact results; required export artifact failure fails closed.

## 7. Sources, freshness and revocation

Identical content can merge across syndicated sources only when publication time and native revision agree. Different revisions/times and different literals remain separate; near duplicates are labelled, never suppressed. Undated snippets explicitly carry observation-only freshness. A mandatory `published_after` bound excludes undated, older and future-dated sources. Existing TTLs remain in force.

New observation rights dependencies bind the server-owned preflight version and flow through shared context snapshots, detail/reuse checks, selected research context, account-export disclosure and cached export artifact revalidation. Provider account/preflight references are hashed. This is current operator-configured snippet authority, not proof of live publisher rights or closure of Phase 15's historical source/membership gaps. Existing cross-app denial/gates remain; same-owner identity grants nothing new. The new compact family is in account export/owner inventory and bounded scheduled expiry; real-store lifecycle acceptance remains deferred.

## 8. Baseline and promotion decision

The pre-change 18-case freeze has 18 synthetic search-adapter calls, 15,902 estimated packed tokens and 11 completed excerpt answers. Correctly preserving different publication versions raises the current literal control to 16,027 packed tokens; that correctness repair is not credited as an optimization gain.

| Paired strategy | Adapter calls | Packed token estimate | Total input/output token estimate |
| --- | ---: | ---: | ---: |
| Literal control | 18 | 16,027 | 17,977 |
| Compact extractive | 18 | 15,385 | 17,335 |
| Preserved-question qualifier | 18 | 16,027 | 17,977 |
| Bounded expansion | 35 | 18,637 | 20,587 |

Each variant has 12 synthetic synthesis invocations and 149 local counting invocations. Physical live provider calls are zero; live quota is unknown. Compression inference is absent. Numeric retained-artifact bytes are measured after publication and allocated exactly to compact summaries. Source bodies are not retained.

The v1 rubric is fixed before final judging: zero rights/literal/freshness/support regression, no unsupported claims or conflict loss, no additional search/quota/synthesis calls, at most 20% latency overhead, and at least five percentage points of answer improvement or 10% total-token savings at equal quality. Synthetic-only evidence and insufficient independent coverage always deny promotion. Compact packing saves about 4% of packed tokens and 3.6% of total estimated tokens; qualifiers add no benefit and expansion spends more search calls. **None is promoted.** Literal citation/support validation is measured; live model question-answering quality is unmeasured. The curated 18 synthetic cases are not sufficient independent held-out families.

## 9. Intentional deviations

No semantic rewrite/decomposition, hybrid index/crawler, new live provider or model compression is added: baseline evidence does not justify them. Whole passages provide exact support without compression calls or a new claim-authority model. The existing Phase 6 claim/conflict contracts remain separate. Bulky experiment retention is numeric P20 observations, not an unrestricted raw-source corpus.

The shared runtime change invalidates Phase 32's material-source lock, so its unchanged corpus is refrozen as `planning-baseline-v3` / `planning-evaluator-v3`; historical v2 is preserved. Generated Python caches and `.DS_Store` are excluded from material source identity. This fixes a non-source dependency and does not weaken source/dependency checks or promote planning.

## 10. Verification and external acceptance

Checks passed: 1,592 runnable backend tests (85 infrastructure/cloud tests deselected;
both credentialed manual suites excluded), plus 61 final targeted retrieval/planning
checks after the last composition change. Frontend: 123 tests across 23 files,
ESLint, TypeScript checks and production build. Backend: Ruff and sdist/wheel build.
All 13 applicable Makefile offline/deterministic evaluation targets passed: context,
context-plan, planning, memory, memory-lifecycle, research, retrieval, decision,
domain, iterative-research, itinerary-proposal, quota-scarcity and cascade.
Added documentation links were checked and `git diff --check` passed.

Final source evidence: tested revision `db32b1c-working-tree-718f57610691`; material Python/runtime dependency
digest `201d70a1a548d9cacd0de49215c96600c464282e6ca5798ce38a4c1bd20e64ca`. The Phase 32 v3 freeze independently binds the complete material
source/fixture tree and installed runtime dependencies. Known PostgreSQL/pgvector, DynamoDB Local, reviewed cloud-smoke and live Gemini suites are intentionally not executed because their environments are deferred. The new real-Postgres concurrent replay/isolation/truncation/expiry suite is maintained under that existing marker. This is not an implementation defect or review finding. Live Brave/account/source-rights behavior and real GCS retention/IAM are also unverified; offline HTTP/store fixtures do not replace those checks.

## 11. Sensitive downstream phases

Phase 34 must consume exact support/source-rights dependencies without turning evidence into durable user memory or mixing embedding spaces. Phase 35 must use P19 observations and distinguish synthetic/missing outcomes from observed live quality. Phase 36 must challenge cross-boundary revocation, actual accounting/store races, migration 026, retention/export, and composed rollback before release acceptance. These phases can extend the existing seams without moving canonical source state or replacing the research runtime.

## 12. Independent review focus

Challenge the operator-preflight authority and revocation reach; historical-source and cross-app gates; unknown versus mandatory publication freshness; exact observation/derived support identity; syndicated versus materially versioned deduplication; partial-plan/unknown-send restart semantics; every physical P19 link; source denial before disclosure; export artifact dependency reuse; compact metadata versus raw retention; and whether the synthetic rubric could be mistaken for live answer-quality or promotion proof. Verify production composition and default-off rollback rather than relying only on hand-built fixtures.

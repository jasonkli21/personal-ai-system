# Phase 33 implementation and review report

Date: 2026-10-12. The original Phase 33 implementation is at `79d7455`; the independent-review remediation is tested as a working tree directly on that revision. See the dated [review remediation evidence](phase-33-independent-review-remediation-evidence-2026-10-12.md) for corrected contracts, the v2 semantic baseline, verification results, and the remaining routing gate. No strategy coverage is promoted.

## 1. Architectural model

Research starts after an authorized explicit research request or an existing research choice; it does not add automatic planner dispatch. The pipeline remains query planning → admitted search adapter → immutable snippet observations → eligible evidence projection → deterministic ranking → whole-passage extractive context → shared builder → literal validated synthesis. Iterative research retains its existing budget/state machine. Search identity remains separate from inference identity.

## 2. Canonical owners and identities

- Existing owner/application/workspace-scoped Postgres research sessions own query plans, queries, adapter attempts, source observations, deduplicated evidence, selections and citations. `EvidenceObservation` aliases the existing `SourceObservation`; it is not another store.
- Query-plan identity binds exact original text, source bounds, publication bound, freshness, query/result/attempt/time caps and strategy/version. Observations bind terminal attempt, query, result position, adapter, source URL/revision/publication time, immutable passage/fingerprint, origin, rights reference and observation time. P19 invocation/physical-attempt IDs are references, never admission proof.
- Evidence is an immutable deduplicated projection of observations. A separately identified `DerivedEvidence` package binds packing strategy, exact full-passage support spans/fingerprints/observation IDs, omissions and an unresolved-conflict marker. It never becomes a domain fact.
- P19 still owns admission, quota and settlement. Migration 026 owns only compact immutable experiment summaries, indexed by task/source/strategy. P20 owns optional bulky numeric evaluation batches. No raw experiment source bodies, private prompts or credentials are retained.

## 3. Shared seams reused

The existing `QueryPlanner`, typed `SearchAdapter`, extraction/reranker contracts, research repositories, context source metadata/builder, permission revalidator, strict synthesis validator, P19 usage context and P20 evaluation consumer are extended. The installed search catalog is shared by both API compositions. Synthetic and non-synthetic registrations are exercised through production composition. Provider validation, endpoint profiles and cost policy live in registration/provider-owned functions; generic orchestration consumes declared metadata.

## 4. Production composition

`api.research.research_service` / `api.iterative_research.iterative_research_service` compose search through `search.runtime.compose_search_adapter` and synthesis through `llm.research.compose_research_inference`. Search registration does not select synthesis or its counter. Research synthesis still uses the configured fake/Gemini composition and is not yet dispatched through a Phase 21 `ExecutionPlan`; request-time research routing remains within the repository's existing Gemini-only acceptance gate. The paired runner calls the real single-pass API factory with an installed synthetic adapter. Query/packing experiments remain behind `RESEARCH_RETRIEVAL_EXPERIMENTS_ENABLED=false` by default. Turning that gate off restores the literal strategy.

## 5. Invariants preserved

Query validation preserves complete original word order, multiplicity, punctuation, quoted identifiers, numbers, units, dates and negation; only a small plain-word suffix is allowed. Each adapter receives an immutable `SearchOperation` carrying query/plan identity, typed and literal domain bounds, exclusions, publication bound, result cap, and deadline. Typed allowlists intersect literal `site:` bounds; exclusions win. Brave translates supported domain bounds and rejects an exact mandatory publication bound it cannot honor before dispatch. Returned observations are filtered again before extraction/ranking. Returned result lists must fit the requested source cap. Rankers may only permute exact eligible records and must identify their version; malformed output restores the deterministic ordering. All eligible potentially conflicting passages must fit, otherwise synthesis is withheld.

## 6. State, replay and failure semantics

Existing scoped creation idempotency, claim tokens, revision fences, append-only provenance and terminal replay rules remain authoritative. A plan cannot change after persistence. Three queries × three explicit attempts × started/terminal records fit the existing 18-record cap. Research persists a logical started attempt without a physical P19 link. The adapter returns canonical P19 invocation/attempt IDs after admission; an admission denial may return its canonical invocation but no physical attempt. Quota denial, timeout, malformed/oversized results and unavailable rights fail boundedly. A partial standard plan retains known completed observations, identifies uncompleted/failed queries and returns no answer; an uncertain call contributes no invented observations and is not replayed under that session. Iterative research uses the same `SearchOperation` envelope while retaining its budget/state machine. Optional artifact failure preserves non-promoted compact results; required export artifact failure fails closed.

## 7. Sources, freshness and revocation

Identical content can merge across syndicated sources only when publication time and native revision agree. Different revisions/times and different literals remain separate; near duplicates are labelled, never suppressed. Undated snippets explicitly carry observation-only freshness. A mandatory `published_after` bound excludes undated, older and future-dated sources. Existing TTLs remain in force.

New observation rights dependencies bind a source-rights authority ID, account-derived authority hash, revocation epoch, and preflight reference; they flow through shared context snapshots, detail/reuse checks, selected research context, account-export disclosure and cached export artifact revalidation. Historical permissions are checked against the recorded provider's registered rights authority, independently of current search selection or feature enablement. This is current operator-configured snippet authority, not proof of live publisher rights or closure of Phase 15's historical source/membership gaps. Existing cross-app denial/gates remain; same-owner identity grants nothing new. The new compact family is in account export/owner inventory and bounded scheduled expiry; real-store lifecycle acceptance remains deferred.

## 8. Baseline and promotion decision

The original v1 18-case measurements remain historical. The repaired v2 suite has 20 cases, including typed/literal domain intersection and mandatory publication bounds. Its frozen literal control is now a mandatory semantic oracle for state, failure, source statuses, exact support/citations, hard bounds, freshness, and resource ceilings. V2 records two evidence items for cross-source unknown-version content and two for materially versioned content; these are correctness repairs, not optimization gains.

| Paired strategy | Adapter calls | Packed token estimate | Total input/output token estimate |
| --- | ---: | ---: | ---: |
| Literal control | 20 | 18,089 | 20,381 |
| Compact extractive | 20 | 17,480 | 19,772 |
| Preserved-question qualifier | 20 | 18,089 | 20,381 |
| Bounded expansion | 39 | 21,012 | 23,304 |

Each 20-case variant has 20 synthetic synthesis invocations. Physical live provider calls are zero; live quota is unknown. Compression inference is absent. The v2 paired run emits 60 candidate summaries. Source bodies are not retained.

The v1 rubric is fixed before final judging: zero rights/literal/freshness/support regression, no unsupported claims or conflict loss, no additional search/quota/synthesis calls, at most 20% latency overhead, and at least five percentage points of answer improvement or 10% total-token savings at equal quality. Synthetic-only evidence and insufficient independent coverage always deny promotion. Compact packing saves about 4% of packed tokens and 3.6% of total estimated tokens; qualifiers add no benefit and expansion spends more search calls. **None is promoted.** Literal citation/support validation is measured; live model question-answering quality is unmeasured. The curated 18 synthetic cases are not sufficient independent held-out families.

## 9. Intentional deviations

No semantic rewrite/decomposition, hybrid index/crawler, new live provider or model compression is added: baseline evidence does not justify them. Whole passages provide exact support without compression calls or a new claim-authority model. The existing Phase 6 claim/conflict contracts remain separate. Bulky experiment retention is numeric P20 observations, not an unrestricted raw-source corpus.

The review-remediation source changes invalidate Phase 32's material-source lock, so its unchanged corpus is refrozen as `planning-baseline-v4` / `planning-evaluator-v4`; historical v2 and v3 are preserved. The v4 lock keeps the material source/runtime identity checks and the current-or-direct-child revision binding. Generated Python caches and `.DS_Store` are excluded from material source identity. Planning remains deterministic and non-promoted.

## 10. Verification and external acceptance

The remediation checks and tested working-tree revision are recorded in the dated [review remediation evidence](phase-33-independent-review-remediation-evidence-2026-10-12.md). This report's earlier frontend and broad evaluation results describe the original Phase 33 implementation and are not claims about the remediation tree. PostgreSQL/pgvector, DynamoDB Local, cloud, live Gemini/Brave, publisher-rights, and real GCS retention/IAM behavior remain unverified; offline HTTP/store fixtures do not replace those checks.

## 11. Sensitive downstream phases

Phase 34 must consume exact support/source-rights dependencies without turning evidence into durable user memory or mixing embedding spaces. Phase 35 must use P19 observations and distinguish synthetic/missing outcomes from observed live quality. Phase 21 execution-plan dispatch for request-time research synthesis remains an explicit integration gap behind the current request-workflow gate. Phase 36 must challenge cross-boundary revocation, actual accounting/store races, migration 026, retention/export, and composed rollback before release acceptance.

## 12. Independent review focus

Challenge the operator-preflight authority and revocation reach; historical-source and cross-app gates; unknown versus mandatory publication freshness; exact observation/derived support identity; syndicated versus materially versioned deduplication; partial-plan/unknown-send restart semantics; every physical P19 link; source denial before disclosure; export artifact dependency reuse; compact metadata versus raw retention; and whether the synthetic rubric could be mistaken for live answer-quality or promotion proof. Verify production composition and default-off rollback rather than relying only on hand-built fixtures.

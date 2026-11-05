# Personal AI System — MEM-5 Detailed Implementation Plan

**Phase:** MEM-5 — Hybrid Memory Index and Context Research  
**Prepared:** 2026-11-04  
**Repository baseline:** [`jasonkli21/personal-ai-system`](https://github.com/jasonkli21/personal-ai-system), `main` at [`fe1915ec50d075eb9eba7b4d51c8d56527adc3fc`](https://github.com/jasonkli21/personal-ai-system/commit/fe1915ec50d075eb9eba7b4d51c8d56527adc3fc)  
**Program baseline:** Integrated Harness Excellence Roadmap v3.1 (2026-11-03) and Memory Architecture & Research Roadmap  
**Status:** proposed development plan; **not** live-memory, provider, deployment, or production-enable approval.

## 1. Decision and expected result

Deliver a bounded, reproducible **research layer for memory navigation, hybrid retrieval and adaptive context packing**. Reuse existing memory authority, immutable source records, pgvector/embedding contracts, lifecycle, `MemoryRetriever`, knowledge service, and `ContextBuilder`. Do not create a parallel memory store or a second RAG/disclosure pipeline. A generated topic map is an advisory navigation aid, **never** a permission grant, provenance source or trusted replacement for underlying evidence.

Build six experimental capabilities as **independently ablatable** parts of a small vertical slice:

1. A compact, versioned, scoped topic directory with topic→record references and exact invalidation dependencies.
2. A hybrid candidate strategy combining bounded lexical and existing semantic search, with strict eligibility and version compatibility.
3. Trusted metadata/temporal filters and a deterministic reranker that preserves corrections, contradictions, uncertainty and explicit authority priority.
4. Two-stage navigation: topic overview → authorized record fetch → evidence/currentness validation; opt-in expansion/backoff only while budgets allow.
5. Adaptive memory token allocation within the **existing** endpoint-counted shared context-builder policy.
6. Paired research/evaluation comparing fixed retrieval, hybrid variants and eligible full-context where feasible on task **answers**, not just recall.

**Development target (E0/E1, optionally native E2 component):** a complete offline, public/synthetic and/or explicitly authorized non-sensitive research implementation, with conformance, failure injection, ablations, and honest evidence reports. **Blocked integrated target:** private MEM-3 episodes, live auto-use, new source disclosures or model/embedding calls, cross-application sharing, production indexing, and promotion pending their separate gates. This is a capability-specific restriction, not an excuse to defer deterministic components or native tests that are practical now.

### Non-goals

- Do **not** enable the read-disabled MEM-3 projection, fabricate issuer-bound source epochs, or treat workflow receipts as authenticated historical evidence.
- Do **not** turn MEM-4 `pending` proposals into accepted memory or index them as trusted facts. No automatic promotion.
- Do **not** build external document connectors (HXE-1), a new memory experiment-promotion service (MEM-6), new grants/erasure orchestration (MEM-7), an agent coding loop, or a second vector/embedding system.
- Do **not** edit frozen evaluation corpora, digests, earlier receipts or old release source locks to make tests pass.
- Do **not** put `mem5`, `phase_5` or similar phase-specific names in active modules, public commands, tests or current module READMEs. Historical/deliverable documents may use MEM-5.

## 2. Verified repository architecture and current readiness

Follow repository [`AGENTS.md`](https://github.com/jasonkli21/personal-ai-system/blob/fe1915e/AGENTS.md) and the [`docs/README.md`](https://github.com/jasonkli21/personal-ai-system/blob/fe1915e/docs/README.md) route: code/executable contracts/migrations/tests outrank historical plans. Re-pin `main` before implementation, inspect working-tree status and reconcile drift.

| Area | Current evidence at `fe1915e` | Impact on MEM-5 |
| --- | --- | --- |
| Legacy personal-memory retrieval | `memory/services.py` implements `MemoryRetriever`; server-owned `MemoryQuery`; embeddings, exact scope/source/lifecycle checks, candidate caps, `fixed`/`compact`/`scored`/`consolidated` experimental variants; `fixed` default. | Preserve existing default and route all experimental reads through canonical authority. |
| Memory persistence | `persistence/postgres/memory.py` and in-memory repository; pgvector search with compatibility checks and eligibility; no lexical/ANN memory index per memory README. | Hybrid must not rank an unqualified corpus or open an unbounded scan; prefer bounded eligible candidate APIs. |
| Verified knowledge | `knowledge_service.py` supports explicitly scoped schema-3 `procedure`/`project_decision` selection; exact project/revision source resolver; default-off flags; no production issuer. | Do not mix verified knowledge with legacy personal memory merely because text/embedding is comparable. Preserve type/scope and source verification. |
| Context | `context/builder.py` supplies source-class limits, permission checks, endpoint token accounting and deterministic packing; `context/assembler.py` plans source operations. | Adaptive packing is an input policy to the existing builder, not a new assembler or unmetered prompt join. |
| Standalone retrieval | `retrieval/` is an isolated default-off operator-installed lexical corpus without model/context/memory integration. | Borrow bounded lexical design concepts, but don't wire an external source index into memory authority. |
| MEM-3 | `episodes.py`, `episode_service.py`, migration 035: capture and selection **hard disabled**, no trusted producer/issuer or canonical erasure integration. | No historical episode indexing, read or hierarchical fetch until independently unblocked. |
| MEM-4 | `memory/consolidation/` and migration 036 contain isolated synthetic pending proposals, generation-scoped checkpoint/CAS and some native PostgreSQL component evidence; `fe1915e` addresses review findings. | Can use separately labeled **synthetic fixture** content as research material. Never silently consume proposal data in the production retriever. |
| MEM-4 evidence | [`2026-11-04-consolidation-review-remediation.md`](https://github.com/jasonkli21/personal-ai-system/blob/fe1915e/docs/memory/2026-11-04-consolidation-review-remediation.md): 107 focused tests passed, two frozen corpus digests preserved, local pilot unavailable, latest native PostgreSQL rerun blocked, planning v35 source lock failed; review/production acceptance open. | Keep these failures visible; do not import prior author E1/E2 claims as MEM-5 independent evidence. |
| Release state | `docs/current-state.md`: independent release acceptance pending, all release profiles NO_GO. | Experimental research does not flip flags or imply E3–E5 readiness. |

**Key file map (inspect exact current versions):**

- `backend/src/personal_ai/memory/{contracts.py,services.py,knowledge_service.py,knowledge_repository.py,dependencies.py,freshness.py,policy.py}`
- `backend/src/personal_ai/memory/{lifecycle/,consolidation/}` and their tests
- `backend/src/personal_ai/persistence/postgres/{memory.py,knowledge.py,consolidation.py}`; migrations `027`–`036` (and any newer additions)
- `backend/src/personal_ai/context/{builder.py,assembler.py,providers.py,authorization.py,planner.py}`
- `backend/src/personal_ai/evaluation/{memory_optimization.py,memory_task_baseline.py,memory_knowledge_consumer.py,consolidation_quality.py}`
- `backend/src/personal_ai/evaluation/fixtures/memory/`, `backend/tests/test_memory_revalidation.py`, `backend/tests/test_memory_knowledge.py`
- `backend/src/personal_ai/retrieval/{installation.py,service.py}` for **patterns**, not authorization reuse
- `docs/memory/{episode-development-blockers.json,consolidation-development-blockers.json}` and current-state / roadmap.

## 3. Ownership, security and non-negotiable invariants

| Boundary | Owner / required behavior |
| --- | --- |
| Identity and authority | Server-supplied request scope and existing source authorization/issuer. The model, query string, topic path or index metadata cannot supply owner, actor, project, permission, purpose, grant or trusted time. |
| Eligibility | Resolve scope, source class, exact revisions/epochs, retention, sensitivity, lifecycle state, conflicts, dependency versions and permission **before candidate eligibility/ranking**; recheck at fetch, packing and final disclosure/consumption. |
| Content | Treat indexed topic labels, lexical matches, metadata and generated summaries as untrusted data. No instruction execution or source-derived authorization. Never index secrets, raw tool outputs, reasoning traces or disallowed fields. |
| Persistence | Canonical memory/knowledge records are source of truth. Index is reproducible/rebuildable, versioned, bounded, namespaced and derivative; cannot resurrect forgotten or withdrawn content. |
| Context | `ai_memory` stays an existing source class; builder owns token counting, source-aware packing, permission dependencies and late revalidation. A separate research policy may request a budget, not bypass class/global ceilings. |
| Models and budget | No new external embedding/rerank/rewrite calls in initial deterministic slice. Optional provider work requires strict-free provider/account/privacy, allowed source disclosure and physical-attempt accounting, or else a verifiably offline pinned local model. Fakes are E1 only. |
| Evaluation | Freeze arm manifest before results, retain every attempted/denied/failed row, count actual packed tokens and end-task outcomes. Index-recall wins alone are insufficient. |

**Revocation rule:** any source forget/withdraw/regrant/correction/expiry/owner purge invalidates all derived index entries and cached topic views associated with prior epochs. Tombstone/issuer floors must survive replays; a fresh regrant may reintroduce content only as a *new* eligible identity with new evidence. A stale process snapshot or a changed index alias cannot confer rights. If a full current authority check cannot run, return `unavailable` or deny; never treat an empty query result as proof that no eligible memory exists.

**Filter-order nuance:** an implementation may use a *strictly scoped* index for performance, but the index cannot be the sole authorization check. Prevent both leakage (scoring unauthorized candidates) and incorrect omissions (top-K over mixed rights before scope filtering). Use bounded, verifiably eligible candidate sets or a trusted query predicate before lexical/vector recall; validate each fetched record again. Preserve neutral, content-free diagnostics.

## 4. Experimental contracts and policies

Design exact names against the live code before writing. Suggested *conceptual* contracts—not an instruction to add all of these classes/tables:

### 4.1 `MemoryResearchQuery`

Trusted, immutable wrapper around existing server-built `MemoryQuery`, with source kind (`legacy_personal` or `verified_knowledge`, **not** arbitrary union), exact owner/app/workspace/actor/project filters, permitted purpose and time window, maximum candidate fetches and bytes, top-K, topic depth, deadlines, as-of time, embedding-space identity, requested research policy, token ceiling and explicit `source_profile` (`frozen_fixture` initially). Reject unknown fields and contradictory or model-supplied scope attributes. Do not copy an obsolete `MemoryQuery` into a parallel public API.

### 4.2 `MemoryIndexEntry` / `TopicNode`

- Exact authorized namespace; memory UUID and canonical record kind; immutable source reference set (with source fingerprint, revision/epoch/validity version and dependency digest); record content/payload digest and optional expiry.
- Normalized bounded lexical terms with deterministic tokenization and closed maximum text/term counts. Duplicate assertions map to distinct IDs until canonical exact-collapse policy decides otherwise.
- Topic ID and bounded, non-sensitive, deterministic display label; parent/child IDs and ordered leaf references. No unbounded path growth, free-form file path authority or raw evidence excerpts in directory entries.
- Policy/index generation = source corpus version + normalization/tokenization version + topic policy + embedding-space identity (where applicable) + scope/rights namespace. Reject incompatible snapshots rather than silently compare embeddings across spaces.
- Build watermark and invalidation dependency manifest; materialized index is disposable cache. **Directory ≠ memory store ≠ grant.**

### 4.3 `RetrievalResearchResult`

Separate result identities from presentation. Include selected record IDs, eligible candidate provenance, topic navigation IDs, source refs, why ranked, policy/generation IDs, hard exclusion and incomplete/unsupported reasons, **bounded** neutral traces, final `ContextBuilder` packing report and token counts. Avoid exposing private rejected content or raw cross-scope metadata. Report stale-index fallback/denial explicitly. Preserve source order and correction/conflict priority rather than manufacturing a single synthetic truth.

### 4.4 Variant matrix

| Variant | Contribution | Early implementation choice |
| --- | --- | --- |
| `fixed` | Current canonical semantic retrieval | Frozen comparator. Never change semantics or default. |
| `lexical_only` | Deterministic lexical recall | In-memory bounded fixture index first; optional native SQL extension if justified. |
| `semantic_only` | Existing version-compatible embeddings | Use canonical search when its issuer/embedding chain is available; otherwise explicitly unsupported. No fake embedding claims. |
| `hybrid` | Bounded union + rank fusion | Calibrate exact lexical/vector rank-based fusion without calling the model; no scores across incomparable spaces. |
| `hybrid_reranked` | Metadata/temporal/authority-aware reranking | Deterministic, conservative; corrections and trusted source validity are hard constraints, not learnable bonuses. |
| `topic_hierarchical` | Compact topic browse + selected on-demand fetch | Overview contains IDs/labels only; fetch revalidates actual record dependencies. |
| `adaptive_pack` | Context-budget assignment | Reuse shared builder; compare actual full-message tokens/quality/latency, not declared budgets. |
| `eligible_full_context` | Small-history upper bound | Only authorized, current source items and within actual hard context budget; mark oversized/infeasible honestly. |

Avoid a misleading “hybrid” comparison if the only data available has no compatible embeddings or the fixed baseline cannot represent it. Report unsupported arms and denominators explicitly. Never label the standalone PI-5 document search as the fixed memory baseline.

## 5. Retrieval and navigation algorithm

1. **Bind:** derive trusted principal/app/actor/project/source profile and exact `MemoryQuery` plus policy identity server-side; reject caller attempts to broaden scope or set currentness epochs.
2. **Plan:** take a bounded memory-only query (no generic external RAG); set global time, read count, candidate, topic, depth, token and byte caps before any index access. Sensitive query/embedding policies remain active.
3. **Eligible corpus:** query canonical owner-restricted records with lifecycle/source/revision/permission predicates, including separate knowledge type and source authority. If native store cannot guarantee pre-rank filtering, fetch a bounded compatible eligible corpus and score only eligible IDs; cap-overrun is **incomplete/denied**, not silent selection.
4. **Index health:** read/rebuild matching versioned topic/lexical index under exact namespace. On missing, mismatched or stale index, use fixed-safe fallback when truly equivalent or return `index_unavailable`; do not reuse a previous epoch/corpus index.
5. **Recall:** lexical candidate ranks and existing semantic ranks from the *same eligible universe*. Deterministically union and deduplicate by canonical record ID; ensure ties, normalization, and missing-arm handling are stable and explainable. No unrestricted query expansion.
6. **Rerank:** apply hard currency/scope/consent/correction validity first, then metadata/temporal relevance and query match. Separate observation time from effective time; negative/conflicting knowledge is not silently dropped to boost answer confidence. A verified procedure's historical success does not authorize execution.
7. **Navigate:** optionally return a terse directory of eligible topic labels/IDs. A topic fetch independently re-resolves each record and every source dependency; an unsafe or expired leaf is omitted/denied with a reason. Bounded backoff (e.g. one level / one extra page) may fetch more only under remaining budget, never after grant change.
8. **Pack:** turn records into existing `ContextBuildItem`/knowledge adapters with source references, permissions and authority labels; call shared `ContextBuilder` and honor source/global ceilings. On permission change, rebuild/remove affected blocks or deny before dispatch, not retain stale summary.
9. **Consume:** final host/source revalidation immediately before model disclosure and any downstream reuse. No implicit live model send is part of MEM-5's synthetic development authorization.
10. **Observe:** bounded, content-free counters for eligible/denied/incomplete, topic and source fetches, index generation, packed tokens, elapsed time and answer-utility labels; avoid exposing cross-scope timing/term counts to untrusted clients.

## 6. Work packages and staged delivery

### WP0 — Re-pin, reconcile and pre-register (must precede code)

- Inspect current HEAD, status, `AGENTS.md`, code and tests. Compare MEM-4 amended code with any new changes; record exact baseline commit and observed gates.
- Write a concise memory-retrieval research ADR/design note (dated docs are allowed to mention MEM-5) identifying the **one** owner of index versions/derivative cache, safe candidate APIs, legacy vs knowledge source boundaries, final revalidation, no-runtime-consumer policy and index invalidation/erasure.
- Pre-register policy IDs, bounded candidate/term/topic/token/deadline budgets and experiment comparator/fixture manifests before evaluation. Preserve historical dataset identities byte-for-byte.
- Define meaningful evidence tiers and a dependency/gate matrix. Decide whether any native persistence is required (bias toward no new migration until measured necessity).

**Exit:** in-session plan hardening documented, no index path with independent disclosure authority, baseline identities locked.

### WP1 — Hermetic corpus, eligibility and topic directory

- Add a small independent synthetic corpus representing cross-session procedures, explicit project decisions, corrections, duplicate preferences, a conflicting pair, unrelated owner/app/actor/project data, expiring grants, source revisions, regrant, withdrawal, missing source, stale snapshots, and low-information queries. Protect existing MEM-0–4 fixture hashes.
- Build deterministic normalization, lexical postings and topic grouping from **eligible** canonical-record-shaped fixtures. Require typed metadata/source references and a current synthetic issuer; generated topics cannot infer new facts.
- Provide list-topics and fetch-by-topic in a private research/test adapter with exact namespace and bounded depth/pagination. Separate topic metadata from fetched content and check source-currentness on every dereference.
- Implement explicit invalidation for correction, withdrawal, revocation, expiry, owner purge, scope change, regrant and index-generation switch, including restore/replay barriers. If safe durable invalidation is unavailable, keep the index ephemeral and rebuild from current canonical data.

**Exit:** determinism under reorder/replay, bounded index size, no stale/cross-scope leaf read even under concurrent withdrawal.

### WP2 — Lexical + semantic candidate retrieval

- Introduce a small private retrieval-policy seam that adapts current `MemoryRetriever`/`KnowledgeService`, **without altering default `fixed` behavior** or schema-3 admission semantics.
- Make lexical-only work completely offline. Reuse the existing compatible semantic path where available; mark genuinely unavailable embedding/query-provider arms `unsupported` and do not fabricate vectors. Synthetic embedding fixtures may test vector-fusion plumbing but must be labeled non-real-model/E1.
- Implement reciprocal-rank fusion or another deterministic documented fusion over **eligible**, source-verified record IDs, not raw unfiltered top-K. Compare recall/precision and costs of lexical, semantic and hybrid on the same corpus; add candidate exhaustion and adversarial ties.
- Preserve request timeout, cancellation, unknown-result semantics, no unbounded enumeration, and explicit max retained entry/index bytes.

**Exit:** no unauthorized candidate ranking; reliable union/dedupe; legacy semantic-only baseline unchanged.

### WP3 — Filters, conservative rerank, hierarchical fetch

- Add trusted metadata filters (record type, project, source class, revision, verified status, time range) and temporal boosts with a frozen clock. All soft relevance adjustments occur **after** hard eligibility and must never override user correction/forget, provenance, contradiction or exact scope.
- Implement a deterministic topic→leaf fetch plan and one bounded fallback expansion for queries that need detail. Every expansion repeats authorization/currentness and applies the original request budget.
- Treat unsupported questions as abstentions with accurate source citations; never synthesize aggregate facts from incomplete evidence. Test prompt injection in labels, poisoned metadata, incorrect topic ancestry, ambiguous names and held-out queries.

**Exit:** navigable scoped index with complete source provenance, stale/ambiguous cases abstain or deny.

### WP4 — Adaptive context packing

- Experiment with at least three bounded policies: fixed memory allocation, conservative request-aware allocation based on other occupied context classes, and a selected adaptive policy using estimated answer value/record size. Keep complete original evidence references.
- Feed candidate `ContextBuildItem`s and requested policy budgets through the **same** builder, token counter, source permission revalidator and final disclosure path. Do not precompose unmetered text or drop a stronger source class to fit more memory.
- Compare actual packed content IDs, endpoint count, truncation/omission, bad-citation rate and task answer quality at the same total context ceiling. Record when eligible full-context is feasible and when it is not.

**Exit:** builder parity and no overflow; no source/citation dependency loss in hierarchical or compact views.

### WP5 — Durable index only if justified, native verification where possible

- Prefer ephemeral index over an additional SQL schema unless data-volume/restart measurements establish a genuine requirement. If persistence is chosen, add an *additive, forward-only* migration after the current latest migration; validate canonical owner fences and source-version CAS in one read/refresh/erasure design. No unscoped materialized views.
- Run isolated PostgreSQL/pgvector tests where a disposable `PERSISTENCE_TEST_POSTGRES_DSN` is available: two-process concurrent index generation; grant/forget racing top-K, index rebuild, crash before/after invalidate, lost ACK, stale read after rollback, owner erase, quota exhaustion, and obsolete index generation refusal. Never point tests at user data.
- Independently distinguish local transaction evidence from cold restore, MVCC/replica/backups, external issuer or live provider validation. If native environment unavailable, keep rigorous in-memory/concurrency tests and mark native **BLOCKED**, not passed.

**Exit:** current code handles safe index maintenance/rebuild; no falsely claimed E2+ evidence or new authority.

### WP6 — Reproducible evaluation and research report

**Study design:** pre-register at least ~30 representative **additive** task cases across ≥6 families; target 6–10 paired multi-session transfer tasks and explicit stale/corrected/permission negatives. A subset must be genuinely independent/held-out for any generalization claim; author-created fixtures alone are author-visible E1, not independent.

| Family | Illustrative objective |
| --- | --- |
| Exact and paraphrased recall | Retrieve a verified repository procedure/decision and exact preconditions. |
| Lexical vs semantic divergence | Rare identifier where lexical wins; paraphrase where embeddings help; missing embeddings = unsupported. |
| Multi-session cross-task utility | Prior verified lesson improves a separate later task without leaking source-only details. |
| Temporal, correction, contradiction | Prefer current explicit correction, distinguish as-of claims, disclose unresolved conflict. |
| Topic/hierarchical navigation | Find a fact in a multi-topic history within depth/token budgets; wrong-topic and stale leaf negatives. |
| Privacy, grant and revocation | Deny cross-owner/app/actor/project; withdrawal/regrant, owner purge and stale index/restore. |
| Stress, full-context and budget | Small history where full eligible context wins; large history/candidate overflow; time/cost/latency. |

**Arms:** existing `fixed` with frozen semantics; lexical; semantic where legitimately supported; hybrid; hybrid+rereank; topic/hierarchical; adaptive; eligible full-context where feasible; a gold-authorized evidence ceiling if useful. Optional MEM-4 pending **fixture** index must be a separate clearly named development-only arm, never a canonical memory arm. `no_memory` remains a useful floor. Use the same model/build, prompt, task input, known grants, serializer, device, context/output/deadline budgets and instrumentation for every supported arm.

**Measures:** top-K recall and precision *plus* end-task success/abstention, exact source attribution, false support, stale/scope leak counts (hard veto), answer quality, actual packed tokens, prompt and retrieval tokens, estimated vs reported usage, latency, index build/refresh time/size, lookups, provider calls, cost and cost-confidence classification. Report per-family distributions, paired deltas/confidence intervals where sample size permits, denominators, unsupported/incomplete/timeout/failure rows and hardware. A result with fewer tokens but worse safety or task success is not a promotion candidate.

**Pareto criterion:** a candidate must be non-dominated or meaningfully improved in measured quality/token/latency/cost *and* show **zero observed critical authority/revocation violations** on the locked negative suite. Do not invent a numeric win threshold before baseline distributions are measured. No MEM-6-style automatic promotion; export a recommendation only.

**Evidence:** E0 architecture/static review; E1 hermetic scripting and synthetic tests; E2 native local DB/pinned local model when genuinely run; E3 hosted/live source with explicit rights (not authorized here); E4 deployed restore/erasure; E5 independent longitudinal task utility. Scripted answer parser accuracy is not model utility. Blinded tasks must be independent of the implementation author and model runner, with immutable manifest and retained failed trials.

### WP7 — Documentation, gates and handoff

- Update the owning memory/evaluation README and `docs/current-state.md` (capability-named, honest default-off status). Add a dated implementation/architecture receipt with source and fixture digests, executed commands/results, failures, skips, environment, source-identity drift, feature/rollback contract, and remaining authority/issuer/E2–E5 gates.
- Do not change historical gate identities or mark `episode-development-blockers.json`, consolidation blockers, independent acceptance or release NO_GO as closed without independent evidence. If new code changes planning v35 source identity, record failure and propose an **additive**, reviewed generation rather than modifying frozen locks.
- Finish with a concise acceptance matrix and a named next step for independent Sol High review and subsequent Luna High/XHigh remediation/final verification. No automatic post-Luna review.

## 7. Required adversarial and concurrency matrix

| Test | Expected safe result |
| --- | --- |
| Mixed-scope index with high-scoring other-owner record | Other-owner entry never eligible, ranked, exposed or packed. |
| Grant revoked after candidate lookup, before topic fetch | Fetch denies; no stale excerpt or topic detail. |
| Grant revoked after pack, before physical send | Final host fence aborts/removes affected context; no disclosure. |
| Regrant after revoke; stale index replay | Prior epoch never resurrects; new source identity requires fresh verified evidence. |
| Explicit correction conflicting with high-ranked stale memory | Corrected state preserved; stale content excluded or conflict clearly represented. |
| Bad topic metadata / poisoned title with “ignore instructions” | Text treated as untrusted metadata or rejected; no instruction execution. |
| Over-capped corpus or unbounded topic expansion | `incomplete`/deny under finite cap; never an authoritative empty/no-memory answer. |
| Embedding model/dimensions/normalization mismatch | Semantic arm unsupported/denied; no cross-space similarity. |
| Duplicate and near-duplicate memories | Preserve separate identities/evidence; exact dedupe only under canonical policy. |
| ANN/lexical mixed filtering (if ANN added) | No post-top-K privacy leak or eligible omission masked as recall success. |
| Cancellation/timeouts/lost ACK/rebuild races | No leaked buffers, stuck lease, invalid read generation, or new authority. |
| Index/cache or SQL restored to stale snapshot | Current authority epoch rejects stale content; if full issuer unavailable, deny and mark restore E4 BLOCKED. |
| Owner deletion during query or background rebuild | No result after terminal fence; payload cleanup/retention claims match actual tested boundary. |
| Huge term/topic path, adversarial Unicode, malformed source IDs | Bounded validation/size; stable deterministic error reasons; no PII trace. |
| Full-context would be feasible and better | Report it as a stronger baseline; do not declare hybrid universally superior. |

## 8. Verification commands and recording rules

Inspect the live Makefile before executing; do not assume preexisting research targets. Typical inherited checks:

```bash
git status --short
git rev-parse HEAD
make memory-eval memory-optimization-eval memory-knowledge-eval memory-knowledge-causal-eval
make memory-control-eval memory-consolidation-check memory-consolidation-eval
make context-eval context-plan-eval naming-policy-check backend-lint
make backend-test-offline
git diff --check
```

Add capability-oriented focused checks for new retrieval/index research, and opt-in native PostgreSQL tests if a **disposable** fixture is available. Do not run cloud/paid providers, mutate user data or assume model install. Record each command's exact environment, pass/fail/blocked/not-run, case counts and durations. Re-run old frozen suite identities unchanged; if a source-lock check fails because code changed, preserve that failure and isolate additive source generation work for separate review. An unchanged historical failure is still a failed gate.

## 9. Gates, deferral discipline and acceptance

| Gate | MEM-5 development requirement | Live/promotion requirement |
| --- | --- | --- |
| E0 architecture | Concrete ownership, index-generation, source filter and rollback design | Reviewed and accepted alongside cross-program contracts. |
| E1 synthetic functionality | Runnable deterministic topic/lexical, hybrid wiring where available, filtering/rerank/navigation/packing; adversarial fixtures and measured paired script-level outcomes | No assumption of task-model quality. |
| Native E2 component | Run if disposable Postgres/pgvector available; else explicit BLOCKED with test code and setup | Independent native re-run, real model for actual utility claims, tested erasure/lease behavior. |
| MEM-3 source issuer | **Not needed** for sealed synthetic-only research adapter | Required before any episode fetch/index or private-history auto-use. |
| MEM-4 consolidation | Isolated synthetic pending proposals may be **optional** comparator only | Trusted eligible producer, accepted proposal review/admission and current lifecycle edges. |
| E3/E4/E5 | None claimed | Explicit source rights/send policy, deployed issuer/revocation/backup/restore, blind real-task evidence and independent review. |
| Production release | Remains NO_GO | All inherited release and memory gates closed; MEM-6 owns policy promotion, MEM-7 owns memory-specific governance/scale. |

**Definition of done for the E1 research slice:** topic directory and lexical index work; semantic/hybrid arms either genuinely run or clearly declare unsupported with an executable adapter contract; strict all-stage revalidation; deterministic reranking, hierarchical fetch and builder-based adaptive packing; bounded concurrency/resource tests; versioned manifests and comparable reports; no default behavior change or runtime source disclosure; honest unresolved native/live gates. Prefer completing practical components before deferring: defer *only* where trusted producers, external issuers, native services, operator models/accounts or independent blinding are genuinely unavailable.

**Independent review decision:** `ACCEPT E1 DEVELOPMENT CANDIDATE`, `CHANGES REQUIRED`, or `BLOCKED`, separately from `PRODUCTION NO_GO`. There is no automatic activation.

## 10. Rollback and migration strategy

All research variants are default-off, test/profile scoped, with an explicit kill switch. Disable new query policy and index consumer; legacy `fixed` path returns unchanged results. Derived indexes can be invalidated/rebuilt without changing canonical memory, source events, original receipts or user corrections. SQL schema additions, if any, are forward-only and read-compatible; do not destructively drop on rollback. Preserve tombstones/owner fences and do not restore stale grants. Any unusual persistence growth, source-epoch mismatch, index corruption, or permissions uncertainty fails closed.

## 11. Next phase boundaries

- **MEM-6:** independent longitudinal experiment registry, blinded evaluation, comparative promotion/rollback; MEM-5 exports immutable experiment artifacts, not a promotion decision engine.
- **MEM-7:** real cross-agent grants, retention/external erasure, replica/backup recovery, production scale and memory governance. MEM-5 cannot grant itself production authority.
- **HXE-1:** MCP/external document ingestion. Do not conflate its source indexes with memory-specific retrieval policy.
- **HXE-2:** shared telemetry, model identity and attempt accounting. MEM-5 contributes memory metrics through this path.
- **RE-0–5:** effort selection/adaptive reasoning policy, outside memory ranking semantics.

## 12. Source anchors

1. [Current repository and `main`](https://github.com/jasonkli21/personal-ai-system/tree/fe1915ec50d075eb9eba7b4d51c8d56527adc3fc).
2. [Integrated Roadmap v3.1](https://github.com/jasonkli21/personal-ai-system/blob/fe1915e/docs/personal-ai-system-integrated-roadmap-11-03.md) (MEM-5 definition, freeze and program ownership).
3. [Memory Architecture & Research Roadmap](https://github.com/jasonkli21/personal-ai-system/blob/fe1915e/docs/memory/memory-architecture-and-research-roadmap.md) (Stage 5 algorithm and task-level exit).
4. [Memory README](https://github.com/jasonkli21/personal-ai-system/blob/fe1915e/backend/src/personal_ai/memory/README.md) and [Context Builder](https://github.com/jasonkli21/personal-ai-system/blob/fe1915e/backend/src/personal_ai/context/builder.py).
5. [MEM-4 review remediation](https://github.com/jasonkli21/personal-ai-system/blob/fe1915e/docs/memory/2026-11-04-consolidation-review-remediation.md); [MEM-3 blockers](https://github.com/jasonkli21/personal-ai-system/blob/fe1915e/docs/memory/episode-development-blockers.json); [MEM-4 blockers](https://github.com/jasonkli21/personal-ai-system/blob/fe1915e/docs/memory/consolidation-development-blockers.json).

**Research principle:** A memory index is valuable only if it improves what an agent can correctly accomplish under a known budget without weakening user control over remembered information.

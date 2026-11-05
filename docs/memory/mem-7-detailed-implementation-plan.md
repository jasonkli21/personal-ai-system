# Personal AI System — MEM-7 Detailed Implementation Plan

**Phase:** MEM-7 — Memory Governance, Sharing, and Production-Scale Readiness  
**Prepared:** 2026-11-04 (America/Los_Angeles)  
**Repository:** https://github.com/jasonkli21/personal-ai-system  
**Planning baseline:** `main` at [`b694c5f26e0c5fc21880bac06f1fdf2eac5ca650`](https://github.com/jasonkli21/personal-ai-system/commit/b694c5f26e0c5fc21880bac06f1fdf2eac5ca650)  
**Strategic sources:** *Integrated Harness Excellence Roadmap* v3.1 (2026-11-03), *Memory Architecture & Research Roadmap* (2026-10-28), repository code/ADRs and dated implementation/review evidence.  
**Status:** Implementation plan, **not** a finding of independent acceptance, authorization to access real data, or production release. Re-pin the repository before executing.

## 1. Decision and definition of done

Build a **portable, policy-governed memory-sharing and lifecycle capability** over existing canonical memory records, using explicit, versioned grants rather than treating a shared database, matching user identifiers, or an agent's request as consent. Preserve user inspection, correction, forgetting, data portability, retention and deletion; prove meaningful cost and failure behavior at the evidence tier actually exercised.

MEM-7 is the **memory-specific** ownership boundary. HXE-4 owns product-facing owner controls and portability UI/API; HXE-5 owns overall product/deployment release. The existing authentication, profile consent, source issuer, memory lifecycle, context builder, Postgres/pgvector persistence, Dynamo jobs and HXE-2 telemetry continue to own their respective functions. Do not install a second identity/grant service, memory database, context assembler, execution state machine, or general release mechanism.

Two different acceptance decisions are mandatory:

1. **Bounded implementation acceptance (E0/E1):** deterministic, public/synthetic, default-off contracts, grant/retention/deletion simulations, adversarial tests, quotas, dry-run operational drills, evidence ledger, docs and rollback; optional independently provisioned disposable native component tests. A successful E1 candidate may legitimately be complete *at that narrowed tier*.
2. **Full MEM-7 phase exit / production promotion:** independently verified runtime issuer and recipient identity; authorized agent/project grants and later revalidation; native Postgres/Dynamo and cloud/backup recovery; physical deletion/restore; non-resurrection, realistic scale and cost; separate user and reviewer approval, appropriate real task evidence, canary and rollback. Current code does **not** satisfy this decision. Record `PHASE_EXIT_BLOCKED / PRODUCTION_NO_GO` until each claimed topology is proven.

Complete all useful offline implementation and fault testing now. Only defer a test or live operation when it genuinely needs external authority, configured infrastructure, unbuilt producer integration, deployment credentials, a third-party recipient or independent custody. Never simulate E2–E5 evidence and label it native/live.

### 1.1 Key existing facts at the planning revision

| Area | Actual code/evidence boundary | Consequence for MEM-7 |
| --- | --- | --- |
| MEM-1 verified knowledge | Schema-3 `procedure` / `project_decision`, migration `028_verified_memory_knowledge.sql`, current source/project lease and lifecycle restrictions; admission/selection flags default off | Reuse records and fences. A shared grant cannot elevate user assertion or pending suggestion to verification. |
| MEM-2 controls | `memory/control_{contracts,service,repository,tools}.py`, migration `030`, scoped search/fetch/topics, agent proposals, authenticated review/reject and user forget; missing production replacement issuer and native receipt/capacity evidence | Extend authority at trusted boundaries, **not** agent-minted `owner_id`/`actor` fields or self-approvals. |
| HXE-4 owner experience | `memory/portability.py`, `api/memory_portability.py`, `docs/memory/owner-portability.md`; profile-only explicit-field export, import **preview only**, grant controls elsewhere | Do not broaden profile export into arbitrary knowledge export or turn preview into import commit. |
| Profile cross-app consent | `context/profile_consent.py` supports bounded explicit profile disclosure grants | Use as a pattern, **not** a memory-share grant that changes persisted knowledge scope by implication. |
| MEM-3 episodes | Migration `035` and local erasure exist, but capture and selection are **hard-disabled**, even with constructor flags | No agent trace export, cross-agent episodic read, or automatic capture in MEM-7. |
| MEM-4 consolidation | Synthetic pending-only proposals; migration `036` has a limited native component seam but not live source epochs/backup erasure | A derived proposal never becomes shareable verified memory by a grant alone. |
| MEM-5 navigation | Default-off sealed E1 retrieval/index research; no real semantic/hybrid provider or blind utility proof | Grant checks must precede selection and repeat before packing/consumption, regardless of index ranking. |
| MEM-6 research | Commit `0289ac1` plus review remediation `b694c5f`; 48 author-visible synthetic cases, 3,528 grid rows, dry-run decision custody | Corrected primary matched scripted Task-B quality delta is **0 pp across 25 eligible pairs**. Earlier +20 pp was strategy-confounded. No real-model task uplift, no effective policy promotion. |
| HXE-5 / Phase 36 | Release profiles remain `NO_GO`; independent acceptance, source/identity, native/cloud IAM, physical erasure/recovery and cost evidence open | No MEM-7 work can silently close these shared release gates. |

Read, in precedence order: `AGENTS.md`, `docs/README.md`, `docs/current-state.md`, `backend/src/personal_ai/memory/README.md`, relevant executable contracts/migrations/tests, dated reviews, ADRs, then roadmap. The active repo may have advanced; this table is **not** a substitute for a fresh entry audit.

### 1.2 Roadmap freeze and execution authority

Integrated Roadmap v3.1 explicitly says MEM-3+ is frozen absent an **owner decision, readiness ADR, evidence-aware scope and narrow independent review**. This planning file does not lift it. A future owner-initiated Codex run using the accompanying implementation prompt can authorize **only the E0/E1 public/synthetic development slice** described here. If the owner has not authorized even that scope or a repo policy still forbids it, write the readiness/ADR and stop before behavior changes. Nothing here grants live user-data ingestion, production feature enablement, provider dispatch, external agent sharing, cloud access, or deployment.

## 2. Scope and authority matrix

### 2.1 In scope for the bounded Sol Medium implementation

- Versioned strict **memory grant intent, policy evaluation, effective-rights snapshot and receipt** contracts; no wildcard or inferred sharing.
- Trusted-host-issued identity/grant test seam and a sealed public/synthetic **two-agent, two-project** evaluator; separate memory owner, source app/project, recipient agent/service identity, destination app/project, purpose and authorized operations.
- Pure grant decision and explicit revoke/expiry/correction/forget/regrant state-machine tests using canonical source/owner epochs; simulated pre-selection, pre-pack, pre-consume and pre-dispatch fences.
- A minimally scoped **canonical persistence adapter** only if its trust and replay contract can be implemented safely; otherwise complete strict repository protocols and hermetic integration with a precise native blocker. Avoid a production-reachable mutating API merely to make an E1 test convenient.
- Owner-facing *capability/receipt metadata* and dry-run export/retention/erasure plans for permitted data classes. Preserve HXE-4's current profile export-only behavior; offer synthetically testable previews and explicit unavailability for unsupported knowledge import/export.
- Dependence-aware erasure graph and fail-closed restore/reconciliation model, including physical-erasure evidence schemas that distinguish confirmed/local/pending/unknown.
- Storage/operations quotas and maintenance budgets with safety-reserved capacity, backpressure, bounded pagination and bounded denial reasons; injected clock and deterministic fault tests.
- A documented E2–E5 operator drill/runbook and **non-effectful** canary/rollback plan with exact no-go checks, plus reproducible E1 fixtures/metrics.

### 2.2 Explicitly out of scope absent later authorization and evidence

- Accepting model-provided grants, beneficiary identity, owner confirmation, policy epochs or a source lease as authoritative.
- A live cross-agent sharing endpoint, auto-sync, global cross-user search, bulk export of private knowledge/episodes, external delivery of memory text, scheduled capture, automatic proposal promotion, real model calls or hidden provider spend.
- Changing MEM-3 capture/selection hard-denial; enabling MEM-4 proposals; changing MEM-5/MEM-6 policy default; adding new domain authority or copying content into other agents' durable stores.
- A second memory store, generalized distributed ACL/identity service, product release pipeline, or unrelated Phase 36/PI source-lock repairs.
- Claiming exported files or recipients' already-downloaded copies can be recalled. Internal revocation blocks **future managed reuse**, not external copies.

## 3. Architectural contracts and invariants

### 3.1 Trusted scope and subject model

The **requester** is an independently authenticated human or delegated service. The **beneficiary** is an exact registered agent/service identity within an exact destination application/project/workspace. The **memory subject** is canonical owner-scoped knowledge in a source application/project. The owner/project mapping is resolved by trusted host code; matching names, email addresses, UUID shapes, shared storage, or model-provided tags establish nothing.

Minimum closed fields (names illustrative; reconcile with existing strict Pydantic idiom before implementation):

| Contract | Required fields / constraints |
| --- | --- |
| `MemoryShareIntent` | `operation_id`, `grant_id`, `grant|revoke`, `expected_revision`, strict source memory ID and source identity, **exact** target registered agent principal + app/project/workspace, fixed purpose, allowed read-use operations, expiration, human-confirmation reference; no unknown fields or user-chosen owner. |
| `TrustedGrantContext` | Verified owner principal and freshness, source rights/lease issuer, recipient registry binding, destination permission, current source/project/deletion/permission epochs, policy version, scoped original operation identity; only host can construct. |
| `MemoryShareGrant` | Stable ID; `active|revoked|expired` with monotonic revision/epoch; exact source and destination; purpose; rights ceiling; issuing actor and time; source-identity/version fingerprint; user decision and expiry; no wildcard/transitive/delegable scope. |
| `GrantDecision` | `allowed|denied|unavailable|stale|capacity` plus safe reason code, current policy/grant/source epochs, permitted operation/scope, bounded dependency IDs for internal use; no private text or existence oracle in denial. |
| `GrantOperationReceipt` | Original operation key and input fingerprint, before/after revision, durable committed-vs-uncertain status, trusted principal class, timestamp and hash/provenance; same-key different-body is conflict. |
| `DeletionPropagationReceipt` | Canonical owner/subject fence, affected record/index/cache/summary/derived/view/episode/artifact type counts or opaque IDs, source authority epoch, per-store status, physical-vs-logical status, backup/replica horizon, verification tier and unsatisfied edges. |
| `QuotaSnapshot` | Owner/namespace count and bytes, records/grants/receipts, tombstone/fence reserve, pending operations, page/read/tool cost, maintenance rate and budget, measured vs estimated cost and observation period. |

Hard bounds: cap active grants, maximum descendants, target identities, purpose vocabulary, TTL, receipt sizes, fan-out, content/metadata length, concurrent workflows and total bytes. Pick constants after reviewing current quotas (e.g. MEM-1's 128 record / 1,024 fence limits, MEM-2 retained forget receipts and proposal caps); document rationale, schema migration compatibility and overflow outcomes. Unknown policy field/version must fail closed. Avoid exact internal counts/IDs in a denial surface that could leak source existence.

### 3.2 Authorization decision order

1. Authenticate caller and confirm fresh human authority for grant/revoke; resolve principal, owner and requested source/destination from *trusted* registries.
2. Read current canonical source, user deletion state, project ownership/permission, source epoch, verification/expiry, lifecycle version and content sensitivity restrictions. A pending/unverified/forgotten/quarantined source is never grantable.
3. Compute an intersection (never union) of owner policy, source rights, trusted identity/delegation, target app/project/agent, requested purpose, operation and record classification; disallow default broadening.
4. Transactionally CAS grant revision/original-key operation and required owner/epoch fences; return durable committed or explicit unavailable/uncertain with reconciliation key.
5. For every read candidate, verify **at selection, pack, and physical consumption/send**, not just grant creation. Shared context builder still assembles output. A stale/unknown lease cannot imply permission to send.
6. Revoke/forget/expiry immediately advances logical ineligibility and invalidates all derived/cache/packed uses. Monotonic authority must survive an older backup's restore; an in-process counter alone is insufficient for deployed acceptance.

**Security rule:** Agent text, prompt, memory payloads, imported JSON and research receipts are untrusted data. They cannot instantiate `TrustedGrantContext`, change policy, grant themselves rights or authorize tool effects. Do not infer access from `MemoryQuery` filters alone.

### 3.3 State, concurrency and replay

Represent at least `absent → active → revoked|expired`; a new approval after revocation must be a **new generation** (or ID), with a monotonically increasing authority epoch. Never let an old ID and matching scope produce an ABA resurrection. Require expected-revision CAS and unique original `(owner, trusted actor, operation_id)` with immutable input fingerprint; duplicate exact operations reconcile to the original receipt; mismatched body rejects. For crash windows, distinguish `not_committed`, `committed`, `response_lost`, `effect_unknown`. No exactly-once external-delivery claim without fenced physical dispatch/reconciliation.

Do not turn the sharing state machine into a second memory lifecycle. It is a **read-use capability overlay** on canonical source and lifecycle authorities. A memory revision, correction, source replacement, content classification change, project revocation, user forget, deletion request, or retention expiry invalidates grant eligibility by dependency, even if the grant row still says active. A grant never copies or mutates source content. No transitive grant sharing or cross-owner delegation in v1.

### 3.4 Physical-retention and erasure graph

Build a typed dependency inventory and revocation/erasure propagation graph for: canonical memory and verification/source edges; lifecycle and grant rows; search/topic/semantic derived indexes; packed contexts/history/summaries; pending proposals; episode and consolidation projections; research artifacts/receipts; caches; exports; Dynamo outbox/jobs; Postgres MVCC/replicas/backups; object storage and external recipients. Distinguish data-bearing artifacts from content-free compliance receipts/fences and reason about legal/operational retention explicitly.

- **Forget/revoke:** immediate no-reuse fence in serving paths; asynchronous cleanup can follow only when no path may read stale bytes.
- **Physical erase:** store-specific actual purge and verification; evidence must identify remaining replicas/backups, retention schedule and out-of-system copies as `pending`/`unverifiable` rather than `done`.
- **Cold restore:** reconcile with a separately surviving monotonic authority/fence before serving *any* restored record; stale snapshots cannot overwrite newer forget/grant revocation.
- **Export:** issue bounded, user-directed, class-specific download with warning; no credentials, private tool payloads, unverifiable old records or grants-as-authority; imported files cannot carry live rights. Any proposed knowledge export/import extension is a separate reviewed, disabled capability.
- **Lifecycle quota:** tombstones, original-key receipts and revocation fences cannot be silently evicted to satisfy a size cap. If safe compaction cannot be demonstrated, report capacity and block new sharing/creation rather than unsafe forget.

## 4. Detailed work packages (one Sol Medium implementation session)

### WP0 — Fresh entry audit, readiness ADR and plan hardening

1. Record exact HEAD/tree/branch/status, environment and existing changes; preserve unrelated work. Read code/contracts/migrations/tests and dated evidence rather than trusting roadmap summaries.
2. Make a **capability/evidence matrix** of MEM-0–6, HXE-4, HXE-5, PI source/identity/restore and Phase 36 gates: accepted? candidate? default? evidence tier? missing issuer? independent acceptance? precise unblock test?
3. Explicitly reconcile latest MEM-6 corrections: 0 pp/25 eligible scripted pairs, 3,528 attempted rows; historical +20 pp is not valid causal memory lift; pending blind challenges and real-model evidence; existing PI-6 source-lock and offline suite failures. Preserve old datasets and receipts.
4. Write `docs/memory/<date>-governance-readiness.md` with threat model, source/recipient trust ownership, the owner's narrowed E0/E1 authorization, release freeze, evidence-tier split, design choices and a list of rejected expansions. If authorization cannot be established, stop at the decision/report rather than coding.
5. Plan-harden critically *in the same session*: examine whether a new grant primitive is necessary versus extending current profile consent, whether dual source/grant epochs are sufficient for revoke/send ordering, and whether a native adapter is justified. Make decisions before editing code.

**Exit:** documented exact scope, failed/unverified gates, minimal design and finite acceptance checklist.

### WP1 — Closed grants and strict negative capability

1. Introduce enduring names (e.g. `memory/governance/{contracts,policy}.py`), not phase IDs in active code/tests/public commands.
2. Model exact subject/beneficiary/purpose/operation, source and policy epochs, expiry, correction/version dependency, expected revision and non-delegability. Use finite constraints/limits and canonical serialization.
3. Build a pure policy evaluator with host-injected trusted proof objects not constructible from wire requests; source-rights and recipient registry protocols are host-owned and unavailable by default.
4. Ensure `unknown`, `unavailable`, stale epoch, wrong user, wrong project, wrong agent, wrong purpose, sensitivity, expired source, pending record, insufficient target registration, revoked app and unsupported schema all deny safely.
5. No new production factory, route, live flag or tool registration for the grant path in this WP.

**Exit:** serialization/property/adversarial tests; no prompt-shaped input can widen rights or mint trusted proof.

### WP2 — Grant lifecycle, synthetic cross-agent serving and transactional semantics

1. Implement a bounded in-memory deterministic adapter and two independent simulated registered agent principals for test/eval. Use existing `RequestScope` and canonical source/knowledge/lifecycle authority adapters, not agent-declared owner scope.
2. Implement strict original-key idempotency, same-key different-payload conflicts, CAS, source revision epoch pinning, regrant ABA denial, expiry and concurrent revoke/read tests. Version every dependency; reject authorization evidence from stale snapshots.
3. Exercise selection → builder packing → tool/consumer use under fresh fences. If trusted host provider is absent, return `unavailable` and zero content. Never install model-facing registration merely for tests.
4. If a canonical Postgres adapter is viable without inventing a producer/source issuer, implement behind an opt-in test-only factory and migration with owner fences and native tests; otherwise implement protocol + E1 with precise blocker. Do not promise cross-process durability from a process-local lock.
5. Check live external send atomicity explicitly as an **unsatisfied dependency** unless a trusted physical-send lease and cancellation/recheck actually exist.

**Exit:** legal exact grant in synthetic fixture works; all altered source/recipient/scope/expiry/forget permutations deny; no duplicate effects or stale success claims.

### WP3 — Owner controls and safe portability contract

1. Integrate **non-effectful** inspect/preview/proposal operations with existing HXE-4 owner-control semantics and verified identity checks. A human must see precise memory class, destination agent/app/project, purpose, expiration and copy warning before any future effective grant.
2. Retain existing owner profile export/preview routes byte-compatible. Any new grant receipt export is content-free by default and explicitly separate; unsupported knowledge export/import is surfaced as unavailable, not silently partial complete.
3. Design or add bounded preview validation for future memory bundles: source provenance, deletion/expiry, cryptographic integrity vs authentication distinction, no imported owner grants, no automatic namespace remapping, no quarantined record promotion.
4. Add tests for stale owner auth, same-owner wrong acting user, revoked app, injected `grant` field in imported JSON, hidden consent field, UI error disclosure and outstanding profile deletion fence.

**Exit:** owner can reason about synthetic grants and supported profile controls; no unapproved content export or import commit.

### WP4 — Retention, forget, propagation and restore drills

1. Build a typed dependency graph inventory with cardinality caps and origin evidence. Cover source→verified record→derived view/index→packed output; episode/consolidation projections are inventory-only if hard-disabled.
2. Add deterministic forget/revoke/expiry propagation planning and acknowledgement semantics. Use canonical deletion authority, not new arbitrary background writers. Preserve irreversible user-request receipts/fences from quota eviction.
3. Inject crash/lost ACK, independent worker, stale grant cache, stale index, changed source epoch, stale project rights, backup older than forget, delayed Dynamo job and multi-actor race. Require fail-closed restore denial until anti-rollback reconciles.
4. Emit per-store `verified|pending|blocked|unknown` with scope, topology, evidence tier and timestamps. No blanket `deleted` success from an in-memory tombstone.
5. Document native PostgreSQL, pgvector, Dynamo, replica, backup and object storage probes as explicit **future runbook** entries unless actual isolated infrastructure is approved/available.

**Exit:** public/synthetic non-resurrection proofs and honest physical-erasure limitations.

### WP5 — Quotas, finite maintenance and cost visibility

1. Account separately for grant count/bytes, retrieval amplification, index bytes, pending proposals, original-key receipts, tombstones, source fences, background jobs, retry attempts, export bytes and per-namespace activity.
2. Cap writes/reads/fan-out, retention and cleanup batches; use source/owner-fenced pagination rather than unbounded scans. Reserve safety capacity for delete/revoke/reconciliation. Define spill/overflow policy that **cannot** drop required revocation state.
3. Simulate quota exhaustion while a forget, revoke, erasure, restore, grant renewal and retry are in flight. New grants may be denied; safety actions must succeed or return an explicit durable pending/unavailable state with replay/recovery, never fabricated completion.
4. Produce scripted E1 counts/estimated memory, CPU/latency and maintenance work. Reserve distinct fields for observed native DB/storage/egress, actual model tokens, billed cost and idle cost; default unknown when not measured.
5. Free-first posture: no paid embedding, external model or storage call without separately approved account, monetary ceiling and dispatch admission.

**Exit:** no silent unbounded job/cache/receipt growth in tests; quantitative resource and storage-envelope report with uncertainty.

### WP6 — Operational failure campaign, canary and rollback dry run

1. Create a fixed, versioned synthetic suite and table-driven **at least 36** governance cases across six families (grant/scope; revocation/regrant; lifecycle/forget; export/restore; concurrency/replay; quota/operations). Include 8+ cross-agent/project positive/negative pairs and 8+ temporal mutation cases. All cases author-visible, with explicit limitation; do not claim blind holdout.
2. Include at least 2 fresh-process deterministic reproductions; record exact source hash, manifest, fixtures, schema version, full attempted denominator, unsupported rows and outputs. Preserve historical MEM fixture bytes/hashes unchanged; use additive source generation when dependencies drift.
3. Run dry-run canary with finite stages, vetoes and rollback target; no effective runtime, grant, flag, DB, provider or external data mutation. Threat scenarios include malicious memory text, forged grant receipt, restored stale grant, cross-owner identity confusion, a late physical send and a quota deadlock during erase.
4. Produce operator runbook with E2 disposable DB verification, E3 authorized identity/source/send, E4 distributed/cloud/recovery/deletion, E5 cross-session multi-agent utility and independent review, each with preconditions, expected evidence and stop conditions.

**Exit:** deterministic E1 campaign, separate observed-vs-unobserved metrics, default-off/NO_GO verified, rollback-plan purity.

### WP7 — Docs, validation and independent-review handoff

1. Update `docs/current-state.md`, `docs/README.md` only if routing changes, `backend/src/personal_ai/memory/README.md`, the owner-control docs if behavior changes, and a dated implementation/release-blocker receipt. Explain every default and unsupported profile.
2. Run focused contract/policy/lifecycle/authorization/context/import-export/replay tests; related memory evaluations; `make backend-lint naming-policy-check`; suitable `make backend-test-offline` and `make planning-eval` with exact environment and outcomes.
3. Preserve known historical frozen planning/PI-6 identity failures and native unavailable cases in evidence. Do not weaken a test, overwrite a frozen input, or call the full suite passed if it was not.
4. Deliver one self-contained reviewer handoff with revision, files, commands, failing/skipped tests, raw receipts/digests, coverage gaps, exact integration topology and all remaining gates.

**Exit:** independently reproducible E0/E1 slice, explicit block on full phase exit, no hidden enablement.

## 5. Adversarial and acceptance matrix

Each row is `PASS`, `FAIL`, `BLOCKED` or `NOT_RUN`, with **evidence tier, exact test/receipt, observation environment and status owner**. A generic passing script cannot substitute for E2/E3/E4/E5.

| ID | Required test / proof | Minimum E1 target |
| --- | --- | --- |
| G01 | Fresh commit/tree/status, route docs and historical evidence reconciled | Exact inventory and readiness ADR |
| G02 | Default-off flags, hard-disabled MEM-3, pending-only MEM-4, fixed policy preserved | No changed runtime effect |
| G03 | Host-only owner/actor/beneficiary/source resolution | Forged wire principal denied |
| G04 | Source+recipient app/project/workspace exact grant | Cross-scope negatives denied |
| G05 | Purpose/operation ceiling, no wildcard/transitive grant | All escalation attempts denied |
| G06 | Unverified, expired, superseded, sensitive, unknown-origin source | No grantable content |
| G07 | Grant CAS, original-key replay and mismatch | One durable intent outcome; conflict safe |
| G08 | Source revision/project epoch/owner deletion fence | Stale-source use denied |
| G09 | Concurrent revoke/selection/packing/consumption race | No unauthorized consumed content in supported E1 path |
| G10 | Regrant ABA, expiry, changed agent registry, changed purpose | New generation required |
| G11 | Correction/supersession invalidates prior grant dependencies | Old content no longer usable |
| G12 | User forget propagates across eligible derived/index/cache/summary inventory | Safe no-reuse and honest pending purge |
| G13 | Hard-disabled episodes cannot be exposed/exported | Denied even if fixture row exists |
| G14 | Export is explicit, bounded, classification-safe; import cannot bring rights | No live knowledge import/auto-share |
| G15 | Stale backup and restoration of old grants/forget | Fail closed pending surviving authority |
| G16 | Crash/lost ACK/duplicate worker/uncertain send | Reconciliation without false success |
| G17 | Quota exhaustion preserves deletion/grant revocation safety capacity | Bounded safe status |
| G18 | Page/lookup/index/workflow amplification | Finite maximum and resource accounting |
| G19 | Physical erasure receipt names every participating store/topology | Unsupported replica/backup remains BLOCKED |
| G20 | No model-output/prompt injection/manifest may mint grants | Trusted policy unchanged |
| G21 | 36+ additive cases, complete attempted grid, stable source hashes | No dropped failure denominator |
| G22 | Two fresh-process replays, drift/tamper detection | Exact deterministic match |
| G23 | Canary and rollback cause no effective writes | Explicit unchanged-state proof |
| G24 | Exact controlled test outcomes; inherited failures retained | No fabricated acceptance |
| G25 | Independent actor/native physical grant/erase/restore proof | **BLOCKED** until real tier evidence |
| G26 | Independently measured real multi-agent task value and native operating cost | **BLOCKED** until real tier evidence |
| G27 | Phase 36, PI and HXE-5 release prerequisites, explicit owner approval | **BLOCKED / NO_GO** unless independently closed |

**Hard vetoes for any effective sharing or release:** cross-owner/recipient disclosure; stale/revoked/forgotten memory selected/packed/sent; a model or import creating authority; grant replay widening scope; a cold restore resurrecting erased data; deletions falsely labeled physical; missing budget/cost cap; missing independent review; unsupported issuer/identity and send-fence claims. An unsupported positive path is a **blocker**, not a failing score silently discarded or a reason to loosen the security goal.

## 6. Evidence tiers and release ladder

| Tier | Allowed evidence/operation | Not established |
| --- | --- | --- |
| **E0** | Static contract, threat model, schema and policy inspection; no runtime effects | Behavior, persistence or authorization in a host |
| **E1** | Hermetic two-agent synthetic issuer, fixed grants, fault simulation, unit/integration/replay, dry-run plan | Real agent identity, physical sends, native durability or private-data processing |
| **E2** | Explicitly approved disposable native Postgres/pgvector/Dynamo component tests with actual crashes/concurrent processes | Cloud IAM, backups beyond test topology, live human/agent source rights |
| **E3** | Explicitly approved real registered actor/source/recipient and physical-send permit, with no-charge/cost proof and verified current rights | Distributed failover, deletion/restore under deployment, broad utility |
| **E4** | Approved cloud/deployed grants, workloads, replicas, backup restoration/erasure, identity and billing drills | Independent longitudinal product benefit unless measured |
| **E5** | Independent matched multi-agent/project longitudinal tasks, actual downstream success and native operation economics across time | Anything not covered by exact subjects/topology |

Acceptance is **profile-specific**. E1-only may be marked `IMPLEMENTED_E1_GOVERNANCE / PHASE_EXIT_BLOCKED`; a native subset may be marked `E2_COMPONENT_OBSERVED`, never `E4_PRODUCTION_READY`. Each external step needs its own separately approved source and credentials. The old Phase 36 memory/identity/cloud and newer PI-5 source/send, PI-7 restore/original-key, MEM-2/3/4/5/6 and HXE-5 gates remain separately owned and tracked.

## 7. Verification strategy and commands

Suggested stable implementation names (to verify against naming policy): `memory/governance/`, `test_memory_governance*.py`, `memory-governance-check`, `memory-governance-eval`, `docs/memory/<date>-governance-*.md`. Do not use `mem7` in active runtime symbols, test names, public commands or current module README headings.

Use repository Makefile targets where they exist; otherwise run focused `pytest` with documented dependency setup. Candidate checks:

```bash
git rev-parse HEAD
git status --short
make memory-research-check memory-research-eval
make memory-navigation-check memory-navigation-eval
make memory-consolidation-check memory-consolidation-eval
make memory-task-eval memory-knowledge-eval memory-control-eval
make backend-lint naming-policy-check
make planning-eval
make backend-test-offline
```

Do **not** assume every target exists at the future HEAD. Add a target only when it is stable, needed and consistent with Makefile policy. Test exact authorization negative cases, freeze/default flags, source/consumer lifetime and `no content on unavailable`. If native DSN is already operator-approved, run only scoped disposable tests and record physical topology and cleanup. Never make implicit cloud/paid/provider calls. Keep command exit status, test counts, env/dependency versions, source digest, changed files and reasons for skipped/blocked tests. Distinguish author claims from independently reproduced results.

### 7.1 Resource measurements

Report per tested envelope: memory count, grant count, receipt/tombstone/fence bytes, lookup reads, p50/p95 latency (only if measured), retry amplification, index growth, erase backlog, maintenance work, disk size and cost provenance. Explicitly report `unknown` for real DB storage/cost, total cloud egress, model tokens, native idle burn and deployed concurrency until observed. Compare grant-enabled vs disabled on the *same* synthetic case, rights and budgets; do not claim the grant path increases task quality without a separate real-task comparison.

## 8. Operational and rollout runbook requirements

The non-effectful runbook must contain:

1. **Inventory/preflight:** exact feature profile, approved owners/recipients, source policies, live project mappings, storage and backup topology, budgets and no-go conditions.
2. **Migrations/rollback:** additive schema compatibility, older reader denial of unknown grant types, safe migration backout, original-key continuity, and no data-loss rollback.
3. **Canary:** begin with synthetic and a dedicated opt-in owner/project/agent pair; bounded stages, observation windows, abort thresholds, evidence attribution and independent review. No switch executes until separately authorized.
4. **Revocation drill:** revoke active grant during retrieve/pack/send; change source owner/project rights, update knowledge and regrant with new epoch. Verify *actual* physical send fencing before live support.
5. **Erase/restore drill:** old snapshot/replay after forget; mixed-age Postgres/Dynamo, replica and backup tests; verify externally surviving epoch, tombstone/capacity and physical purge status.
6. **Resource soak:** defined concurrency, bounded grant/receipt/tombstone volume, tenant isolation, idle cost, recovery time, p95 tail latency, background backlog, quota exhaustion and resource cleanup. Do not invent target SLOs; register measurable envelopes before runs.
7. **Rollback:** disable effective sharing path/selection, stop new sends, revoke outstanding leases and preserve safety receipts; reconcile effects, leave existing canonical owner data protected, publish blocker and reviewer sign-off.

## 9. Deliverables and milestone sequencing

| Milestone | Deliverable | Gate |
| --- | --- | --- |
| M0 | Entry inventory, narrowed readiness ADR, hardened design | Explicit E0/E1 authorization; no silent freeze bypass |
| M1 | Strict grant/rights and trusted-context contracts | Identity/scope, negative and schema tests |
| M2 | Synthetic grant lifecycle, revoke/consume/replay integration | Cross-agent/project, CAS, ABA and epoch tests |
| M3 | Safe owner preview and portability/inert import boundary | No unintended knowledge export/import |
| M4 | Dependency-aware erasure/restore model and quotas | Safety reserve, stale restore and crash tests |
| M5 | Fixed 36+ case study, cost envelope, non-effectful canary | Complete grid, replays, tamper, no mutation |
| M6 | Dated docs, status matrix, test report, reviewer handoff | E1 candidate ready for independent review |
| Later | True native/cloud/live issuer, restore, multi-agent utility and canary | Independent exact-topology acceptance + owner release decision |

Expected dated handoff files inside the repository (choose date based on implementation run):

- `docs/memory/<date>-governance-readiness.md`
- `docs/memory/<date>-governance-implementation.md`
- `docs/memory/<date>-governance-verification.json`
- `docs/memory/<date>-governance-blockers.json`
- `docs/memory/<date>-governance-operator-drills.md`

Implementer produces exact changed-contract inventory, test transcripts/receipts, dry-run canary, rollback, default-off matrix and independent review handoff. Do not overwrite historical evidence or merge accepted and proposed status. The separate Sol High reviewer will challenge the architecture, not just compliance with this document; Luna High/XHigh can remediate without another open-ended design session.

## 10. Open decisions and honest deferrals

| Decision / dependency | Default recommendation | What closes it |
| --- | --- | --- |
| Share record identity vs copy | Capability overlay referencing immutable canonical source; no copied knowledge | Trusted target/project resolver and epoch-validated reader |
| Agent authentication/delegation | Exact host-registered principal, no user-supplied agent label | E3 physical actor and issuer proof |
| Physical-send fence | No external sharing until current source+grant permit is atomic with send or robustly reconciled | Tested deployment protocol with revocation race |
| Durable grant table/migration | Implement only within existing owner-fenced Postgres lifecycle when safe; otherwise protocol/E1 first | Native E2 tests and independently reviewed restore semantics |
| Export/import | HXE-4 profile-only remains; memory grant/export preview inert | Separate source/legal/retention consent and full erasure path |
| Backup and replicas | `pending/unknown`, fail closed on stale restore | E4 independent cold restore plus physical erase receipts |
| Grantee copies | Explicit warning; future managed reads blocked, external copies irretractable | User controls plus documented boundary |
| Quota compaction | No eviction of safety-critical fences/receipts | Verified native growth/compaction and recovery invariants |
| Cost targets | Pre-register after native baseline; free-first | Actual measured storage/DB/egress/maintenance cost and SLO |
| MEM-6 positive utility | **Not established** after corrected 0 pp comparison | New independent real-model/task evidence at matched budgets |
| Production/profile release | Remains `NO_GO` | Independently accepted Phase 36, PI, MEM and HXE-5 applicable gates |

## 11. Independent review contract

Review `b694c5f` **as planning input**, but pin the actual implementation commit. Require the reviewer to check live code and tests, not trust the implementation report; independently reproduce deterministic tests; attempt scope- and time-based exploit paths; inspect SQL and reader/packer/effect boundaries; challenge whether grant overlays are justified or subtly duplicate owner consent; independently assess erasure and original-key semantics; and verify no authority is derived from research/JSON or a copied memory. A claimed phase exit with only E1, no separately registered issuer/recipient or no physical erase must be rejected even if all unit tests pass.

The reviewer produces one self-contained Luna remediation Markdown with ranked, reproducible findings; exact file/line references, impact and minimal fix; negative regression tests; required verification; and a separately labeled list of **genuinely external dependencies** that cannot be closed in a local session. Keep existing default-off/`NO_GO` intact after remediation absent independent release approval.

## 12. Source references

Authoritative repository snapshot:

- [`AGENTS.md`](https://github.com/jasonkli21/personal-ai-system/blob/b694c5f26e0c5fc21880bac06f1fdf2eac5ca650/AGENTS.md)
- [`docs/current-state.md`](https://github.com/jasonkli21/personal-ai-system/blob/b694c5f26e0c5fc21880bac06f1fdf2eac5ca650/docs/current-state.md)
- [`memory/README.md`](https://github.com/jasonkli21/personal-ai-system/blob/b694c5f26e0c5fc21880bac06f1fdf2eac5ca650/backend/src/personal_ai/memory/README.md)
- [`memory/control_service.py`](https://github.com/jasonkli21/personal-ai-system/blob/b694c5f26e0c5fc21880bac06f1fdf2eac5ca650/backend/src/personal_ai/memory/control_service.py)
- [`context/profile_consent.py`](https://github.com/jasonkli21/personal-ai-system/blob/b694c5f26e0c5fc21880bac06f1fdf2eac5ca650/backend/src/personal_ai/context/profile_consent.py)
- [`docs/memory/owner-portability.md`](https://github.com/jasonkli21/personal-ai-system/blob/b694c5f26e0c5fc21880bac06f1fdf2eac5ca650/docs/memory/owner-portability.md)
- [`docs/memory/2026-11-04-longitudinal-review-remediation.md`](https://github.com/jasonkli21/personal-ai-system/blob/b694c5f26e0c5fc21880bac06f1fdf2eac5ca650/docs/memory/2026-11-04-longitudinal-review-remediation.md)
- [`docs/memory/2026-11-04-longitudinal-blockers.json`](https://github.com/jasonkli21/personal-ai-system/blob/b694c5f26e0c5fc21880bac06f1fdf2eac5ca650/docs/memory/2026-11-04-longitudinal-blockers.json)
- [`docs/decisions/0026-offline-memory-research-custody.md`](https://github.com/jasonkli21/personal-ai-system/blob/b694c5f26e0c5fc21880bac06f1fdf2eac5ca650/docs/decisions/0026-offline-memory-research-custody.md)
- [`docs/harness-excellence/2026-11-03-release-verification.md`](https://github.com/jasonkli21/personal-ai-system/blob/b694c5f26e0c5fc21880bac06f1fdf2eac5ca650/docs/harness-excellence/2026-11-03-release-verification.md)

Saved project references: *personal-ai-system-integrated-roadmap-11-03.md* v3.1 and *memory-architecture-and-research-roadmap.md*. Their strategic intent is subordinate to newer executable code and dated acceptance evidence.

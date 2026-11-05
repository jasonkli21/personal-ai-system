# Personal AI System — MEM-4 Detailed Implementation Plan

**Phase:** MEM-4 — Bounded Offline Consolidation  
**Planning baseline:** `jasonkli21/personal-ai-system` `main` at `e906bfc1007d27bc75e97b4ad852bac901da931c` (2026-11-04 UTC)  
**Program baseline:** Integrated Harness Excellence Roadmap v3.1 (2026-11-03), MEM-0–7 sequence  
**Status:** implementation plan, not authorization to enable live capture, dreaming, disclosure, or release.

## 1. Executive decision

Build the smallest independently evaluable **offline, checkpointed memory-consolidation proposal pipeline**, with deterministic extraction and conflict detection first, an optional model-assisted proposal adapter later, and **no automatic promotion**. It must reuse existing canonical memory records, selected-episode evidence interfaces, source/authorization fences, and lifecycle machinery. A proposal is not trusted memory. No new path may read from MEM-3's disabled episode projection, disclose it to a model, or circumvent its blocked source-epoch and lifecycle gates.

The roadmap defines MEM-4 as incremental per-actor/session checkpointed extraction of typed procedure/lesson/conflict proposals, exact source verification, idempotent compare-and-swap (CAS), and task-evaluation evidence. The local `e906bfc` remediation explicitly keeps MEM-3 capture and selection **hard disabled**, with migration `035_memory_episodes.sql` only an experimental read-disabled projection. Thus separate two targets:

1. **Authorized development target (E0/E1):** deterministic, synthetic-only per-scope offline proposal extraction from a purpose-built, immutable, verified test-source adapter; checkpoints, dedupe, conflict detection, evaluation and governed review flow. No live episode read.
2. **Blocked integrated target (E2–E5):** production episode ingestion, scheduled dreaming, model calls, automatic user-memory writes, cross-app learning, or release promotion. These require source issuer epochs, canonical lifecycle/erasure integration, durable original-submission receipts, physical-send authority, and independent native evidence.

Do not treat permission to implement this phase as permission to unfreeze MEM-3, ingest private histories, or turn on background processing. Where an inherited gate cannot close within scope, build a smaller honest component and document `BLOCKED/PARTIAL`.

## 2. Verified baseline and sources

- GitHub commits: `42f00b0` (HXE release tooling), `09f3ef1` (structural terminal-step validation), `e906bfc` (hard-disable and maintenance remediation). Review exact diffs and current HEAD again at implementation start.
- `docs/current-state.md`: MEM-3 experimental projection is read-disabled; exact-namespace forget/purge works locally; no issuer epoch, producer, context, export or send integration.
- `docs/memory/2026-11-03-luna-remediation.md`: 93 focused tests; 38/38 structural cases; frozen source lock mismatch remains; native Postgres and provider-isolation validation not established; independent acceptance pending.
- `docs/memory/episode-development-blockers.json`: canonical blocker ledger. Never silently mark blockers closed.
- `backend/src/personal_ai/memory/{episodes.py,episode_service.py,episode_repository.py}` and `backend/src/personal_ai/persistence/postgres/episodes.py`: experimental contracts, not authority to read.
- `backend/src/personal_ai/memory/lifecycle/jobs.py` and existing consolidation services: background leases, deterministic consolidation, lifecycle owner; inspect behavior and avoid introducing a second worker/state machine.
- `backend/src/personal_ai/evaluation/episode_candidates.py`: bounded structural validation, not provenance authenticity or task success.
- Existing MEM-0–2 baseline, MEM-1 knowledge schemas/source fences, MEM-2 user proposal/review controls; check actual typed API/migrations and reuse rather than guessing names.
- [Integrated Roadmap v3.1](https://docs.google.com/document/d/15e2mPUC72bfT_6_bg3mYmBCLxpSmw3nS-ilSB4-DRv8/edit), [MEM-3 detailed plan](https://docs.google.com/document/d/1eat60-Jq0hYPEKHRucOGECjEfUdlg27x1dGohlgjDkg/edit), [MEM-3 remediation](https://github.com/jasonkli21/personal-ai-system/blob/e906bfc/docs/memory/2026-11-03-luna-remediation.md).

## 3. Architectural ownership and invariants

| Concern | Canonical owner | MEM-4 responsibility |
| --- | --- | --- |
| Source rights, actor/app/workspace/project, disclosure | Existing trusted authorization/source policy | Require exact current source validation at read, commit, review, retrieval and send; deny unresolved authority |
| Raw sessions/attempts | Existing message/workflow stores | Read only approved bounded immutable source projections; never replicate raw transcripts, hidden reasoning, secrets or tool payloads |
| Durable memory, provenance, tombstones, user corrections | Existing memory storage/lifecycle | Propose typed derived knowledge with evidence edges; no competing active/forgotten state |
| Background lease, retries, jobs | Existing lifecycle coordinator | Extend with opt-in job kind/adapter only after concurrency review; E1 can use synchronous fixture driver |
| Proposal approval/rejection | Existing MEM-2 authenticated user workflow | Reuse review authority; model cannot approve itself or bypass versioned CAS |
| Context packing/retrieval | Existing shared assembler | No new inference path in initial slice; later verified proposals enter existing approved route only |
| Usage/cost/evaluation | Shared HXE evidence and MEM benchmark harness | Record reproducible ablations with evidence-tier labels |

**Hard invariants:** source immutable history is distinct from derived memory; source withdrawal/forget/correction always wins; regrant never resurrects old content; exact tenant/actor/client/purpose isolation; checkpoint may advance only with committed eligible outputs or explicit terminal skip reason; duplicate deliveries do not double-apply; a failed model pass cannot erase verified knowledge; user-confirmed correction outranks inferred proposal; no new physical model call without strict-free admission and source disclosure check; every loop has finite time, tokens, candidates, writes, retries and retained bytes.

## 4. Data contracts (design proposals; reconcile with repository)

Use durable capability-oriented names in source/tests—not `mem4`, `phase_4` or equivalent. Design strict, versioned, bounded structures:

- `ConsolidationSourceRef`: trusted scope including owner, nullable actor, app, workspace, project, client/purpose; immutable session/run/source ID, source generation/epoch, revision and issuer; recorded eligibility, source class, retention deadline; no arbitrary free-form payload.
- `ConsolidationCheckpoint`: exact scope + stream/source adapter version + policy/extractor version; monotonic source cursor, lease/fencing token, last committed batch fingerprint, source watermark and bounded terminal failure metadata. Cursor ordering must be defined by the source—not timestamps alone.
- `DerivedProposal`: stable proposal key, typed kind `procedure | lesson | conflict | project_observation` (only kinds reconciled with MEM-1), normalized bounded proposition, confidence **not** authority, evidence edges, contradictory/equivalent existing memory references, sensitivity, TTL, extractor revision, verification level and review disposition. Separate candidate text from a verified fact.
- `ConsolidationBatch`: immutable input-set digest, policy/extractor/config digest, sorted source refs, proposed changes, rejection reasons, resource metrics and durable outcome.
- `ProposalDisposition`: `pending | rejected | withdrawn | accepted` only via existing authorized review; automatic extraction does not set `accepted`.

Prefer additive tables/indexes only if existing durable lifecycle/proposal schema cannot represent the data. Any new migration must be after the actual latest migration and preserve old schema 1/2/3 readers and source-lock histories. Treat checkpoint, dedupe identities, proposal changes and outbox/audit as one crash-consistent transition, or explicitly split with a transactional outbox and replay-safe reconciliation. State how a crash between checkpoint advancement and proposal commit is prevented. No unbounded uniqueness/tombstone accumulation; define quota-exhaustion deny policy rather than unsafe pruning.

## 5. Processing algorithm

1. **Admission:** operator-controlled, default-off, synthetic/public fixture mode only. Validate owner/actor/app/workspace/project/client/purpose and exact source profile. No open-ended scan, cron, or third-party export.
2. **Claim:** acquire canonical lifecycle lease or a hermetic E1 stand-in with fencing token; read stable checkpoint and bounded source page. No cross-actor batching.
3. **Source snapshot:** current issuer-bound generation, consent and retention must be provable. For E1 use a frozen synthetic issuer with explicit revoke/regrant/epoch fixtures. Production issuer missing = `blocked_source_authority`, no record read.
4. **Extract:** pure deterministic rule(s) over an allowlisted typed evidence envelope. E1 rules can produce a modest procedure, lesson or conflicting observation only when independently evidenced. Avoid generic chat summarization. Unknown or ambiguous input yields no proposal with reason.
5. **Verify and compare:** source record presence and integrity, exact revision, scope, trust level and evidence entailment; detect duplicate, supersession, contradiction and user-correction conflict. Do not auto-resolve conflicting user facts. No assertion that task succeeded merely because a workflow completed.
6. **Commit:** transactional CAS over checkpoint generation and proposal identity under a current source fence; immutable provenance edges and replay marker committed atomically. Changed input under same idempotency key is a conflict. On ambiguous ACK reconcile by original key, never issue a fresh key.
7. **Review:** expose only through established authenticated MEM-2 pending proposal controls if integration is safely established; otherwise retain test-only pending proposals. User correction/rejection and forget take precedence and invalidate derived dependents.
8. **Advance:** move cursor only past fully decided input set; malformed items receive a bounded durable terminal skip reason without losing later eligibility; transient failures retry same page within finite budgets.
9. **Lifecycle:** expiry/revoke/source correction/owner deletion suppresses pending and accepted dependents; physically purge owned proposal payload where supported, maintain anti-replay fences; cannot claim cloud backup deletion without native proof.
10. **Observability:** structured content-free counters and hashed identities, no source or proposal text in logs, metrics or exception surfaces.

## 6. Staged implementation packages

### WP0 — Reconcile gates and freeze a phase-specific ADR

Pin HEAD, enumerate active memory code/migrations/config, source and job contracts, release source locks, review findings. Produce `docs/memory/...` ADR for exact source selection, trust lattice, checkpoint semantics, schema choice, credential-free setup, privacy classification, rollback and E1 vs E2+ gates. Resolve whether any MEM-3 source can be legitimately consumed (current answer: no). Establish explicit implementation-unfreeze versus enablement distinction.

**Exit:** reviewed-in-session decisions, concrete code seam, no premature runtime registration.

### WP1 — Deterministic fixture pipeline

Implement source adapter protocol plus a frozen public/synthetic evidence corpus; small pure extractor and typed verifier; unknown/untrusted evidence always declines. Version policy and extractor; ensure bounded per-source output and deterministic ordering. Include non-success observed attempts, absent verification, forged receipts and contradictory user corrections.

**Exit:** deterministic outputs, strict validation, no private source readers.

### WP2 — Checkpoint, CAS and recovery

Add a scoped store or reuse existing lifecycle store. Implement atomic checkpoint/proposal/outbox batch, fencing and replay; test two workers, crash before/after transaction, lost ACK, mid-page error, cursor gaps, stale worker, changed policy and migration. Re-extraction on policy revision must be an explicit backfill job with its own stable generation and review—not silently rewrite accepted memory.

**Exit:** no skip/double-apply under deterministic fault injection and appropriate native DB E2 tests when environment available.

### WP3 — Proposal governance and conflict path

Integrate with existing authenticated review proposal type only if the canonical authority and CAS APIs support it; otherwise implement a sealed offline adapter with `integration_blocked` evidence. Never let models or background jobs accept proposals. Ensure user corrections and withdrawn source edges suppress pending candidates immediately; no leaked cross-scope topic listing.

**Exit:** no unauthorized writes or resurrection, including revoke/regrant and stale restore simulations.

### WP4 — Optional model-assisted research adapter (non-blocking)

Specify, but do not enable by default, a provider-neutral extractor behind existing admission and physical-send accounting. Permit only separately authorized, synthetic/public content. Typed closed output validated as an untrusted suggestion; source/verifier and user review still mandatory. Hard cap provider calls, total tokens, retries, latency and cost; strict-free means deny unknown counters/cost/provider privacy and no paid fallback. If no safe environment, document contract and tests with fake provider only.

**Exit:** deterministic fallback remains usable; model cannot affect promotion authority.

### WP5 — Research benchmark and report

Create frozen fixtures and held-out tasks, preregister comparator identity and metrics before scoring. Arms: no new consolidation, current fixed memory, deterministic proposals, optional model-assisted proposals (only if safely available), and eligible full-source upper bound. Compare source precision, evidence entailment, conflict resolution, stale/revoked leakage, checkpoint completeness, task success, token/cost/latency. E1 scripted replay must not masquerade as real agent utility; E5 requires separately observed longitudinal tasks. Preserve historical MEM-0/1/2/3 corpora and score locks byte-for-byte.

**Exit:** honest report of supported gains and regressions; insufficient evidence leads to no promotion.

### WP6 — Documentation and handoff

Update `docs/current-state.md`, memory README, blocker ledger and a dated implementation receipt. Include exact commands, commit SHA, failed/skipped suites, environment, migrations and rollback. No release promotion or default flag changes.

## 7. Required adversarial/test matrix

| Family | Must prove |
| --- | --- |
| Isolation | actor-null vs actor-bound, cross-owner/app/workspace/project/client/purpose forbidden; hostile IDs and untrusted claims never widen scope |
| Source validity | revoke/regrant epoch, changed grant, expiry, branch correction, missing issuer, stale backup and concurrent source withdrawal block recall |
| Replay | duplicate batch, changed payload same key, lost ACK, crash before/after commit, stale lease, dual workers, out-of-order events and cursor gaps |
| Trust | forged or structurally consistent but unauthenticated receipts, model self-certification, observed vs verified success, contradictory evidence, user correction |
| Privacy | secret/prompt/hidden-reasoning injection, control characters, long text, unknown JSON keys, diagnostics/log exfiltration, poisoned evidence |
| Lifecycle | forget, project deletion, owner deletion, expired proposals, tombstone exhaustion, restore, cache/in-flight lookup, external-disclosure denial |
| Resource | source-page/candidate/bytes/fan-out/time/token limits; repeated malicious input and per-actor fairness |
| Compatibility | memory schema 1/2/3, MEM-2 review, existing retrieval, background jobs, workflow, HXE release identity and frozen evals |

Run the smallest relevant current commands first (`make memory-episode-check`, `make memory-episode-candidate-eval`, `make memory-knowledge-eval`, `make memory-knowledge-causal-eval`, `make memory-control-eval`, `make memory-eval`, `make workflow-check`, `make backend-lint`, `make naming-policy-check`); discover any newly introduced targeted target. Run broader offline and native PostgreSQL suites where permitted, preserve precise BLOCKED reasons. Do not modify a frozen digest or its expected assertion just to turn a red gate green; introduce a reviewed additive source-generation identity if appropriate.

## 8. Acceptance and promotion gates

**Development candidate E0/E1:** typed bounded fixture-only extraction, provable source eligibility, transactional/replay-safe checkpoint and proposal operations or explicit sealed pure-only fallback, deterministic tests and security negatives, no auto-acceptance, old tests unchanged, transparent report. If transaction semantics are untested, label checkpoint integration partial.

**Integrated E2:** separate native PostgreSQL test of CAS, leases, transactional recovery, delete and invalidation, with issuer-backed monotonic epoch and canonical lifecycle. MEM-3 blocked source adapter must first be independently accepted; existing experimental tables cannot be deemed safe by enabling a flag.

**E3/E4:** live provider/source identity, physical-send disclosure, operator approval, restoration and physical deletion/backup propagation, storage/cost budgets, release profile evidence and independent review.

**E5:** genuinely held-out longitudinal multi-session task improvement under matched budgets, with no privacy, stale-memory or user-correction regressions. Only E5 can justify a claim that dreaming improves actual agent work.

Full MEM-4 phase exit requires no skip/double-apply under retry, trustworthy attribution, and measured task improvement without stale/privacy regression. A local synthetic implementation is **not full exit**. Explicit owner enablement and a separate review remain mandatory.

## 9. Non-goals and rollback

No production history sweep, hidden chain-of-thought capture, raw tool-result retention, autonomous promotion, self-certifying verifier, custom new worker queue, external app integration, unreviewed scope sharing, dedicated vector index (MEM-5), autonomous strategy learning (RE), or new release profile (HXE-5). Do not implement a competing coding harness.

Rollback: disable the experimental adapter/driver; stop jobs, invalidate in-flight leases, quarantine pending proposals, retain content-free original-key and source-tombstone fences, and leave existing verified memory untouched. Apply only migration-forward repair; never down-migrate or reanimate deleted records. If a source epoch/lifecycle bug is found, hard-disable reads and capture first and document erasure limitations.

## 10. Delivery checklist

- [ ] Exact baseline SHA and changed-file inventory
- [ ] In-session plan-hardening ADR and rejected alternatives
- [ ] Minimal bounded typed contract and fixture-source boundary
- [ ] Stable idempotency, CAS/checkpoint semantics or clearly isolated fallback
- [ ] Source-evidence edges, conflict/review authority and lifecycle invalidation
- [ ] Security/concurrency/property/fault tests, frozen corpus and comparator
- [ ] Honest E0–E5 evidence ledger with all inherited blockers
- [ ] Dated implementation receipt, rollback and independent review handoff
- [ ] No model/provider calls, no external disclosure and no default-on behavior without separate approval


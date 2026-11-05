# HXE-4 — Detailed Implementation Plan

Personal AI System \| 4 November 2026 \| Planning baseline: 51cfda1c9ad7c610364454e405cbfe5769a8e11e \| Implementer: Sol Medium \| Independent reviewer: Sol High \| Final remediator/verifier: Luna High/XHigh

# 1\. Executive decision

Deliver a narrowly scoped, default-off memory-management and portability product built on the existing canonical memory, verified source, profile-consent and user-control services. The first valuable slice is owner inspection, explicit source-aware correction where authorized, forget, export, bounded dry-run import, and a consented cross-application demonstration. Do not create a second memory store, authorize new memory from an imported file, or silently lift the MEM-3+ freeze.

Speed-first principle: complete safe offline/E1 features now; retain capability-specific NO\_GO outcomes for missing issuers, distributed revocation, deployed identity, source fences, native recovery and physical erasure. Make truthful partial capability status a product requirement, not a reason to fake a green gate.

# 2\. Authority, planning sources and baseline

Repository: https\://github.com/jasonkli21/personal-ai-system. Read AGENTS.md, docs/README.md, docs/current-state.md, backend/src/personal\_ai/memory/README.md, docs/memory/mem-2-control-adr.md, docs/memory/mem-2-blockers.json, docs/platform-independence/profile-sharing-v1.md, docs/decisions/0023-external-consumer-and-execution-authority.md, and docs/platform-independence/pi-cross-phase-gate-registry.md. Read only relevant code and adjacent tests via the documentation router.

Roadmap: Personal AI System — Integrated Harness Excellence Roadmap v3.1, /Users/jasonkli/projects/personal-ai-system/docs/personal-ai-system-integrated-roadmap-11-03.md. It assigns HXE-4 the memory product, consented sharing and portable representation; authoritative storage, verification, corrections, deletion and promotion remain MEM-owned.

Planning commit 51cfda1 includes HXE-3 remediation of dispatched-attempt evidence. At this baseline, HXE-0 has a provisional external consumer v1.2.0/Python SDK; HXE-1 has a default-off read-only MCP pilot; HXE-2 has local inference and synthetic evaluation, but real E2/E3 evidence remains blocked; HXE-3 has a default-off local read-only workflow with focused checks and a still-blocked disposable PostgreSQL lifecycle suite. None implies production acceptance.

Existing memory-control route backend/src/personal\_ai/api/memory\_control.py offers bounded GET knowledge/topics/individual records/proposals; POST proposal review/reject and knowledge forget; POST revise exists but returns unsupported\_evidence\_source without a trusted revision issuer. The service binds current verified actor, owner, project resolver/lease, expected version and durable operation key. The Next.js memory panel already has inspect and exact-key uncertain-operation recovery. Do not recreate it.

PI-4 sharing is currently limited to four explicit user-set profile fields (preferred\_units, locale, response\_style, answer\_length), exact destination/purpose/expiry/value/revision grants, and current-rights rechecks. It explicitly does not share arbitrary memory or inferred/sensitive/derived knowledge. Existing external SDK has no privileged memory-admin API. MEM-0–2 are scoped implementation candidates; MEM-3–7 remain frozen and default-off.

Code/contracts/migrations/tests outrank dated receipts, which outrank planning language. At session start re-pin actual HEAD, inspect git status, and reconcile any post-baseline changes without overwriting user work.

# 3\. Desired product and non-goals

* An authenticated owner can inspect eligible knowledge and pending suggestions, see provenance, scope, verification, currentness, expiration and limits, and explicitly forget a record with safe same-intent recovery.  
* An owner can correct an explicitly user-authored profile preference through its existing authoritative profile writer. A verified schema-3 knowledge correction is offered only if a real issuer-bound, atomic replacement path has been established; otherwise it remains visibly unavailable and its exit criterion stays blocked.  
* An owner can produce a versioned, bounded, source-attributable export of eligible records and assess a candidate import via deterministic dry-run with conflict/duplicate/scope/issuer reasons. Applied import is restricted to records with independently reestablished source authority; unknown-origin or foreign-scope content stays quarantined.  
* An independent application can receive only a current, explicitly granted projection through the existing PI-4 boundary; a simple two-consumer demonstration proves non-disclosure on absent/revoked/expired grants and source changes.  
* A CLI/browser path explains unavailable capabilities, stale rights, partial results, retention and the fact that previously disclosed provider/external copies cannot be recalled.  
* Out of scope: MEM-3+ consolidation, novel learning or semantic promotion, unapproved derived-memory sharing, full memory sync, cross-device CRDT, auto-import into active context, agent-authorized grants, background scraping, arbitrary remote destinations, autonomous data writes, live production/private-data enablement, a new policy/permission engine or a PAS-controlled OpenCode execution lifecycle.

# 4\. Architectural invariants

* MEM owns canonical knowledge records, lifecycle state, verification, revisions and forget. HXE-4 is an API/SDK/UX/export adapter and may add only narrowly necessary MEM-2-owned primitives after documenting source authority. It must not become another source of truth.  
* Identity is always server-resolved: verified owner, exact actor issuer/subject, client authorized party, application, workspace, project and requested purpose. A filename, manifest, portable archive, same owner claim, user-supplied JWT body or model text confers no authorization.  
* An export is a disclosure. Revalidate current record scope, evidence, grant, source revision, owner deletion fence and provenance at preparation AND release; if a reliable issuer-bound send fence is unavailable, keep sensitive/external paths unavailable. No broad account export just because the caller can inspect one record.  
* A portable source reference is evidence metadata, not an entitlement. Record-level rights must be re-proven by the current origin/source issuer at destination, or the imported object remains inert. Never silently upgrade unverified to verified or remap workspace/application scope.  
* Correction must be immutable/lineage-preserving and CAS-protected. No in-place mutation of historical verified claims, no 'reviewed' proposal promoted to verified memory, no claim that free-form owner text is evidence of a past external event.  
* Forget/revoke invalidates future managed use, exports, cached contexts, summaries and replay under existing dependency checks; it does not erase already-delivered downstream bytes. Preserve non-rollbackable original intent, tombstone, validity epoch and revocation evidence; a backup restore cannot reactivate stale grants.  
* Client-visible error/status codes are bounded and content-free for forbidden records; no enumeration, private source IDs or sensitive values in traces. Operations have explicit size, count, timeout, concurrency and byte limits. Strict-free inference remains unaffected; portability itself must trigger zero model calls.  
* No phase IDs in new/modified active production filenames, module/class/function names, tests, fixtures, commands, CLI flags, endpoint routes, comments, current user docs or UI strings. Historical plans/review receipts may refer to HXE-4. Preserve immutable compatibility IDs unless a provenance-preserving migration is necessary.

# 5\. Work packages

## WP0 — In-session architecture and plan hardening

Map the actual memory-control read/mutation transactions, PostgreSQL/fake repositories, source lease/revalidator, owner export, profile-share CAS, browser proxy, SDK credentials, MEM-1 lifecycle and the latest HXE-3 run/attempt evidence. List reuse points and real blockers. Write a compact dated design decision with API audience separation, export/import trust model, correction-issuer decision, data schema, quotas, replay/rollback boundaries and evidence tiers. Rank assumptions NOW, BEFORE\_ENABLEMENT or DEFER. Keep this review and hardening in the same Sol Medium session without subagents; then implement.

## WP1 — Owner inspection and management UX/API

Extend the existing gated MemoryPanel and owner-only /v1/memory/control seam, not a second dashboard. Present explicit kind, source authority, source/revision/verification, scope (application/workspace/project), observed/expiry times, state version/validity epoch, partial/truncated status, and actionable reasons without leaking denied records. Preserve the existing 32-candidate/8-return bounds or improve query performance under a separately justified limit; do not claim complete account inventory from a bounded search.

Expose safe, typed owner-management operations behind independently checked recent authentication, anti-CSRF/browser proxy protection, capability negotiation, and stable error semantics. External application SDK credentials are not owner-management credentials; if an SDK helper is added, give it an explicit privileged owner-audience/client type and refuse external app tokens. An existing owner API may suffice; avoid expanding the provisional public consumer contract unnecessarily.

Keep review/reject as disposition of untrusted proposals, not knowledge admission. Keep explicit confirmation, expected version, original operation UUID and identical-body retry for forget. A client disconnect/timeout stays UNKNOWN until reconciliation. Do not store private payloads or bearer tokens in browser persistence.

## WP2 — Truthful correction path

Implement usable editing of four explicit owner-set profile fields through existing profile revision/CAS/writer and current consent invalidation; show how a new value requires fresh grants. This is profile correction, NOT schema-3 memory revision.

For verified schema-3 correction, first inspect whether a trusted completed-turn/project/source issuer with lease and atomic replacement lineage actually exists at current HEAD. If yes, add a narrow issuer-bound MEM-2 correction operation with expected version, source evidence, transactional supersession, retained original intent/receipt, source/grant rechecks and adversarial tests. If not, retain unsupported\_evidence\_source and make the UX/SDK state unmistakable; do not synthesize an issuer, backfill verification from owner text or relax the freeze. Flag verified-memory correction as unmet in exit report.

## WP3 — Versioned portable export

Design an explicit immutable manifest version (for example personal-ai-memory-export/v1) with format/schema version, created/observed time, origin system, original owner/application/workspace/project identities or safe opaque mappings, memory kind, source references and revision/verification metadata, permission dependencies and restrictions, expiry/retention/deletion lineage, embedding model/space compatibility or absence, content digest, optional signature metadata, and complete/incomplete indication. Keep manifest data vs export rights separate.

Begin with a small enumerated subset of eligible schema-3 procedure/decision records and/or explicit profile fields, under explicit owner request. Use canonical deterministic JSON, stable ordering, bounded count/bytes, no secrets, no provider calls, and no raw hidden prompts/history or credentials. Persist an export intent/receipt only if supported by current owner lifecycle without inventing a parallel ledger. If limited by current 32-row read bound, label snapshot partial and require an explicit continuation mechanism before claiming complete export.

Recheck source rights at serialized release, and test revocation during enumeration, serialization, stream/response release, and retained export replay. Never export another app's records based only on shared owner. Downloads leave system control: show a clear irreversible-copy warning.

## WP4 — Import validation, conflicts and constrained commit

A dry-run accepts only bounded, well-formed input bytes, closed schema/version, digest-valid records and known memory kinds; reject zip/path traversal, recursive structures, huge strings, malicious Unicode, forged issuer/signatures, duplicate IDs, mismatched project/app/workspace, stale revisions, revoked grant references, incompatible embeddings and impossible deletion/retention dependencies. Return deterministic per-item nonsecret accept/reject/quarantine/conflict reasons and an all-or-nothing preview summary without writing active knowledge.

For actual import, demand a current trusted local issuer or source-origin proof, exact destination scope, explicit recent-auth user confirmation, expected state, stable caller-generated operation UUID and payload digest. Stage/commit atomically through the canonical MEM repository, preserving source/lineage/tombstone semantics; no direct SQL insert into active knowledge. Same-key replay observes the first result, changed body conflicts, uncertain commit uses original key, and rollback never deletes original authority receipts.

If those conditions cannot be met honestly without building MEM-3+ or a new trust system, ship dry-run plus unavailable commit with precise capability status. Track full roundtrip as blocked, not passed. A quarantined file is never context or retrieval input.

## WP5 — Consent and cross-application canary

Reuse PI-4 profile-share issuer, explicit field/value/revision/destination/purpose/expiry grants and current output/replay/source dependency checks; do not introduce general memory grants. Demonstrate one owner and two separately registered unrelated consuming applications or equivalent independently installed synthetic clients, with narrow profile projection to the authorized destination and no access by the other. Revoke, expire, change profile value, remove membership/client rights and retest every disclosure path. Surface explicit destination and irreversible-copy warning in the owner UX if it is safely implementable; otherwise keep management API-first and document UX gap.

Include a small matched-task E1 canary showing whether granted context changed a consumer's output and what provenance was attached, while recording latency, bytes disclosed and denials. Synthetic improvement is not real-world utility. An opt-in OpenClaw/OpenCode read-only adapter is a deferred interoperability experiment, not authority to send private derived memories to external harnesses.

## WP6 — Documentation, conformance, rollback

Update user-facing memory/profile contracts, SDK types if modified, current memory module README, docs/current-state.md, focused gate registry/evidence, naming policy compliance and a dated HXE-4 implementation report. Document supported export versions, portability limits, privacy warnings, denied-state UX, safe upgrade path, and how to disable the adapter without removing revocation/tombstone receipts.

Use existing Makefile commands discovered at HEAD. Run focused backend, native-if-available, frontend, SDK/consumer and relevant offline regression checks. Separate E0 static, E1 hermetic, E2 native local, E3 external identities/providers, E4 deployed restore/erasure and E5 real utility; do not promote any gate based on mock success.

# 6\. Minimum adversarial test matrix

* Rights and scope: wrong owner, verified actor, authorized party, application, workspace, project, recipient, purpose, grant, issuance and expiry; no foreign ID/count/source leakage; missing or faulty resolver denies.  
* Source lifecycle: revoke/forget after inspect, during export, before release, before import commit and before reuse; old summary/cache/export/detail/replay refuses stale dependencies; source mutation changes fingerprint even when value changes back.  
* Corrections: concurrent profile CAS, profile update invalidates old grants; schema-3 revise with no issuer is unsupported and writes nothing; if enabled, two-user/two-process CAS, atomic supersession, verified lineage, lost ACK, same UUID replay and changed-body conflict.  
* Export: deterministic manifest and digest, type/version unknowns, noneligible rows, partial limits, enormous data, malicious sources, no secret/traces, no model calls, revoke during serialization, download warning and no scope widening.  
* Import: malformed and oversized manifests, forged owner/issuer/signature, mismatched embedding, duplicate IDs, stale scope/rights, malicious text/prompt-injection, rollback, partial failure, crash after commit, idempotent replay and quarantined data never selected by context.  
* Cross-app: separate clients with and without consent, change/expire/revoke/membership removal, attempt to use a consent for different purpose or destination, exact external detail/stream/replay semantics, no legacy unmarked data disclosure.  
* Recovery: two concurrent operations, rollback-prone backup restores, tombstone/forget receipts, overflow/quota failure, known stale source fence capacity, feature disable/re-enable never resurrects authority.  
* Client/UI: correct typing, 401/403/404/409/422/503 handling, recent sign-in, accessible confirmation, safe error copy, clipped/truncated search, identity switch, session-storage uncertain operation, offline/no-host fallback, no secret persistence or double submits.  
* Regression and naming: old consumer contract, MEM-0/1/2 frozen evidence, PI-4/5, HXE-0/1/2/3 feature gates; active new paths and identifiers are capability-named. Keep historical benchmark hashes/thresholds and old fixtures immutable, use additive source locks when needed.

# 7\. Exit criteria and evidence disposition

P0 safety: no newly enabled cross-app private memory sharing; no unauthorized active import or schema-3 correction; no source/grant bypass; immutable original intents/forget receipts preserved; zero unapproved model/provider calls. Any violation is a blocker regardless of schedule.

P1 useful local delivery: existing owner UI demonstrably inspects, safely forgets and reviews; owner-set profile fields can be corrected; bounded versioned export and deterministic import preview work on supported fixtures; one consented cross-app demo denies all unauthorized recipients. New typed contracts and unit/integration tests pass at E1 where fixtures are available.

Conditional full exit: verified schema-3 correction and applied import pass ONLY with real issuer authority and atomic lineage; native backup, physical erasure and distributed send fencing are separate enablement gates. If unavailable, record those as BLOCKED/DEFERRED and call the implementation an intentionally narrowed HXE-4 development slice, not full feature acceptance.

Evidence packet: actual base/target SHA, diff and tests run, passed/failed/skipped counts, environment and missing dependencies, contracts/data schema, manual canary transcript with synthetic identities, security negative results, acceptance matrix, before-enablement registry, rollback instructions and future owner. Never claim independent acceptance, native PostgreSQL, E2/E3/E4/E5 or production safety from E1.

# 8\. Suggested execution order and stop rules

1. Read actual HEAD/status/ownership; perform in-session plan critique and hardening, decide scope and issuer truth.  
2. Improve existing owner read/UX and typed management controls; preserve old defaults.  
3. Implement bounded export and dry-run validator with strict source permissions and negative tests.  
4. Add profile correction UX and consented independent-consumer canary; do not widen PI-4 authority.  
5. Implement issuer-bound knowledge revision/import commit only if existing authoritative primitives permit a narrow, testable transaction; otherwise return explicit unsupported statuses.  
6. Run adversarial, focused and relevant broad checks; document evidence, blockers, operational disable/rollback and make a focused commit.

Stop and ask for authorization only if a genuine scope expansion/production activation/unavailable credential is required. Do not block safe offline work on unrelated external validation. Do not amend historical accepted evidence to make a test pass.

# 9\. Delivery workflow

Sol Medium independently critiques and hardens THIS plan before coding, in the same Codex session and with NO subagents. It then implements, self-reviews, tests, documents, commits and reports exact SHA/gates. Sol High conducts ONE independent post-implementation review and creates ONE self-contained Luna High/XHigh remediation handoff. Luna fixes all actionable findings, reruns final security/regression checks, self-verifies and commits. There is NO additional review cycle after Luna; any remaining production gates are honestly recorded, not silently promoted.


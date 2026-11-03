# Personal AI System — Integrated Harness Excellence Roadmap

Version 3.1 \| 3 November 2026 \| OpenCode-informed refinement of the 20-phase execution roadmap; not an implementation authorization or production approval

Repository: [https\://github.com/jasonkli21/personal-ai-system](https://github.com/jasonkli21/personal-ai-system) \| Original planning baseline: b61d69890255ca3de736e7236581cee559358f32 \| HXE-0 implementation candidate: 9c90c1d844e9126cb494f286e5f0f80e4be9a6a0 (review fixes in progress)

Primary source: independently reviewed Post-PI Harness Excellence & Extensibility Roadmap v2 (3 November 2026), existing MEM-0–7 and RE-0–5 plans, and lessons from OpenCode V2's coding-agent harness architecture and extension model. This v3.1 preserves all 20 phase identities, the HXE-0 definition, completed MEM-0–2 definitions, frozen evidence, safety gates and separate promotion authority. Its refinements are limited to future work and program-wide rules.

## Executive decision

Continue the existing platform. Do not rebuild. Treat the four domain applications as optional consumers. Concentrate on a genuinely useful, independently consumable, free-first AI runtime. Deliver thin, end-to-end slices before adding abstractions or long feature checklists. Learn from mature coding harnesses such as OpenCode: prioritize a productive model–context–tool–verification loop, replaceable components and measurable task results. Reuse maintained coding-agent shells, edit/test/Git integrations and IDE/session infrastructure rather than duplicating them in PAS. PAS should own general-purpose governed memory, reasoning policy, evidence, admission and evaluation. Consider a PAS-native coding harness only if a demonstrated, important gap cannot be closed by documented extension seams.

The portfolio comprises exactly 20 named phases: HXE-0–HXE-5 (6), MEM-0–MEM-7 (8), and RE-0–RE-5 (6). The original 14 HXE phases are consolidated into six. MEM and RE definitions are preserved, including their separate review and enablement gates. Existing MEM-0–2 implementation candidates remain default-off/unpromoted; MEM-3+ stays frozen until explicitly authorized.

Rationale for 20 rather than 18 or 19: with 14 MEM/RE phases fixed, fewer than six HXE phases would force unrelated SDK, source/tool, inference/evaluation, execution, memory-UX and operational/release concerns into oversized phases, increasing rework and review scope. This is a ceiling, not a mandate to implement all 20 before delivering value.

## What success looks like

* An unfamiliar developer installs a core without sample apps and integrates an unrelated app through stable, versioned public contracts with no core business-logic edits. In coding use cases, PAS adds measurable cross-session knowledge, evidence or reasoning value without taking over the external agent's editor, tools or lifecycle.  
* An explicitly authorized read-only source or tool can be used with a local or approved hosted model, producing useful, attributed output under finite resources.  
* Provider, account, data-disclosure and strict-free restrictions are enforced before every physical call, including attempts, retries, fallbacks, counting and embeddings.  
* Memories are scoped, correctable, revocable and source-aware; no implicit cross-app private-data sharing or model-authorized grants.  
* A bounded reasoning planner improves real task performance under matched resource budgets; low effort stays fast and max always terminates.  
* A newcomer can reproduce contract tests, diagnose denial and resource usage, measure setup/cold-start/idle cost and understand exactly which deployment profiles are unverified.

## Current baseline, as opposed to aspirational scope

Current repository HEAD at planning time is b61d698 (open-source docs, AI context and maintainability). PI-0–PI-8 implementation candidates and review fixes are represented in Git, but they do not collectively constitute production acceptance. The PI-8 historical audit records 21 PASS and 15 BLOCKED cases; independent PI-8 acceptance remains pending and production is NO\_GO.

The b61d698 cleanup already added Apache License 2.0, project-focused README, CONTRIBUTING, SECURITY, routing documentation and license metadata for distributions. Do not schedule this work again. A bounded packaging/evaluation conflict remains: the new backend/pyproject.toml license metadata changes a frozen PI-6 source identity, yielding one broad offline-suite failure. Resolve this as an additive, provenance-preserving identity transition; do not rewrite historical fixtures, thresholds or attest that the old digest still matches.

PI-1 gives a standalone core/reference package split. PI-2 gives a versioned HTTP contract and an unrelated Reading Logbook consumer. PI-3 gives provider-neutral selection/admission with local fakes but not wide live provider acceptance. PI-4 gives scoped revocable profile sharing, not arbitrary global memory. PI-5 gives local retrieval/citations/read-only tools with source-authority production gaps. PI-6 provides a scripted synthetic evaluation baseline, not verified model utility. PI-7 gives local operation/static deployment preflight; native/cloud recovery remains incomplete. PI-8 gives a documented independent-readiness evidence structure but not a release signoff.

Evidence tiers: E0 static architecture and policy checks; E1 hermetic synthetic tests; E2 separately installed/native local systems and real local model endpoints; E3 live external provider/source/protocol peers with approved accounts; E4 deployed operational/restore/delete/cost verification; E5 longitudinal real-task utility. Do not describe one tier as another.

## Operating rules: speed with hard safety boundaries

* Implementation gate is not enablement gate. Offline drafting, tests, source-only adapters and default-off features may proceed despite unrelated E3/E4 predecessor gaps; live disclosure, writes and release promotion may not.  
* Never infer permission from a capability manifest, model argument, source result, same-owner identity, local fake, gateway price label or client-selected workspace.  
* Keep exactly one canonical PAS source/authorization policy, prepared-context pipeline, provider attempt ledger, memory lifecycle and durable intent/run state machine for work executed under PAS control. Extend them behind explicit interfaces; do not fork them for MCP, RE or HXE. External coding harnesses retain authority for their own sessions, tool loops and filesystem effects; correlate their activity through identifiers and reports instead of introducing a competing PAS controller.  
* New live paths must recheck issuer-bound rights at physical send; ambiguous provider privacy, operation eligibility, token count, quota, price or cost fails closed. No silent paid fallback.  
* Retained output needs source, grant, revision and revocation dependencies. Stale backups cannot recreate lost original-intent, forget or revocation authority. External copies already disclosed are outside managed recall. In particular, returning a memory or source excerpt over MCP is an external disclosure: PAS controls the decision and payload at that boundary, but cannot guarantee a recipient coding harness will enforce PAS privacy, strict-free model routing, retention, deletion or later revocation. Use minimal, expressly authorized, non-sensitive canary data before relying on downstream controls.  
* Constrain calls, tokens, time, concurrency, fan-out, persistence, retries and task duration; observe unknown remote effects rather than rekeying/retrying irreversible calls.  
* Use E1 checks during development; require the relevant E2/E3/E4 independent evidence before release. Preserve exact historical benchmark identities and failures.

## Program ownership and phase-count contract

HXE owns public developer experience, protocol/source adapters, local-provider portability, common diagnostics, general governed execution below RE strategy selection, memory portability UX, operations and independent release evidence. MEM retains memory semantics, capture, consolidation, retrieval research, evaluation promotion and memory governance. RE retains effort policy, dynamic planning, bounded strategy execution, grounded iteration and adaptive strategy promotion. Coding-agent tools, terminal/patch/edit/Git workflows, LSP/IDE integration and the external coding session loop remain owned by specialist coding harnesses unless independent evidence shows a critical, unextendable gap.

New workstreams, examples, optional adapters and follow-up tickets are not counted as new phases. Do not create HXE-6+, MEM-8+ or RE-6+ without an explicit scope and overhead review. Every phase should be completable and reviewable as one coherent vertical slice, and optional P2 features never block the first useful release. Adopt external-harness lessons as portable design constraints, not requirements to build a coding product or vendor-specific OpenCode integration.

# Part I — Six consolidated Harness Excellence phases

## HXE-0 — Foundation, developer contracts and first independent consumer

Priority: P0. Entry: immediately after b61d698; no new external authority. Incorporates old HXE-0, HXE-1 and the minimal publishing/docs obligations of HXE-12. This is the next recommended implementation phase.

Outcome: a traceable capability/ownership inventory, one validated no-example core installation, a small versioned developer API/SDK and a working independent read-only application. This phase is about establishing a trustworthy integration surface, not implementing every possible plugin family.

### Deliverables

* Reconcile docs/current-state.md, PI cross-phase gate registry and this roadmap against a pinned commit. Classify each capability by owner, public contract, enabled/default-off state, evidence tier, threats, test command and remaining gate. Keep the historical PI ledger unchanged.  
* Resolve the one new frozen PI-6 package/source-identity mismatch caused by the b61d698 license metadata, using an explicit additive source-generation or compatible evaluation identity. Preserve v26/v27 fixtures and original digests; don't modify an assertion to conceal history.  
* Document exactly one RequestContext identity model, source/provenance envelope, error taxonomy, capability manifest, provider operation contract and run/intent/attempt semantics. Write ownership ADRs for RE-2/HXE-3 execution, monotonic permission authority, event ordering and SDK schema authority before creating new persistence.  
* Freeze a modest initial OpenAPI public contract, typed errors, version/capability negotiation, idempotency/retry and cancellation semantics. Implement one maintained Python OR TypeScript SDK first; the second language is optional until demand or the first release profile requires it.  
* Build clean-room canaries in separate package/process boundaries: a new unrelated app, a second provider adapter (initially synthetic), a read-only source/tool and a memory consumer. Require no private imports or core business-logic edits for supported extension points.  
* Provide a credential-free quickstart, minimal provider/source/tool scaffolds, one preflight/diagnostics command and redacted sample traces. Reuse the newly shipped Apache-2.0 README/contributor/security/docs infrastructure; only repair verified gaps.  
* Freeze basic E1 task and safety fixtures, plus an explicitly separate E2/E3 real-model utility target, setup-time/resource measurements and a migration/compatibility support policy.

### Exit gate and rollback

Exit: clean no-example installed core \+ independent app pass the versioned contract; unsafe identity/workspace and source tests deny; SDK errors/retries are typed and no physical attempt is duplicated; tested revisions are pinned; every advertised supported capability has an evidence tier. If native egress/clean-install validation is unavailable, accept a narrower E1 development candidate and keep installed-release acceptance BLOCKED.

Rollback: disable/revert provisional SDK/canaries and additive schema drafts without changing canonical user records, historical evidence or security controls. Do not publish a 'stable' contract until cross-version and independent installation pass.

## HXE-1 — MCP, source ingestion and read-only interoperability

Priority: P0 minimal pilot, P1 expanded ingestion. Entry: HXE-0 stable interim contracts and PI-5 authorization at the target evidence tier. Incorporates old HXE-2 and HXE-5; protocol transport and ingestion share one source/rights envelope.

Outcome: unrelated applications can connect authorized third-party tools, resources and documents without adding domain logic to the core or bypassing consent/provenance.

### Deliverables

* Implement replaceable, version-pinned MCP client and server adapters. Start with local stdio and selected Streamable HTTP as supported by a maintained SDK; negotiate capabilities and protocol revisions explicitly, rather than treating an old initialize/session model as universal.  
* Consumer side: discover tools/resources/prompts as different kinds, validate schemas/effects/limits/namespace and registry versions, bind exact server/actor/client identity and revalidate permissions before every use. Initially enable read-only tools/resources; deny ambiguous effects and arbitrary URL/file/network access.  
* Server side: expose only explicitly granted memory lookup, bounded retrieval and task status as first capabilities. Enforce per-client/purpose/expiry, minimal output, pagination, revocation, source IDs and safe error semantics; never expose an entire corpus merely because a client authenticated. Treat external-harness replies as disclosures with purpose-limited payloads, never as an assurance that downstream model calls or storage will obey PAS policy.  
* Implement one local document loader and one appropriately authorized external source adapter behind general ingestion contracts. Preserve issuer, source ID, revision, rights/expiration, license, sensitivity, provenance, withdrawal and embedding/index identity. Apply permission filtering before indexing/ranking/packing.  
* Reuse the existing retrieval, token-budgeted context assembler, source revalidator, read-only tool registry and P19 accounting. Avoid a second RAG, planner, permission ledger or automatic mutating tool loop.  
* Exercise two materially different MCP servers, one independent MCP client, a local document corpus and cross-app denial cases. Keep poisoned tool output as untrusted content, not an instruction or grant. An optional OpenCode MCP-client canary may use synthetic or explicitly approved low-sensitivity material to test usefulness and compatibility; it is not an HXE-1 exit criterion, and it must not require private memory export or external coding-loop control.  
* Document tested protocol versions, source limitations, client/server disconnect/retry rules and future compatibility. AG-UI/A2A are separate later adapter candidates, not this phase's exit gate.

### Exit gate and rollback

Exit: E1 client/server and ingestion conformance with poisoned-output, wrong-client, stale-revision, expired-grant, schema-drift and interruption negatives; zero unauthorized source send. Native/live E2/E3 profiles require external rights, source issuer and physical send fences and remain disabled until proven.

Rollback: independently disable MCP client, MCP server or source adapter; preserve original HTTP API, permitted memory, provenance records and original-intent receipts.

## HXE-2 — Free-first provider portability, observability and real task evaluation

Priority: P0 local model \+ minimal evidence plumbing, P1 optimization breadth. Entry: PI-3 admission semantics, PI-6 frozen benchmark, HXE-0 trace and public contract. Incorporates old HXE-3 and HXE-8. RE-4 and MEM-6 retain their own optimization promotion decisions.

Outcome: at least one real, useful local-model task under measured resource bounds; concrete evidence for provider quality/cost and an auditable attempt/citation/denial trace.

### Deliverables

* Support one locally hosted endpoint first (choose a realistically operable Ollama/llama.cpp-compatible transport based on current hardware). Validate input serialization, model/token capabilities, embedding-space compatibility and graceful absence; no local model or inference service becomes a mandatory core dependency.  
* Validate one genuinely distinct hosted/free provider profile when operator permission, exact account eligibility, privacy/terms and cost caps are available. Keep unsupported/unknown profiles denied; paid mode requires separately explicit monetary admission before any use.  
* Unify trace context across run, model attempt, retrieval, tool, memory, permission and quota checks. Emit structured reason codes, actual-vs-estimated resource use, latency and citations; do not log private payloads or hidden chain-of-thought.  
* Reconcile attempt reservations with actual dispatch/response, ancillary counting/search/embedding operations, provider retries and provider fallback. A gateway zero-price setting is never the sole eligibility proof.  
* Freeze a small reproducible multi-family baseline including independent held-out tasks, prompt-injection and scope negatives, direct/fixed/full-context comparisons and explicit E1-versus-E2/E3 labeling. Use real-model output for utility claims; scripted tasks validate plumbing only. Include an optional coding-task evaluation lane comparing unmodified OpenCode V2 on a specified free/local model with the same OpenCode harness plus separately authorized PAS retrieval/memory/reasoning support, using matched models, task inputs, hardware, budget and intervention rules. Report PAS's marginal contribution; never credit PAS for OpenCode's pre-existing coding capabilities.  
* Measure setup time, cold start, idle CPU/RAM, token estimates vs observed usage, task quality, time-to-first-token, cost, failure/denial rates and local hardware burden. For coding comparisons also measure accepted patch/test success, human interventions, retries, tool failures, stale-context errors and context utilization. Establish targets from observed distributions rather than arbitrary benchmarks. A more elaborate orchestration path must justify its extra latency, state and failure surface.  
* Provide one safe CLI trace/benchmark export and an experiment manifest format shared by MEM-6/RE-4, with immutable variants, ablations and failure retention. Do not implement an independent memory or reasoning promotion controller.

### Exit gate and rollback

Exit: a real E2 local or explicitly approved E3 hosted task achieves a useful result with attributable evidence/resource use; a clean E1 suite is reproducible; zero unapproved physical sends; live profiles remain NO\_GO unless their separate cost/rights gate passes. No optimization is promoted merely because a scripted proxy scores well.

Rollback: pin the deterministic provider/strategy baseline, disable an adapter or exporter, and preserve safety-critical attempt and source receipts.

## HXE-3 — Governed execution, tools and background workflows

Priority: P1; the read-only substrate can start early. Entry: RE-2 has defined the canonical run/step/attempt lifecycle; HXE-1 tool/rights semantics are available at the intended tier. Incorporates old HXE-4 and the scheduling/job portion of HXE-9.

Outcome: a reusable execution layer for bounded workflows, parallel reads, approvals, cancellation, checkpoints, safe resumes and explicit uncertain-effect reconciliation. Strategy choice belongs to RE; execution and physical effect semantics belong to this shared substrate.

### Deliverables

* Write a joint RE-2/HXE-3 ownership ADR: for PAS-controlled workflows, define one canonical run, step, original intent, attempt, effect class, checkpoint, event ordering, cancellation, policy revision and persisted receipt model. Share one PAS state machine and schema; don't create a rival workflow engine. For externally controlled coding runs, OpenCode or another selected harness is authoritative for its own edit/tool/Git lifecycle. PAS supplies scoped context/advice, permitted capabilities and correlation IDs; it does not mirror or commandeer that executor's run state.  
* Start with sequential read-only tools and limited dependency graphs; add bounded parallel independent reads only with deterministic merge and resource reservations. Require declared effects and capability versions.  
* Add explicit proposal/approval/execute/reconcile states for selected mutating tools. Observe unknown outcomes with the original key; do not reissue an irreversible effect under a fresh intent after timeout or process restart.  
* Introduce a narrow opt-in sandbox adapter for approved tools with OS/network/file isolation. Treat manifest signatures as integrity only, never authorization or proof of sandbox safety. Distinguish user-visible permission prompts, application-level policy checks and genuine OS-enforced isolation; an external coding harness's approvals or plugin configuration are not by themselves a sandbox.  
* Provide structured progress events, ordered per-run with at-least-once delivery and resumption cursors, not impossible global cross-worker ordering. Preserve a durable final outcome and content-free audit trail.  
* Support a minimal scheduled/background runner only after cancellation, quotas, lease ownership and restart reconciliation work; do not make general cron/workflow infrastructure mandatory for a local single-user install.  
* Adversarially test malicious tool descriptions, prompt injection, replay, revoked grants, job starvation, orphaned workers, broken retries, resource exhaustion and source changes between planning and send.

### Exit gate and rollback

Exit: E1 deterministic bounded read-only workflow survives interruption, cancellation and idempotent retry; no duplicate irreversible intent or unbounded work. Real mutating tools remain default-off until issuer-bound physical permissions, durable monotonic receipts, human approval and native distributed recovery are independently verified.

Rollback: stop scheduling/new runs, quiesce and reconcile existing original keys, and disable actions without rewriting task history, permission ledgers or user data.

## HXE-4 — Portable memory product and user control

Priority: P1 basic inspect/correct/export; advanced sync later. Entry: PI-4 governed sharing, MEM-2 controls and HXE-0 public contracts; MEM-3+ remains frozen absent authorization. Incorporates old HXE-6 only. Memory semantics still belong entirely to MEM.

Outcome: a developer and user can inspect and manage their authorized personal knowledge, and a consumer can use a bounded portable representation without flattening scopes or losing provenance.

### Deliverables

* Expose minimal user-facing inspect/search/review/correct/forget UX and typed API/SDK operations built over existing MEM-2. Separate explicit user corrections from agent proposals; never register automatic model host writes by default.  
* Define versioned export manifests for supported memory kinds including original owner/workspace/application, source references, verification status, grant restrictions, revisions, embedding compatibility, retention and deletion dependencies.  
* Provide dry-run import, schema/provenance validation, conflict preview, duplicate detection, source-issuer mismatch rejection and controlled rollback. Do not treat an imported file path or same owner identity as a grant.  
* Offer narrow consented cross-app views of explicit profile fields, with expiry, purpose/destination and current value checks. Rich derived or sensitive memories remain individually gated.  
* Add bounded no-secret browser/CLI diagnostics for unsupported legacy rows, stale rights and impossible revocation of copies already exported to other systems. Unknown-origin historical records remain quarantined.  
* Defer full bidirectional multi-device sync, automatic cross-agent sharing and memory promotion until MEM-7 governance and actual operational demand.

### Exit gate and rollback

Exit: explicit owner can inspect/correct/forget, export/import a minimal supported record set without unauthorized scope widening, and observe provenance/denial reasons. A managed retraction removes current allowed reuse; external recipients' copies are outside recall. Native physical erasure/recovery and producer rights gate any sensitive deployed profile.

Rollback: disable portability adapter/UX, retain canonical records and revocation/tombstone/forget receipts, and never silently downgrade a record's scope or verification state.

## HXE-5 — Operational release, independent adoption and optional ecosystem

Priority: P0 minimum release decision, P1 operations, P2 expansion. Entry: the selected feature profile has passed its own HXE/MEM/RE checks and target evidence tiers. Incorporates old HXE-12/13 plus deployment and operator portions of HXE-9. Old HXE-10/11 are retained as explicit optional backlog, not release gates.

Outcome: a narrowly scoped, honest, open-source developer preview/release that another person can install and extend, with measured resource cost, recovery limitations and independently reproducible safety claims.

### Deliverables

* Recheck the already-added Apache-2.0 license across all distributions, dependency/license provenance, CONTRIBUTING and SECURITY docs; produce reproducible builds, a versioned package index/release manifest, trusted dependency provenance and a real no-example quickstart.  
* Give each supported topology a release profile and feature matrix: local E1/E2, optional hosted E3, and cloud E4 only after explicit IAM/identity/network/billing/backup receipts. Unsupported tiers stay disabled instead of becoming generic blockers.  
* Perform clean, pinned native installations from a trusted wheelhouse, independent client/SDK upgrades, real provider/source usage when authorized, resource measurements, bounded stress, rollback and safe restore/delete drills for every topology claimed.  
* Commission a fresh skeptical integration/security review that independently composes app/provider/source/tool/memory consumer and hunts hidden example imports, second ledgers, direct provider bypasses, source-send races, stale journal rollback, budget defects and inaccessible errors.  
* Publish a compact feature-tier scorecard, known limitation list, reproducible conformance commands, redacted evidence manifests, source/SDK compatibility policy, release notes and a finite remediation queue. Reject or disable features whose utility does not justify cost/risk.  
* Optional ecosystem work—reusable skills, additional SDKs, adapters and contribution templates—may grow after observing real developer demand. Try a narrowly scoped OpenCode MCP or plugin adapter only if it demonstrably lowers integration friction or adds PAS value; it is secondary to generic protocol correctness and not a release gate. AG-UI can be added as an independent client adapter; A2A and multimodal remain deferred P2 candidates requiring explicit demand and risk decisions. Avoid implementing a second coding UI, command shell, patch engine, IDE integration or Git workflow inside PAS.  
* Set up a lightweight feedback loop: real outcomes and developer friction \-\> hypothesis \-\> fixed comparison \-\> safety negatives \-\> independent review \-\> canary/rollback. Avoid a permanent heavyweight committee or repeated full-repo reaudits for unrelated changes.

### Exit gate and rollback

First developer preview gate: no-example install; independent HTTP app; one typed SDK; strict-free no-unapproved-send verification; useful E2 local or approved E3 task; authorized read-only source/tool; reproducible diagnostics and cost/resource measurements; Apache-2.0 notices; independently reviewable release evidence. Advanced memory sync, RE adaptation, mutating tools, cloud, A2A and multimodal are not prerequisites.

Production-enabled profile gate: close all inherited relevant PI-0–8, MEM and RE native/live/privacy/deletion/restore/operator gates with independent evidence. A developer preview passing E2 does not make personal-data cloud deployment ready.

Rollback: withhold release or pin the last independently accepted profile, disable failing adapters, preserve source/attempt/memory receipts, and publish a known-limits and migration notice.

## Original HXE-0–13 consolidation map

* Old HXE-0 (inventory), HXE-1 (SDK/extensions), and release-essential HXE-12 (license, docs, packaging) \-\> new HXE-0. Basic OSS docs/license are already implemented at b61d698; do not repeat.  
* Old HXE-2 (MCP) plus HXE-5 (source ingestion/retrieval) \-\> new HXE-1.  
* Old HXE-3 (local/hosted model portability) plus HXE-8 (telemetry and cross-program evaluations) \-\> new HXE-2. RE-4 and MEM-6 still own experiment-specific promotion.  
* Old HXE-4 (general bounded execution) plus HXE-9 (background scheduling) \-\> new HXE-3. RE-2 provides the shared minimal run/step lifecycle.  
* Old HXE-6 (memory portability, user management) \-\> new HXE-4, using MEM-2/MEM-7 authoritative semantics.  
* Old HXE-13 (independent release), remainder of HXE-12 (distribution/ecosystem), and HXE-9 (deployment/operational maturity) \-\> new HXE-5.  
* Old HXE-7 (reasoning improvement) is not duplicated: RE-0–RE-5 are the phase owners; HXE-2 supplies common telemetry and evaluation infrastructure.  
* Old HXE-10 (AG-UI and A2A) and HXE-11 (multimodal) become explicitly deferred optional adapter backlogs under HXE-5, not required named phases. They can be activated by demand and their own acceptance checks.

# Part II — Memory phases MEM-0–MEM-7 (preserved)

These eight phase IDs, boundaries and exit decisions are carried forward from the Memory Architecture & Research Roadmap. This document summarizes their already-defined contracts for integrated sequencing; it does not replace that detailed plan or silently unfreeze MEM-3+. MEM-0–2 have local/default-off candidates with unresolved evidence; MEM-3–7 are future work requiring explicit authorization.

## MEM-0 — Memory baseline and task-level evaluation

Scope: reconcile existing memory/context state; freeze no-memory, fixed memory, full-context and gold baselines, at least 30 hand-reviewed synthetic/masked cases and a task-quality/resource rubric. Explicitly separate recall from actual task completion and source-rights failures.

Dependencies: pinned repository and existing memory/PI fixtures. Exit: reproducible locked dataset/scoring, negative scope/revocation cases, measured baseline and recorded missing live/native evidence. No new automatic memory admission or production enablement. HXE-2 may host shared experiment infrastructure but does not own this benchmark's semantics.

## MEM-1 — Verified project and procedural knowledge

Scope: scoped versioned procedures, project facts/decisions and lessons with exact source/verification labels, lifecycle and context packing; do not treat model summaries as verified. Use a task-A-to-task-B demonstration with stale or invalid-source negatives.

Dependencies: MEM-0, current memory/source authority. Exit: correct provenance, safe idempotency, source-denial and measured reusable benefit without changing default fixed memory. Existing candidate remains default-off/unaccepted until independent/native/issuer gates.

## MEM-2 — Agent-facing governed memory operations

Scope: distinguish authenticated user correction/instruction from an agent proposal; bounded search/fetch/propose/review/revise/forget with CAS, durable receipts, source rechecks and inspection UX. Never let model-supplied identifiers create grants.

Dependencies: MEM-1. Exit: authorized durable outcomes, correct concurrent conflict handling, forget invalidates future retrieval/context use, malicious-content and wrong-actor tests pass. Existing candidate remains default-off; HXE-4 supplies portability UI without taking ownership of memory lifecycle.

## MEM-3 — Selected completed-task episodes

Scope: source-aware, privacy-budgeted capture of eligible completed steps, normalized outcomes and verified tool receipts; explicitly exclude raw hidden reasoning and indiscriminate payload logs. Preserve branch/source/owner links, redaction, retention and deletion.

Dependencies: MEM-0/1/2, a stable canonical run/step event contract from RE-2/HXE-3, and explicit unfreeze. Exit: safe retrieval of a prior validated step, correct replay/abort/isolation and revocation without retrievable remnants. Until unfreeze, planning or fake design only.

## MEM-4 — Bounded offline consolidation

Scope: incremental per-actor/session checkpointed extraction of typed procedure/lesson/conflict proposals with exact source verification and idempotent CAS. Model-assisted proposals must not self-certify or override user corrections.

Dependencies: MEM-3 and explicit unfreeze. Exit: no skip/double-apply under retry, supportable attribution and held-out task improvement without stale or privacy regression. Keep deterministic consolidation as fallback.

## MEM-5 — Hybrid memory index and context research

Scope: experiment with topic indexes, lexical+semantic retrieval, metadata/temporal filters, reranking, hierarchical fetch and adaptive token packing. Compare against fixed retrieval and full context for small histories; no new authority from index location.

Dependencies: MEM-1/3 and ideally MEM-4 plus explicit unfreeze. Exit: candidate lies on a task-quality/token/latency/cost frontier with no scope or revocation regression. HXE-1 owns external document/source adapters, not this memory-specific research.

## MEM-6 — Memory research and promotion flywheel

Scope: durable dataset/model/policy manifests, cross-provider ablations, longitudinal held-out tasks, poisoning/drift tests, blind scoring, canaries and rollback. Record failed hypotheses. Use the shared HXE-2 telemetry store while keeping memory promotion logic in MEM.

Dependencies: MEM-0 onward; formalize after MEM-5 and explicit unfreeze. Exit: independently reproducible end-to-end improvement beyond synthetic recall, bounded resource use and supported native/live promotion evidence.

## MEM-7 — Memory governance, sharing and production scale

Scope: versioned cross-agent/project grants, explicit user control, retention/export/delete propagation, storage quotas, native/cloud failure drills, operational cost and release rollback. Share only from verified policies, not common physical storage.

Dependencies: MEM-2–6 as applicable, explicit unfreeze and inherited authority gates. Exit: relevant release gates, physical deletion/restore and multi-agent/scope evidence close at the claimed topology. HXE-5 owns general product release, not memory semantics.

## Memory program freeze and promotion rule

The original PI charter froze new MEM-3+ feature work. A phase name appearing in this roadmap does not lift that freeze. HXE-4 may improve the user/product layer over accepted MEM-2 semantics without introducing new automatic capture/consolidation. Before implementing MEM-3+, require an explicit owner decision, readiness ADR, evidence-aware scope and narrow independent review. No historical MEM-0–2 implementation candidate is relabeled accepted by this document.

# Part III — Dynamic Reasoning phases RE-0–RE-5 (preserved)

These six phase IDs and responsibilities are carried forward from the Dynamic Reasoning Engine PRD. HXE does not introduce a parallel reasoning planner or duplicate adaptive strategy policy. Requested effort is a user control; effective effort is a policy-narrowed, provider-capability-aware, bounded execution plan.

## RE-0 — Architecture and benchmark

Scope: versioned PRD/API and threat/ownership ADR, strategy registry, fixed and held-out task-quality/latency/resource baselines and direct-response comparator. Incorporate PI-6 synthetic tasks without confusing them for actual model utility. Include optional external-harness paired tasks to test whether PAS planning, evidence and memory materially improve a mature coding agent under matched model, resource and human-intervention budgets; keep that separate from general-purpose reasoning benchmarks.

Dependencies: pinned PI-6 baseline and HXE-0 execution ownership. Exit: reproducible offline benchmark and clear safety/phase ownership, no new live model dispatch.

## RE-1 — Effort-level contract and capability mapping

Scope: auto/low/medium/high/max requested-versus-effective controls, app/user/operator narrowing, exact model-native reasoning capability mapping, telemetry and explicit fallback/unsupported. Maintain strict-free physical dispatch admission.

Dependencies: RE-0, PI-3/HXE-2 policy. Exit: existing direct/chat behavior remains compatible; unknown effort features cannot cause hidden calls or unbounded work.

## RE-2 — Finite deterministic orchestrator

Scope: direct, decompose, critique-refine and tool-verify strategies with one canonical PAS-controlled run/step/attempt lifecycle, finite time/token/tool budgets, bounded fan-out, cancellation, progress and replay. Establish the minimal execution contract that HXE-3 extends. Do not subsume the session manager, terminal tool loop or edit lifecycle of OpenCode or another external coding executor; external correlation is an adapter concern.

Dependencies: RE-1, HXE-0 joint ADR. Exit: objective paired improvement in eligible tasks, no duplicate attempts, safe stop/cancel/recovery and no hidden provider spend. HXE-3 must reuse this state machine.

## RE-3 — Grounded iterative reasoning and research

Scope: evidence-gap detection, selective authorized retrieval and tool verification, source-grounded synthesis, citation-aware critique and bounded follow-up. Source changes or revoked rights must propagate through all steps.

Dependencies: RE-2 plus PI-5/HXE-1 at the claimed evidence tier. Exit: grounded task improvement without fabricated citations or permission expansion. Live paths remain disabled until the issuer/source/send-time gates pass.

## RE-4 — Adaptive strategy selection

Scope: shadow strategy variants, task features, measured expected utility/resource tradeoffs, early exit, capped candidate comparison and reversible policy promotion. Keep a deterministic safe baseline available. When external-harness support is considered, score the incremental PAS-assisted benefit against the unchanged external harness on held-out tasks, accounting for latency, cost, interventions, stale memory, injection risk and failure complexity; reject complexity without a reliable net lift.

Dependencies: RE-3 and HXE-2 experiment infrastructure. Exit: independent held-out matched-budget lift, no critical safety/cost regression, canary and one-command rollback; reject variants without evidence.

## RE-5 — Production and extension hardening

Scope: long-run UX, limits/fairness, independent API/SDK integration, native/cloud recovery where supported, cross-provider/capability robustness and adversarial review.

Dependencies: RE-0–4 as released and relevant PI/HXE gates. Exit: independently reproduced useful performance, privacy/cost/replay evidence, robust cancellation and rollback at the claimed topology. An offline useful reasoning preview can ship without claiming this production acceptance.

## Potential MEM/RE consolidation — recommendation

Do not merge phase IDs now. MEM-0 and RE-0 share evaluation plumbing but have different scientific baselines and are already defined; MEM-6 and RE-4 share experiment infrastructure but promote different policies; RE-2 and HXE-3 share one execution substrate but have separate strategy/execution deliverables; MEM-7 and HXE-5 share operational evidence but distinct memory versus overall release authority. Consolidating these would reduce naming overhead slightly but enlarge review blast radius and blur accountability.

If implementation reveals genuine duplication, merge the code/ADRs first and keep phase gates distinct. Revisit phase consolidation only after HXE-0 inventory demonstrates shared acceptance tests, no incompatible rollback or authority boundary, and a measured reduction in maintenance effort.

# Part IV — Sequence, dependencies, acceptance and governance

## Execution sequence: value before breadth

Sprint 0 (historical/under review): HXE-0 implementation candidate landed at 9c90c1d844e9126cb494f286e5f0f80e4be9a6a0. Its independent review fixes are in progress as of 3 November 2026; this roadmap does not alter HXE-0's scope, attest acceptance, or presume the PI-6 frozen source-identity issue is resolved. Finish its existing verification and record any remaining evidence blockers under the original gate.

Sprint 1 (next): HXE-1 minimal read-only MCP/source pilot and HXE-2 local-model/real-task benchmark in the same coherent developer vertical slice. Start RE-0 and the common HXE-2 evidence format without waiting for future MEM-3+. Prove useful PAS behavior and generic client compatibility first; treat a synthetic/low-sensitivity OpenCode MCP consumer as an optional comparative canary, not a prerequisite. Keep live external rights/billing gates disabled until separately approved.

Sprint 2: RE-1/RE-2 effort controls and finite orchestration while extending HXE-1 retrieval; move from one useful direct request to selected grounded tasks. HXE-3 must consume RE-2's canonical run state, not invent its own.

Sprint 3: RE-3 grounded iteration and HXE-4 basic inspect/correct/export experience over existing permitted MEM controls. Add HXE-3 read-only tool workflows and background work only where the measured tasks need them.

Sprint 4: RE-4/RE-5 and, only after explicit unfreeze, MEM-3–MEM-7 scientific program. Introduce adaptive promotion, richer memory, approved actions and true distributed operations only after corresponding evidence.

Sprint 5: HXE-5 release evaluation for the narrowest useful supported profile; independently verify real task value and setup/idle operating cost. Mature cloud, AG-UI, A2A, multimodal or ecosystem only if justified by actual integrations.

These are sequencing labels, not additional phases or calendar commitments. Work may overlap when contracts are stable and safety profiles isolated. A phase can be accepted at E1 while live branches stay default-off and blocked; its documentation must state that narrower scope explicitly.

## Minimal developer-preview profile (first public usefulness gate)

* Install core without reference apps and pass an independently reproduced minimal package/startup test.  
* Use a stable v1 external HTTP API through one typed SDK and an unrelated separately packaged consumer; no private core import or unapproved manifest authority.  
* Perform at least one useful E2 local-model or expressly authorized E3 hosted-model task, with source/citation accuracy and a transparent failure/denial path. E1 scripted responses never satisfy the utility claim.  
* Exercise one authorized read-only retrieval/source/tool route and a small MCP interoperability canary; preserve exact scope, issuer and source revision.  
* Demonstrate no unapproved physical sends under strict-free policy, no hidden provider fallback, resource ceilings, bounded failure and redacted usage/trace diagnostics.  
* Publish accurate Apache-2.0 licensing and dependency notices, reproducible setup, baseline test receipts, time-to-first-result and idle/local resource figures.  
* Explicitly exclude advanced memory synchronization, autonomous memory promotion, mutating tools, adaptive RE, A2A, multimodal and production cloud data handling from this preview unless separately accepted.

## Capability-specific inherited gates (do not waive)

* PI-0–PI-4 independent and native/live acceptance: document the exact unsupported profile; no default-on disclosure/production claims from prior synthetic probes.  
* PI-5 source/recipient/model-processing rights, atomic revocation-to-send permit and source issuer epochs: close before any external model/source disclosure affected by the path. A stale final read check is not an atomic issuer lease.  
* PI-5/PI-7 original-key and revocation monotonic authority: close before distributed replay, mutating remote effects, stale snapshot restore or production data recovery. SQLite snapshots alone cannot protect uncertain intents.  
* Legacy missing-provenance historical records: quarantine before export/replay/SSE/history until inventory and canaries prove classification. A hypothetical unmarked leak is not an established incident.  
* PI-6 live model quality, source-identity and physical accounting: keep historic E1 case fixtures immutable; add new revision identities for post-license builds; do not promote synthetic success to E2/E3.  
* PI-7 native egress, independent wheelhouse provenance, Docker/Postgres/Dynamo, cloud IAM/network/identity, billing caps, deletion and mixed-age restores: close only when the corresponding deployment profile is enabled or released.  
* MEM-2 default-off and MEM-3+ freeze: retain until separately reviewed. RE paid-mode/native-effort/strategy promotion needs its own positive and adversarial gates.

Risk-triggered exception: if HXE-0 finds a reproducible P0 leak, unauthorized paid send, irreversible data corruption, or an architectural impossibility that every intended supported path requires, stop affected work and fix that specific seam. Do not replace the entire core merely because an optional cloud capability lacks an approved operator environment.

## Architecture guardrails and shared seams

* Identity/auth: trusted principal, actor, app, workspace, purpose, grant version and source authority bind once at the server boundary and are rechecked at physical disclosure.  
* Inference: one canonical provider admission/reservation/settlement path for PAS-originated physical calls. RE decides if further PAS reasoning is useful; HXE-2 supplies replaceable model transports; PAS-owned tools/MCP paths cannot dispatch around that control. Do not represent external coding-agent model calls as PAS-admitted unless an independently enforceable, verified integration actually routes those calls through the PAS gate.  
* Execution: RE-2 creates the minimal durable run/step state for PAS-controlled work; HXE-3 adds general effects, approval and scheduling using the same PAS IDs, events and replay strategy. Exact original intents survive restart. Externally owned coding sessions remain external; integrate using scoped MCP/SDK actions, correlation and observed outcomes, not competing attempt controllers.  
* Retrieval: PI-5 defines rights/provenance and context packing; HXE-1 adds external protocol and ingestion adapters; MEM-5 owns memory-specific ranking and context research.  
* Memory: MEM defines authoritative storage, verification, correction, consolidation, deletion and promotion. HXE-4 is a product/API layer; no second memory store or implicit global namespace.  
* Evaluation: HXE-2 owns shared telemetry and experiment packaging; PI-6 fixtures, MEM-6 memory promotion and RE-4 strategy promotion remain independently versioned and independently accepted. Optional coding comparisons use the same external harness/model/budget in both arms, isolating whether PAS-supplied retrieval, memory or reasoning changes outcomes rather than claiming to reproduce the coding harness.  
* Operations: HXE-5 owns general operator and distribution gates; MEM-7 and RE-5 still prove their feature-specific production behavior, never inferred from a generic deployed smoke.

## Measurement and independent review contract

At each phase start, pin HEAD, inspect status and AGENTS.md, docs/README.md, docs/current-state.md, relevant contracts, migrations, source, tests and original evidence. Confirm the phase's concrete prerequisites. If a required native or live system is missing, mark the precise evidence blocked rather than presenting a mock as equivalent.

Each phase produces a compact plan/hardening record, changed-contract/source inventory, bounded tests including negative cases, evidence-tier ledger, capability/default-off matrix, independent review target, rollback and known limitations. Prefer targeted suites and a small fixed safety smoke over rerunning every historical full suite after every documentation edit; still run cross-cutting coverage when a shared boundary changes.

Score task usefulness, quality-per-resource, latency, setup and idle cost, independent integration friction, scope/security violations, retries, output attribution and operational recovery separately. For external-agent augmentation, record incremental task success, accepted edits, tests, human interventions, context freshness, total tool/model work and contamination/permission incidents against an unchanged-harness comparator. Freeze thresholds only after representative baselines. A successful phase reduces friction without hiding unsupported paths.

Use Sol High for plan+skeptical design review, Sol Medium/High for implementation by complexity, Sol High for independent verification, and Luna Max/XHigh for bounded remediation when useful. Keep separate review from implementation; no unnecessary subagents or repeated handoff documents when a focused single-session review suffices.

## Risks and responses

* Risk: six HXE phases become mega-phases. Mitigation: each has one measurable outcome, a narrow minimal preview, optional subworkstreams, explicit exit tests, and no automatic promotion of optional features.  
* Risk: SDK/API freezes a flawed identity/attempt contract. Mitigation: HXE-0 ADR and clean-room consumer first; early versions provisional until independent conformance; compatibility tests before declaring stability.  
* Risk: MCP and research routes bypass rights, quotas or physical send checks; a recipient harness might subsequently disclose a PAS excerpt to its own model or retain it after revocation. Mitigation: central PAS policy adapters, manifest-versus-grant distinction, provider-attempt accountability, minimal approved disclosure, default-off live branches, and clear recipient-side trust limits. Never claim downstream strict-free/privacy/deletion enforcement on the strength of a PAS-side MCP check alone.  
* Risk: separate RE and HXE runtimes—or PAS and an external coding agent—accumulate overlapping controllers and technical debt. Mitigation: one persisted PAS run/step/intent/attempt contract for PAS-controlled work, RE strategy above shared HXE execution; externally owned sessions remain in the coding harness, with only explicit correlation, advisory capabilities and scoped interfaces at the boundary.  
* Risk: legacy memory export or stale backup revives private evidence. Mitigation: monotonic out-of-snapshot authority, quarantine unknown lineage, negative mixed-age restore and physical erasure drills before release.  
* Risk: optimization looks successful only on scripted test cases. Mitigation: E2/E3 useful tasks, matched-budget independent holdouts, ablations and fail/reject decisions; preserve failed experiments.  
* Risk: a feature-rich default install becomes operationally expensive or a duplicate coding IDE/terminal project. Mitigation: credential-free minimal PAS profile, optional infrastructure, measured setup/idle hardware costs, reuse maintained coding harnesses for editing/test/Git/IDE workflows and require measured unmet needs before adding coding-specific infrastructure.

## Open decisions to resolve inside existing phases

* HXE-0: API/schema source of truth, supported first SDK language, stable extension manifest version range, execution ownership ADR, the license-metadata/PI-6 identity transition and first independent consumer.  
* HXE-1: exact MCP protocol revision and tested peers, initial source rights model, local versus remote transport, minimal read-only server exposure, and whether an optional synthetic OpenCode client canary yields useful compatibility evidence without widening disclosure.  
* HXE-2: first local endpoint given actual hardware, official provider-account eligibility, safety-safe trace retention, benchmark tasks and real utility thresholds; if a coding augmentation lane is run, select matched OpenCode/model/task baselines and intervention metrics.  
* RE-0/2: canonical PAS work budget per effort level, strategy registry, stop/retry semantics and shared task event schema; explicitly distinguish PAS-controlled work from an external coding harness's own run/tool lifecycle.  
* MEM post-freeze: whether and when to authorize MEM-3+, using real memory utility and lifecycle readiness, not simply the calendar.  
* HXE-5: which E2/E3/E4 profiles to actually ship and what third-party integrations justify AG-UI, A2A, multimodal or sync.

## References and revision log

Source roadmap: [post-pi-harness-excellence-roadmap-reviewed-final-2026-11-03.md](https://chatgpt.com/library?file_id=libfile_ccd25a42ecc48191bfbf00ec149800f0&account_id=personal), saved in ChatGPT Library.

Memory source plan: [Personal AI — Memory Architecture & Research Roadmap](https://chatgpt.com/library?file_id=libfile_64d40c950370819192c063a6c792e1f6&account_id=personal) (MEM-0–MEM-7), 2026-10-28.

Reasoning source PRD: [Dynamic Reasoning Engine (RE-0–RE-5)](https://chatgpt.com/library?file_id=libfile_81e47018d6fc8191bc423dec389740b0&account_id=personal), 2026-11-01.

Repository baseline: [https\://github.com/jasonkli21/personal-ai-system/commit/b61d69890255ca3de736e7236581cee559358f32](https://github.com/jasonkli21/personal-ai-system/commit/b61d69890255ca3de736e7236581cee559358f32)

Current state and PI gate registry: [https\://github.com/jasonkli21/personal-ai-system/blob/b61d69890255ca3de736e7236581cee559358f32/docs/current-state.md](https://github.com/jasonkli21/personal-ai-system/blob/b61d69890255ca3de736e7236581cee559358f32/docs/current-state.md) \| [https\://github.com/jasonkli21/personal-ai-system/blob/b61d69890255ca3de736e7236581cee559358f32/docs/platform-independence/pi-cross-phase-gate-registry.md](https://github.com/jasonkli21/personal-ai-system/blob/b61d69890255ca3de736e7236581cee559358f32/docs/platform-independence/pi-cross-phase-gate-registry.md)

Quality cleanup evidence: [https\://github.com/jasonkli21/personal-ai-system/blob/b61d69890255ca3de736e7236581cee559358f32/docs/quality/repo-quality-review-2026-11-03.md](https://github.com/jasonkli21/personal-ai-system/blob/b61d69890255ca3de736e7236581cee559358f32/docs/quality/repo-quality-review-2026-11-03.md)

Revision summary: v3 updated PI/repo baseline to b61d698, removed already-shipped license/docs from TODOs, carried forward the PI-6 frozen identity conflict, consolidated HXE-0–13 into HXE-0–5, preserved MEM-0–7 and RE-0–5, moved HXE reasoning ownership into RE and AG-UI/A2A/multimodal into optional backlog, and added the E2/E3 developer vertical slice with separate development-versus-enablement gates. v3.1 adds an explicit build-versus-integrate rule informed by OpenCode V2, optional matched-budget external coding-harness experiments, clear external session ownership and MCP disclosure limits, and a status-only HXE-0/sprint update. No phases are added; HXE-0 and MEM-0–2 phase definitions are unchanged.

Status: execution proposal only. User approval of this roadmap does not authorize provider use, personal-data processing, cloud deployment, unsafe tool effects, frozen MEM-3+ implementation or acceptance-gate waiver.


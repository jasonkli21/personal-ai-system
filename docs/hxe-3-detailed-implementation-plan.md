# HXE-3 — Detailed Implementation Plan

Personal AI System \| 2026-11-03 \| Planning baseline 6d9fd3c4252e3e2bde6563af76d7a896af7de5f8 \| Intended implementer: Sol Medium \| Independent reviewer: Sol High \| Final fixes: Luna High/XHigh.

# 1\. Objective, decision and authority

Deliver an optional, bounded, governed execution substrate for PAS-owned read-only workflows, with durable original-intent/attempt identities, deterministic step dependencies, cancellation, resumable per-run progress and failure/uncertainty reconciliation. Design a guarded approval/effect state machine and a narrowly isolated optional tool process; do not enable real mutating effects or an unattended scheduled service without their separate evidence gates. Speed-first success is a useful and adversarially tested E1 read-only vertical slice, not a general-purpose autonomous agent.  
Scope source: Integrated Harness Excellence Roadmap v3.1 /Users/jasonkli/projects/personal-ai-system/docs/personal-ai-system-integrated-roadmap-11-03.md. Repository https\://github.com/jasonkli21/personal-ai-system. Exact planning commit 6d9fd3c4252e3e2bde6563af76d7a896af7de5f8 (HXE-2 review remediation). Repository AGENTS.md is binding; code, executable contracts and tests outrank implementation receipts, accepted ADRs outrank future plans, and current permission/security gates outrank convenience. Pin the actual HEAD, compare to baseline, inspect git status and preserve unrelated edits before implementing.  
The roadmap says RE-2 should define the canonical lifecycle before HXE-3. RE-2 is still planned rather than accepted; this is an architectural dependency, not a blanket ban on offline work. The first in-session task is a joint RE-2/HXE-3 ownership ADR and one minimal, versioned runtime contract. HXE-3 owns execution/effects/permissions; RE-2 later owns reasoning strategy selection through that contract. Do not claim RE-2 is implemented or add direct/decompose/critique strategies here.

# 2\. Verified starting state and reusable seams

* HXE-0: provisional consumer v1.2.0, Python SDK, separate Project Checklist consumer, owner/actor/application/workspace binding, original-key continuation, partial E1; full independent installed/native acceptance remains open.  
* HXE-1: read-only PI-5 retrieval/MCP pilot, bounded stdio/Streamable HTTP synthetic paths and rights-aware ingestion; partial E1 only. Reuse closed operator tool registry and source permission/revision checks.  
* HXE-2: optional llama.cpp Unix socket, canonical P19 reservation, privacy-safe trace and frozen real-task manifest; synthetic E1 only. E2 real local-model utility is blocked unavailable, E3 hosted blocked unverified. Latest review remediation includes source generation 5 and planning lock v31.  
* Existing mutable task machinery: backend/src/personal\_ai/contracts/delegated\_tasks.py and task\_control.py already represent source-owned immutable commands and proposal/validation/confirmation/execution/reconciliation; backend/src/personal\_ai/retrieval/tools.py permits read\_only only. Reuse exact binding, idempotency, immutable receipts and existing source/domain ownership; do not replace them with an ungoverned generic executor.  
* Existing contracts: docs/decisions/0023-external-consumer-and-execution-authority.md requires one run/step/intent/attempt model, exact logical keys, changed-body conflict, conservative unknown dispatch, cancellation boundaries and current-rights replay. P19 owns physical provider reservations; PI-4/PI-5 own source rights; MEM remains default-off and MEM-3+ frozen.

Evidence and status sources: docs/current-state.md; docs/harness-excellence/README.md; docs/harness-excellence/2026-11-03-local-inference-verification.md; docs/harness-excellence/2026-11-03-hxe1-remediation.md; docs/platform-independence/pi-cross-phase-gate-registry.md. At planning time, production is NO-GO. The implementer must re-read all relevant files at actual HEAD, not assume this snapshot is still current.

# 3\. Ownership and safety invariants

Single PAS lifecycle: every PAS-controlled workflow has a single canonical run, bounded step, original immutable intent, physical attempt and content-free ordered receipt/event model. Existing chat continuation and domain mutation protocols retain their immutable identifiers; extend via adapters and additive migrations, not parallel ledgers.  
External harnesses: OpenCode/other coding agents own their own edit, shell, test and Git lifecycle; PAS can supply scoped context, bounded advice/permissions and a correlation ID. Never mirror or seize that run state, nor build a second coding shell, patch engine or IDE.  
Authority: verified owner/actor/client/app/workspace/purpose binding and current capability/source revision/issuer/expiry checks at planning, immediately before each tool call, at result consumption, at any provider send and at disclosure/replay. Manifests and tool descriptions never confer grants.  
Effects: closed effect classes read\_only, proposal\_only, and explicitly approved effect. Unknown effect is deny. For real mutation, approval is bound to exact actor, intent digest, tool identity/version, parameters, scope, target revision, source dependencies, expiry and one operation key; a click/approval is neither an OS sandbox nor durable issuer authority.  
Retry: exact-key retry with same body returns prior terminal/uncertain state; changed body conflicts. Never generate a new original key to paper over timeout or lost acknowledgement. An unknown remote effect is reconciled against the original intent and downstream receipt before any reissue.  
Resources: a run and every step enforce finite limits on DAG size/depth, active concurrency, deadlines, CPU/wall time if enforceable, bytes, tool output, model tokens, physical sends and reservations. Reserve before work; shared quota/strict-free denial must stop before send. No unlimited fork, fallback or background retry.  
State and security: durable stop/cancel/lease state; fencing or CAS for competing workers; per-run sequence values (not global ordering); progress can be redelivered, cursors resume without gaps under retention contract; never log prompt text, tool secrets or hidden reasoning.

# 4\. Scope and work packages

## WP0 — Inspect and harden architecture before code

* Map existing entity/state ownership, code paths, durable idempotency authority, P19 usage, PI-5 tool invocation, task confirmation protocol, SDK and trace semantics. Reconcile RE-2 entry assumption and existing ADR 0023 with a new narrowly accepted joint ownership ADR. Document one chosen storage/transaction strategy, versioned event schema, effect taxonomy, step transitions, recovery and limits. Record which prior artifacts remain immutable.  
* Set explicit supported profile: E1 synthetic, default-off, read-only. Identify contingent E2/native tests, effect-enablement gates, and the maximum safe initial scheduler scope. If an existing run aggregate supports the needs, extend it rather than create new tables; otherwise make only additive, isolated persistence with a migration/backfill/rollback policy.

## WP1 — Finite, deterministic workflow contract

* Introduce enduring capability-named contracts for RunSpec, StepSpec, ToolBinding, ExecutionBudget, ScopedIntent, AttemptReceipt, ProgressEvent, RunStatus and StepStatus. Version and validate closed schemas. Reject cycles, missing dependencies, duplicated steps, ambiguous effects, untrusted dynamic tool code, version drift, oversized values, and non-deterministic graph plans before any work.  
* Implement sequential read-only step execution first with bounded DAG topological order and deterministic result aggregation. Add bounded parallel independent reads only after reservation and cancellation correctness; stable result ordering follows graph/step index, not completion timing.  
* Reuse existing PI-5 read-only tool registry and optional MCP adapter by trusted operator registration, not client-submitted Python handlers or URLs. Preserve input/output schema checks, timeout, max bytes, source provenance and per-client rights. Deny tool output masquerading as system instructions, additional tools or approvals.

## WP2 — Durable progress, cancellation and restart

* Persist scoped immutable run/request digest and step/attempt transitions atomically with monotonically ordered per-run events and a terminal result. Use one transaction boundary for state+event+quota reservation where the existing store supports it; document exactly-once claims vs at-least-once event delivery. No globally ordered event promise.  
* Add safe create/status/cancel/events controls only to the smallest appropriate existing authenticated HTTP/SDK surface; treat v1.2.0 as provisional, add capabilities under negotiated semantics, and avoid breaking existing continuation keys. If public API expansion creates acceptance risk, ship an internal operator-only E1 boundary and record the API gate.  
* Cancellation is persistent and best-effort for already-running read calls; forbid any new physical work once observed. A restart resumes only proven-unstarted or provably idempotent operations; UNKNOWN outcomes remain reconciliation\_required. Lease epochs/CAS prevent old workers from committing after takeover. Handle client disconnect without treating it as confirmed cancellation.  
* Progress events have bounded payloads, nonsecret reason codes, per-run sequence, stable cursor, explicit truncation/retention, terminal event and safe replay. Trace correlations are pointers, not a second execution ledger. Subscriber outages cannot cause duplicate work.

## WP3 — Guarded effects and approvals (NO real effects enabled)

* Define proposal \-\> awaiting\_approval \-\> approved/rejected/expired \-\> dispatching \-\> reconciling \-\> applied/failed/uncertain as a state machine and bind approval to exact immutable intent and current authority. Implement E1 synthetic/mocked effect simulations and wrong-actor/expired/stale-revision denials. Production execution of mutating tools remains disabled; distinguish this from historical domain-specific confirmed tasks.  
* If a real effect adapter is considered, stop at a non-executing contract until an independent issuer-bound dispatch permit, monotonic external original-key authority, human confirmation, physical sandbox and native multi-worker/restore evidence are available. Unknown sends cannot be repeated with a new key. Do not assert an approval prompt substitutes for a trusted physical-send fence.

## WP4 — Optional sandbox and worker pilot

* Sandbox adapter is opt-in and designed for one selected, fixed executable/operation with explicitly restricted FS/network/process privileges, resource bounds, no ambient credentials and denied redirects/egress. Do not claim isolation from a manifest signature, Python monkeypatch, environment variable or process timeout. If OS sandbox primitives cannot be tested, leave the adapter disabled and mark E2 blocked.  
* A minimal background worker may support queued one-shot read-only runs only after durable lease/CAS, cancellation and quota admission have passing tests. A repeating scheduler is conditional; if added, require bounded cadence/missed-run policy, per-schedule identity and duplicate prevention. Full cron, multi-tenant fleet scheduling and unattended mutation are deferred.

## WP5 — Evidence, docs, packaging and cleanup

* Add behavior-named unit/state-machine tests, property/fault-injection sequences, process-restart and two-worker fixtures, API/SDK contract tests if public, and independent read-only MCP/source canary. Add one focused Make target such as workflow-check if useful, never a phase-named command. Preserve frozen planning and PI-6 records; an actual hashed-source change may require a new additive source identity instead of modifying source-generation-5/v31.  
* Update owning module README, durable ADR, docs/current-state.md, docs/harness-excellence/README.md, release gate registry and dated verification receipt. Keep root README for enduring user value, not phase history. Classify every test as E1, E2, E3, E4 or not run. Do not manufacture E2 real model or E4 production evidence.

# 5\. Proposed bounded defaults (harden in-session)

Initial guardrail targets (not magic constants or permission grants): \<=12 steps, DAG depth \<=4, \<=2 parallel independent read steps, \<=3 active tool calls total, per-step deadline \<=20 s, per-run \<=120 s, per-step result \<=32 KiB, total retained run result \<=128 KiB, events \<=256/run with bounded retention and an explicit truncation marker. Actual limits should be derived from existing budgets/quotas and documented in one trusted operator policy. Fail closed for absent limits; no user-controlled increase beyond configured caps. Token and provider operation budgets must use canonical P19 admission rather than these byte caps.

# 6\. Acceptance and adversarial test matrix

* Graph/contract: duplicate/cycle/unmet dependency/unsupported effect/version/schema/oversized graph rejected before execution; stable topological ordering; results deterministic across completion order.  
* Permission: wrong owner/actor/app/workspace/client/purpose, revoked grant, changed source revision/issuer, expired scope, stale model/quotas and poisoned tool metadata deny. Recheck before use, before retention and replay; no source text in denial logs.  
* Replay/uncertainty: same key/same payload resumes or returns exact state; same key/different payload conflicts; crash before reservation, after reservation, after dispatch before receipt, after durable completion, and before ack never create a second irreversible intent. Unknown remains UNKNOWN until evidence-based reconciliation.  
* Concurrency: two workers claim same run; expired lease, delayed completion, fencing token change, cancellation during claim, worker death and fairness starvation do not double-call or exceed quotas.  
* Cancellation/quotas: cancel queued/running/partial DAG; deadline and oversized output; failed/rejected tool; burst of runs; background restart and schedule misfire if enabled. No runaway calls, event gaps hidden as success or negative quota.  
* Approval/effect: wrong actor, stale tool version, changed parameters, reused approval, expired approval, replay across targets, source revocation and lost effect ack all deny/reconcile in E1 fake. No production mutation is physically dispatched.  
* Sandbox: if enabled, prove native FS/network/process isolation, no inherited credentials, inaccessible paths, traversal/symlink defenses, time/CPU/memory/output caps, redirects, teardown and cleanup. A mocked subprocess alone is E1, not sandbox acceptance.  
* External-harness boundary: OpenCode-like caller cannot submit edit/shell/Git execution as PAS-authorized tool or override PAS run receipt; PAS correlation references external run only, and no automatic private memory export.  
* Compatibility and evidence: HXE-0 SDK/Checklist, HXE-1 MCP, HXE-2 local inference, existing delegated Shopping controls and MEM-2 default-off behavior remain unchanged. Offline-frozen PI-6 and planning evidence are preserved additively.

# 7\. Verification commands and exit decisions

At implementation HEAD run the appropriate new focused test command and existing commands (adapt env to installed toolchain): git status \--short; git diff \--check; make naming-policy-check; make backend-lint; make provider-isolation-check; make retrieval-security-check; make mcp-adapter-check; make planning-eval; make offline-benchmark-check; make backend-test-offline; make backend-build. Do not delete or rewrite the user's untracked files; document individual blocked commands with exact reason. Run native PostgreSQL/two-worker tests if a disposable database and permission are available.  
Scoped E1 EXIT (required): one trusted operator-enabled synthetic read-only workflow executes \>1 dependent step; bounded parallel independent reads if implemented; deterministic terminal result; cancellation, source revision revocation, restart/replay and changed-body conflict pass; zero unauthorized physical sends; no mutation enabled; coverage and performance evidence reproducible. If core cannot durably resume without duplicate effect risk, mark CHANGES REQUIRED rather than pass.  
Optional acceptance: native sandbox, installed server, schedule runner, real-model E2, hosted E3 and deployed E4 are capability-specific gates and may be BLOCKED/DEFERRED with relevant adapters disabled. Do not let a blocked native profile masquerade as globally passed HXE-3; state precise PARTIAL E1 scope. Real mutation release is NO-GO without issuer-bound physical authorization, durable monotonic journal, approval and native recovery.  
Rollback: disable workflow intake and background scheduling, cancel/quiesce safe reads, retain original-key/attempt/progress receipts, reconcile unknown effects against their original identity, keep source/permission ledgers intact, and revert optional adapter routing rather than destroying persisted run history. Schema rollback is additive-compatible; no silent deletion of audit authority.

# 8\. Hard blockers versus deferrable work

* NOW: reach ownership agreement with RE-2; one canonical persistence/attempt authority; safe read-only DAG and cancellation/replay; source/capability rechecks and bounded budgets; clean targeted security and regression evidence. Any duplicate idempotency engine, unbounded retry, or unauthorized send is a stop issue.  
* BEFORE\_ENABLEMENT: real mutating tools, remote MCP executors, sandboxed OS/tool effects, recurring unattended schedules, cloud/multi-worker recovery, real provider sends, private sources, distributed leases and physical deletion each require their exact issuer, network, user-consent, restore/retention, billing and native evidence.  
* DEFER: generic cron/UI, autonomous multi-agent agents, automatic strategy adaptation (RE), memory episodes/consolidation (MEM-3+ freeze), OpenCode edit control, A2A/AG-UI, new provider breadth and cloud release. Keep in backlog with owner and measurable activation criterion.

# 9\. Execution handoff

Sol Medium must first inspect the actual repository and harden this plan in the same session, no subagents; implement in focused commits and self-verify. Sol High independently reviews exact target commit and emits a single complete Luna High/XHigh remediation handoff. Luna implements fixes, performs final verification and commits. No additional review follows Luna.  

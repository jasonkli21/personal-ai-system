# PI-7 Independent Post-Implementation Review Prompt

**Run in a fresh, separate Codex session:** GPT-6.1 Sol, **High** reasoning.
**Repository:** [jasonkli21/personal-ai-system](https://github.com/jasonkli21/personal-ai-system).
**Target:** the single PI-7 commit supplied by the implementer. Verify that it contains the [implementation report](pi-7-implementation-report.md) and [verification ledger](pi-7-verification.json), and compare it with its pinned parent. The plan-only deploy entrypoint, blocked apply, and v27 revision guard are explicit review items.
**Mode:** Independent skeptical review. Do not spawn subagents or delegate. Do **not** implement fixes in this review session; report findings and produce a self-contained remediation handoff if needed.

## Mandate

Independently assess whether PI-7 makes the existing application-neutral platform reproducibly installable, safe to operate offline, appropriately guarded for cloud deployment, measurably free-first and privacy-preserving, and honest about all unverified production gates. The plan is a hypothesis, not a checklist to rubber-stamp. Search for serious defects and unplanned omissions \*outside\* the implementation plan too.
Prior source baseline: 57fc5ea53af6540c86f6f0df7ef2ff23b67a1d62. PI-5 remained blocked\_unverified and PI-6 offline evaluation was locally complete while production promotion was no\_go. Recheck current evidence, not just this statement.

## 1\. Boundaries and safety

* Read AGENTS.md, docs/README.md, docs/current-state.md, PI charter/index/PI-0 exit, PI-5 completion gate/remediation, PI-6 report/closure/verification, the [PI-7 hardened plan](pi-7-implementation-plan.md) and [pre-code hardening](pi-7-plan-hardening.md), implementation report and machine ledger, root/build/deployment docs and changed code/tests.
* Record exact target SHA, parent/base, dirty/untracked files, artifact hashes, OS/toolchain and all skips. Preserve user changes and historical files.
* Do not use real providers, credentials, source data, cloud accounts, production databases, paid APIs, live IAM operations, restore/delete, or network package installations. No cloud apply, Git push or PR. Run only isolated offline and specifically owned local tests; respect active execution permissions.
* Treat fake/installed/local-native/cloud-live evidence as different categories. A reported passing script is not acceptance of provider billing, physical model dispatch, durable distributed receipts, cloud identity, physical deletion or real-model utility.

## 2\. Review method

1. Read the implementer's plan/hardening and claims, then independently inventory the actual changed files and relevant code paths. Use code/contracts/tests as authority over documents.
2. Challenge plan completeness and alternative architecture. Could the same usability goal be met with less new policy? Are critical operational risks omitted? Are features slipped in from MEM-3+, PI-8 or future reasoning work?
3. Reproduce positive/negative tests from a fresh install and verify artifacts outside the checkout. Trace real production composition where possible, not only fakes.
4. Add \*your own\* adversarial tests and failure injections; do not only rerun named P7-01–36 cases.
5. Inspect complete diff for regressions, accidental authority expansion, config drift, test weakening, hidden example/provider coupling and undeclared persistent state changes.
6. Assign reproducible severity-ranked findings with file:line/symbol, exploit/failure path, expected vs actual behavior, evidence, fix recommendation and acceptance test.
7. Verify rollback and unverified gates; issue an independent verdict. If material defects remain, produce a fully self-contained Codex remediation handoff ready for a separate fixing session (suggest GPT-6 Luna XHigh or Sol High depending complexity; do not require further prompting).

## 3\. Mandatory adversarial areas

### A. Core-only reproducibility

* Build core wheel and sdist offline; inspect manifest members/dependencies/entrypoints/hidden source paths. Physically remove reference packages. Confirm no eager/import-time examples, no transient source PYTHONPATH, no editable install or implicit provider key.
* Exercise actual FastAPI factory/lifespan, HTTP conversation/context/branch and disabled route. Check clean cold start, missing optional adapters, missing env/cache, read-only temp, locale, OS, Python 3.11/3.12 compatibility and cancellation cleanup.
* Check installer idempotency, injected bad package/version, stale build artifacts, network/DNS probes, subprocess/SDK bypass of a Python-only fence and native denial claims.

### B. External consumer and scope security

* Independently install Reading Logbook client+host in another environment and use only public versioned HTTP; no private imports or core patches.
* Forge owner, actor, app ID, workspace, issuer/audience, service identity, registration and source claims. Test nonmember, revoked/expired profile grants, historical/cached context, cross-app source access and detailed error/stream replay.
* Retry same key with same/different payload, cancel stream and simulate lost acknowledgment. Reject duplicate effect or disclosure, preserve original attempt identity.

### C. Cloud plan/apply boundary

* Inspect \*all\* mutating deployment entrypoints, child scripts and sourced files. A no-op/dry-run flag must not execute gcloud config changes, IAM/service enablement, image build, artifact push, API/worker deployment, policy modification or secret read.
* Inject invalid/missing project, region, secret reference/version, identity issuer, allowed origin, model profile, price/limit, IAM role, network policy and stale plan. Verify no operation occurs before comprehensive validation.
* Inspect least-privileged service accounts, public web/private API/worker ingress, forwarded identity, OIDC audience, workload identity, worker push auth, CORS, app/owner isolation, rate/concurrency and configured egress.
* Look for the Gemini defaults in deployment code diverging from PI-3 offline/neutral profiles, paid fallback when strict-free exhausts, feature flags enabled by install/config alone, and unsafe drift rollback.

### D. Budget, provider and diagnostics

* Verify enforcement at the \*physical\* send/admission seam, not just after usage. Inject concurrency, cross-worker/scope totals, unknown usage, 429, timeout, restart, clock reset, lost ack, SDK retry, provider outage, overlarge token request and cost cap.
* Prove no unexpected provider/search send, no paid fallback or duplicate ambiguous effect. Distinguish app budget from cloud/account billing hard caps; verify factual cost classification (actual vs estimated vs synthetic) and source rights.
* Seed prompt/secret/token/source text and identity canaries; search logs, error surfaces, plan JSON, traces, reports, screenshots, export, exception handling and CI artifacts. Confirm data minimization and redaction even on failed startup.

### E. Storage and lifecycle

* Review PG/pgvector, Dynamo, journal, receipts/tombstones, profile grants, backups, summaries/history/cache/export and artifacts. Audit retention/capacity limits, cross-worker monotonic source/send authority and original-key non-reuse.
* Revoke/delete a synthetic source and try prior history, summary, context preview, SSE/replay, provider-send admission, export and retrieval source views. Restore a stale isolated snapshot and verify old source/attempt state cannot be resurrected.
* Distinguish simulated anti-rollback from real database/device/cloud restore. Look for destructive cleanup commands that target shared volumes, personal data, cloud stores or unverified names; never execute them.
* Challenge the storage topology decision with empirical cost/correctness evidence. Absence of measured billing/native recovery is an open question, not a completed migration justification.

### F. Compatibility and evidence integrity

* Re-run PI-1 installed/core, PI-2 consumer, PI-3 provider-neutral, PI-4 sharing, PI-5 retrieval/context, PI-6 frozen evaluation, inherited provider-matrix/Phase35–36, planning, research, memory-control and offline backend as safe/available.
* Verify no historical fixture/lock bytes were rewritten, scores or thresholds weakened, tests skipped deceptively, API IDs/wire contracts/migrations changed without compatibility/rollback, or MEM-2 default-off flags promoted.
* Challenge sample size, p95/timing measurement, fake spend labels, binary hash/source identity and report/test consistency. Verify all claimed commands were actually executed on the final tested source; distinguish earlier failed iterations.

## 4\. P7-01–36 and roadmap gates

Independently evaluate every P7 scenario from the plan. Use PASS / FAIL / BLOCKED / NOT\_RUN with reproduction, evidence class and reason. Cross-map roadmap A01, A03–A07, A10, A15, A18, A20, A21; ensure A19 real quality and A22 independent full-platform audit remain separately gated.
Validate explicit independent states for:

* pi7\_offline\_operability
* pi7\_cloud\_preflight
* pi7\_hosted\_operations
* pi7\_native\_recovery\_deletion
* pi7\_release\_promotion
* inherited pi5\_completion, pi6\_offline\_evaluation and pi6\_production\_promotion

No positive offline result may silently close G2/G3, provider/physical-send, deployed IAM, distributed receipt, physical erasure, canonical external acceptance, MEM or PI-8 gates. If no proper cloud/provider authorization exists, preserve blocked\_unverified / no\_go and review the safe local implementation anyway.

## 5\. Suggested safe commands

Inspect their side effects and prerequisites first. Candidates: git status \--short; git diff \--check; make backend-lint; bash \-n infrastructure/gcp/deploy.sh; new make pi7-check, make pi7-local-smoke PI7_SMOKE_FLAGS=--require-native, make pi7-consumer-smoke PI7_SMOKE_FLAGS=--require-native, and make pi7-cloud-plan; make platform-independence-check; make pi2-check; make pi3-check; make pi4-check; make pi5-check; make pi6-check; make backend-test-offline; planning/retrieval/research/memory-control/knowledge-causal evaluations; focused deployment and PI-7 tests.
Where the environment lacks native fence/Docker/canonical macOS runtime, mark the exact unavailable check. Never substitute a fake CLI or Python network hook for OS-wide network or cloud proof.

## 6\. Required written output

Produce docs/platform-independence/pi-7-independent-review-YYYY-MM-DD.md containing:

1. Independent executive verdict: accept\_local, changes\_required or blocked\_unverified (separately for local, cloud-plan, hosted and native-recovery gates).
2. Findings ordered P0/P1/P2/P3. For each: concise title, affected file/symbol/line, evidence/reproducer, impact/security implications, expected/observed behavior, exact fix direction and regression test.
3. Completeness/architecture critique **beyond the plan**: missing scenarios, better alternatives and unjustified additions.
4. Commands and precise results, including initially failing iterations, toolchain, source/artifact hashes, test scope, redaction/cost/privacy evidence classes and all unreviewed areas.
5. P7-01–36 matrix and inherited open-gate ledger. No inferred cloud/provider/physical deletion acceptance.
6. API/package/fixture/lock/rollback compatibility assessment.
7. A self-contained remediation handoff if P0/P1/P2 changes are warranted: exact target SHA, files, test cases, constraints, ordering, stop conditions, expected outputs and later verification process.

Do **not** quietly fix defects, issue a passing verdict based on the implementer report, or turn PI-8 into a checklist auto-completion. End with one unambiguous recommendation on whether PI-7 local scope can be accepted and what blocks anything further.

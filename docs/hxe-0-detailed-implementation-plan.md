# HXE-0 Detailed Implementation Plan

Version 1.0 — 2026-11-03 — Proposed development scope, not production authorization  
Repository: https\://github.com/jasonkli21/personal-ai-system  
Pinned baseline: b61d69890255ca3de736e7236581cee559358f32  
Roadmap: /Users/jasonkli/projects/personal-ai-system/docs/personal-ai-system-integrated-roadmap-11-03.md  
Execution: Sol Medium (in-session plan review and hardening; no subagents). Independent review: Sol High. Review remediation and final verification: Luna High/XHigh. No further review after Luna fixes.

## Executive objective

Deliver a minimal, independently consumable, free-first AI platform vertical slice: truthful capability ownership and evidence, a stable provisional developer API surface, one maintained Python SDK, a new unrelated app, synthetic provider/source/tool/memory canaries, and credential-free developer diagnostics. Reuse existing canonical runtime and authority boundaries. This phase does not deliver general MCP, local-model production integration, autonomous execution, broad memory research, real provider certification or cloud deployment.

The integrated roadmap tracks 20 historical phase IDs (HXE-0–5, MEM-0–7, RE-0–5), but MEM-0–2 already have scoped/default-off implementations; approximately 17 phases require substantive new work. Do not reimplement MEM-0–2. MEM-3+ remains frozen and is not authorized by HXE-0.

## Baseline and sources

At the pinned commit, the Apache-2.0 license, OSS README, CONTRIBUTING, SECURITY, AI documentation routing and broad maintainability cleanup are already completed. PI-0–8 have local implementation and remediation candidates, with independent acceptance still pending and production NO\_GO. PI-5 external-source authority, physical send/revocation atomicity, durable original-intent/revocation after restore, real provider accounting and native/cloud deletion/recovery remain capability-specific before-enablement gates. No global hard blocker prevents offline HXE-0 work.

Start by reading root AGENTS.md, docs/README.md, docs/current-state.md, docs/architecture.md and the cross-phase gate registry; then only task-relevant source/tests. Source code and executable contracts outrank historical plans.

Critical references:

* docs/platform-independence/consumer-v1.md and consumer-v1.openapi.json, backend/src/personal\_ai/api/consumer\_contract.py, backend/scripts/pi2\_contract.py.  
* backend/src/personal\_ai/extensions/v1.py; examples/reading-logbook/README.md and its separately packaged client/host.  
* backend/src/personal\_ai/auth, context, llm, retrieval, memory and services/external\_turns owner contracts; backend/src/personal\_ai/contracts/execution.py.  
* docs/platform-independence/pi-6-benchmark-contract.md, frozen context planning-baseline-v26/v27 and relevant evaluator source-identity code.  
* docs/quality/repo-quality-review-2026-11-03.md and backend/pyproject.toml for the PI-6 source digest conflict.  
* docs/platform-independence/pi-8-readiness-assessment.md, pi-cross-phase-gate-registry.md and existing verification reports.

## Architecture invariants

* Identity, actor, application, workspace and purpose derive from verified server authority (RequestScope/AuthenticatedPrincipal), not from client headers, extension manifests or same-owner assumptions.  
* One source-permission/provenance and revocation model, context assembler, provider physical-attempt/accounting path, memory lifecycle, and canonical run/intent/attempt state machine. HXE-0 may document future ownership but must not create a duplicate engine.  
* Versioned HTTP consumer subset v1.2.0 is the existing public starting point. The entire FastAPI /openapi.json and trusted personal\_ai.extensions.v1 host metadata are not public client APIs.  
* A capability manifest is descriptive; it cannot grant access. Every read, model send, retry, retained history/export and memory use must honor current rights.  
* Define future atomic issuer-bound revoke-versus-physical-send and independently monotonic original-key/forget authority now, but do not claim production proof without native issuer/restore canaries.  
* No new paid calls, secrets, live personal data, cloud writes, broad network egress, mutating agent tools, automatic memory capture, or silent defaults change.

## Work package 1 — Evidence reconciliation and phase accounting

Create a compact capability matrix under docs/harness-excellence (or an established equivalent location): capability, owner, versioned public seam, enablement/default, E0–E5 evidence tier, threat, test command, inherited gate and future phase owner. Include SDK/HTTP, trusted host extensions, providers/P19, source retrieval/tools, governed memory, run/attempt, source authority, packaging and operator preflight.

Refresh docs/current-state.md and relevant documentation links against the checked-out SHA. Keep historical PI audit ledgers immutable. Mark MEM-0–2 as implemented scoped/default-off with unresolved acceptance, not three unstarted development phases. Preserve MEM-3+ freeze, PI production NO\_GO and all before-enablement restrictions.

Acceptance: an unfamiliar developer can find each public boundary, supported operation, denial reason, verification command and release restriction without loading the whole repo or mistaking synthetic tests for native acceptance.

## Work package 2 — PI-6 frozen source-identity conflict

The completed OSS cleanup added license metadata to backend/pyproject.toml. This changed a source digest in a frozen PI-6 evaluation/packaging identity and caused one broad offline-suite failure. Reproduce the precise assertion and trace source manifest generation and verification. Introduce an explicit additive current-source generation/identity (the next valid version, if supported) while preserving v26/v27 original digests and bytes, old corpora, thresholds, scoring code, recorded failures and historical reports. Do not remove license metadata, weaken a test, rewrite a lock or pretend an old digest still matches.

Acceptance: preserved old identities verified unchanged; current source identity explicit; relevant checks pass. If correct migration is blocked, document exact root cause and keep the full HXE-0 exit gate BLOCKED rather than inventing a pass.

## Work package 3 — Canonical ownership ADR and small public contract

Write one concise ADR, splitting only if necessary, that decides:

* RequestScope/AuthenticatedPrincipal ownership, app/workspace/actor and protected identity binding.  
* Generated external OpenAPI subset, version/capability negotiation, typed errors, migration compatibility and stable-versus-provisional publication.  
* Source/provenance envelope, owner/purpose/source revision/expiry/grant dependency and retained-output recheck/withdrawal.  
* Provider operation categories and canonical P19 physical-send admission/accounting, including ancillary operations and strict-free failure.  
* One future RE-2/HXE-3 run/step/intent/attempt lifecycle, event ordering, idempotency/retry/cancel, unknown remote outcomes, reconciliation and recovery.  
* Atomic send/revoke and monotonic original intent/forget/tombstone across restore as before-enablement architectural requirements.

Reuse existing v1.2.0 consumer contract and its generated OpenAPI. Add the smallest additive endpoint/metadata for capability negotiation only if no current public mechanism suffices. Do not expose first-party memory/account/admin/external-turn routes or add a second persistence/permission framework.

Acceptance: every cross-cutting concern has one explicit authoritative owner and forward-compatible contract; no new capability silently assumes deployment authorization.

## Work package 4 — One standalone Python SDK

Prefer Python first because the independent Reading Logbook client already supplies a tested dependency-free transport/SSE pattern. Create a separately built wheel/sdist in a discoverable sdk/python or equivalent layout, with no runtime imports of personal\_ai, server implementation, sample apps or reference-apps. Extract/reuse transport and parsers when safe; avoid duplicated divergent code.

Minimum typed client:

* Constructor with caller-provided Google user ID token, base URL, application ID, optional workspace ID, bounded timeouts and redacted diagnostics. No token minting, authz grant or secret logging.  
* Create/list/detail conversations, context preview, continuation SSE and canonical status lookup; read-only retrieval/tool only if already in supported external subset and authorized.  
* Public contract/version/capability mismatch and unavailable operations reported explicitly, not treated as permissions.  
* Stable caller-journaled UUID original idempotency keys; retries use original complete request. No replacement-key retry after uncertainty or duplicate physical send.  
* Bounded SSE parsing of UTF-8 fragments, CRLF, invalid/oversize frames, provisional deltas, incomplete EOF, duplicate/mismatched terminal frames, 200-with-disconnect and status reconciliation. No Last-Event-ID resume or server-cancel guarantee.  
* Typed safe 400/401/403/404/408/409/413/422/429/503 and transport-unknown errors.

Acceptance: clean external interpreter installs SDK wheel/sdist with backend/reference modules physically absent and PYTHONPATH clear; contract/SSE/idempotency/error and denied-client tests pass. Keep stable-publication claim provisional until independent installed acceptance.

## Work package 5 — New unrelated application and four canaries

Build a tiny 'Project Checklist' independent app (or similarly narrow justified choice) with its own checklist records and SQLite/local operation journal. Client uses SDK over HTTP only; optional trusted host uses only personal\_ai.extensions.v1 and explicit operator selection. No changes to generic core business logic or implicit grants. Reading Logbook is a regression control, not the sole independent-app proof.

Canary A — unrelated app: separate package/process; synthetic verified Google-style ID token with exact aud/azp, app/workspace policy; create/list/detail/preview/continue/status; wrong client and no-source denials.

Canary B — second synthetic provider adapter/profile through the PI-3 provider-neutral seam. Prove capability selection, strict-free denial, bounded physical-attempt accounting or explicit unavailable result. No real provider account or paid fallback.

Canary C — one deterministic local read-only source/tool using the PI-5 immutable registry and provenance/source-rights envelope. Deny wrong owner/client/workspace/purpose, revoked or expired grant, stale revision and ambiguous effects; treat tool output as untrusted content. No general tool loop.

Canary D — governed MEM-1/2 consumer with default-off/opt-in authorization and project/source/actor checks, plus safe unavailable behavior without production issuer. No new automatic admission, host registration, memory sharing or MEM-3 work.

Consolidate repeated assertions in a small conformance matrix rather than growing large overlapping suites. Test negative paths and retained output, not only a successful fake response.

## Work package 6 — Developer docs, diagnostics and tests

Create a credential-free quickstart, installation and version matrix, SDK examples, operator app/client registration placeholders, minimal provider/source/tool scaffold, read-only capability/preflight diagnostics and redacted sample trace. Extend existing diagnostics if simpler. Keep the root README focused on product/setup/architecture, without phase reports. Reuse already-delivered license/contributor/security docs.

Focused verification:

* Generated consumer-v1 OpenAPI drift, SDK serializers/errors/stream parser, original-key duplicate prevention and status reconciliation.  
* Separately installed wheel/sdist with reference packages absent and no private imports.  
* Wrong Google aud/azp, owner/actor/workspace/app and client-selected source; expired/revoked/stale permissions; source-derived retained history/export quarantine.  
* Synthetic provider strict-free limits, read-only tool effects, MEM default-off, provenance/revocation and redacted diagnostics.  
* Reading Logbook regression and targeted PI-5/PI-6 contracts.

Use actual Makefile targets and report exact environments:

* git diff \--check; backend/.venv/bin/python backend/scripts/pi2\_contract.py \--check.  
* backend/.venv/bin/python \-m pytest \-q backend/tests/test\_openapi.py plus focused new tests; backend/.venv/bin/ruff check backend where available.  
* make pi2-build and installed client tests with offline caches and clean interpreter.  
* make pi2-check only where its loopback/native prerequisites are met; make pi6-check ONLY under its native macOS or approved equivalent egress fence.  
* Bounded broader offline regression and PI-6 historical/source-identity integrity verification.

E0 static, E1 hermetic synthetic, E2 separate install/native, E3 approved real providers/sources, E4 deployed recovery/deletion/cost, E5 longitudinal real utility. Explicitly record PASS/FAIL/SKIP/BLOCKED per tier; Python-only deny-network is not native egress proof. No real credentials/cloud calls just to turn a check green.

## Exit criteria, rollback and exclusions

E1 development candidate must have truthful inventory/ADR, preserved PI-6 provenance, generated bounded API/SDK, independently packaged new app, synthetic provider/source/tool/memory canaries, negative security and idempotency/SSE tests, documentation and exact evidence receipts. If PI-6 identity or core conformance is blocked, label the candidate partial and do not claim completed HXE-0.

Installed developer-preview acceptance additionally requires fresh clean external consumer/install, origin-pinned dependencies where applicable, appropriate native egress evidence and independent review. Real provider/source rights, atomic send/revoke, monotonic restore, deployed identity, cloud billing/recovery and physical erasure remain BEFORE\_ENABLEMENT gates. Production remains NO\_GO.

Exclude HXE-1 MCP/ingestion breadth, HXE-2 local provider/real-model evaluation, HXE-3 autonomous tools/background, HXE-4 memory portability UX, HXE-5 release/ecosystem, RE strategies, MEM-3+, AG-UI/A2A/multimodal and broad scheduler.

Every new SDK/app/adapter is opt-in and disableable without changing canonical user records, idempotency/forget receipts, provenance, source permission epochs, migrations or default-off controls. No destructive persistence refactor.

## Execution and review handoff

Sol Medium first critiques/hardens this plan in the SAME session before coding, records rationale, then implements/tests/self-reviews without subagents. Deliver a dated implementation report, changed-file list, base/head SHA, exact checks/counts/tier, contract migration, remaining gates and rollback. Commit locally when authorized; no force-push or unrequested publication.

Then ONE independent Sol High review against exact implementation SHA; reviewer outputs ONE fully self-contained Luna High/XHigh remediation handoff with ranked findings and final verification. Luna fixes findings and runs final verification. The user explicitly requires NO independent post-Luna review. Residual unresolved P0/P1 or external production gates remain BLOCKED, not waived.  

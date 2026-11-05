# HXE-5 implementation plan — operational release and independent adoption

Status: implementation handoff; not a production approval. Prepared 2026-11-03 (America/Los\_Angeles).  
Repository: https\://github.com/jasonkli21/personal-ai-system  
Inspected baseline: main at 60bcacb6cac1a252ecb2001b9324eab9dfd198c3 (owner profile portability review fixes). Before editing, resolve and record the actual HEAD and tree; if newer, inspect the delta and harden this plan against it.  
Work allocation: Sol Medium implementation, Sol High independent post-implementation review, Luna High/XHigh remediation and final verification. No further independent review after Luna.  
Planning source: docs/personal-ai-system-integrated-roadmap-11-03.md, “HXE-5 — Operational release, independent adoption and optional ecosystem”; controlling evidence: docs/current-state.md, docs/platform-independence/pi-cross-phase-gate-registry.md and executable source/tests.

# 1\. Decision and scope

Deliver a narrowly scoped, auditable open-source developer-preview candidate that another developer can install without example applications, exercise through the public SDK/API and evaluate under finite cost and resource bounds. Separate building this evidence machinery from authorizing a preview or production deployment. A release decision of NO\_GO or BLOCKED is a valid implementation outcome when the evidence is unavailable.

P0 — required: capability/profile matrix; pinned dependency-origin and independently installed consumer path; reproducible build and compatibility evidence; redacted diagnostics and resource measurements; deterministic release gate and review-ready evidence; user-facing operator instructions and known limits.

P1 — conditional, only after P0 is coherent: bounded native local E2 run with a real pinned model and authorized read-only source, on an operator-approved isolated host; safe restore/rollback drills where the required trusted environment is available. Missing E2 does not justify inventing evidence or broadening permissions.

P2 — optional and default-off: one low-sensitivity OpenClaw interoperability canary and, if still valuable, a generic OpenCode MCP-consumer canary. Validate current official peer interface/version when implementing; do not build a separate coding agent, shell, editor, patch engine, connector platform or messaging orchestration. AG-UI, A2A, multimodal, sync and second-language SDK remain deferred unless separately authorized.

Not in scope: reimplementing MEM-0–2, unfreezing MEM-3+, implementing RE strategy/adaptation, enabling mutating tools/background effects/cloud deployment, installing unknown third-party plug-ins, paid hosted inference, live private data, production migration or destructive data lifecycle changes.

# 2\. Repository-specific starting point

The README/Apache-2.0/CONTRIBUTING/SECURITY foundation already exists. The Python SDK is provisional personal-ai-sdk 0.1.0 against consumer contract v1.2.0. The Project Checklist and Reading Logbook canaries exist; the MCP source adapter is a default-off synthetic read-only pilot; local llama.cpp inference is a development-only Unix-socket candidate with no hardware-verified E2 utility acceptance; the workflow runner and memory portability controls remain default-off with inherited security/restore gates.

Relevant existing seams:

* Makefile: sdk-build, sdk-check, sdk-install-check, consumer-contract-check, mcp-adapter-check, operations-check, offline-benchmark-check, real-task-eval, naming-policy-check, release-evidence-check.  
* backend/scripts/installed\_core\_smoke.py and sdk\_install\_smoke.py: install/operability checks, but prepared environments and installed RECORD hashes do not establish independent origin of a wheelhouse.  
* backend/scripts/release\_evidence\_check.py: guards frozen PI-8 historical ledger, exact independently supplied SHA and clean checkout; its author-reported receipts intentionally cannot grant acceptance. Extend or compose it, never replace its frozen meaning.  
* docs/platform-independence/pi-7-operations-runbook.md, pi-7-data-lifecycle-runbook.md and pi-8-readiness-assessment.md: distinct native fence, disposable stores, cloud proposal and restore/erasure boundaries.  
* docs/harness-excellence/README.md, docs/memory/owner-portability.md, adapters/mcp\_source/README.md and sdk/python/README.md: current public/default-off contract.  
* docs/naming-exceptions.md and backend/scripts/naming\_policy\_check.py: narrow frozen naming exceptions.

Source code, tests, scripts, new active filenames, public commands, runtime identifiers, current README and user-visible strings must use durable capability names, never “HXE-5” or other phase shorthand. Phase IDs are allowed in this plan and dated historical evidence only. Do not rename persisted/immutable identities merely to remove phase labels; document a narrowly justified compatibility exception instead. A future additive evaluator source identity may be required for modified runtime/test inputs: preserve every frozen PI-6 lock, fixture, digest, scorer, threshold and historical non-promotion result.

# 3\. Evidence and release profiles

Use one machine-readable profile manifest consumed by a deterministic validator and human-readable scorecard. Keep source evidence separate from claims and never allow the subject implementation to certify itself as independently accepted.

Evidence tiers:

* E0: code/manifest/static policy checks.  
* E1: hermetic fakes, source-free client and synthetic conformance.  
* E2: clean independent native/local install, real local model and native fences/stores when claimed.  
* E3: expressly approved live external provider/source/peer accounts.  
* E4: deployed IAM/network/billing, mixed-age restore, anti-rollback, physical deletion and operator drills.  
* E5: longitudinal task utility, matched-cost human-evaluated results.

Proposed durable profile names (final spelling after hardening):

* offline\_development: E0/E1, synthetic data only, development use; cannot be marketed as an independently accepted preview.  
* local\_developer\_preview: needs source-free clean install, trusted input provenance, native egress fence, signed independently registered HTTP consumer, controlled read-only source/tool, real useful E2 local task, measured setup/latency/idle resources and independent skeptical signoff. No cloud/paid/private-data assertion.  
* hosted\_opt\_in: separate E3 issuer/account/privacy/operation-specific strict-free or explicitly approved spending/counter evidence; never inherited from local status.  
* cloud\_operator: separate E4 identity/IAM/network/backup/restore/erasure/billing proof; default withheld.

An optional peer compatibility result is not a license to share private memory and never upgrades the profile above its weakest controlling gate.

Require explicit per-capability defaults, enabled/disallowed modes, authority owner, contract version, code/test refs, source revision, required tier, observed tier, exact command, receipt digest and decision reason. States should include PASS, FAIL, BLOCKED, NOT\_RUN and NOT\_APPLICABLE, with no “pass” from skipping. Profile verdicts should be derived monotonically: any mandatory failing or blocked gate precludes GO, unknown cannot be converted to success, and a child profile cannot inherit an unverified parent assumption.

# 4\. Architecture and implementation slices

## Slice A — current-state inventory and profile contract

1. Read AGENTS.md, docs/README.md, the two current gate registries, public API/SDK contracts, relevant operational code/tests and current-state. Inspect git status, current HEAD/tree, recent HXE-4 delta and target paths before editing. Preserve user changes.  
2. Create a compact profile schema and pure validator near existing release/evidence modules. Prefer a single canonical release evidence store and an additive profile projection over a second attempt, source, memory or grant ledger. Version the schema; unknown profile, capability, evidence tier, source digest, field or status fails closed. Require exact reviewed commit/tree and evidence whose provenance is declared. Detect duplicate IDs, path traversal, stale source identity, unsupported combination and altered manifest after review. Evidence output must be content-free/redacted and deterministic.  
3. Retain independent-review and operator signoff as external inputs, never values synthesized by the test runner. The validator may output “candidate” evidence without claiming a signed GO decision. Treat reviewer status unknown until a separate session supplies an exact target revision and observations.  
4. Add narrow migration/version-compatibility rules for the Python SDK and public consumer contract: supported version range and an explicit breaking-change policy, tested cross-version parse/error behavior, no hidden example imports. Do not silently mark provisional v1.2.0 stable.

## Slice B — build origin and truly independent installation

1. Inventory package graph (backend, Python SDK, optional MCP adapter, independent host/client, frontend only if claimed). Reuse existing packaging and Apache notices. Produce an artifact index with package names, versions, source commit/tree, trusted externally supplied input digest, resolved dependency hash, wheel/sdist digests, license metadata, build environment and toolchain identity. Verify NOTICE/license and dependency disclosures; flag ambiguous license/origin for review rather than inventing compliance.  
2. Build twice in disposable isolated directories with a documented fixed input set; compare byte-for-byte when achievable, otherwise report exactly which nondeterministic fields differ. Use a source-date policy if appropriate without rewriting archive history. Strictly separate reproducible output from trusted input origin.  
3. Add an operator-supplied, out-of-band pin manifest for a no-index, no-deps or hash-locked clean installation on the supported platform. Never bootstrap trust from the just-built artifact’s own RECORD. Disallow network, ambient credentials, editable installs, source checkout imports, unsigned/unpinned wheel substitutions, .pth/startup hooks and undisclosed extras; verify the target runtime import origins. On unsupported OS/native sandbox, report BLOCKED. No broad unfenced fallback can count as acceptance.  
4. Exercise a generated or separately packaged unrelated client from outside the repository against the documented public contract. Require exact issuer-bound identity/workspace/application, typed SDK errors, same original idempotency key/uncertainty and safe status reconciliation. Any public seam added must be versioned and tested from the independent package.

## Slice C — capability, safety and resource canary

1. E1: a credential-free local sample uses only synthetic opted-in read-only source, one provider-neutral fake, and the same canonical context, provider admission, source-rights, P19 attempt and memory authority paths. Include normal completion, cancellation, replay and withholding on revoked/expired/wrong recipient/source revision.  
2. E2 only with independently authorized native prerequisites: pin local llama.cpp build/GGUF hash and physical resource envelope, use the existing exact token/count and usage path, conduct at least one genuinely useful source-attributed task with an explicit rubric. Record task output/rubric/latency, RAM/idle CPU, cold start, setup steps, token/call usage, trace/denial counts and operator hardware. Use matched baseline or clearly label a single task as anecdotal; do not claim general reasoning or memory gains. If the environment cannot do this, leave E2 BLOCKED with exact prerequisites.  
3. Hosted use remains blocked absent account-specific rights/privacy/strict-free proof and before-send admission; no automatic paid fallback. Mutating tools and external memory exports stay off. An MCP reply to an external harness is an actual disclosure: outbound consent, purpose, recipient, source revision, sensitivity and payload minimization must be rechecked. Do not claim downstream memory deletion/revocation or strict-free policy after bytes leave PAS.  
4. Bounded stress/negative set: request/body/event caps, timeout/cancel, concurrency/reservations, error redaction, unavailable provider, network denial, source revoke between prepare/send, stale derived output, poisoned MCP text, restart/uncertain effect. Fail closed if source/issuer or physical send authority is unavailable; do not counterfeit distributed atomicity.

## Slice D — operator experience and release evidence

1. Provide one stable preflight command and machine-readable redacted report. It describes a topology and its missing prerequisites without contacting providers or launching cloud workloads. Make exit status reflect actual readiness and distinguish blocked prerequisites from product regressions.  
2. Add narrow, opt-in measurement command(s) using explicit caps and disposable state; no secrets, personal payloads or hidden chain-of-thought in logs. Capture revisions, prerequisites, test argv, wall/CPU/RAM/idle, startup time, resource use, errors and artifact hashes. Skip metrics that cannot be measured faithfully.  
3. Maintain a static feature/default-off matrix and scorecard derived from the manifest; link a reproducible quickstart, rollback, independent upgrade/compatibility policy, known limitations, source/SDK support window, release notes and bounded remediation queue.  
4. Do not automatically publish PyPI, GitHub releases, cloud images, package registries or sign a release. Produce a release candidate and a GO/NO-GO recommendation only. The independent reviewer owns signoff; operator owns any final public release.

## Slice E — optional ecosystem canary

If P0 is green and time remains, test one publicly documented OpenClaw read-only integration under a pinned peer version using entirely synthetic non-sensitive material, explicit recipient/purpose/disclosure consent, no private corpus, no automatic send and a kill switch. Revalidate official peer contract; a generic MCP-client route is preferred if supported. Compare benefit versus a plain MCP consumer and record why it is worth maintaining. An OpenCode generic MCP or plugin canary is likewise secondary. Treat AG-UI/A2A and multimodal as explicit future decisions, not new dependencies. A failed/unsupported peer canary blocks only its own optional feature, never core local preview.

# 5\. Acceptance cases

Each case needs a positive, at least one negative, exact command and evidence tier; mark unrun honestly.

A01: canonical profile inventory maps actual defaults, owners, contracts and inherited gates with no invented promotion.  
A02: manifest schema rejects duplicate/unknown/ambiguous/mismatched/tampered evidence, stale commit/tree, unsupported tier and self-supplied review signoff.  
A03: deterministic E1 release report and redacted safe errors; repeated runs yield stable verdicts without hard-coded fixture success.  
A04: two builds from pinned inputs produce a documented reproducibility result; archived metadata and trusted origin are separately assessed.  
A05: independently supplied dependency hashes and clean isolated no-index install; tampered wheel, startup hook, source import and optional-package absence fail as expected.  
A06: unrelated app \+ separately installed Python SDK operate only through public contracts; auth, workspace, wrong-client, typed error and original-key replay negatives pass.  
A07: read-only source/tool and provider tests cover current permission, prompt injection, revocation, stale revision and source-to-model disclosure; zero unapproved physical sends observed under an actual effective fence.  
A08: resource caps, failure reporting, cancellation and uncertain restart evidence remain bounded; no duplicate irreversible attempt.  
A09: exact feature matrix and strict-free policy deny unknown/paid/hosted paths, including ancillary count and retry.  
A10: E2 real local useful task, independently approved model and native fences, explicit hardware/resource observations, or BLOCKED with precise missing prerequisites.  
A11: E3/E4 deployed account, storage, physical erasure/restore and billing profiles remain NO\_GO without independent evidence.  
A12: optional external-harness canary proves consent minimization, revocation-before-send and source provenance, or is deferred/default-off without degrading the required path.  
A13: naming-policy, historical evaluation identity, API/SDK compatibility and no-example installation checks pass; historical frozen receipts remain byte-identical.  
A14: exact-commit independent review can distinguish implementer receipts, review observations and production decision; output contains rollback/known limitations.

# 6\. Verification and evidence collection

First run focused tests for each changed contract, then fixed safety smoke. Expected existing commands, subject to current Makefile:

* make naming-policy-check  
* make backend-lint  
* make sdk-check  
* make sdk-build && make sdk-install-check  
* make consumer-contract-check  
* make mcp-adapter-check (only in its prepared optional environment)  
* make operations-check  
* make offline-benchmark-check  
* make planning-eval  
* make memory-control-eval  
* make backend-test-offline, with all environmental failures retained and classified  
* make frontend-typecheck, frontend-lint, frontend-test, frontend-build only if affected  
* after a clean exact commit: RELEASE\_EVIDENCE\_EXPECTED\_COMMIT=\<full-reviewed-sha\> make release-evidence-check

The implementation may add descriptive, phase-neutral Make targets and scoped tests. Distinguish not run, sandbox blocked, product failure, and independently reproduced evidence. Do not change historical verification statuses, planning locks, frozen corpus/scoring or source generations in place to make checks green. If the new code changes a frozen evaluator input, create a new additive generation/lock through existing mechanism with predecessor identity retained.

# 7\. Security and authority gates

Never treat a signed manifest as user authorization; never infer trusted origin from self-generated hashes, install RECORD or declared versions. No live provider account, external source, paid spend, cloud deployment, public publication, real personal data, destructive restore/erasure or mutating workflow without explicit operator authority and independently evidenced prerequisites. Exact attempt/reservation/physical send and send-vs-revoke ordering remain canonical. No new source, grant, task, memory, provider or attempt ledger. External recipient retention is outside managed recall after disclosure.

Any unresolved P0 authority/billing/privacy defect: release verdict NO\_GO. Unavailable native sandbox, model, trusted wheelhouse, independent host, Docker or external credentials: BLOCKED, not a softened acceptance test. Preserve rollback paths, original-key receipts, source/memory revocation and deletion fences; never reset production state.

# 8\. Deliverables and final handoff

Expected capability-named artifacts, adjusted to inspected repo conventions:

* a versioned profile schema/validator and tests;  
* reproducibility/origin manifest generator/inspector and isolated installer canary;  
* independent source-free consumer and safety tests;  
* redacted preflight/measurement and reporter;  
* docs/operations/developer-preview.md or analogous operator page, plus current-state, gate registry, docs router and relevant module READMEs;  
* one dated historical implementation/hardening report with exact SHA/tree, changed source/contract inventory, test commands/receipts, E0–E5 ledger, capability/default-off matrix, unanswered prerequisites, compatibility, rollback and decision.

Acceptance for implementation handoff is coherent P0 machinery and honest evidence, not automatic developer-preview GO. Independent Sol High review follows at the exact implementation commit; Luna High/XHigh then fixes all review findings and independently re-runs the final bounded verification within that one remediation session. There is no further reviewer pass after Luna.  

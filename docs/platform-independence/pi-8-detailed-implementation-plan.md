# PI-8 Detailed Implementation Plan — Independent Platform Readiness Audit

Date: 2026-11-03 (America/Los\_Angeles)  
Repository: [https\://github.com/jasonkli21/personal-ai-system](https://github.com/jasonkli21/personal-ai-system)  
Planning baseline: main at 9b4b0f4db358ac97c156a615831dbb81a0a636a9 (PI-7 independent-review remediation).  
Authority: repository code and executable contracts \> dated verification/review evidence \> accepted ADRs \> architecture charter \> phase plans. Refresh the checkout and HEAD in the execution session; never silently assume the baseline is unchanged.  
Phase status: proposed PI-8 plan; no PI-8 implementation, independent acceptance, deployment, or production approval is claimed.  
Recommended execution: GPT-6.1 Sol, High reasoning. Independent post-implementation review: a fresh GPT-6.1 Sol, High session.

## 1\. Decision: PI-8 is an audit and release-gating phase

The platform-independence roadmap explicitly defines PI-8 as an independent platform readiness audit, not another major feature phase. PI-8 implementation should build reproducible evidence, perform skeptical integrated tests and threat-model analysis, classify gaps, and publish an accurate readiness/rollback decision. It must not silently turn blocked production features on or build a new generalized agent platform.

The implementation session performs a mandatory internal plan critique, hardens this plan, then implements bounded audit machinery and gathers what evidence is permitted. That same-session work is not an independent audit. A separate fresh reviewer evaluates the actual diff, test execution, sources and release conclusions. A PI-8 PASS is not synonymous with authorization to deploy or process private data; gate-by-gate evidence controls those capabilities.

## 2\. Mission and success conditions

Demonstrate, to the extent legally and technically possible, that the standalone core can be installed without Travel/Shopping/Health/Finance reference packages, support a separately built unrelated application through versioned public contracts, use a provider-neutral free-first route and permitted search/retrieval, enforce owner/actor/app/workspace/source grants on profile and memory, account for attempts and costs, and refuse unsafe replay, stale restore, cross-actor access or unauthorized send.

Success is a reviewable, machine-checkable matrix of every roadmap A01–A22 case, explicit reproduction steps and provenance, identified P0/P1/P2/P3 findings, disposition owners, release profile decisions, and clear remaining gates. The audit must also look beyond the planned checklist for unexpected architectural and safety gaps. Evidence availability is an outcome, not a reason to invent PASS.

## 3\. Source baseline and inherited gates

Read AGENTS.md, docs/README.md, docs/current-state.md, docs/platform-independence/README.md and platform-independence-roadmap.md first. Inspect the actual code, migrations, Makefile and focused tests before relying on the reports.

At the planning baseline:

* PI-7 implementation: 5c7e377827572a4e7770c10fd9bd91e71a7851b4, with review remediation 9b4b0f4db358ac97c156a615831dbb81a0a636a9. The remediation is implementer follow-up, not independent closure.  
* PI-7 local operability: candidate; native egress-fenced installed smoke blocked in the managed environment. Prepared installed dependency RECORD checking is not a clean independent wheelhouse provenance chain.  
* PI-7 disposable PostgreSQL/DynamoDB operations: Docker native checks not reproduced. Fake Docker checks, internal-network syntax and image-ID preflight are not daemon-level evidence.  
* PI-7 cloud plan: static\_policy\_validated\_only; live IAM, image, audience, network, storage, billing and operator approvals unverified. Apply is intentionally refused.  
* PI-7 hosted operations, physical deletion, anti-rollback recovery, live provider/account spend: blocked\_unverified; release promotion no\_go.  
* PI-5: blocked\_unverified for trusted monotonic source/revision/rights authority, atomic send permits, original-key durable receipts, live provider/identity/network, canonical native/restore and other recorded F01–F03 requirements. Read pi-5-completion-gate.md.  
* PI-6: synthetic offline evaluation locally\_complete; live-model utility and production promotion no\_go. No benchmark profile auto-promotion.  
* PI-0–4: distinguish local review/remediation candidates from formal independent acceptance. Do not retroactively convert reports into accepted gates.  
* MEM-2 remains default-off with inherited safety, host, issuer and storage-capacity limitations; MEM-3+ frozen. Do not implement MEM-3+, relax grant scopes, or enable any experimental feature.  
* Historical untracked inputs or user modifications at execution must be inventoried and preserved. The planning baseline is not proof the future worktree is clean.

## 4\. Operating constraints and evidence taxonomy

Offline-first and free-first: do not download dependencies, launch networked services, use private credentials, contact model/search providers, deploy, mutate live stores, restore personal data, delete real data, or incur costs without explicit, exact authorization. Use synthetic identities/data with canaries, bounded resources and an audited native deny-egress fence where possible. An environment rejecting an OS fence must produce BLOCKED, not a degraded acceptance PASS.

Use evidence classes: static\_inspection; deterministic\_synthetic; installed\_hermetic; native\_store; operator\_authorized\_live; independently\_reproduced. A command result may have several classes; the claimed gate can use only sufficiently strong classes. Separate observed denial from inferred denial, expected refusal from successful end-to-end behavior, tested bytes from repo HEAD and historical evidence from newly run evidence. Include executor OS, Python, uv, dependency lock, source SHA and dirty state.

Each case disposition is PASS, FAIL, BLOCKED, NOT\_RUN, or NOT\_APPLICABLE with reason. A PASS must include command/artifact, assertion and observed result. A BLOCKED must name missing authority, environment or predecessor proof. NOT\_APPLICABLE requires a justified scope decision. Refusal cannot be relabeled success for a positive usability case.

## 5\. Workstream W0 — Pre-code audit design and plan hardening

1. Record git status \--short, HEAD, upstream/base, tracked/untracked paths, SHA-256 of any supplied plan/prompt, and the source/fixture revision; identify all actual repository instructions.  
2. Build an evidence inventory from the PI-0–7 reports and dated follow-up, and reconcile every contradictory status with code and current-state.  
3. Write docs/platform-independence/pi-8-plan-hardening.md BEFORE changing audit/test code. Challenge the plan for blind spots, false assumptions, hidden coupling, unsafe commands, missing native/live gates, evidence fabrication risk, and scope creep. State accepted changes, rejected alternatives and a frozen acceptance matrix.  
4. Produce a threat model: trust boundaries across consumer/issuer, app/workspace/actor, model/search providers, cache and source rights, memory grants, P19 quota/attempt, two stores, backups, hosted IAM and exporter/log sinks.  
5. Set predeclared case expectations, environment requirements and evidence thresholds. Risky paths require default-off, explicit approval and rollback.

Exit: the hardened plan can be executed without inventing parameters or promoting earlier gates.

## 6\. Workstream W1 — Executable audit contract and provenance ledger

Implement a modest PI-8 audit runner under backend/scripts or an equivalent existing scripts location, plus backend/tests/test\_pi8\_\*.py and make pi8-check. Reuse existing tests and scripts rather than copying major business logic.

The runner should:

* Pin checkout and executable/fixture versions in a machine-readable JSON report, record exact commands, exit code, timeout, duration, isolation, egress fence, skipped reason and no-secret output allowlist.  
* Run focused deterministic checks with no provider/cloud/data side effects by default. Higher-trust native/live cases require a separate flag and operator plan, and must remain disabled in ordinary make pi8-check.  
* Associate each P8 scenario with roadmap A01–A22, upstream P5/P6/P7 cases and a required evidence level; reject missing IDs, duplicate IDs, bad status/evidence combinations, mismatched source revision or fabricated zero-cost assertions.  
* Record negative tests and counterexamples, not just positive checks. Use explicit fail-closed command timeouts and output caps. Redact and scan artifacts for secrets, private prompts, canary values and unauthorized source snippets.  
* Preserve original historical receipts and evaluation fixtures; add audit artifacts without rewriting prior evidence, scoring thresholds, lockfiles or acceptance history.  
* Produce docs/platform-independence/pi-8-verification.json from observed runs, reproducible offline with no hidden implicit environment.

Runner implementation is optional if a smaller existing mechanism gives equivalent repeatable evidence; the hardening file must justify that substitution. Avoid a framework or general-purpose CI orchestrator for a one-time audit.

## 7\. Workstream W2 — Standalone packaging and unrelated application

Independently build wheel and sdist of the core in a clean output directory. Install outside checkout, with PYTHONPATH unset, optional apps physically absent and import-deny checks for example namespaces. Inspect distribution metadata, entry points, transitively required modules, model/router/app registration and HTTP route inventory. Verify actual FastAPI lifespan, loopback consumer calls, context packing and use of offline\_fake; a package import alone is insufficient.

Separately install the unrelated Reading Logbook host/client (or another demonstrably unrelated external consumer) without private core imports, then run versioned API, signed issuer/actor identity, workspace membership, streaming, error, retry and continuation tests. Do not weaken auth to make the consumer work. Build a negative run for forged identity, missing membership, duplicate idempotency key, revoked app and mismatched version. Verify that dropping reference apps does not expose their routes or providers.

## 8\. Workstream W3 — Provider, search and free-first portability

With fakes and deterministic transport hooks, run at least two distinguishable provider profiles (not both aliases for Gemini) and denied/unsupported count/embed capability cases. Verify model dispatch identity, token accounting provenance, streaming, timeout/429/quota fallback, cancellation, partial output, physical attempt count and no silent paid or Gemini fallback. Treat live non-Gemini evidence as a separate gate if unavailable.

Verify free-first policy is an invariant at the physical dispatch and reconciliation boundary, not merely a router score. Check quota limits across workers and restarts at the level the actual store can prove; synthetic single-process tests cannot close a distributed gate. Search/retrieval must fail closed on unavailable provider, missing source rights or purpose/recipient mismatch; no unauthorized export or model-context attachment. Inspect strict-zero release policy and PI-6 evidence to prevent fake \$0 or synthetic utility being marketed as measured provider cost/quality.

## 9\. Workstream W4 — Authorized cross-app continuity and privacy

Exercise explicit user-global profile consent across two unrelated apps and a separate owner/actor/workspace; prove authorized read after grant and denial without grant. Confirm app-private records stay private even for the same owner. Test purpose, recipient, sensitivity, source revision, TTL, grant withdrawal and expiry at request inspection, context assembly, final physical-send boundary, SSE, history/detail/summary/replay/export and any cache. Run revoke-vs-send and permission-change races; record whether atomic issuer lease or distributed send fence is actually available.

Include MEM-2 default-off search/fetch/topics and proposal-only tool behavior, and verify no accidental MEM-3+ or memory auto-promotion. Use content canaries to detect cross-scope leakage, including stdout, errors, logs, traces and evaluation artifacts. Do not serialize private content in the audit ledger.

## 10\. Workstream W5 — Replay, deletion, restore and two-store authority

Audit P19 reservation/settlement, unique original keys, retained attempts, unknown outcomes, SDK retries, timeout/cancel and replay after restart. Require no duplicate physical effect or false success under retry. Do not erase a receipt as cleanup or treat a local in-memory journal as distributed durable authority.

Run a disposable stale-backup experiment only if native stores, exact resources, approved images and owner fence are verified. The drill must preserve monotonic rights/deletion epochs outside the restored snapshot, refuse resurrected data on read/export/send, preserve consumed quota/attempt identity, and account for external recipients and backups. Distinguish logical serving denial, physical object erasure, provider deletion, backup expiry and signed URL revocation. If native testing cannot safely run, preserve BLOCKED and a precise operator-approved runbook, not an assertion that a synthetic restored repository proves recovery.

## 11\. Workstream W6 — Cloud/operations and cost review

Review PI-7 preflight as static policy only. Verify the planner refuses apply, unbound account/project/audience/image/IAM/network/storage/billing identifiers, secret-bearing logs and unexpected flags. Review local life cycle, dependency artifact provenance, container ownership, native egress and teardown races; refuse an untrusted/shared Docker daemon.

For operator-authorized live acceptance, require an exact project, identity, account, resource, budget ceiling, request caps, free-first permissions, deployment plan and rollback approval. Without them do no live provider/cloud work. Calculate documented cost envelopes with authoritative pricing and actual account-specific usage; label potential vs observed. Verify opt-out, kill switch, failure recovery, backup/restore, telemetry redaction and strict-zero policy across restart/worker boundaries only to the extent evidence permits.

## 12\. Workstream W7 — Skeptical cross-cutting threat review

Search beyond the roadmap for: implicit optional-app imports; hidden global default identities; cross-tenant cache keys; stale or revoked content in embeddings/summaries/evidence/export; replay with original vs fresh keys; quota starvation/undercharge; provider SDK retries; network egress through child processes; untrusted manifest/URL/DNS redirection; arbitrary tool effects; unsafe serialization; supply-chain lock and wheel provenance; cloud IAM/config drift; data retention and irreversible deletion; resource exhaustion or hanging cleanup.

For each credible P0/P1, create a minimal adversarial reproduction and document whether it is a new defect, inherited unresolved gate or untested hypothesis. Fix only bounded audit-tool defects in the PI-8 implementation session. Any substantive platform security/runtime issue should be made explicit with owner and remediation decision; do not mix a broad core refactor into a purportedly independent audit.

## 13\. Minimum acceptance matrix (P8-01 to P8-36)

Packaging and consumer:

* P8-01 pinned source, dirty state, input hashes and full evidence provenance.  
* P8-02 built wheel/sdist installed outside repo, optional apps physically absent.  
* P8-03 installed core API/lifespan/chat/context with no example dependency or env.  
* P8-04 unrelated app client/host installs without private core imports/source edits.  
* P8-05 registered identity/actor/workspace and versioned consumer success.  
* P8-06 forged identity, absent registration/membership, revoked app denial.  
* P8-07 duplicate request and lost-ack continuation original-key safety.

Provider/search/quality:

* P8-08 non-Gemini transport and stream/timeout/cancel provenance.  
* P8-09 unavailable count/embed do not silently use another vendor.  
* P8-10 strict-free policy prevents unexpected billable fallback and retry.  
* P8-11 physical attempt, quota, timeout/429, cross-worker and uncertainty semantics.  
* P8-12 embedding identity/version fence and no cross-space reinterpretation.  
* P8-13 retrieval rights, source binding, attribution and purpose checks.  
* P8-14 tool registry allowlist/side-effect permissions and failure containment.  
* P8-15 measured-versus-synthetic quality/cost labels and PI-6 non-promotion.

Consent and memory:

* P8-16 explicit cross-app global preference success and revocation.  
* P8-17 same-owner app-private isolation; other actor/owner denied.  
* P8-18 right-to-send check under revision/grant race and expiry.  
* P8-19 denial across context, SSE, history, summary, replay, export and cache.  
* P8-20 MEM-2 defaults, forget receipts and no MEM-3+ leakage.

Resilience and operations:

* P8-21 retained original-key receipts after timeout/cancel/restart.  
* P8-22 quota reservation/settlement and no double-charge/no duplicate effects.  
* P8-23 native PostgreSQL \+ DynamoDB isolation, state/restart and teardown if safe.  
* P8-24 stale backup restore cannot undo revocation/deletion/receipt fence.  
* P8-25 deletion classification: serving denial vs physical/provider/backup erasure.  
* P8-26 redacted logs, traces, exceptions, subprocess and artifacts.  
* P8-27 native child egress fence and supply-chain/package provenance.  
* P8-28 static cloud plan rejects unverified live binding and apply.  
* P8-29 approved live identity/IAM/network/account operation, otherwise BLOCKED.  
* P8-30 real model/search costs and effective caps, otherwise BLOCKED.  
* P8-31 outage/retry/rollback/kill-switch, resource boundedness and cleanup.

Audit and release:

* P8-32 roadmap A01–A22 mapped to evidence and independently challenged.  
* P8-33 reproducibility: source, fixture, command, environment and digest.  
* P8-34 negative/adversarial matrix with P0/P1 triage and owners.  
* P8-35 compatibility: migrations, public APIs, legacy data, default-off flags, evaluation locks.  
* P8-36 operator readiness decision with exact gate-by-gate status, independent-review pending flag, rollback and blockers.

A01–A22 mapping must be complete and many-to-many where warranted: A01/A02 \-\> P8-02/03; A03/A04 \-\> P8-04/05; A05/A06 \-\> P8-06; A07 \-\> P8-07/21; A08–A12 \-\> P8-08–12; A13–A16 \-\> P8-16–20; A17/A18 \-\> P8-13/14/18/19; A19 \-\> P8-15/30; A20 \-\> P8-24/25; A21 \-\> P8-02/27; A22 \-\> P8-32–36. For each scenario include exact prerequisites and expected evidence strength in the hardened matrix.

## 14\. Outputs, gate decisions and rollback

Commit only justified audit source/tests and PI-8 documentation under docs/platform-independence. Required files, or equivalents with links:

* pi-8-plan-hardening.md: original-plan critique, threat model, narrow scope changes and frozen matrix.  
* pi-8-implementation-report.md: changed files, observed execution, negative findings and limitations.  
* pi-8-verification.json: machine-readable case ledger, evidence identity, no sensitive payloads.  
* pi-8-readiness-assessment.md: each feature/profile gate, P0/P1/P2/P3 findings, no-go reasons, safe offline/local limits, operator actions.  
* pi-8-independent-review-handoff.md: exact commit/parent, commands, fixtures, outstanding risks and reviewer challenge areas.  
* Makefile pi8-check and focused tests only where audit automation merits it.  
* Update docs/current-state.md, docs/README.md and PI index without erasing prior historical status. No fake PASS for blocked predecessor requirements.

Verdict vocabulary:

* AUDIT\_CANDIDATE\_READY\_FOR\_INDEPENDENT\_REVIEW: repeatable implementation and candid evidence, not independent approval.  
* CHANGES\_REQUIRED: reproducible deficiencies or evidence defects that prevent responsible audit closure.  
* BLOCKED\_UNVERIFIED: external/native/authority prerequisites absent.  
* PROFILE\_APPROVED\_FOR\_NARROW\_USE: only after relevant independent acceptance and explicit authorization for the exact profile; never inferred from overall PI-8 completion.  
* PRODUCTION\_NO\_GO: default for personal-data, cloud, paid or provider live use until all necessary predecessors and independent acceptance close.

Rollback means disable or remove only new audit tooling, return to last accepted safe/default-off profile and retain immutable historical evidence, original keys, tombstones, deletion receipts and review findings. Do not roll back monotonic safety authority or "restore" deleted data by reverting a migration.

## 15\. Completion and review protocol

The implementing Codex session must review and harden this plan BEFORE code, in the SAME session and WITHOUT subagents, then execute bounded changes/tests and skeptical self-review. Never claim its self-review independent.

The fresh post-implementation reviewer must derive its own requirements from architecture and real behavior, inspect changed and unchanged high-risk code, independently reproduce a representative test subset, challenge the plan itself, and publish a severity-ranked remediation handoff with concrete file:line evidence and a gate-by-gate verdict. Any required runtime fixes and independent re-verification occur in a subsequent distinct change/session.

The phase should finish even if some live gates are BLOCKED, provided the final artifacts accurately say what is locally proven and what remains unsafe. It should not finish as "production ready" while PI-5/PI-7, real-model, identity, native recovery, deletion or independent-review gates remain open.

## 16\. References

* Repository: [https\://github.com/jasonkli21/personal-ai-system](https://github.com/jasonkli21/personal-ai-system)  
* PI charter: [https\://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/platform-independence-roadmap.md](https://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/platform-independence-roadmap.md)  
* Current state: [https\://github.com/jasonkli21/personal-ai-system/blob/main/docs/current-state.md](https://github.com/jasonkli21/personal-ai-system/blob/main/docs/current-state.md)  
* PI-5 gate: [https\://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/pi-5-completion-gate.md](https://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/pi-5-completion-gate.md)  
* PI-6 gate: [https\://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/pi-6-completion-gate.md](https://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/pi-6-completion-gate.md)  
* PI-7 report: [https\://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/pi-7-implementation-report.md](https://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/pi-7-implementation-report.md)  
* PI-7 remediation: [https\://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/pi-7-review-remediation-2026-11-03.md](https://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/pi-7-review-remediation-2026-11-03.md)  
* PI-7 verification: [https\://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/pi-7-verification.json](https://github.com/jasonkli21/personal-ai-system/blob/main/docs/platform-independence/pi-7-verification.json)


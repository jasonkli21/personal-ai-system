# Codex Handoff — Conditional PI-6 Offline Development With PI-5 Production Gates Preserved

**Repository:** https://github.com/jasonkli21/personal-ai-system  
**Known main HEAD / starting anchor:** `093e3b6816581e0b975e74e498dab99a2ac9a4b6` (parent `6056a9c9f18750d2044e2fd47bc5ca67fb16633b`)  
**Decision date:** 2026-11-01, America/Los_Angeles  
**Execution model:** **GPT-6.1 Sol (`gpt-6.1-sol`), High reasoning**; one long-running Codex implementation session, **no subagents or parallel agent delegation**.  
**Independent reviewer, after implementation:** **GPT-6.1 Sol (`gpt-6.1-sol`), High reasoning**, in a genuinely separate session from implementation. If the reviewer produces bounded remediation, use GPT-6 Luna, Max for the targeted fix and GPT-6 Luna, High for verification, followed by a distinct independent signoff where required.  
**How to use:** Attach or paste **this entire file as the only execution prompt** into a fresh Codex session in the repository. Execute its safe local work without asking for another plan or prompt. Do not treat its mention of blocked external operations as authorization to perform them.

## 0. Role and decision — read this first

You are the implementing staff-level platform engineer, evaluation scientist, and privacy/reliability engineer. The user explicitly wants to **continue with PI-6 offline development** even while some PI-5 external/production verification remains incomplete, **provided the gaps are documented, disabled, and not misrepresented as accepted**. This is a **narrow sequencing exception** to the former PI-6 Stage G/G5 entry rule. It is not a PI-5 completion acceptance, source-rights grant, spending authorization, production/deployment approval, or waiver of privacy/replay/cost correctness.

Implement a meaningful, reproducible, application-independent **offline PI-6 task-evaluation and optimization harness** through existing personal-ai-system seams, with accurate utility/cost/safety evidence. First revise the local PI-6 plan and gate documentation so the implementing and review workflow honors this new distinction. Do a skeptical review/hardening of the plan **in this same Codex session before implementation**, without subagents. Then implement, test, self-review, produce a separate independent-review prompt, and stop. **Do not wait for live provider credentials, cloud infrastructure, or physical deletion authority to start safely scoped local work.** Do not fake those evidence classes.

Required outcome labels (keep distinct in reports and verification JSON):

| Gate | Required status at start | Meaning |
| --- | --- | --- |
| `pi5_completion` | **`blocked_unverified`** | Prior PI-5 F01/F02/F03, source/cost/recovery and operational proof remain open. Never label `accepted`. |
| `pi6_offline_development_entry` | **`conditional_go`**, subject to a quick code/safety preflight | Authorized to add local, default-off, synthetic evaluation machinery; independently review this narrower scope later. |
| `pi6_offline_evaluation` | `pending`, then evidence-specific `verified_local` / `partial` / `blocked` | A local harness is not evidence of real-model task lift. |
| `pi6_production_promotion` | **`no_go`** | No runtime policy changes, source-enabled deployment, paid/live routing, or claims of eligible utility/cost promotion. |

If a genuine **P0/P1 defect in a capability actually enabled by the proposed offline code** appears, fail closed and stop that path. A production-only unavailable path may remain explicitly `blocked_deferred` when it is disabled and cannot be called by the PI-6 runner. Do not convert the old PI-5/P6 pass criteria to `pass` just to move forward.

## 1. Starting evidence and authority

At the time this handoff was prepared, GitHub `main` was exactly `093e3b6816581e0b975e74e498dab99a2ac9a4b6` (direct child of `6056a9c`). The new commit fixes only PI-5 review finding **R05**: `/v1/conversations/{id}/context` now supplies `get_context_permission_revalidator` to `ConversationService.get_conversation`, with `current/revoked/missing` synthetic route tests. The implementer recorded **17 passed** in `backend/tests/test_context_routes.py` and clean backend lint; **these are implementer claims, not an independent new-SHA full-suite run**. The independent prior-SHA reviewer had obtained **172** focused native-fenced passes, **34** HTTP passes, **896** PI-3/4 passes, and **2,326** broad offline backend passes under Linux equivalents, with documented macOS/Python runtime and installed-probe differences. Do not attribute those results to `093e3b6` or the PI-6 changes.

Remaining mandatory **PI-5 production** blockers, all still open at this starting SHA:

1. **R01/F01, P5-11/14:** local source snapshots are not a distributed monotonic issuer/rights epoch and atomic physical-model-send permit; external source-to-model context and source-specific export-purpose grants with downstream provenance/revalidation are incomplete.
2. **R02/F02, P5-04/19/26:** no approved live provider/account/source rights/privacy/free-tier/billing/physical P19 attempt proof; no deployed private IAM/network identity, safe quota/cost or recovery acceptance.
3. **R03/F03, P5-22/27:** a bounded local SQLite intent journal is not a distributed original-key fence or stale-backup anti-rollback/recovery/deletion system.
4. **P5-24:** canonical pinned macOS arm64 / CPython 3.11.15 PI-2–5 and inherited provider-matrix/Phase35/36 causality remain to be independently verified.
5. **R07/F08, P5-28:** original pre-existing untracked plan/file bytes and ownership were not verifiable in the reviewer's clone; verify only in their owning environment and do not overwrite.
6. **Independent acceptance:** PI-5 remains `blocked_unverified`. A narrower PI-6 sequencing exception is not a signoff on those gates.

Read, in the repo as available: `AGENTS.md`; root and backend READMEs; `docs/README.md`, `docs/current-state.md`; `docs/platform-independence/README.md` and `platform-independence-roadmap.md`; `pi-0-architecture-decisions.md`, PI-1–4 public contract and baseline docs; `retrieval-v1.md`; `pi-5-completion-gate.md`, `pi-5-completion-implementation-report.md`, `pi-5-completion-verification.json`, `pi-5-completion-independent-review-remediation-2026-11-01.md`; MEM-0–2 and Phase35/36 compatibility evidence; relevant implementation and tests. Historical PI-6 plan/prompt/review artifacts may exist outside Git or in an untracked worktree; **do not assume they are checked in, overwrite them, or require the user to attach them**. This file contains the revised executable PI-6 requirements. Reconcile any existing `pi-6-*.md` user documents if found.

## 2. Non-negotiable operational boundaries

- **No network/provider/cloud/live actions:** no real Brave or model send, nominally free API call, billable request, credential harvesting, account probing, deployment/IAM change, production database/real personal data access, backup restore, physical deletion, or egress-based fixture generation. Tests and benchmarks must be hermetic, deterministic, synthetic, and bounded. Do not request new external authority merely to finish this offline phase. If a requested future live operation is needed, record the exact missing authorization and leave it blocked.
- **No new side-effect path:** no provider fallback, model-driven arbitrary tool, client-supplied executable scoring code, untrusted Python imports, URLs/paths, native external send, SDK retry or paid route. Use statically reviewed allowlisted fake adapters only. External/production PI-5 capabilities remain default-off and inaccessible to this runner. Fail closed if the disabled path is encountered.
- **Preserve safety and independence:** no cross-owner/actor/application/workspace source use, no quote-purpose conflation, no weakened revalidation/consent, no replay of unknown physical original intents, no old receipt/tombstone pruning, no downgrade of context/provenance/citation/summary/export gates. Existing MEM-0/1/2 protections and default-off behavior remain; MEM-3+ frozen. Reference/toy apps are not core dependencies. Reading Logbook access must use public HTTP where needed.
- **Preserve historical evidence:** do not rewrite, weaken, rebaseline, delete, or silently regenerate PI-1–5/Phase35/36/MEM fixtures, thresholds, score expectations, source manifests or v1–v25 planning locks. A newly needed PI-6 suite/manifest gets its own version; an actual new planning identity requires an additive new version with explicit justification.
- **Avoid external writes:** this handoff authorizes local working-tree code/docs/tests, not pushing to GitHub, opening a PR, changing remote branches, publishing, deploying, or deleting users' files. Preserve dirty and untracked files; avoid destructive reset. Do not use subagents, delegate parallel tasks, or take over another agent's work.
- **Evidence honesty:** synthetic correct output is not real-model task utility; a fake $0 is not free-tier proof; a Python network hook is not a native OS egress fence. No result may promote a production policy or mark PI-5 accepted.

## 3. Work order A — reconcile, preflight, and rewrite the gate **before** PI-6 code

1. Record exact `HEAD`, parent(s), tracked/untracked status, diff, current runtime/ABI/OS/dependency lock, migrations, installed distributions and relevant feature flags. At a later HEAD, inspect all intervening changes; never reset or overwrite user work. Capture baseline lint and narrow R05 tests. Check the expected reviewer artifact source hashes where possible without editing old manifests. If source has changed, retarget and update the handoff ledger rather than pretending the reviewed SHA is current.
2. Independently inspect R05 and validate the actual route handler and service guard. Run `test_context_routes.py` and relevant PI-5 context/HTTP tests on the supported environment; inspect new tests' synthetic attribution construction. At minimum test `current`, `revoked`, and `missing` validator statuses; add realistic wrong-application/actor/workspace and source-expiry/mutation tests if safe and feasible. Confirm denial content stays opaque. Record results and limitations.
3. On a supported macOS arm64 / CPython 3.11.15 machine, run canonical pinned `make pi5-check`, `make pi2-check`, `make pi3-check`, `make pi4-check`, relevant planning/provider-matrix/Phase35/36/research suites and backend lint. If supported only partially, run the strongest bounded no-egress equivalents and classify skipped canonical portions; Linux cannot claim the macOS sandbox runner or v25 runtime-identity pass. Investigate genuine failures without changing old locks.
4. Create or reconcile `docs/platform-independence/pi-6-conditional-entry-decision.md` (dated) and `pi-6-plan-hardening.md`. Critique the old absolute Stage G/G5 requirement on its merits; map current source/permission/attempt/cost architecture and distinguish missing **implementation** from missing **external verification**. Document the user-authorized scheduling exception as `pi6_offline_development_entry=conditional_go`, not `pi5_completion=accepted`.
5. Amend `docs/platform-independence/pi-5-completion-gate.md`, `docs/current-state.md`, the platform roadmap/README and **any existing PI-6 plan, implementation prompt and review prompt** to use the two gates, preserving their original P6-02/P6-14/P6-15/P6-29/P6-30/P6-32 complete-acceptance targets as **open**, not passed. If historical PI-6 files do not exist in Git, create a concise revised PI-6 local plan and a distinct independent review prompt from this file; do not invent a preexisting plan checksum.
6. Write a concrete feature/arm eligibility table: which current source, context, memory, profile, research, route, P19, and tool seams are usable with synthetic fake I/O; which require real credentials or distributed authority; which are outright unsafe to call. Mark each ineligible arm `blocked_capability`, `denied_policy`, `not_applicable`, or `unmeasured`, with reason and missing prerequisite. A disabled capability must not be reachable via the evaluator, even through retries, tool registration, or fallbacks.

**Pre-code gate:** continue to PI-6 implementation only if the worktree is safely reconciled, the local R05 path still fails closed, core permissions/tenant isolation and original-key invariants are intact, hermetic no-egress execution is available, and the restricted entry contract above is written. If a new exploitable P0/P1 affects **enabled offline** paths, fix or quarantine that path first. Missing **disabled production** capabilities do not prevent offline W0–W5, but remain visible blockers.

## 4. Work order B — offline PI-6 evaluation harness, one session

**W0 — architecture and preregistration.** Before writing PI-6 runtime/evaluation code, perform the critical plan hardening in the same session. Pin what is actually measurable, the hard privacy/cost vetoes, eligibility per arm, existing reusable modules, and experiment hypotheses. Prefer additive evaluation/fixtures/test code, no new API/storage migration/provider/runtime or policy default. Record design alternatives and rejected shortcuts. Distinguish (a) local structural safety, (b) causal scripted task success, (c) real-model utility, (d) live cost, and (e) production promotion as different evidence classes.

**W1 — task corpus and rubrics.** Add a separately versioned `fixtures/pi6/` corpus and narrow contracts under `backend/src/personal_ai/evaluation/`; start with **32–48** entirely synthetic cases spanning **eight families**, at least two independent variants per family and both one-turn and state-transition tasks. Families: (1) one-app relevant/irrelevant context; (2) exactly consented cross-app whole-profile use via Reading Logbook public API; (3) MEM-0/1/2 recall/correction/forget; (4) long-context packing/branch summary; (5) existing research citations and conflicts; (6) eligible **local-only** PI-5 retrieved document-to-model/context/citation/replay with fake transport and denied external alternative; (7) provider/quota/unavailability; (8) original-intent replay/source revocation transitions. Include true task outcomes, forbidden claims/actions, source rights/expiry events, citation oracle, hard constraints, operation eligibility, matched token/output/deadline cap, rubric/version and provenance. Separate calibration from group-held-out by task lineage/source config; freeze and hash cases, scoring, split and manifest **before** candidate measurement. No historical fixture mutation.

**W2 — paired production-seam runner.** Build an offline CLI/runner using the **actual existing** `create_app`, authorization, context planner/packer/counting, chat service, P19/P21 usage accounting and local PI-5 retrieval/tool integration, with fake source/provider adapters at I/O boundaries only. Never replace business logic with a parallel evaluation-only implementation of authorization or orchestration. Use isolated state per case/arm, controlled clock/seed/cache and source revision, bounded time/batch/bytes, OS-level network fence where feasible, and a separate warmup set. Reading Logbook must exercise its public signed HTTP consumer where applicable, not private Python imports. Verify core wheel/sdist with toy apps physically absent. Do not make the real external model path callable.

Prespecify **eligible arms**, with identical facts, scopes and budgets: fixed current context/routing baseline; no eligible durable memory ablation; existing selective memory/profile under exact local grants; existing research-v1 variants; existing admitted fake routing profiles (plumbing only, not real model quality); PI-5 **local-only** retrieved context versus no-retrieval and standalone retrieval controls. The old P6 requirement for a fully eligible *external* retrieval arm remains `blocked_deferred` under the new dev gate, never replaced by a fake marked as live. Use exact `measured`, `blocked_capability`, `denied_policy`, `not_applicable`, and `unmeasured` labels and matched denominators.

**W3 — observations, cost and safety.** Per case/arm retain allowlisted numeric/categorical and non-linkable digest metadata: suite/case/fixture/rubric/source/runtime/commit identity; owner/app/workspace and authority *classification* (no plaintext identity); provider/model/serializer/token-counter identity; source/revision epoch classification, policy/seed/order; factual/hard-constraint/citation scores; context/input/tool/output tokens with authoritative vs estimated vs unknown confidence; wall/CPU latency and meaningful percentiles; quota reservation/settlement, expected vs observed fake dispatches, cancellation/unknown outcome and duplicate effect veto. Keep `$0 synthetic`, real USD, upper bound, estimated cost and unknown **separate**. Persist **no raw task prompt, generated answer, quote/passage, profile value, source label/path, secret, credential, authorization header or real owner identity**. Score ephemeral raw text in memory then discard; assert report/trace/log redaction, including exception paths and optional `emit()` retention.

**W4 — analysis.** Primary endpoint: **hard-constraint-valid task success** for eligible matched held-out pairs. Secondary: supported factual/citation correctness, token/latency/quota/cost overhead, graceful denial, unnecessary context and duplicate-effect attempts. Pre-register hypotheses, minimum meaningful gain, per-family vetoes, budget ceilings, uncertainty method **before** held-out runs. Report per-family matched counts, wins/ties/losses and effect size. For small deterministic synthetic datasets, do not quote fake statistically generalizable 95% intervals or infer real-model lift; if confidence is not meaningful, say `inconclusive`. Any unauthorized disclosure, stale source, unauthorized tool, duplicate effect, hidden fallback, missing source dependency or unapproved provider request is a **noncompensatory veto**. No real-model utility or operator-promotion eligibility from this phase.

**W5 — optional narrowly scoped candidates and reporting.** Compare at most **two** existing configuration-only or offline policy variants (e.g., context budget/selection or research packing), and never alter production defaults automatically. If an arm cannot be safely run, label it blocked and continue the rest. Produce `pi-6-benchmark-contract.md`, `pi-6-implementation-report.md`, `pi-6-verification.json`, `pi-6-benchmark-report.md` (+ canonical machine JSON), `pi-6-plan-hardening.md`, conditional-entry decision, updated gate/current-state/readmes and an independent PI-6 review prompt. Add a reproducible `make pi6-check` where practical. Declare `not_promoted` or `unmeasured` unless genuine eligible evidence supports a later separately approved promotion.

## 5. Adversarial and compatibility verification matrix

**Execute bounded negative cases**, including at least:

- Same owner/foreign actor/app/workspace, forged or expired PI-4 consent, revoked/changed local source/grant/issuer during selection/packing/count/pre-send/SSE/history/detail/replay, missing revalidator, blocked external snippet, stale citation and unauthenticated Reading Logbook call. Confirm no private source or derived content escapes and failed states stay quarantined.
- Malicious quote instructions, false citation/source ID, static tool registry swap/unregistered tool, executable scoring payload, manifest-supplied import/URL/path, file traversal/SSRF, schema drift, kill-switch denial and tool/resource budget exhaustion. No unreviewed code execution or side effects.
- Changed payload under same original key, cancellation, lost fake acknowledgment, timeout/429, unavailable provider/unknown counter, SDK retry simulation, concurrent fake worker, journal full/limit, old receipt and post-restart unknown-intent denial. Never retry a possibly sent real effect; destructive backup/restore remains `not_run` unless independently approved in a disposable environment.
- Cross-arm cache/history/state contamination, duplicate case IDs, tampered manifest, calibration-to-heldout leakage, grouped split violations, score hacking by schema-valid but factually false answers, missing cost interpreted as $0, fake latency labeled live, biased denominator, negative-veto washed out by high average quality, raw content or secrets in reports/logs.
- Independent installed core-only and signed HTTP example consumer, no toy imports, no MEM-3+ behavior, default-off existing flags, unaffected old APIs/schema/migrations and unchanged historical scenario identities.

**Minimum commands, subject to actual Make targets and host:** `git diff --check`; `make backend-lint`; `make pi5-check`; `make pi2-check`; `make pi3-check`; `make pi4-check`; `make platform-independence-check`; `make planning-eval`; `make retrieval-eval`; `make memory-task-eval`; `make pi6-check` after creation; focused context/routes/PI5, provider-matrix/Phase35/36, research, MEM and inherited suites; full offline backend suite; core wheel/sdist plus separately installed Reading Logbook public-HTTP checks. Validate existing target names from Makefile before running. Use repo-approved native/no-egress harness and bounded fake adapters. If a canonical macOS-only check is unavailable, record exact environment and an appropriately classified alternate; never relabel it a canonical pass. No live account, remote provider or destructive DB tests.

Create a **full P6-01–P6-33 scenario ledger** referencing the original phase definitions as preserved, with test/command/observation type and disposition. In particular:

| Original P6 ID(s) | Revised offline-development treatment |
| --- | --- |
| P6-02, P6-29 | Original accepted-PI-5-before-code conditions remain **unmet**. Record a documented user-directed *sequencing exception* for offline work; never mark these tests pass. |
| P6-14, P6-30 | Local eligible PI-5 context-to-fake-model/replay/citation can be measured if source rights are current. External source and distributed authorization subcases remain blocked/unmeasured. |
| P6-15, P6-32 | Native distributed receipt, source lease, restore/deletion and live provider evidence remain **blocked_deferred**, not fabricated by SQLite/fake tests. |
| P6-24, P6-25 | Paired statistics and safety vetoes must be honest under small synthetic samples and never hide missing eligible arms. |
| P6-26, P6-33 | Preserve and independently rerun affected historical checks, with exact canonical skips/runtime restrictions. |
| All other P6 IDs | Implement/adversarially verify to the extent their specific existing **offline eligible** path supports; explicitly mark gaps, not automatic passes. |

When old PI-6 planning files are available, do not rewrite their historical scenario definitions or silently weaken the matrix; add an **offline development interpretation/waiver column** and preserve full production obligations. If absent, use the matrix from this handoff and define missing scenario descriptions in the new revised local plan before coding; do not need another user attachment.

## 6. Reporting, self-review, rollback, and stop

Provide one final implementation report with: exact start and end SHA/dirty state, preserved user files, changed paths, design alternatives, user sequencing exception, old PI-5 status and deferred evidence list, eligible/ineligible arm matrix, source/fixture/artifact/test hashes, exact commands with results/warnings/skips, 33-case P6 ledger, safety negative cases, cost confidence, matched paired measurements, unsupported claims and current production flags. Include honest failures and reruns, not just green summaries. Before finalizing, independently inspect your own diff for privacy leaks, incorrect fixed/missing data distinctions, overbroad source grants, sample/corpus leakage, port duplication, tool side effects, backend dependency creep and hidden provider calls. Keep rollback additive: disable/remove PI-6-only runner and candidate config while preserving PI-5 source fences, historical locks, receipts and tombstones. No destructive cleanup.

Write a **standalone independent PI-6 review prompt** as a repo doc, sufficient for a fresh `gpt-6.1-sol`, High session to review the actual code and challenge the evaluation design beyond its original plan. It must verify conditional-entry scope rather than demand nonexistent complete PI-5 acceptance as a prerequisite to reviewing **offline** work. It must still block production promotion and carry F01/F02/F03, P5-04/11/14/19/22/26/27, P5-24/P5-28 and P6 blocked rows forward. Reviewer should reproduce real negative cases, check installed-example isolation, adversarially scrutinize rubric/denominator/held-out leakage and independently verify source hashes. A same-session self-review is **not** independent acceptance.

**Stop at the end of the offline PI-6 candidate.** Return:

1. A link/path to the code diff or new local commit only if actually created; no push/PR without user authorization.
2. The conditional-entry decision, updated PI-5 and PI-6 gate statuses and all delivered report/prompt paths.
3. Exact tests, evidence types and outstanding failures/blocked scenarios.
4. A decisive `pi6_offline_development_completed_pending_independent_review` or a truthful `blocked` status, plus `pi5_completion=blocked_unverified`, `pi6_production_promotion=no_go`.
5. A plain statement that no real provider/cloud/billable/deployment/production-data/destructive operations were performed.

If the environment prevents a safe local implementation (for example, a mandatory enabled-path security regression, unreconcilable user edits, or an explicit protected workflow), stop and report the precise issue. **Do not request user input for ordinary design choices, missing external accounts, or unavailable production evidence; choose the safe offline path and document the deferral.** Do not start PI-7, MEM-3+, external enablement, a live model-quality experiment, or a production migration.

---

**Model rationale:** GPT-6.1 Sol at High reasoning is suited to both a multi-file Codex implementation and a skeptical independent review. **Run those as separate sessions with separately pinned evidence and no shared self-approval.** Model identity and supported reasoning settings were verified against official OpenAI documentation: https://developers.openai.com/api/docs/models/gpt-6.1-sol and https://developers.openai.com/api/docs/guides/model-selection. If the exact model label is not offered in your Codex UI, select the nearest available Sol coding model at **High** and record the substitution; never silently lower the safety/verification contract.

## Appendix A — Complete original PI-6 scenario checklist (historical target, not automatic acceptance)

The prior PI-6 plan was a proposed, separately stored artifact, not necessarily present in Git. Its section title mentioned 28 scenarios but the actual matrix extended to **P6-33**. This compact checklist preserves the intended targets so the implementation session is self-contained. Each row must receive `pass`, `fail`, `partial`, `blocked_deferred`, or `not_run`, with a test/result/observation class. The original full-acceptance requirement is *not* automatically satisfied by the development-only exception.

| ID | Original intent (paraphrased) |
| --- | --- |
| P6-01 | Exact base and dirty/untracked state; prerequisites and pre-code hardening recorded. |
| P6-02 | Independently accepted PI-5 completion before PI-6; predecessor blockers carried forward. **Unmet; sequencing exception only.** |
| P6-03 | Frozen versioned synthetic cases/rubrics and separate calibration/grouped held-out set. |
| P6-04 | Independent case/family identities, oracle validation, tamper/hash rejection. |
| P6-05 | Core install without any reference/toy app or domain coupling. |
| P6-06 | Reading Logbook uses public HTTP, never private implementation imports. |
| P6-07 | Actual shared context planner/packer with current authority, not a parallel fake. |
| P6-08 | Correct current-profile relevance and unrelated-profile omission. |
| P6-09 | Exact-purpose, recipient, revision and consent for eligible cross-app use. |
| P6-10 | Private/revoked/expired/sensitive source never crosses app or emits. |
| P6-11 | MEM-0/1/2 default-off and security intact; no MEM-3+ or embeddings. |
| P6-12 | Branch/supersession, history/summary dependencies and context counting preserved. |
| P6-13 | Research-v1 citation, grounding, freshness and deterministic adapter checks. |
| P6-14 | PI-5 standalone plus source-to-model/context/read-only-tool/replay tests. **Local-only subcases eligible; external remains blocked.** |
| P6-15 | Durable source/attempt authority, capacity, restore/deletion and live/provider proof. **Blocked for full acceptance.** |
| P6-16 | Matched fixed/ablation/eligible-selective task arms with same budget and rights. |
| P6-17 | Unsupported candidates labeled blocked and excluded transparently. |
| P6-18 | Provider outage/429/quota/counter/kill-switch denial, no fallback or extra send. |
| P6-19 | Original-key collision/replay/cancellation/uncertain attempt/no duplicate effect. |
| P6-20 | Factual/hard-constraint/citation task scoring resists schema-only success. |
| P6-21 | Exact case/source/runtime/model/fixture/rubric attribution and reproducibility. |
| P6-22 | No raw source/prompts/answers or secrets in persistent artifacts. |
| P6-23 | Honest confidence for tokens, latency, quota, monetary cost and fake/live class. |
| P6-24 | Matched denominators, family splits, wins/ties/losses and justified uncertainty. |
| P6-25 | Security/privacy veto cannot be cancelled by mean utility or missing coverage. |
| P6-26 | Hermetic no-network PI-1–5/Phase35/36/MEM regressions or exact skips. |
| P6-27 | Production defaults, historical locks, schema and public APIs preserved. |
| P6-28 | Honest PI-5 and PI-6 acceptance, rollback and evidence boundaries. |
| P6-29 | Exact separate PI-5 independent signoff and operational evidence *before* PI-6. **Unmet; development-only exception.** |
| P6-30 | Retrieved source actually influences bounded context/fake generation/citations and stays authorized through history/SSE/replay. |
| P6-31 | Read-only trusted-tool extension respects static registration, auth, schema, effects and resource bounds. |
| P6-32 | Source revocation, distributed attempt/restore/deletion and no double physical send under adversarial state changes. **Local-only subcases possible; distributed/live blocked.** |
| P6-33 | Historical PI-3/4/Phase35/36 compatibility resolution or independently reviewed blocking status. |

## Appendix B — Review and model handoff contract

- **Now:** one implementing session on **GPT-6.1 Sol / High** completes sections 1–6, no subagents. In-session architecture challenge precedes code; in-session self-review follows tests. The agent's own self-review does not count as independent evidence.
- **After the candidate:** a **fresh GPT-6.1 Sol / High** session runs a skeptical independent review against the pinned implementation SHA. It may declare **offline PI-6 evaluation** accepted within the conditional scope while separately declaring **PI-5 completion blocked** and **production promotion denied**. It must not reject the local work merely because the deliberately deferred PI-5 production gate was not passed, nor misreport that gate as waived for production.
- **Only if findings demand fixes:** bounded Luna Max remediation, then Luna High re-verification; a genuinely separate independent signoff if the fix changes the accepted scope. Do not start another stage or invoke a live provider automatically.

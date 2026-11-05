# Personal AI System — MEM-6 Detailed Implementation Plan

**Phase:** MEM-6 — Memory Research, Longitudinal Evaluation, and Guarded Promotion  
**Prepared:** 2026-11-04 (America/Los_Angeles)  
**Repository:** [jasonkli21/personal-ai-system](https://github.com/jasonkli21/personal-ai-system)  
**Planning revision:** [`619d724bd91d9f633714b576a3fef8e7a8841b6d`](https://github.com/jasonkli21/personal-ai-system/commit/619d724bd91d9f633714b576a3fef8e7a8841b6d), `main` at inspection  
**Program authorities:** *Personal AI — Memory Architecture & Research Roadmap* (MEM-0–7), *Integrated Harness Excellence Roadmap v3.1* (2026-11-03).  
**Status:** Proposed implementation plan. Authorizes no live data access, external model sends, background ingestion, memory-policy promotion, or deployment. The subsequent Codex implementation session must re-pin HEAD and independently harden this plan before editing.

## 1. Executive decision

Build the *scientific decision layer* for memory: a reproducible, versioned experiment ledger; honest longitudinal task comparisons and ablations; mandatory safety/resource vetoes; evidence-tier-aware candidate decisions; and reversible **offline promotion simulations**. The objective is to answer whether a memory policy improves future *task outcomes*, rather than merely retrieval relevance or scripted fixture answers.

The minimum coherent delivery is a **default-off, hermetic E0/E1 research vertical slice**, optionally with a separately approved disposable E2 component test. Complete every safely feasible offline component now; do not interpret missing E2/E3/E4/E5 evidence as permission to synthesize it. Production/live promotion is expressly **out of scope**.

**The central boundary:** This phase may produce `eligible_for_independent_review` or `blocked` *research decision proposals*, but must not make a runtime configuration effective. No agent, research script, imported manifest, or model can change the canonical memory algorithm, source rights, storage lifecycle, or feature flags as an effect of an experiment.

### Why MEM-6 now?

- MEM-0 established 30 synthetic memory-task cases and a comparison harness, not native/model task-quality proof.
- MEM-1 introduced scoped verified procedures/project decisions with paired synthetic Task A → Task B evidence; its production issuer and some independent gates remain open.
- MEM-2 introduced default-off controls and scoped operations; review and production rights remain gated.
- MEM-3 terminal-step episode capture and selection are **hard disabled**; its source-issuer, retention, and runtime trust boundaries are incomplete.
- MEM-4 has bounded synthetic consolidation, E0/E1 and partial native PostgreSQL E2 component evidence, but no live episode intake or automatic approval.
- MEM-5 at `f33aec3`, amended by `619d724`, contains a sealed, public/synthetic, default-off `memory/research/` navigation experiment: 40 author-visible cases, ten arms, and a 400-attempt v2 replay. Its fixed arm and real semantic/hybrid/reranked arms have **zero completed eligible comparison cases** because compatible real embeddings/knowledge adapters are unavailable; they must not be silently excluded from the denominator or presented as losing policies. It has no independently authored blind challenge cohort, no demonstrated real-model longitudinal lift, and no production promotion. Latest remediation reports 57 focused passing tests, 806 wider regression tests with one skip, blocked disposable PostgreSQL DSN, and inherited `planning-eval` source-identity failure. All release profiles remain `NO_GO`.
- HXE-2 owns *shared telemetry and model/task experiment plumbing*. MEM-6 owns *memory hypotheses, memory-specific validity constraints, and promotion decisions*. RE-4 separately owns reasoning-strategy promotion.

The existing `research_experiments` persistence is a compact immutable scoped 30-day `not_promoted` record store (`026_research_experiments.sql`); investigate reuse before adding persistence. It is **not** a general evidence authority, long-term archive, or mutable promotion registry. No parallel experiment database or control plane.

## 2. Scope and authorization matrix

| Capability | Implement now in one Sol High session | Extra authority/evidence required |
| --- | --- | --- |
| Typed versioned experiment, corpus, model, policy, environment, scorer, source and decision manifests | **Yes**, E0/E1, synthetic/offline | Independently certified source identity for acceptance |
| Immutable, hash-checked run receipts and append-only research decisions | **Yes**, local/ignored artifacts and bounded existing seams | Native durability/retention decision for deployed records |
| Within-task matched arms and cross-session *synthetic* temporal replay | **Yes** | Real historical sessions, active MEM-3 issuer, owner consent |
| Longitudinal drift, poison, conflict, revocation/forget and restore fault matrix | **Yes**, deterministic fakes with explicit limits | Deployed source issuer, native/cloud recovery |
| Scorer isolation, blind-ready challenge ingestion, independent replay package | **Yes**, with **author-visible** labeling unless independently sealed | Independent scorer/challenge authorship, custody |
| Statistical uncertainty and paired ablation reports | **Yes**, only for supported matched pairs | Adequate sample and independent real-task evidence for claims |
| Memory selection proposal / veto / dry-run canary / dry-run rollback | **Yes**, no effective writes | Separate review, physical execution authority and opt-in |
| Native PostgreSQL component verification | Run **only if** approved disposable DSN already available | DSN and isolated infrastructure; never assume |
| Real local model or cross-provider trials | Protocol/manifest/driver can be prepared, **do not dispatch by default** | Opt-in owned endpoint/account, rights, no-cost proof, quotas, approved data and hardware |
| Live/hosted inference, real user history, automatic memory promotion and deploy | **No** | Explicit owner authorization, E3/E4/E5 and prior release gates |

**Freeze interpretation:** The integrated roadmap retains a MEM-3+ feature freeze except for explicitly authorized, bounded development slices. This request is to generate planning artifacts, **not** a live unfreeze or enablement decision. The future implementation prompt should confine work to the E0/E1 research slice and separately accepted native local checks. If repository gate documents show a narrower restriction, obey it and record the affected items as blocked. Do not widen scope based on a phase name or the existence of a roadmap.

## 3. Owning architecture and non-duplication

Relevant code/evidence to inspect at the implementation revision:

| Area | Owning seams / evidence | Use |
| --- | --- | --- |
| Memory service and authority | `backend/src/personal_ai/memory/README.md`, `services.py`, `knowledge_service.py`, `research/{contracts,engine,index,semantic,source}.py`, lifecycle and knowledge modules | Candidate policies and trusted source filtering stay here; no new model-facing grant |
| Canonical context/prompt | `context/builder.py`, `context/tokens.py`, `MemoryQuery`, `ContextBuilder` | All compared arms use the same approved packing/token semantics |
| Evaluation | `backend/src/personal_ai/evaluation/`, `memory_task_baseline.py`, `memory_knowledge.py`, `memory_navigation.py`, `real_tasks.py`, fixture schemas and tests | Add a separate E1 study, keep historical cases/hashes immutable |
| Experiment state | `persistence/postgres/research_experiments.py`, migration `026_research_experiments.sql`, `evaluation/retrieval_contracts.py` | Reuse compact scoped `not_promoted` summaries if suitable; don't expand 30-day payload limits casually |
| Shared HXE telemetry | `docs/harness-excellence/local-inference.md`, `evaluation/real_tasks.py`, usage/trace and provider-attempt ledger | Produce compatible sanitized observations; HXE-2 remains telemetry owner |
| Other phase controls | `docs/current-state.md`, `docs/memory/2026-11-04-retrieval-remediation.md`, `docs/memory/2026-11-04-retrieval-source-proposal.json` | Preserve unaccepted source locks, default-off gates and rejected evidence |
| General execution | `workflow/`, RE/HXE event and attempt contracts | Never create a competing run/effect controller or dispatch loop |

**No phase names in active implementation names.** Use enduring names such as `memory_research`, `memory_experiments`, `memory_policy_decisions`, `memory_longitudinal`, and `memory-research-eval` if approved by naming policy. `MEM-6` belongs in dated planning/evidence files only, not active modules, public commands, tests, or current README labels.

Do not alter old fixtures, hashes, manifest IDs, immutable receipts or source locks. Generate a new, additive study generation. A changed dependency hash is a **source drift proposal**, not an excuse to rewrite a frozen identity. In particular, preserve the inherited planning baseline failure until its own independent reconciliation.

## 4. Detailed work packages

### WP0 — Reconcile current code, prior evidence and development authority

1. Record `git rev-parse HEAD`, branch, status, working-tree dirt, Python/runtime dependencies, feature flags and effective local profile. Preserve unrelated local edits. Read repository `AGENTS.md`, `docs/README.md`, `docs/current-state.md`, module README, relevant contracts/migrations/tests, and the MEM-5 remediation.
2. Produce a compact architecture/gate matrix mapping MEM-0–5 data/evaluation seams, HXE-2 telemetry, RE-4 strategy promotion, and all owner/right/retention/freeze gates. Confirm which experimental arms have actual supported outputs.
3. Decide whether the existing 30-day experiment table suffices for bounded optional native metadata persistence. Default to reproducible ignored local artifacts with a manifest; avoid a migration absent a concrete requirement. If persistence is truly necessary, state owner and deletion/replay semantics before edits.
4. Harden this plan **inside the same implementation session**, without spawning agents. Record accepted changes and rejected expansions in a dated decision note. Specifically challenge whether the proposed task corpus is large/diverse enough and whether run/scorer boundaries actually permit blind assessment.

**Exit:** A reviewed scope/authority decision and documented known blockers before code changes.

### WP1 — Versioned experiment contracts, chain of custody and registry

Create minimal, strict typed contracts (Pydantic/dataclasses per current idiom) for:

- `DatasetManifest`: immutable dataset ID/version, provenance/consent class, fixture bytes digest, source snapshot/time, eligibility policy, splits, task-family coverage, scoring seal and contamination disclosure.
- `TaskManifest`: task and temporal split/episode order, subject/workspace/actor, source availability and permission timeline, permitted tools/effects, expected outcome *held by scorer*, refusal/abstention scoring, gold reference IDs (scorer-only).
- `ModelManifest`: provider or local endpoint, model/build/weights/hash, tokenizer/config, temperature/seed, capability and privacy/cost profile, actual versus estimated usage; nullable when scripted.
- `MemoryPolicyManifest`: current fixed baseline or experimental algorithm versions (capture, verified knowledge, episode availability, consolidation, index, selection, context allocation), feature flags and full parameter hashes. A hash is identity, **not permission**.
- `RunManifest`: code revision and dirty-state, dependency source hashes, dataset/scorer/parser/serializer, arm and resource budgets, policy, model, attempts/retry IDs, environment and evidence tier, preregistered hypothesis and exclusions.
- `AttemptReceipt`: one row for every attempted (task, arm, seed, repetition, time step), including unsupported/incomplete/deny/timeout/cancel/error, source/permission epochs, selected/packed/consumed source identities, observed task outcome and safe aggregate resource counters; unknown/null where not observed.
- `EvaluationReport`: signed/digested input provenance, denominator accounting by status, paired metrics, uncertainty method, safety failures, scope limitations, leakage/contamination flags and exact comparisons supported.
- `ResearchDecision`: `candidate`, `blocked`, `needs_independent_review`, `rejected`, `not_evaluable` or `eligible_for_offline_canary` — **none equals effective production promotion**. Link immutable artifacts and distinct reviewer identity; keep rejected hypotheses.

Use canonical JSON serialization or an existing deterministic serializer, SHA-256 digests, strict key validation, versioning and tamper detection. No credentials, user text, private traces, raw prompts or personal records in portable receipts. Store protected source payloads only in their authorized owners; research references are scoped and redacted. Bound record length, corpus bytes, cardinality, CPU/runtime and local artifact size. Fail closed on hash mismatch, unknown schema, mismatched env/model space, duplicate receipt ID with conflicting bytes, missing rows or a changed evaluator source.

Make experimental flags a *dependency* of the run, never a writable global setting. Proposals cannot overwrite an existing accepted policy. Ensure canonical owner deletion/forget suppresses current reuse irrespective of an older experiment artifact.

### WP2 — Longitudinal task study with independent-ready splits

Build a new **additive** challenge corpus of at least **48** distinct test cases across at least six families (target eight per family, with deliberately varied ordering and distribution):

1. **Cross-session procedural transfer:** Task A learns a verified local procedure; later Task B executes a new action or avoids repeated discovery, not merely echoing text.
2. **Project decision and revision drift:** valid memory followed by changed project revision/source, including obsolete advice and proper abstention.
3. **Correction and contradiction:** user correction after an old assertion, two unresolved conflicting sources, and correct non-use of rejected claims.
4. **Scope, rights and forget:** cross-owner/workspace/app/actor denial; grant revoke/reissue; deletion/tombstone; stale contexts and replay.
5. **Poisoning and unsupported inference:** injected instructions, fake tool receipts, malicious retrieved content, claimed verified success with ambiguous outcome.
6. **Resource and lifecycle resilience:** growing history, tight token/latency budget, interrupted refresh/checkpoint, cancellation, partial retrieval and index staleness.

Minimum 16 cases must contain **three or more temporal steps**, with at least two truly separate simulated sessions and a change in evidence/authorization/knowledge between steps. Include negative controls where memory should hurt or provide no benefit. Task A receipts must not be counted as Task B success. All arm histories, current evidence, source rights, available tools, canonical budgets, timestamps and seed plans are matched.

Suggested split (adjust only via preregistered hardening):
- 24 development/author-visible cases.
- 12 sealed-*for-the-implementation* validation cases (author is still able to see them; do not label independently blind).
- 12 challenge slots using a separately reproducible challenge-manifest **interface**, populated with new author-visible negatives now; an independent reviewer later supplies genuinely held-out cases without changing scoring code.

Use public/synthetic data only; no real conversation history. A future independent reviewer must be able to substitute a signed challenge package with scorer-only expectations and an opaque driver input that cannot leak rubric/answers/source internals to the policy. Record if the author inspected any split. Deterministic scripted/fake Task B action success is only **E1 causal-proxy** evidence; it is not LLM success.

### WP3 — Baselines, factorial ablations and comparability

Prioritize narrow contrasts that the repository can *actually support*:

- No persistent memory.
- Eligible full history, only if it fits in the same canonical context budget; otherwise `unsupported_full_context`.
- Current fixed legacy memory for records it supports; `unsupported_record_kind` for schema-3, not zero quality.
- Verified procedural/project knowledge selected via existing service and trusted fixture.
- Memory tool lookup/search if existing scoped adapters are exerciseable in the hermetic host.
- Offline pending consolidation proposals **as diagnostic proposals only**; never scored as approved or exposed as trusted memory.
- MEM-5 lexical/topic/adaptive bounded fixture path, with source revalidation and exact eligible-universe context.
- Semantic/hybrid/rerank arms only if an actual compatible authorized embedding adapter is available and verified; fake vectors may test fusion contracts but are *not* a performance comparison.
- Isolate capture versus retrieval versus consolidation versus context packing when source compatibility permits. Avoid a combinatorial explosion: preregister up to six primary pairwise contrasts and limited exploratory combinations.

Do not invent adapters that silently flatten schema-1, schema-3, episode and proposed memory into one trusted corpus. If a comparator is not legal on a case, log an explicit unsupported row and pair eligibility; keep its attempted denominator. Do not claim a win by comparing different data rights, tools, models, token budgets, eligible history or source-currentness clocks. If different capabilities *must* be compared, report a separate non-causal product-system comparison, with the confounders stated.

Benchmark output quality separately from retrieval. A scorer may inspect independently observed task actions, terminal-state receipts, citations/attributions, abstention and false support; not only string match. Use a stateful simulated task tool with stable original intent IDs to detect repeated/duplicate effects. No model-generated “success” labels. Preserve post-task source and permission checks through the final reuse boundary.

### WP4 — Measurement design and statistical protocol

Before the first measured run, record hypotheses, primary outcome, primary contrast, estimand, practical effect size, matched budget and veto thresholds in an immutable, hash-identified protocol. Do not peek at challenge results and then select a new “primary” arm.

**Primary outcome:** paired Task B success at a newly observed terminal state, among preregistered eligible paired units. **Secondary:** repeated-error/rediscovery rate, correct abstention, provenance validity, unsupported-memory rate, recall/precision or answer support, token usage, p50/p95 latency, bytes/index growth, tool/provider calls, maintenance work, actual billed/free-tier provenance and failure/denial rate. Use `null/not_observed`, not zero, for missing native/model/cost data.

**Unit of independence:** task family or scenario/longitudinal trajectory, not each step/repetition as an unrelated sample. Use scenario-clustered paired bootstrap (fixed preregistered seed and interval method) and exact paired win/loss/tie counts; optionally McNemar or paired randomization test when assumptions hold. Report confidence/compatibility intervals, denominator, variance, absolute percentage-point difference and subgroup regressions. With small correlated synthetic cases, avoid inferential “statistical significance” claims. Register multiplicity handling for the few primary contrasts and treat the rest as exploratory.

**Safety is not averaged away.** Any reproducible cross-scope/source disclosure, forgotten resurrection, false-success promotion, unauthorized physical send, duplicate irreversible action or policy-bypass attempt is a **hard veto**, even if aggregate scores improve. Unknown status is not `pass`.

**Resource parity:** same query/tokenizer, shared `ContextBuilder`, context ceiling, output budget, tool count, time deadline and trial order/randomization. Report synthetic fixture-word estimates distinctly from actual model token IDs and total end-to-end costs. Include index build and background maintenance costs in end-to-end accounting; avoid only timing successful candidates.

**Reproducibility:** run every supported arm at least twice with semantic outcome digest (excluding unstable wall timing/ephemeral nonces) and inspect status-level invariants. Record hardware/runtime/version changes as separate cohorts. A fresh process must be able to reproduce from the package without hidden filesystem state.

### WP5 — Adversarial and drift campaign

Implement explicit tests that mutate authority at distinct boundaries:

- source/grant revoke after retrieval candidate generation, after card packing, and immediately before simulated consumption;
- same-owner regrant under a new issuer epoch; different process and stale index;
- correction before/after `observed_at` and `as_of` fences;
- stale snapshot/backup attempting to resurrect forgotten payload or superseded evidence (simulated only; native restore unverified);
- poisoned memory text or fabricated receipt claiming evaluator/policy authority;
- mixed-tenant identifiers, corrupted schema/hash, invalid signature/manifest, unsupported embedding space;
- late timeout, job cancel, exception after partially recorded attempts, retry of original intent, partial task result;
- overlong corpus, extreme vocabulary and token/card budgets, all arms unsupported or no eligible pairs;
- scorer leakage via case metadata, expected answers, filename, canary markers or procedural task artifact;
- experiment proposal and canary manifest attempting to modify live configuration or lower a gate.

Require rejection or explicit non-evaluable status without data disclosure. Tests must demonstrate an attack actually reaches the protected code seam; no superficial mocked function that always denies. Treat research reports and datasets as untrusted inputs to any runtime.

### WP6 — Promotion policy, independent-review package and dry-run canary

Define a **pure decision evaluator** that consumes immutable report references and a gate registry, yielding a decision proposal plus reasons; no database/config promotion side effect.

Proposed gate groups:
1. **Integrity:** reproducible source/dataset/scorer hashes, valid custody, non-leaky split, matched controls and full attempted rows.
2. **Quality:** preregistered positive paired downstream Task B lift over applicable baselines; intervals and regression bounds, not cherry-picked family means.
3. **Safety:** all critical adversarial gates pass; zero known scope, source, forget/replay, poisoning and unintended side-effect regressions.
4. **Resources:** bounded actual model/transport/maintenance/storage resource usage; truthful free-tier/provider eligibility; no undocumented paid fallback.
5. **Evidence tier:** E1 synthetic permits only an offline research decision. E2 independently installed native/local systems, E3 approved live counterpart, E4 deployed recovery/deletion/cost and E5 independently assessed longitudinal real-task utility are required *where relevant to the contemplated live profile*.
6. **Independent review:** distinct reviewer approval of corpus/scorer/source controls, methodology, evidence and release gates, with an immutable signed-off decision record. The implementation author cannot self-approve.

A **dry-run canary planner** accepts an explicitly reviewed candidate and emits staged eligibility checks, sample sizes, stop conditions, monitored metrics and exact rollback target. It does not register a live scheduler, route, migration or feature toggle. A **dry-run rollback** returns the previous stable manifest identity and confirms which offline selectors *would* be disabled, retaining original receipts/forget authority. A later live canary would require trusted issuance, physical-send fencing, immutable provider attempts, per-actor segmentation, protected opt-in, resource caps and actual rollback rehearsal. Do not implement or enable those live effects now.

The decision ledger must retain **failed hypotheses** and unsupported candidate statuses. A rejected candidate cannot be repackaged with the same evidence under a fresh alias to bypass vetoes. New evidence requires a new immutable run identity with a clearly linked prior failure.

### WP7 — Verification, documentation and handoff

Add focused tests for each contract/failure seam, including intentionally broken controls and negative acceptance; run existing relevant memory, research, context, HXE/usage and naming checks. Tests must not assert an arbitrary candidate always wins. Document the actual E1 effect sizes, supported paired comparison count, unsupported-arm denominator, failures/unknowns and resource observations. If policy is worse, record a **NO_PROMOTION** decision and leave the implementation correct.

Expected deliverables:

1. Source/contracts and minimal `memory research` package extension, no runtime enablement or duplicate state.
2. New additive fixtures, manifests, scorer/driver, fault campaign and offline evaluation command, with immutable hashes and two deterministic replays.
3. Ignored machine-readable receipts, human-readable report and dry-run decision/canary/rollback plan.
4. Focused and regression tests and commands/results, with separated E0/E1/E2 evidence.
5. Dated ADR/implementation evidence, updated owning README and `docs/current-state.md`, precise blocker registry, and independent-review handoff.
6. No push, deploy, release, live provider spend, private data extraction, real memory promotion, or automatic model-generated writes.

If a precondition is absent, finish the safe independent portions and mark only the specific affected item `BLOCKED` with needed evidence, responsible owner and exact re-entry test. Never edit historical fixtures or lower a test to make a candidate look superior.

## 5. Proposed acceptance contract

### A. Implementation acceptance — bounded E0/E1

- All new contracts have schema/version validation, deterministic identity and bounded resource parsing.
- At least 48 additive public/synthetic tasks across the six named families, including at least 16 three-step longitudinal cases; task IDs and splits are stable.
- All supported comparisons run with identical permitted information and budget; every requested arm/case/repetition yields a receipt, including `unsupported` and failure statuses.
- At least two complete semantic replays, deterministic digests and source hash locks; independent fresh-process verification works.
- Scorer expectations are unavailable to policy runtime; benchmark contamination and author-visible holdout limitations are honest.
- Primary paired quality and uncertainty summaries use scenario independence and preserve negative findings.
- All critical scope, correction, revocation, poisoning, tampering, cancellation and replay negatives pass.
- Dry-run promotion evaluator vetoes synthetic-only “live promotion,” corrupted manifests, unapproved reviewers, source drift, missing paired eligible tasks and critical failures.
- Dry-run canary and rollback leave runtime flags/storage/lifecycle unchanged; `fixed` remains default and MEM-3 capture/selection hard-disabled.
- No unknown source/provider cost or native verification is reported as observed. Existing gate failures remain recorded.
- Focused tests, relevant regression tests, lint, source/naming policy and docs checks pass or are explicitly reported failing without concealment.

### B. Scientific/phase exit — NOT automatically conferred by A

Independently reproducible **real end-to-end** task-quality improvement over appropriate matched baselines, adequate uncertainty/control against contamination, bounded native/model/maintenance resources, no critical safety regressions, and separately approved local/live/deployed evidence for the supported rollout profile. Independent blind/challenge and E5 longitudinal tasks are required; E1 fixture success is insufficient. If unavailable, mark `IMPLEMENTED_E1_RESEARCH / PHASE_EXIT_BLOCKED`, do not “accept” the full MEM-6 claim.

### C. Live promotion — separately approved future decision

Live effective policy selection only after prior source/identity/forget, original-key replay, provider-send and strict-free billing, native/cloud recovery/deletion, independent reviewer, canary/rollback and final owner approvals. The promotion mechanism should not be built as a usable hidden switch in this phase. If a later policy fails any critical safety gate, rollback and halt promotion regardless of mean utility.

## 6. Explicit inherited blockers and deferrals

| Blocker | What can proceed now | What stays blocked |
| --- | --- | --- |
| MEM-3 issuer/capture/selection hard-disabled | Synthetic longitudinal events and versioned references | User/agent episodes as real trusted learning data |
| MEM-4 pending-only proposals | Proposal quality study under diagnostic labels | Auto-approval, trusted injection and live consolidation |
| MEM-5 no supported real semantic/hybrid arm and no blind cohort | Author-visible lexical/topic/adaptive ablations; plug-in contracts for future comparison | Claiming hybrid superiority or independent task lift |
| `planning-eval` inherited source-lock failure | New additive research source-generation identity and explicit failure note | Rebinding historical lock or claiming complete regression PASS |
| No disposable PostgreSQL DSN here | Hermetic E1, native adapter tests prepared | Fresh native E2 PASS claim |
| HXE-2 live model evidence incomplete | Consume compatible measurement format; zero-transport synthetic study | Real-model/provider cost, live free-tier and E5 claims |
| PI-5 permission/source leases; PI-7 restore/deletion; MEM-2 default-off | Deterministic deny/revoke/replay fault suite | External disclosures, autonomous promotion and production |
| Owner’s MEM-3+ development freeze | This self-contained implementation **plan** and bounded prompt | Assumed release permission from plan/request alone |

**Dependency rule:** Do not defer any deterministic E1 package, fault test, negative-control scorer, manifest hashing or dry-run governance logic just because an unrelated E3/E4 gate is open. Conversely, do not turn the research package into a backdoor around those gates.

## 7. Test plan and commands

Suggested new enduring task names: `make memory-research-check` and `make memory-research-eval` (subject to repository naming conventions). Run:

- New contract/manifest/scorer/driver/fault/decision unit and property tests.
- `make memory-task-eval memory-knowledge-eval memory-control-eval memory-navigation-check memory-navigation-eval` where supported.
- Focused `backend/tests/test_memory*.py`, research/context/authorization/usage tests and the relevant persistence smoke (no destructive DB commands).
- `make backend-lint naming-policy-check`; `make backend-test-offline` where practical.
- `make planning-eval` as a known inherited boundary check; do **not** “fix” historical identities incidentally.
- If a disposable DSN is already configured and approved: a narrowly scoped native component test with a private namespace and evidence tier recorded. No cloud, hosted provider or production data calls.

The final report should include commands, exact exit codes, environment and commit, test counts, failure causes and provenance to retained outputs. Running tests that rely on unavailable infrastructure is not proof of failure of the E1 package; unsupported native acceptance must remain explicitly blocked.

## 8. Sequencing and schedule (milestone-based)

| Increment | Deliverable | Gate |
| --- | --- | --- |
| 0 | Re-pin and harden plan; authority/gap matrix | No mutation before reconciliation |
| 1 | Immutable manifest and run receipt contracts | Hash, scope, version and tamper tests |
| 2 | Multi-session synthetic dataset and evaluator | No labels in driver; complete denominator |
| 3 | Supported ablations, uncertainty and adversarial suite | Matched-control and safety-veto tests |
| 4 | Decision proposals, simulated canary/rollback, rejected-hypothesis ledger | No effective runtime write |
| 5 | Full E1 replay, regression, reports and review handoff | Separate implementation versus phase-exit evidence |
| Future | Independent challenge, E2/E3/E4/E5, user-approved effective canary | Explicit owner/reviewer/evidence gate |

## 9. Independent review focus

The separate Sol review must *not* assume the plan was correct. It must attempt to falsify:

- Does the benchmark measure **new task outcomes**, or is answer matching/correlated replay disguised as a quality claim?
- Could rubric/expected answers leak through task IDs, fixtures, source cards, driver, filenames or feedback?
- Are unsupported arms handled honestly, especially MEM-5 fixed/semantic/hybrid?
- Are comparison rights, tool support, prompt packing and provider budgets genuinely matched?
- Does the unit of independence avoid inflated sample size across repetitions?
- Could a forged manifest, stale snapshot, revoked grant or poisoned memory generate a positive promotion verdict?
- Is research metadata improperly reused as an authorization or memory storage authority?
- Does dry-run promote/rollback perform even one effective write or weaken default flags?
- Does the phase declare scientific success without E2/3/4/5 evidence or independent review?
- Are all negative results, drift and incomplete rows preserved, and is rollback traceable?

Review output must be one actionable, severity-ordered Markdown Luna High/XHigh remediation handoff, with exact files/functions, reproductions, safe fix requirements, focused tests and post-fix verification. No additional independent review is planned after Luna review fixes/final verification unless a new critical scope expansion is discovered.

## 10. Codex handoff contract

Sol High implementation will: review/harden this plan in the **same session**, use no subagents, implement bounded E0/E1 fully, test, self-review, document exact limits, and stop with a commit-ready working tree but no push/deployment. A separate Sol High session independently reviews and produces one self-contained remediation document. Luna High/XHigh addresses findings and performs final verification; do not silently classify unavailable external evidence as fixed.

The attached implementation and independent-review prompts are complete standalone alternatives for their respective sessions and do not require this file to be attached again, although it is a useful reference.

## References

- [Repository and latest reviewed code](https://github.com/jasonkli21/personal-ai-system/tree/619d724bd91d9f633714b576a3fef8e7a8841b6d)
- [MEM-5 remediation and open gates](https://github.com/jasonkli21/personal-ai-system/blob/619d724bd91d9f633714b576a3fef8e7a8841b6d/docs/memory/2026-11-04-retrieval-remediation.md)
- [MEM-5 research implementation receipt](https://github.com/jasonkli21/personal-ai-system/blob/619d724bd91d9f633714b576a3fef8e7a8841b6d/docs/memory/2026-11-04-retrieval-implementation.md)
- [Current state](https://github.com/jasonkli21/personal-ai-system/blob/619d724bd91d9f633714b576a3fef8e7a8841b6d/docs/current-state.md)
- [Memory Architecture & Research Roadmap](https://chatgpt.com/library?file_id=libfile_64d40c950370819192c063a6c792e1f6&account_id=personal)
- [Integrated Harness Excellence Roadmap v3.1](https://chatgpt.com/library?file_id=libfile_c19a2a4a420c8191b0d9af3ebded9107&account_id=personal)


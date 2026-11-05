# Product Requirements Document: Dynamic Reasoning Engine

**Project:** `personal-ai-system`  
**Document ID:** `DRE-PRD-001`  
**Version:** 1.0 (proposed)  
**Date:** 2026-11-01 (America/Los_Angeles)  
**Decision:** Adopt a **dynamic, provider-independent reasoning planner**; retain bounded, free-first execution and explicit authorization.  
**Status:** Design proposal, **not** an implementation commitment, release gate closure, or assertion that the capabilities below exist.  
**Repository reference:** [`main` at `093e3b6816581e0b975e74e498dab99a2ac9a4b6`](https://github.com/jasonkli21/personal-ai-system/commit/093e3b6816581e0b975e74e498dab99a2ac9a4b6). Re-check the authoritative implementation and current-state documents before implementation.

## 1. Executive summary

Add a reusable **Dynamic Reasoning Engine (DRE)** to `personal-ai-system`. Applications request a user-facing reasoning effort (`auto`, `low`, `medium`, `high`, or `max`); the platform translates that request into a **bounded, task-adaptive execution policy**. It selects strategies and permitted tools dynamically, potentially decomposes work, gathers evidence, proposes and checks alternatives, revises selectively, and stops when sufficient or when a hard budget/policy boundary is reached.

This is **system-level inference-time reasoning**, distinct from any model vendor's native reasoning-token/effort control. DRE can use native controls where an installed, authorized adapter explicitly supports them, but it must also work with ordinary models lacking native reasoning. Its primary goal is to increase task quality from **free or mostly-free resources through better allocation of work**, not simply to increase output length or the number of model calls.

**Roadmap placement decision:** Preserve the full **PI-0 through PI-8 Platform Independence program** without adding DRE as a new PI completion criterion or renaming PI-8. Reuse PI-6's falsifiable harness and evaluation methodology; rely on PI-7's operating constraints and PI-8's independent readiness discipline. Execute DRE as a **separately scoped, versioned RE-0 through RE-5 program**. Design and offline benchmarks may proceed in parallel with PI-6 if explicitly segregated; provider-connected rollout must satisfy the applicable existing PI-3/5, source, billing, identity, persistence, and security gates. DRE is not a means of waiving those gates.

## 2. Product rationale

### 2.1 Problem

Ordinary free-tier models often have limitations in complex planning, multi-step reasoning, source evaluation, and error correction. Providing more prompt text or asking a model to “think harder” is an unreliable substitute for a verified workflow. Native reasoning effort varies by provider/model and is absent on many endpoints. Existing PAS capabilities (inference, routing, context, research, retrieval, tools, evaluation, and accounting) are substantial but lack one app-neutral control plane that allocates *reasoning work* across them.

### 2.2 Opportunity

Build **system intelligence** using task decomposition, bounded exploration, evidence-aware research, deterministic verification, selective revision, and measured allocation of test-time compute. The platform should prefer a high-value check or search to another unsupported round of self-critique. Higher effort authorizes *more* work, not arbitrary autonomy.

### 2.3 Jobs to be done

1. As an end user, I can select a familiar thinking level and receive a correspondingly appropriate level of analysis, without understanding model providers or internal algorithms.
2. As an app developer, I can request reasoning through a stable API without embedding a proprietary prompting loop or coupling to toy/reference apps.
3. As an operator, I can cap money, tokens, time, model calls, search requests, concurrency, and authorized destinations; `max` never bypasses those limits.
4. As an evaluator, I can compare reasoning strategies against a fixed baseline under matched budgets, with replayable policy identities and grounding/quality metrics.
5. As a user of a free-first system, I can see whether a request completed, stopped early, exhausted quota, or remained uncertain—without hidden paid or unauthorized fallbacks.

## 3. Explicit decisions and principles

| ID | Decision | Rationale |
|---|---|---|
| D1 | **Dynamic planner**, rather than a fixed `medium/high/max` sequence | Adapt strategy to task type, available evidence, model capability, and remaining budget; allows measured future improvements. |
| D2 | User effort is **provider-independent** | A native vendor effort flag is only an optional adapter capability and does not define platform behavior. |
| D3 | **Policy controls permissions; planner controls tactics** | More effort cannot authorize new data, tools, models, recipients, paid spend, or writes. |
| D4 | **Free-first, fail-closed** | No silent paid fallback or treating advertised free-tier pricing as verified account-specific eligibility. |
| D5 | **Verification before repetition** | Favor tests, calculations, schema checks, fresh evidence, and independently supported claims over repeated same-model critique. |
| D6 | **Reuse canonical PAS infrastructure** | No second chat lifecycle, routing/usage ledger, context assembler, search framework, memory store, task-confirmation mechanism, or app registry. |
| D7 | **Safe partial results** | Explicit stop reason and supported/unsupported claims when evidence or budget is insufficient. |
| D8 | **No broad autonomous agent framework in the initial release** | Bounded, auditable single-orchestrator workflows first; no implicit delegation, open-ended browsing, or unreviewed tool installation. |
| D9 | **No hidden chain-of-thought persistence requirement** | Store structured step purposes, evidence, checks, outcomes, and concise user-facing progress; do not require or expose private model deliberations. |

## 4. Experience and reasoning controls

### 4.1 User-facing effort levels

| Requested level | Intended behavior | Typical tasks |
|---|---|---|
| `low` | Prefer a direct, short execution; verify only where a deterministic check is necessary. | Extraction, straightforward summaries, routine chat. |
| `medium` | Balanced response; optional limited decomposition, retrieval, or validation when value is likely. | Ordinary explanation, moderate analysis. |
| `high` | Multi-step approach when warranted; targeted evidence/tools, verification and specific revisions. | Coding, research questions, nuanced comparisons. |
| `max` | Maximum **bounded** exploration: alternative plans, gap-oriented research and stronger cross-checks when useful. | Architecture design, difficult debugging, deep investigations. |
| `auto` | Detect task difficulty/risk and choose an effective policy under the same authority and configured ceiling. | Default. |

These are *behavioral intents*, not guarantees of call counts, latency, answer correctness, or a uniform mapping to proprietary model effort values. No effort level requires gratuitous model calls. Operator/app policy may narrow an effort request; if the effective level differs, the response must disclose that downgrade.

### 4.2 Orthogonal controls

- **Effort:** How much problem-solving work is justified?
- **Strategy:** Which approved reasoning procedure is appropriate? Initial public default is `auto`; administrator-reviewed strategies may be explicitly pinned for experiments.
- **Research availability:** Whether already-authorized sources/tools may be used; it is **not** itself a source grant. Product UI can expose “Research when needed,” subject to the existing consent/source-policy system.
- **Budget:** Explicit hard ceilings on time, model dispatches, token reservations, tool/search calls, concurrency, and cost. The effective budget is the **minimum of request, user, app, workspace, and operator limits**; omitted request values use safe operator defaults.

### 4.3 User-visible outputs

- Normal answer, with citations and provenance when applicable.
- Bounded progress states such as `planning`, `researching`, `checking`, `synthesizing` (avoid dumping private model reasoning).
- Completion or explicit partial/insufficient/unavailable status, stop reason, and meaningful caveats.
- Resource summary: effective effort, used model/tool calls, elapsed time, known/estimated tokens, and cost/quota status when available.
- Optional concise “what was checked” summary, distinguished from a guarantee of correctness.

## 5. Dynamic planning architecture

### 5.1 New logical owner

Introduce a small **reasoning orchestration domain**, provisionally `personal_ai/reasoning/`, with modules/contracts for: request policy, task characterization, strategy catalog, plan selection, step execution, sufficiency/verification, run state/recovery, and evaluation hooks. The exact package layout is a later implementation decision. Expose it via a narrow versioned public API or optional extension to existing app-neutral invocation contracts; do **not** make external consumers import private Python modules.

The DRE composes existing infrastructure:

| Existing owner | DRE's responsibility | Ownership boundary |
|---|---|---|
| `llm/` and approved execution profiles | Invoke models and optionally set supported native effort | Adapter owns serialization/capability and physical dispatch. |
| `routing/` and usage accounting | Choose eligible endpoints per typed subtask, reserve/settle use | DRE cannot invent billing, quota or disclosure authority. |
| `context/` | Prepare per-step bounded, authorized context | Preserve exact source dependencies and final-send revalidation. |
| `agents/research/iterative/` | Reuse gap assessment, source selection, budget and state-machine patterns | Do not convert a research-only contract into an unconstrained generic agent. |
| `search/`, `retrieval/`, read-only tools | Fetch authorized evidence with citations and rights/freshness | Tool availability is not user consent; source text is untrusted data. |
| `evaluation/` | Benchmark task outcome, quality/cost/latency and adversarial safety | Version and hold out measurements; never promote on synthetic success alone. |
| Existing task controls | Gate consequential domain mutations if ever invoked | Initial DRE **read-only/proposal-only**; no automatic writes. |

### 5.2 Runtime flow

1. **Admit request:** Verify authenticated actor/app/workspace, allowed operations, strict-free/paid opt-in policy, disclosure rights, budget and stable idempotency identity.
2. **Characterize task:** Use conservative deterministic heuristics first; optional classifier only when its own authorized invocation cost is justified. Identify factual freshness, computational/verifiable nature, ambiguity, complexity, and potential sensitivity.
3. **Select strategy:** Evaluate a closed, versioned strategy catalog against task features, eligible tools/models, remaining budgets and measured performance. No request-specified arbitrary plugin/import path.
4. **Create bounded plan:** Typed steps with purpose, dependencies, authority scope, success criteria, expected cost, stop conditions and maximum fan-out/depth. Cap the cost of planning itself.
5. **Execute one or more steps:** Route via existing provider admission; use source/tool ports where separately permitted. Never expand scope or send data to an endpoint solely because an earlier step recommended doing so.
6. **Verify and assess sufficiency:** Prefer deterministic or evidence-backed checks. Detect conflicts, missing constraints, unresolved subproblems, unsupported citations and stale sources.
7. **Adapt selectively:** Continue only when a permitted next step is likely to reduce a concrete uncertainty/defect, the budget can reserve it, and no policy/revocation condition has changed. Otherwise stop.
8. **Synthesize:** Produce a supported answer and safe status; retain structured run metadata and source dependencies through all applicable downstream response/history/replay paths.

### 5.3 Initial strategy families

| Strategy ID (conceptual) | Method | Strong verification signal |
|---|---|---|
| `direct` | One appropriately prepared generation | Contract/schema validation. |
| `decompose` | Split task into bounded subproblems and integrate | Constraint coverage and subproblem completion. |
| `critique_refine` | Draft, check against explicit criteria, revise defectively supported portions | Tests, validation, independently supported defects. |
| `candidate_compare` | Generate a small diverse set of approaches and compare | External scoring, constraints, independent checks; not mere majority vote. |
| `evidence_research` | Search/retrieve, identify gaps, fetch focused additional evidence, synthesize | Fresh provenance, citation support, source conflict resolution. |
| `tool_verify` | Solve with deterministic tool checks and fix measured failures | Test/calculation/schema outcomes. |

Strategies are composable but cannot form an arbitrary graph at launch. Version catalogs and bound graph depth, model invocations, external actions, and wall time. Do not assume same-model agreement establishes truth or that any self-reported model confidence is calibrated.

### 5.4 Adaptive-selection evolution

**V1:** Interpretable deterministic decision rules and fixed budget templates, with a safe baseline fallback.  
**V2:** Shadow-only measured strategy ranking using outcome and resource features.  
**V3:** Opt-in adaptive strategy selection promoted only after held-out, matched-budget quality/safety proof.  
**Later:** Optional learned policy or cross-model composition; remain versioned, explainable, bounded and rollbackable.

The planner must learn **which next step is worthwhile**, not simply how to consume the maximum budget. Evaluation should treat unnecessary calls as a regression.

## 6. Proposed API contract (illustrative, not implemented)

```json
{
  "message": "Analyze this architecture and identify failure modes",
  "reasoning": {
    "schema_version": "reasoning-request-v1",
    "effort": "high",
    "strategy": "auto",
    "research": "if_authorized",
    "budget": {
      "max_model_calls": 8,
      "max_tool_calls": 6,
      "max_elapsed_seconds": 90,
      "max_provider_cost_usd": "0.00"
    }
  }
}
```

- The example is a *request for ceilings*, not permission to raise them or a promise that 8/6 calls will occur.
- Validate enumerations and strict upper bounds; reject unknown fields. Existing authenticated scopes and app-specific contracts continue to determine tool and provider access.
- Support a separate response/run record with `run_id`, `schema_version`, `policy_version`, `requested_effort`, `effective_effort`, `selected_strategy_versions`, `budget_reserved/settled`, `state`, `stop_reason`, attribution, evidence references, verification outcomes and an opaque continuation/idempotency identity.
- Never expose raw chain-of-thought, provider secrets, credential references, full sensitive traces, or unapproved cross-app evidence as diagnostics.
- Compatibility: existing chat/research APIs should behave unchanged when reasoning is absent or default-off. Do not silently reinterpret historical receipts or source provenance.

## 7. Functional requirements

| ID | Requirement | Priority |
|---|---|---|
| FR-01 | Accept `auto/low/medium/high/max` via a versioned, provider-neutral request contract. | P0 |
| FR-02 | Resolve requested vs effective effort from operator/app/user limits; report narrowing. | P0 |
| FR-03 | Dynamic planner selects only installed, code-reviewed, capability-eligible strategies under a frozen versioned policy. | P0 |
| FR-04 | Permit direct, decomposition, bounded verification/revision and evidence-research execution; allow a no-tool, no-remote fallback only when it does not misstate completeness. | P0 |
| FR-05 | All physical inference and search/tool attempts use existing eligibility, exact data-disclosure and accounting checks; no hidden paid/network fallback. | P0 |
| FR-06 | Persist/reconstruct original run identity, reservation state and uncertainty; never re-send an uncertain external effect using a fresh key. | P0 |
| FR-07 | Explicit stop conditions: sufficient, budget exhausted, evidence insufficient, policy denied, provider unavailable, cancelled, uncertain effect and internal failure. | P0 |
| FR-08 | Propagate source grants, revisions, citations, deletion/revocation dependencies through planning, model context, synthesis and visible outputs. | P0 |
| FR-09 | Support cancellation, deadlines, bounded concurrency and finite fan-out; `max` always terminates. | P0 |
| FR-10 | Record structured task, strategy, verifier, usage, latency and safety observations without raw private reasoning. | P0 |
| FR-11 | A model-specific native reasoning control may be used only after capability and exact endpoint/profile validation; unsupported settings fail or use the independently authorized system strategy. | P1 |
| FR-12 | Provide safe progress events and partial results for longer tasks without changing canonical chat/research event semantics. | P1 |
| FR-13 | Support operator-pinned strategy variants and side-effect-free shadow evaluation, not unreviewed live auto-promotion. | P1 |
| FR-14 | Allow new third-party applications to use DRE through the same stable public boundary without core changes or reference-app imports. | P1 |
| FR-15 | Add adaptive selection from representative task-level evaluation, with rollback to a deterministic fixed policy. | P2 |

## 8. Nonfunctional and security requirements

1. **Authorization and privacy:** Verified owner/actor/app/workspace and purpose; source and destination sensitivity policy; revalidate at use and final physical send. No cross-app memory/profile widening, and no MEM-3+ feature expansion.
2. **Free-first semantics:** Strict-free requires current, exact provider/account/operation eligibility. If a call cannot be counted or reserved authoritatively enough, refuse it. “Free” may still consume quota and other infrastructure resources. `Max` cannot silently spill into BYOK/paid modes.
3. **No automatic consequential actions:** Initial DRE is read-only and proposal/analysis oriented. Future mutation requires the *existing* explicit confirmation and reconciliation lifecycle, not model output alone.
4. **Prompt-injection isolation:** Retrieved documents, websites and tool results remain untrusted evidence, never system instructions. No unreviewed shell, arbitrary URL, filesystem, tool or plugin execution.
5. **Boundedness:** Hard ceilings on total calls, iterations, depth, context/output tokens, search queries, sources, time, outstanding retries and concurrency. Reserve synthesis/answer budget so a deep run can still return a meaningful partial status.
6. **Recovery/idempotency:** Preserve stable original identities, uncertain attempts, immutable receipts and revocation fences across crashes, replay, export and restore. Do not claim distributed/native guarantees from local synthetic tests.
7. **Observability:** Safe, low-cardinality policy/strategy IDs, stop reason, estimated vs reported usage, quota pressure, objective verifier outcome and latency. Avoid persisting model private reasoning or unredacted external text into telemetry.
8. **Extensibility:** Clean dependency direction: app -> published platform contract -> DRE -> existing neutral ports -> installed adapters. DRE must function with zero toy/reference apps and with the offline fake execution profile.

## 9. Success criteria and evaluation

### 9.1 Evaluation methodology

- Reuse PI-6's versioned tasks, fixed baseline, no-memory/retrieval/routing comparisons, held-out or blinded cases, and exact fixture/runtime/model identities.
- Compare *task outcome at matched resource budgets* and quality-per-cost, not raw answer length, subjective “depth,” or synthetic pass rates alone.
- Partition cases by task type and difficulty (simple Q&A, evidence-grounded research, multi-constraint planning, software/debugging, numeric/deterministic checks, sensitive/privacy adversaries, and provider/tool failure).
- Include adversarial cases for stale/revoked sources, prompt injection, incorrect self-critique, correlated model mistakes, quota exhaustion, deadline interruption, cancellation, retries, unknown external effects, and duplicate sends.
- Any adaptive policy promotion requires predeclared thresholds, repeated paired trials and uncertainty/error bars; distinguish offline fakes from real authorized model/provider evidence.

### 9.2 Outcome and guardrail measures

| Class | Measures | Gate interpretation |
|---|---|---|
| Quality | Correct task completion, constraint satisfaction, factual grounding, supported citations, reproducible test success | Demonstrate statistically credible lift in target hard-task segments; no unexplained regressions on simple tasks. |
| Efficiency | Model/search/tool calls, token reservations and settled use, free-tier pressure, P50/P95 latency, work after sufficiency | The engine should stop early; quality gain must justify overhead. |
| Reliability | Provider failure handling, correct partial/unavailable status, cancellation, durable recovery, no duplicate physical effects | No silent retry on uncertain dispatch or unsupported “completed” states. |
| Security | Unauthorized disclosure, app/workspace crossover, stale/revoked source use, tool permission escalation, paid fallback | **Zero known violations**; block launch on any verified P0/P1 defect. |
| Transparency | Accurate effective effort, strategy identity, stop reason, verifiability and usage confidence | Explanations must not claim unperformed steps or guaranteed truth. |

Before RE-1, set explicit numerical goals and sample sizes in an evaluation plan using measured baseline variance; avoid inventing percent-lift promises now.

## 10. Relationship to Platform Independence PI-0 through PI-8

**Decision:** DRE is a **post-independence product capability**, not a ninth item retroactively required to close PI-8. Keep current PI acceptance requirements intact. Treat it as a new program that consumes the platform after its boundaries have been established.

| PI phase | Relation to DRE | Scope boundary |
|---|---|---|
| PI-0 / PI-1 | Defines independence and standalone core | DRE must not reintroduce toy-app imports or domain coupling. |
| PI-2 | Public, separately installed consumer contract | DRE uses the versioned authenticated API; no private module imports or implicit identity. |
| PI-3 | Provider-neutral inference, strict-free admission and accounting | DRE reuses approved execution profiles; native reasoning is a later opt-in capability, not a new provider loophole. |
| PI-4 | User-governed cross-app profile/context | DRE can use only explicit, current grants and existing MEM-0/1/2 semantics. |
| PI-5 | App-neutral search/retrieval/read-only tools | DRE reuses evidence and source rights; *current* completion is `blocked_unverified`, so external/model-bound paths remain gated. |
| **PI-6** | **Benchmark and measurement foundation** | Establish matched-budget, task-level evaluation and negative suites. DRE benchmark design/offline prototypes may be parallel work but do **not** expand or satisfy PI-6 by assertion. |
| **PI-7** | **Operational prerequisites** | Supply reproducible local/free-first setup, caps, metering, recovery and deployment acceptance. DRE must consume these; it is not a required PI-7 deliverable. |
| **PI-8** | **Independent baseline platform readiness audit** | Audit existing promised platform boundaries. If DRE has been separately enabled before PI-8, audit its affected paths explicitly; do not quietly move the PI-8 finish line. |

### 10.1 Scheduling and gates

- **Now / during PI-6:** Finalize this PRD, create a separate DRE architecture/evaluation plan, add *isolated* offline task suites or experiments where authorized. Clearly label their non-production status and do not weaken PI-5 or PI-6 locks.
- **During PI-7/PI-8:** Consume the operational/independent findings to harden DRE contracts. Keep this work off the PI critical path unless an existing safety defect is implicated.
- **After stable prerequisites:** Implement and accept RE stages independently, with default-off flags and explicit operator authorization. An offline RE prototype need not wait for every unrelated cloud gate, but **live provider/search/derived-context release** must meet the applicable current source/physical-send/billing/identity/recovery gates.
- **Do not equate progress with acceptance:** The current PI-5 completion gate is `blocked_unverified`; PI-6 Stage G/G5 cannot be represented as satisfied while that gate remains. Work can be planned and measured with documented limitations; no release evidence is silently assumed.

### 10.2 Documentation placement

Store future DRE-specific product/architecture/implementation/review records under a dedicated `docs/reasoning-engine/` directory, with a small cross-link from `docs/platform-independence/README.md` when work is authorized. Avoid copying or rewriting historical PI evidence. This PRD is a standalone proposal and has **not** modified the repository.

## 11. Recommended DRE delivery program

| Stage | Deliverables | Exit gate |
|---|---|---|
| **RE-0: Design and benchmarking** | Versioned PRD/API/ADR, threat model, strategy registry specification, offline quality/cost fixtures and frozen baseline | Clear ownership and safety invariants; no new live dispatch. |
| **RE-1: Control contract + native capability plumbing** | Default-off reasoning request/effective policy, telemetry, explicit model-native capability mapping, strict-free accounting proof | Existing chat/consumer behavior unchanged; unsupported effort cannot cause covert execution. |
| **RE-2: Bounded orchestrator** | Deterministic strategy selector, `direct`, `decompose`, `critique_refine`, `tool_verify`; durable run and stopping | Finite budgets, safe recovery/cancellation, objective improvement under paired tests. |
| **RE-3: Grounded iterative reasoning** | Connect existing research/retrieval authority, evidence gaps, citation-aware synthesis and selective follow-up | No ungrounded promotion; source revocation/send and existing PI-5 release gates satisfied for any enabled path. |
| **RE-4: Adaptive selection** | Shadow strategies, task features, measured selection and rollback; optional capped candidate comparison | Held-out lift at matched budget, zero known safety regressions and no unverified promotion. |
| **RE-5: Production/extension hardening** | Long-run UX, quotas/fairness, independent external consumer, native/cloud recovery where in scope, independent adversarial review | Independently reproduced task utility, admission, authorization, operational and rollback evidence. |

Each stage gets its own implementation plan, bounded Codex handoff, independent review, remediation and objective acceptance record. Do not combine RE-0–5 into one large unreviewed phase.

## 12. Non-goals and deferrals

- Training/fine-tuning or hosting new local foundation models merely to support reasoning.
- Assuming free providers are always available, that model-native effort exists universally, or that all effort levels have identical semantics across models.
- Arbitrary agent spawning, unrestricted background browsing, recursive autonomous exploration, dynamic code imports, or unapproved side effects.
- Replacing LiteLLM, the existing inference gateway, routing ledger, context planner, source/rights authority, search/research services, memory, or task-control machinery.
- Adding MEM-3+ features or implicitly merging app-private records into shared memory.
- Guaranteed correctness from `max`, majority vote, model self-confidence or unverified critique loops.
- Requiring raw private chain-of-thought capture/display, or persisting hidden vendor deliberation as an audit substitute.
- Premature online self-optimization without a versioned frozen baseline, safety gates, and rollback path.

## 13. Open design questions for RE-0

1. **Strategy-selection features:** What minimal non-sensitive task descriptors and verification signals predict benefit from extra steps? Start with explainable heuristics; evaluate learned alternatives later.
2. **Budget portfolio:** How should a cap be divided between planning, research, generation, independent checking, and synthesis, especially under free-tier scarcity? Reserve final answer resources.
3. **Sufficiency policy:** Which tasks have objective success predicates, and how is uncertainty represented when none exist? Avoid equating a verifier model's assertion with proof.
4. **Native model effort:** Which exact, installed profiles can accept provider-native effort and count all relevant tokens/attempts under current admission requirements? Never assume generic cross-provider compatibility.
5. **Run lifetime:** Which existing durable run/continuation interfaces can be reused versus introducing one small DRE-specific, compatible record? No second general chat lifecycle.
6. **Research policy UX:** Should “Research when needed” be a default-on *preference* only when an explicit, already-authorized source exists, or default-off until selected? Either way it cannot create a grant.
7. **Promotion criteria:** Which real-model evaluation subsets and error bounds justify higher-cost strategies and adaptive selection? Pre-register before implementation.

**Recommended defaults:** `auto` effort; fixed deterministic strategy baseline; strict-free execution with zero paid fallback; research only through existing grants; read-only/proposal-only operations; conservative early stopping; exhaustive structured status and resource accounting; DRE disabled in production until independently accepted.

## 14. Source references and evidence limits

Repository documents as of the reference commit:

- [Platform Independence architecture charter and PI-0–PI-8 roadmap](https://github.com/jasonkli21/personal-ai-system/blob/093e3b6816581e0b975e74e498dab99a2ac9a4b6/docs/platform-independence/platform-independence-roadmap.md)
- [Current implemented state and freeze/gate status](https://github.com/jasonkli21/personal-ai-system/blob/093e3b6816581e0b975e74e498dab99a2ac9a4b6/docs/current-state.md)
- [PI-5 completion gate (`blocked_unverified`)](https://github.com/jasonkli21/personal-ai-system/blob/093e3b6816581e0b975e74e498dab99a2ac9a4b6/docs/platform-independence/pi-5-completion-gate.md)
- [Research orchestration, bounded iterative run and budgets](https://github.com/jasonkli21/personal-ai-system/blob/093e3b6816581e0b975e74e498dab99a2ac9a4b6/backend/src/personal_ai/agents/research/README.md)
- [Provider-neutral inference and current PI-3 admission boundaries](https://github.com/jasonkli21/personal-ai-system/blob/093e3b6816581e0b975e74e498dab99a2ac9a4b6/backend/src/personal_ai/llm/README.md)

External supporting work (architecture inspiration, **not** proof of performance for PAS):

- [OpenAI API reasoning models and effort controls](https://developers.openai.com/api/docs/guides/reasoning)
- [Anthropic thinking and effort controls](https://platform.claude.com/docs/en/build-with-claude/thinking)
- [ReAct: Synergizing Reasoning and Acting in Language Models](https://arxiv.org/abs/2210.03629)
- [Self-Consistency Improves Chain of Thought Reasoning](https://research.google/pubs/self-consistency-improves-chain-of-thought-reasoning-in-language-models/)
- [PlanGEN: Inference-Time Algorithms for Planning and Reasoning](https://research.google/pubs/plangen-a-framework-utilizing-inference-time-algorithms-with-llm-agents-for-planning-and-reasoning/)

**Evidence boundary:** Source inspection confirms reusable existing code and open gates. It does **not** establish that native effort portability, DRE, multi-step model execution, connected live provider eligibility, deployed retrieval authority, or material quality improvement has been delivered. Those are future acceptance claims to be independently demonstrated.

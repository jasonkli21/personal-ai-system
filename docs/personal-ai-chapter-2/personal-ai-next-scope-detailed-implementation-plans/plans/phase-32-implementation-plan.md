# Phase 32 implementation plan — Smarter context planning

Renumbered from former Phase 24. This revision preserves the baseline-before-LLM-planning, strict-free, permission, rollback, and measurement requirements while making the planner contracts, experiment methodology, promotion rules, resource accounting, and trace semantics explicit.

## Scope boundary

**Goal:** Improve macro-level context selection only where measured deterministic-planning failures justify additional planning intelligence.

Phase 32 optimizes **what categories/providers/scopes of context should be retrieved for a request**. It does not optimize the internals of web/evidence retrieval (Phase 33), memory candidate retrieval/ranking/consolidation (Phase 34), or model/endpoint routing (Phase 35).

### Normative commitments

- Benchmark the implemented deterministic planner before introducing assisted planning.
- Measure omitted relevant context, irrelevant over-fetch, sensitive/unauthorized proposal attempts, token/byte use, planning latency, downstream supported-answer quality, and total planner resource cost.
- Add LLM-assisted planning only for task classes where measured failures justify it.
- Route any planner inference through the existing strict-free inference/runtime/accounting path; planner inference is a real admitted model operation, not hidden free work.
- Keep authentication, authorization, application/workspace membership, grants, source eligibility, sensitivity, provider privacy eligibility, and all hard policy constraints outside the model.
- Give the model only minimized, already-authorized planning metadata; the planner must not fetch arbitrary source contents merely to decide whether to request them.
- Make assisted output typed, bounded, versioned, and server-validated.
- Preserve a deterministic strategy as baseline, fallback, and rollback.
- Compare quality improvement against added planning calls, tokens, quota consumption, and latency.
- Persist/reconstruct enough safe planning evidence to reproduce why a deterministic plan, assisted proposal, validation result, and final plan differed.
- Default assisted planning off until promotion evidence exists for a declared task/application coverage.
- Never recursively invoke the same assisted-planning path from planner inference.

### Acceptance criteria

A planner variant may be promoted only for declared covered tasks when paired held-out evaluation demonstrates a meaningful improvement over the deterministic baseline without authorization, sensitivity, provenance, resource-budget, or strict-free regression. Invalid, unavailable, timed-out, or rejected assisted planning deterministically returns the baseline or a policy-narrower result.

## Role in the request pipeline

Conceptually:

```text
authenticated RequestScope
        ↓
hard application/workspace/policy eligibility
        ↓
task + available authorized capability descriptors
        ↓
deterministic ContextPlan baseline
        ↓
(optional, promoted task classes only)
bounded assisted planning proposal
        ↓
server validation / narrowing
        ↓
final ContextPlan
        ↓
authorized provider retrieval
        ↓
shared ContextBuilder
```

The model may **propose selection**; it never authorizes source access.

## Current state and reuse

Phase 13 supplies deterministic context-planning behavior and fixtures. Phases 14–15 provide provenance, permissions, sensitivity, and revocation semantics. Phases 26–30 provide implemented domain/federation provider traces and realistic cross-app planning cases. Phase 19 supplies admitted usage/quota accounting. Phase 22 supplies evaluation identity/fixtures.

Do not introduce a second planner architecture. Extend the existing planner/plan/builder/provider seams generically.

## Prerequisites

Required phases: 22 and 30, plus standing Phase 10 persistence and implemented Phase 13/15 planner-policy foundations.

## Invariants

- No model call where deterministic rules meet the declared quality threshold.
- Registration or discoverability never grants permission.
- Assisted planning cannot add a provider, application, workspace, export category, field, entity, purpose, time window, or operation outside the already-authorized planning envelope.
- Invalid proposals fail closed to deterministic planning; they never broaden access.
- Most-restrictive effective sensitivity and current grant/policy state remain binding.
- Revocation/membership changes are revalidated before retrieval and before model disclosure.
- Planner inference cannot recursively call assisted planning.
- Planner inference cannot dispatch tools, domain APIs, arbitrary search, or direct database access.
- Strict-free exhaustion cannot silently enable paid/BYOK/ChatGPT lanes.
- Historical plans are evidence of prior decisions, not current authorization.

## Planner contracts

### `PlanningRequest`

The exact code shape may follow existing repository conventions, but the logical contract must include bounded, non-secret facts sufficient for selection:

- authenticated owner-derived request identity by safe reference;
- `application_id` and optional `workspace_id`;
- task identity and typed task requirements;
- deterministic baseline plan/version;
- available **already policy-eligible** context capability descriptors;
- provider/source class identifiers;
- allowed categories/fields/entity-scope shapes, represented as bounded capability metadata rather than source contents;
- effective sensitivity ceiling;
- token/source/item/time budgets;
- freshness/time-window constraints;
- cross-app grant/export descriptors when applicable;
- relevant policy/grant/source-version references;
- planner strategy/version;
- request deadline and permitted planner resource budget.

The assisted planner must not receive raw credentials, unrestricted source catalogs, arbitrary domain rows, or sensitive source bodies solely for planning.

### `ContextPlanProposal`

Assisted output must be a typed proposal containing only bounded selection decisions, for example:

- provider/capability ID;
- category/source class;
- requested fields from the supplied allowlist;
- entity selector from the supplied bounded schema;
- time window/freshness requirement;
- item/source/token cap;
- optional priority/utility estimate;
- compact rationale/reason code;
- proposal schema/version.

Free-form text is non-authoritative. Unknown IDs, fields, selector types, or caps are rejected.

### Server validation

Validation must independently enforce:

1. authenticated request/application/workspace scope;
2. provider registration and runtime availability;
3. current policy and source eligibility;
4. cross-app grants and source-domain policy;
5. field/entity/category allowlists;
6. sensitivity constraints;
7. source/item/token/time budgets;
8. downstream builder/provider capabilities;
9. current revocation/membership state;
10. no widening relative to the authorized planning envelope.

Validation may narrow a proposal. It must not infer new permission from the model rationale.

### `PlanningTrace`

Record a privacy-safe, versioned trace sufficient for evaluation/debugging:

- request/task/profile identity;
- deterministic strategy/version and baseline plan;
- assisted strategy/model/profile/version when called;
- minimized input-feature identity/configuration, not necessarily raw contents;
- proposal;
- accepted/rejected/narrowed elements with reason codes;
- final plan;
- policy/grant/source dependency versions;
- planner tokens/usage/latency;
- downstream retrieval/context metrics;
- evaluation identity and outcome references.

Bulky permitted raw experiment artifacts follow the Phase 20 artifact tier; compact searchable summaries remain in Postgres under the Phase 10 ownership contract.

## Evaluation design

### Baseline corpus

P32.0 must add held-out fixtures spanning:

- single-domain requests;
- cross-app federation cases;
- tasks requiring no personal context;
- tasks requiring memory plus domain context;
- tasks where recent conversation is sufficient;
- freshness-sensitive requests;
- sparse-source requests;
- intentionally ambiguous requests;
- high-sensitivity eligible and ineligible cases;
- revoked/expired grants;
- large available-source catalogs under tight token budgets.

Keep related conversations/fixture families together across train/tuning/test boundaries if any learned or model-tuned policy is used.

### Metrics

At minimum measure:

- relevant-source/category omission rate;
- irrelevant selected-source/category rate;
- sensitive or unauthorized proposal attempt rate;
- validation rejection/narrowing rate;
- selected item/source count;
- input bytes/tokens ultimately assembled;
- planner input/output tokens and invocation count;
- total strict-free quota consumed by planning;
- planning latency and total request latency;
- downstream supported-answer quality;
- downstream evidence/source coverage where applicable;
- deterministic/assisted agreement;
- fallback rate and reason;
- task/application-specific coverage.

### Promotion thresholds

P32.0 must write explicit numeric or categorical thresholds before promotion. The exact values are evidence-driven, but the criteria must include:

- no authorization/sensitivity regression;
- no unsupported source expansion;
- no strict-free cost-mode regression;
- statistically or practically meaningful omission/quality improvement on the declared coverage;
- bounded over-fetch;
- acceptable total token/quota/latency overhead;
- sufficient sample/fixture coverage;
- successful deterministic rollback.

A planner call that saves context tokens but consumes greater model quota/latency without downstream quality benefit is not an improvement.

## Work packages

### P32.0 — Deterministic failure baseline and experiment contract

Freeze/version the current deterministic planning strategy and extend evaluation fixtures with implemented domain/federation selections plus held-out tasks.

Measure omission, irrelevant/sensitive over-fetch, source/item/token use, latency, supported-answer quality, and planning/retrieval resource use. Categorize observed failures rather than assuming an LLM is required.

Define:

- candidate task/application coverage for experiments;
- `PlanningRequest`, `ContextPlanProposal`, validation, and trace schemas;
- permitted planner input features;
- resource budgets for planner inference;
- promotion thresholds;
- explicit cases where deterministic planning is already sufficient and assisted planning must not run.

**Acceptance:**
- A versioned baseline identifies concrete failure classes and metrics.
- Promotion criteria are written before assisted results are judged.
- No mandatory LLM planner is assumed.
- Offline fixtures prove the authorized planning envelope cannot be widened by proposal shape.

### P32.1 — Bounded assisted planner behind existing seams

For justified cases only, implement an assisted strategy behind the existing planner strategy seam.

Use minimized authorized planner metadata and the strict-free runtime/accounting path. Require structured output matching the proposal schema. Apply deterministic server validation/narrowing before any provider retrieval.

Prohibit:

- arbitrary tools;
- direct domain DB/API access;
- new source discovery outside registered eligible capabilities;
- all-app/profile dumps;
- planner recursion;
- unaccounted inference;
- policy decisions based on model rationale.

Timeout, malformed output, unavailable endpoint, exhausted planner quota, schema mismatch, or validation failure must return the deterministic baseline or a narrower safe result.

**Acceptance:**
- Assisted planning cannot authorize new access.
- Every planner inference is admitted/accounted like other model operations.
- Invalid/unavailable assisted planning falls back deterministically.
- Planner traces distinguish proposal from server-approved final plan.
- Recursive planner invocation is impossible by contract/test.

### P32.2 — Paired evaluation, promotion, and rollback

Run paired held-out comparisons between deterministic and assisted strategies.

Evaluate end-to-end, including planner overhead. Slice results by task/application/source pattern rather than promoting globally from aggregate gains.

Version promotion policy. Keep assisted planning default-off until evidence meets thresholds. Allow selective promotion only to covered task/application classes.

Test:

- timeout/unavailability;
- quota exhaustion;
- endpoint removal/config changes;
- stale policy/grant versions;
- revocation between planning and retrieval;
- malformed and adversarial proposal fields;
- excessive requested budgets;
- deterministic rollback.

**Acceptance:**
- Any promoted coverage has paired held-out evidence showing net benefit.
- Unsupported coverage remains deterministic.
- Rollback requires no planner/provider/builder architecture rewrite.
- No authority/sensitivity regression exists in negative fixtures.

### P32.3 — Planner observability and maintenance hooks

Expose compact diagnostics for development/evaluation:

- why assisted planning ran;
- baseline vs proposal vs final plan;
- rejection/narrowing reasons;
- resource overhead;
- task/application coverage;
- experiment/promotion version.

Do not expose sensitive planner inputs or raw private source metadata in ordinary telemetry. Keep user-facing inspection aligned with existing provenance/context-inspection semantics rather than creating a second debugging model.

**Acceptance:**
- A failed or surprising plan can be explained from safe versioned trace data.
- Telemetry redaction and retention follow existing policy.
- Experiment identity is reproducible.

## Requirement coverage

All former Phase 24 commitments remain represented: evaluate deterministic misses/over-fetch; add assisted planning only where justified; route planner calls through strict-free runtime; keep permissions outside the model; compare quality/token/latency; preserve deterministic fallback. This revision adds explicit contracts, accounting, evaluation, promotion, trace, and recursion safeguards without changing the phase's role.

## Explicit non-goals

- Replacing deterministic authorization or policy with an LLM.
- Web/search retrieval ranking or evidence compression (Phase 33).
- Memory candidate retrieval, lifecycle maintenance, or consolidation (Phase 34).
- Learned endpoint/model routing (Phase 35).
- Autonomous tool execution.
- New domain providers or cross-app permissions.
- Paid/BYOK planner fallbacks.
- A general-purpose agent planner framework.

## README maintenance

Review the repository-root `README.md` before closing this phase. Update it only if implementation changes the truth of user-visible capabilities, architecture, technology stack, prerequisites, local setup, cloud deployment, provider support, or current project status. Keep experiment mechanics in detailed docs.

## Targeted verification and closeout

Run applicable backend/frontend tests, lint, typecheck, build, established evaluation commands, and `git diff --check`.

Use deterministic fakes and synthetic fixtures by default. Credentials/network/private domain data must not be required for offline coverage. External provider/cloud/domain checks are opt-in and skipped checks remain **unverified**, not passed.

Implementation evidence must record:

- actual files/interfaces;
- baseline and assisted strategy versions;
- tested revision/configuration;
- commands/results;
- promotion thresholds and observed metrics;
- planner resource accounting;
- disabled gates;
- unresolved external checks;
- exact promoted task/application coverage, if any.

Completion requires every normative commitment and work package to be locally verified. Externally gated behavior may remain unavailable with the gap explicit; it may not be described as complete.

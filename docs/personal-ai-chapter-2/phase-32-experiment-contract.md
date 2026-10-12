# Phase 32 experiment contract — v2

Declared 2026-10-12 before running the Phase 32 benchmark. This contract is not a promotion record.

## Frozen control

Control: `deterministic-context-planner-v1`, maximum source allocation 1,200 tokens,
configured rules from the canonical deployment contribution catalog plus built-in
rules. The benchmark records the configuration fingerprint, fixture digest, tested
Git revision relationship, material source digest, full Python runtime, platform,
and installed distribution inventory digest. A changed algorithm/configuration or
runtime requires a new baseline, never an overwritten historical result.

## Coverage and decision rules

Held-out synthetic task families include literal and paraphrased profile/memory
recall, no-personal-context, conversation-sufficient, negated retrieval, unshared
profile, unavailable implementations, and registered domain/entity rules.
Phase 13's synthetic field/window/budget/ambiguous fixtures and existing domain
and federation regression suites are supplemental contract evidence, not live
source or model-answer evidence. Related variants remain in the same family;
no training or tuning uses the held-out corpus.

Promotion policy `context-planning-promotion-v1` requires, **per task/application
slice**, at least 100 independent held-out families; zero unauthorized selections,
sensitivity violations, unsupported expansion or non-STRICT_FREE dispatches;
at least 10 percentage points less relevant-category omission and at least 5
percentage points more supported downstream answers; irrelevant selection rate
at most 5% and at most 1 percentage point above control; total model tokens/quota
at most 110% of control, at most one extra physical planner call per request;
p95 end-to-end latency at most 120% of control and planner latency at most 500 ms;
zero malformed-output access widening; and successful deterministic rollback.
Unsupported counterfactuals, unmeasured provider quota, and unmeasured downstream
answers remain missing. Missing metrics or insufficient families deny promotion.
A source-selection/support proxy is not a measured model-answer quality score.

## Four artifacts

1. `ContextPlan`: frozen deterministic strategy/version/configuration and scoped
   retrieval baseline; not an authorization grant.
2. `PlanningRequest`: v1 is explicitly a **narrowing-only validation experiment**,
   not an assisted-selection request and not eligible for model inference. Bounded
   metadata is produced only after shared policy and provider authority preflight;
   opaque choice IDs resolve to exact server-held selections. It contains no task
   semantics and cannot recover omissions by manufacturing access. A future
   assisted-selection contract must be separately versioned and authorized before
   any model call. It must define privacy-reviewed typed task/profile features and
   a candidate envelope already independently eligible under current policy,
   grants, sensitivity, and provider authority. It must not include raw intent,
   source bodies, credentials, raw entity/grant IDs, or an unrestricted catalog.
3. `ContextPlanProposal`: bounded IDs, allowlisted fields and caps only. Exact
   entities, federation purpose/grant, windows and scope stay server-held. Extra
   keys, unknown IDs/fields, duplicate choices and excess caps fail validation.
4. Server-approved final plan plus `PlanningTrace`: independently repeats current
   policy, scope, capability/spec availability and registered authority preflight.
   Typed dependency versions distinguish validation state from exact source and
   permission revisions observed after retrieval. Each known proposal choice records
   accepted, narrowed, rejected, or retained disposition with a reason code.
   Bound validation traces can be reduced to per-case proposal-attempt, rejection,
   narrowing, fallback, and unauthorized-attempt measurements. When no such trace
   was recorded, those measurements remain unknown.
   Required selections cannot be removed. Builder/provider checks still run at
   retrieval and disclosure. Compact diagnostics reuse existing context traces;
   experiment records are synthetic files, not a private production dataset.

The v2 held-out corpus adds an authorized 16-provider catalog under a tight token
budget and exact trip-source revision transitions with complete and partial
observations. Grant epoch, export-consent, membership/source-policy, revocation, and
expiry states are separate synthetic benchmark rows. They do not establish live
store race acceptance or independent-family sufficiency for promotion.

The evaluation runner accepts Phase 22 quality evidence only when the strategy,
configuration, exact assembled-context digest, and tested revision match the row.
Quality evidence includes the scorer's hard-boundary outcome. The current
deterministic corpus has no observed downstream answer or validation-trace evidence;
these fields remain explicitly unmeasured and block promotion.

## Resource and inference boundary

Permitted initial planner inference budget is **zero calls/tokens/quota** with
no promoted task/application slices. There is no installed model planner, tool
executor, recursive planner, endpoint-selection shortcut or paid fallback.
A future justified model experiment must use P21 dispatch receipts/P19 physical
attempt accounting, strict-free admission, endpoint-bound preparation, structured
output and bounded deadline; it must not enable an alternate Gemini-only path
around the standing workflow acceptance gates. Unavailable prerequisites and
inadequate quality evidence cannot be fixed by sending private planner inputs.

## Failure classes

Distinguish lexical omission, irrelevant phrase selection, policy/source omission,
budget packing omission, required-source denial, and downstream unsupported input.
Provider absence, sharing revocation and consent denial are expected exclusions,
not reasons to ask an LLM for broader permissions. If evidence cannot distinguish
these from genuine selector failures, preserve control and decline promotion.

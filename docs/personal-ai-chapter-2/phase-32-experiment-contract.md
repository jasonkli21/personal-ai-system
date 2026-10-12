# Phase 32 experiment contract — v1

Declared 2026-10-12 before running the Phase 32 benchmark. This contract is not a promotion record.

## Frozen control

Control: `deterministic-context-planner-v1`, maximum source allocation 1,200 tokens,
configured rules from the canonical deployment contribution catalog plus built-in
rules. The benchmark records the configuration fingerprint, fixture digest, source
revision, and deterministic algorithm digest. A changed algorithm/configuration
requires a new baseline, never an overwritten historical result.

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
2. `PlanningRequest`: bounded typed metadata produced only after shared policy
   and provider authority preflight; opaque choice IDs resolve to exact server-held
   selections. No intent text, source bodies, credentials, raw entity/grant IDs or
   unrestricted catalogs. The first experiment envelope permits only narrowing
   already selected sources. It cannot recover omissions by manufacturing access.
3. `ContextPlanProposal`: bounded IDs, allowlisted fields and caps only. Exact
   entities, federation purpose/grant, windows and scope stay server-held. Extra
   keys, unknown IDs/fields, duplicate choices and excess caps fail validation.
4. Server-approved final plan plus `PlanningTrace`: independently repeats current
   policy, scope, capability/spec availability and registered authority preflight.
   Required selections cannot be removed. Builder/provider checks still run at
   retrieval and disclosure. Compact diagnostics reuse existing context traces;
   experiment records are synthetic files, not a private production dataset.

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

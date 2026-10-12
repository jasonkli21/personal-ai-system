# Phase 35 implementation plan — Adaptive routing experiments

Renumbered from former Phase 27. This revision preserves deterministic hard-filter, offline/shadow-first, supported-outcome, strict-free, and rollback requirements while making feature construction, strategy progression, objective/coverage, drift, artifact identity, and promotion semantics explicit.

Phase 35 is the **first** phase that implements learned/adaptive endpoint selection, behind the replaceable project-owned `RoutingStrategy` seam defined by Phase 21.

## Scope boundary

**Goal:** Improve quality-per-free-quota and latency/resource efficiency by selecting among already-eligible execution endpoints using measured adaptive strategies, without allowing learning to weaken authorization, privacy, capability, quality-floor, context-fit, cost-mode, quota, or consent rules.

### Normative commitments

- Keep all deterministic hard admission outside learning.
- Keep the deterministic strategy as baseline and immediate rollback.
- Build a privacy-safe, versioned offline dataset from the Routing Observation Contract.
- Define feature schema/version and permitted source facts explicitly.
- Start with simple bounded adaptive strategies before more complex online-learning approaches.
- Explore complexity classifiers, pairwise/ranking models, RouteLLM-style concepts, contextual bandits, or other methods only where dataset size/label coverage justifies them.
- RouteLLM is a conceptual precedent, not an architectural dependency.
- Run offline/replay first, then non-dispatching shadow; no production promotion from training/replay fit alone.
- Never treat an unexecuted endpoint as having an observed counterfactual quality/usage/latency label.
- Keep related requests/conversations/runs/retries/cascade attempts together across data splits.
- Use temporal and relevant endpoint/configuration separation to avoid leakage.
- Include strategy inference overhead and all physical attempts/retries/cascade/accounting operations in cost/latency comparisons.
- Record stable strategy ID/version, feature schema/version, training/evaluation dataset identity, hyperparameters/configuration, and model artifact identity.
- Promote only for declared task/endpoint/profile coverage supported by held-out outcomes.
- Detect materially stale strategy evidence when endpoint/profile/configuration/task distributions change.
- ChatGPT remains explicit-only and is never an automatic learning candidate.
- Failure cannot silently enable paid/BYOK/unknown-cost paths.

### Acceptance criteria

No production promotion without held-out supported outcome evidence, bounded inference overhead, no hard-policy regression, and tested deterministic rollback. Unsupported or drifted coverage remains deterministic or shadow-only.

## Current state and reuse

Reuse:

- Phase 18 endpoint profiles and strict-free eligibility;
- Phase 19 quota/usage/accounting and invocation lineage;
- Phase 21 project-owned `RoutingStrategy` seam and deterministic baseline;
- Phase 22 quality/evaluation identities;
- Phase 23 quota/scarcity-aware routing;
- Phase 24 validator/cascade outcomes;
- shared Routing Observation Contract;
- Phase 20 GCS for permitted bulky model/training artifacts;
- Postgres compact evaluation/strategy metadata under Phase 10.

No learned router exists before this phase.

## Prerequisites

Required phases: 22, 23, and 24, plus standing Phase 10/18/19/21 foundations.

## Invariants

Learning receives only candidates that already passed hard filters for:

- execution/cost mode;
- privacy/sensitivity;
- authorization/consent;
- capability;
- context/count fit;
- required quality floor;
- known exhaustion/cooldown;
- account/credential/profile eligibility.

Adaptive strategy output is a **preference/ranking among eligible candidates**, not permission.

Shadow mode:

- performs no additional private/billable provider dispatch;
- does not change user-visible routing;
- does not fabricate alternate answer quality;
- can compare route agreement and decision overhead only unless paired outcomes exist.

ChatGPT plan and future explicit BYOK lanes are excluded from automatic learned routing.

## Routing observation and dataset contract

Phase 35 consumes privacy-safe, joinable, versioned observations, including where already available:

- request/task/profile characteristics;
- eligible candidate set after hard filters;
- endpoint/account/cost/profile identities;
- deterministic strategy/policy versions;
- decision-time quota/scarcity/health snapshot;
- endpoint-specific context/count fit;
- selected endpoint;
- invocation outcomes/usage/latency/error lineage;
- validator/cascade outcomes;
- Phase 22 task quality/evidence versions;
- retries/cascade attempt grouping.

Replay reconstructs bounded decision context; it does not require raw prompts.

### Dataset identity

A training/evaluation dataset must have a stable manifest including:

- observation time range;
- included task/profile/application coverage;
- strategy/policy/profile versions;
- endpoint configuration versions;
- group/split policy;
- label source/version;
- excluded/sensitive fields;
- missing-label statistics;
- dedupe/grouping rules.

## Feature schema

Features are derived here rather than smuggled into earlier routing phases.

Allowed initial feature families may include:

- task identity/category;
- structured task requirements;
- input/context token/count buckets;
- output budget bucket;
- required capabilities;
- sensitivity/privacy class after eligibility has already been established;
- candidate endpoint quality profile values;
- quota/scarcity bucket;
- endpoint health/cooldown state as already represented;
- historical task-endpoint aggregate statistics with leakage-safe cutoff;
- deterministic route rank/reason;
- request complexity proxies that do not require exposing raw private prompt text.

Raw prompt text, arbitrary private context, credentials, and unrestricted domain records are not default training features.

Feature schema/version must be explicit so a strategy artifact cannot be used against incompatible runtime features.

## Strategy progression

Candidate strategies should progress from simplest to more complex only when evidence supports the next step:

### Strategy 0 — Deterministic baseline

Existing Phase 21/23/24 behavior.

### Strategy 1 — Bounded rule/score complexity policy

A transparent task/complexity classifier or score that reorders eligible candidates using existing measured quality/quota facts.

Purpose: test whether a small amount of task conditioning captures most of the value before ML complexity.

### Strategy 2 — Learned ranker/classifier

For example, pairwise ranking or multiclass endpoint selection trained only where supported labels exist.

Must expose calibrated confidence/coverage or an equivalent abstention criterion.

### Strategy 3 — Contextual bandit or online adaptation

Optional and **not required** for Phase 35 completion.

May be evaluated only if:
- sufficient safe traffic/evaluation data exists;
- reward attribution is trustworthy;
- exploration can remain within strict-free/privacy/quality floors;
- offline policy evaluation limitations are explicit;
- user-visible degradation risk is bounded.

No mandatory external framework is required.

## Labels and counterfactuals

Observed selected-route outcomes may label only the route that actually executed.

Unexecuted alternatives are `missing`, not negative examples.

Counterfactual comparison is supported only by:

- paired Phase 22 evaluations;
- bounded separately authorized paired experiments;
- other directly observed equivalent outcomes with defensible identity.

Shadow agreement with an unexecuted route is not a quality label.

## Data splitting and leakage prevention

At minimum:

- group related conversation/session/request families;
- keep retries/cascade attempts together;
- keep duplicated/paired fixture families together;
- apply held-out grouped splits;
- include temporal holdout;
- separate relevant endpoint/configuration versions when testing generalization;
- ensure aggregate historical features use only data available before the decision timestamp.

Report coverage and missing labels per split.

## Objective and evaluation

Do not optimize "quality" alone.

For each declared task/profile coverage, compare:

- supported answer/task quality;
- validator pass rate where applicable;
- quota conservation;
- free-capacity consumption;
- end-to-end latency;
- strategy inference latency/CPU;
- total input/output tokens;
- all physical attempts/retries/cascades;
- abstention/fallback rate;
- endpoint distribution;
- uncertainty/calibration;
- hard-filter agreement = 100% by construction.

A candidate may be valuable because it preserves quality while saving scarce quota, or because it improves quality at acceptable equal resource use.

## Drift/staleness policy

Adaptive evidence becomes suspect when relevant identity changes, including:

- endpoint/model/configuration;
- serializer/counting behavior;
- task/profile requirements;
- quality evaluation version;
- provider/account/tier facts;
- candidate-set composition;
- feature schema.

Define runtime checks that can demote a strategy to deterministic/shadow when compatibility or freshness requirements are not met.

Do not silently continue using a strategy artifact against incompatible endpoint/profile facts.

## Work packages

### P35.0 — Offline dataset, feature contract, and candidate strategy specification

Build the privacy-safe dataset manifest from permitted routing observations.

Define:

- group/split rules;
- supported label sources;
- missing/counterfactual label semantics;
- initial feature schema/version;
- task/endpoint/profile coverage;
- Strategy 0–2 candidates justified by available data;
- promotion metrics/thresholds.

Reproduce historical deterministic decisions where expected before training adaptive strategies.

**Acceptance:**
- Group-held-out and temporal/configuration-separated data can be reproduced.
- Related attempts/conversations cannot leak across splits.
- Unsupported counterfactual labels remain missing.
- Feature extraction uses only permitted, decision-time-available facts.
- Raw sensitive prompt/context is not required.

### P35.1 — Simple adaptive baseline and learned ranker offline evaluation

Implement the simplest justified adaptive strategy first.

Compare Strategy 1 and, only if data supports it, Strategy 2 against deterministic/quota-aware/cascade baselines.

Measure training/serving overhead and calibration/abstention. A learned strategy must be able to decline to reorder when outside covered/confident conditions.

Persist safe strategy metadata in Postgres and permitted bulky artifacts in GCS.

**Acceptance:**
- Any adaptive gain is measured on held-out supported labels.
- Strategy artifact has reproducible identity/configuration.
- Missing labels are not imputed as failure/success without explicit justified methodology.
- Simpler strategy remains preferred when performance is equivalent within uncertainty.

### P35.2 — Non-dispatching shadow integration behind hard filters

Run adaptive strategies only after deterministic hard admission produces the eligible set.

Shadow records:

- candidate set;
- deterministic choice;
- adaptive proposed choice/ranking;
- agreement/disagreement;
- strategy inference overhead;
- coverage/abstention reason.

Shadow must not dispatch the alternate candidate and therefore does not record alternate quality/usage/latency outcomes.

**Acceptance:**
- Shadow cannot change visible routes.
- Shadow cannot bypass hard filters.
- No additional provider disclosure/call occurs.
- Route-agreement metrics are clearly separated from supported outcome metrics.

### P35.3 — Promotion evidence, scoped rollout, drift guard, and rollback

For task/endpoint/profile subsets with adequate held-out paired/supported outcomes, compare:

- quality;
- validator results;
- quota conservation;
- total pipeline latency/usage;
- strategy overhead;
- uncertainty;
- endpoint/configuration churn sensitivity.

Define explicit promotion thresholds and minimum coverage.

Promotion may be partial by task/profile. Insufficiently supported regions remain deterministic or shadow-only.

Implement compatibility/drift checks that demote stale/incompatible strategies.

Test deterministic rollback and strategy removal without rewriting orchestration or transport.

**Acceptance:**
- Promoted coverage has held-out supported outcomes establishing the claimed benefit.
- No split leakage exists.
- Strategy inference overhead is included.
- Drift/incompatibility causes safe demotion.
- Rollback is tested.
- Failure cannot enable paid/unknown-cost/explicit-only routes.

### P35.4 — Optional advanced strategy experiment gate

Only if P35.0–P35.3 show adequate data/reward quality, document whether a contextual bandit/online adaptation experiment is justified.

If not justified, explicitly defer it; Phase 35 can still complete with a simpler promoted or shadow-only strategy.

If justified, require:

- bounded eligible-set exploration;
- strict-free accounting;
- no safety/privacy exploration;
- minimum quality floor;
- reward-delay/attribution design;
- exploration budget;
- kill switch/rollback;
- no fabricated offline counterfactual certainty.

**Acceptance:**
- The plan records a reasoned implement/defer decision.
- Online adaptation is not introduced merely to satisfy a roadmap label.

## Promotion criteria

Promotion thresholds must be written before final evaluation and cover:

- supported quality/task metric;
- quota/resource benefit;
- end-to-end latency;
- strategy overhead;
- calibration/abstention;
- minimum observation/evaluation coverage;
- endpoint/configuration compatibility;
- deterministic rollback.

A strategy choosing mostly unobserved alternatives cannot be promoted based on historical selected-route success or shadow agreement.

## Requirement coverage

All former Phase 27 commitments remain represented: learned ranking only behind `RoutingStrategy`; deterministic rollback; optional RouteLLM-style/complexity/bandit concepts; offline/shadow first; hard filters outside learning; quality/quota comparison; stable artifact identity; supported outcomes only.

This revision adds explicit feature, dataset, split, strategy progression, calibration/abstention, drift, and optional-online-learning gates.

## Explicit non-goals

- Learning authorization/privacy/cost-mode/capability policy.
- Automatic ChatGPT or BYOK routing.
- Fabricated counterfactual model outcomes.
- Provider transport changes.
- Replacing Phase 19 quota admission.
- Replacing Phase 22 evaluation.
- Mandatory RouteLLM dependency.
- Mandatory contextual bandits/online learning.
- Training on unrestricted raw personal prompts/context.
- Global promotion from narrow benchmark gains.

## README maintenance

Review the repository-root `README.md` before closing. Update only if implemented current-state facts change.

## Targeted verification and closeout

Run applicable tests, lint, typecheck, build, offline evaluation/replay, shadow tests, and `git diff --check`.

Use synthetic/privacy-safe fixtures by default. Live provider/cloud experiments are opt-in and skipped checks remain **unverified**, not passed.

Implementation evidence must record:

- files/interfaces;
- dataset manifest;
- feature schema;
- split/group policy;
- strategy/artifact identities;
- label coverage/missingness;
- held-out metrics;
- strategy overhead;
- promoted task/endpoint/profile coverage;
- drift/compatibility checks;
- rollback results;
- disabled external gates.

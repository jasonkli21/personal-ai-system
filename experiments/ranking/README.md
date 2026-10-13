# Ranking experiments

Domain scorers remain domain-owned. Adaptive endpoint experiments use the shared
`RoutingStrategy` seam in `personal_ai.routing.adaptive`, not a second router.

Phase 35 declares thresholds before evaluation: at least 30 independent live
families in each grouped, temporal, and relevant configuration holdout; no quality
regression; at least 5% resource saving; no pipeline latency increase; at most
5 ms strategy inference and 25% abstention. Missing measurements deny promotion.
The current rule is **shadow-only**, with no runtime promotion lane. Strategy 2
is deferred until supported paired labels justify learning; online bandits are
deferred because safe traffic, rewards, exploration budget, and calibration are
absent. Equivalent performance favors the simpler deterministic strategy.

The frozen Phase 21/23/24 baseline is
`backend/src/personal_ai/evaluation/fixtures/routing/adaptive-baseline-v1.json`.
The initial privacy-safe synthetic snapshot has 80 P22 observations (20 fixtures
across four endpoints), one conservative run/family group, and no live outcomes.
P22 evaluates one target at a time; these observations do not establish adaptive
benefit over a simultaneously eligible candidate set. Unexecuted alternatives
remain missing. Exact prepared input/rubric/run paired measurements are reported
separately; different serializers are not silently equated.

Run `make adaptive-routing-eval`. The report separates agreement, supported
selected quality, single-case resources, P19 physical-attempt projections, and
strategy latency/CPU. Unknown pipeline/end-to-end/lineage measurements remain
missing. It never turns case latency or retained reservation sums into complete
pipeline cost or actual free-capacity consumption.

Dataset manifests freeze permitted decision facts, coverage/config/strategy
identities, label versions and missingness, time range, dedupe and connected
component splits. Whole runs, scoped requests, roots/retries/cascades, and paired
fixture families remain together. A missing fixture-family classification merges
the whole suite. A canonical session join is required before ordinary conversation
traffic can enter training. Historical aggregates are disabled; their optional
projection requires both decision and label observation times before the cutoff.

Runtime configuration is default-off: `ROUTING_SHADOW_ENABLED` and a bounded,
versioned `ROUTING_SHADOW_ARTIFACT` JSON object. The factory registers the rule and
injects it after hard admission. Feature schema, baseline/rule implementation,
full endpoint/account/tier/model/serializer/counter config, full task/requirements,
policy, quality evidence, candidate composition and a maximum 30-day freshness
window bind coverage. Churn/absence/errors/overhead cause deterministic abstention.
Disabling the gate removes the implementation without changing dispatch paths.
Metadata is embedded in the existing bounded Postgres routing decision, inheriting
owner/application/workspace fencing, export, deletion and replay retention. There
is no new ledger or bulky trained artifact; any future bulky model must use the
existing private Phase 20 artifact contract rather than a new file store.

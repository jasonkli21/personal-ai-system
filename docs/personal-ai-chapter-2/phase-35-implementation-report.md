# Phase 35 implementation report

The original implementation report below records the initial implementation
snapshot. The independent post-implementation review remediation record dated
**2026-10-12** supersedes its composition and current verification claims; Phase
35 is still not wired into a user workflow while Phase 15 authorization/revocation
acceptance remains open.
See the [remediation evidence](phase-35-independent-review-remediation-evidence-2026-10-12.md).

Implemented locally on **2026-10-12**, with **shadow-only rollout and no promoted
coverage**. Tested revision: base `16f74f4005b83527e7fd6589a439182d4caa7513`
plus this single-commit candidate. The tested backend material-source digest is
`32dd44c75bcdb09406011a1e2756b0a6fd50dfec9df793a32799e6b2bdd9b4df`,
recorded in the [v7 runtime freeze](../../backend/src/personal_ai/evaluation/fixtures/context/planning-baseline-v7.json).

1. **Architectural model.** Phase 18/21 authorization, strict-free, capability,
   sensitivity, quality-floor, fit and Phase 19 quota/health admission remain
   deterministic. `RoutingStrategy` owns preferences only. A transparent small-task
   capacity rule is evaluated offline and observed in non-dispatching shadow;
   the Phase 23 deterministic ranking remains the visible route and rollback.

2. **Canonical owners and identities.** The endpoint registry owns full
   endpoint/model/account/tier/credential-scope/serializer/counter configuration.
   P19 owns physical attempts, reservations, settlement and health. P21 owns
   decision/root/request/reselection identity and bounded replay facts. P22 owns
   run, fixture, scorer and executed quality observations. Dataset and artifact
   content digests bind feature/config/implementation identities; none confer
   authorization or mutation authority.

3. **Shared seams.** Extended the existing strategy view and schema-6 decision
   JSON; reused deterministic replay, P22 run/case contracts, P19 attempt facts,
   owner fences and bounded repository reads. Compact artifact metadata is stored
   inside the existing Postgres decision, not a parallel experiment/quota ledger.
   Historical schemas remain readable for deterministic replay. SQL migrations
   remain unchanged and hermetic. No bulky trained model is produced; future
   bulky artifacts must use the existing private Phase 20 contract.

4. **Production composition.** `PostgresDynamoPersistenceFactory.routing_service`
   remains the shared factory. The canonical FastAPI
   `get_routing_decision_service` dependency now calls it and requires an
   app-installed current routing authorization authority; absence returns a
   fail-closed 503. No user workflow consumes that dependency yet. Phase 15
   membership/revocation acceptance and provider-neutral dispatch integration
   remain prerequisites, so configured shadow is not production-reachable and
   F35-01 remains open. `ROUTING_SHADOW_ENABLED=false` remains the default.
   The adaptive resolver is an injected registry with distinct strategy IDs and
   versions; unknown or incompatible entries fall back to the deterministic
   baseline. Its synchronous contract admits only code-reviewed bounded, pure,
   in-process implementations. The 5 ms measurement threshold is post-hoc, not a
   preemption or timeout guarantee.

5. **Preserved invariants.** Strategies see only post-filter candidates. Paid,
   unknown-cost, explicit-only, ChatGPT and BYOK lanes are absent. Ranking cannot
   widen eligibility; shadow cannot send, change the selected endpoint, or claim
   alternate answer quality. Features exclude prompt/context/source payloads,
   credentials and arbitrary domain records. Unknown counts/capacity remain
   missing. Shadow artifacts also retain deterministic selection under direct injection.
   Invalid or oversized optional diagnostics are omitted with a stable
   reason while preserving the deterministic route.

6. **Lifecycle and failures.** No new execution state machine or external effect
   is introduced. The existing atomic decision identity returns the retained
   observation on duplicate requests. Root bounds, single-use dispatch receipts,
   physical attempts, retry/reselection lineage, uncertain-outcome fencing and
   restart/reconciliation stay with P21/P19. Missing signals, incompatible/stale
   artifacts, malformed proposals, exceptions and excessive inference overhead
   abstain. Decision/source expiry and owner deletion retain existing fences.

7. **Provenance and freshness.** Coverage binds full task/requirements/policy
   identity, exact endpoint configuration, quality evidence identity, candidate
   composition, feature schema and baseline/rule implementation. Artifacts expire
   within 30 days. Canonical authority revalidation still occurs before effects.
   Schema-6 observations are projected without raw prompts; historical missing
   feature identity is excluded. The manifest separates a normalized safe
   configuration-facts digest from a source-observation-corpus digest. Reads
   distinguish retained completeness from truncation and from expired/deleted
   history. Metadata inherits existing retention/export/deletion; there is no
   private training corpus or new derived assistant state to bypass source
   revocation. Source implementation digests are cached by callable identity and
   are not recomputed through `inspect.getsource` on each proposal.

8. **Baseline and promotion decision.** The [frozen baseline](../../backend/src/personal_ai/evaluation/fixtures/routing/adaptive-baseline-v1.json)
   reproduces P21/P23 scoring and P24's direct default (40 versus 54 synthetic
   cascade attempts at equal quality). The [synthetic dataset](../../backend/src/personal_ai/evaluation/fixtures/routing/adaptive-observations-v1.json)
   has 80 executed P22 cases, 56 exact coverage identities and one conservative
   run/family group; dataset digest is
   `558236f36030575795decb7a2f5fd3c07f94282f21a8d5fc9b39e5b44ca66447`.
   Each P22 decision targets one endpoint. Twenty exact-input paired groups have
   three same-serializer outcomes; they remain separate from policy/counterfactual
   labels. Unexecuted alternatives remain missing. The machine-readable evaluator
   reports a pass/fail/unverified gate matrix per coverage and emits promotion
   only when every gate passes. The replay abstains on all 80 cases; all 80 route
   agreements are deterministic fallback agreement, not quality evidence. The
   updated source snapshot digest is
   `0cbe5bffb03df5577d6ca015e3baf07dac2043a277617d273636cb7de27e248e`.
   Measured strategy overhead is 41–151 µs, totaling 3,650 µs CPU in this run.
   Synthetic P19 projections count 80 sends and 5,440/2,800 input/output tokens.
   There are zero supported alternate quality comparisons, independent live
   groups, or pipeline-complete groups. Full root lineage, end-to-end latency,
   calibration and live free-capacity consumption are missing.
   Thresholds were declared before final evaluation: 30 independent live groups
   per holdout, no quality regression, 5% resource saving, no pipeline latency
   increase, ≤5 ms inference and ≤25% abstention. **No coverage is promoted.**

9. **Intentional deviations.** Strategy 2 is deferred because supported paired
   label diversity/held-out families do not justify learning. Bandits are deferred
   because safe traffic, reward attribution and exploration/calibration evidence
   are absent. Ordinary conversational observations are excluded until a
   canonical session join exists. Missing fixture-family classification merges
   the whole suite instead of guessing independent families. Runtime promotion
   is unavailable; this phase does not bootstrap production authorization from
   offline/shadow evidence. The P32 v8 lock preserves its unchanged corpus and
   non-promotion decision while binding the review-remediation backend source.

10. **Verification and remaining gaps.** The initial implementation snapshot
    recorded **1,668 backend tests passed**, **123 frontend tests passed**, and
    frontend lint, type checks and builds. Review-remediation verification is
    recorded separately: the full backend suite has **1,672 passed and 91
    skipped**, changed Python modules pass Ruff, and adaptive-routing and v8
    planning evaluations pass. There is no configured separate backend
    type-check target. Context, planning, memory/lifecycle/optimization,
    research/retrieval, decision/domain/itinerary, quota, cascade and adaptive
    deterministic evaluations passed in the initial snapshot. The
    iterative-research evaluation has four **pre-existing** `site:example.org`
    follow-up-string expectation failures, reproduced from an isolated archive
    of base `16f74f4`; its implementation and fixtures were not weakened.

    **Deferred environment-dependent verification — intentionally not executed:**
    the known PostgreSQL/pgvector, DynamoDB Local, reviewed cloud-smoke and live
    Gemini suites require environments deferred to a later phase. Their omission
    is not an implementation defect or review finding. Native schema-6
    roundtrip/paging/scope/idempotency and resource-projection coverage was added to the deferred Postgres
    suite; database locking, deletion/export, deployment, identity/privacy and
    live-provider acceptance remain unverified. Offline projections are not
    substitutes for that evidence.

11. **Sensitive downstream phases.** Phase 36 must preserve these hard-admission,
    fallback, lineage and incomplete-measurement distinctions when combining
    optimization layers. Future learned routing must add supported calibration,
    session grouping and full paired pipeline measurements before rollout, using
    the same strategy/observation/artifact contracts. Phase 15 remains the owner
    of workflow authorization/revocation acceptance; P20 owns any bulky model body.

12. **Aggressive review targets.** Challenge any inference of policy benefit from
    single-target P22 observations or route agreement; any claim that one run is
    independent held-out coverage; incomplete retained reads treated as history
    completeness; reservation totals treated as actual quota consumption; and
    per-inference timing treated as full pipeline/initialization cost. Inspect
    exact configuration/freshness demotion, metadata-overflow fallback, native
    store isolation/retention, canonical factory reachability, and any proposal
    to enable workflows or live promotion before their existing gates close.

The pre-final audit found no new provider/app-name branch in generic routing,
transport rediscovery, parallel accounting/state owner, caller-granted execution
authority, hard-coded frontend capability list, migration/runtime coupling, or
private-prompt training path. See the [experiment contract](../../experiments/ranking/README.md)
and [measured summary](phase-35-evaluation-summary.json).

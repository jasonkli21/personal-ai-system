# Phase 32 implementation report

2026-10-12. Plan authority: committed revision `b3c50ea`, reread after the user's
plan commit. The remediation was tested against base revision
`3e9452185848414410ccbbedbd228bf5f22a8bce` and source identity digest
`1041ce057469d6e72a32af7e9b89022d24c6b60980cf9d9d7025361d76bd99a4`; the
benchmark accepts that revision or its direct child only when the material source
digest is unchanged. Outcome: **non-promotion; no model planner installed, zero
planner inference budget**. This does not close standing Phase 15/30 acceptance
gaps.

1. **Architectural model.** Four separate artifacts: deterministic `ContextPlan`;
   minimized `PlanningRequest`; non-authoritative typed `ContextPlanProposal`;
   independently validated final plan and `PlanningTrace`. Selection remains
   subordinate to current policy, registered authority, provider admission and
   builder disclosure checks. The initial envelope only permits narrowing.

2. **Canonical owners and identities.** Request authentication owns owner/acting
   user/app/workspace identity. Application declarations own disclosure policy;
   installed contributions own implementations; domain authorities and the
   federation broker own membership, exact records, grants/revisions/epochs and
   export consent. Plans bind the authenticated request fingerprint. Opaque
   choice IDs bind exact server-held selections, entities, purposes and windows.
   Strategy/configuration, policy, baseline, proposal and final-plan fingerprints
   are distinct diagnostic identities, never proofs of permission.

3. **Shared seams reused.** `context/planner.py`, `assembler.py`,
   `planning_experiment.py`, `providers.py` and `traces.py` extend existing seams.
   Operation-bound validation was extracted from actual provider preparation and
   is reused by experiment preflight. There is no second authorization registry,
   source store, usage ledger, search optimizer, memory retriever or endpoint router.

4. **Production composition.** Installed contribution catalog → canonical API
   `get_context_assembler`/external assembler → `plan_context` → shared policy and
   authority preflight → coordinator retrieval → `ContextBuilder` → existing
   manifest/inspector. Production requests retain deterministic planning and now
   carry compact planning diagnostics. Experiment envelope/validation methods use
   that same assembler. FastAPI dependency-path tests exercise validation followed
   by actual provider retrieval/build; scripted comparisons use those methods.
   No production service automatically invokes a proposal producer.

5. **Invariants preserved.** Unknown fields/IDs/selectors/providers/source classes,
   oversized caps, duplicate choices, mode/tool/recursion keys and schema mismatches
   cannot widen the envelope. Required allocations cannot be removed/reduced.
   Full policy digest and implementation spec are rechecked independently of
   rationale. A 200-provider installed catalog discloses only the authorized
   selected descriptor. No source body, credentials, raw entity/grant ID or raw
   intent enters planning metadata/telemetry. Existing context inspection remains
   the diagnostic surface.

6. **State/failure/retry semantics.** Baseline → optional request-local proposal →
   validation → final plan → retrieval/build. Invalid or expired proposals return
   current control. Revoked authority, changed request identity/policy/provider
   configuration or unavailable baseline implementation denies before retrieval,
   rather than returning historical permission. Required-source budget denial
   remains intact. No new durable operation, external send, retry, reservation,
   reconciliation, replay authority or model recursion exists. Rollback is the
   unchanged deterministic path. Timing is excluded from deterministic identity.

7. **Provenance/freshness/revocation.** Exact entity/window/federation bindings stay
   server-held; descriptor fingerprints are not source truth. The versioned
   planning trace records policy, validator/schema, provider-spec and federation
   grant revision/epoch dependencies at validation, plus per-choice result/reason
   and measured planning latency. After retrieval, the existing build trace adds
   exact source revision and permission dependencies, with references hashed and
   payloads omitted. Current broker dependencies are checked before experiment
   metadata/validation and again at retrieval; builder/dispatch reuse checks remain
   canonical. Active, revoked, expired, source-revoked, consent-revoked and
   membership-revoked states are separate synthetic fixtures. Additive optional
   trace fields accept old manifests and follow existing DynamoDB context trace
   scope, size, retention/export/deletion behavior. Synthetic CLI evaluation uses
   the existing optional Phase 20 retention path; no private experiment store or
   migration was introduced. Searchable production experiments are not retained
   as a new Postgres dataset while no model experiment is enabled.

8. **Baseline and promotion.** `planning-baseline-v2.json` binds evaluator and
   corpus versions, configuration, fixture dependencies, full Python version/ABI,
   platform, installed distribution inventory digest, and the material source-tree
   digest. It enforces the tested Git base/direct-child relation.
   Thresholds were declared in the [experiment contract](phase-32-experiment-contract.md)
   before comparisons; `evaluation/planning_promotion.py` requires exact
   application/task/source-pattern/sensitivity coverage keys. Each hard invariant,
   physical-call count, quota measure, answer-quality score and rollback input is
   nullable and missing values deny promotion. A Phase 22 scorer adapter accepts
   an observed output and only the source IDs actually injected into that exact
   assembled context, returning payload-free evidence including the scorer's hard
   boundary result. The evaluator accepts only evidence matching the strategy,
   configuration, assembled-context digest and tested revision. Bound validation
   traces can also produce per-case proposal-attempt, rejection, narrowing,
   fallback and unauthorized-attempt counts and rates. Missing trace observations
   remain null. Neither path invents an observation or a candidate comparison.

   The 30-row held-out v2 corpus includes a 16-provider independently authorized
   catalog under a tight context budget, exact trip-source revision transitions
   (including a partial revision-8 observation), and synthetic grant, source,
   consent, membership and expiry states. The evaluation has 22 scripted
   retain-control pairs; their inputs preserve selection/support where applicable.
   Observed deterministic-control issues include two lexical omissions, one
   irrelevant negated profile selection and one required-budget denial; expected
   authority exclusions remain visible. Domain payloads and byte-based counts are
   synthetic. Source-support proxies are not generated answer quality. No quality
   observation or assisted candidate comparison is present, no exact coverage key
   has 100 independent families, and there is no measured net inference benefit.
   **Promoted coverage: none.** Measured planner model calls/tokens/quota: zero.
   The evaluator retains the control defects rather than tuning the baseline to
   the held-out corpus.

9. **Review remediation and intentional deviations.** The [2026-10-12
   remediation evidence](phase-32-review-remediation-evidence-2026-10-12.md) maps
   each independent-review finding to code, tests and remaining limits. The
   current `PlanningRequest` is labeled `narrowing_validation_only`; it is not a
   model selection interface and no endpoint/call path exists. Any future
   assisted-selection request must be separately versioned and privacy-reviewed,
   carry typed task features for the omission class, and expose only a candidate
   envelope independently authorized under current policy, grants, sensitivity
   and provider authority. Paired comparisons remain scripted validation/rollback
   controls, **not LLM-assisted evidence**. Model-specific endpoint removal,
   planner-quota exhaustion, malformed model output and paid fallback are not
   claimed as executed inference tests. Zero-budget/mode schemas and absence of a
   tool executor enforce this non-promotion boundary. An eventual model strategy
   still requires canonical P21/P19 admission/physical accounting and standing
   gates.
   Existing offline fixtures were repaired for Phase 31's startup inventory and
   Phase 30's verified authentication-time/separate Health federation gate. The
   startup guard still runs; populated retirement/conformance tests retain their
   own repositories. No production security behavior was weakened.

10. **Verification and external limits.** Final commands/results are recorded
    below. Offline fakes prove their bounded contracts only. Live model quality,
    provider counting/quota, deployed membership/consent, real domain HTTP/browser
    behavior, migration application, database races and production trace retention
    remain unverified. None is counted as promotion evidence.

11. **Sensitive downstream phases.** Phase 33 consumes macro selection without
    gaining source rights; Phase 34 retains memory lifecycle and embedding-space
    ownership; Phase 35 ranks already-eligible endpoints through routing, never
    through this proposal schema; Phase 36 must retain missing-measurement gates,
    derived-source revocation and total physical overhead checks. Any future model
    planner must add evidence rather than reinterpret these control observations.

12. **Independent review challenges.** Challenge the scope/quality of the corpus,
    negation and paraphrase defects, distinction between support and model quality,
    real membership/revocation races, metadata minimization and trace bounds,
    deterministic-versus-proposal identity, required-source preservation, factory
    availability changes, test-fixture isolation and any claim that zero calls
    proves an assisted runtime. Audit that no proposal can become historical
    authority, no unknown metric becomes zero, and no deployment promotion follows
    from the scripted control.

## Verification evidence

Final remediation checks and their exact outcomes are recorded in the
[review-remediation evidence file](phase-32-review-remediation-evidence-2026-10-12.md).
The planning evaluator is an offline synthetic measurement: successful execution
proves its contract and fixture outcomes, not live provider, database, deployment,
or production trace behavior. It reports deterministic-control failures and
non-promotion rather than treating the run as a product-quality pass.

## Deferred environment-dependent verification — intentionally not executed

The known PostgreSQL/pgvector, DynamoDB Local, reviewed cloud-smoke, and live
Gemini suites were intentionally excluded because their required environments
are deferred. They are not implementation defects or review findings. No
infrastructure or provider credentials were provisioned. The initial broad run
revealed unmarked offline fixtures attempting a startup database inventory;
those fixtures now declare an empty synthetic inventory without disabling the
retirement guard or changing the deferred persistence suites.

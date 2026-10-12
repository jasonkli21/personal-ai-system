# Phase 32 implementation report

2026-10-12. Plan authority: committed revision `b3c50ea`, reread after the user's
plan commit. Tested source: that revision plus the uncommitted Phase 32 changes.
Outcome: **non-promotion; no model planner installed, zero planner inference budget**.
This does not close standing Phase 15/30 acceptance gaps.

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
   server-held; descriptor fingerprints are not source truth. Current broker
   dependencies are checked before experiment metadata/validation and again at
   retrieval; builder/dispatch reuse checks remain canonical. Active, revoked,
   expired and source-revoked grants run through the existing broker. Domain source
   snapshots and exact revision/freshness dependencies still arise from providers
   after retrieval; no speculative revision is fabricated by planning. Additive
   optional trace fields accept old manifests and follow existing DynamoDB context
   trace scope, size, retention/export/deletion behavior. Synthetic CLI evaluation
   uses the existing optional Phase 20 retention path; no private experiment store
   or migration was introduced. Searchable production experiments are not retained
   as a new Postgres dataset while no model experiment is enabled.

8. **Baseline and promotion.** `make planning-eval` freezes algorithm,
   configuration and fixture identities; `planning-baseline-v1.json` records the
   exact digests. Thresholds were declared in the [experiment contract](phase-32-experiment-contract.md)
   before comparisons; `evaluation/planning_promotion.py` enforces them per slice.
   Twenty-three cases cover five application slices, including synthetic federation;
   the report also identifies task-family/provider-operation coverage slices.
   Eighteen scripted retain-control pairs preserve selections, injected support,
   assembled bytes and estimated tokens. Observed control failures: two lexical
   omissions, one irrelevant negated profile selection, one required-budget denial;
   five sharing/revocation exclusions are expected. Domain payloads and byte-based
   counts are synthetic. Source-support proxies are not generated answer quality.
   Assembled control input totals were 13,089 bytes and 3,675 estimated tokens
   across successful builds; denied builds are missing, not authoritative empty.
   Model answer quality, real downstream quota and model-assisted counterfactuals
   remain missing. No slice has 100 independent families or measured net inference
   benefit. **Promoted coverage: none.** Measured planner model calls/tokens/quota:
   zero. Deterministic selection defects remain visible; this phase does not tune
   the control against its held-out corpus.

9. **Intentional deviations.** P32.1 says “for justified cases only”; no current
   slice justifies a strict-free model experiment. Consequently, paired comparisons
   are scripted validation/rollback controls, **not LLM-assisted evidence**. The
   initial proposal schema cannot add an omitted source; a future justified
   experiment must build an independently authorized expanded envelope through the
   same seams. Model-specific endpoint removal, planner-quota exhaustion, malformed
   model output and paid fallback are not claimed as executed inference tests: there
   is no planner endpoint/call path. Zero-budget/mode schemas and absence of a tool
   executor enforce this non-promotion boundary. An eventual model strategy still
   requires canonical P21/P19 admission/physical accounting and standing gates.
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

- Backend environment-independent suite: **1,565 passed**, 84 persistence/cloud
  cases deselected; both manual Gemini suites explicitly excluded. Command:
  `python -m pytest -m 'not persistence_integration and not cloud_smoke' --ignore=tests/test_gemini_manual.py --ignore=tests/test_context_manual.py -q`.
  Latest trace projection changes additionally passed 81 relevant regressions.
- Targeted planner/provider/builder/trace/federation/mutation suite: 181 passed;
  additional adversarial, promotion, privacy/catalog and trace-roundtrip coverage
  is included in the final broad suite.
- Backend Ruff: passed. Backend source distribution/wheel build: passed
  (`UV_CACHE_DIR=/tmp/phase32-uv-cache` for writable build cache).
- Frontend: 123 tests passed; lint, typecheck and Next.js build passed using the
  bundled Node runtime.
- All established Makefile offline evaluations passed: context, context-plan,
  memory, memory-lifecycle, research, decision, domain, iterative-research,
  itinerary-proposal, quota-scarcity and cascade. New `planning-eval`: passed;
  it reports benchmark failures and denies promotion rather than hiding them.
- Link/content review, pre-final architecture audit and `git diff --check`: passed.

## Deferred environment-dependent verification — intentionally not executed

The known PostgreSQL/pgvector, DynamoDB Local, reviewed cloud-smoke, and live
Gemini suites were intentionally excluded because their required environments
are deferred. They are not implementation defects or review findings. No
infrastructure or provider credentials were provisioned. The initial broad run
revealed unmarked offline fixtures attempting a startup database inventory;
those fixtures now declare an empty synthetic inventory without disabling the
retirement guard or changing the deferred persistence suites.

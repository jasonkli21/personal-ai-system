# Phase 36 implementation report

Date: 2026-10-12. Tested base revision: `2d4d5a4c21d820ad0894619cb5a1985436f7c665`
plus the final working-tree source/configuration digest recorded in
[matrix results](matrix-results.json). The single implementation commit is the
direct child of this base; evidence binds file contents rather than claiming the
base commit alone contains the implementation.

1. **Architectural model.** A strict, versioned 48-row verification program maps
   27 normative boundaries and 13 fault scenarios to executable evidence or
   original blockers. Passed, failed, blocked, unverified and justified
   not-applicable remain distinct. The [model](architecture.md) was established
   before implementation; the [release report](release-report.md) and
   [blocker ledger](blockers.json) are derived projections.
2. **Canonical owners and identities.** DynamoDB owns timeline/runtime/jobs;
   Postgres owns knowledge, lifecycle, grants, proposals, routing and P19 usage;
   GCS owns bulky private bodies. Owner/actor/app/workspace, exact source revision,
   grant epoch/issuance, endpoint/account/credential/cost/quota and physical
   attempt/operation identities retain their existing authorities. No new
   runtime store or migration is introduced.
3. **Shared seams.** Reused startup contributions, application registry,
   permission revalidators, planner/coordinator/builder, research-service
   composition, memory lifecycle/retrieval, routing factory, P19/P21/P22/P24,
   mutation reconciliation and artifact lifecycle. The research evaluator now
   observes combined rewrite/packing and full synthesis-envelope estimates.
4. **Production composition.** `main.lifespan` installs a fifth app's two typed
   providers through the contribution catalog; FastAPI dependencies compose
   automatic/external assemblers and shared sidecar policy. Provider/task
   evaluation and registered cascade validation consume the production routing
   factory, with only I/O and authority fixtures substituted. No fifth product,
   alternate inference runtime or generic app/provider-name branch is added.
   The combined route receives the actual assembled token count, sensitivity,
   source fingerprints and owner; it does not rank an unrelated fixture input.
5. **Preserved invariants.** Authorization precedes source work; same owner does
   not grant cross-app access. Hard admission precedes adaptive strategy input.
   Exhaustion cannot overflow to paid, unknown-cost, BYOK, ChatGPT or explicit-only
   profiles. Receipts retain test IDs and numeric observations; no live prompts
   or reusable credentials are collected.
6. **State, retries and failure.** Existing exact confirmation, CAS, single-use
   claims, linked cascades and original-key uncertain-outcome reconciliation
   remain binding. The accumulated-state probe injects database, provider/network
   and artifact outages; interrupted cleanup retains one original generation and
   retries it safely. It introduces no cross-store transaction or blind resend.
7. **Source and revocation.** Existing authorities revalidate grants, exact
   source versions, expiry, lifecycle epochs and inherited history/summary/cache/
   artifact dependencies. A discovered memory-service defect is fixed at its
   owner: bound request retrieval preserves owner/actor/app/workspace rather than
   constructing duplicate owner arguments; foreign owners are denied before
   embedding. Revoked accumulated memory remains excluded.
8. **Baseline and promotion.** The unchanged 30-case planner corpus has a v9
   runtime freeze; v8 remains historical. Combined held-out synthetic estimates
   total 34,502 baseline, 33,921 combined and 34,502 rollback tokens: 1.68% saving
   misses the 5% gate. Live answer quality, whole-workflow timing, physical quota
   lineage and native-store resources are unmeasured. No coverage is promoted;
   deterministic defaults remain. The 32-step soak measures 70 timeline records,
   34 original memories, 59 views, 91 jobs, 32 research sessions and 32 routing
   records; all 32 artifact bodies are reclaimed. These are synthetic bounds,
   not native capacity or physical account-deletion evidence.
   Internal routing uses `quota-scarcity@1` with
   `remaining-sends-reset-relief-health-v1`; optional shadow uses
   `bounded-capacity-rule@1`. Memory uses `memory-read-v1` with `whole-v1` or
   `exact-redundancy-v1` packing. Exact enabled/default coverage is recorded in
   the matrix; promoted coverage is empty.
9. **Intentional deviations.** No assisted model planner or fully routed user
   workflow exists to benchmark; the program measures implemented narrowing and
   internal routing paths and explicitly blocks broader claims. The iterative
   fixture advances to v2 because Phase 33 carries program-generated domain
   constraints in typed operations. The original fixture is preserved; the new
   regression detects loss of the dispatched domain envelope rather than
   requiring an obsolete generated `site:` string. User literal constraints and
   original answer/resource assertions remain intact.
10. **Unresolved verification.** Original Phase 9/10 account deletion, restore,
    migration/inventory, deployed identity/privacy and Phase 14/15/25/domain/client
    acceptance obligations remain with their authoritative evidence owners.
    Missing mandatory evidence keeps affected capabilities unavailable; disabling
    a gate never creates a pass.
11. **Downstream sensitivity.** The detailed plan index ends at Phase 36.
    Subsequent domain dispatch, immutable source/policy authority, client
    acceptance, native-store operations and learned promotion must consume these
    existing seams and measured evidence, without moving canonical state or
    treating synthetic labels as live observations.
12. **Review aggressively.** Challenge matrix omissions, parameter-case capture,
    external/local evidence confusion, exact configuration binding, aggregate
    counting and embedding overhead, held-out family independence, retained view/
    job growth, eventual cleanup, mutation uncertainty and any implied live,
    strict-$0, privacy or release-readiness claim.

Verification results are recorded in the accompanying evidence files. The final
offline matrix executes 744 cases: 24 local rows passed, 21 external rows remain
unverified and 3 original obligations remain blocked. All 13 declared fault
scenarios pass. The failed synthetic resource-promotion gate is an experiment
result, not an enabled-path failure.

The pre-final audit found no new dual canonical state, policy/ledger/registry,
app-specific production singleton, transport rediscovery, mutable historical
migration dependency, hard-coded client capability list or truncation-as-absence
path. Existing workflow integration, immutable version, native-store and
deletion/recovery obligations remain explicit blockers. Receipt references hash
`json.dumps(receipts, sort_keys=True)`; this binds JSON facts independently of
display indentation. Matrix definitions use their exact byte hash. The release
report and ledger are reproducible from those stored facts.

| Check | Result |
| --- | --- |
| `make backend-test-offline` | 1,692 passed; 89 deferred marked cases deselected; live files excluded |
| `make integrated-verification` | 744 passed; matrix/report/blockers generated; release-ready false |
| Backend lint and package build | Passed; build used writable temporary uv cache, offline mode |
| Frontend tests/lint/typecheck/build | Passed; 123 tests; bundled Node runtime |
| All 15 Makefile deterministic/offline evaluation targets | Passed; artifact retention disabled |
| Link/content review and `git diff --check` | Passed |

## Deferred environment-dependent verification — intentionally not executed

The known PostgreSQL/pgvector, DynamoDB Local, reviewed cloud-smoke and live
Gemini suites were intentionally not executed because their required environments
are deferred. This is not treated as an implementation defect or review finding.
Real domain, browser, ChatGPT billing/transport, cloud IAM/capacity/headroom and
deletion-aware recovery also remain explicit unverified gates. All other applicable
environment-independent verification was executed normally.

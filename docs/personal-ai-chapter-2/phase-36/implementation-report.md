# Phase 36 implementation report

Date: 2026-10-12. Tested base revision: `77fdce50790f45b9d04b3cae48e71d1dd43e4621`
plus the final working-tree source/configuration digest recorded in
[matrix results](matrix-results.json). The single implementation commit is the
direct child of this base; evidence binds file contents rather than claiming the
base commit alone contains the implementation.

1. **Architectural model.** A strict, versioned 48-row verification program maps
   27 normative boundaries and 13 fault scenarios to executable evidence or
   original blockers. Passed, failed, blocked, unverified and justified
   not-applicable remain distinct. The [model](architecture.md) was established
   before implementation; the [release report](release-report.md) and
   [blocker ledger](blockers.json) are derived projections. A typed
   `--external-evidence` receipt path can merge separately executed non-offline
   results only when row, class, revision, matrix/source digest, environment,
   profile, authority, artifact, freshness and provenance bindings match.
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
4. **Production composition.** The production `create_app` factory installs a
   fifth app's manifests and workspace authority through the generic application
   contribution catalog. `AuthenticationMiddleware` constructs the request scope
   and checks required workspace membership through that registered authority;
   absent membership authority denies access. `main.lifespan` installs the app's
   two typed providers through the context contribution catalog. FastAPI dependencies
   compose automatic/external assemblers and shared sidecar policy. Provider/task
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
8. **Baseline and promotion.** The unchanged 30-case planner corpus has a v10
   runtime freeze for the review-fix source tree; v9 and v8 remain historical.
   The combined held-out measurement
   reports baseline and candidate latency distributions separately and evaluates
   every declared threshold as passed, failed, or unverified. Live answer quality,
   whole-workflow timing, physical quota lineage and native-store resources remain
   unavailable. No coverage is promoted; deterministic defaults remain. The
   32-step soak's exact final counts are recorded only in the generated
   [release report](release-report.md) and [matrix results](matrix-results.json);
   the report does not duplicate sample counts that can vary between runs. Its
   synthetic observations are not native capacity or physical account-deletion
   evidence.
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

Verification results are recorded in the generated evidence files. The current
matrix records 24 offline rows passed, 21 unverified external rows, and 3 original
blocked obligations; exact case counts, source/configuration digest, and soak
observations live in `matrix-results.json`, `receipts.json`, and
`release-report.md`. This summary does not duplicate run-specific soak counts.
All 13 declared fault scenarios pass. Failed or unverified synthetic promotion
gates are experiment results, not enabled-path failures.

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
| Offline backend suite | 1,699 selected; 89 deferred marked cases deselected; manual live files excluded |
| Integrated Phase 36 verifier | See generated matrix results and release report; external/native gates remain open |
| Planning evaluation | Passed against the v10 runtime freeze; no strategy coverage promoted |
| Backend lint | Passed with Ruff |
| Documentation review and `git diff --check` | Passed |

## Deferred environment-dependent verification — intentionally not executed

The known PostgreSQL/pgvector, DynamoDB Local, reviewed cloud-smoke and live
Gemini suites were intentionally not executed because their required environments
are deferred. This is not treated as an implementation defect or review finding.
Real domain, browser, ChatGPT billing/transport, cloud IAM/capacity/headroom and
deletion-aware recovery also remain explicit unverified gates. All other applicable
environment-independent verification was executed normally.

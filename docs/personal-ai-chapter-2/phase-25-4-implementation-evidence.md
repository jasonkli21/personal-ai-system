# Phase 25.4 implementation evidence

Date: 2026-10-11
Tested base revision: `7d3c8e4bce05c51708905b86d72486d1f9c017f0` plus the Phase 25.4 working-tree changes recorded in this review. The repository was not clean: the listed pre-existing independent-review and handoff notes were preserved and not modified.

## Delivered locally

- Added bounded, versioned application launch metadata bound to authenticated app,
  workspace, client context, and route conversation. Entity references are advisory
  and consumed only by the shared planner and registered source-provider checks.
- Added application-owned sidecar policy for connected/manual disclosure categories
  and sensitivity, imported-response history reuse, Copy, draft Insert targets, and
  future Apply declarations. Execution options expose this existing policy model;
  there is no parallel API policy schema or new state machine.
- Passed category/sensitivity narrowing into shared context authorization before
  source reads and checked effective sensitivity again before reservation binding.
  A shared history filter removes denied imported turns and their paired user prompts
  before summary compatibility/context construction while preserving canonical
  messages and attribution.
- Routed launch entity references through both existing automatic and external
  continuation paths. Requests without launch metadata keep the prior digest shape
  for retry compatibility; launch metadata binds into the digest when present.
- Added deterministic shared package/turn fixtures for `travel`, `shopping`,
  `finance`, `health`, and `synthetic_fifth`. They verify manual import followed by
  automatic continuation, unchanged historical attribution, scope and category
  narrowing before fetch, policy denial, and optional imported-history reuse.
- Added sidecar UI coverage for policy-denied manual mode, allowed and disallowed
  draft targets, no network write from draft insertion, canonical import callbacks,
  and launch context on the existing API request path.

## Verification

| Command | Result |
| --- | --- |
| `backend/.venv/bin/python -m compileall -q backend/src/personal_ai` | Passed. |
| `PATH="$(pwd)/backend/.venv/bin:$PATH" make backend-test` | **1,343 passed, 82 skipped**, 2 warnings, 75.00 seconds. Skips include opt-in persistence/cloud/provider integration. Docker is not installed in this environment, so Docker-backed persistence acceptance remains unverified. |
| `PATH="$(pwd)/backend/.venv/bin:$PATH" make backend-lint` | Passed: Ruff reported all checks passed. |
| `UV_CACHE_DIR=/private/tmp/personal-ai-system-uv-cache make backend-build` | Passed: source distribution and wheel built. The first build attempt used the protected default uv cache and was denied by the sandbox; retrying with a writable temporary cache succeeded. |
| `make frontend-test` | Passed: 21 files, 110 tests. |
| `make frontend-lint` | Passed. |
| `make frontend-typecheck` | Passed for application and test TypeScript configs. |
| `make frontend-build` | Passed: optimized Next.js production build completed. |
| `PATH="$(pwd)/backend/.venv/bin:$PATH" make context-eval context-plan-eval` | Passed with exit status 0 using the established deterministic fixture runners and fake/estimated counts. These do not establish live provider behavior. |
| `git diff --check` | Passed. |

The frontend emitted existing tooling notices for the Vite CJS API and missing
Next.js ESLint plugin detection; lint, type checking, and the production build still
completed successfully. Backend tests emitted Starlette/httpx and Pydantic
`ReadOnly` warnings.

## Architecture audit and scope

- No second conversation store, context assembler, planner, external-turn controller,
  reservation model, provider registry, or app-specific auth path was introduced.
- The existing conversation/message repositories remain canonical. Existing
  idempotency key/identity, reservation/CAS, retry, completion, and attribution
  semantics remain; the absent-launch digest compatibility case is tested.
- One canonical context source-class contract now feeds provider types, builder
  budgets, and sidecar policy. The API returns `ApplicationSidecarPolicy` directly.
- Generic service/policy/context layers branch on registered policy facts and source
  categories, not application/provider names. App-specific differences live in
  built-in manifests and host callbacks.
- Copy/import do not call domain mutation APIs. Insert is a client callback that must
  match the host-declared and policy-allowed target ID. Apply remains unavailable;
  typed proposal validation and confirmation stay with Phase 31.
- Finance and Health still advertise no external execution mode. They default to
  excluding manual imported turns from future context. Real domain adapters are not
  delivered by this phase.
- The root README was reviewed and not edited: Phase 25.4 adds implementation hooks,
  but it does not turn on a new user-facing domain integration or external execution
  capability.
- No material deviation from the written Phase 25.4 contract was required.

## Unverified acceptance and independent review focus

The external execution gate remains false by default. Phase 15’s complete source
membership, derived-history/revocation, and immutable policy/source-version acceptance
remain open. Phase 25.2 DynamoDB transaction, concurrent CAS/race, and restart
acceptance were not run against a real isolated engine. No live domain repository,
membership API, current source-revision, provider/account/billing, cloud identity,
browser/PNA/loopback, or deployed transport integration was exercised. These items
are **unverified**, not passed by the synthetic fixtures.

An independent reviewer should focus on:

- whether every real adapter checks current membership and source revision before
  retrieval and revalidates the declared dependencies at each required transition;
- whether a persisted summary or any other derived context can reintroduce an
  excluded manual turn after a branch change or summary refresh;
- whether host-provided launch IDs stay advisory and scope-bound across every route;
- whether manual/connected category and sensitivity narrowing remains aligned
  between API projection, preview, preparation, dispatch, completion, and retry;
- whether all eventual application hosts keep Apply behind Phase 31 and only expose
  non-authoritative draft targets through the policy/host intersection.

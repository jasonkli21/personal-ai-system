> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Shopping Assistant stabilization status

Date: 2026-10-13
Gate: 0 baseline recorded; Gate 1 repairs and local checks are complete; hosted and coordinator sign-off remain pending.
Repository baseline: `main` at `2268b944ffa8fe5c2e6f2787c88dea616160e398`, matching `origin/main`. The Gate 1 working-tree patch is uncommitted and was tested against this base revision.

At Gate 0 capture, no Shopping source or test files were edited and the repository had no tracked changes. Three pre-existing, untracked review handoffs remain and were preserved:

- `docs/planning/phase-8-independent-review-handoff.md`
- `docs/planning/phase-9-independent-review-handoff.md`
- `docs/shopping-assistant-maintainability-review-handoff.md`

## Current baseline

GitHub Actions run [38265114836](https://github.com/jasonkli21/shopping-assistant/actions/runs/38265114836) is the latest run on main and tests the same SHA. It completed with failure:

| Job | Result |
|---|---|
| backend | Failed at Ruff format check; later offline tests, migration SQL, and generated-type checks were skipped. |
| backend-db | Failed: 1 failed, 128 passed, 198 deselected. |
| frontend | Failed: 2 failed, 66 passed; lint and typecheck passed, build was skipped. |
| container-build | Image build passed; packaged smoke failed during migration CLI startup. |
| frontend-e2e | Passed. |

The attached audit correctly identified the database and frontend failures, the SQLAlchemy foreign-key-cycle warning, and the unavailable Personal AI external client. It omitted the formatter failure. The container smoke failure is more specific than the audit indicates: running Alembic from `/tmp` without an explicit configuration file fails with “No 'script_location' key found.”

Local checks at this revision confirm the offline API suite passes (197 passed); Ruff reports one unformatted production file; and all 68 frontend unit tests pass locally. Thus the CI discovery failures are real CI evidence but were not reproduced in this local run.

The canonical Shopping status remains: Phases 6–9 are not accepted, and hosted deployment is not verified. See [current state](../../../shopping-assistant/docs/current-state.md), [Phase 6 review](../../../shopping-assistant/docs/planning/phase-6-review.md), [runbook](../../../shopping-assistant/docs/deployment/runbook.md), and [Phase 30 destination evidence](../../../shopping-assistant/docs/planning/phase-30-federation-destination-evidence.md).

## Gate 1 local repair evidence

The local working-tree diff addresses the baseline formatter failure, canonical rejection enum fixture drift, discovery form initialization race, container smoke's missing Alembic config, and stale generated API types. A second PostgreSQL issue found after correcting the enum was a test-only timestamp comparison: it compared `Z` and `+00:00` strings rather than aware instants. The assertion now parses both timestamps and still requires both values to be present.

Verified on the uncommitted diff: API Ruff lint/format passed across 176 files; the offline API suite passed 197 tests; the PostgreSQL suite passed 129 tests with 198 deselected against the local PostgreSQL 17 `shopping_test` database; API generated-type freshness passed after regeneration; frontend had 69 tests pass plus ESLint, TypeScript, and Vite build; Alembic `upgrade head` and `check` passed when invoked from `/tmp` with the packaged config path. The known SQLAlchemy foreign-key-cycle and Starlette/httpx deprecation warnings remain. The generated diff adds optional context fields `partial_result`, `omitted_count`, and `selection_policy_version`.

The workflow now uses `/app/apps/api/alembic.ini`, matching the Dockerfile copy destination. Docker is unavailable, so the actual image smoke was not executed. Hosted GitHub Actions was not rerun on this working tree, and local frontend validation used Node 24.19.0 rather than CI Node 20. Gate 1 remains locally verified but not externally accepted.

## Destination identity, task, and idempotency boundary

Shopping has no accepted incoming typed-task host. Its Personal AI integration exposes a gated, read-only context route. It authenticates a Personal AI service token and forwarded Google user token, then maps the exact configured user to the deployment’s single Firebase owner. Both sides default the context feature off. This is a fixed single-owner mapping, not a general delegated-user grant store.

The application generation seam is `PersonalAIClient.generate(AIRequest) -> AIResponse`; external mode selects `UnavailablePersonalAIClient` and makes no network request. Durable research jobs persist Shopping run/job ownership and leases but carry no delegated-user identity or grant dependencies. Existing request-key idempotency belongs to owner/project Shopping commands. There is no destination task identity, cross-app idempotency record, or accepted result lifecycle. These facts make Finance → Personal AI → Shopping the first integration blocker for the suite, not a completed Shopping capability.

## Remaining Gate 1 verification

Run hosted GitHub Actions against the repaired diff when an authorized commit/PR or other CI mechanism is available; specifically verify its Node 20 frontend job and actual Docker image smoke. The main-branch CI failure remains evidence about the baseline SHA and must not be rewritten as a passing hosted result. Separately assess the SQLAlchemy foreign-key-cycle warning. Keep cloud acceptance and typed-task work gated behind their documented identity, recovery, and predecessor-phase requirements.

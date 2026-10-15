> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Personal Finance stabilization status

Date: 2026-10-13
Gate status: 0 complete; 1 offline checks green, PostgreSQL/browser acceptance pending; 2 bounded docs/navigation review complete, broader quality pass pending
Repository: `jasonkli21/personal-finance-and-investments`
Branch: `main`
Tested revision: `495c21186b68215bf110ab6ab3115cd67190cc67` (`Add scoped monthly discretionary budget export`)
Current worktree: uncommitted Gate 1 and documentation changes; HEAD remains the baseline SHA. The clean-worktree statement below describes the Gate 0 inspection only.

Gate 0 established the baseline at `495c21186b68215bf110ab6ab3115cd67190cc67`. It confirmed that CI run 38265069585 stopped at stale generated API output: the backend schema already included `GET`/`PUT /v1/finance/discretionary-budgets/{period}` and the monthly-budget read/write schemas. The clean-worktree observation and pre-change failures below are historical Gate 0 evidence.

## Gate 1–2 checkpoint — 2026-10-13

The canonical `pnpm api:generate` has now refreshed `apps/web/src/api/openapi.json` and `schema.d.ts`; `pnpm api:check` passes. The valuation test failure was caused by its October 1 quote being older than the seven-day policy at the October 13 run date. Its expected `$198` was valid for a fresh quote, so the test now freezes read time at October 2; no production valuation behavior changed. Full offline `pnpm check` passes: **244 passed, 55 skipped**. The run used pinned pnpm 11.19.0, a synthetic private directory, and no database/provider credentials.

The PostgreSQL endpoint `127.0.0.1:55439` was not listening during verification. The 55 skips therefore remain outside the accepted evidence, and no PostgreSQL-backed suite or browser journey has run in this checkpoint. The Playwright runner’s destructive schema reset is limited by its guard to an explicitly authorized loopback database whose name ends in `_test`; use only a separate synthetic database.

Gate 2 review clarified the OpenAPI generation path in Finance documentation and reviewed the largest handwritten modules. No file-size-only refactor was made; higher-risk module/UI splits are deferred until the existing PostgreSQL and browser journey coverage can run. The working tree remains uncommitted and tested against the baseline HEAD above.

## Baseline evidence

| Check | Result |
| --- | --- |
| `git status --short --branch`; `git rev-parse HEAD` | Clean `main...origin/main`; exact SHA above |
| GitHub Actions `Quality`, run [38265069585](https://github.com/jasonkli21/personal-finance-and-investments/actions/runs/38265069585) | **Failure** on this exact SHA; `pnpm check` stops at `pnpm api:check`, reporting `apps/web/src/api/openapi.json is stale`. Lint, typecheck, tests, build, and browser journeys did not run in this job. |
| Previous green main run | [37640080597](https://github.com/jasonkli21/personal-finance-and-investments/actions/runs/37640080597), SHA `7b34529`; predates the current Phase 28/30 changes. |
| `node scripts/check-generated-api.mjs` with repository Node/uv/pnpm runtimes and temporary `PRIVATE_FILE_DIR`/`UV_CACHE_DIR` | **Failed as expected** on stale OpenAPI. The default local `.private` path is not writable under this sandbox; the supported temp-directory override made the check executable. |
| `uv run --directory services/api --locked pytest -q -p no:cacheprovider --basetemp=/private/tmp/finance-baseline-pytest-budget tests/test_finance_context.py tests/test_discretionary_budget.py` | **15 passed**. |
| `uv run --directory services/api --locked pytest -q -p no:cacheprovider --basetemp=/private/tmp/finance-baseline-pytest tests/test_stage1_imports.py::test_cached_quote_asof_precedence_and_signed_percentages` | **1 failed**: `total_usd` was `None`, expected `198.0000000000`. This matches the already documented valuation issue; causality still needs comparison at a clean pre-change revision. |
| `uv run --directory services/api --locked alembic heads` | `0019_monthly_discretionary_budgets (head)`. |
| Full `pnpm check`, full database suite, browser E2E, cloud/provider tests | Not run for Gate 0; no claim of acceptance. CI exited before these stages. |

The local Python commands used `UV_NO_SYNC=1`, a temporary `UV_CACHE_DIR`, and `PRIVATE_FILE_DIR=/private/tmp/finance-baseline-private`; test cache and temp paths were also moved under `/private/tmp`. The initial un-overridden local attempt was blocked while the app tried to `chmod` the ignored `services/api/.private` directory. That sandbox error is not a product test result.

## Reconciled delivery boundary

- Portfolio/exposure, local history/performance, supplied-lot planning, reviewed transaction workflows, and deterministic/manual research exist locally as documented.
- Stage 2 ingestion remains partial: OCR/shared extraction, account sync, recurring/month coverage, parsed-output reuse/cleanup, complete worker lifecycle, and benchmark acceptance remain open.
- Stage 4 is prepared infrastructure, not an accepted deployment. No GCP/Firebase/Neon/GCS deployment or recovery rehearsal is evidenced.
- Finance context is a default-off, read-only `finance-context-read-v1` integration. Synthetic token/principal tests do not establish deployed identity or owner authorization.
- Phase 30 has a local, revisioned monthly budget with explicit Shopping consent and a narrow amount/currency/period export. Consent defaults off and verify rechecks current consent/source version. There is no accepted downstream user-bound Shopping task host, so Finance → Personal AI → Shopping is not end-to-end available.

## Minimum documentation path

Begin with Finance `AGENTS.md`, `docs/README.md`, and `docs/current-state.md`. For the next CI fix, inspect `docs/02-architecture.md`, the API exporter/checker, the web generation command, and current code. For ingestion, add `docs/05-roadmap.md`, `docs/stage-2-implementation-plan.md`, `docs/stage-2-release.md`, and `docs/07-postgres-neon.md`. For Finance context/budget integration, add `docs/adr/0001-shared-personal-ai.md`, `docs/phase-28-personal-ai-integration-evidence.md`, and `docs/phase-30-discretionary-budget-evidence.md`. For any cloud acceptance, add `docs/06-security-and-deployment.md`, `docs/adr/0002-gcp-neon.md`, `docs/gcp-neon-migration.md`, `docs/stage-4-release.md`, and the Stage 4 operations/recovery runbooks. Plans order work; code and dated evidence establish delivery.

## Next action

When the root-managed synthetic PostgreSQL service is available, run the PostgreSQL-backed test set and the guarded Playwright journeys against a dedicated `_test` database. Record exact results and remaining gaps before deciding whether to split any of the large stateful modules. Re-run hosted CI after the worktree is ready for review; the historical CI failure still describes the unmodified baseline SHA.

Supporting files: [prioritized findings](FINDINGS.md), [size inventory](CODE-QUALITY.md), [QA baseline](QA.md), and [cloud acceptance](CLOUD-ACCEPTANCE.md).

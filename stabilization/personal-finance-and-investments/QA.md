> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Finance QA baseline

Baseline revision: `495c21186b68215bf110ab6ab3115cd67190cc67`. QA separates local executable checks from cloud or provider acceptance; the latter were not performed.

## Gate 0 baseline checks

| Check | Outcome |
| --- | --- |
| Current GitHub Quality run, [38265069585](https://github.com/jasonkli21/personal-finance-and-investments/actions/runs/38265069585) | Failed at `pnpm api:check` on stale `apps/web/src/api/openapi.json`. Because the workflow chains checks with `&&`, lint, formatting, typecheck, full tests, build, and browser journeys did not execute on this SHA. |
| Canonical API checker with temp runtime/file-store settings | Reproduced stale OpenAPI. Generated output adds `GET` and `PUT /v1/finance/discretionary-budgets/{period}` and two monthly-budget schemas. |
| Finance context and budget tests | `tests/test_finance_context.py tests/test_discretionary_budget.py`: 15 passed. |
| Known portfolio valuation test | At baseline, `tests/test_stage1_imports.py::test_cached_quote_asof_precedence_and_signed_percentages` returned `None` because the quote was stale under the seven-day rule on the run date. Gate 1 froze read time to keep this precedence test deterministic; the corrected test passes with the original `$198` expectation. |
| Migration head | Alembic reports `0019_monthly_discretionary_budgets`. |
| Full local suites / E2E | Not run in Gate 0. No cloud, live identity, provider, or production-readiness claims are made. |

For targeted offline runs under this sandbox, direct `uv run --directory services/api --locked pytest` worked when using `UV_NO_SYNC=1`, a temporary `UV_CACHE_DIR`, `PRIVATE_FILE_DIR=/private/tmp/finance-baseline-private`, and `-p no:cacheprovider --basetemp=/private/tmp/...`. The initial default file-store path attempted to chmod the ignored `.private` folder and was denied; rerunning with the supported temp path avoids touching existing private files.

## Gate 1 current local verification — 2026-10-13

Tested worktree on baseline HEAD `495c21186b68215bf110ab6ab3115cd67190cc67` with uncommitted changes. The canonical API generation and freshness check passed. Full pinned `pnpm check` passed API freshness, ESLint/Ruff, Prettier/Ruff format checks, TypeScript, mypy (**117 source files**), web tests (**8 files, 22 tests**), infra contracts (**6 tests**), backend pytest (**244 passed, 55 skipped**) and production build. Vite emitted its existing large-chunk advisory.

The command ran with `TEST_DATABASE_URL`, `DATABASE_URL`, Neon and recovery admin variables unset, `PRIVATE_FILE_DIR=/private/tmp/finance-stabilization-private`, and temporary uv/pytest/mypy paths under `/private/tmp`. PostgreSQL at `127.0.0.1:55439` did not respond. No database, cloud, provider, identity, browser, or production acceptance is implied by this offline result. `pnpm --filter web exec playwright test --list` discovered **7 tests in 2 files**. None was launched; the E2E server requires `E2E_DISPOSABLE_DATABASE=1` and a loopback `E2E_DATABASE_URL` ending in `_test`, then replaces that test database's public schema before migrating.

## QA coverage map and gaps

| Journey | Current code/test surface | Gate still needed |
| --- | --- | --- |
| Portfolio, holdings, valuation, exposure | Stage 1 routes/domains and `test_stage1_*`; cached-quote chronology now uses a fixed valuation clock in its test fixture. | Run the PostgreSQL/browser journey and exercise stale/missing quotes, currency, reconciliation, and cross-owner denial. |
| History and performance | Stage 3 history services and tests. | Verify gaps, contribution/withdrawal treatment, date boundaries, stale/future data, and immutable snapshot semantics. |
| Supplied lots, sale, allocation, liquidity | Stage 3 tax/planning contracts and `test_stage3_*`. | Confirm hypothetical-only semantics, partial/fractional selections, invalid quantities/dates, revision behavior, and explicit dated-lot limitations. |
| CSV/manual transaction review | Stage 2 imports/transaction domains and `test_stage2_*`. | Duplicate/reformatted imports, malformed rows, review-before-commit, split/transfer accounting, retries, job restart/cancel, delete/reprocess, and source provenance. OCR and scanned PDF remain unimplemented. |
| Spending and budget | `test_discretionary_budget.py`, `test_finance_context.py`; 15 relevant tests passed. | Browser reconciliation, period/currency boundaries, incomplete-month representation, and end-to-end downstream consent/revocation once a task host exists. |
| Research/thesis/watchlist | `test_stage5_research.py`, deterministic/manual flows. | Frozen result stability, contradictory/missing evidence, list completeness, and authoritative live-source authenticity when live retrieval is authorized. |
| Auth/session/cloud | Synthetic config/auth tests and infrastructure contracts. | Hosted OIDC/PKCE, cookie/CSRF, cross-user denial, private GCS access, Cloud Run direct-call restrictions, real Neon behavior, and log redaction. |
| Finance context read | Synthetic token, owner binding, source-version and bounded projection tests; default-off. | Real caller/user identity, active owner mapping, revoked grant, deployed private route, read-only DB principal, provider privacy and recovery. |
| Finance → Personal AI → Shopping | Narrow Finance budget projection/verify only; no task transport or destination host. | Shared delegated identity, version/capability validation, idempotent task persistence, retry/timeout/uncertain-result semantics, destination execution, and user-bound replay/revocation tests. |

## Recommended acceptance order

1. Re-run the PostgreSQL-backed suite and guarded browser journeys against separate synthetic `_test` databases; record exact commands, revisions, and failures.
2. Preserve the generated API freshness gate and run hosted CI when the worktree is ready for review.
3. Reassess candidate code splits only after the stateful journeys have executable coverage.
4. Add missing Stage 2 lifecycle and provenance scenarios before declaring ingestion trustworthy.
5. Keep cloud and delegated typed-task claims gated until live staging and cross-repo tests produce their own evidence.

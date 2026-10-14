> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Finance code and context inventory

Inventory date: 2026-10-13. Revision: `495c21186b68215bf110ab6ab3115cd67190cc67`. The inventory uses `git ls-files`; it excludes ignored/build output and counts newline-delimited lines with blanks included. Directory totals are recursive and overlap their child directories. Directory category is the category contributing the most bytes.

## Largest tracked files

| File | Bytes | Lines | Category |
| --- | ---: | ---: | --- |
| `apps/web/src/api/openapi.json` | 382,480 | 14,872 | Generated contract |
| `apps/web/src/api/schema.d.ts` | 203,172 | 8,549 | Generated contract |
| `services/api/uv.lock` | 154,578 | 1,139 | Configuration/manifest |
| `pnpm-lock.yaml` | 97,056 | 2,865 | Configuration/manifest |
| `services/api/app/recovery/archive.py` | 68,066 | 1,581 | Handwritten production |
| `services/api/app/domains/transactions.py` | 65,936 | 1,708 | Handwritten production |
| `services/api/app/db/models.py` | 60,146 | 1,412 | Handwritten production |
| `apps/web/src/TaxLotWorkspace.tsx` | 57,132 | 1,465 | Handwritten production |
| `services/api/app/domains/tax.py` | 46,763 | 1,230 | Handwritten production |
| `services/api/app/domains/imports.py` | 46,121 | 1,238 | Handwritten production |
| `apps/web/src/StageOneWorkspace.tsx` | 45,651 | 1,159 | Handwritten production |
| `apps/web/src/PlanningWorkspace.tsx` | 43,770 | 1,074 | Handwritten production |
| `apps/web/src/SpendingWorkspace.tsx` | 43,523 | 1,285 | Handwritten production |
| `apps/web/src/PortfolioScenarioWorkspace.tsx` | 41,503 | 1,081 | Handwritten production |
| `apps/web/src/ResearchWorkspace.tsx` | 40,749 | 1,052 | Handwritten production |
| `services/api/app/domains/finance_context.py` | 40,731 | 1,088 | Handwritten production |
| `apps/web/src/App.tsx` | 37,385 | 988 | Handwritten production |
| `services/api/app/domains/planning.py` | 35,146 | 855 | Handwritten production |
| `services/api/tests/test_stage5_research.py` | 31,649 | 867 | Handwritten tests |
| `services/api/app/domains/portfolio_scenarios.py` | 31,320 | 798 | Handwritten production |

## Largest tracked directories

| Directory | Bytes | Lines | Dominant category |
| --- | ---: | ---: | --- |
| `services/` | 1,616,748 | 40,822 | Handwritten production |
| `apps/` | 1,031,080 | 35,694 | Generated contract |
| `docs/` | 859,602 | 8,105 | Documentation |
| `services/api/app/` | 952,790 | 25,569 | Handwritten production |
| `apps/web/src/api/` | 607,748 | 24,271 | Generated contract |
| `docs/history/` | 551,778 | 5,334 | Documentation |
| `services/api/app/domains/` | 473,504 | 12,558 | Handwritten production |
| `services/api/tests/` | 419,684 | 11,873 | Handwritten tests |
| `services/api/app/api/` | 161,115 | 4,858 | Handwritten production |
| `services/api/alembic/versions/` | 82,689 | 1,983 | Migrations |
| `services/api/app/recovery/` | 72,398 | 1,700 | Handwritten production |
| `docs/history/pre-gcp-neon/` | 501,474 | 4,275 | Documentation |

The generated web API spec and types dominate bytes and lines in the web API subtree. This is expected contract output, but CI must keep it generated and reviewed with source changes. The largest hand-written code concerns coherent domains (transactions, import/recovery, finance context, tax/planning) and substantial stateful UI workspaces; their size alone does not justify a split. The largest test hotspots include research evaluation and schema setup; review duplication and fixture shape only when changing those areas. Documentation is deliberately dated and routed; historical records should stay out of routine task context.

## Navigation and implementation observations

- Canonical source and generated output are discoverable: backend FastAPI schema is emitted by `services/api/app/export_openapi.py`; `pnpm api:generate` writes web OpenAPI and TypeScript; `pnpm api:check` regenerates to temp and checks freshness.
- The current CI failure is precisely the kind of generated drift that the contract gate is meant to catch. The Phase 30 routes were added without refreshing the generated web files.
- Use `docs/README.md` as the context router and `docs/current-state.md` as the delivery boundary. Do not treat implementation plans or historical release records as current test results.
- After Gate 1 protects behavior, inspect the workspace modules for clear domain/view-model ownership splits and `transactions.py`/`archive.py` for cohesive lifecycle boundaries. Avoid moving financial calculation policy across modules merely to lower line counts.

## Gate 2 bounded review — 2026-10-13

Reviewed the largest handwritten production and test files from the Gate 0 inventory and inspected the local Playwright journey map. The current module boundaries remain reasonable for this checkpoint: `archive.py` owns a high-risk encrypted archive/verify/restore protocol; `models.py` defines one connected ORM metadata graph; `transactions.py` contains staged import/publish/cancel plus canonical transaction, split, and transfer operations; `finance_context.py` couples bounded projections to source-version verification. The large React workspaces hold stateful review flows. A future decomposition may be useful, especially around transaction import lifecycle and spending review state, but only if it follows those state/lifecycle boundaries and preserves the existing journeys. No broad extraction was made while PostgreSQL and browser acceptance were unavailable.

The generated OpenAPI and TypeScript outputs remain visibly generated artifacts. The Finance docs now name their FastAPI source, canonical `pnpm api:generate` command, and temporary-output freshness check. This addresses the concrete discovery failure that caused the baseline CI break without introducing a parallel contract source.

Gate 3 preparation: the browser suite contains one Stage 1 portfolio/ETF/report-export journey and six focused regression journeys for transaction revision fencing, sign-out refresh fencing, transaction pagination, research-source reset, tax-lot stale saves, and account-bound position review. Its helper requires explicit disposable-database opt-in and drops the public schema only after validating a loopback `*_test` database. Keep all future runs on synthetic DBs. Current PostgreSQL service at `127.0.0.1:55439` was unavailable, so no browser run is claimed.

# Five-repository re-review verification — 2026-10-14

This record covers the Luna XHigh fixes against the reviewed baselines below.
The independent review document supplied for this task described findings and
acceptance criteria; it did not override repository authority, security
boundaries, or existing tests. This file records local evidence only.

## Source revisions

| Repository | Reviewed baseline | Fix commit |
| --- | --- | --- |
| Personal AI | `20ef41ae6b76de691c003ae6a345fdb91b3ecd02` | Resolve with `git log -1 --format=%H -- stabilization/FRESH-REVIEW-HANDOFF.md` |
| Shopping | `197849e545ae74f1860a58054c8a741ccb39d9e5` | `720efc925b34ca06b4e429e0a180d1a360761029` |
| Finance | `8097060f7734525f2c8294bc77f2325d47f2c7d4` | `a6a848ac8314a5a8bfcc7a66cb9df30dd48f42b7` |
| Travel | `4836fb82d45a66ed2fab726eff4e31e09f9ae8fa` | `61a708b257cb9862bc415ce8a7151201489d3472` |
| Health | `c3020b9c6926fd6454e5fe95b0d7fa5fa13ebb00` | `5112cad381cc38900bd1333c95fdc87c0668f00` |

Personal AI contains this record, so its hash is resolved from the committed
handoff path to avoid a self-referential hash.

## Local/native results

All native suites used the owned loopback PostgreSQL 17 cluster at
`127.0.0.1:55439`, role `suite_stabilization`. Runners created and removed
UUID-named test databases. Provider, Google IAM, and Firebase lookups were
synthetic; PostgreSQL locking, migrations, signatures, source routes, Shopping
transactions, receipts, and loopback HTTPS behavior were exercised locally.

| Scope | Result | Evidence |
| --- | --- | --- |
| Personal AI offline backend | 1,749 passed, 90 deselected | `/private/tmp/pai-re-review-offline.log` |
| Personal AI native PostgreSQL | 75 passed, 14 skipped, 1,752 deselected | `/private/tmp/pai-re-review-final.log`; skipped cases require unavailable DynamoDB |
| Shopping native PostgreSQL | 142 passed, 198 deselected | `/private/tmp/shopping-re-review-rerun.log` |
| Finance native PostgreSQL | 294 passed, 11 skipped | `/private/tmp/finance-re-review.log` |
| Travel native PostgreSQL | 344 passed | `/private/tmp/travel-re-review-rerun.log` |
| Health native PostgreSQL | 282 passed | `/private/tmp/health-re-review.log` |
| Five-app delegated-task matrix | 40 passed | `/private/tmp/suite-task-re-review-rerun.log` |
| Planning freeze | 30 cases; non-promotion; 0 promoted coverage | `/private/tmp/pai-planning-v14.json` |

The first full matrix run had one submit-time 403 in the stale-destination
case. That case passed in isolation, and the complete matrix passed on rerun
without changing authorization behavior.

Personal AI's planning v14 lock keeps v13 and earlier locks unchanged, preserves
the same planner, configuration, runtime, fixtures, and 30-case corpus, and
binds source identity to the reviewed base plus its identical-source direct
child. The run had 18 cases with no failure, 2 lexical omissions, 1 irrelevant
selection, 8 expected policy/source exclusions, and 1 required-source denial.
The decision remains non-promotion; no model-answer quality evidence or
promoted coverage is claimed.

## Web and generated-contract results

| Repository | Local result |
| --- | --- |
| Finance | Generated OpenAPI equality passed; TypeScript, ESLint, 23 tests in 9 files, and production Vite build passed. |
| Shopping | Generated API types are current; TypeScript, ESLint, 69 tests in 9 files, and production Vite build passed. |
| Travel | TypeScript, ESLint, 68 tests, and optimized Next.js production build passed. |
| Health | API/OpenAPI client regenerated and formatted; mobile TypeScript, ESLint, and 163 tests in 34 files passed; historical migration hash test passed. ESLint reported 6 pre-existing test warnings and no errors. |

The Finance and Shopping Vite builds emitted the existing large-chunk advisory;
both builds completed successfully. Shared task-contract generation passed and
all five isolated runtime manifests matched. The Health migration lock covers
the 17 pre-existing migration files. Personal AI targeted Ruff checks passed.
`git diff --check` passed in the Personal AI checkout; all repository diff
checks and changed-document link checks are rerun before commit.

Raw generated inventory and manifest output is reproducible through
`stabilization/scripts/inventory.py` and
`stabilization/scripts/check_isolated_contracts.py`. Current output is written
under ignored `stabilization/evidence/`; dated files under
`stabilization/archive/2026-10-14/evidence/` remain historical snapshots.
The review source-inventory output SHA-256 is
`566e069e546257b7d1256c95bc8a5ce9cea4a929108735fb6c6a99e6bc70ee21`; the
isolated-manifest output SHA-256 is
`15e379885e2e265cc069d1c2028936fec823a02d629e618918cb3111792a9a76`. The
inventory's application/runtime source-tree digests are:

| Repository | Source-tree SHA-256 |
| --- | --- |
| Personal AI | `5c2800bf687e45b27974a4f2df6c3272bf2b56026cbf4ffb95c87ab2cf7d5c56` |
| Shopping | `74ecce9b2a33ed6123bb52b2d4c431e1c0ac04af1cbf15513cae9da45a41b7ba` |
| Finance | `d6008781f4c7c39925c17fbf044028a8937c7242ec18d66975ad00dd19440848` |
| Travel | `18c5753a30477b76585bb3b22a646237572846248b726929832541790480edf3` |
| Health | `91fc3dc528bc60166eecd40e07b5f7b632262d4ac5b5e2dc55762d41f7e95921` |

These hashes cover the application/runtime trees selected by the inventory
generator; the Git commit table above anchors the complete reviewed changes,
including tests and documentation. Generator inputs and historical baseline
revisions remain preserved in the archive.

## Reproduction commands

Run from the Personal AI checkout unless a repository path is shown:

```sh
backend/.venv/bin/python -m pytest -p no:cacheprovider -m 'not persistence_integration and not cloud_smoke' --ignore=tests/test_gemini_manual.py --ignore=tests/test_context_manual.py
backend/.venv/bin/python stabilization/scripts/run_native_tests.py personal-ai --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres --log /private/tmp/pai-re-review-final.log
backend/.venv/bin/python stabilization/scripts/run_native_tests.py shopping --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres --log /private/tmp/shopping-re-review-rerun.log
backend/.venv/bin/python stabilization/scripts/run_native_tests.py finance --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres --log /private/tmp/finance-re-review.log
backend/.venv/bin/python stabilization/scripts/run_native_tests.py travel --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres --log /private/tmp/travel-re-review-rerun.log
backend/.venv/bin/python stabilization/scripts/run_native_tests.py health --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres --log /private/tmp/health-re-review.log
backend/.venv/bin/python stabilization/scripts/run_native_tests.py tasks --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres --log /private/tmp/suite-task-re-review-rerun.log
backend/.venv/bin/python backend/scripts/sync_task_contracts.py --check
backend/.venv/bin/python stabilization/scripts/check_isolated_contracts.py
/Users/jasonkli/projects/health-app/services/api/.venv/bin/python stabilization/scripts/inventory.py
```

Repository-specific frontend commands used the checked-in locked dependencies
and bundled Node 24.19.0. Finance ran `tsc --noEmit -p tsconfig.json`,
`eslint src test vite.config.ts vitest.config.ts eslint.config.js --max-warnings 0 e2e playwright.config.ts`,
`vitest run`, `vite build`, and `scripts/check-generated-api.mjs`.
Shopping ran API type generation check, `tsc -b`, `eslint .`, `vitest run`,
and `vite build`. Travel ran its frontend typecheck, lint, test, and Next.js
build scripts. Health regenerated OpenAPI and its typed client, ran mobile
typecheck/lint/tests, and checked the migration byte-lock.

## CI and external acceptance

No CI result for these five fix commits is asserted. Push starts the repositories'
normal CI; check those runs separately against the resulting commit SHAs.

Local evidence does not establish real Cloud Run IAM or Google service-token
acquisition, certificate rotation, live Firebase linked-account/revocation
behavior, multi-instance ordering, live model/provider behavior, browser/mobile
rendering in real sessions, HealthKit device behavior, cloud object-store IAM
or retention, cloud backup/restore, approved RPO/RTO, process kill/restart at
effect boundaries, mixed-version deployment/drain, or legal/privacy retention
approval. Production release readiness remains false until those gates are
accepted in their real environments.

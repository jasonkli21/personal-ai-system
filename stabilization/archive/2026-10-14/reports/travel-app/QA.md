> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Travel baseline and Gate 1 QA

All local backend checks below used synthetic data only. PostgreSQL was the root-managed disposable PostgreSQL 17.11 cluster at `127.0.0.1:55439`, role `suite_stabilization`, and databases `travel_test` / `travel_restore`.

| Check | Result | Classification / limit |
| --- | --- | --- |
| GitHub run `38286358285` at baseline `09584976d46c67c97a19c72d173b2ee88dbcb31c` | Docs, frontend, and containers passed. Backend Ruff check passed; format failed, so backend mypy/tests/build/migrations were skipped. Security dependency audit passed; secret hook failed on two synthetic OAuth test fixtures. Recovery failed after migrating to `0017`. | Verified remote baseline CI; remains red until a new commit is tested. |
| Ruff lint | Passed: `All checks passed!` | Local working tree. |
| Ruff format | Passed: 164 backend files already formatted. | Local working tree. |
| mypy | Passed: 103 source files. | Local working tree. |
| Backend pytest | 334 passed, 51 warnings in 28.77 seconds. | Full suite on PostgreSQL 17.11, including the route, auth/session, migration, booking-import, attachment, context, export, and recovery-guard tests. The warnings are existing Starlette/httpx and per-request cookie deprecations. |
| API package build | Source distribution and wheel built under `/tmp/travel-api-dist`. | Local build after resolving the declared hatchling backend from PyPI; artifacts were outside the repository. |
| Encrypted recovery | Passed. | Verified synthetic SQL+blob backup, age authentication, isolated restore, revision/ORM parity, table counts, lifecycle object hashes, recovery of pending uploads, and JSON export at `0017`. Does not establish approved RPO/RTO, production backup retention, independent cloud recovery, or deletion fencing. |
| Secret scan | No new findings in full tracked source scan (baseline file omitted from the file list to avoid scanning its own hashes); temporary baseline copy used. | Existing baseline contains 29 known synthetic fingerprints; reviewed location-only changes retained. The repository hook itself refuses to run when its baseline file is unstaged, so the exact clean-checkout CI invocation cannot return green from this intentionally dirty working tree. |
| Frontend package checks | Passed: `lint`, `typecheck` (`next typegen && tsc --noEmit`), 60 Node tests, and production `build`. Pinned pnpm 10.17.1 installed the frozen lockfile. | Used the requested bundled Node v24.19.0 runtime; CI uses Node 22. The pre-existing untracked `frontend/pnpm-workspace.yaml` caused pnpm to skip the `unrs-resolver` build script. No lockfile changes. `next typegen` generates Next route types; there is no API-contract generator, and `frontend/lib/api.ts` is handwritten. |
| Local synthetic browser journey | Passed the exercised local journey: create trip, itinerary item, tentative reservation; export JSON/HTML/ICS; verify revision-stamped no-store/nosniff responses and private-field/document omission; reload and backend restart persistence; stale revision returned `409`; cross-owner read returned `404`; synthetic trip cleanup returned `204`. | Local auth and synthetic-only PostgreSQL 17 data on loopback. Research/proposals, map provider, private imports/attachments, Google OAuth, and AI/provider calls were disabled or unavailable. This does not satisfy the full Gate 3 journey matrix or external gates. |
| Frontend / container baseline CI | Green in baseline GitHub run. Frontend used Node 22 and pnpm 10.17.1; build and tests passed. API/web image build and non-root health smoke passed. | Baseline workflow is not fresh evidence for the dirty fixes tree. Docker is unavailable locally. |
| Hosted browser, OAuth/provider, cloud | Not exercised. | No Google client, hosted identity, Cloud Run/Neon, live provider, production storage, or hosted acceptance is claimed. |

Ruff, mypy, and pytest were run from `backend/`; the package build was run from the repository root:

```bash
RUFF_CACHE_DIR=/tmp/travel-ruff-cache .venv/bin/ruff check .
RUFF_CACHE_DIR=/tmp/travel-ruff-cache .venv/bin/ruff format --check .
MYPY_CACHE_DIR=/tmp/travel-mypy-cache .venv/bin/mypy src
UV_CACHE_DIR=/tmp/travel-uv-cache uv build --project backend --out-dir /tmp/travel-api-dist
```

The full pytest command used:

```bash
TEST_DATABASE_URL='postgresql+psycopg://suite_stabilization@127.0.0.1:5432/travel_test' DATABASE_URL='postgresql+psycopg://suite_stabilization@127.0.0.1:5432/travel_test' PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q --tb=short
```

A temporary loopback forward sent port `5432` to the authorized PG17 server at `55439` because `backend/tests/fixtures/synthetic_identity_server.py` intentionally accepts only loopback port 5432. The port had no listener before the test, and the forward was stopped after the suite. The root-owned cluster remained untouched.

The encrypted restore was run from `backend/` with PostgreSQL 17 tools and `age` v1.3.2 on `PATH`:

```bash
PATH=/tmp/travel-age-v1.3.2/bin:/opt/homebrew/opt/postgresql@17/bin:$PATH RECOVERY_SOURCE_DATABASE_URL='postgresql+psycopg://suite_stabilization@127.0.0.1:55439/travel_test' RECOVERY_RESTORE_DATABASE_URL='postgresql+psycopg://suite_stabilization@127.0.0.1:55439/travel_restore' PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m scripts.recovery_smoke
```

Frontend commands ran from `frontend/` using the bundled Node runtime and the
manifest-pinned pnpm version:

```bash
export PATH=/Users/jasonkli/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH
pnpm dlx pnpm@10.17.1 --version
CI=true PNPM_HOME=/tmp/travel-pnpm-home NPM_CONFIG_STORE_DIR=/tmp/travel-pnpm-store XDG_CACHE_HOME=/tmp/travel-pnpm-cache pnpm dlx pnpm@10.17.1 install --frozen-lockfile
pnpm dlx pnpm@10.17.1 run lint
pnpm dlx pnpm@10.17.1 run typecheck
pnpm dlx pnpm@10.17.1 test
pnpm dlx pnpm@10.17.1 run build
```

The built standalone app and backend ran bound to loopback only, in explicit
local-auth/local-deployment mode, against the disposable `travel_test` database.
Synthetic traveler content only was used. The browser created one Copenhagen
trip, one itinerary item, and one tentative lodging reservation, then used the
UI's three export downloads. The HTTP proxy returned JSON, HTML, and ICS with
revision and attachment headers, `Cache-Control: no-store`, and
`X-Content-Type-Options: nosniff`; private reservation fields and attached
documents were omitted. The JSON export included the synthetic lodging name
after it was added but omitted its synthetic confirmation code. Reload and a
backend restart preserved the local trip. A write using an old revision got
`409` without changing data; a cross-owner read got `404`. Deleting the journey
trip returned `204`, and a direct SQL count confirmed its trip, reservation,
and days were gone while the separate recovery-smoke owner row remained.

This is a narrow browser acceptance sample, not Gate 3 completion. It did not
exercise every create/edit/delete journey, uncertain network retry, UI stale
draft recovery, attachment/import lifecycle, provider-dependent journey,
multi-user Google-auth boundary, or production restart. No map key was present;
research, proposals, comparisons, private imports, and attachments stayed
disabled. Frontend checks used Node 24.19.0 because that is the requested
bundled runtime; the GitHub job's Node 22 environment remains the CI authority.

The output reported source/restored Alembic revision `0017`, `backup_verified: true`, 1 trip, 1 reservation, 1 itinerary proposal, 1 booking import, 4 private objects (2 ready and 2 pending), zero unreferenced objects, and a passing application export. The smoke source and destination are separate; the source is explicitly migrated to the repository head first.

Remote main remains unmodified and no fresh CI run was triggered. A new CI run is required to validate the edited tree on its Ubuntu/PostgreSQL 16 workflow; local PG17 evidence is supplemental only.

For secret scanning, `backend/.venv/bin/detect-secrets-hook --baseline <temporary copy of .secrets.baseline> <341 tracked paths excluding .secrets.baseline> backend/tests/test_recovery_smoke.py` exited 0. The tracked baseline was intentionally left unstaged, so the exact CI hook command refuses to proceed against the working-tree baseline; the temporary copy scan checks all tracked source plus the newly added test without staging or blind-baselining.

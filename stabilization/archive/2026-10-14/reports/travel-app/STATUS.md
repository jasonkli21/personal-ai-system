> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Travel Gate 0/1 plus bounded Gate 2/3 checkpoint

Date: 2026-10-13 PDT. Baseline revision: `09584976d46c67c97a19c72d173b2ee88dbcb31c`.

Gate 0 evidence is recorded in [findings](FINDINGS.md), [code inventory](CODE-QUALITY.md), [QA](QA.md), and [cloud acceptance](CLOUD-ACCEPTANCE.md). Gate 1 backend/recovery fixes and the frontend lint, type, test, and build checks pass locally; Gate 1 remains open because the working tree is uncommitted and the remote workflow has not been rerun. Gate 2's bounded responsibility review is documented in [code inventory](CODE-QUALITY.md); no behavior-preserving code change was justified without broader contract/security review. A local synthetic browser journey exercised trip, itinerary, reservation, export, stale-write, cross-owner, reload, and restart behavior; this is partial local evidence only, not full Gate 3 acceptance. No commit, push, deployment, or PR was made.

The [GitHub Actions run 38286358285](https://github.com/jasonkli21/travel-app/actions/runs/38286358285) was confirmed at the baseline revision. Docs, frontend, and container jobs passed. Backend Ruff check passed, but formatting failed on `backend/src/personal_travel/api/routes/personal_ai_context.py` and `backend/tests/test_personal_ai_context.py`; later type, test, package, and migration steps were skipped. Dependency audit passed, while detect-secrets flagged two test-only OAuth fixture values. The recovery job migrated through `0017` and then failed because the smoke still required `0015`.

The recovery guard now derives the single repository Alembic head and still rejects a mismatched source revision. The first corrected local run exposed a test-fixture hard-link direction error before any backup occurred; that fixture is fixed. A complete encrypted backup, verification, isolated restore, restored schema/ORM check, and application export smoke then passed at revision `0017`. The other locally exposed issues were stale mypy typing in the read-only context projection, an auth test that expected `401` for the deliberately default-off context route (which intentionally stays hidden with `404`), and a migration test pinned to `0015` instead of checking rollback to its starting revision. These were corrected with bounded changes and regression coverage.

Local verification:

- `RUFF_CACHE_DIR=/tmp/travel-ruff-cache .venv/bin/ruff check .` — passed.
- `RUFF_CACHE_DIR=/tmp/travel-ruff-cache .venv/bin/ruff format --check .` — 164 files already formatted.
- `MYPY_CACHE_DIR=/tmp/travel-mypy-cache .venv/bin/mypy src` — passed, 103 source files.
- `TEST_DATABASE_URL='postgresql+psycopg://suite_stabilization@127.0.0.1:5432/travel_test' DATABASE_URL='postgresql+psycopg://suite_stabilization@127.0.0.1:5432/travel_test' PYTHONDONTWRITEBYTECODE=1 .venv/bin/python -m pytest -p no:cacheprovider -q --tb=short` — 334 passed, 51 Starlette deprecation warnings, on PostgreSQL 17.11.
- `UV_CACHE_DIR=/tmp/travel-uv-cache uv build --project backend --out-dir /tmp/travel-api-dist` — source distribution and wheel built successfully.
- The encrypted recovery smoke passed with source and destination `travel_test` / `travel_restore`, both on the root-owned PostgreSQL 17 cluster at port `55439`; `age` v1.3.2 and PostgreSQL 17.11 client tools were used from `/tmp` and Homebrew’s PostgreSQL 17 path. It reported `backup_verified=true`, source/restored revision `0017`, 1 trip, 1 reservation, 1 proposal, 1 booking import, 4 private objects (2 ready, 2 pending), no unreferenced objects, and `application_export=passed`.
- The existing Uvicorn fixture accepts only the usual local port 5432. Since no service was listening there, a temporary loopback-only forward from 5432 to 55439 let the unchanged disposable-database guard run; it was stopped after the suite. The PostgreSQL cluster itself remained under root ownership.
- The secret scan found no new findings using a temporary copy of the reviewed baseline against all tracked files except the baseline file itself, plus the new recovery regression test. The repository hook updates its baseline and refuses an unstaged baseline; see [findings](FINDINGS.md) for the reviewed fingerprint/line-number changes.

The repository’s pre-existing untracked `docs/reviews/phase-9-independent-review.md` and `frontend/pnpm-workspace.yaml` were preserved. Docker is unavailable locally. The GitHub container job passed at the baseline revision, but local image smoke, current-HEAD GitHub CI, PG16 runner behavior, browser journeys, hosted identity, cloud deployment, and provider acceptance remain unverified. Phase 9 is not accepted; recovery objectives, owner-wide deletion, restore-time deletion fencing, hosted identity/storage, and other Phase 9 gates remain open.

Start from Travel’s [documentation router](../../../../../../personal-travel-app/docs/README.md), [current state](../../../../../../personal-travel-app/docs/current-state.md), and [Phase 9 evidence](../../../../../../personal-travel-app/docs/releases/phase-9-operational-hardening.md).

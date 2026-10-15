> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Health app QA baseline and journey matrix

**Baseline revision:** `7fb84c76217c772b2bce6715744b8294afafa771`; latest recorded CI run [38286355765](https://github.com/jasonkli21/health-app/actions/runs/38286355765). The run predates the current uncommitted working-tree fixes.

## Automated baseline evidence

The checked-in workflow provisions PostgreSQL 17, applies Alembic to head through `services/api/tests/conftest.py`, runs the full API test suite, then runs Ruff, format, mypy, generated-client drift/type checks, mobile lint/typecheck/tests, and an iOS JavaScript export. A separate infrastructure job runs Terraform formatting, backend-disabled provider init/validate, and a local API image build.

On the latest CI run:

- scaffold verification, dependency install, and service initialization passed;
- pytest collected 271 API cases: 265 passed and the six P0 cases in [FINDINGS.md](FINDINGS.md) failed;
- the later Python static and all JS/mobile checks were skipped;
- infrastructure formatting stopped at `infra/gcp/main.tf`; provider validation and image build were skipped.

Historical baseline reproduction used an isolated PostgreSQL 17.11 database with SCRAM-authenticated loopback access. The synthetic SCRAM DSN was supplied through `HEALTH_TEST_DATABASE_URL`; its credential value is intentionally omitted here. The combined test command was:

```bash
TEST_DATABASE_URL="${HEALTH_TEST_DATABASE_URL}" .venv/bin/pytest -c services/api/pyproject.toml -p no:cacheprovider services/api/tests/test_operations_api.py services/api/tests/test_personal_ai_context_db.py -q -vv --tb=short -rs
```

That combined run showed the four context DB setup failures at the owner seed FK. The two readiness tests were then run with SCRAM authentication to reproduce the connection-URL password masking:

```bash
TEST_DATABASE_URL="${HEALTH_TEST_DATABASE_URL}" .venv/bin/pytest -c services/api/pyproject.toml -p no:cacheprovider services/api/tests/test_operations_api.py -k 'readyz_returns_sanitized_503_on_pool_exhaustion_and_recovers or readyz_bounds_slow_postgres_query_and_releases_connection' -q -vv --tb=short -rs
```

Result: both failed as expected for masked credentials; the slow-query test’s initial timeout and `checkedout()==0` assertions passed before recovery returned 503. The no-database run produced four explicit skips and is not PostgreSQL evidence. The full API suite was not run locally for this bounded baseline.

## User journeys and acceptance status

| Journey | Main trace | Existing local coverage | Current local status / next evidence |
| --- | --- | --- | --- |
| Sign-in, owner session, account switching | Mobile auth → authenticated fetch → Firebase/local API identity → owner mapping | API auth tests are included in the passing suite; mobile auth/session tests exist. | Device interaction, token expiry/revocation while active, account switch/cache isolation, and real Firebase owner mapping remain unverified. |
| Profile and canonical record lifecycle | Profile screens → `api/profile.py` → `application/profile_service.py` → health objects/revisions | PostgreSQL-backed API/domain/persistence suite passes locally. | Complete a mobile walkthrough for history/provenance, units, consent changes, stale-revision rejection, and archive/delete behavior. |
| Today and daily entries/events | Today/Add/Edit/History → `api/daily.py` → daily service → owner objects/revisions | PostgreSQL-backed API suite passes locally. | Walk timezone/DST boundaries, manual/device provenance, retry duplicates, future timestamps, and revision/history in the mobile UI. |
| Planning/schedules/trackers | Planning screens → `api/planning.py` → resources/schedules/trackers | PostgreSQL-backed API and domain tests pass locally. | Walk recurrence/timezone validity, reschedule past/future effects, stale edits, deactivation, and dangling references in the UI. |
| Insights/trends/evidence | Insights/evidence screens → analytics API/service/sources/computation/artifacts | API suite passes locally; deterministic analytics tests and evidence links exist. | Complete numerical goldens, permission/`as_of` integration, sparse/mixed-unit/timezone cases, invalidation, query plans, and device evidence. |
| Assistant/context/proposal review | Assistant → context/search → proposal review/apply/reject | Context/federation contract and PostgreSQL tests pass locally; provider messaging and AI-originated writes remain disabled. | Walk denied context, bounds/ranking, stale proposals, explicit confirmation, replay/idempotency, and revocation. UI must not imply live AI submission. |
| HealthKit import | Settings/coordinator → normalized import API → canonical daily records | Synthetic mapper/coordinator and server tests are included in the passing API suite. | Native adapter remains unavailable; no permissions/entitlements/real sync. Real-device permission, duplicate, tombstone, timezone/unit, account switch, and deletion tests remain open. |
| Export and account/domain erasure | Account Data → API export/deletion → DB/object cleanup | Local PostgreSQL-backed export/erasure tests pass. | Durable large exports, live GCS cleanup, encrypted backup restore, deletion-ledger replay, idempotent repeated erasure, and measured RPO/RTO remain open. |
| Health → Personal AI / Travel / Shopping | Health context/export APIs → shared delegation and destination adapter | Local broad context and narrow export contract tests pass; both integration gates remain default-off. | Broad identity mismatch remains. Narrow export has no deployed/live identity proof, and Health → Personal AI → Shopping typed task is not accepted end to end. |

Use Health’s [documentation router](../../../../../../health-app/docs/README.md) to find the domain-specific acceptance record before running a journey. Keep fixtures synthetic. Capture command, revision, test counts, and manual/device/cloud scope explicitly; mock/fake results must not be reported as cloud or provider behavior.

## Gate 1 final local verification — 2026-10-13

At base HEAD `7fb84c76217c772b2bce6715744b8294afafa771` plus the uncommitted fixes, the full API suite passed against PostgreSQL 17.11 SCRAM: **272 passed, 1 warning in 17.17s**. The exact command, with the synthetic credential kept out of this file, was:

```bash
TEST_DATABASE_URL="${HEALTH_TEST_DATABASE_URL}" .venv/bin/pytest -c services/api/pyproject.toml -p no:cacheprovider -q --tb=short -rs services/api/tests
```

CI-scoped Ruff lint and format, strict mypy (70 files), scaffold verification, Terraform 1.13.3 formatting, and `git diff --check` pass. The initial nine Ruff import-order findings and eleven formatting files were fixed. Three mypy diagnostics were fixed with local typing improvements. A focused Firebase/federation/context-contract run passed **36 tests**.

The current test suite is server/API evidence only. pnpm 9.15.0 is unavailable (installed version 11.25.0 violates the repository's `>=9 <10` engine), and Docker is unavailable; generated-client/Prettier/mobile checks, Expo export, Terraform init/validate, and image build did not run. `docs/current-state.md` and the README remain the minimal routes for implementation state and local setup. For a local UI journey, obtain the pinned package manager, follow the README using a separate disposable database and synthetic account, and use Expo Go or Xcode; no Firebase/cloud/device behavior is inferred from this suite.

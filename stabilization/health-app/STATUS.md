> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Health app stabilization status

**Gate:** Gate 0 reconciled; Gate 1 local API/static checks pass. A fresh hosted CI run remains pending.
**Evidence date:** 2026-10-13.
**Base HEAD:** `7fb84c76217c772b2bce6715744b8294afafa771` (`main`, same as `origin/main`).
**Tested source:** that HEAD plus the uncommitted Health working-tree changes; no commit was created.

## Current status

The latest recorded GitHub Actions run [38286355765](https://github.com/jasonkli21/health-app/actions/runs/38286355765), created 2026-10-12, is red at the base HEAD. It reported 265 API passes and 6 failures, then stopped at Terraform formatting in `infra/gcp/main.tf`. It predates the current uncommitted fixes and has not been rerun.

The current working tree fixes those issues and passes the full PostgreSQL-backed API suite. A disposable PostgreSQL 17.11 cluster on `127.0.0.1:55432` uses SCRAM for IPv4 and a synthetic `health_test` database; the test fixture applies migrations. The URL reconstruction tests pass with the original SQLAlchemy URL object, `_seed_owner()` flushes `User` before `ProviderIdentity`, and the two context cases exposed by the first rerun are corrected: optional `domain` is validated only when selected, and the test checks candidate membership instead of an unordered scalar result. The FK remains enforced.

| Gate area | Current local evidence | State |
| --- | --- | --- |
| API PostgreSQL suite | 272 passed, 1 Starlette/httpx deprecation warning on PostgreSQL 17.11 SCRAM. | Passed locally; hosted run pending. |
| Ruff lint and format | CI-scoped checks pass; 9 import-order fixes and 11 formatter files were applied. | Passed. |
| Strict mypy | 70 source files pass after narrowing the Firebase UID from the untyped SDK and marking the federation schema constant `Final`. | Passed. |
| Terraform format | Terraform 1.13.3 `fmt -check -recursive infra/gcp` passes. | Passed locally. |
| Scaffold | `scripts/verify_scaffold.py` passes. | Passed locally. |
| JavaScript/mobile and generated client | Not run: installed pnpm is 11.25.0; package requires `>=9 <10` and pins 9.15.0. | Open. |
| Terraform validation and image | Terraform init/validate and Docker image build were not run; Docker is unavailable on this host. | Open. |
| Cloud, device, and recovery | No live identity/IAM, Neon, GCS, deployed image, native HealthKit, backup restore, or deletion-replay test. | Open acceptance gates. |

## Commands and results

The complete API command used the environment variable `HEALTH_TEST_DATABASE_URL` for the synthetic SCRAM DSN; its value is intentionally not stored in this report:

```bash
TEST_DATABASE_URL="${HEALTH_TEST_DATABASE_URL}" .venv/bin/pytest -c services/api/pyproject.toml -p no:cacheprovider -q --tb=short -rs services/api/tests
```

Result: **272 passed, 1 warning in 17.17s**. The warning is Starlette's deprecation notice for using `httpx` with its test client. The focused Firebase, federation-export, and context-contract files also passed: **36 passed**.

```bash
uv run --project services/api --locked ruff check --config services/api/pyproject.toml services/api/src services/api/tests services/api/scripts scripts
uv run --project services/api --locked ruff format --check --config services/api/pyproject.toml services/api/src services/api/tests services/api/scripts scripts
uv run --project services/api --locked mypy --config-file services/api/pyproject.toml services/api/src services/api/scripts scripts
.venv/bin/python scripts/verify_scaffold.py
terraform fmt -check -recursive infra/gcp
git diff --check
```

All six commands pass; Terraform was 1.13.3. No cloud credentials or personal health data were used. The pnpm version mismatch and missing Docker prevented the corresponding checks, so generated-client drift/typecheck, Prettier, mobile lint/typecheck/tests, Expo export, Terraform init/validate, and image build remain unverified.

## Priority backlog

1. **Gate 1 hosted verification:** run the complete workflow at a reviewed source revision and reconcile any new failures. Do not call the local pass a hosted CI pass.
2. **P1 identity and integration:** keep broad Health context read unavailable until a reviewed delegated identity contract is accepted across Personal AI and Health. Narrow federation export remains default-off and is not typed-task end-to-end proof.
3. **P1 recovery and release:** prove backup/restore with deletion-ledger replay, cloud staging controls, Firebase owner mapping, Neon TLS/pooling/migrations, GCS IAM, rollback, and operational redaction before cloud acceptance.
4. **P1/P2 journeys:** use the QA matrix to complete mobile walkthroughs when pnpm 9.15.0 and Expo Go/Xcode are available; run native HealthKit acceptance only with a compatible build and real device. Keep records upload disabled until malware scanning, isolated parsing, retention, and review controls exist.

## Navigation and evidence boundary

Start with Health's [AGENTS.md](../../../health-app/AGENTS.md), [documentation router](../../../health-app/docs/README.md), and [current state](../../../health-app/docs/current-state.md). Use [FINDINGS.md](FINDINGS.md), [CODE-QUALITY.md](CODE-QUALITY.md), [QA.md](QA.md), and [CLOUD-ACCEPTANCE.md](CLOUD-ACCEPTANCE.md) for the durable handoff.

Local results use a disposable database and synthetic test rows. They establish the current working-tree behavior against PostgreSQL 17.11 and the listed offline checks only. They do not establish hosted CI, cloud/provider behavior, Firebase revocation in production, live Personal AI calls, mobile UI behavior, HealthKit permissions, restore, or release readiness. The attached audit is a starting reference; current code and this dated executable evidence take precedence where they differ.

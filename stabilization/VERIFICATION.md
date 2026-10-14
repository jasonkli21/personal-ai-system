# Final local verification — 2026-10-14

This record covers the stabilization source tuple based on the five baselines in
[review handoff](REVIEW-HANDOFF.md). Final source-tree digests are in
`evidence/source-inventory.json`; isolated wire manifests are in
`evidence/isolated-contracts.json`. Published commit identities are recorded in
`evidence/publication.json`; Root uses its containing-commit resolver to avoid
a self-referential hash. Independent review and external acceptance remain
separate. No personal records, live model providers or cloud deployments were used.

## Runtime and isolation

PAI uses its Python 3.11.15 virtualenv; domain repos use their own Python 3.12
environments. The task integration environment is Python 3.12.13 under
`/tmp/suite-task-integration-venv`, preserving all repo locks/environments. The
bundled Node is 24.19.0. Finance pins pnpm 11.19, Travel 10.17.1 and Health 9.15;
Shopping commands ran the installed locked binaries directly. CI uses other
Node/PostgreSQL versions, so local results do not replace hosted CI.

Native checks used the owned PostgreSQL 17.11+pgvector cluster at 127.0.0.1:55439,
role suite_stabilization, data `/tmp/suite-stabilization-pg17.TLKzM7/data`. Each
runner owns a UUID suite_*_test DB and drops only that DB in finally. Domain
schemas are separate. Finance PRIVATE_FILE_DIR is always an explicit synthetic
temporary directory. Shopping's synthetic runtime URI differs from TEST_DATABASE_URL
so its refusal to test against the configured runtime DB remains enforced.

## Results

| Scope | Final local result | Evidence |
| --- | --- | --- |
| PAI offline backend |1748 passed,90 deselected | `/tmp/pai-offline-publication-final.log` |
| PAI native PostgreSQL |75 passed,14 skipped,1751 deselected | `/tmp/pai-scram-native-final.log`; unavailable DynamoDB checks remain skipped |
| PAI web |123 tests/23 files; lint/types/build pass | local tool output and `/tmp/pai-frontend-build-final.log` |
| PAI evaluations/package |9 offline evaluator CLIs passed; strict v13 non-promotion; wheel/sdist built | `/tmp/suite-eval-*.json`, `/tmp/pai-stabilization-package-publication-final` |
| Finance package gate |API generation, lint/format/types,22 web tests,6 infra-contract tests,250 API tests/55 skips, production build pass | `/tmp/finance-package-release.log` |
| Finance native |294 passed,11 skipped, including actual encrypted SQL/private-file restore | `/tmp/finance-native-release.log` |
| Shopping offline |197 passed,140 deselected; lint/format/API generation pass | `/tmp/shopping-offline-release-final.log` |
| Shopping native |139 passed,198 deselected; one existing Starlette warning | `/tmp/shopping-native-release.log`; migration cycle warning removed without FK semantics change |
| Shopping web |69 tests/9 files; lint/types/build pass | final local tool output; generated types checked |
| Travel native |344 passed,51 existing deprecation warnings | `/tmp/travel-native-release.log` |
| Travel web |60 tests; lint/types/build pass | final local tool output and `/tmp/travel-web-build-final.log` |
| Travel encrypted recovery |age authentication, real SQL/blob restore at 0020, pending upload/export and post-backup owner-erasure replay pass | `/tmp/travel-encrypted-recovery-final.log`;1 erased owner completed,0 pending; retained owner/export preserved |
| Health native |281 passed; one existing Starlette warning | `/tmp/health-native-release-final.log` |
| Health static/mobile |Ruff lint/format, strict mypy 78 files, scaffold, API/client generation and types; 155 mobile tests/32 files; lint passes with 6 existing test warnings | local output, `/tmp/health-mobile-tests-final.log`, `/tmp/health-prettier-release-final.log` |
| Health iOS JS bundle |Export passes | `/tmp/health-ios-bundle-final.log`, `/tmp/health-stabilization-ios-bundle-final`; not device/HealthKit acceptance |
| Health Terraform |1.13.3 fmt passes | local command; provider init/validate/deployment not established |
| Shared contracts |8 consumer files byte-identical;5 isolated runtime manifests match | generator --check and `evidence/isolated-contracts.json` |
| Cross-app matrix |32 passed | `/tmp/suite-task-matrix-release-clock-final.log`; actual migrations, focused production composition, PostgreSQL, five TLS listeners and synthetic external identity |

Health’s final HTTPS run exposed a clock-domain mismatch: uvloop’s loop clock
has a different epoch from time.monotonic(). Body deadlines now use the loop
clock; log durations still use monotonic(). A regression covers distinct epochs.
Health lint ownership and generated-format exclusions now work from the actual
CI root. Full native/static/format and the cross-app matrix were rerun.

All five changed-file secret scans were inspected: findings are public alphabets,
Git/content hashes and explicit synthetic credentials. Travel’s offline full scan
passed on 358 source files after reviewing its public base64url alphabet constant;
its baseline adds that false positive and retains original synthetic entries.
All modified task Markdown links and git diff --check passed.

Final commands and log digests are captured in `evidence/checks.json`; raw logs
stay outside Git. Shell output is evidence for commands without a separate log.
Source/static checks are rerun where later changes require them. Formatting-only
edits do not substitute for behavioral checks.

## Exact reproduction commands

From the PAI checkout, with the documented owned loopback cluster:

```sh
PATH="$PWD/backend/.venv/bin:$PATH" make backend-test-offline
backend/.venv/bin/python backend/scripts/sync_task_contracts.py --check
backend/.venv/bin/python stabilization/scripts/check_isolated_contracts.py
backend/.venv/bin/python stabilization/scripts/run_native_tests.py personal-ai --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres --log /tmp/pai-native.log
backend/.venv/bin/python stabilization/scripts/run_native_tests.py finance --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres --log /tmp/finance-native.log
backend/.venv/bin/python stabilization/scripts/run_native_tests.py shopping --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres --log /tmp/shopping-native.log
backend/.venv/bin/python stabilization/scripts/run_native_tests.py travel --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres --log /tmp/travel-native.log
backend/.venv/bin/python stabilization/scripts/run_native_tests.py health --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres --log /tmp/health-native.log
backend/.venv/bin/python stabilization/scripts/run_native_tests.py tasks --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres --log /tmp/tasks.log
PATH=/tmp/travel-age-v1.3.2/bin:/opt/homebrew/opt/postgresql@17/bin:$PATH backend/.venv/bin/python stabilization/scripts/run_travel_recovery.py --admin-dsn postgresql://suite_stabilization@127.0.0.1:55439/postgres --log /tmp/travel-recovery.log
```

The last command used age1.3.2 and PG17 tools. The runner owns two UUID databases.
Finance native runner sets STAGE4_RECOVERY_TEST_ADMIN_URL to this loopback admin
URI; its encrypted drill owns pf_source_/pf_restore_ UUID DBs and private dirs.

PAI backend: `.venv/bin/ruff check .`; canonical shared modules explicitly checked
with `ruff format --check --line-length88`. Run evaluator modules context, memory,
memory_lifecycle, research, decision, domain, iterative_research, context_planner,
planning with `AI_PROVIDER=fake AI_MODEL=synthetic AUTH_MODE=development
APP_ENVIRONMENT=test ARTIFACTS_ENABLED=false`; build with
`uv build --no-build-isolation --out-dir /tmp/pai-stabilization-package-publication-final`.
Strict v13 planning requires the recorded exact runtime/source and enough Git history
to resolve the frozen baseline/direct parent; a shallow incompatible checkout is
not accepted by replacing its lock.

Finance: pinned pnpm `api:generate`, then `check`, always with
`PRIVATE_FILE_DIR=/private/tmp/finance-stabilization-release` and synthetic cache.
The check includes API equality, lint, formatting, mypy, web/infra/API tests/build.
Travel backend: `.venv/bin/ruff check .`, `ruff format --check .`,
`mypy src/personal_travel`; frontend pinned pnpm 10.17.1 lint/typecheck/test/build.
Shopping backend: `.venv/bin/ruff check src tests migrations`, format --check,
`python ../../scripts/generate_api_types.py --check`, pytest -m 'not db and not live'.
Shopping web: installed eslint, vitest run, tsc -b, vite build using bundled Node.
Health: CI-scoped Ruff/mypy over src/tests/scripts, scaffold, pnpm 9 generation,
client/mobile typecheck, lint/test, format:check and Expo export --platform ios;
Terraform 1.13.3 fmt -check -recursive infra/gcp.

## Fresh CI corrections

The first published runs exposed three environment-specific failures. Shopping’s
one-shot container migration now sets ENVIRONMENT=local and AUTH_MODE=local,
while the production image/security defaults stay intact. Offline SQL generation
from /tmp with the absolute Alembic config passes; fresh container smoke is the
actual image evidence. Travel parser resource-limit tuples now have explicit
variable-length annotations; Linux mypy passes 111 source files. Cross-repository
doc links use GitHub so single-repo checkouts need no siblings. Travel’s native
link checker passes 232 local links. Health’s date-only fixture explicitly chooses
its asserted timezone; 155 mobile tests pass separately under UTC and Los Angeles.
Production device-timezone behavior is unchanged.

Primary native/matrix QA preceded only these type annotations, fixture and docs/CI
changes. Affected static/mobile checks were rerun; hosted CI verifies the final
published source. Earlier failed runs remain historical evidence, never green.

## Interpretation and remaining gates

The suite harness boots focused production routers/runtime compositions; it does
not prove every normal app supervisor/startup path. IAM, Firebase tokens/certificate
lookups and linked SDK records are fake. Signatures, HTTPS verification, handlers,
database state, grants, revisions and receipts are real. Lost-ack tests use an
explicit injected transport failure after real commit; process-crash and mixed
deployed revision acceptance remain separate.

Health's earlier readiness fix was additionally reproduced under a synthetic
SCRAM cluster; final trust-auth PG checks alone would not prove password handling.
No Docker/emulator, real linked IAM, cloud resources/provider validation, live
inference, native iOS/HealthKit, complete new rendered task journeys or approved
cloud retention/RPO/RTO is passed by this evidence. Historical partial Travel
browser evidence is retained separately. Fresh GitHub CI at the pushed commits
is recorded as external evidence when available, never inferred from these tests.

See [blockers](BLOCKERS.md), [operations](OPERATIONS.md) and [review handoff](REVIEW-HANDOFF.md).

## Publication and cleanup

The four domain commits were pushed normally and their remote main SHAs verified:

| Repo | Published commit |
| --- | --- |
| Shopping |197849e545ae74f1860a58054c8a741ccb39d9e5 |
| Finance |8097060f7734525f2c8294bc77f2325d47f2c7d4 |
| Travel |4836fb82d45a66ed2fab726eff4e31e09f9ae8fa |
| Health |c3020b9c6926fd6454e5fe95b0d7fa5fa13ebb00 |

PAI’s exact containing commit is resolved by `git log -1 --format=%H --
stabilization/REVIEW-HANDOFF.md`; its direct parent is 4413b0a, the reviewed v13 anchor. Verify remote main with
`git ls-remote origin refs/heads/main`. Final publication/CI completion output is
also preserved in `/tmp/suite-ci-latest.json` and the per-repo stabilization-commit
JSON records. CI in publication.json is the dated preparation snapshot, not an
assertion about its later outcome.

The owned cluster at 55439 was stopped after all native checks. No runner-owned
UUID databases remained. Logs/test data are preserved under /tmp for review;
these paths are temporary and should be copied to a private evidence location
if long-term retention is needed. No personal/deployed resources were removed.
The consumed one-shot restart is PAUSED. No session model or reasoning setting
was changed. Only pre-existing unrelated user files remain outside the commits.

Final supplemental checks: Travel’s actual SCRAM pool regression passes; all
seven Finance browser journeys pass using a UUID DB/private store and explicit
historical valuation. Root’s v13 focused/source/documentation guards and full
offline/native checks are rerun after restoring the Phase36 offline phrase.
v13 preserves v12’s 30-case corpus/config/runtime and strict guards while recording
the final revision anchor; v10/v11/v12 are unchanged.

Final password-authenticated supplemental cluster:
`/tmp/suite-scram-release.A7UZVA/data`, loopback 55449, synthetic role
suite_ci_fixture. Incorrect passwords were explicitly rejected. Travel pool
recovery, PAI’s 75 native tests and all seven Finance browser journeys passed;
the runners dropped their owned UUID DBs and the cluster is now stopped.
No private/deployed storage was touched.

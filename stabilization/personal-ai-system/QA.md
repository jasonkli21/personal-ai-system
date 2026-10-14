> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Personal AI QA evidence

Date: 2026-10-13. Tested base revision: `c029194156c570ec55f8173af969702f0265e57b` plus the working-tree changes reviewed for Gate 1. The v11 source identity is `300db6f570d8626fdffef24696f332a63db91944fd859f17f5934f39d622646b`; it includes the reviewed production source tree and does not include test-only locks.

| Command | Result | Evidence class |
| --- | --- | --- |
| `PERSISTENCE_TEST_POSTGRES_DSN='postgresql://suite_stabilization@127.0.0.1:55439/pai_test' .venv/bin/python -m pytest -m persistence_integration tests/persistence/test_provider_usage_accounting.py tests/persistence/test_artifact_tier.py tests/persistence/test_routing_decisions.py -q --tb=short` from `backend/` | 46 passed in 16.95s | Native PostgreSQL 17 (`server_version_num=170011`) with pgvector migrations; synthetic data |
| Same 46-test command with file order reversed | 46 passed in 17.88s | Native PostgreSQL repeat/order check |
| `psql 'postgresql://suite_stabilization@127.0.0.1:55439/pai_test' -Atqc "select current_database(), current_setting('server_version_num'), (select count(*) from pg_database where datname ~ '^pai_test_[0-9a-f]{32}$')"` | `pai_test|170011|0` | Test-only database cleanup; no generated database remained |
| `PATH="$PWD/backend/.venv/bin:$PATH" make backend-test-offline` | 1,705 passed, 89 deselected, 2 warnings, 167.46s | Local deterministic offline suite |
| `backend/.venv/bin/python -m ruff check .` from `backend/` | All checks passed | Static |
| `backend/.venv/bin/python -m pytest tests/test_planning_experiment.py -q --tb=short` from `backend/` | 45 passed, 1 warning, 4.40s | Portable evaluator conformance; temporary per-test runtime/source lock |
| `backend/.venv/bin/python -m personal_ai.evaluation.planning` from `backend/` | Strict v11 replay passed 30 rows; non-promotion; zero planner calls/tokens/quota; quality unmeasured; no promoted coverage | Local synthetic strict replay on the v11 captured runtime/source |
| `git diff --check` | Passed after source and documentation edits | Tracked source/evidence hygiene |

The old v10 lock and held-out corpus are unchanged. V11 records the exact event-forwarding and UTC deadline source corrections, its tested base revision, local runtime identity, and unchanged non-promotion decision. Portable unit tests write their test lock only below pytest's temporary directory. Production `evaluate()` still rejects incompatible runtime, source, lock-version and unrelated-revision identities. Strict v11 replay on other runtimes remains intentionally unverified and should fail closed until a separately reviewed freeze exists.

The last recorded CI run is [38348677456](https://github.com/jasonkli21/personal-ai-system/actions/runs/38348677456), against the pre-patch HEAD. It failed the two strict planner-evaluator tests on Python 3.12, had 1,697 passing tests and 91 skips, cancelled Python 3.11, and passed frontend and container jobs. No post-patch CI result is claimed. The earlier frontend check remains 123 tests in 23 files plus lint and types; this patch changes no frontend files.

These results do not establish DynamoDB Local, GCS, cloud identity/IAM, live-provider, browser, recovery, deletion, production capacity, or integrated domain acceptance. Test migrations and fakes establish only the local contracts exercised above.

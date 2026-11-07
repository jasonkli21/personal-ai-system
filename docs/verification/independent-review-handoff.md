# Independent review handoff: W0 review remediation

## Commit and scope

Review the single remediation commit containing this file. Resolve its exact SHA with `git log -1 --format=%H -- docs/verification/independent-review-handoff.md`. Its parent is the rejected W0 commit `3b92dfbbd27ee1735e8957d2acc65d084230c100`. The supplied review report is `pas-w0-sol-high-independent-review-handoff.md`; it is independent review evidence, and its ordered checklist informed this implementation. It does not authorize history rewriting, release approval, provider execution, or production action.

This change addresses the review's six findings: immutable migration and fixture bytes; forged active source metadata; relaxed historical offline corpus types; invalid workflow working directories; missing Git history for ancestry validation; and urllib3's import-time IPv6 probe tripping the offline network fence. The old W0 implementation commit was not amended or rewritten.

## Key implementation paths

- Active source contracts, current selectors, and check: `backend/src/personal_ai/evaluation/source_contracts.py`, `backend/scripts/source_contract_check.py`, and `Makefile` target `source-contract-check`.
- Additive source identities: planning lock v37 and offline source manifest generation 11 under `backend/src/personal_ai/evaluation/fixtures/`.
- Closed offline corpus contract: `backend/src/personal_ai/evaluation/offline_information_contracts.py` and `backend/tests/test_offline_information_handling.py`.
- Migration checksum compatibility and recorded-history regression: `backend/src/personal_ai/persistence/migrations/`, `backend/src/personal_ai/persistence/migrations_py/022_routing_authorities.py`, and `backend/tests/test_routing_migration.py`.
- Historical byte pins and naming compatibility: `backend/scripts/naming_policy_check.py`, `backend/scripts/test_naming_policy_check.py`, and `docs/naming-exceptions.md`.
- Offline test network fence: `backend/scripts/offline_test_runner.py`.
- Workflow jobs and full-history fetch: `.github/workflows/quality.yml`.
- Current evidence and boundary: [current-source-integrity.md](current-source-integrity.md).

## Reproduction

Use the committed tree and locked Python environment. The core portable and regression checks are:

```bash
make source-contract-check naming-policy-check
backend/.venv/bin/python -m pytest backend/tests/test_source_contracts.py backend/tests/test_routing_migration.py backend/tests/test_planning_experiment.py -q
backend/.venv/bin/python -m pytest backend/tests/test_offline_information_handling.py -m 'not loopback_http' -q
```

The offline SDK and capability gates are:

```bash
PATH="$PWD/backend/.venv/bin:$PATH" make sdk-check
PATH="$PWD/backend/.venv/bin:$PATH" make hermetic-capability-check
PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint
```

The managed sandbox does not permit local loopback binds, so the loopback HTTP subset and full native PostgreSQL upgrade path remain unverified. The hermetic target itself completed with zero blocked network attempts. Its passing fakes and unit checks do not establish native PostgreSQL, installed native consumer, hosted CI, provider, cloud, or production behavior. `actionlint` was not installed; workflow YAML was parsed locally.

## Invariants to review

1. The eight released SQL migration files and the Python file in migration 022 match the immutable parent bytes. The three frozen decision/research fixtures match their parent bytes. Their exact hashes are checked; exceptions are not broad path exclusions.
2. Planning lock v37 supersedes the pinned v36 lock. Offline manifest generation 11 supersedes pinned generation 10 and retains the frozen case digest. Prior locks, manifests, case bytes, scoring, thresholds, and decisions remain unchanged.
3. The active planning lock has a closed field set and fixed evidence metadata. The source check recomputes source, configuration, corpus, and fixture digests; checks exact source maps; pins predecessor bytes; and requires source revisions to be real Git ancestors. Planning and offline anchors must agree.
4. Generation 11 claims no new measurements. Planning remains `non_promotion`, with zero quality cases. Strict runtime replay is separate from portable source validation.
5. Offline suite, rubric, seed, and case-ID values are closed and coupled across v1/v2. Tests reject arbitrary identifiers and cross-generation mismatches.
6. The workflow uses repository-root working directories for backend commands and fetches full history in source-contract jobs.
7. The urllib3 IPv6 capability probe is initialized before the test-time network fence. The fence stays installed while tests run, and the hermetic lane reports zero blocked attempts.

## Independent checks and remaining boundary

Inspect `backend/tests/test_source_contracts.py`, `backend/tests/test_routing_migration.py`, `backend/tests/test_offline_information_handling.py`, and `backend/scripts/test_naming_policy_check.py` for negative cases. Then verify the commit summary and run `make source-contract-check` from the committed tree. Confirm only this remediation is committed; unrelated user-owned documentation remains uncommitted.

Independent review of the new commit and a fresh hosted CI run are pending. Native PostgreSQL migration upgrade with predecessor database records, full loopback tests, installed native consumer checks, external identity/source rights, live provider utility, cloud IAM/billing, restore, physical erasure, and E2–E5 remain `NOT_RUN` or `BLOCKED_UNVERIFIED`. Production remains `NO_GO`; no W1 implementation is authorized by this remediation.

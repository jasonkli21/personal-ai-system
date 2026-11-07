# Independent review handoff: current-source verification repair

## Commit and scope

Review the single local implementation commit that contains this file. The handoff is self-locating: resolve its exact SHA with `git log -1 --format=%H -- docs/verification/independent-review-handoff.md`. Its expected parent is `adb5b744a8a17bdc22e3953bfaa1903b927ce38c`. The final Codex response records the resolved SHA. No push or hosted workflow run was performed.

The change repairs stale planning and offline benchmark identities, establishes deterministic read-only current-source conformance with explicit versioned proposals, cleans phase-coded names from active source/tests/current documentation, and strengthens CI. The detailed before/after hashes and gate results are in [current-source-integrity.md](current-source-integrity.md).

## Key implementation paths

- Current-source contracts and proposal/check command: `backend/src/personal_ai/evaluation/source_contracts.py`, `backend/scripts/source_contract_check.py`, and `Makefile` target `source-contract-check`.
- Descriptively named offline evaluator: `backend/src/personal_ai/evaluation/offline_information_handling.py`, `offline_information_contracts.py`, `offline_task_driver.py`, `offline_information_scoring.py`, `evaluation_effect_audit.py`, and `loopback_synthetic_host.py`.
- Offline check/install probes: `backend/scripts/offline_benchmark_checks.py` and `backend/scripts/installed_offline_benchmark_checks.py`.
- Current planning lock: `backend/src/personal_ai/evaluation/fixtures/context/planning-baseline-v36.json`.
- Current offline source manifest and renamed frozen fixtures: `backend/src/personal_ai/evaluation/fixtures/offline_information_handling/`.
- Related additive source identities: `backend/src/personal_ai/evaluation/memory_longitudinal/source-lock-v5.json`, `backend/src/personal_ai/evaluation/fixtures/reasoning/manifest-v2.json`, and `backend/evaluation/adaptive-development-conformance-v2.json`.
- Naming policy and exact compatibility register: `backend/scripts/naming_policy_check.py`, `backend/scripts/test_naming_policy_check.py`, and `docs/naming-exceptions.md`.
- CI grouping and canonical status: `.github/workflows/quality.yml`, `Makefile`, `docs/current-state.md`, and `docs/verification/current-source-integrity.md`.

Use `git show --summary --find-renames <resolved-sha>` and `git show --stat --find-renames <resolved-sha>` for the complete rename and changed-file inventory. The original unrelated user-owned PRD work was not staged or committed.

## Reproduction

Use Python 3.11.15, `uv 0.11.13`, the locked backend environment, and a clean checkout of the resolved commit. The short identity and naming lane is:

```bash
cd backend
uv sync --locked --extra dev --group build --no-build-isolation
cd ..
make source-contract-check naming-policy-check sdk-check consumer-contract-check release-profile-check
```

The complete local offline suite and installed-consumer lanes are:

```bash
PYTHONPATH=sdk/python/src:examples/project-checklist/client/src:examples/project-checklist/host/src:examples/reading-logbook/client/src:examples/reading-logbook/host/src:reference-apps/src make backend-test-offline
make offline-benchmark-check sdk-install-check synthetic-reasoning-install-check
make hermetic-capability-check
```

The full offline target needs local loopback sockets for signed HTTP tests. Its result on this implementation was 3,332 passed, 1 skipped, and 204 deselected by its documented filters. The CI workflow provisions a disposable pgvector service and runs the separate PostgreSQL integration targets; local PostgreSQL evidence was unavailable in this session.

`make source-contract-check` verifies both active source identities without running an evaluator. It must pass only after the bound source and active locks are committed. The proposal modes are opt-in, print a full diff without writing by default, and refuse to overwrite an occupied versioned target:

```bash
backend/.venv/bin/python -I backend/scripts/source_contract_check.py --propose-planning
backend/.venv/bin/python -I backend/scripts/source_contract_check.py --propose-offline-benchmark
```

## Invariants to review

1. Planning lock v36 supersedes v35; offline source generation 10 supersedes generation 9. Every earlier planning lock, offline manifest, frozen case, scorer, threshold and measurement remains unchanged.
2. The two current source closures are deterministic and sorted. Missing, changed, unexpected, unreadable or dirty bound files fail closed. The planning closure covers the application package tree and stable required inputs. The offline closure covers the package Python/JSON tree plus the named consumer and host distributions; versioned offline manifests are excluded to prevent recursion.
3. Planning is proposed before the offline manifest because the latter hashes the current planning lock. The source-check utility never refreshes itself during `--check`.
4. The offline case digest remains `25df654eda27040c3b52695fd6ec695b53238a7cf76b82e1ed4e5d442b55205d`. Generation 10 says earlier measurements do not validate its source identity and claims no new measurement.
5. Runtime package fingerprints remain strict replay provenance and are not portable source-conformance inputs. The current planning evaluation passed with no quality-case denominator and therefore supplies no promotion evidence.
6. Memory lock v5, reasoning manifest v2, and adaptive conformance v2 are additive; prior source locks and manifests remain preserved. Their old measurements are not rebound to new identities.
7. The implementation does not enable provider or external-source sends, memory capture, workflow effects, adaptive promotion, cloud access, restore claims, or production behavior.
8. The naming checker covers active code, tests, scripts, configs, commands, current docs, experiment guides, and stabilization guides. Persisted IDs and immutable evidence labels remain only where the exact path and identifier are documented in the compatibility register.

## Negative and independent checks

Inspect `backend/tests/test_source_contracts.py` and `backend/scripts/test_naming_policy_check.py`. They exercise source mutation, missing paths, lock/manifest corruption, predecessor consistency, schema/version mismatch, exact exception scoping, active-document coverage, and frozen fixture hashes using temporary data. Do not mutate committed historical files to test failure paths.

For the review itself, verify the staged/committed tree is clean in a fresh checkout, run `make source-contract-check` and `make naming-policy-check`, inspect `git show --summary --find-renames`, and confirm the full offline suite and benchmark evidence are not conflated with unavailable database/provider/cloud evidence. A reviewer must independently decide whether the commit is acceptable; this implementation session does not self-approve it.

## Remaining conditions

- Independent review and fresh hosted CI are pending.
- Disposable PostgreSQL migration, workflow, memory episode/consolidation/navigation, restore, and recovery tests were not run locally because no test DSN or Docker executable was available.
- External identity/source rights at physical send, provider/model utility, billing, cloud IAM, distributed restore, physical erasure, and E2–E5 remain open or `BLOCKED_UNVERIFIED`.
- Production remains `NO_GO`; experimental reasoning, memory, workflow, and disclosure gates remain off according to their owning contracts.

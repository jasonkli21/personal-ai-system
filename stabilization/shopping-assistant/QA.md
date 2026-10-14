> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Shopping QA baseline

Date: 2026-10-13. Source revision: `2268b944ffa8fe5c2e6f2787c88dea616160e398`. No Shopping source changes were made.

## Gate 1 local verification update — 2026-10-13

The working tree now contains the Gate 1 repair set based on the source revision above. It is not committed, and its checks do not replace the recorded hosted CI run.

| Check | Result |
|---|---|
| API Ruff lint/format | Passed across 176 files. |
| Offline API | Passed: 197 passed, 130 deselected. |
| PostgreSQL integration | Passed: 129 passed, 198 deselected on local PostgreSQL 17 using `shopping_test`; existing httpx deprecation and FK-cycle warnings remain. |
| Generated API types | Passed after canonical regeneration; `ContextRecord` gained optional `partial_result`, `omitted_count`, and `selection_policy_version` fields. |
| Frontend | Passed: 69 Vitest tests, ESLint, `tsc -b`, and Vite build on bundled Node 24.19.0. The main chunk size advisory remains. |
| Alembic CLI from `/tmp` | Passed `upgrade head` and `check` with `/Users/jasonkli/projects/shopping-assistant/apps/api/alembic.ini`; no new upgrade operations were detected. |
| Hosted/container/Node 20 | Not run: no hosted rerun, Docker CLI, or local Node 20 runtime was available. The Dockerfile source confirms the configured Alembic path. |
| Whitespace | Passed: `git diff --check`. |

The new discovery regression renders the saved project goal with no passive effects. Saved command replay remains authoritative, and explicit user edits—including empty values—remain preserved. PostgreSQL evidence also covers the `too_large` rejection fixture and aware-instant expiry comparison. The existing CI run remains historical evidence for the baseline SHA.

## Executable evidence

Current GitHub Actions: run [38265114836](https://github.com/jasonkli21/shopping-assistant/actions/runs/38265114836), main at the baseline SHA, concluded failure. The frontend E2E journey passed. The backend formatter, DB, frontend unit, and container smoke jobs failed as detailed in [STATUS](STATUS.md) and [FINDINGS](FINDINGS.md).

Local checks, run from the indicated directory:

1. In `apps/api`:

       UV_CACHE_DIR=/private/tmp/shopping-uv-cache uv run --locked pytest -m 'not db and not live'

   Passed: 197 tests, 130 deselected. Two environment warnings were reported: uv could not acquire the environment lock, and pytest could not write its cache under the read-only Shopping checkout.

2. In `apps/api`:

       RUFF_CACHE_DIR=/private/tmp/shopping-ruff-cache .venv/bin/ruff format --check src tests migrations

   Failed: one file would be reformatted, `src/shopping/projects/context.py`; 175 files were already formatted.

3. In `apps/web`:

       /Users/jasonkli/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node node_modules/vitest/vitest.mjs run --configLoader runner

   Passed: 9 test files, 68 tests. The bundled Node executable was used because `node` is not on this shell's PATH. The runner config avoids Vite writing its temporary config into the read-only repository's `node_modules`.

4. DB-marked tests were not run locally. `TEST_DATABASE_URL` was unset and Docker is unavailable. A disposable PostgreSQL 16 cluster was attempted under `/private/tmp`; native `initdb` failed during bootstrap with `shmget: Operation not permitted`, including with mmap/posix shared-memory overrides. CI remains the executable DB evidence: 1 failed, 128 passed, 198 deselected, plus the FK-cycle warning.

5. Container smoke was not run locally because Docker is unavailable. CI built the image but the smoke migration CLI failed before running migrations because no Alembic config was loaded from `/tmp`.

6. A local browser E2E, manual visual/keyboard review, live-provider check, and hosted journey were not run. CI's deterministic frontend E2E passed; this does not close those review or deployment gates.

## Journey coverage and open QA

| Journey | Existing evidence | Remaining verification |
|---|---|---|
| Project and requirements | Project/API unit coverage and deterministic browser journey | Reload/deep links, stale concurrent edits, malformed local drafts, deletion |
| Discovery and retry | Unit tests cover request keys, saved commands, candidates; CI currently fails two recovery assertions while the local suite passes | Reproduce CI failures, verify same-key ambiguous retry and safe corrupted-storage fallback |
| Research and evidence | Offline evals and API tests cover bounded work and evidence semantics; PostgreSQL job/migration tests are separate | Process death, lease recovery/fencing across instances, provider timeout/quota behavior, SSRF and source freshness |
| Compare and shortlist | Unit journey covers comparison and decision interactions; Phase 6 review says unknown/stale facts stay explicit | Manual evidence-panel/keyboard review, narrow viewport review, PostgreSQL snapshot/revision behavior |
| Preferences | Offline schema/eval coverage; Phase 8 implemented locally | Stale revision forms, money/content preservation, first-use locking, delayed drafts, lifecycle UX, prompt precedence, DB lifecycle |
| Owner privacy | Auth/config and privacy CLI tests; production owner mapping is implemented | Live Firebase wrong-user denial, full export/purge, restore-and-delete fence, log redaction |
| Personal AI destination | Context read/auth tests cover a gated read-only contribution; fake client is deterministic | Typed task transport, delegated identity through queue, authorization, result state, and idempotent retry are absent |

The canonical phase gates remain open: Phase 6 manual/browser and review disposition; Phase 7 deployed lease, termination, mixed-revision, provider, and cancellation behavior; Phase 8 preference lifecycle review and database behavior; Phase 9 live identity, Cloud Run/Neon, backup/restore, security, and hosted acceptance. Do not count a fake, offline evaluation, or local browser test as cloud or provider evidence.

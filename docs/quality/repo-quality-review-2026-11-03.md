# Repository quality review — 2026-11-03

## Scope and provenance

Reviewed and edited the local checkout at base `5213fa597dd4b6b09f0d34dd26bcc80166eb9cb8` (`main`). The tracked history reports one author identity across 202 commits. The three pre-existing untracked PI planning documents were preserved verbatim. The configured remote was not used to infer public repository links or reporting channels.

The new Apache-2.0 grant covers the repository's original project code and documentation. No vendored source tree or third-party license file was found in the reviewed project packages. Dependencies and externally sourced content retain their own licenses; this change does not relicense them. The project contains references to external data-provider terms and synthetic test labels. A full dependency-license inventory and legal provenance audit were not performed.

## Changes

- Rewrote the root README as concise user-facing project orientation, accurate core/optional-app boundaries, credential-free local setup, commands, and documentation links. Corrected retrieval wording: gated local retrieval may enter normal assembled model context; this does not mean general external retrieval is available.
- Added the full Apache License 2.0 text at the repository root and per-distribution license files plus SPDX metadata for the backend, optional reference apps, Reading Logbook client, and Reading Logbook host.
- Updated Hatch sdist inclusion so all four package archives carry the license. Updated the backend Dockerfile to copy its package license into the backend build context before installation.
- Added contributor and vulnerability-reporting guidance without inventing a maintainer email or promising response times.
- Replaced root agent instructions with concise durable authority, invariants, privacy, documentation-placement, and focused-check routing.
- Reduced the docs router to short task-scoped first reads and updated the current-state date and pointer to this review. Runtime behavior and acceptance gates are unchanged.

## Final paths

Changed: `AGENTS.md`, `README.md`, `CONTRIBUTING.md`, `SECURITY.md`, `LICENSE`, `backend/Dockerfile`, `backend/LICENSE`, `backend/pyproject.toml`, `docs/README.md`, `docs/current-state.md`, `docs/quality/repo-quality-review-2026-11-03.md`, `examples/reading-logbook/client/LICENSE`, `examples/reading-logbook/client/pyproject.toml`, `examples/reading-logbook/host/LICENSE`, `examples/reading-logbook/host/pyproject.toml`, `reference-apps/LICENSE`, and `reference-apps/pyproject.toml`. Removed from the Git index only: `frontend/tsconfig.tsbuildinfo` (local file retained). The three pre-existing untracked PI planning documents are not part of this change.

## Confirmed and deferred findings

- Confirmed the README's former claim that retrieved passages never enter model context conflicted with the PI-5 completion implementation/gate evidence. The rewrite describes the gated local path and links to its API contract; it does not promote external eligibility or production acceptance.
- The existing modularity report documents prior extraction of the named high-risk coordinators. No runtime extraction was made: the handoff itself identifies ordering, policy, and persistence parity risks, while no narrowly scoped, behavior-neutral code defect was established in this documentation/license pass.
- No tests, evaluation cases, CI jobs, frozen fixtures, or generated tracked outputs were removed. Verification optimization and baseline-vs-after speed claims are deferred: this pass made no test or CI changes and did not collect comparable cold/warm suite timings.
- `frontend/tsconfig.tsbuildinfo` was confirmed to be ignored and unreferenced outside `.gitignore`; it was removed from the index only. The local generated file remains present.
- Docker build-context behavior was reviewed: CI uses `./backend` as context and the Dockerfile now copies the adjacent `backend/LICENSE`. Docker itself was unavailable for an image build, so that image-level effect is not claimed as verified.
- Existing package READMEs were left in place where they already document ownership, entry points, and safety boundaries. No mechanical trimming was justified.

## Checks on 2026-11-03

The checkout was unchanged in source from the base commit; these checks ran against that base plus the uncommitted documentation and packaging changes. No real credentials, providers, cloud, or deployment were used.

| Check | Result |
| --- | --- |
| `UV_CACHE_DIR=/tmp/pa-quality-uv-cache make pi2-build` | PASS. Built wheel and sdist for all four distributions. |
| Archive inspection of all eight artifacts | PASS. Each wheel contains `*.dist-info/licenses/LICENSE`; each sdist contains its package `LICENSE`. |
| `backend/.venv/bin/python backend/scripts/pi2_contract.py --check` | PASS (`PI2_CONSUMER_CONTRACT=PASS`). |
| `backend/.venv/bin/python backend/scripts/pi2_artifact_checks.py` | Initially blocked by sandbox loopback binding: 101 passed, 91 setup errors, 0 forbidden network attempts. A verifier rerun with approved local-loopback execution passed: 191 passed, 1 skipped, 0 forbidden network attempts. |
| PI-2 constituent checks | PASS: `UV_CACHE_DIR=/tmp/pa-quality-uv-cache make pi2-build`, `backend/.venv/bin/python backend/scripts/pi2_contract.py --check`, PI-1 core installed probe (190 passed), PI-2 installed HTTP/client/uninstall suite (191 passed, 1 skipped), and inspection of all eight wheel/sdist license members. `make pi2-check` was not run as one combined target. |
| Initial `make pi2-build` with default uv cache | BLOCKED: sandbox denied access to `/Users/jasonkli/.cache/uv`; rerun with `/tmp` cache passed. |
| `git diff --check` | PASS. |
| `backend/.venv/bin/ruff check backend` | PASS. `make backend-lint` itself is BLOCKED because `python` is absent from PATH. |
| Full offline backend suite (`cd backend && .venv/bin/python -m pytest -m 'not persistence_integration and not cloud_smoke' --ignore=tests/test_gemini_manual.py --ignore=tests/test_context_manual.py --tb=short -q`) | 2,449 passed, 1 skipped, 1 failed, 119 deselected. The sole failure is `test_v27_pi6_review_rebind_preserves_v26_and_non_promotion`: frozen source identity is `d099f766…`, while current calculated identity is `3199e902…`. `backend/pyproject.toml` is an explicit member of that frozen source identity, so the required license metadata change triggers the mismatch. Frozen planning locks/tests were not changed. This is a remaining packaging/evaluation-lock conflict, not evidence that runtime behavior changed. |
| Frontend lint, typecheck, test, build | BLOCKED: installed pnpm shims could not launch because Node.js is absent from PATH. |
| Docker image build | NOT RUN; Docker CLI unavailable. |
| Timed baseline/after comparison | NOT RUN; no test or CI changes were made, and no comparable baseline was collected. |
| Provider, cloud, native database, production security | NOT RUN; no credentials or external services used. |

These package and offline contract checks do not close independent review or provider/cloud/native acceptance gates. The pre-existing untracked PI plans remain user-owned local state. The frozen PI-6 source-identity conflict remains open; do not refresh or loosen the frozen fixture merely to make the suite green.

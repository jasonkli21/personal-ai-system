# PI-1 review remediation evidence

**Date:** 2026-10-30 (America/Los_Angeles)
**Base revision:** `b97aab4a679df0410ad7688fa50c8b8557a7ec8b`
**Source revision:** the single remediation commit containing this report; its exact SHA is supplied in the delivery message. This report does not embed its own commit hash.
**Status:** implementation remediation complete locally; independent PI-1 review and external acceptance remain pending.

This report records the bounded remediation requested by the PI-1 review handoff. Handoff text was treated as findings and constraints to verify, not as permission to widen product scope. The user authorized one local commit. No push, provider call, cloud access, credential use, network dependency installation, native database mutation, or external effect was performed.

## Findings and changes

The review handoff identified eight concrete CI failures. The same four test files reproduced **8 failed, 79 passed** under the offline network fence, with zero network attempts. The failures came from historical reference fixtures resolving against the now core-only application catalog and from test hosts that had not explicitly composed the optional application contributions.

- Context-planner and planning fixtures now use explicit synthetic reference rules over neutral core contracts. Core-only remains the default. Historical planning lock v18 is unchanged; current v19 records the source binding and keeps the result non-promoting. All nine context fixture IDs and all 30 planning cases remain evaluated, with zero planner calls or tokens.
- Research and signed task-identity tests explicitly compose the selected Travel, Finance and Shopping contributions. Separate checks retain denial when an application is not selected. Middleware, signed identity verification and scope checks remain exercised.
- The reference package's installed domain evaluator now discovers the repository from the current working directory and runs without assuming source checkout paths. CI builds both distributions, installs the reference wheel only for the backend compatibility stage, runs context/planning evaluations, and invokes reference domain/itinerary evaluations from the reference package. A Python 3.11/3.12 artifact-profile matrix runs the portable package checks.
- The platform artifact check uses the system temporary directory instead of `/private/tmp`; installs are explicitly offline and require the configured `uv` executable. Added probes check the core evaluator with reference namespaces denied and run reference evaluators from the installed wheel. The offline pytest runner no longer re-enters pytest in spawned worker processes. `pythonpath` in backend pytest configuration is documented as source-tree compatibility, not installed-artifact evidence.
- README and reference-app instructions distinguish source-tree compatibility tests from installed distribution checks. No routes, migrations, provider activation, memory behavior, or promotion gates were added.

## Verification

Commands below ran from the repository at the base revision plus this remediation worktree. `UV_CACHE_DIR` pointed to `/private/tmp/pi1-uv-cache`, `UV_OFFLINE=true`, and the artifact check ran on macOS with Python 3.11.15. A local artifact run is not Linux or Python 3.12 acceptance.

| Check | Result |
| --- | --- |
| Offline reproduction of the eight handoff failures, before edits | 8 failed, 79 passed; zero network attempts |
| Four focused test files after edits, via `scripts/pi1_offline_checks.py` | 91 passed; zero network attempts |
| `make context-plan-eval` | 9/9 historical context fixtures evaluated |
| `make planning-eval` | 30 cases; non-promotion; 0 planner calls and 0 tokens |
| `make backend-lint` | Passed |
| `make platform-independence-check` | Passed; inventory reported 0 core/example/facade edges and no issues; core/reference wheel and sdist rebuilt offline |
| Installed core-only compatibility subset | 49 passed; reference package and namespaces physically absent; core probe passed |
| Installed reference compatibility subset | 190 passed; restored reference profile and original task-key subset 56 passed |
| Installed reference evaluation probe | Travel 4/4, Shopping 6/6, itinerary 6/6; 0 provider calls and 0 network attempts |
| Broad offline backend suite excluding persistence/cloud/manual cases | Pytest reported 2,028 passed and 114 deselected, but the safety wrapper exited 3 after blocking 3 DNS attempts. This is not recorded as a passing full-suite check. The three isolated formerly failing tests passed with zero network attempts. |
| `git diff --check` | Passed after final whitespace cleanup |

The handoff's stale `.github/workflows/quality.yml` call to `personal_ai.evaluation.domain` is replaced by `personal_ai_reference_apps.evaluation.domain`; optional evaluation targets require an explicit reference contribution selection. The test suite continues to use the real identity middleware and trusted test contribution catalogs.

## Artifact identities

| Artifact | Members | SHA-256 |
| --- | ---: | --- |
| `backend/dist/personal_ai_backend-0.1.0-py3-none-any.whl` | 413 | `7f8889b56b28c64f7e9a0edc7267eca9b79217f5d6370ef6122af194faaf4500` |
| `backend/dist/personal_ai_backend-0.1.0.tar.gz` | 414 | `c1b5e723df49bad639d04de4f3cdc0fe1f6eb794f1c1e4f9e6e8fd5f61bb1cb7` |
| `reference-apps/dist/personal_ai_reference_apps-0.1.0-py3-none-any.whl` | 54 | `dc34894104bdda3a82fef1b4f1b69fca6f84649cdacaa6983eeefc0a107071fd` |
| `reference-apps/dist/personal_ai_reference_apps-0.1.0.tar.gz` | 54 | `ba3464852d505ae68a2484af9dacbc03ca3ca9d03c3b17abbe12d551de4cc58c` |

Planner v18 remains historical and unchanged (SHA-256 `04342a8f00c82503f52f4cfb93a25bd45ff6c2507c769ff30db71ffe372c48dd`). The new v19 lock binds the worktree's reference-fixture profile to the base source revision; its configuration identity is `c1e4f6057781add8a9ddc8b8372d988904ab04f793c7c21f9838ed705e45d7fe` and source identity is `ac0526535784cc783db25689fb45f63fe2a2812640ff74c420fdd334c87d8142`. The original context fixture corpus bytes are preserved.

## Remaining acceptance

The GitHub Python 3.11/3.12 jobs, actual Linux artifact execution, independent post-remediation review, native PostgreSQL/DynamoDB replay, provider and cloud behavior, deployed identity, production source revocation, physical-send/deletion behavior, and Phase36 acceptance were not established here. PI-0 acceptance remains pending. MEM-2 remains frozen at its existing default-off boundary; PI-2 must wait for explicit independent PI-1 acceptance. The independent reviewer should inspect the complete remediation diff and rerun the required Linux/CI and safety negatives without being directed to a particular verdict.

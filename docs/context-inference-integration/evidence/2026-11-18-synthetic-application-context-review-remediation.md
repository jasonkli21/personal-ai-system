# Synthetic application context review remediation · 2026-11-18

**Remediation disposition: COMPLETE AND ACCEPTED for the scoped fixes and evidence updates.** The synthetic acceptance verdict remains **BLOCKED**. This record is not independent Stage 0 approval, independent final review, CI-green evidence, or production readiness.

## Baseline and scope

- Reviewed tree: `16d02a78db2d0dd1fe92fceeb0399c7e06b8cbfa`.
- Reviewed parent: `e7ff57e695f22d6d790fcee910a0178246f5daa9`.
- The reviewed tree was the checked-out `HEAD`. The working tree already contained unrelated untracked reasoning-engine and context-inference planning documents, plus a deletion of the old reasoning-engine PRD and its replacement under `docs/reasoning-engine/`. Those files were preserved and are not included in this remediation commit.
- No independent Stage 0 decision or independent final review was supplied. The 2026-11-17 maintainer authorization is retained as historical evidence and explicitly separated from independent acceptance.
- Production and every later live integration gate remain unchanged.

## Finding disposition

| Finding | Disposition | Evidence |
| --- | --- | --- |
| R-01 | `DOCUMENTED_BLOCKED` | Delivery ledger, current state and dated evidence now say maintainer authorization is not independent Stage 0 acceptance. Stage 1 entry remains blocked until an independent reviewer accepts the exact mapping and both snapshot outcomes at a named revision. |
| R-02 | `FIXED` | Source delegation is authenticated before raw request size/schema checks. Operator identity is checked before installation payload screening. PAS reads require an authenticated principal before request encoding/sizing. Oversized authenticated input remains bounded. Added regression cases cover these orderings and zero lookup. |
| R-03 | `UNVERIFIED` | `SourceProvider.fetch()` still constructs a new `TurnBudget` per provider invocation. The frozen same-app multi-provider aggregate byte/token/result/call budget is not demonstrated; its gate remains open. No production coordinator behavior was changed to manufacture a pass. |
| R-04 | `FIXED` | Delegation type, bytes body, body size, bytes signature and digest length are checked before HMAC. Malformed delegation metadata returns `unauthenticated` and performs no payload lookup. |
| R-05 | `PARTIALLY_FIXED` | The backend and hermetic-capabilities CI jobs now check out full Git history. The source-lock tests and sealed-evaluation test pass locally. A post-change GitHub Python 3.11/3.12 matrix run is unavailable, so CI is not claimed green. |

## Verification

Commands were run with the repository's `backend/.venv` (Python 3.11.15). Results reflect this local environment only.

| Command | Exit and result |
| --- | --- |
| `cd backend && python -m pytest -q --tb=short tests/test_synthetic_application_context.py tests/test_context_provider.py tests/test_context_authorization.py tests/test_context_builder.py tests/test_context_planner.py tests/test_auth.py tests/test_applications.py tests/test_application_scope.py` | 0; **235 passed**, 3 dependency deprecation/support warnings. |
| `cd backend && python -m pytest -q --tb=short tests/test_source_contracts.py` | 0; **44 passed**. `31813dd394e9adeed29f9dae608fb9bdae863aeb` is a verified ancestor of `HEAD` (`git merge-base --is-ancestor`, exit 0). |
| `cd backend && python -m pytest -q --tb=short tests/test_reasoning_grounded.py -k test_sealed_evaluation` | 0; **1 passed, 76 deselected**. |
| `make backend-lint` | 0; Ruff reports all checks passed. |
| `make source-contract-check` | 0; portable source passed. Strict historical runtime replay and installed native capability were not run. |
| `make hermetic-capability-check` | 0; every prerequisite suite completed successfully, including offline runner fences, reasoning, synthetic reasoning, memory, workflow and mutation checks. |
| `make backend-test-offline` with the documented SDK/checklist `PYTHONPATH` | 1; **3,402 passed, 11 failed, 1 skipped, 92 errors, 204 deselected**. Loopback HTTP fixture setup is blocked by this environment: `sock.bind(("127.0.0.1", 0))` raises `PermissionError: [Errno 1] Operation not permitted`. A focused reproduction in `test_offline_information_handling.py` failed at that bind after 55 preceding cases passed; retrieval and signed HTTP fixtures fail at the same bind. This is an environment-limited run, not a pass. |
| `make naming-policy-check` | 1; it reports pre-existing untracked planning and handoff paths and their phase-coded text, including `docs/context-inference-integration/phase-1-handoff/*` and `pas-context-inference-integration-plan.md`. These user files were preserved and are outside this remediation. |
| `git diff --check` | 0. |

The changed Markdown files' local relative links were checked and resolved successfully.

## Remaining decisions and release boundary

The next Stage 0 action belongs to an independent reviewer: record the accepted revision and scope for the actor/permission mapping and positive and negative in-process snapshot cases. The next implementation proof for R-03 must establish one request-local aggregate source budget across a same-app multi-provider turn, including failed-attempt accounting and no partial optional result disclosure.

The local offline backend run also requires a runner that permits the repository's loopback-only test hosts, followed by the full Python 3.11 and 3.12 GitHub matrix after the full-history workflow change. Naming-check results should be reevaluated with the intended tracked/untracked file set; unrelated planning artifacts were not renamed or removed.

The synthetic composition remains an offline test witness. MCP, manual export of real data, SIWC, paid inference, shared hosting, live identity/provider behavior, and production remain separately gated; production is **NO_GO**.

# Phase 25.4 post-implementation review fix evidence

Date: 2026-10-11

Tested base revision: `e1723a750fd25edefc503e481138f9e4c6b18f1d` plus the review-fix working-tree changes. Seven unrelated pre-existing untracked review/handoff notes were preserved and excluded from the change.

## Review findings

| Finding | Resolution and evidence |
| --- | --- |
| F1 — Canonical runtime composition | Added a deployment-owned `ContextRuntimeRegistry` for provider implementations and planning contributions. The canonical FastAPI context-assembler dependencies compose these with built-ins for both automatic and external preparation; capability authorization remains separate. `test_context_runtime_composition.py` exercises a synthetic fifth provider/rule through the real dependency path and verifies that a declared capability without an implementation causes no provider call or selection. |
| F2 — Derived-memory bypass | Added a shared manual-import eligibility check using canonical turn attribution and the current typed reuse policy. It gates post-completion extraction and validates existing memory source turns and source memories before retrieval. Denied manual turns remain in canonical conversation storage but cannot produce or supply reusable memory. Memory and sidecar contract tests cover the denial path. |
| F3 — Reuse policy narrowing | Replaced the reuse boolean with `ManualImportReusePolicy(allowed, maximum_sensitivity)`. The original turn's effective sensitivity is checked for direct history and derived-memory use. Tests cover denial and a sensitivity ceiling. |
| F4 — Explicit denied continuation | Explicitly selected manual-import targets denied by policy now fail with `continuation_source_policy_denied` instead of being silently removed. The sidecar disables the unavailable inclusion control and explains the policy restriction. Backend and frontend tests cover the behavior. |
| F5 — Connected domain-launch coverage | Extended the synthetic contract fixture through connected preparation, dispatch, and finalization with a synthetic profile and signer, using the same launch, entity-provider, and policy path as manual and automatic turns. The fixture then continues automatically and checks historical attribution remains unchanged. This is local synthetic coverage, not live provider acceptance. |
| F6 — Transitive derived-state revocation | The immediate memory path in F2 is closed. Transitive revalidation of already-derived assistant turns, summaries, artifacts, traces, and exports after later policy/source changes remains an open Phase 15 gap; no separate Phase 25.4 revocation graph was introduced. External execution remains behind its default-off acceptance gate. |
| F7 — Overlapping execution identity | New attribution writes use the canonical `execution_origin` values `automatic_managed`, `connected_local`, and `manual_import`, independent of provider identity and observation source. Legacy `mode` records are decoded compatibly and normalized. Backend and frontend attribution tests cover canonical and legacy records. |
| F8 — Future Apply authority | Removed `future_apply_operation_ids` from sidecar policy. Apply remains non-executable; the planned typed Phase 31 mutation capability is the authority for any future operation. |
| F9 — Evidence scope | Updated this record and the Phase 25.4 architecture, implementation guide, and current-state summary to distinguish canonical local composition tests from synthetic lane coverage and unverified live acceptance. |

## Verification

| Check | Result |
| --- | --- |
| Focused backend tests for runtime composition, application sidecar contract, external turns, and memory | Passed: 114 tests. |
| `PATH="$(pwd)/backend/.venv/bin:$PATH" make backend-test` | Passed: 1,349 passed, 82 skipped, 2 warnings. Skips include opt-in persistence, cloud, and provider checks. |
| `PATH="$(pwd)/backend/.venv/bin:$PATH" make backend-lint` | Passed. |
| `UV_CACHE_DIR=/private/tmp/personal-ai-system-uv-cache make backend-build` | Passed: source distribution and wheel built. |
| `make frontend-test` | Passed: 21 files, 111 tests. |
| `make frontend-lint` | Passed. |
| `make frontend-typecheck` | Passed for application and test TypeScript configurations. |
| `make frontend-build` | Passed: optimized Next.js production build completed. Existing tooling notices were emitted. |
| `PATH="$(pwd)/backend/.venv/bin:$PATH" make context-eval context-plan-eval` | Passed using deterministic fixture runners and fake/estimated counts; this does not establish live provider behavior. |
| `git diff --check` | Passed. |

The frontend commands used the bundled Node.js runtime available in the workspace. Backend tests emitted existing Starlette/httpx and Pydantic warnings; these did not fail checks.

## Remaining acceptance gates

No real domain repository or membership/source-revision adapter was exercised. Phase 15 transitive source-dependency and revocation behavior remains incomplete. Phase 25.2 transaction, concurrent CAS/race, and restart behavior was not checked against DynamoDB Local or a deployed store. Provider/account/billing compatibility, cloud identity, browser private-network/loopback transport, and deployed execution were not exercised. These checks remain **unverified**, not passed by local fakes. The external execution gate remains disabled by default.

The canonical conversation/message store, shared planner/provider/policy/builder path, and existing external-turn state machine remain authoritative. Launch references remain advisory and scope-bound; Copy/manual import do not write domain records; draft Insert remains host-callback-only; Phase 31 mutation execution is not enabled.

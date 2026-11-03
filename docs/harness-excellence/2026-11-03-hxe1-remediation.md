# HXE-1 remediation evidence

**Date:** 2026-11-03
**Reviewed commit:** `9e82b7babd9b0305a18c73af448692ee88473a8a`
**Merge base:** `e3c6169b5ea5157b88665b7812b10cf2d9e02123`
**Profile:** Local synthetic E1 only; no provider, external source account, or cloud access.

## Finding disposition

| Finding | Disposition |
| --- | --- |
| HXE1-R01 P1 | Added a separately launched PAS retrieval host over SDK stdio. It negotiates `2026-07-28`, discovers only `retrieval.query.v1`, returns the exact synthetic quote and citation, and fails closed for wrong owner, actor, application, workspace, client binding, expired source, revoked source, and unsupported tool. These are fixed synthetic host bindings, not installed authentication. |
| HXE1-R02 P1 | Added a hermetic local Markdown + MCP fixture → explicit `retrieval-installation-v2` → canonical PI-5 context → `FakeLLMClient` turn. It checks bytes, SHA-256, issuer and revision, sends both exact quotes once, retains both revision dependencies, treats hostile source text as data, and verifies that removing the separate model-context grant prevents another model request. |
| HXE1-R03 P2 | Added EOF-mid-frame, invalid UTF-8, malformed JSON, oversized frame, excessive response-frame, duplicate tool, nested/drifted schema, wrong output schema, unexpected structured output, wrong HTTP content type, oversized HTTP body, redirect, peer timeout, client cancellation and child-process cleanup coverage. Existing fixed size/time/concurrency limits and content-free failures remain. No retry is made after the one fixture dispatch. |
| HXE1-R04 P2 | Stdio registration now resolves and pins executable and working-directory identities, validates executable ownership and write permissions, checks for replacement before launch, and executes the pinned target. A resolved Python interpreter symlink retains its venv through the macOS launcher marker. Tests cover a valid interpreter symlink, symlink replacement and a group/world-writable executable. This does not claim OS-level isolation. |
| HXE1-R05 P2 | Kept the `mcp==2.3.0` pin and accepted revisions `2026-07-28` and `2025-11-25`. Both are tested with the same SDK implementation; separately implemented legacy-peer compatibility and independent wheel-origin proof remain unverified. Unknown revisions remain rejected. |
| HXE1-R06 P3 | Deferred capability-oriented package/command renaming. No persisted or wire identities changed. |

## Verification

Environment: macOS ARM64; adapter environment CPython 3.12.13, SDK `mcp==2.3.0`; backend environment CPython 3.11.15. Tests used local synthetic documents and fixtures. The process peer audit hook reported zero blocked-network attempts.

| Check | Result |
| --- | --- |
| `make hxe1-check` | PASS: 44 passed, 0 skipped, exit 0. |
| `make hxe1-check HXE1_IMPORT_PATH=` | PASS: 44 passed, 0 skipped, exit 0 after rebuilding and installing the local offline adapter wheel. |
| `make hxe0-check` | PASS: contract PASS; 367 passed, 12 deselected, 0 failed. |
| `make pi5-check` | BLOCKED: native socket bind denied by the managed sandbox (`PermissionError: [Errno 1] Operation not permitted`). No network access was attempted. |
| `backend/.venv/bin/python backend/scripts/pi1_offline_checks.py -q -m 'not loopback_http' backend/tests/test_pi5_retrieval.py backend/tests/test_pi5_context.py backend/tests/test_pi5_http.py` | PASS: 89 passed, 34 deselected, 0 failed. |
| `PATH=/Users/jasonkli/projects/personal-ai-system/backend/.venv/bin:$PATH make backend-lint` | PASS: Ruff reports all checks passed. |
| `UV_CACHE_DIR=/tmp/uv-cache UV_OFFLINE=1 make backend-build` | PASS: backend sdist and wheel built. |
| Offline adapter build (`uv build --no-build-isolation`, CPython 3.12.13) | PASS: adapter sdist and wheel built under `/tmp/hxe1-dist-final2`. |
| Core optional-absence probe | PASS: isolated core import succeeds and `personal_ai_hxe1` is absent. |
| `git diff --check` | PASS. |

The PI-5 native loopback assertion is not represented by its offline fallback. Provider, cloud, native installation, live source, deployed identity and production checks were not run.

## Evidence levels and gates

| Tier | Status | Evidence |
| --- | --- | --- |
| E0 static | PASS for scoped changes | Source, test, documentation and diff review; offline builds and Ruff. |
| E1 synthetic | PASS for the restricted HXE-1 profile | 44 HXE-1 cases, process-boundary PAS retrieval, source-to-context fake-model canary, HXE-0 and offline PI-5 regressions. |
| E2 native installed | BLOCKED | No independent installed authentication environment, native isolation fence or network listener acceptance. |
| E3 live | BLOCKED | No external issuer, provider, rights or account authority. |
| E4 deployed | BLOCKED | No deployed IAM, storage, recovery or erasure evidence. |
| E5 utility | NOT RUN | No approved real-task evaluation. |

Inherited source/send atomicity, source provenance and rights epochs, original-key anti-rollback, retained-output withdrawal, legacy-output quarantine, provider admission, installed MCP fencing, cloud deployment, independent acceptance and governed-memory gates remain open. **Production remains NO-GO.**

## Rollback

Withdraw optional host registrations, quiesce in-flight exchanges, then revert only the scoped remediation commit with `git revert --no-edit <commit-sha>`. Do not remove or rewrite PI-5 installations, authority records, receipts, historical evidence or user data.

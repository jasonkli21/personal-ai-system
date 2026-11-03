# HXE-1 implementation receipt · 2026-11-03

Baseline `e3c6169b5ea5157b88665b7812b10cf2d9e02123`, tree
`8905699be6b0e26c07c3dd48a419ec3333f517af`. The commit containing this
receipt identifies the implementation tree. The pre-existing untracked
companion plan is outside that tree.

## Verification

| Command or probe | Result |
| --- | --- |
| `make hxe1-check` | 22 passed under the Python network audit fence. Zero blocked attempts. |
| `make hxe1-check HXE1_IMPORT_PATH=` | 22 passed with backend and adapter installed from built wheels. CPython 3.12.13, pre-cached SDK and an existing backend dependency directory for imports. This was an installed-package probe with fixture test files from the checkout. |
| `make hxe0-check` | Consumer contract passed, 367 tests passed, 12 native loopback tests deselected, zero blocked attempts. |
| `make pi5-check` | Consumer contract passed. Native check blocked at Unix socket bind with EPERM. |
| `backend/.venv/bin/python backend/scripts/pi1_offline_checks.py -q -m 'not loopback_http'` with PI-5, research, provider usage and inference suites | 197 passed, 34 deselected, zero blocked attempts. Files were `test_pi5_retrieval.py`, `test_pi5_context.py`, `test_research_provider.py`, `test_research_pipeline.py`, `test_retrieval_phase33.py`, `test_pi5_http.py`, `test_provider_usage.py` and `test_inference_execution.py`. |
| `make backend-lint`, adapter Ruff check, `git diff --check` | Passed. |
| `UV_OFFLINE=1 make backend-build` and `uv build --offline --no-build-isolation --python ../../backend/.venv/bin/python` from the adapter | Backend and adapter wheels and sdists built. |
| Core import under `backend/.venv/bin/python -I` | Passed with both MCP and the adapter absent. |
| SDK dependency lock | SDK 2.3.0 and 27 pinned dependencies. Installed-environment `uv pip install --offline --require-hashes --dry-run` reported no changes. A fresh hash-enforced offline install was blocked by the missing downloadable MCP wheel cache entry. |
| Native sandbox probe | Nested `sandbox-exec` failed with EPERM. No native fence or listener acceptance is claimed. |

The [SDK release](https://pypi.org/project/mcp/2.3.0/) records publishing
provenance for the lock's artifacts. The SDK negotiated 2026-07-28 over
a child stdio peer and an in-process ASGI Streamable HTTP peer. The SDK
consumer used modern auto discovery and legacy 2025-11-25 initialization
against the PAS server. It discovered `retrieval.query.v1`, sent the
synthetic query `amber` and received one verbatim quote with a PI-5
citation. Source withdrawal during search and client revocation after
discovery suppressed disclosure. External retrieval failed before
provider accounting. Removing the outbound post-exchange guard made the
revoked-source regression fail. Restoring it brought the suite back to
green. Redirect, endpoint drift and caller denials produced no unauthorized
tool dispatches in the fixture counters.

Fixture SHA-256 values

- `peer.py` · `c31e8994188b3ec4893efe16745138d1b96d20afc783c8b2f223a93530868134`
- `test_hxe1.py` · `313d9acf96c956b2befd934783c3f966e229adc04384358de07f1e367098a21b`
- SDK lock · `c1e16280bdb1e18c8a373d93d6ba1d6f76285b0909abe27142743d015dcaed64`

## Evidence classification

| Tier | Classification |
| --- | --- |
| E0 static | Local source, build, lint and contract checks passed. |
| E1 hermetic | **PARTIAL.** Positive scoped PI-5 retrieval, exact local loader, default-off fixture reads and negative cases passed. The SDK consumer is a separate dependency exercised in the same test process. The child stdio server is a synthetic script, and the HTTP peer shares its fixture implementation. A separately distributed consumer/peer and a composed HXE-1 ingestion-to-model canary remain open. Existing PI-5 fake model/context checks ran as regressions. |
| E2 native installed | **BLOCKED.** Authenticated installed host and native-fenced independent client/server conformance remain open. |
| E3 live | **NO-GO.** External issuer and account admission, P19 physical send and atomic revoke permits remain open. |
| E4 cloud/recovery | **NO-GO.** Deployed identity, monotonic restore authority and erasure remain open. |
| E5 utility | **UNMEASURED.** No real model or external coding-harness utility evidence. |

See [ADR 0024](../decisions/0024-hxe1-read-only-mcp.md) and the
[adapter guide](../../adapters/hxe1/README.md) for ownership and rollback.

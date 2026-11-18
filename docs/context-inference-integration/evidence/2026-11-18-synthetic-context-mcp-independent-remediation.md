# Synthetic outbound MCP independent review remediation · 2026-11-18

This record documents the focused remediation of review findings against
historical candidate `50bff63ec8f28b45b6196b2a824944b01c21b380`, whose parent
was `c1500ce9be41a789131ef1fca323e9d97bdf11fe`. The remediation was committed
with this record; `git show -s --format=%H HEAD` identifies its exact commit.
The original dated verification remains historical and was only clarified to
pin its candidate SHA. This is maintainer-run evidence, not independent
acceptance or hosted CI evidence.

## Finding dispositions

| Finding | Status | Change and focused evidence |
| --- | --- | --- |
| MCP2-001 | **BLOCKED** for physical cancellation; event-loop impact mitigated | The synthetic host offloads the legacy synchronous source client behind eight nonblocking worker slots. A deadline cancels the awaiting request; the worker slot remains occupied until the operation exits. The blocked-exchange test confirms a second request completes, the timed-out response has no result, and no selector is generated late. Python cannot forcibly stop a running synchronous call, so the strict physical-cancellation claim remains blocked for E1 and production transports. |
| MCP2-002 | **FIXED / HOSTED UNVERIFIED** | A dedicated `macos-14-xlarge` Python 3.12 job installs the existing macOS-arm64 hash-pinned optional lock, lints, runs the source suite, builds the wheel, installs it, and reruns the suite. The GitHub job has not run from this local commit. |
| MCP2-003 | **FIXED** | The bounded per-subject rate table is populated only after a valid tool call resolves to a linked PAS binding. Discovery/list and unlinked subjects do not consume those buckets. The 1,024-subject churn test confirms owner A can still search and that only one source lookup occurs. |
| MCP2-004 | **FIXED for direct ASGI HTTP; future TLS ingress deferred** | The protected app rejects non-HTTPS ASGI scopes. Documentation requires a trusted TLS ingress that blocks direct HTTP and does not trust arbitrary forwarded headers. No listener or deployment was enabled. |
| MCP2-005 | **FIXED** | Duplicate control headers and comma-coalesced ambiguous values are rejected before frame dispatch. The repeated-header HTTPX test covers protocol version, method, name, and content type and confirms zero source lookup. |
| MCP2-006 | **FIXED** | The historical evidence now names its exact candidate SHA. This remediation is separately dated and preserves the old command results as historical author-reported evidence. |

## Verification performed

Local macOS ARM64 environment, CPython 3.12.13 for the MCP SDK suite, pinned
`mcp==2.3.0`, existing lock
[`requirements-macos-arm64-py312.txt`](../../../adapters/mcp_source/requirements-macos-arm64-py312.txt).
Lock SHA-256: `c1e16280bdb1e18c8a373d93d6ba1d6f76285b0909abe27142743d015dcaed64`.
The lock was not changed. The offline test runner reported zero blocked network
attempts.

| Command | Observed result |
| --- | --- |
| `make mcp-context-check` | Exit 0; 99 passed. |
| `uv --no-cache build --offline --no-build-isolation --python adapters/mcp_source/.venv/bin/python --wheel --out-dir /tmp/pas-mcp-context-wheels adapters/mcp_context` | Exit 0; optional wheel built. |
| `uv --no-cache pip install --python adapters/mcp_source/.venv/bin/python --no-deps --target /tmp/pas-mcp-context-installed-final /tmp/pas-mcp-context-wheels/personal_ai_mcp_context-0.1.0-py3-none-any.whl` | Exit 0; final wheel installed into an isolated target directory. |
| `make mcp-context-check MCP_CONTEXT_IMPORT_PATH=/tmp/pas-mcp-context-installed-final:backend/src:backend/tests MCP_ADAPTER_PYTHON=adapters/mcp_source/.venv/bin/python` | Exit 0; 99 passed against the final installed wheel. |
| `make mcp-adapter-check` | Exit 0; 44 passed; zero blocked network attempts. |
| `backend/.venv/bin/python -m ruff check adapters/mcp_context` | Exit 0; clean. |
| `LITELLM_LOCAL_MODEL_COST_MAP=True .venv/bin/python -m pytest -q --tb=short tests/test_synthetic_application_context.py` from `backend/` | Exit 0; 123 passed, 2 dependency warnings. |

The local wheel install and tests establish package import and behavior in this
checkout only. The new GitHub job is **not yet hosted evidence**. The exact
Python lock remains targeted to macOS ARM64; no Linux reproducibility claim is
made.

## Release gates and residual limits

E1 remains **NOT READY / awaiting independent acceptance**. The bounded worker
shim does not prove physical cancellation of a stalled synchronous source
operation. Upstream independent Stage 0 mapping/snapshot acceptance is still
required, and R-03 aggregate budgets remain unverified. Installed ChatGPT E2
remains `BLOCKED_UNVERIFIED`; production E3 remains `NO_GO`. No real OAuth,
client, TLS deployment, citation URL, application record, model/provider call,
paid route, or subscription inference was exercised or authorized.

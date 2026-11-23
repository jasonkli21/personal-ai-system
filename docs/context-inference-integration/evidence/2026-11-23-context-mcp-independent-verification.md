# Independent offline MCP review · 2026-11-23

**Decision.** The Linux offline adapter and wheel passed their scoped verification. Full E1 acceptance remains open for the dependencies and physical-stop requirement below. E2-N is NOT RUN, E2-I is BLOCKED_UNVERIFIED and E3 is NO_GO.

Remote main matched baseline 07b43ece590634ecc290ee8ba2b5a99763206f30 at review entry. The reviewer ran the original 99 source tests successfully on a separate checkout. Clean review of Sol commit 016a2ea249c220d533a2a0450781f7be28401fb3 produced two failures and 133 passes on both source and wheel. The citation test attempted a second SDK lifespan on a single-use app. The work test assumed the default executor could start eight workers plus its observer. The independent review also found a missing tenant dimension in workspace registration, a rate charge separated from current authority resolution, and authenticated browser reads outside the linked-subject limit.

Luna code 78b3e841d860766383b94a6a04d95c0a1a25e8e1 scopes registration by tenant, charges at authorized read entry, limits browser reads, and repairs the two failing witnesses. Independent clean source and rebuilt-wheel runs at ba2175752aaf405f5b362314f4b4759ec6e35e95 each passed 139 tests. Final review added factory rejection of missing, blank and padded registration tenants. The final executable revision is 8f6924f18274888c692f7b9a8b28c1721685e669.

## Execution receipts

Linux x86_64, CPython 3.12.14, MCP and MCP Types 2.3.0. The optional stack was installed with the existing SHA-256 hash requirements. Dependencies were provisioned separately from the fenced runs. Each adapter test run used the repository offline runner. Hosted macOS execution remains unverified.

| Check | Observed result |
|---|---|
| make mcp-context-check with MCP_ADAPTER_PYTHON=/tmp/r7env/bin/python at final executable revision | Exit 0, 142 passed, zero skipped and zero blocked network attempts |
| Offline uv wheel build, no build isolation, clean no-deps target install | Exit 0. Import resolved to /tmp/r7finishedinstall/personal_ai_mcp_context/__init__.py |
| Same make target with MCP_CONTEXT_IMPORT_PATH=/tmp/r7finishedinstall:backend/src | Exit 0, 142 passed, zero skipped and zero blocked network attempts |
| Scoped Ruff and git diff --check | Exit 0 |
| Backend test_synthetic_application_context.py and consumer contract checker at ba21757 | 123 passed with zero blocked network attempts, consumer contract PASS |
| make sdk-install-check with UV_OFFLINE=1 | Exit 0 |
| make mcp-adapter-check | 11 failures, 33 passes on candidate and baseline. Trusted path/ownership checks reject this workspace environment. |
| Backend lint and hermetic-capability-check | Same failure on baseline and candidate for lint in tests/test_memory.py; same three reasoning failures on each for the hermetic target. Both make targets exit 2. |
| Naming policy and source-contract targets | Exit 2. Historical naming and source-lock discrepancies reproduced on the base in the author investigation. No shared contract files in the R7 diff. |

## Criterion dispositions

Use the [candidate ledger](2026-11-23-context-mcp-offline-candidate.md) for each numbered row's test node, packet and expected observation. The following independent results supersede its execution statuses only for the named scope. Counts and latencies beyond test assertions are unobserved.

| R7 rows | Independent disposition |
|---|---|
| 01 | PASS for base pin and historical source rerun. Stage 0, R-03 and hosted CI remain open. |
| 02–05, 07–09, 11–14, 17–18, 21, 23–24, 27, 31, 33, 35 | PASS for offline adapter assertions, including exact resource audience, field projection, framing, admission and both tool representations. |
| 06, 15–16, 19 | PASS for direct ASGI and synthetic authority changes. Public TLS, installed client identity and native revocation/source remain unverified. |
| 10 | PASS for synthetic metadata assertions. Actual OAuth code exchange and callback modes BLOCKED at E2-I. |
| 20, 22 | PASS for synthetic empty-result and sensitive-source denial. Broader timing, privacy and live Health approval remain unverified. |
| 25–26, 34 | PASS for process-local miss, expired/stale binding and restart denial. Multi-worker continuity and native restore NOT RUN. |
| 28–29 | PASS for in-process authenticated citation view, constrained URL and response-header assertions. Installed click, upstream access logging and production ingress unverified. |
| 30, 38–39 | Installed mode and external privacy/operational admission remain blocked. |
| 32 | PASS for timeout, retained physical slots, recovery, no late publication and the async fixture's cleanup. BLOCKED for physical termination of legacy synchronous work. |
| 36 | PASS for observed SDK install and consumer contract. Inbound and broader compatibility checks have residual baseline failures. |
| 37 | PASS for changed-path isolation. Integration with a future SADRC result NOT RUN. |
| 40 | PASS for this scoped independent source/wheel record. External receipts and hosted CI remain outstanding. |

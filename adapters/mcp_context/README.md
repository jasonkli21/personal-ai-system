# Read-only application context over MCP

This optional adapter serves synthetic application context to an MCP client
over stateless Streamable HTTP revision `2026-07-28`. The default PAS API does
not load it. The [MCP source adapter](../mcp_source/README.md) handles the
opposite direction.

Use `personal_ai_mcp_context.server.context_mcp_app` from a test composition
with `enabled=True` and `environment="test"`. Supply a canonical HTTPS
resource and issuer, an exact set of approved OAuth client IDs, a verified
access-token callback, and an authorized source reader implementing
[`contracts.py`](src/personal_ai_mcp_context/contracts.py). The ASGI app owns
the MCP endpoint and the RFC 9728 protected-resource metadata route. The
authorization server owns issuer metadata. The factory does not open a
listener or supply an issuer, token verifier, account mapping, or source.

The verifier checks signature or trusted introspection and revocation for every
request and again before successful disclosure. The reader maps the verified
issuer and subject to the current PAS owner, selects one connection by OAuth
client ID, and checks the exact app, workspace, installation and
`chatgpt-mcp` grant for `answer-context`. Ambiguous connections fail closed.
Each invocation gets one deadline and one budget, with at most one delegated
source request and zero retries. Source and permission revalidation precedes
the result. The adapter uses short-lived, capacity-limited selectors that become
unusable on eviction or restart. Call rate is capped at 30 per issuer and
subject per fixed one-minute window. At most eight requests can be in flight.

| Tool | Arguments | Successful structured result |
| --- | --- | --- |
| `search` | `query`, nonblank and at most 256 UTF-8 bytes | `results`, up to ten `{id, title}` objects |
| `fetch` | `id`, opaque ASCII selector of at most 200 bytes | `id`, `title`, `text`, `source`, `revision`, `observed_at`, `fresh_until` |

The test reader renders `text` as a JSON string of the allowed typed source
fields. Both structured and text MCP content encode the same projection.
The entire serialized tool result is capped at 8,192 bytes. Fetch timestamps
use UTC. Both tools require `context:read`. HTTP 401 and 403 carry Bearer
challenges for missing or invalid credentials and insufficient scope
respectively. A credential failure during a read produces a tool-level
challenge. Business denials share one content-free tool error.

This synthetic tool profile omits citation URLs. Installed ChatGPT, Deep
Research and company knowledge require separate client evidence. Citation
surfaces also require an authenticated, user-openable canonical item URL.
Production remains **NO_GO**. See the [read-direction contract and release
boundaries](../../docs/context-inference-integration/chatgpt-integration-boundaries.md).

Run `make mcp-context-check` from the repository root with CPython 3.12 and the
[locked optional MCP stack](../mcp_source/requirements-macos-arm64-py312.txt).
Set `MCP_ADAPTER_PYTHON` when using a different environment. The target also
needs the backend and pytest dependencies available to that interpreter. It
loads the source package by default. Set `MCP_CONTEXT_IMPORT_PATH` to the
installed package environment's import path or set it empty when the adapter
and backend distributions are both installed. The tests use the SDK over
in-process HTTP, the existing synthetic source package, and a test-only signed
issuer with controllable revocation. The runner blocks Python network egress.

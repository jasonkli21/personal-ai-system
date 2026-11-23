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
Workspace is required by default. Test composition may pass
`workspace_less_sources` with exact `SourceInstallation` application, source
and installation IDs. Those bindings must explicitly set `workspace_id=None`.
The reader verifies current domain ownership and enforces record and field ACLs
on search, fetch and revalidation. The synthetic Travel reader uses trip ACLs
within a tenant and owner. Fitness uses the exact workspace grant.
Each invocation gets one deadline and one budget, with at most one delegated
source request and zero retries. Source and permission revalidation precedes
the result. The adapter uses short-lived, capacity-limited selectors that become
unusable on eviction or restart. Use one adapter composition in one process.
The factory accepts only `process_count=1`. Call rate is capped at 30 per issuer and
subject per fixed one-minute window after the PAS connection is resolved; valid
but unlinked OAuth subjects do not consume linked-subject buckets. At most eight
requests can be in flight. Direct plain-HTTP requests are rejected. Any future
TLS-terminating proxy must be an explicitly trusted ingress that prevents direct
HTTP access; forwarded headers alone are not trusted.

The synthetic fixture adapts its legacy synchronous source client through at
most eight worker slots. A timed-out call cannot publish its late result, but
Python cannot forcibly stop an already running synchronous operation. The slot
remains occupied until that operation exits. This fixture shim does not establish
physical cancellation for E1 or a production source transport.

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

## Synthetic citation profile

The factory selects the citation profile only with the exact HTTPS
`/mcp-citations/v1` resource path and a separately trusted `verify_browser`
callback. Issued access tokens must name that resource as their audience. The
default resource retains the URL-free tool schemas above.

| Tool | Successful structured result |
| --- | --- |
| `search` | `results`, up to ten `{id, title, url}` objects |
| `fetch` | `id`, `title`, `text`, and the search result's exact `url` |

Both representations share the 8,192-byte limit. The adapter generates
same-origin HTTPS URLs under `/citations/v1/` with an opaque locator that is
stable for the exact grant and record revision in that process. The browser
view requires a current, separately authenticated owner, subject, tenant and
actor. It checks the original connection, grant, field ACL, watermark, record
revision and expiry at open and before release. Its JSON body projects the
same title and text as fetch. It uses private no-store caching headers and a
no-referrer policy. Failed authentication or authority produces an empty denial
and the view issues no redirects. An external composition would require the
source owner's independently approved browser authentication and access-log
policy.

Installed ChatGPT, deep research and company knowledge require separate
client evidence. Production remains **NO_GO**. See the [read-direction
contract and release boundaries](../../docs/context-inference-integration/chatgpt-integration-boundaries.md).

Run `make mcp-context-check` from the repository root with CPython 3.12 and the
[locked optional MCP stack](../mcp_source/requirements-macos-arm64-py312.txt).
Set `MCP_ADAPTER_PYTHON` when using a different environment. The target also
needs the backend and pytest dependencies available to that interpreter. It
loads the source package by default. Set `MCP_CONTEXT_IMPORT_PATH` to the
installed package environment's import path or set it empty when the adapter
and backend distributions are both installed. The tests use the SDK over
in-process HTTP, the existing synthetic source package, and a test-only signed
issuer with controllable revocation. The runner blocks Python network egress.

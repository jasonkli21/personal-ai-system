# ChatGPT integration boundaries

**NOT DEPLOYED.** The protected read interface has a synthetic MCP implementation. Each live direction needs its own identity, grants, evidence and release decision.

## Read direction: ChatGPT to PAS protected MCP

The [synthetic read-only adapter](../../adapters/mcp_context/README.md) targets stateless Streamable HTTP revision `2026-07-28`. Its default profile omits `url` from both schemas. Search returns at most ten `{id, title}` objects. Fetch returns `id`, `title`, `text`, `source`, `revision`, `observed_at`, and `fresh_until`. The resource validates the exact issuer, audience, client and `context:read` scope. Access also requires a separate `chatgpt-mcp` grant. Structured and text content encode the same projection under one serialized result limit. Independent E1 acceptance is pending. [Baseline synthetic verification](evidence/2026-11-18-synthetic-context-mcp.md)

Direct plain-HTTP requests are rejected by the synthetic ASGI edge. Any future TLS-terminating ingress must be a trusted, documented boundary that blocks direct HTTP access; arbitrary forwarded headers do not establish HTTPS. The fixture's bounded worker shim prevents timed-out synchronous reads from blocking the event loop or publishing late results, but does not physically cancel a running source operation.

Installed ChatGPT remains `BLOCKED_UNVERIFIED`. A real authorization server must publish issuer metadata and verify the exact redirect URI, client registration, authorization code with PKCE S256 and resource binding at authorization and exchange. The resource publishes protected-resource metadata and requires current access-token and connection state. Deep research and company knowledge additionally require the documented citation profile and an authenticated, user-openable canonical item URL. [OpenAI search and fetch format](https://developers.openai.com/api/docs/mcp) · [MCP authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)

### Synthetic citation profile

Trusted test composition can select the separate `/mcp-citations/v1` HTTPS resource with a matching token audience and a browser authentication callback. The URL-free resource keeps its existing schemas and audience.

Each disclosure checks the owner grant for the exact source, installation, app, workspace mode, fields, purpose, recipient and expiry. Travel can use explicit null workspace scope under exact source registration and current trip and field ACLs. Fitness retains required workspace scope.

| Tool | Input | Result | Annotations |
| --- | --- | --- | --- |
| `search` | One nonblank UTF-8 query up to 256 bytes | `{results: [{id, title, url}]}` with at most ten authorized hits | Read-only, nondestructive, closed-world |
| `fetch` | The opaque selector from search, up to 200 bytes | `{id, title, text, url}` for the exact current record | Read-only, nondestructive, closed-world |

Search and fetch emit the same canonical, same-origin HTTPS URL. It uses a process-local opaque locator scoped to the exact grant and revision. The browser view separately authenticates the user and rechecks tenant, owner, connection, grant, revision, record ACL and fields. Denials disclose no records and the URL carries no credentials. The view uses private no-store caching and a no-referrer policy. Installed protocol, schemas, OAuth callback and citation behavior require evidence for each intended ChatGPT mode.

The [inbound MCP adapter](../../adapters/mcp_source/README.md) reads an MCP source into PAS.

## Export direction: PAS snapshot for manual use

Manual export requires a live grant for the exact ChatGPT/manual recipient, purpose, fields and selected source revisions. A grant to `runtime-a` or `runtime-b` cannot be reused. PAS authenticates owner/actor, re-fetches exact revisions under recipient-bound authority, checks grant and expiry, creates a redacted preview, binds confirmation to recipient/purpose/fields/content digest, then returns an all-or-nothing snapshot and content-free audit receipt. If one item is stale, unauthorized or unavailable, reject the whole export. PAS rechecks dependencies before any PAS-controlled import/reuse.

Portable content contains no bearer token, delegation, credential, raw grant secret or authority-bearing URL. A snapshot ID is not a bearer authorization. A local download handle must be owner-bound and short-lived. Explain before confirmation that a manual recipient may retain a copied snapshot after revocation or expiry; PAS cannot recall an offline copy. See the exact export sequence in the [source contract](application-context-contract.md).

## Execution direction: connected-app inference

ChatGPT authentication and MCP read access do not grant SIWC or paid execution. SIWC plan inference is a distinct connected-app route with exact user, app, operation, model, host and provider eligibility. User preference, observed account/workspace credit settings, and runtime/distribution eligibility are separate evidence. If credits/no-charge behavior is unknown, deny. The runtime must be user-controlled; persistent SIWC credentials cannot live on PAS shared managed infrastructure. No paid upgrade may be required to use an eligible plan route. Generic multi-app plan proxy remains `BLOCKED_PENDING_APPROVAL`; a named local connected app remains `BLOCKED_UNVERIFIED` until evidence is obtained.

The Personal AI Local Bridge exercises one foreground PAS chat turn with synthetic history and injected transports. The issuer requires the authenticated owner, an independently configured pairing and source-free assembly before it signs. The operator exposes identity-only commands, and the private API omits the SIWC text profile from connected execution options. [Local bridge contract](../../backend/src/personal_ai/local_bridge/README.md).

Any future provider send checks source, grant and recipient at preparation and just before a single-use short-lived permit; the verified host performs its final possible check and durably fences send-start. This is not an atomic source-to-provider guarantee. A change noticed before send denies; a midstream change stops further PAS-controlled output/reuse, but already transmitted bytes cannot be recalled. Unknown sends never retry or fall back automatically. The residual check-to-wire race blocks live data pending measured acceptance.

## Independent status

| Capability | Status | Minimum next evidence |
| --- | --- | --- |
| Synthetic source projection into PAS | Private fixture implemented with maintainer entry acceptance | Independent review of the [authorization and assembly evidence](evidence/2026-11-17-synthetic-application-context.md) |
| Protected ChatGPT-facing MCP | Synthetic E1 implemented, awaiting independent acceptance. Installed E2 `BLOCKED_UNVERIFIED`. | Independent review of the exact synthetic candidate. Installed client, real registration and issuer, audience/scope checks, and live isolation and citation evidence for external use. |
| Manual ChatGPT snapshot | Proposed, recipient-grant gated | Preview/recheck, copy warning and independent disclosure review |
| User-controlled local SIWC | `BLOCKED_UNVERIFIED` | Exact app/user/workspace/host approval; provider eligibility, credits, serializer and usage evidence |
| PAS-managed multi-app SIWC | `BLOCKED_PENDING_APPROVAL` | Written provider authorization for exact hosting, app scope and credential custody |
| Paid API | `BLOCKED_UNVERIFIED` | Exact endpoint/model/payer grant, enforceable cap, atomic holds and reconciliation |

No evidence in this draft admits a live surface, OAuth client, provider account, endpoint, host, or distribution.

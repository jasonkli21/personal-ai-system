# ChatGPT integration boundaries

**NOT DEPLOYED.** The protected read interface has a synthetic MCP implementation. Each live direction needs its own identity, grants, evidence and release decision.

## Read direction: ChatGPT to PAS protected MCP

The [synthetic read-only adapter](../../adapters/mcp_context/README.md) serves stateless Streamable HTTP revision `2026-07-28`. Its custom tool profile omits `url` in both schemas. Search returns at most ten `{id, title}` objects. Fetch returns `id`, `title`, `text`, `source`, `revision`, `observed_at`, and `fresh_until`. The resource validates an exact issuer, audience, client and `context:read` scope. Access also requires a separate `chatgpt-mcp` grant. It returns both structured and text content under one serialized result limit. Independent E1 acceptance is pending. [Synthetic verification](evidence/2026-11-18-synthetic-context-mcp.md)

Installed ChatGPT remains `BLOCKED_UNVERIFIED`. A real authorization server must publish issuer metadata and verify the exact redirect URI, client registration, authorization code with PKCE S256 and resource binding at authorization and exchange. The resource publishes protected-resource metadata and requires current access-token and connection state. Deep research and company knowledge additionally require the documented citation profile and an authenticated, user-openable canonical item URL. [OpenAI search and fetch format](https://developers.openai.com/api/docs/mcp) · [MCP authorization](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)

### Draft citation profile

`https://pas.example.invalid/mcp` is a placeholder in the draft citation contract. The schemas below describe the proposed citation surface.

Each disclosure has a separate live owner grant naming exact source, app, workspace, fields, purpose, recipient and expiry. ChatGPT identity alone grants no source access and does not authorize plan or paid inference. No arbitrary tools, mutations, prompts that invoke tools, cross-resource token exchange, or bearer tokens in URLs are permitted. Citation URLs are authenticated resolution handles scoped to the same owner and resource; they contain no bearer query parameter and disclose nothing to a foreign tenant. Errors are bounded and content-free.

The only proposed tools are:

| Tool | Input schema | Output schema | Annotation |
| --- | --- | --- | --- |
| `search` | `{ "type":"object", "properties":{"query":{"type":"string","minLength":1,"maxLength":256}}, "required":["query"], "additionalProperties":false }` | `{ "results":[{"id":"opaque","title":"authorized title","url":"authenticated citation URL"}] }` | `readOnlyHint:true`, `destructiveHint:false`, `openWorldHint:false` |
| `fetch` | `{ "type":"object", "properties":{"id":{"type":"string","minLength":1,"maxLength":200}}, "required":["id"], "additionalProperties":false }` | `{ "id":"opaque","title":"authorized title","text":"bounded projection","url":"authenticated citation URL","metadata":{"source":"opaque","revision":"opaque"} }` | `readOnlyHint:true`, `destructiveHint:false`, `openWorldHint:false` |

Both JSON text content and MCP structured content must encode the same bounded value. Search results are authorized before titles are returned. `fetch` accepts only a previously authorized opaque item reference under the caller's active owner/app/workspace grant. Invalid issuer, audience, client, scope, connection or mapping returns a uniform denial with no records. Exact error names and transport conformance remain to be reviewed against the installed MCP client before implementation.

Proposed complete JSON Schema descriptors (the server validates the input schema and returns output matching the declared schema):

```json
{
  "tools": [
    {
      "name": "search",
      "readOnlyHint": true,
      "destructiveHint": false,
      "openWorldHint": false,
      "inputSchema": {"type":"object","properties":{"query":{"type":"string","minLength":1,"maxLength":256}},"required":["query"],"additionalProperties":false},
      "outputSchema": {"type":"object","properties":{"results":{"type":"array","maxItems":10,"items":{"type":"object","properties":{"id":{"type":"string","maxLength":200},"title":{"type":"string","maxLength":256},"url":{"type":"string","format":"uri"}},"required":["id","title","url"],"additionalProperties":false}}},"required":["results"],"additionalProperties":false}
    },
    {
      "name": "fetch",
      "readOnlyHint": true,
      "destructiveHint": false,
      "openWorldHint": false,
      "inputSchema": {"type":"object","properties":{"id":{"type":"string","minLength":1,"maxLength":200}},"required":["id"],"additionalProperties":false},
      "outputSchema": {"type":"object","properties":{"id":{"type":"string","maxLength":200},"title":{"type":"string","maxLength":256},"text":{"type":"string","maxLength":8192},"url":{"type":"string","format":"uri"},"metadata":{"type":"object","properties":{"source":{"type":"string","maxLength":100},"revision":{"type":"string","maxLength":100}},"required":["source","revision"],"additionalProperties":false}},"required":["id","title","text","url","metadata"],"additionalProperties":false}
    }
  ]
}
```

The [inbound MCP adapter](../../adapters/mcp_source/README.md) reads an MCP source into PAS.

## Export direction: PAS snapshot for manual use

Manual export requires a live grant for the exact ChatGPT/manual recipient, purpose, fields and selected source revisions. A grant to `runtime-a` or `runtime-b` cannot be reused. PAS authenticates owner/actor, re-fetches exact revisions under recipient-bound authority, checks grant and expiry, creates a redacted preview, binds confirmation to recipient/purpose/fields/content digest, then returns an all-or-nothing snapshot and content-free audit receipt. If one item is stale, unauthorized or unavailable, reject the whole export. PAS rechecks dependencies before any PAS-controlled import/reuse.

Portable content contains no bearer token, delegation, credential, raw grant secret or authority-bearing URL. A snapshot ID is not a bearer authorization. A local download handle must be owner-bound and short-lived. Explain before confirmation that a manual recipient may retain a copied snapshot after revocation or expiry; PAS cannot recall an offline copy. See the exact export sequence in the [source contract](application-context-contract.md).

## Execution direction: connected-app inference

ChatGPT authentication and MCP read access do not grant SIWC or paid execution. SIWC plan inference is a distinct connected-app route with exact user, app, operation, model, host and provider eligibility. User preference, observed account/workspace credit settings, and runtime/distribution eligibility are separate evidence. If credits/no-charge behavior is unknown, deny. The runtime must be user-controlled; persistent SIWC credentials cannot live on PAS shared managed infrastructure. No paid upgrade may be required to use an eligible plan route. Generic multi-app plan proxy remains `BLOCKED_PENDING_APPROVAL`; a named local connected app remains `BLOCKED_UNVERIFIED` until evidence is obtained.

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

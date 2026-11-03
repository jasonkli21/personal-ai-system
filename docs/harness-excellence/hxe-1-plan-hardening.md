# HXE-1 plan hardening · 2026-11-03

Baseline e3c6169b5ea5157b88665b7812b10cf2d9e02123, tree
8905699be6b0e26c07c3dd48a419ec3333f517af, main checkout. The companion
plan was already untracked and is excluded from the implementation commit.

- PI-5 owns lexical indexing, source eligibility, citation identity and model
  context. Keep the adapter out of the backend package and frozen evaluator
  inputs. Use the existing executable retrieval registration and service.
- Pin official SDK 2.3.0 in an isolated optional distribution. SDK auto discovery
  can probe modern and fall back to legacy. Keep each exchange uncached and
  allow only tested revisions. Modern discovery is optional in the protocol.
  Inspect transport behavior independently of the nominal client settings.
- Scope the remote pilot to one operator-pinned no-argument document read.
  Bind it to an expected content digest and canonical PI-5 rights record before
  dispatch. Recheck authority and expiry before accepting bytes. Peer metadata
  cannot select URLs, schemas, rights, prompts or execution. No automatic
  installation or model use of remote results.
- Host code must supply current verified caller authority for the PAS server.
  Limit retrieval to explicitly installed public synthetic evidence and use
  the same PI-5 access checks at discovery, execution and disclosure. Reject
  external search, task status and memory on this adapter. Live issuer,
  cost/account and atomic send permits are unavailable. Keep native egress
  and production promotion separately blocked.
- Start with a fixed one-page tool catalog and zero cache lifetime. Prompts,
  resources, pagination and remote authentication challenges are outside the
  pilot. The SDK follows some redirects and its stdio reader buffers lines;
  bound framing or leave a path unavailable where these cannot be controlled.
- Verification matrix before implementation: public UTF-8 snapshot with exact
  bytes and provenance; traversal, symlink, mutation, size and digest denial;
  current caller, scope and source grant before/after exchange; unsupported
  tools, schema drift, duplicate and paginated catalogs, forged content and
  transport interruption; independent SDK client against scoped PAS and a
  separate fixture peer; verify the core with the adapter absent. Run inherited
  PI-5, context and accounting checks under the existing Python audit fence.

Protocol references: [2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28)
and [official Python SDK 2.3.0](https://pypi.org/project/mcp/2.3.0/).

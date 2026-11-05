# HXE-1 Detailed Implementation Plan

Version 1.0 — 2026-11-03. Planning and E1 development authorization only; no production or external-data enablement.  
Repository: [https\://github.com/jasonkli21/personal-ai-system](https://github.com/jasonkli21/personal-ai-system)  
Pinned planning HEAD: e3c6169b5ea5157b88665b7812b10cf2d9e02123 (documentation follow-up); HXE-0 implementation: 9c90c1d844e9126cb494f286e5f0f80e4be9a6a0; HXE-0 review fixes: 1fc902c27941 (verify full SHA in Git).  
Roadmap: /Users/jasonkli/projects/personal-ai-system/docs/personal-ai-system-integrated-roadmap-11-03.md  
Execution: Sol Medium plan review/hardening and implementation in one session, no subagents. Independent review: Sol High. Remediation and final verification: Luna High/XHigh. No review after Luna.

## 1\. Objective and precise exit

Deliver an optional, default-off, read-only MCP integration and source-ingestion vertical slice for unrelated consumers: a PAS MCP client, a narrowly scoped PAS MCP server, a local document loader, one externally sourced adapter behind explicit rights and admission, reproducible independent interoperability canaries, and precise evidence and rollback. Use existing PI-5 retrieval, authority, provenance, context, P19 accounting and HXE-0 external consumer seams. No new general agent loop, arbitrary tool execution or universal source-authority system.

The primary exit is honest E1 hermetic conformance. It may be marked PARTIAL E1 if any mandatory canary is blocked; it must not be called installed/production-ready. An optional E2 independently installed/native-fenced demonstration is valuable but cannot be assumed available. Live E3 external sources, private memory disclosures, cloud deployment and production are NO-GO unless their own explicit issuer, send/revoke, rights, identity and cost gates close.

## 2\. Current baseline and source of truth

* HXE-0 is a PARTIAL E1 local candidate. Its Python SDK 0.1.0, consumer contract v1.2.0, Project Checklist canary, operator-selected host, ADR 0023, generated contract and review fixes exist; native-fenced installed signed server and PI-6 native measurement are blocked. Do not redo HXE-0 or claim stable release acceptance.  
* PI-5 retrieval-v1 is opt-in: bounded operator-installed local lexical corpus, distinct source permissions, citation/provenance identities, exact retrieval.query.v1 tool wire, constrained external search with closed strict-free profile, and content-free attempt journal. It is not a generic executable registry, trusted distributed source issuer or production authorization.  
* Existing context assembly already can recheck gated local retrieval before model send. Memory MEM-0–2 has scoped default-off implementations; MEM-3+ remains frozen. HXE-1 cannot expose private memory merely because an MCP client asks.  
* PI-5 R01–R03, original-intent anti-rollback, revoke-versus-physical-send atomicity, legacy export provenance, source ownership, real provider/source eligibility, native recovery, dependency-origin and HXE-0 installed acceptance remain BEFORE\_ENABLEMENT.  
* The latest v3.1 roadmap adds one key constraint: MCP output to another coding harness is a disclosure; PAS cannot guarantee that remote consumer's future model routing, storage, retention, erasure or privacy controls honor PAS policy. Keep first canaries synthetic/low sensitivity. Optional OpenCode canary is not an exit gate.

## 3\. Authority and architecture invariants

* Derive owner, actor, application, workspace, purpose and client binding from verified PAS auth and operator-selected policy, never from model arguments, MCP description, request headers, localhost assumption or same-owner identity.  
* Treat MCP tool annotations (including read-only hints), names, resource URIs, prompt text and remote output as untrusted claims. An operator-maintained closed allowlist and an exact installed executable mapping determine availability/effect class. No mutating, filesystem, shell, browser or arbitrary URL tools.  
* Keep one source/rights/provenance envelope and one canonical retrieval/context path. Do not add a second search index or permission ledger, parallel memory store, generic RE planner or separate P19 physical-attempt accounting.  
* Read-time source eligibility, rights, grant, revision and expiry must be rechecked before disclosure and again at model send where relevant. Existing local snapshots are not atomic distributed revocation proofs. No external-source-to-hosted-model forwarding until an issuer-bound per-attempt send permit is independently demonstrated.  
* Strict-free and provider-account eligibility remain enforced for every physical model/search/count/embed operation; no paid fallback, hidden retries, automatic rekey after uncertainty or credentials in logs.  
* Bound input, output, tool catalogs, pagination, resource bytes, time, concurrency, fan-out, subprocess lifetime, retries and persistent receipts. Fail closed when contracts/rights cannot be established.  
* Keep the existing generated external consumer OpenAPI and SDK versioning intact unless a deliberately versioned additive change is necessary; HXE-1 MCP surface is separately gated and not automatically an external HTTP API expansion.

## 4\. MCP protocol and packaging decision

Use the official maintained MCP Python SDK as an optional, pinned dependency in a separate adapter distribution/module, subject to a quick license, transitive dependency, Python version, API and reproducible-lock review. The current protocol revision to evaluate is 2026-07-28: stateless requests, optional server/discover, protocol metadata per request, Streamable HTTP routing headers and no required initialize/session. Interoperate with at least one legacy handshake-era peer such as 2025-11-25 only if supported by the pinned SDK; explicitly test negotiation/fallback and refuse unsupported revisions. Never assume an initialize handshake is universal or that pinning a modern revision proves peer discovery.

Sources: [https\://modelcontextprotocol.io/specification/2026-07-28](https://modelcontextprotocol.io/specification/2026-07-28) and [https\://github.com/modelcontextprotocol/python-sdk](https://github.com/modelcontextprotocol/python-sdk) (pin inspected exact version/commit in implementation receipt). Treat official docs as version-sensitive; verify at implementation time.

Package MCP as optional so base core/SDK startup remains credential-free and unaffected if MCP dependencies are absent. Respect existing operator extension selection. Define versioned PAS adapter configuration and capability/effect manifest. Separate client and server feature flags, plus an independent external-source flag, all default false. Do not dynamically import Python from remote metadata.

## 5\. Work package A — contract/ownership and threat-model preflight

* Inspect current repo head, working tree, AGENTS.md, docs/README.md, docs/current-state.md, ADR 0023, PI-5 retrieval-v1, current HXE-0 receipts, PI gate registry, HXE v3.1 roadmap and actual code/tests. Document any drift; protect pre-existing changes.  
* Produce one small HXE-1 ADR covering trust boundaries, MCP server identity, legacy/modern version behavior, server versus consumer authority, scope mapping, resource/source identity, allowlist/effect policy, return/disclosure rights, failure/retry/cancel semantics, and shared P19/PI-5 integration. Specify which MCP operations are unsupported.  
* Explicitly decide where the trusted MCP client catalog and scoped server capability policy live. Distinguish descriptive metadata from authorization. Keep config minimal and reviewable.  
* Freeze a small E1 fixture matrix before coding, including at least one genuine independent package/process seam. Use injected clock/issuer and fake transport; do not require cloud or real accounts.

## 6\. Work package B — bounded MCP client

* Support selected local stdio peer first and selected Streamable HTTP peer second; for stdio use only operator-approved executables/arguments and a constrained working directory, no shell or broad inherited environment. For HTTP use a configured endpoint/transport with HTTPS or narrowly approved numeric loopback; disable redirects, ambient proxies, surprise DNS/URL fetch and private network pivoting. Validate auth and server identity separately from transport reachability.  
* Negotiate protocol and capabilities, distinguishing tools, resources and prompts. Limit list sizes, nesting, names, schemas, resource content and pagination; namespace by immutable server registration and effective scoped capability identity. Reject ambiguous duplicates, changed schema/effect flags and unsupported versions.  
* Only operator-allowlisted exact read-only tools/resources may be invoked. Require current owner/actor/app/workspace/purpose/source rights immediately before dispatch and output disclosure; validate arguments and outputs against bounded schemas. An MCP prompt can be displayed/handled only as untrusted data, never policy or grant.  
* Map source items to canonical PI-5 attribution/rights envelopes; keep upstream resource URI as untrusted source metadata, never an executable fetch target. Do not create a new model tool loop. Preserve content-free error reasons, cancellation and original-key/attempt semantics for ambiguous remote results; no automatic retry of an effect-uncertain call.

## 7\. Work package C — restricted PAS MCP server

* Add an optional read-only server adapter, independently startable without reference apps. Reuse PAS authenticated scope policy and existing service API, not direct database access. Stdio local use needs operator-bound caller credentials/scope; it is not authenticated just by being local. Streamable HTTP must derive identity through verified server middleware and avoid generic public access.  
* Offer bounded local retrieval.query.v1, optional canonical continuation/task-status observation (if an existing safely scoped service supports it) and carefully gated MEM-2 search/fetch only if current issuer/grant/host gates are actually satisfiable. If not, advertise memory as unavailable and exclude it from E1 positive cases; do not silently weaken MEM gates.  
* Each capability has explicit per-client, actor, application, workspace, purpose, expiry, query/result budgets and safe error semantics; support bounded pagination only where service semantics allow. No list-all memory/corpus export, secret dump or cross-app implicit sharing.  
* Retain citations, current rights dependencies, redaction and non-cacheable/withdrawal semantics for each response. Ensure revocation or workspace loss between discovery and call, or between source read and result serialization, suppresses content. Document that already delivered external copies cannot be recalled.

## 8\. Work package D — one local loader and one external source adapter

* Implement a small operator-selected loader for UTF-8 text/Markdown files, using canonical PI-5 installation/source contracts, stable issuer/source ID, exact revision/hash, rights epoch/reference, licensed model-processing permission, sensitivity, observed/expiry and withdrawal. Reject symlinks/traversal, unknown encodings, oversized or changed files and untrusted ownership; ingest nothing by default.  
* Implement one specific operator-selected external read-only source adapter behind an explicit issuer/rights record and narrow endpoint/domain policy. Prefer a hermetic source fixture and fake service for E1. If no verified live issuer/account/rights exists, the live path remains unavailable; do not mislabel the fake adapter as independently authorized E3.  
* Permission filtering must precede indexing, ranking and context packing; subsequent revocation/revision changes must invalidate results, citations and retained downstream output. No arbitrary web crawling, background sync, vector store rewrite or embedding call. Use existing lexical retrieval first.  
* If live external ingestion cannot meet trusted source/current rights and physical-send conditions, deliver a complete default-off adapter contract and negative E1 tests, classify the live gate BLOCKED, and keep the release explicitly partial; do not fabricate real-source coverage.

## 9\. Work package E — integration canaries and regression

Required E1 demonstration:

* Two materially different MCP servers: e.g. a separate packaged stdio fixture and an isolated Streamable HTTP fixture, with one modern and (where pinned SDK supports it) one legacy-compatible peer.  
* One independent MCP client package/process, separate from PAS server and example applications, that discovers and executes a scoped read-only operation.  
* One operator-approved synthetic local corpus with correct quote/citation/source revision, one externally sourced fake adapter, and a composed authorized retrieval-to-model-context fake path when current gates permit it.  
* Negative matrix: wrong owner/actor/client/workspace/purpose, expired grant, revoked source, changed revision during call, unsupported effect, ambiguous read-only hint, duplicate tool names, schema drift, malicious tool description/result, poisoned resource/prompt, resource URI SSRF, symlink/path traversal, broken stdio/framing, body/time/quotas, premature close, uncertain call and retries, stale retained disclosure, missing optional dependency and default-off startup.  
* Zero unauthorized source/physical provider sends; rejected calls must not reveal foreign source IDs, titles, excerpts, token claims, secrets, local paths or raw provider errors. Use an observable fake dispatch counter.

Suggested commands (adapt to actual repo tooling after hardening): make hxe1-check as a bounded fenced/deny-network target; make hxe0-check; make pi5-check; offline backend focused tests; contract generation check; build/install isolated optional adapter and source-free consumer; git diff \--check; backend lint. Treat native loopback, OS egress and full PI-6 as BLOCKED if environment policy prevents them; do not skip silently or alter frozen fixture thresholds to claim success.

## 10\. Deliverables and acceptance matrix

* Optional client and server adapters; tested pinned protocol/SDK compatibility; source/permission contract/ADR; local loader; external-source adapter in safe disabled mode; independent canaries; read-only CLI/example; focused tests; concise docs/router/current-state and gate updates; final source/test receipt with exact commit/tree and limitations.  
* E0: code review, link/config/schema checks, no core import/leak, documented defaults and operator limits.  
* E1: all required conformance and abuse tests reproducible with no unauthorized dispatch or private disclosure; hold exact source/fixture identity.  
* E2: separate installation \+ native-fenced client/server exchange only when available; HXE-0's blocked installed evidence cannot be inherited as a pass.  
* E3/E4/E5: separately authorized real source/protocol peer, deployed identity, issuer/send atomicity, recovery/deletion/real-model utility. Not HXE-1 E1 exit requirements and not implicitly enabled.  
* Define truthfully PASS / PARTIAL / BLOCKED per capability. A missing memory issuer is an intentional unavailable feature, not authorization to bypass it; if the documented minimal E1 server feature set is unmet, label PARTIAL rather than complete.

## 11\. Rollback, boundaries and follow-up

Disable MCP client, MCP server and external source independently; drop optional adapter installation without touching core/SDK v1.2.0, PI-5 corpus/journal, memory provenance or original-key receipts. Quiesce in-flight reads and reconcile any uncertain original keys; never delete receipts solely to achieve rollback. Preserve pre-existing documents, historical PI and MEM locks and evidence. No migration that changes canonical memory or user records without a separate necessity review.

Explicitly defer: general mutating MCP tools, autonomous tool loops, background schedules, arbitrary crawling and web search, broad file formats, embeddings/vector reindex, live private memory exports, unverified cloud/hosted providers, AG-UI/A2A, an OpenCode-specific product, external coding session takeover, RE-2/HXE-3 runtime and MEM-3+. Add no new phase ID.

## 12\. Final handoff to reviewer

Provide exact baseline and commit/tree; modified file list; architecture decisions and deviations; reproducible setup and commands; per-test counts, skipped/blocked reasons and fixture hashes; one legitimate end-to-end transcript with source IDs/citations redacted as appropriate; denial/disconnect/revocation matrix; protocol/SDK version and origin evidence; evidence tier and NO-GO gates; rollback steps. Independent review follows in one separate Sol High session; Luna then remediates and verifies once, with no further review.  

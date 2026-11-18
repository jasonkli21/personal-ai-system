# Application context provider contract

**OFFLINE WITNESS / NOT DEPLOYED.** The in-memory test composition exercises this bounded protocol with synthetic applications. Live application integration, credential issuance, and network transport remain proposals. See the [verification record](evidence/2026-11-17-synthetic-application-context.md) for the exact scope.

## Trust boundaries and principals

| Principal | Verified by | Authority | Cannot do |
| --- | --- | --- | --- |
| Human requester | PAS consumer authentication; verified issuer/subject and current membership | Establishes `RequestScope.owner_id`, optional `acting_user_id`, and the exact request scope | Choose owner/actor/app/workspace in a request body or gain another app's records |
| App client | Operator install record, bound to one PAS `application_id` and pinned origin | Authenticate its own user-facing client to PAS where the existing consumer contract admits it | Authenticate a human or grant source-read permission |
| Source service | PAS validates installation-bound service identity and pinned origin; source separately authenticates PAS | Serve its own records after checking its own ownership/membership and a valid delegation | Infer human consent from machine TLS/OAuth or echoed JSON |
| PAS signer/verifier | Operator-managed key identity and active key set | Sign and verify narrowly scoped, short-lived source delegations | Turn a signature into a durable or independently revocable grant |
| Recipient/host | Separate recipient binding and grant; host identity where applicable | Receive only the exact permitted projection for its named purpose | Reuse a runtime grant for ChatGPT, another host, app, or manual copy |

The existing `RequestScope` owner and actor are derived from verified authentication and server-side membership. The external app's service identity is a separate authenticated transport principal. Source operations are authorized only when **both** identities are valid and the live PAS grant allows the exact owner, actor, source installation, app, workspace, fields, purpose, recipient, operation, and current grant epoch. Same-email accounts with different verified subjects remain different owners. Unknown membership, mismatched IDs, unavailable revocation state, or cross-app access denies before record lookup. Cross-app promotion is not part of this contract.

### Signed source delegation

Each PAS-to-source read carries a signed, short-lived, single-request delegation in authenticated transport metadata (never a URL or portable snapshot). Required claims are `iss` (PAS signer), `aud` (one installed source service), `sub` (PAS-derived end-user subject), `owner_id`, `acting_user_id` (nullable), `application_id`, `workspace_id`, `source_id`, `installation_epoch`, `kind_allowlist`, `field_allowlist`, `purpose`, `recipient`, `operation`, `request_digest`, `nonce`, `grant_id`, `grant_epoch`, `iat`, `exp`, and `kid`. The digest binds the canonical request body; nonces are one-use. The source verifies issuer, audience, key, expiry, nonce, installation and its own record ownership/membership. PAS independently checks the live grant and permission state before and after retrieval. Service authentication is not the delegation, and neither replaces source-side authorization. The test composition injects a pinned fixture signer and verifier with bounded nonce custody. Those keys and identities exist only in the fixture.

## Installation control plane and owner read plane

These are separate protocols and identities. Operator installation/update/disable is control-plane work. It has no owner, actor, workspace, record-read or export authority. Owner data reads are bound to a verified `RequestScope` and a signed delegation. The implementation uses an in-memory synthetic installation registry.

| Operation | Caller / transport | Body | Result |
| --- | --- | --- | --- |
| `install` | Verified operator principal; control-plane transport | `schema_version`, `application_id`, `installation_id`, pinned `origin`, `service_identity`, `projection_schema_id`, `max_sensitivity`, `max_ttl_seconds` | PAS-assigned `source_id`, `installation_revision`, `installation_epoch`; no workspace or record access |
| `update` | Same operator principal | Exact installation ID plus a complete replacement binding and expected revision | New revision/epoch; old cursors and delegations invalidated |
| `disable` | Same operator principal | Exact installation ID and expected revision | Disabled installation; all reads deny |
| `describe` | Human-scoped data plane | Exact installed `source_id`, app and workspace selectors; transport carries verified user scope and delegation | Installed schema and bounded operation capabilities after authorization |
| `search` | Human-scoped data plane | `record_kind`, literal `query`, `limit`, optional cursor | Authorized titles/IDs/revisions only, stable watermark and next cursor |
| `fetch` | Human-scoped data plane | Exact `record_ref` and `source_revision` | One typed projection only if current revision and all grants still match |

The app cannot choose the PAS-assigned source ID, origin, owner, actor, recipient, grant, epoch, or allowed fields. Those values are resolved from trusted registration, request scope, and live authorization. `export_snapshot` is a PAS orchestration operation, not a source operation: PAS authorizes and fetches exact items one by one under recipient-bound authority, then creates a bounded snapshot.

Example operator installation request (control-plane identity is authenticated outside JSON):

```json
{"schema_version":"app-context-v1","operation":"install","application_id":"travel-demo","installation_id":"travel-main","origin":"https://travel.example.invalid","service_identity":"travel-source-prod","projection_schema_id":"travel-projection-v1","max_sensitivity":"sensitive","max_ttl_seconds":300}
```

Example per-owner source request (human identity and delegation are authenticated transport metadata; body selectors are checked against both):

```json
{"schema_version":"app-context-v1","operation":"search","source_id":"itinerary-demo","application_id":"travel-demo","workspace_id":"trip-a","record_kind":"itinerary_leg","query":"shuttle","limit":10}
```

## v1 data shapes and bounds

Reject unknown keys, unsupported schema versions, unknown classifications, malformed UTF-8, IDs that cannot round-trip through the owning PAS types, and any body over the raw serialized UTF-8 limit **before parsing**. Do not normalize IDs to make them fit. The source assigns opaque record refs and revisions; PAS assigns source IDs and installation epochs. `source_revision` changes on every material content or authorization-relevant change. `source_revision` is never inferred from a search cursor. Cursors bind the verified subject, owner, actor, app, workspace, source, kind, literal query, limit, selected fields, purpose, recipient, installation epoch, application policy, grant ID/revision/epoch, watermark, sort position, and expiry. For a currently authorized matching request, an expired cursor or a change to the bound watermark, grant version, or policy requires a fresh search.

The frozen synthetic schema is `itinerary_leg{title:string, platform:string}` and `workout{title:string, duration_minutes:integer}`. Each field has a source schema sensitivity and PAS policy sensitivity; effective sensitivity is the maximum of source, operator, and PAS classification. A source cannot lower classification. Deny unknown fields, malformed types, or values above a grant ceiling. Search titles are disclosed context and require the same current read grant as fetched fields.

| Bound | v1 proposal |
| --- | --- |
| Serialized request/response | 8 KiB raw UTF-8 per message before parsing |
| Search | One page per turn, `limit` 1–10, query 0–256 UTF-8 bytes |
| Fetch | At most 10 exact fetches per turn, shared deadline and aggregate byte/token budget |
| Record projection | 8 KiB raw UTF-8; each string at most 2 KiB |
| Clock | UTC RFC 3339 timestamps; reject naive, future-observed, expired or invalid intervals |
| Order | `effective_at` descending, then opaque `record_ref` ascending; exact ties are stable by `source_id` |
| Error precedence | Authenticate → validate schema/installation → authorize tuple/grant → validate cursor/revision → lookup → enforce limits |

Successful examples below are canonical; JSON examples in this page are illustrative wire values and must parse as strict JSON. `describe` only returns installed, grant-permitted kinds and fields:

```json
{"schema_version":"app-context-v1","source_id":"itinerary-demo","installation_revision":"i3","installation_epoch":3,"operations":["search","fetch"],"kinds":[{"name":"itinerary_leg","fields":[{"name":"title","type":"string","sensitivity":"personal"},{"name":"platform","type":"string","sensitivity":"personal"}]}],"max_page_size":10,"max_record_bytes":8192,"max_ttl_seconds":300}
```

Search response, with the same envelope rules for the fitness source:

```json
{"schema_version":"app-context-v1","source_id":"itinerary-demo","application_id":"travel-demo","workspace_id":"trip-a","record_kind":"itinerary_leg","watermark":"w7","items":[{"record_ref":"r01","source_revision":"v7","record_kind":"itinerary_leg","effective_at":"2030-01-02T08:00:00Z","title":"Demo shuttle A"}],"next_cursor":null}
```

Fetch response. The echoed grant fields are provenance only; PAS permission is derived from its own live grant authority, never from source echo:

```json
{"schema_version":"app-context-v1","source_id":"itinerary-demo","application_id":"travel-demo","workspace_id":"trip-a","record_ref":"r01","record_kind":"itinerary_leg","source_revision":"v7","watermark":"w7","observed_at":"2030-01-02T09:00:00Z","effective_at":"2030-01-02T08:00:00Z","expires_at":"2030-01-02T09:05:00Z","sensitivity":"personal","content_projection":{"title":"Demo shuttle A","platform":"Blue"}}
```

Stale or unauthorized reads use uniform opaque errors; do not reveal tenant existence, title, count, or timing-sensitive pagination metadata:

```json
{"schema_version":"app-context-v1","error":{"code":"stale_dependency","request_id":"req-opaque"}}
```

Stable codes: `invalid_request` (400), `unauthenticated` (401), `unavailable` (404 for absent or unauthorized), `stale_dependency` (409 for an authorized stale revision/cursor/grant), `limit_exceeded` (413), `rate_limited` (429), and `source_unavailable` (503). Retry reads only after fresh authorization and within the same deadline. Never retry an inference send after an unknown outcome.

## Exact synthetic registry and clock

All fixtures use fixed clock `2030-01-02T09:00:00Z`; timestamps are valid at that clock. Each source owns its own revision and authoritative record. The repeated `r01` values deliberately test source-scoped opaque references. Initial grants authorize only the named app answer/runtime; none authorizes ChatGPT or a manual export.

| Owner | App | Workspace | Source | Ref | Revision | Kind and allowed fields | Initial read grant |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `owner-a` | `travel-demo` | `trip-a` | `itinerary-demo` | `r01` | `v7` | `itinerary_leg`: title=`Demo shuttle A`, platform=`Blue`; personal | A → travel answer/runtime-A |
| `owner-a` | `fitness-demo` | `gym-a` | `workout-demo` | `r01` | `v2` | `workout`: title=`Fixture session A`, duration_minutes=20; sensitive | A → fitness answer/runtime-A |
| `owner-b` | `travel-demo` | `trip-b` | `itinerary-demo` | `r01` | `v4` | `itinerary_leg`: title=`Demo shuttle B`, platform=`Green`; personal | B → travel answer/runtime-B |
| `owner-b` | `fitness-demo` | `gym-b` | `workout-demo` | `r01` | `v3` | `workout`: title=`Fixture session B`, duration_minutes=30; sensitive | B → fitness answer/runtime-B |
| `owner-a` | `travel-demo` | `trip-a-ungranted` | `itinerary-demo` | `r01` | `v1` | `itinerary_leg`; **never disclose** | None |

The two operator installations are source-specific and succeed without a user workspace. Tests also include a different verified subject with the same email, service-only credentials, mismatched actor, and forged app/workspace/source/recipient/purpose/epoch. Missing or unsupported installation/version denies before lookup. Fixture search results and encoded responses are byte-stable for identical authorized inputs.

## Mapping into existing PAS context

This adapter feeds the existing provider coordinator, planner and assembler. It does not create a new context model, authorization engine, memory store, token counter or model route. Stage 1 admission requires an owning application policy that explicitly registers the provider and fields; registry defaults alone do not grant access.

| Source value | Existing PAS value | Rule |
| --- | --- | --- |
| Installed source + schema revision | `ContextItem.provider_id`, `source_id`, `source_version` | `provider_id` is a registered PAS capability matching `^[a-z][a-z0-9_.-]{1,80}$`. The two private registrations use the installed source IDs as capability IDs. `source_id` preserves the exact installation, and `source_version` encodes the wire schema and source revision as a length-checked JSON tuple. |
| Kind and exact opaque ref | Typed domain payload, `item_id`, non-empty `source_refs` | Encode source, app, workspace, owner, kind, ref, and revision as a reversible JSON tuple within the existing `item_id` bounds. The record source reference and entity reference carry that binding. |
| Read/search for context | `ContextOperation="search"` and registered `ContextOperationSpec` | `fetch` is adapter implementation detail, not a new model-visible operation; if another existing operation is selected it must be declared and permitted by the app policy |
| Domain-owned itinerary/workout fact | `ContextSourceClass="domain_current"`, `authority="authoritative"` | Only for the original owning app's authoritative source; never label it `client_context` or `external_research` |
| Effective time and source expiry | `observed_at`, `effective_at`, `expires_at` | Require UTC observations and valid intervals. Clamp expiry to the earliest record, source TTL, grant, or installation expiry. |
| Source + PAS field classification | `ContextItem.sensitivity`, complete `field_sensitivity` | Use the most restrictive joined classification; enforce server-owned `ContextFieldPolicy` before constructing item |
| Live PAS grant and source revision | `ContextPermissionDependency` | Set `source_scope` to the owning app/workspace, with a matching `entity_ref` and `source_revision`. Set `permission_id` from the trusted grant, bind grant revision and epoch in `version`, and retain purpose, owner, and nullable `acting_user_id`. The paired cross-application IDs are omitted. The trusted grant binds installation and recipient. |
| Verified request scope | `ContextItem.owner_id`, `application_id`, `workspace_id` | Derive from verified `RequestScope` and app registration. The actor lives on the permission dependency. |

`domain_current` exists in the current category contract. The app registry's `domain_context` sensitivity default is sensitive, but it does not by itself admit a provider: exact operations and fields remain server policy. Same-app scope is mandatory. Existing planner result/byte/token/deadline limits and assembler provenance/history behavior remain authoritative. Never write source facts automatically to durable memory. No extra model call is permitted for source preparation.

## Recipient-bound snapshot export

The synthetic composition implements preview and confirmation as two explicit owner actions. Its successful result is a typed in-process value. A stale second selection denies the entire confirmation, including any earlier successful fetch. Files, downloads, imports, routes, and external delivery remain outside the synthetic scope.

`export_snapshot` is PAS-orchestrated and separate from source reads. Normative sequence: authenticate owner and actor → select exact recipient and purpose → check a live source/field grant explicitly naming that recipient → re-fetch each exact selected source/ref/revision under a recipient-bound delegation → recheck source revision, installation, membership, grant and expiry → compute the shortest dependency expiry → redact and render preview → require explicit owner confirmation bound to recipient, purpose, fields and content digest → disclose one all-or-nothing snapshot → emit a content-free audit receipt. If any item is stale, unauthorized, unavailable, or too large, reject the whole snapshot. A runtime grant alone fails export to ChatGPT or a manual recipient; a separate grant is required.

PAS request to begin a preview (confirmation is a separate owner action bound to the resulting preview digest):

```json
{"schema_version":"app-context-v1","operation":"export_snapshot","recipient":"manual-chatgpt","purpose":"answer-context","selections":[{"source_id":"itinerary-demo","application_id":"travel-demo","workspace_id":"trip-a","record_ref":"r01","source_revision":"v7","fields":["title","platform"]}]}
```

Snapshot shape is `schema_version`, opaque random `snapshot_id`, exact `recipient`, `purpose`, `created_at`, `expires_at`, and typed `records` with source/ref/revision, permitted projection, and dependencies. No bearer token, delegation, credential, raw grant secret, or authority-bearing URL appears in the snapshot or filename. Any download handle is owner-bound and short-lived; snapshot ID alone is not authorization. Reuse/import inside PAS rechecks live grants, revisions and expiry. A manual/offline recipient can keep copied text after expiry or revocation; PAS cannot revoke that copy. State this before confirmation.

Synthetic export response shape (a ChatGPT/manual grant must be separately present; this example does not authorize one):

```json
{"schema_version":"app-context-v1","snapshot_id":"snap-opaque-1","recipient":"manual-chatgpt","purpose":"answer-context","created_at":"2030-01-02T09:00:00Z","expires_at":"2030-01-02T09:05:00Z","records":[{"source_id":"itinerary-demo","record_ref":"r01","source_revision":"v7","record_kind":"itinerary_leg","content_projection":{"title":"Demo shuttle A","platform":"Blue"},"dependency":{"grant_id":"grant-manual-a","grant_epoch":1,"application_id":"travel-demo","workspace_id":"trip-a"}}]}
```

Source changes are checked at preparation and immediately before issuing a single-use, short-lived send permit. The verified host performs its final possible check; durable send-start is fenced. A change observed before send denies. A midstream change stops further PAS-controlled output and reuse, but cannot recall transmitted bytes. There is a residual check-to-wire race; live-data admission remains blocked until measured and accepted. An ambiguous send is unknown/terminal-pending-reconciliation, with no automatic retry or fallback. Restore must consult current independent revocation state before reopening reads.

See [architecture](architecture.md), [ChatGPT boundaries](chatgpt-integration-boundaries.md), and [delivery and acceptance](delivery-and-acceptance.md).

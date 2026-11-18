# Application context provider v1

**DRAFT / NOT DEPLOYED.** This proposed protocol connects independent apps using data messages. It requires no PAS imports. Negotiate the literal schema below before reading. Reject unknown request fields, unsupported versions and unknown security classifications. Optional response annotations can be added within v1 only if ignoring them preserves authority and meaning. New required fields, grant semantics or ordering require a new version.

## Parties and access checks

The operator binds a service identity and pinned HTTPS origin to one application, approved workspace authority, projection schema and source registration. Authenticate both ends with installation-bound service credentials. Operator enrollment requires a verified administrator. Disable redirects and caller-selected URLs. The authenticated app may describe its installed source. Enabling an installation grants zero record access.

PAS derives the owner from verified issuer/subject and resolves the calling application from its client registration and the workspace from current membership. The owner grants an exact source, kind, field set, purpose, recipient and sensitivity ceiling for that app/workspace, with expiry and a monotonically advancing epoch. An authenticated app service alone cannot speak for an owner. PAS sends the source a short-lived, audience-bound delegation covering that tuple, allowed operation, request digest and expiry. The source validates issuer, audience, operation, current ownership/membership and grant before lookup. No body accepts an owner override. A different app needs its own explicit approved relationship and grant. Default to same-app access.

## Messages

Every request includes `schema_version: app-context-v1`, `operation`, `source_id`, `application_id` and `workspace_id` strings. These are selectors checked against the authenticated binding. All IDs are opaque ASCII identifiers of 1–128 characters. The limits below are proposed ceilings for the synthetic slice.

| Operation | Additional request fields | Successful result |
| --- | --- | --- |
| register | Operator supplies installation ID, service identity, pinned origin, allowed kind/field schemas, maximum sensitivity and TTL in seconds | Source ID and installation revision. Re-registering identical metadata is idempotent. Any material change increments the installation epoch and invalidates dependent handles. |
| describe | None | Installation revision, array of supported read operations, kind/field schemas, sensitivity ceilings, TTL and page limits, constrained by installed policy |
| search | One allowed kind, literal query (0–256 characters), limit (1–10), optional opaque cursor | Object with `items` (authorized ref, revision, kind, effective time and permitted title per item), watermark string and nullable `next_cursor`. Empty authorized search returns an empty list. |
| fetch | Exact opaque record_ref and source_revision from search | One projected record in the shape below. A changed revision requires a fresh search. |
| export_snapshot | Owner-initiated list of 1–10 exact ref/revision pairs, declared purpose and named recipient | Versioned object with `snapshot_id`, `recipient`, `purpose`, `expires_at` and `records` containing only approved projected fields and dependencies. Use the earliest dependency expiry. Reject the whole export if any record fails. |

For register, the operator assigns the source ID before installation. Use the following operation-specific JSON keys in addition to the common envelope. A question mark denotes an optional key. Schema and policy IDs resolve only in the operator's immutable catalog.

| Operation | Request keys and types | Result keys and types |
| --- | --- | --- |
| register | installation_id, service_identity, origin, projection_schema_id, max_sensitivity (strings), max_ttl_seconds (positive integer) | source_id, installation_revision (strings) |
| describe | No additional keys | installation_revision, projection_schema_id, max_sensitivity (strings), operations (string array), max_ttl_seconds, max_page_size (positive integers) |
| search | record_kind, query, cursor? (strings), limit (integer) | items (array of objects with record_ref, source_revision, record_kind, effective_at and title strings), watermark (string), next_cursor (string or null) |
| fetch | record_ref, source_revision (strings) | Record object below |
| export_snapshot | selections (array of objects with record_ref and source_revision strings), purpose, recipient (strings) | schema_version, snapshot_id, recipient, purpose, expires_at (strings), records (record array) |

The schema catalog defines field types, redaction rules and bounds for each kind. PAS orchestrates export through authorized fetches. Before returning a snapshot, verify that the named recipient and purpose match the export grant. An adapter must never accept the caller's field list as authority.

Bind each cursor to the verified tuple, filter, watermark, sort position, grant epoch and expiry using server-side state or authenticated encoding. Order by effective time descending then opaque ref ascending. Reject a changed watermark or epoch. Cap a turn at one search page and at most ten exact fetches, each within a shared deadline. A consumer explicitly requests another page as a new read.

```json
{"schema_version":"app-context-v1","operation":"fetch","source_id":"itinerary-demo","application_id":"travel-demo","workspace_id":"trip-a","record_ref":"r01","source_revision":"v7"}
```

## Two synthetic fetch responses

```json
{
  "schema_version":"app-context-v1","source_id":"itinerary-demo","application_id":"travel-demo","workspace_id":"trip-a",
  "record_ref":"r01","record_kind":"itinerary_leg","source_revision":"v7",
  "observed_at":"2030-01-02T09:00:00Z","effective_at":"2030-01-02T08:00:00Z","expires_at":"2030-01-02T09:05:00Z",
  "sensitivity":"personal","provenance":{"installation_revision":"i3","authority":"itinerary-demo"},
  "grants_or_permission_dependency":{"grant_id":"g-trip","epoch":4,"purpose":"answer","recipient":"runtime-a"},
  "content_projection":{"title":"Demo shuttle","platform":"Blue"}
}
```

```json
{
  "schema_version":"app-context-v1","source_id":"workout-demo","application_id":"fitness-demo","workspace_id":"gym-b",
  "record_ref":"r01","record_kind":"workout","source_revision":"v2",
  "observed_at":"2030-01-02T09:00:00Z","effective_at":"2030-01-01T10:00:00Z","expires_at":"2030-01-02T09:02:00Z",
  "sensitivity":"sensitive","provenance":{"installation_revision":"i8","authority":"workout-demo"},
  "grants_or_permission_dependency":{"grant_id":"g-gym","epoch":9,"purpose":"answer","recipient":"runtime-b"},
  "content_projection":{"title":"Fixture session","duration_minutes":20}
}
```

The source issues ref, immutable revision, kind, provenance and typed projection. Reusing a ref across sources is valid. Every material edit changes the revision. PAS matches all IDs and the authority/installation revision against the installation. The source sets UTC observation, domain-effective and expiry timestamps. Reject a future observation, missing time, expired record or excessive age. A future itinerary event can have a future effective time. Effective expiry is the minimum of source expiry, observation plus operator TTL, and grant/installation validity. PAS takes the highest of field, source and operator sensitivity in the ordered set public, personal, sensitive, restricted. Unknown fields or excessive sensitivity deny the projection. The source echoes the grant dependency from verified delegation. PAS independently checks it against live grant state, including actor, app, workspace and allowed fields.

Enforce an 8 KiB UTF-8 record limit before decoding projection text. Validate field types and byte limits against the installed schema. Treat all projected strings as quoted data. For identical authorized inputs, deduplicate by source/ref/revision, rank by explicit source selection then effective time descending and source/ref ascending. Use the shared assembler and its counter on the serialized projection including citations. Admit whole records that fit the remaining context after required turns and output reserve. Skip oversize records with a content-free reason. Return zero optional records if the budget is exhausted. No per-record model call or automatic durable memory write.

## Failure and reuse

Return a stable code plus opaque request ID. Use `invalid_request` (400), `unauthenticated` (401), uniform `unavailable` (404 for missing or unauthorized records), `stale_dependency` (409 for an authorized stale revision/cursor), `limit_exceeded` (413), `rate_limited` (429) or `source_unavailable` (503). Never expose another tenant's existence in errors, counts or timing-dependent pagination metadata. Retry bounded reads only after reauthorization and within deadline.

Revalidate installation, grant epoch, membership, revision and expiry at search, fetch, packaging and final disclosure, including model send. Stop on change or inability to verify. Drop pending output and invalidate dependent handles, packages and summaries. Restore requires current independent revocation state before reopening reads. PAS-controlled snapshot import requires a live recheck of all dependencies, recipient and expiry. Manual export requires a separate explicit disclosure grant, owner preview and field redaction. Offline recipients can retain copied text beyond revocation or expiry. See [architecture](architecture.md) and [acceptance](delivery-and-acceptance.md).

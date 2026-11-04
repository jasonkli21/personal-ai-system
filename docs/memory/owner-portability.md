# Owner memory controls and portability

The browser entry point is `/memory`. Set `MEMORY_USER_MANAGEMENT_ENABLED=true`
and `MEMORY_PORTABILITY_ENABLED=true` on the frontend and backend for a
development deployment using verified owner identity. Both default to false.
Backend user management also requires `MEMORY_ENABLED=true` and
`MEMORY_KNOWLEDGE_SELECTION_ENABLED=true`. Profile portability can operate
without an installed project host. The private API requires recent Google authentication from the builtin UI
audience and authorized party. External consumer credentials and development
identity are denied. Profile operations also require the standalone application
and no workspace.

Project inspection still requires schema-3 selection and an installed source
resolver, lease and project mapping. It checks up to 32 recent candidates and
returns up to eight eligible records for one project. The panel shows provenance,
revision, observation time, expiry and lifecycle state. A truncated result covers
only the checked subset. A missing host yields a content-free unavailable status.
Review and rejection only disposition unverified suggestions. Confirm forget
explicitly and retain the original operation UUID and body to reconcile a lost
response. Verified knowledge revision requires a trusted replacement issuer and
remains unavailable.

## Profile and file operations

Load profile controls to negotiate capabilities. Save one of the four explicit
preferences or unset it. Each successful edit advances the canonical profile
revision and invalidates existing grants, including when a value changes away
and back. Manage fresh grants with the existing [profile consent API](../platform-independence/profile-sharing-v1.md).
That API shows the exact destination, purpose, expiry and copy warning.

The following routes use the private `/v1/memory/control/portability` prefix.

| Request | Result |
| --- | --- |
| `GET /capabilities` | Supported owner operations and the download warning |
| `GET /profile` | Canonical explicit profile and revision |
| `POST /profile` | Profile update with required integer `expected_revision` and the existing bounded `fields` and `remove_fields` lists |
| `GET /export` | Fresh JSON attachment with up to four explicit profile fields |
| `POST /import-preview` | Per-field duplicate, conflict or quarantine dispositions, with commit unavailable |

A stale correction returns 409. After a timeout or storage error, reload the
profile to see the current revision and value before submitting another change.
The canonical writer performs the revision check in its existing owner-fenced
transaction. No correction grants sharing authority.

Export v1 is a closed UTF-8 JSON object identified by
`format: "personal-ai-memory-export/v1"`. It records the opaque server owner ID,
standalone app with null workspace and project, explicit profile kind and
canonical source, revision, creation time and field observation times with
user-set provenance. `expires_at` and `embedding` are null. The
`owner_copy_only` restriction carries no grant. `complete: true` refers to the
bounded explicit profile snapshot. Project knowledge, pending suggestions, grant
material, conversation data, and provider data are outside the format. Records
are sorted by field name. The lowercase SHA-256 `digest` covers the object
without the digest key using lexicographically sorted JSON keys, ASCII escapes
and no whitespace between tokens. The digest checks integrity only. Copies leave
Personal AI and cannot be recalled.

Send the JSON file bytes directly with `Content-Type: application/json`. The
body limit is 8 KiB, with a two-second receive budget and eight in-flight
portability requests per backend process. Unknown schema, duplicate keys or
fields, malformed values, scope metadata outside the supported format, and
digest mismatch return a content-free 422. Oversize returns 413. A foreign
owner claim is quarantined. An old or future profile revision conflicts. A
matching value and observation can be marked already current. Other
well-formed content is quarantined because source authority cannot be proven.
Preview retains no file, writes no knowledge and never invokes inference.

Disable `MEMORY_PORTABILITY_ENABLED` on the proxy and backend to stop this
adapter. Canonical profile data, revocations, forget receipts and tombstones
must be retained. Leave features disabled after a restore until current
owner-deletion and revocation authority has been reconciled. Deployed release
ordering and physical erasure require separate verification.

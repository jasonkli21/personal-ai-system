# PI-4 profile consent API and operations

2026-10-30. Local implementation candidate, pending separate independent review.
The PI-2 consumer OpenAPI/version is unchanged. These are owner management routes,
not additional external-app capabilities. Browser controls are not delivered;
management is through the documented API using the existing authenticated gateway.

## Authority and consent

`PROFILE_SHARING_ENABLED=false` is the default. An enabled deployment still needs
an affirmative grant for one expressly user-set `preferred_units`, `locale`,
`response_style` or `answer_length`. No inferred records, arbitrary notes, Health,
Finance or app-private memory are shareable. The exact-record memory view reports
`available: false`, `original_source_authority_unavailable`; it performs no reads,
provider calls or embeddings. MEM-3+ remains frozen.

Management requires a verified Google owner with recent upstream authentication,
the builtin UI OAuth audience/authorized party, `personal_ai`, null workspace and
the exact issuer|subject actor. Development identity and external app clients
cannot manage grants. Do not expose this endpoint as a model tool. Recipient
registration, exact workspace membership, operation/field/sensitivity policy and
current owner/client rights are checked separately. Provider privacy, approved
counter, strict-free admission and reservations remain PI-3's independent gates.
A grant does not authorize a provider or make shared data eligible for extraction.

## Owner workflow

1. Read `GET /v1/profile`. Set explicit values with the existing `PUT /v1/profile`,
   then read its `revision`. Value-only PUT remains supported. A nonempty legacy
   `shared_with_applications` list returns **409** `profile_sharing_requires_consent`
   (an unknown legacy destination still returns 422). It creates no consent.
2. Read `GET /v1/profile/shares` with the owner credentials. It returns consent
   `revision`, current `profile_revision`, grant identities, exact recipient and
   actor, value when still bound to the current profile, expiry, revoked/epoch
   state, and the irreversible-disclosure warning. Treat elapsed expiry as denial.
3. Show the user the exact field/value, recipient application/workspace, purpose,
   and expiry before submitting. **Past provider sends cannot be recalled.** The
   API workflow requires the user to review these facts; there is no browser UX
   acceptance claim.
4. Generate and durably retain an operation UUID, grant UUID and the complete
   original request before sending `POST /v1/profile/shares`. Include exact quoted
   `If-Match: "<expected_revision>"`. Example synthetic request:

```json
{
  "operation_id": "11111111-1111-4111-8111-111111111111",
  "operation": "grant",
  "expected_revision": 0,
  "expected_profile_revision": 1,
  "grant_id": "22222222-2222-4222-8222-222222222222",
  "field": "preferred_units",
  "destination": {"application_id": "reading_logbook", "workspace_id": "my-shelf"},
  "purpose": "assist_response",
  "expires_at": "2026-10-31T12:00:00Z"
}
```

The example expiry must be replaced with a future aware UTC time at most 30 days
from submission. UUIDs are owner-generated intent identities, not authorization
or foreign-record handles. Owner/actor/source/value are resolved server-side.
`expected_profile_revision` binds the value the user reviewed; a concurrent edit
conflicts. The response is a content-free receipt: operation UUID, intent digest,
grant UUID, aggregate revision and operation.

5. For revocation, retain the grant's exact field/destination/original profile
   revision/expiry, use `operation: "revoke"`, a new operation UUID and the latest
   consent `expected_revision`/matching header. Revocation works after expiry,
   profile edits, destination removal and capacity exhaustion. Missing/foreign,
   already-revoked and stale targets collapse to a safe conflict. No extension or
   reactivation operation exists. A fresh grant permanently supersedes older
   coverage for the same actor/field/destination; revoking it cannot revive an
   older grant.

Keep tokens and header files outside the repository, with private permissions;
never put user data, tokens or live owner identifiers in examples or logs.

## CAS, retries and unknown outcomes

| Outcome | Meaning / recovery |
| --- | --- |
| 200 receipt | Durable operation observed; GET shares to inspect **current** state |
| Same UUID, identical intent/actor | Original receipt, even after revoke/expiry; never re-applies consent |
| 409 `profile_share_conflict` | Header/revision/target or changed-intent conflict; inspect current state before a new explicit action |
| 409 `profile_share_destination_denied` | No permitted registered destination/policy/membership; no foreign record information |
| 409 `profile_share_capacity` | 32 lifetime grants exhausted; revoke remains available |
| 422 `profile_share_expiry_invalid` or validation error | Invalid bounded request; no write |
| 401 / 403 / 404 | Reauthenticate, client denied, wrong management scope or disabled feature |
| 503 `profile_share_unknown_commit`, timeout or lost ACK | Outcome unknown; reconcile with the **original UUID, header and identical request** |

A stale `If-Match` can accompany an exact original-key replay: the receipt is an
observation of the original transaction. It is not proof of current permission.
Do not silently create a new operation/grant identity after an uncertain outcome.
Refresh authentication while retaining that intent. Read/list storage failures are
safe 503 `storage_unavailable`. No provider is invoked by management or revocation.

## Context and reuse

The standard planner selects a field, the existing provider returns a destination
projection, and the assembler/packer checks the exact dependency before disclosure.
The source remains owner `personal_ai`/null; dependencies bind original source,
actor, destination, purpose, immutable grant/epoch and whole-profile revision/value
fingerprint. The compact prompt contains only the selected user-set preference,
source label and revision. The complete authority graph stays in snapshots/traces.
All model counts still obey the unchanged per-selection/source/global budgets.

Any profile update invalidates all old grants conservatively, including changing
another field or changing a value away and back. Fresh consent is required. Expiry,
revoke, disable, source removal, owner deletion fence, lost membership/client
binding, recipient policy loss or storage failure denies future use. Assistant
answers and summaries inherit dependencies; expired/revoked turns are omitted
from subsequent model input. Counters, summary preparation, provider preparation
and physical reservation recheck current authority. External streaming checks
before each delta and completed-key replay. Original continuation UUIDs/status
remain authoritative; there is no automatic new-key/provider fallback.

Canonical messages and owner history remain unchanged after revocation. Before an
external client receives conversation detail, the service rechecks its current
client/workspace authority and every retained `global_profile` source dependency.
Expired, revoked, disabled, stale-revision, legacy/incomplete or unavailable
authority returns a content-free `409 conversation_source_authority_changed` for
the whole detail response. Fully unattributed assistant records are quarantined
from new external detail responses because their source cannot be classified.
This does not recall a provider send or bytes already delivered. It also cannot
identify profile use in historical assistant text that has neither a profile
source marker nor attributable provenance; deployments must keep those legacy
external histories quarantined until reviewed before enabling profile sharing.

There is still a race between the last check and an external wire operation. No
atomic distributed source lease or production transport-revocation claim is made.

## Storage, upgrade, disable and restore

Migration **032** adds the canonical `profile_consents` owner aggregate, archives
legacy recipient arrays there without converting them to grants, clears those
arrays from active profile JSON, and adds a SQL constraint refusing old allowlist
writes. Old profile values and v1 decoding remain. Profile and consent writes lock
owner deletion authority -> consent namespace -> profile. Native tests exercise
forward migration, old-writer rejection, CAS, transaction rollback, lost ACK and
fenced erasure; these are synthetic local engine checks.

The aggregate retains at most 32 lifetime grants and 64 content-free receipts;
replacement also consumes a lifetime slot. No pruning/reuse of IDs. Expired and
superseded grants remain non-authorizing audit/replay evidence. Payloads are capped
at 128 KiB. Long-lived churn beyond this conservative cap needs a separately
reviewed capacity design. Existing MEM tombstone/forget receipt blockers remain.
Account export inventories include profile/consent/archive/receipts. The explicit
operator `PostgresGlobalProfileRepository.purge_owner` deletes both record families
only under a retained irreversible owner deletion fence. No automatic account
eraser, replica/backup erasure or cloud recovery is added.

Drain old readers/writers first; migrate with sharing disabled; deploy strict
readers/revalidators everywhere; validate a synthetic owner; only then opt in.
Mixed old binaries with active cached profile data are unsupported. The constraint
blocks old writers, but cannot patch already-running old readers. Rollback sets
`PROFILE_SHARING_ENABLED=false` and drains in-flight work while retaining migration,
strict dependency-denial readers, grant epochs, receipts and deletion fences.
Disabling stops future reuse of persisted dependencies as well as new selection.
A kill switch is not permanent user revocation: explicitly revoke before resuming
if old unexpired consent must not resume. Never down-migrate to restore allowlists.

After restoring a backup, leave sharing **disabled** until all post-backup
revocations, owner deletion fences and original-key receipts have been reconciled.
Restoring a stale database is not proof of non-resurrection. Production restore,
physical erasure, real identity/membership/provider behavior, Linux/Python 3.12,
browser UX and independent PI-0–4 acceptance remain open gates.

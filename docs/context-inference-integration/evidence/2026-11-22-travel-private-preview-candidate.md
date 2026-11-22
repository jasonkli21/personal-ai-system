# Travel private preview candidate · 2026-11-22

A reduced paired run passed the synthetic A/B preview. The normal isolated
applications and disposable PostgreSQL were unavailable. Full paired E1 and
native E2 remain unverified. Integrated dispatch remains `BLOCKED_CONTRACT`.
Live E3 remains `BLOCKED_EXTERNAL`.

| Repository | Revision and scope |
| --- | --- |
| PAS | Candidate working tree based on `15b9801d5ab56107ee122f67a8da761aee3ba9b7` |
| Travel | Clean `77f3c7a1257b6231ca6cbcffb8a93d121372c861` |
| Before the candidate | [Paired contract attempt](2026-11-22-travel-paired-preview-attempt.md) |

The optional Travel contribution uses the installed Travel provider ID, the
shared planner’s server-supplied bounded selection, and the pending message
created after PAS validates the conversation's owner, scope and client
namespace. The route and request schemas stay at private v1. The signed
reverse hop carries the verified human and exact conversation, with a
separate service bearer. Travel selects its own bound trip. The preview uses
an independent PAS read grant, runtime-recipient grant, model-recipient grant,
and one separately consented canonical memory. Typed preview authority
travels with the prepared source snapshot and digest. It leaves Travel's
decimal revision, source ID, fingerprint, observation, sensitivity and ACL
dependency intact. The typed authority has its own grant expiry.

## Observed paired results

| Check | Observation |
| --- | --- |
| Selection and inventory | One owner and client, two fabricated conversations, trips A and B. PAS returned four 200 previews in A/B/A/B order. Each had one Travel source with `trip_title` and `trip_revision`, one canonical PAS memory with `content`, and zero prior turns. The prepared packages contained only their own trip title, revision and memory. The HTTP inventory withheld both titles and the memory text. |
| Reverse hop and provenance | Four signed `current` calls and 16 signed `verify` calls for those four previews. The Travel route returned one v2 record with null workspace. PAS retained the original source ID, decimal revisions `0` and `9`, fingerprints, timestamps, sensitivity and field classifications, and Travel permission version. Each verify projected only the original decimal revision. Snapshot JSON round-tripped the private attestation, missing attestation and changed fingerprint failed validation, and the snapshot could not revalidate outside its preview binding. |
| Fail-closed checks | Removing any one of the three PAS source/recipient grants, substituting a grant for the other conversation, or removing the memory's model grant denied the preview before a Travel call. A malformed response revision failed. A revision change between read and verify returned 409 from Travel, and an ACL change returned 404. PAS denied both previews and still admitted trip B. An unknown PAS conversation, wrong authorized party or audience, forwarded identity, and extra request field were also denied. |
| History and delivery | The shared history projection and automatic chat filter excluded a turn marked with the private source snapshot. The new target rejected continuation before replay or delivery. The runtime delivery sentinel saw zero calls. The socket audit saw zero outbound attempts. |

Both HTTP boundaries ran as reduced in-process ASGI compositions. The PAS
candidate used its actual private route and middleware function bodies, plan
and chat services, context planner/assembler and canonical memory reader,
with an in-memory conversation, memory and lifecycle store. It used local
Ed25519 test credentials, in-memory grants, fixture request dependencies, an
inline worker substitute, and inert cloud import shims. The pinned Travel
private route and delegation verifier ran with a separate locally verified
service bearer and the unchanged v2 projector. A SQLite lookup substituted
for the active identity, private binding and SQLAlchemy ACL/revision path.
The test used no Google verification services, real provider or model,
charges, local runtime release, or live credentials. Its continuation denial
does not exercise a send fence or recovery.

The [one-way diagnostics](2026-11-22-travel-paired-preview-attempt.md) also
reran successfully. They retain the unconfigured PAS denial and verify
five permitted and ten denied reverse-authentication cases. An isolated
schema comparison against the PAS baseline confirmed that the ordinary
`ContextSourceSnapshot` validation and serialization JSON Schemas are
identical. The twin Travel reservation fixtures still have SHA-256
`5e5aa6e161c4d8461a3098eeaafb098e8661b78a0a87de2e85f63df2b937076d`.
The private PAS v1 wire schema still has SHA-256
`40e4c1e3515fab057488042c791e298e15f2942008fe1ffba597a9020b700081`.

## Reproduction and remaining checks

Run from the PAS root with the pinned synthetic checkouts on the import path.

```sh
PYTHONPATH=backend/src:reference-apps/src:sdk/python/src:/tmp/r4travel/backend/src \
  python backend/scripts/travel_plan_preview_check.py /tmp/r4travel

PYTHONPATH=backend/src:reference-apps/src:sdk/python/src:/tmp/r4travel/backend/src \
  python backend/scripts/travel_plan_paired_diagnostics.py
```

| Check | Result |
| --- | --- |
| Paired and one-way diagnostics above, changed Python compilation, platform dependency inventory, whitespace | Passed in the reduced environment. |
| Normal isolated PAS and Travel app imports | Blocked by missing Google libraries and SQLAlchemy, respectively. Both locked offline UV syncs stopped at uncached wheels. |
| Focused PAS pytest and Travel `backend/tests/test_private_plan_postgres.py` | Pytest unavailable. No test DSN or PostgreSQL executables were available, and Docker inventory could not access its socket. No migrations, native ACL store or restore cases ran. |
| `make backend-lint`, `make hermetic-capability-check` | Ruff and urllib3 were unavailable, respectively. |
| `make naming-policy-check` | Two inherited findings in the earlier handoff document. |
| `make source-contract-check` | The locked environment lacked Pydantic. The system-Python check stopped on modified files bound by the existing locks. Frozen manifests were left intact. |
| `UV_OFFLINE=1 UV_CACHE_DIR=/tmp/r4-pas-cache make consumer-contract-check` and `make sdk-install-check` with the same environment | Hatchling unavailable. The direct consumer schema generator also stopped on the missing Google imports. |

Independent acceptance still needs both normally assembled applications,
a disposable migrated Travel PostgreSQL store, and scoped current authority
stores in the exercised configuration. A local coordination lock cannot order
Travel SQL ACL writes against a remote send. This preview candidate provides no
evidence for provider transport, continuation recovery, or that distributed
ordering.

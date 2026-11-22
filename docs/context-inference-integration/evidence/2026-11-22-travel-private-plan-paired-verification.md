# Travel private plan paired verification · 2026-11-22

The reduced paired preview returned the correct data for two conversations and two fabricated trips belonging to one owner. G1 remains `BLOCKED_CONTRACT`. Travel ADR 0017 is proposed, normal isolated app composition and native authority stores were unavailable, and the PAS source contract check is red. Integrated confirmation, dispatch and recovery remain gated. There is no paired E1 acceptance or new E2 witness. Live E3 remains `BLOCKED_EXTERNAL`.

## Paired manifest

| Field | Recorded value |
| --- | --- |
| PAS base and result under test | `f5f60fb6f871dad9d59071f2ebf91ecb8e1c69f1` → `31ceb21a614a622fc1edb841eabac0e46cdc3dc5`. Candidate code uses a typed Travel preview adapter. The unchanged PAS control denied the preview. |
| Travel base and result under test | `61a708b257cb9862bc415ce8a7151201489d3472` → `77f3c7a1257b6231ca6cbcffb8a93d121372c861`. Preview-only source binding and journal. |
| Ancestry and worktrees | Both base-to-result ancestry checks exited 0. Both worktrees started clean. The expanded reduced assertions ran as a PAS test-only working-tree change over the result above. The Travel tree remained clean. |
| Shared seam | [Proposed Travel ADR 0017 at the tested revision](https://github.com/jasonkli21/travel-app/blob/77f3c7a1257b6231ca6cbcffb8a93d121372c861/docs/decisions/0017-private-plan-preview-source.md). SHA-256 `8e0ff9d9b7b091a88763b93832850c81a847e4870a0777f97261e165b274e826`. Joint approval pending. |
| Wire contracts | `travel-context-read-v2`, PAS private `application-plan/v1`, consumer `1.2.0`, SDK extension `0.2.0`. Ordinary SDK `0.1.0` compatibility is a predecessor witness. |
| Fixture and schema bytes | Twin `backend/tests/fixtures/travel-context-read-v2-reservation.json` fixtures share SHA-256 `5e5aa6e161c4d8461a3098eeaafb098e8661b78a0a87de2e85f63df2b937076d`. PAS private schema SHA-256 `40e4c1e3515fab057488042c791e298e15f2942008fe1ffba597a9020b700081`. |
| Executed journey | Reduced ASGI routes exercised synthetic signature verification, seeded conversations A/B and one canonical memory. Four interleaved A/B/A/B previews, then expiry, scope, bounds, revocation, and continuation denials. Create, confirm, fake send, canonical status and detail as an integrated journey were unexecuted. |
| Delivery and disclosure counters | Runtime delivery sentinel calls 0, runtime/provider plaintext before confirmation 0 package bytes, fake provider POSTs 0 because the send path stayed closed. Reduced preview and one-way diagnostics each audited zero outbound socket attempts. Wrong-trip and raw inventory disclosures were 0 for the observed A/B and authentication cases. Cross-owner full-journey disclosure is unmeasured. |
| Store and process inventory | In-process PAS and Travel ASGI compositions. PAS conversation, memory, memory lifecycle and grants used in-memory repositories. The Travel ACL and binding lookup used an in-memory SQLite substitute, with the real v2 projector. Supplemental journal contention used two threads with separate SQLite connections and a reopened repository. No migrated PostgreSQL, DynamoDB, real runtime, independent OS delivery process or restore ran. |
| Independent reviews | No signed PAS, Travel or paired acceptance review of this pair. No Luna remediation result. All matrix rows retain independent disposition `PENDING`. |
| Live eligibility | `BLOCKED_EXTERNAL`. No live identity, partner SIWC, provider credential, provider trip data, charge, or model credit was used. |

## Command results

`Preview` and `Diagnostics` ran from PAS with the paired checkouts on the import path and a stripped environment. The ordinary app dependencies remain unavailable. [Candidate evidence and composition details](2026-11-22-travel-private-preview-candidate.md) · [First paired attempt](2026-11-22-travel-paired-preview-attempt.md)

```sh
(
  set -eu
  travel=/tmp/r4travel
  pas_result=31ceb21a614a622fc1edb841eabac0e46cdc3dc5
  git merge-base --is-ancestor "$pas_result" HEAD
  git diff --quiet "$pas_result" -- backend/src reference-apps/src sdk/python/src
  test "$(git -C "$travel" rev-parse HEAD)" = 77f3c7a1257b6231ca6cbcffb8a93d121372c861
  test -z "$(git -C "$travel" status --porcelain)"
  imports="backend/src:reference-apps/src:sdk/python/src:$travel/backend/src"
  env -i PATH="$PATH" PYTHONPATH="$imports" \
    python -B backend/scripts/travel_plan_preview_check.py "$travel"
  env -i PATH="$PATH" PYTHONPATH="$imports" \
    python -B backend/scripts/travel_plan_paired_diagnostics.py
)
```

| Evidence | Command and exit | Observation |
| --- | --- | --- |
| Preview | First Python command above, 0 | Four 200 responses, four signed `current` calls and 16 signed `verify` calls for the positive interleave. Correct destination, expiry, projected fields and prepared content. Oversized source, malformed revision, stale revision and changed ACL deny. Continuation 422 before runtime delivery. Zero outbound socket attempts. |
| Diagnostics | Second Python command above, 0 | Four 422 unconfigured previews. PAS denied the unknown conversation, wrong authorized party, wrong audience, forwarded token and extra field. The PAS signer and Travel verifier admitted five bound assertions and denied ten invalid combinations. Zero outbound socket attempts. |
| Delegation | Travel root, `env -i PATH="$PATH" PYTHONPATH=backend/src python -B -m unittest discover -s backend/tests -p test_private_plan_delegation.py -v`, 0 | Five tests passed using distinct local Ed25519 service and human keys. No Google verification or ACL store. |
| Journal | Local diagnostic `/tmp/r4-travel-journal-probe.py`, with `PYTHONPATH=/tmp/r4travel/backend/src:/tmp/r4travel/backend/tests`, 0 | Ran the pinned journal control flow with SQLite replacing the binding and locking repository. One reservation and one concurrent join. On reopening, the ambiguous preview offered only its original key. Changed key/body yielded 409, foreign owner 404, changed trip revision quarantined the lookup. This ad hoc diagnostic is supplemental. The repository reproduction target is Travel's pinned [native journal test](https://github.com/jasonkli21/travel-app/blob/77f3c7a1257b6231ca6cbcffb8a93d121372c861/backend/tests/test_private_plan_postgres.py). |
| Travel backend | `UV_OFFLINE=1 UV_CACHE_DIR=/tmp/r4-travel-cache make -k backend-lint backend-typecheck backend-test`, 2 | Locked install failed on uncached wheels before lint, mypy or pytest. Native Travel plan tests remain `NOT_RUN`. |
| Travel frontend | `COREPACK_ENABLE_NETWORK=0 make frontend-check`, 2 with clean Corepack cache | Offline pnpm unavailable. Direct `npm test` from `frontend` exited 1 after 15/17 test files passed. React and TypeScript were absent for the two remaining files. Automatic sidecar policy, booking panel, comparison and Shopping recovery, proposals, and workspace helper checks passed. |
| Travel docs | `make docs-check`, 0 | 233 local links checked across 73 files. |
| PAS locked checks | `UV_OFFLINE=1 UV_CACHE_DIR=/tmp/r4-pas-cache LITELLM_LOCAL_MODEL_COST_MAP=True make -k backend-lint naming-policy-check sdk-install-check source-contract-check consumer-contract-check hermetic-capability-check`, 2 | Ruff unavailable, naming reported two inherited R0 handoff findings, Hatchling blocked SDK/consumer builds, Pydantic unavailable to the locked source checker, urllib3 missing for hermetic suites, and adaptive conformance reported changed source. |
| PAS current-source probe | `PYTHONPATH=backend/src:reference-apps/src:sdk/python/src python -B backend/scripts/source_contract_check.py --check`, 1 | Planning and offline information handling source digests disagree with their locks. The same command in a clean detached clone at the PAS base also exited 1. The base already differed from both locks. The result adds builder and provider mismatches and changes the already mismatched authority and history digests. Frozen files stayed intact. |
| PAS direct consumer check | `PYTHONPATH=backend/src:reference-apps/src:sdk/python/src python -B backend/scripts/consumer_contract_check.py --check`, 1 | Normal app import stopped at missing Google runtime libraries. |
| Process and native readiness | `python -m pytest --version`, 1. `unshare -Urn true`, 1. `command -v postgres initdb pg_ctl psql`, 1 | No pytest or PostgreSQL executables detected, no disposable DSN available, and the namespace operation could not open `/proc/self/uid_map`. Prior Docker socket unavailability is recorded in the candidate. PAS focused private-plan, source authority, named PostgreSQL and R3 TLS tests remain `NOT_RUN`. |
| Compatibility bytes | `sha256sum` of the ADR, schema and twin fixtures, 0. Path-scoped `git diff --exit-code` across each base-to-result range, 0 | PAS platform contracts, SDK, signed grants, evaluation files and Travel fixture bytes had no diff. Travel frontend, clients, migration 0016 and fixture bytes had no diff. Runtime compatibility remains open. |
| Ledger structure | Local Markdown check, 0 | 40 unique acceptance IDs, eight mixed-tier splits and all relative links in this ledger and the current-state entry verified. |
| Whitespace | `git diff --check` and `git diff --check <base>..HEAD` on both checkouts, 0 | Candidate and recorded worktree checks pass. |

## Acceptance ledger

All rows use the paired revisions and independent disposition in the manifest. **Observed** means the scoped check ran, **inspection** means the pinned code or evidence was read, and **predecessor** refers to prior evidence awaiting a rerun on the pair. These are implementer observations. `NOT_RUN` identifies unexecuted required witnesses. E2 rows name the missing stores individually.

| ID | Owner | Tier and disposition | Expected witness | Observed or open evidence |
| --- | --- | --- | --- | --- |
| R4-01 | Shared | Provenance · documented | Exact base/results, ancestry, clean test inputs, hashes and review scope. | Manifest records ancestry, dirty test-only follow-up and hashes. All signed review scopes are pending. |
| R4-02 | Shared | Gates · documented | Preserve inherited independent, native and external gates. | R0 Travel partner blocked, browser SIWC unverified, R1 adoption review pending, R2-A implementation review pending, R2-B externally blocked, R3-A 21 synthetic cases and four scoped PostgreSQL cases pending independent acceptance. DynamoDB, native source/memory/journal and whole-host recovery remain open. [Predecessor ledger](2026-11-21-private-runtime-ordering.md) · [Coordinated fixture](2026-11-21-coordinated-private-runtime.md) · [Eligibility](../runtime-r0/R0-eligibility-matrix.md) |
| R4-03 | Both | E1 · `BLOCKED_CONTRACT` | Approved server-owned one-trip binding based on verified app/client/human and private conversation. | Preview observed A/B/A/B from server lookups and a null workspace. SQLite substituted the binding path. ADR 0017 remains proposed and native composition is unavailable. |
| R4-04 | Both | E1 · observed, acceptance pending | Strict private body rejects automatic source selectors before delivery. | Diagnostics extra `entity_refs` 422, no delivery. The private schema and existing Travel frontend wire bytes match their bases. |
| R4-05 | PAS | E1 · partial | Direct verified issuer/subject/audience/effective authorized party and registered active owner before source access. | Diagnostics verified local Ed25519 tokens and denied wrong authorized party, audience and missing conversation. The verifier and owner lookup were test substitutes. Normal Google/owner composition is open. |
| R4-06 | Travel | E1 · observed, acceptance pending | Forwarded human token with hosted service bearer cannot enter the private direct bearer path. | Diagnostics rejected the forwarded header with 401 even on an otherwise valid synthetic direct bearer. Travel hosted client bytes are unchanged. |
| R4-06 | Travel | E3 · `BLOCKED_EXTERNAL` | Approved deployed private direct bearer ingress. | No deployed ingress or Google token validation ran. |
| R4-07 | Both | E1 · partial | Independently authenticate service and scoped human delegation, then recheck owner, trip and revision. | Preview, Diagnostics and Delegation exercised two separate signatures, invalid combinations and revision/ACL denials. Normal authority store unavailable. |
| R4-07 | Both | E3 · `BLOCKED_EXTERNAL` | Live PAS-to-Travel IAM and delegation in approved deployment. | No deployed IAM, service account or source transport exercised. |
| R4-08 | Travel | E1 · partial | Exact binding before preview and rechecked for status/detail/continue, denying foreign owner/trip/lane. | Preview followed SQLite bindings. Journal denied a foreign owner and stale revision. Linked status/detail/continue and restored bindings are unexecuted. |
| R4-09 | Both | E1 · observed, acceptance pending | Travel application with null workspace through the paired source and prepared turn. | Preview asserted `travel` and null workspace on all signed source requests and prepared packages. Trip A/B stayed in Travel's domain selector. |
| R4-10 | PAS | E1 · partial | Removed/expired/rotated clients and same-email distinct subject cause zero foreign reads or sends. | Diagnostics denied wrong client authorized party. Preview rejected cross-conversation, missing and expired grants before Travel. Native client rotation/revocation and same-email subject isolation remain open. |
| R4-11 | Travel | E1 · partial | One current trip through v2 projector with live TripService ACL/revision and bounded verify. | Preview exercised real v2 projector and reduced signed route with SQLite ACL/revision. Verify returned only original trip revision. Native TripService was unavailable. |
| R4-12 | Travel | E1 · partial | Minimum exact trip fields, separately scoped reservations and no private documents or codes. | Preview disclosed only projected title/revision internally and withheld raw source and memory from the inventory. Matching reservation fixture bytes preserved. Explicit reservation-scope and legacy independent regressions are open. |
| R4-13 | Both | E1 · partial | Preserve original provenance, deny stale source revision or membership. | Preview checked ID, fingerprint, decimal revision, observation, sensitivity, ACL version and typed expiry. Revision changed between read/verify gave Travel 409, ACL change gave 404, and PAS denied both. Native ownership and branch behavior remain open. |
| R4-13 | Both | E2 · `NOT_RUN` | Migrated Travel SQL revision/ACL checks using the actual store. | Travel locked suite could not start. No disposable PostgreSQL instance. |
| R4-14 | Both | E1 · partial | Authority rechecked at preview, release, pre-send and each outward/replay boundary. | Preview evidenced fail-closed source and grant changes. Continuation denied before delivery. Release, exact pre-send and replay ordering were unexecuted. |
| R4-15 | PAS | E1 · partial | Separate current source, runtime and model grants, with correct memory binding and no Shopping consent escalation. | Preview denied missing, swapped or expired individual source grants and a missing memory model grant before Travel. Native grants, rotation and paired Shopping negative remain open. |
| R4-16 | PAS | E1 · observed, acceptance pending | One canonical, consented PAS memory with origin/lifecycle. | Preview seeded the existing in-memory canonical repositories, validated the memory through the canonical reader, and found only its content in each prepared package. |
| R4-17 | Both | E1 · partial | Missing, unconsented or forgotten memory or expired model grant returns no-AI. | Preview denied missing or expired model consent and an absent canonical memory record without Travel I/O or a send. A forgotten canonical record remains unexecuted. |
| R4-18 | Both | E1 · partial | Inventory matches prepared/delivered fields, history and destination, with no raw leak and 8,192-byte bound. | Preview compared exact destination and three inventory categories, inspected prepared content, and checked inventory byte length. Delivery match and the oversize publication negative remain unexecuted. |
| R4-19 | Both | E1 · partial | Exact original UUID, digest, branch, source and recipient bound to 45-second confirmation, modified or expired intent denied. | Preview matched the issued confirmation and expiry to the prepared record and checked the 45-second bound. Continuation was denied by preview-only policy. Confirmation mutation and claim tests remain unexecuted. |
| R4-20 | Both | E1 · partial | Source 4,096B, prepared 8,192B, memory 1,024B and model 100B, with over-budget denial. | Preview denied a syntactically valid 4,097-byte source response, checked actual prepared size and its 100-byte/character output limit. Memory oversize and prepared/output boundary sends remain unexecuted. |
| R4-21 | Travel | E1 · partial | Independent default-off backend, frontend and PAS private host. | Preview asserts no Travel reverse route when disabled, on the reduced app using the same mount function. Travel frontend has no plan panel. Ordinary assembled PAS/Travel and full default-off check remain open. |
| R4-21 | Travel | E3 · `BLOCKED_EXTERNAL` | Gated deployment and unavailable live experience by default. | No hosted gate or deployment reviewed. |
| R4-22 | Travel | E1 · partial | Manual domain flows survive absent PAS, disconnected user and 404/503. | Travel frontend helper tests passed while PAS was absent. Manual CRUD and native browser/backend failure journeys were unexecuted. |
| R4-23 | Shared | E1 · `BLOCKED_CONTRACT` | Fabricated successful send and negatives, zero external requests and no credits. | Preview and Diagnostics measured zero outbound socket attempts and zero delivery. Positive integrated fake dispatch withheld at G1. |
| R4-23 | Shared | E3 · `BLOCKED_EXTERNAL` | Explicitly eligible live R4-B transport. | No SIWC, credits or production transport used. |
| R4-24 | Travel | E1 · inspection | Original create UUID/title committed before POST, replay under exact binding with no duplicate. | ADR and pinned journal capture scope/key/title. Paired previews preseeded conversations. Lost create and recovery remained unexecuted. |
| R4-24 | Travel | E2 · `NOT_RUN` | Durable native create key, binding and lost-create recovery. | No disposable migrated Travel PostgreSQL. |
| R4-25 | Travel | E1 · partial | Immutable continuation intent, original key, concurrent body conflict, same-key recovery. | Journal diagnostic exercised preview reservation, matching join, digest-only persistence and changed key/body 409. A confirmed continuation or any POST was unexecuted. |
| R4-25 | Travel | E2 · `NOT_RUN` | Native journal persistence and competing confirmation. | SQLite substitute has no native SQLAlchemy/PostgreSQL locking, continue or restore evidence. |
| R4-26 | Both | E1 · partial | Interrupted SSE/timeout/429/unknown reconciles only same-key authorized status and matching detail. | Journal diagnostic returned an original-key selector after preview uncertainty and no selector for stale/other key. Paired GET/continuation cases unexecuted. Predecessor installed HTTP fixture exercised lost continue and original-key lookups. [Predecessor report](2026-11-21-private-application-inference.md) |
| R4-27 | Both | E1 · `BLOCKED_CONTRACT` | Receiving fake transport sees one POST on success and at most one after crash/restore, with zero on denied turns. | Preview delivery sentinel stayed at zero. Fake send and recovery withheld at G1. Prior PAS fixture belongs to the predecessor. |
| R4-27 | Both | E2 · `NOT_RUN` | Independent send fence across PAS/Travel restore and competing recovery. | No paired native restore, receipt rollback or cross-store fence continuity measured. |
| R4-28 | Both | E1 · `NOT_RUN` | Strict UTF-8/JSON/SSE and bounded terminal with matching canonical status. | The paired suite stopped at preview and continuation denial. Existing SDK parser and installed HTTP test are the next replay targets. |
| R4-29 | PAS | E1 · `BLOCKED_CONTRACT` | Source/owner/client rights gate every delta, terminal, status, detail and replay after revocation. | Preview excluded its typed source snapshot from ordinary history and rejected continuation before release. Paired stream and canonical content were never created. |
| R4-30 | Travel | E1 · `NOT_RUN` | Accessible plan panel, expiry/error/unknown states and no AI domain writes. | Travel has no plan panel in this pair. Legacy frontend checks alone provide no plan UI evidence. |
| R4-31 | Both | E1 · partial | Isolate two owners with same email, cross-trip/client, rotated session and same original UUID. | Preview interleaved two trips using the same original UUID and denied a wrong client. Journal denied a foreign owner in the substitute. Full two-owner/same-email and rotated-session cases remain open. |
| R4-32 | Travel | E2 · `NOT_RUN` | Disposable PostgreSQL ACL, anchors, journal CAS, two processes/tabs, erasure, export, backup and restore. | Native tests and stores unavailable. Pinned Travel native test file covers a subset and has not been executed here. |
| R4-33 | PAS | E1 · `NOT_RUN` | Coordinated two-process TLS tests both revocation orderings and zero pre-send fake POST where revoke wins. | New run blocked by Linux namespace permission and missing pytest. Prior result scopes ordering to participating synthetic writers. [Coordinated fixture](2026-11-21-coordinated-private-runtime.md) |
| R4-34 | Shared | Architecture · blocker documented | Prove ordering over production writers or leave distributed race open. | PAS fixture authority uses a shared POSIX lock only for participating synthetic writers. Travel SQL mutations use their own transactions and native PAS source and memory writers do not participate. Revalidation leaves a race between the final read and a physical remote send. This blocks E3. [Coordinated fixture](2026-11-21-coordinated-private-runtime.md) |
| R4-35 | PAS | E1 · `NOT_RUN` | Native Linux fixture exercises TLS peers, signed binding, frames, timeout and pre-confirm plaintext. | Namespace permission and pytest unavailable. Reduced ASGI calls used local signatures and no TLS delivery. |
| R4-36 | PAS | E2 · `NOT_RUN` | Four named native PAS PostgreSQL cases plus separately identified DynamoDB, source, memory/grant/owner, journal and host restore. | Only predecessor four scoped PostgreSQL routing/principal tests exist as historical evidence. No current native process or store exercised. |
| R4-37 | Travel | Compatibility · partial | Preserve automatic assistant, standalone features, Shopping, v2 and migration 0016. | Client, frontend, fixture and migration bytes unchanged in the base/result diff. Fifteen direct frontend test files passed. Full native and legacy backend regressions remain open. |
| R4-38 | PAS | Compatibility · blocked | Preserve ordinary/standalone APIs, SDK 0.1.0/0.2.0, v1.2.0, signed bytes and frozen locks. | Checked contract/SDK/signed-grant/evaluation bytes, and Preview enforced ordinary history separation. SDK installation and consumer app generation blocked by dependencies. Source locks are intact and source check fails. |
| R4-39 | Shared | Evidence · documented | Pin runs, fixtures, sends and scoped review results. | Manifest and command ledger record the exercised pair. No-code PAS outcome is nonconformant, integrated sends are gated, native E2 unexecuted and separate PAS, Travel and paired sign-offs pending. |
| R4-40 | Shared | E3 · `BLOCKED_EXTERNAL` | Approved app/host/custody, entitlement and no-credit authority, deployed IAM/recovery, trusted terminal and billing. | No live app, host or provider entitlement evidence. Live path remains closed. [Eligibility](../runtime-r0/R0-eligibility-matrix.md) |

## Gate disposition

| Gate | Result |
| --- | --- |
| G0 source and review baseline | Documented with inherited red gates and independent acceptance pending. |
| G1 chosen-trip and security ADR | `BLOCKED_CONTRACT`. Joint review of ADR 0017, normally assembled authority paths and reviewed source-lock disposition are outstanding. |
| G2 PAS contribution | Partial reduced preview evidence. Full paired contribution blocked. |
| G3 Travel backend, UI and journal | Partial preview-only binding and journal recovery evidence. Integrated confirmation, UI and native verification remain open. |
| G4 paired E1 | `BLOCKED_CONTRACT`. No successful integrated fake send and no independent review. |
| G5 native E2 | `NOT_RUN` on the paired candidate. |
| G6 live E3 | `NO_GO` / `BLOCKED_EXTERNAL`. |

# Phase 25.2 architecture and rewrite-risk review

Date: 2026-10-10. This is the local implementation model; it does not establish deployed authorization or live provider acceptance.

## Architectural model and ownership

`ChatTurnService` retains conversation orchestration and now exposes its existing preparation and compare-and-swap transition seams to `ExternalTurnService`. Normal streaming, external preparation, and continuation use the same planner, context assembler, scope, branch selection, preparation lease, and message repositories. An external service coordinates proof issuance/import, never provider IO or domain mutation. `auth.dispatch_grants` owns asymmetric signing/verification; registered application policy owns disclosure decisions; Phase 18 owns exact endpoint definitions; the Phase 25.1 bridge owns credentials, account-specific discovery, provider IO, and physical-send receipts. P19 still owns automatic physical-attempt/quota accounting.

DynamoDB messages are the sole canonical store for prepared reservations, terminal text, producer attribution, and completion identity. The assistant placeholder embeds `TurnReservation`; there is no external-turn table, sidecar conversation, attribution ledger, or new reservation repository. The existing conversation revision and preparation lease arbitrate writes. Safe coarse subscription usage is retained in the existing local registration, beside its connection revision, and projected through `SafeConnection`. It is never a P19 bucket, a cloud account identity, or billing evidence. Reauthorization/account changes invalidate pairing and clear coarse usage; normalized auth failures advance the revision and require local recovery.

Reusable credentials remain protected locally. Cloud code sees a connection UUID/revision and paired caller/runtime UUIDs only. A future authenticated issuer must validate those bindings through authoritative integrations; client labels are not sufficient. There is no permissive `ExternalTurnAuthority` implementation or managed HTTP composition. Default application policy permits no external execution modes. No API selector, external website automation, provider fallback, or domain Apply is enabled.

## Generic seams extended

- The existing branch/preparation transaction remains authoritative. `MessageRepository.update_status` gains a generic expected-message/replacement CAS and branch fingerprint check. DynamoDB commits the message payload, conversation revision, and catalog together; branch validation is bracketed by revision reads, and the condition binds the exact old message payload.
- Messages gain optional `TurnAttribution` and embedded `TurnReservation`. Old records remain readable. `pending` distinguishes prepared external work from an observed stream. Streaming remains the ordinary generation state. Both block competing preparation and participate in stale recovery.
- Existing context source/entity/grant pointer contracts move to a dependency-light module and are re-exported at their original import path. `ContextItem.authority_snapshot()` retains exact provider/source/item/version, disclosure fingerprint, scope, references, dependencies, and expiry without copying payload bodies. Reservations and attribution retain these snapshots for final rechecks.
- `ExecutionChoice` and `ContinuationRequest` are provider-neutral values. Candidate message IDs narrow complete active turns; they never authorize or force inclusion. Historical producer origin does not influence orchestration. Automatic continuation uses the configured existing lane; external continuation uses the shared preparation seam.
- P18 `ProviderAccessPolicy` adds auth/selection/runtime/discovery/automation/history metadata. Access-bearing definitions use frozen schema 3; profiles without the new metadata preserve schema-2 encoding and historical identity. Released migration 022 is untouched. ChatGPT-plan profiles require the explicit local subscription policy and cannot enter automatic admission, even through malformed cost/free configuration.

These are additive extensions. The only foundational extraction moves neutral pointer types to remove a dependency cycle; their fields and old imports are preserved. No persistence ownership changes.

## State, identity, replay, and effects

| Transition | Canonical semantics |
| --- | --- |
| Prepare | Append the user under the existing lease, authorize/narrow/assemble context, then append a pending assistant with a frozen reservation. Preparation failure releases only its own lease; the user may remain persisted. |
| Connected dispatch | Recheck current authority, sensitivity, expiry, exact profile body/version, caller/runtime/connection binding, and branch. Sign, then CAS prepared→dispatched before returning the proof. |
| Manual import | Requires explicit import and the exact matching reservation/fingerprint. There is no dispatch grant, connection, account assertion, or provider IO. Prepared→completed shares the canonical message transition. |
| Connected completion | Requires dispatched, successful neutral completion, matching producer/connection, bounds, current policy/source authority, exact profile, and branch. Dispatched→completed. Browser/bridge facts remain client-reported. |
| Abandon/recover | Prepared→cancelled; dispatched→unknown. Content is empty. Expired reservations recover through the existing stale-turn mechanism. Partial external output is never persisted. |
| Duplicate completion | Same completion digest returns the existing completed message after current authorization. Changed content/provenance/usage/latency conflicts. A lost committed-write response is recoverable by this replay. |
| Stale/superseded/foreign | Cannot dispatch or finalize. Branch change loses CAS; foreign scope/owner is rejected; superseded history remains stored with unchanged attribution. |

`dispatched` is a **cloud grant-issuance fence**, not a claim that the server observed a physical send. Grant loss or abandonment cannot prove no-send; no hidden retry or proof reissue is provided. The bridge's existing pre-send/send-start/terminal receipt remains physical transport authority. Proof IDs are incidental; the signed package's scoped reservation is the physical-send identity. A new explicit request uses a new reservation; there is no automatic account/provider switch or recovery send.

Reservation/message IDs derive from owner/app/workspace/conversation and the caller's idempotency UUID. The request digest detects changed preparation inputs. The branch digest uses immutable active message IDs/content/state. Connected fingerprints use the existing version-2 package canonicalization, including exact profile/deployment/serializer/runtime. Manual fingerprints bind scope, branch, authority, policy, declarations, exact messages, and output bound. Prompt packages are transient; repeated preparation never recreates a sendable package. After restart, inspect/finalize/cancel the canonical reservation or explicitly prepare a fresh request. Completed text and its digest remain canonical. No pruning drops uncertain fences while retaining the owning conversation.

Producer facts and context facts are separate. Manual provider/model labels are optional user declarations, model verification is false, and latency/usage/account/billing/quota claims are forbidden. Connected external facts are client-reported, including any token counts; usage source/confidence is retained. Ordinary server generation records its own observed adapter identity and latency, retaining estimated-versus-reported usage. Context references and recording time are server facts. Neither origin nor later transformation grants content factual authority or domain write rights.

External preparation requires the existing conservative local byte estimator and disables summary refresh. It never sends a count or summary to an unrelated model. Existing compatible summaries still undergo the shared pipeline and their source IDs enter authority rechecks. Counts remain explicitly estimated; endpoint limits and disclosure policy remain hard checks. No exact ChatGPT token-count claim is made.

## Alternatives and downstream composition

Rejected alternatives: an external/manual conversation store; Postgres reservations spanning the DynamoDB branch boundary; per-provider continuation handlers; browser completion as server/billing evidence; manual imports through authenticated generation metadata; unrelated provider count/summary calls; reissuing lost dispatch proofs; retroactively relabelling producer history; and changing old endpoint-definition serialization merely to add metadata.

Phases 25.3 and 25.4 consume these shared request/package/transition and recovery seams for UI and registered host integration. Phase 30 must connect canonical membership/source-grant authority and derived revocation to the required authority interface. Phase 31 consumes provenance as input to a separately validated proposal, never as domain mutation authority. Registered providers and applications can use the same mechanism without a core provider/domain branch; only profile validation contains the ChatGPT subscription invariant.

## Independent review challenges

Challenge the authority integration most aggressively: it must validate actual principal membership, paired caller/runtime/connection revision, fetched source versions/fingerprints, every derived history/summary dependency, and grant freshness through the dispatch/finalization boundary. The current callback and synthetic tests do not establish an atomic cross-store revocation fence, immutable Postgres policy/source history, or deployed authorization. Those existing P14/P15/P30 gates remain open, and no HTTP issuer is composed.

Also challenge real DynamoDB CAS/catalog/race behavior, exact endpoint serialization/count assumptions, signing-key custody/rotation, expiration and clock behavior, grant-delivery loss, deliberate conservative recovery after proof issuance, source snapshot coverage for memory/derived artifacts, and whether later UI preserves the client-reported/user-declared labels. The pending/message and reservation states describe different levels of the same lifecycle; the conversation repository is the sole mutable authority for both. Live bridge interoperability, billing eligibility, native browser transport, and distribution remain Phase 25.1 acceptance gaps. These limitations must be resolved before enabling production execution, rather than patched around by another workflow.

# Phase 25.3 implementation guide — Shared AI continuation sidecar

Phase 25.3 adds a shared continuation sidecar over existing conversation, context,
provider-profile, and local-bridge contracts. The interface is implemented locally.
Production authorization, DynamoDB transaction behavior, and connected ChatGPT
acceptance remain open; see the [implementation evidence](phase-25-3-implementation-evidence.md)
and [prerequisite decision review](phase-25-3-readiness-review-2026-10-10.md).

## Ownership and request flow

| Concern | Owner and extension seam |
| --- | --- |
| Automatic continuation | `ChatTurnService.continue_turn` and the existing SSE transport. The route accepts `ContinuationRequest`; no automatic provider picker or alternate generation service was added. |
| Context planning and assembly | Existing planner, registered providers, `ContextAssembler`, builder, token budget, and application policy. `ExternalTurnService.prepare` requests local estimated counting and disables unrelated summary generation. Candidate message IDs only narrow active completed turns. |
| Context preview | A transient `ContextPackage` is built from the actual assembled messages and manifest. It includes actual bounded selection/exclusion counts, category/sensitivity/authority summaries, policy and current grant versions, estimated count, expiry, sensitivity ceiling, and package fingerprint. Raw source IDs and reference URIs are omitted from the summary. The package is not persisted. |
| Authorization | `get_external_turn_service` composes the authenticated principal, request scope, conversation/message repositories, workspace authorizer, and shared context permission revalidator into `PrincipalBoundExternalTurnAuthority`. It checks owner/conversation/workspace binding, active completed history, source expiry and present permission dependencies at preparation/dispatch/finalization/replay snapshots. P15 end-to-end derived-source and immutable-version acceptance remains open. |
| Reservations and completed turns | The P25.2 reservation remains embedded in the canonical assistant message and uses the existing repository compare-and-swap transition. The same canonical conversation/message store owns completion text, idempotency digest, provider attribution and context references. No sidecar history or import store exists. |
| Connected execution | Only current enabled P18 `CHATGPT_PLAN` profiles with explicit-only selection, user-local credentials, account-specific discovery, approved data-use policy, streaming/context bounds, no hosted conversation state, and a configured grant signer appear in options. The local bridge still owns credentials, pairing and physical-send receipts. |
| Manual execution | `manual_external` uses the same prepared reservation and finalizer, but needs no provider profile, signer, bridge, or credential. Copy is explicit; import is explicit; optional provider/model labels are validated and stored as user-declared and unverified. |
| Browser state | Same-origin cloud requests use the existing authenticated Next.js proxy. The direct loopback client uses only `http://127.0.0.1:8765`, `credentials: omit`, and a transient `X-Bridge-Authorization` caller capability. It sends no ordinary Authorization header, cookies, or provider credentials. |

## Routes and UI

The backend mounts the following under `/v1/conversations`:

- `GET /execution-options` returns automatic plus only policy-allowed external modes and currently admissible profiles.
- `POST /{conversation_id}/continue` streams automatic continuation through `ChatTurnService.continue_turn` and the existing SSE lifecycle.
- `POST /{conversation_id}/external-turns/prepare` returns the shared `ContextPackage`, exact prepared messages, fingerprint, reservation identity, and a copyable manual prompt when selected.
- `POST .../{message_id}/dispatch` revalidates the canonical package/profile/authority and returns the short-lived signed grant.
- `POST .../{message_id}/complete` and `/import` finalize connected and manual turns through `ExternalTurnService`.
- `POST .../{message_id}/fail` and `/abandon` record uncertainty or cancel a prepared reservation through the existing state machine.

External API responses set `Cache-Control: no-store`. The frontend sidecar is a
desktop right drawer and a mobile bottom sheet. It offers a continuation instruction,
a checkbox to narrow or exclude the selected completed turn, a bounded context
inspector, automatic continuation, manual copy/import, and connected ChatGPT controls
when server policy/profile/signer allow them. Completed answers expose Copy and a
non-authoritative “Use in message draft” action. There is no authoritative Apply.
The drawer moves focus into its dialog, traps keyboard Tab navigation, closes on Escape,
and restores focus to the launch button; its mobile layout is a bottom sheet. Local
bridge recovery uses the existing safe recovery projection to display account usage
management and local `reauth`/`enable-usage` instructions. The browser never runs
those operator actions.

Connected bridge output is displayed transiently while streaming and is persisted
only after a terminal success is passed to the canonical finalizer. A failed or
canceled dispatched request is marked unknown; it is not silently retried. A
completed bridge response can retry the finalizer with the same text without sending
again. If a local account/model disappears, refresh discards the prepared reservation
and requires a new preparation. Server-side source/policy/profile rechecks remain
authoritative if the context changes between prepare and completion.

## Configuration and operational boundaries

Manual mode is available under the default Personal AI context policy and does not
depend on the local ChatGPT bridge. Other built-in domain policies leave external
execution modes empty. Connected mode remains hidden unless an approved explicit P18
`CHATGPT_PLAN` profile and the following server signer facts are configured. The
connected lane rejects other P18 execution modes until their own local transport
contract exists; it does not branch on provider names in shared orchestration.

- `EXTERNAL_DISPATCH_GRANT_ISSUER`
- `EXTERNAL_DISPATCH_GRANT_KEY_ID`
- `EXTERNAL_DISPATCH_GRANT_PRIVATE_KEY` (unpadded base64url Ed25519 private key)

Keep the private key in a protected local environment file or Secret Manager and
pin its matching public key/issuer in the local bridge configuration out of band.
The repository does not ship a key, and configuring a signer alone does not establish
ChatGPT plan-only billing or hosted browser transport. The local bridge's own
compatibility gates, exact origin pairing, caller expiry, account/model revision,
credential echo protection, proof validation, and single-send receipt remain active.

## Preserved boundaries and deviation

No provider-name branch was added to generic execution orchestration. The ChatGPT UI
adapter filters generic P18 options to the runtime it can speak; the registry and
external-turn service remain profile-driven. The automatic path remains the existing
Gemini workflow, and connected ChatGPT is excluded from automatic routing/P19 quotas.
Manual text re-enters only as a conversation response; it does not gain domain write
rights or Phase 31 Apply behavior. Previous attribution is immutable.

The user explicitly directed implementation to proceed despite the P15/P25.2
prerequisite discrepancy. The new authority is scoped and fail-closed for owner,
workspace and permission facts available in the existing interfaces, but it is not a
replacement for complete Phase 15 acceptance. The previous P25.2 architecture's
production gate, immutable policy/source references, derived-history revocation, and
real DynamoDB transaction/race verification remain open. Do not report production
authorization, cloud issuance, provider billing, or browser loopback acceptance as
passed based on the local tests.

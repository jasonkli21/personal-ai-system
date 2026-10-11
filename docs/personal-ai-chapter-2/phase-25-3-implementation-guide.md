# Phase 25.3 implementation guide — Shared AI continuation sidecar

Phase 25.3 adds a shared continuation sidecar over existing conversation, context,
provider-profile, and local-bridge contracts. External modes remain unavailable by
default behind `EXTERNAL_TURN_ACCEPTANCE_ENABLED=false`. The gate must remain closed
until the Phase 15 authority and Phase 25.2 DynamoDB acceptance conditions are met.
Local fixture coverage does not establish those gates; see the
[implementation evidence](phase-25-3-implementation-evidence.md) and
[prerequisite decision review](phase-25-3-readiness-review-2026-10-10.md).

## Ownership and request flow

| Concern | Owner and extension seam |
| --- | --- |
| Automatic continuation | `ChatTurnService.continue_turn` and the existing SSE transport. The route accepts `ContinuationRequest`; no automatic provider picker or alternate generation service was added. |
| Context planning and assembly | Existing planner, registered providers, `ContextAssembler`, builder, token budget, and application policy. `get_external_context_assembler` clones the production assembler with the same planner/provider/policy/builder seams, an `EstimatedTokenCounter`, and no summarizer. External preparation excludes memory retrieval because its embedding adapter can make a remote call. User source-class exclusions narrow the shared planner; they cannot force inclusion. |
| Preflight preview | `POST /{conversation_id}/external-turns/preview` returns a bounded planner projection before reservation. It reads candidate history for authorization and runs no retrieval, token counter, summary, model, or reservation operation. It is advisory; canonical preparation replans and reauthorizes. |
| Prepared package | A transient `ContextPackage` is built from the actual assembled messages and manifest. It includes direct history and summary-derived history counts, bounded selection/exclusion categories, sensitivity/authority summaries, policy and current grant versions, estimated count, expiry, and package fingerprint. Raw source IDs and reference URIs are omitted from summaries. The package is not persisted. |
| Authorization | `get_external_turn_service` composes the authenticated principal, request scope, conversation/message repositories, a typed workspace-authorizer dependency, and the shared context permission revalidator into `PrincipalBoundExternalTurnAuthority`. The default workspace authority denies membership. Every external disclosure route checks the acceptance gate before resolving repositories; the service also checks it during composition. The gate exists because Phase 15 derived-source/revocation and immutable-version acceptance is incomplete. |
| Reservations and completed turns | The P25.2 reservation remains embedded in the canonical assistant message and uses the existing repository compare-and-swap transition. The same canonical conversation/message store owns completion text, idempotency digest, provider attribution and context references. No sidecar history or import store exists. |
| Connected execution | Routing owns the endpoint registry and static explicit-selection projection. Eligible profiles carry a registered `external_transport_id`; the shared controller resolves a typed local transport adapter. The ChatGPT bridge is the first adapter. Profiles still require explicit-only selection, user-local credentials, account-specific discovery, approved data-use policy, streaming/context bounds, no hosted conversation state, and a configured grant signer. The local runtime owns credentials, pairing and physical-send receipts. |
| Manual execution | `manual_external` uses the same prepared reservation and finalizer, but needs no provider profile, signer, bridge, or credential. Copy is explicit; import is explicit; optional provider/model labels are validated and stored as user-declared and unverified. |
| Browser state | The sidecar receives a provider-neutral application/workspace scope and passes it through every API request. Same-origin cloud requests use the existing authenticated Next.js proxy. A registered local transport adapter supplies its loopback origin; requests use `credentials: omit` and a transient `X-Bridge-Authorization` caller capability. No ordinary Authorization header, cookies, or provider credentials are sent to loopback. |

## Routes and UI

The backend mounts the following under `/v1/conversations`. The external router is
registered before the dynamic `/{conversation_id}` conversation route so the static
execution-options resource is reachable in the composed application:

- `GET /execution-options` returns automatic plus only policy-allowed external modes and currently admissible profiles.
- `POST /{conversation_id}/external-turns/preview` and `GET /{conversation_id}/external-turns/requests/{idempotency_key}` provide planner-only preview and bounded canonical reconciliation. A prepared result can be abandoned by idempotency key without reconstructing prompt text.
- `POST /{conversation_id}/continue` streams automatic continuation through `ChatTurnService.continue_turn` and the existing SSE lifecycle.
- `POST /{conversation_id}/external-turns/prepare` returns the shared `ContextPackage`, exact prepared messages, fingerprint, reservation identity, and a copyable manual prompt when selected.
- `POST .../{message_id}/dispatch` revalidates the canonical package/profile/authority and returns the short-lived signed grant.
- `POST .../{message_id}/complete` and `/import` finalize connected and manual turns through `ExternalTurnService`.
- `POST .../{message_id}/fail` and `/abandon` record uncertainty or cancel a prepared reservation through the existing state machine.

All external-turn operations other than execution-options return a safe 404 while
the acceptance gate is closed, before repository dependencies resolve. External API
responses set `Cache-Control: no-store`. The frontend sidecar is a
desktop right drawer and a mobile bottom sheet. It offers a continuation instruction,
a checkbox to narrow candidate history, planner source-class omission controls, a
planner-only preview with explicit review, automatic continuation, manual copy/import,
and connected controls when the acceptance gate, server policy/profile/signer, and a
registered local transport adapter allow them. It then requires review of the exact
prepared package. Completed answers expose Copy and a
non-authoritative “Use in message draft” action. There is no authoritative Apply.
The drawer moves focus into its dialog, traps keyboard Tab navigation, closes on Escape,
and restores focus to the launch button; its mobile layout is a bottom sheet. Local
bridge recovery uses the existing safe recovery projection to display account usage
management and local `reauth`/`enable-usage` instructions. The browser never runs
those operator actions.

Connected bridge deltas are projected onto the canonical pending assistant message by
the shared chat reducer; they remain ephemeral and are cleared on interruption. Output
is persisted only after a terminal success is passed to the canonical finalizer. A failed or
canceled dispatched request is marked unknown; it is not silently retried. A
completed bridge response can retry the finalizer with the same text without sending
again. If a local account/model disappears, refresh discards the prepared reservation
and requires a new preparation. Server-side source/policy/profile rechecks remain
authoritative if the context changes between prepare and completion.

## Configuration and operational boundaries

External modes remain unavailable unless `EXTERNAL_TURN_ACCEPTANCE_ENABLED=true` is
set after the Phase 15 and Phase 25.2 hard gates have been accepted. With the gate
closed, `GET /execution-options` returns only automatic and external-turn operations
return 404. The environment flag is a release gate, not evidence that the prerequisites
passed. Built-in domain policies also remain deny-by-default. Connected options require
an approved explicit P18 profile with a registered transport adapter and the following
server signer facts.

- `EXTERNAL_DISPATCH_GRANT_ISSUER`
- `EXTERNAL_DISPATCH_GRANT_KEY_ID`
- `EXTERNAL_DISPATCH_GRANT_PRIVATE_KEY` (unpadded base64url Ed25519 private key)

Partial or malformed signer configuration fails Settings validation with a safe
diagnostic; an entirely unconfigured signer remains intentionally disabled. Keep the
private key in a protected local environment file or Secret Manager and
pin its matching public key/issuer in the local bridge configuration out of band.
The repository does not ship a key, and configuring a signer alone does not establish
ChatGPT plan-only billing or hosted browser transport. The local bridge's own
compatibility gates, exact origin pairing, caller expiry, account/model revision,
credential echo protection, proof validation, and single-send receipt remain active.

## Preserved boundaries and deviation

No provider-name branch was added to generic backend execution orchestration. The
shared controller resolves registered `external_transport_id` adapters; ChatGPT is
the first adapter and a synthetic second adapter exercises the same contract. The
endpoint registry remains owned by routing, not usage accounting. The automatic path remains the existing
Gemini workflow, and connected ChatGPT is excluded from automatic routing/P19 quotas.
Manual text re-enters only as a conversation response; it does not gain domain write
rights or Phase 31 Apply behavior. Previous attribution is immutable.

The new authority is scoped for facts available in the current interfaces, but it is
not a replacement for complete Phase 15 acceptance. The code therefore defaults to a
closed external-turn gate. Immutable policy/source references, derived-history
revocation, workspace membership, and real DynamoDB transaction/race verification
remain open. Do not enable external modes or report production authorization, cloud
issuance, provider billing, or browser loopback acceptance as passed based on local
tests.

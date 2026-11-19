# Shared application service integration

The private test composition uses one PAS ASGI process, one application registry and the normal conversation handlers. Travel and Fitness each have a separate OAuth client and source installation. A Reading contribution exercises onboarding through the same catalogs. Domain records and application operations stay with the respective apps. They remain usable with the AI entry point disabled. [Verification and release gates](evidence/2026-11-18-shared-application-service.md)

## Select and bind an application

The operator selects trusted application contributions and the corresponding context runtime adapters. Declare the application's workspace requirement in its manifest, register its workspace authority, and install at most one typed, same-app source. The application owns record ACLs, revision and watermark semantics, observation time, and the projection schema. Other apps need their own manifest, client policy entry, workspace authority and typed adapter. The source adapter returns the approved fields as data under the existing context provider contract. [Application registry](../../backend/src/personal_ai/applications/README.md)

Use the [consumer v1.2.0 contract](../platform-independence/consumer-v1.md) and its static OpenAPI subset. The operator supplies an absolute client-policy file, replaced atomically, with schema version `application-client-policy-v1`, at most 16 bindings and at most 32,768 bytes. A binding has `audience`, `authorized_party`, `application_id`, `expires_at` as Unix seconds, and `enabled`. Keep the built-in audience reserved.

Send a direct verified Google human ID token in `Authorization: Bearer` and provide `X-Application-ID`. The service verifies the issuer, expiry, permitted email and hosted domain, and active issuer/subject owner mapping. For a missing `azp`, the effective party is the scalar `aud`. A binding with distinct audience and party therefore requires an explicit matching `azp`. The token establishes the OAuth client context for that human request. Network peer authentication and private ingress are separate deployment gates. The private composition denies task delegation, forwarded identity headers and service-only tokens.

Send `X-Workspace-ID` for a required workspace. For an optional workspace, omission selects the app's separate workspace-free namespace. A supplied workspace always needs a current membership decision from its registered authorizer. The synthetic source contract requires a workspace, so workspace-free conversations may use their own history and explicit user text. App, workspace, owner and actor values supplied in request bodies do not grant access.

## Link, grant and disconnect

Installation registers the source schema and supplies zero grants. A verified owner links an exact client and workspace using the existing synthetic authority plane. The owner separately grants PAS runtime access and disclosure of named fields to the exact synthetic inference recipient. The runtime can search the owning source and fetch an exact record revision. The inference recipient receives only the approved projection. Each grant binds owner, actor, app, workspace, source installation epoch, purpose, recipient, kind, fields, expiry and grant revision. A mutation supplies the current expected revision and a stale mutation loses.

Manual ChatGPT export, ChatGPT-facing MCP, local SIWC and the model recipient use distinct grants. The shared conversation service has no SIWC offer or credential lane. A connected-plan selection is rejected before offer creation, account discovery or dispatch, including when a submitted offer was signed for standalone `personal_ai`. [Standalone local bridge](../../backend/src/personal_ai/local_bridge/README.md)

Revocation denies sourced previews, active output, detail and replay as soon as a recheck observes it. Disconnect in the separate owner-control lane can succeed after loss of domain membership or client access. A disconnected binding loses serving access. Keep independent reconciliation available for previous claims. Revocation cannot recall bytes already delivered to a recipient.

## Journal and recover

Persist the authenticated target, including app, workspace, owner and original OAuth client context, with the original creation key and title **before** create. Before continuation, transactionally save the conversation UUID, continuation key and complete request body in the caller-owned journal. Preserve the journal through timeouts, cancellation and process restart. Delta events are provisional. The SDK requires a matching terminal event, clean stream exhaustion and agreeing canonical status before reporting completion.

On reconnect, read status using the original key and the original valid client authority. A retry of a completed turn uses the exact original body and rechecks current source rights. Changed input conflicts. In-progress, unknown, cancelled, partial and missing observations preserve the original intent. Do not automatically repeat the POST, issue another key or fall back to another endpoint. A new user intent is a separate action. The SDK wheel does not store local application credentials or records. [Python SDK and caller journal example](../../sdk/python/README.md)

A strict-free route must remain eligible under policy, recipient permission and quota. The synthetic service reports `context_no_ai_route` when the route is unavailable, with zero physical sends. The SDK treats a stream error as uncertain. Keep the journal and look up the original key. Show a safe no-AI outcome in the app and keep domain operations available. The shared provider-account quota is independent of each owner's preference and any payer or subscription authority.

Keep legacy direct Travel research, booking extraction, itinerary proposals and comparison within standalone `personal_ai`. Existing records and callers retain their original identities. This opt-in composition introduces no tagging, backfill or migration of those records. [Scope compatibility](../platform-independence/consumer-v1.md)

## Run the fixture

Use the documented offline and disposable PostgreSQL commands in the [verification record](evidence/2026-11-18-shared-application-service.md). The application fixture uses synthetic Google claims, typed in-process sources and a synthetic model transport. PostgreSQL exercises the identity, routing, attempt and quota fences. The conversation and source fixture stores are in memory. The service binds no network listener in the hermetic check. The deployment, installed MCP client, live source, billing and personal-data gates remain open.

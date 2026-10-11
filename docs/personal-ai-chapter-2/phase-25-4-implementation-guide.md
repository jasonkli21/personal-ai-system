# Phase 25.4 implementation guide — shared domain launch hooks

Phase 25.4 composes domain host metadata and action policy with the existing shared
sidecar, planner/provider pipeline, and canonical chat lifecycle. The detailed
[architecture](phase-25-4-architecture.md) records ownership and the data flow;
[implementation evidence](phase-25-4-implementation-evidence.md) records tested
revision, checks, and open gates.

## Implemented contract

| Interface | Behavior |
| --- | --- |
| `ApplicationLaunchContext` | Versioned app/workspace/entity/view/conversation metadata and bounded client context. The server binds it to authenticated request scope and the route conversation. It carries no owner ID and never authorizes a selected entity. |
| `ApplicationSidecarPolicy` | Separate connected/manual disclosure allowlists, per-lane maximum sensitivity, manual-import history reuse, Copy, declared draft target IDs, and reserved future Apply operation IDs. |
| `ContinuationRequest.launch_context` | One source of entity references for automatic, connected, and manual continuation. The reference set participates in the request digest; absent launch metadata preserves the old digest shape. |
| Shared context seam | `ContextPlanner` consumes entity references and source-category narrowing. Shared provider and field authorization plus `ContextAssembler` produce the same typed bounded package. The context source category type/list has one canonical definition. |
| Sidecar actions | The API returns the registered app policy. Manual Copy requires both an allowed manual lane and `copy_allowed`. Draft Insert requires a target declared by the host and allowed by policy. Import returns through the existing completion callback. Apply IDs are descriptive policy metadata only; there is no Apply control or endpoint. |
| Imported history | Shared filtering leaves canonical messages and attribution unchanged while removing manual imported turns and paired prompts from later context when the app policy denies reuse. Filtering precedes summary compatibility so a prior summary cannot reintroduce an excluded turn. |

Application-specific behavior belongs in each app’s provider, manifest, and host
callbacks. The integration contract test uses one synthetic read adapter and the same
policy/orchestration path for `travel`, `shopping`, `finance`, `health`, and a
synthetic fifth application. It does not connect to those applications’ databases.

## Live integration handoff

Before wiring an application’s real source, verify and record these items for that
application and each source operation:

1. Identify the authoritative repository/API, its owner and workspace membership
   check, current revision/version field, source lineage, retention/freshness, and
   supported read and mutation boundaries. Record the exact repository revision and
   API contract reviewed.
2. Implement a registered, typed read provider. It must resolve each selected entity
   reference under the current authenticated principal and workspace; reject foreign,
   stale, deleted, or unsupported references; bound fields/results/bytes/deadlines;
   return source version, observation/freshness, authority, sensitivity, provenance,
   and permission dependencies; and revalidate those dependencies before disclosure.
3. Connect the app’s application/workspace/view and entity IDs to launch context.
   Treat those IDs as hints. Bind them to the server route and authenticated scope;
   never accept owner identity or authorization claims from the browser.
4. Review source-category and field-level policy with the domain owner. Narrow by
   sensitivity and purpose before any source read. Finance and Health must retain
   their stricter policy even when automatic execution is allowed. An app may disable
   manual Copy/disclosure or imported-response reuse without a custom sidecar/auth
   flow.
5. Verify the full execution transport for the selected mode. Connected execution
   continues through the registered provider profile, user-local credential runtime,
   transport adapter, short-lived grant, and existing state machine. Manual mode is
   user-mediated Copy/import and must not automate consumer websites or collect
   credentials. Automatic mode continues through existing routing and context
   preparation.
6. Declare only non-authoritative draft surfaces for Insert. Check that both the
   server policy and host expose the same target ID. Keep authoritative Apply
   unavailable until Phase 31’s typed proposal, validation, confirmation, retry, and
   idempotency contract is complete.
7. Add adapter contract tests for current membership, scope mismatch, source revision
   change, revocation, failure/timeout, bounds, narrowing, summary/history behavior,
   and no domain writes from Copy/import/draft insertion. Then run target-repository,
   browser/transport, concurrency, and deployed-identity checks using that
   application’s actual supported environment.

Phase 15 still lacks complete derived-source/revocation and immutable
policy/source-version acceptance; Phase 25.2’s real DynamoDB transaction, race, and
restart acceptance remains unverified. Therefore the current external-turn gate
stays closed. The current implementation does not claim these live integration
checks have passed.

## Current defaults and repository README review

The built-in Travel/Shopping/Finance/Health source providers remain unavailable and
their external modes remain empty. Finance and Health additionally disallow manual
imported responses as future context. Personal AI declares its composer draft
target. `EXTERNAL_TURN_ACCEPTANCE_ENABLED` remains false by default, so the local
runtime does not expose external prepare/import or connected dispatch. The phase
adds an integration contract, not a new end-user domain capability; no user-visible
README fact changed, so the root README was reviewed and left unchanged.

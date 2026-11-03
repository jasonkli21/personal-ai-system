# ADR 0023 — External consumer and execution authority

Accepted for HXE-0 development on 2026-11-03. Production enablement requires the
evidence in the [gate registry](../platform-independence/pi-cross-phase-gate-registry.md).

## Identity and compatibility

Auth verifies the principal and resolves the owner. Operator client binding
matches the verified audience and effective authorized party to one selected
application. The workspace authority checks current membership. Services
consume the resulting server-bound `AuthenticatedPrincipal` and `RequestScope`
for the owner, actor, application and workspace. Headers, manifest declarations
and launch context can select a requested scope within those constraints.
The domain app owns its records and can select what the user explicitly shares.

The generated [consumer OpenAPI subset](../platform-independence/consumer-v1.openapi.json)
and [consumer rules](../platform-independence/consumer-v1.md) define the
provisional HTTP boundary. The full FastAPI schema describes internal routes too.
The separately versioned `personal_ai.extensions.v1` contract is for selected,
operator-trusted host code. HXE-0 uses the published API version and an operator
capability configuration. These describe compatibility and availability.
Authorization is evaluated afresh for each operation. Unsupported operations
fail closed and remain outside the public surface.

Within a major version, optional fields, new operations and safe error codes may
be added. Clients ignore unknown object fields and future nonterminal events,
retain the original key and complete intent after uncertainty, and reconcile via
the canonical status endpoint. Incompatible field or retry changes require a
new major contract, an explicit migration guide and an announced support window.

## Sources, model operations and retained outputs

PI-4 and PI-5 owners bind source dependencies to verified owner and actor,
destination app and workspace, purpose, source revision, issuer/grant and
expiry. Context resolves authorized sources, accounts for their token cost and
preserves dependency metadata through provider handoff. Source text remains
untrusted data. Local read-only tools execute only closed schemas selected
by the operator and apply the same current rights checks. Derived output,
history, replay, summaries, caches and exports must recheck dependencies on
disclosure and quarantine unknown or stale provenance. Already disclosed bytes
require downstream retention and withdrawal controls.

PI-3 owns provider selection and admission through neutral ports. Generation,
structured generation, summary, token count, embedding, extraction and search
have distinct capability and disclosure requirements. Strict-free eligibility
fails closed without current exact-account, operation, counter and policy
evidence. P19 owns physical attempt reservation and accounting. Ancillary
requests and retries each require their own admitted reservation before a
physical send. An SDK operation key identifies a logical intent and cannot
authorize an additional provider attempt.

Memory owns governed, attributable durable knowledge and authorized forget.
External evidence keeps its own freshness and rights. HXE-0 keeps memory
controls outside the external HTTP subset and exercises the existing MEM-1/2
boundaries with synthetic data.

## Canonical future execution

RE-2 strategies and HXE-3 orchestration should share one run, step, immutable
intent and physical attempt lifecycle. Persist the scoped intent and its key
before admitting or reserving an attempt. Record ordered attempt events for
reservation, dispatch and canonical completion, failure or uncertainty. Bind
replay to the original intent, serialize competing claims, and make a changed
body conflict. Cancellation prevents new work at the next authorized boundary.
A disconnect, canceled caller or lost acknowledgement can leave a remote
effect unknown. Reconcile unknown outcomes against durable and downstream
receipts before authorizing a retry. Replaying terminal results requires current
rights. HXE-0 uses the existing canonical continuation path and introduces no
general execution runtime.

Before live source enablement, an issuer-bound exact-attempt permit must
linearize revoke against physical send. Recheck retained output and export
under current issuer authority. Before relying on restore, keep monotonic
original-key and forget/tombstone authority outside rollback-prone snapshots,
quarantine restored data until reconciliation and prove mixed-age native
restore, two-worker races and erasure. Synthetic conformance covers local
ordering and fail-closed behavior.

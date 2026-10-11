# Phase 25.3 prerequisite discrepancy and implementation decision

Date: 2026-10-10. Initial source audit: `fbae7f5` (`main`, three commits ahead of `origin/main`).

The initial audit found a material discrepancy: the Phase 25.3 plan names Phases 14 and 25.2 as prerequisites, while the accepted Phase 25.2 architecture and guide say not to compose authenticated HTTP/UI until Phase 15 authorization/revocation and DynamoDB transaction verification are complete. The repository still does not have the complete P15 derived-source/revocation authority or engine-level DynamoDB acceptance.

The user then explicitly directed: “Ignore the prerequisite and continue.” Implementation proceeded with a narrowly scoped authenticated composition over existing P18/context/chat/message seams. This decision records the deviation; it does not declare the upstream P15 or P25.2 gates complete.

## Scope and safeguards used

- A request-scoped `PrincipalBoundExternalTurnAuthority` binds the verified principal to the owner and conversation scope, checks workspace membership when a workspace is present, verifies candidate history is completed and active, and revalidates typed permission dependencies and source expiry at each external-turn snapshot.
- External modes are enabled only by the standalone Personal AI application policy. Travel, Shopping, Finance, and Health keep their default empty external-mode policies. Cross-application sharing remains denied.
- Context assembly remains owned by `ChatTurnService` and `ContextAssembler`; the UI can narrow selected conversation turns but cannot authorize inclusion. Context remains transient, bounded, estimated, and redacted in its category summary.
- Turn reservations, text, attribution, idempotency and compare-and-swap remain owned by the canonical conversation/message repositories. No sidecar store was added.
- Manual import remains an explicit user action with user-declared, unverified optional labels. The local ChatGPT capability remains separately gated by approved P18 profile, configured signing key, local pairing, and the P25.1 runtime.
- The browser holds a short-lived local bridge caller capability in page memory and sends no provider credential, cookie or normal Authorization header to loopback. Partial or interrupted output remains transient; a dispatched failure is recorded as unknown.

## Remaining discrepancy and review focus

The composed authority rechecks typed dependencies present in current snapshots, but does not make Phase 15 complete: policy/source records are still code-labeled rather than immutable Postgres references, source/history/summary dependencies are not propagated end-to-end through every derived surface, and an atomic cross-store revocation fence is not established. The Phase 25.2 DynamoDB transaction/race/restart tests remain skipped when no isolated engine is configured. Consequently local tests show contract behavior only; they do not prove production membership, deployed identity, storage CAS, or revocation safety.

The most consequential independent-review questions are whether authorization denies before all source/memory/summary/count reads; whether derived history and grants stay current through dispatch, import, replay and cancellation; whether DynamoDB CAS and reservation transitions behave under real concurrency; whether signer custody/rotation and bridge key pinning are operationally safe; and whether native HTTPS-to-loopback/PNA behavior works on supported browsers. Connected plan-only billing, OAuth/Responses compatibility, distribution approval, cloud identity and domain acceptance also remain unverified.

## Historical audit note

Before the user's instruction to proceed, this file recorded a read-only discrepancy review and no Phase 25.3 implementation. That disposition was superseded by the explicit instruction above. The current implementation and its exact checks are recorded in the [Phase 25.3 guide](phase-25-3-implementation-guide.md) and [evidence](phase-25-3-implementation-evidence.md); the living status remains in [current state](../current-state.md).

# Chat feature

`chat-state.ts` owns reconciliation of the visible conversation branch. The
`app/page.tsx` client coordinates navigation, streaming, and composition through
`frontend/src/lib/api/conversations.ts`; backend services own durable branch
state and model behavior. External-turn requests and DTOs live in
`frontend/src/lib/api/external-turns.ts`, with shared request scope and errors
in `frontend/src/lib/api/common.ts`. The continuation sidecar is imported from
`frontend/src/features/chat/continuation-sidecar/ContinuationSidecar.tsx`.

Component and API regression tests live separately under `frontend/tests`.

The shared continuation sidecar accepts an optional `mutationProposalId` supplied by a host integration. It loads a typed server proposal through `/api/mutations`, reviews domain validation, confirms an exact digest, applies the saved confirmation and reconciles unknown results. Server `apply_available` combines declaration, implementation, policy and current domain authorization. Arbitrary assistant/import text never produces an Apply control. Current domain integrations supply no write adapters or conversion path; their Apply remains unavailable.

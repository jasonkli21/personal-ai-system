# Chat feature

`chat-state.ts` owns reconciliation of the visible conversation branch. The
`app/page.tsx` client coordinates navigation, streaming, and composition through
`frontend/src/lib/api/conversations.ts`; backend services own durable branch
state and model behavior. External-turn requests and DTOs live in
`frontend/src/lib/api/external-turns.ts`, with shared request scope and errors
in `frontend/src/lib/api/common.ts`. The continuation sidecar is imported from
`frontend/src/features/chat/continuation-sidecar/ContinuationSidecar.tsx`.

Component and API regression tests live separately under `frontend/tests`.

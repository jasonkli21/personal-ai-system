# Phase 25.3 implementation evidence

Date: 2026-10-10. Tested checkout: branch `main`, `HEAD` `fbae7f5`, plus the
uncommitted Phase 25.3 working-tree changes. No revision was committed for this
verification. Local verification used Python 3.11.15 through `uv` and the configured
bundled Node runtime. Tests used fixtures and generated in-memory signing keys; no
provider credentials or personal conversation data were used.

## Implemented surfaces

- Added authenticated, no-store execution-options, continuation, context-package,
  manual-import, connected-dispatch/completion, failure, and abandon routes. Same-origin
  frontend calls use the existing authenticated conversation proxy.
- Added request-scoped principal/scope authority using the existing conversation,
  message, workspace-membership, and context-permission seams. It checks active
  completed candidate turns, conversation ownership, source expiry, and current typed
  permission dependencies at preparation and external transitions.
- Reused `ChatTurnService.continue_turn`, the shared planner/assembler/builder and
  token budget, P18 endpoint registry, P25.2 reservation state machine, canonical
  message CAS, attribution, and post-completion lifecycle. No sidecar table, new
  conversation store, or alternate generation path was added.
- Added a bounded transient `ContextPackage` using actual assembled messages and
  manifest summaries. Manual imports use the shared completion path with
  user-declared/unverified labels. Connected output is transient until a successful
  shared finalization; uncertain dispatched output becomes `unknown` and cannot be
  resent under that reservation.
- Added the responsive sidecar with automatic continuation, manual copy/import,
  connected ChatGPT controls, current account/model/usage status, local recovery
  instructions, context inspection, Copy and draft insertion. The UI uses the local
  bridge's existing recovery contract and keyboard-focus behavior. It does not expose
  domain Apply.
- Connected profiles are filtered through P18's explicit-local/account-specific
  policy and `CHATGPT_PLAN` execution mode. The provider-specific bridge adapter stays
  in the sidecar; generic backend orchestration has no provider-name or application-name
  branches. Non-ChatGPT endpoint modes remain unavailable until a matching transport
  contract exists.

## Verification

| Check | Result |
| --- | --- |
| Backend full suite: `UV_CACHE_DIR=/private/tmp/personal-ai-uv-cache uv run python -m pytest` | **1321 passed, 82 skipped**, 2 warnings, 95.54s. The skipped `tests/persistence/test_external_turns.py` engine checks (6) leave P25.2 transaction/race/restart behavior unverified. |
| Backend lint: `UV_CACHE_DIR=/private/tmp/personal-ai-uv-cache uv run ruff check .` | Passed. |
| Backend package: `UV_CACHE_DIR=/private/tmp/personal-ai-uv-cache uv build --no-build-isolation` | Passed; source distribution and wheel built. |
| Frontend tests: `pnpm run test` | **20 files, 103 tests passed.** |
| Frontend lint: `pnpm run lint` | Passed. |
| Frontend type checks: `pnpm run typecheck` | Passed, including application and test projects. |
| Frontend production build: `pnpm run build` | Passed on Next.js 15.5.23. Next reported the repository's existing missing Next ESLint-plugin warning. |
| Context evaluation: `uv run python -m personal_ai.evaluation.context` | **5/5 fixtures passed.** |
| Context planner evaluation: `uv run python -m personal_ai.evaluation.context_planner` | **9/9 fixtures passed.** |
| `git diff --check` | Passed. |

Frontend commands used
`PATH=/Users/jasonkli/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:$PATH`.
Backend `uv` commands used the temporary cache path above because the global cache is
outside the writable workspace. The full tests emitted a Starlette/httpx deprecation
warning and a Pydantic `ReadOnly` warning; neither failed a check. Frontend tests also
reported Vite's CJS Node API deprecation warning. The README was updated because this
phase changes user-visible continuation, manual import, and connected-execution status.

The deterministic UI coverage exercises manual preparation/copy/import without the
bridge, no plan-use permission recovery, model-disappearance package invalidation,
connected cancellation with transient partial text, and switching back to automatic.
Backend coverage exercises authenticated prepare/import, policy and signer gating,
authority/revocation snapshots, branch and expiry checks, idempotent/replayed imports,
uncertain-send fencing, canonical attribution, and endpoint-mode admission.

## Architecture audit and preserved invariants

- Conversation and reservation state remain canonical in the existing message and
  conversation repositories. `ContextPackage` is returned for inspection and is not
  persisted. There is no competing sidecar or manual-import history.
- Automatic inference, context assembly, policy, budget, and persistence remain owned
  by the established chat/context layers. External execution does not bypass the
  shared assembler, policy checks, accounting path for automatic turns, or repository
  CAS transitions.
- Manual and connected provenance remain distinct. Historical attribution is
  immutable. Manual provider/model labels and connected usage/latency are not treated
  as server-verified facts.
- The browser does not receive provider credentials. The local caller capability is
  transient in page memory; the signer key stays server-side. External responses are
  no-store, and partial connected output is not persisted.
- Dispatch uncertainty is terminal for that reservation. A failed/canceled send is
  fenced as unknown, and saving a completed response can retry finalization without
  repeating the external send.
- Standalone Personal AI enables the new explicit modes; built-in domain application
  policies remain deny-by-default. Imported content has no domain mutation authority,
  and Phase 31 Apply remains absent.
- Phase 25.4 can add registered domain launch/sensitivity hooks around this shared
  sidecar and package. Phase 31 remains responsible for typed proposals, domain
  validation, explicit confirmation, and authoritative writes.

## Deviation and unresolved gates

The accepted Phase 25.2 architecture had required complete Phase 15 authority and
DynamoDB engine verification before authenticated HTTP/UI composition. The user
explicitly directed implementation to proceed. The new request-scoped authority is a
bounded local composition over permission dependencies that exist today; this does not
complete Phase 15. Derived history/summary revocation is not propagated end-to-end,
source/policy versions are still code labels rather than immutable Postgres references,
and an atomic revocation fence is not established.

The following remain **unverified**:

- Real DynamoDB Local transaction, race, restart, and recovery behavior; six P25.2
  persistence tests were skipped in the full suite because the external engine was not
  configured.
- Production identity, workspace membership, IAM/private invocation, deployed signer
  custody/rotation, and matching public-key pinning in a live local bridge.
- Live ChatGPT OAuth/Responses compatibility, enforceable plan-only billing, hosted
  distribution approval, and real account/model usage behavior.
- Native HTTPS-to-loopback, browser private-network-access and mixed-content behavior.
- Phase 15 end-to-end derived-source/history revocation and immutable source/policy
  reference acceptance.
- Phase 25.4 real domain integrations and Phase 31 mutation acceptance.

These checks were not run against a cloud account, provider account, live bridge,
production deployment, or local persistence engine. Offline fakes and fixture tests do
not establish those behaviors.

## Independent review focus

Review the order and completeness of authorization before context reads/counting and
again at prepare, dispatch, import, completion, replay, and cancellation; examine
history/summary revocation gaps and the synthetic-vs-engine CAS boundary; verify signer
custody and key pinning assumptions; inspect local capability lifetime and uncertain
send recovery; and check that later domain adapters can extend the shared mode/host
contracts without adding provider or application branches to generic orchestration.

# Phase 25.3 implementation evidence

Date: 2026-10-11. The checked source tree was based on `d758802` plus this fix
session's tracked changes; that exact tree was committed as one follow-on changeset
after verification. Local verification used Python 3.11.15 through `uv`, the configured
bundled Node runtime, deterministic fixtures, and generated in-memory signing keys.
No provider credentials or personal conversation data were used.

## Status

The local Phase 25.3 implementation seams and regressions below are present. Phase
25.3 is **not accepted or production-usable**: authenticated external disclosure and
connected dispatch remain unavailable by default behind
`EXTERNAL_TURN_ACCEPTANCE_ENABLED=false`. Keep that gate closed until Phase 15
pre-retrieval/derived-source revocation acceptance and Phase 25.2 DynamoDB
transaction/race/restart acceptance pass. Setting the flag is not evidence that either
prerequisite passed.

## Implemented and locally verified

- External preparation resolves the production `ChatTurnService` dependency with a
  cloned `ContextAssembler` that retains the shared planner, registered provider
  coordinator, permission revalidator, builder, and policy. The clone uses
  `EstimatedTokenCounter`, no summarizer, and excludes AI-memory retrieval so prepare
  does not call a remote counter, summarizer, embedding adapter, or model. A composed
  `main.app` test exercises this dependency path and fails if remote count/summary
  methods are called.
- `GET /v1/conversations/execution-options` is mounted ahead of the dynamic
  conversation route. A `TestClient(main.app)` regression reaches the handler. When
  the acceptance gate is closed, it returns only automatic mode; external-turn
  operations return 404 before resolving repository dependencies.
- A planner-only preview returns bounded source categories and operation summaries
  without retrieval or reservation. Source-class exclusions are applied by the
  shared planner and can only narrow; conversation-history exclusion also suppresses
  candidate message IDs. The UI requires preview review, then separately requires
  review of the exact canonical package before copy, import, or dispatch.
- A lost prepare response can be reconciled through the deterministic idempotency
  identity. The response exposes canonical state, reservation ID/fingerprint, expiry,
  and stale reason, but never reconstructs prompt text. A prepared or stale reservation
  can be canceled by idempotency key. The sidecar keeps only that key in session
  storage and reconciles on mount.
- Connected deltas live in the shared chat reducer under the pending assistant ID.
  They are cleared on interruption or reconciled on completion and are never persisted
  as partial output. Attribution labels use execution origin and fact source for
  automatic-managed, connected-local, and manual-import turns.
- The sidecar threads provider-neutral application/workspace scope through API calls.
  Workspace membership uses a typed injected authorizer whose default denies access.
  Routing owns endpoint registry discovery and its canonical static explicit-admission
  projection; usage accounting no longer supplies that dependency. Profiles identify
  an external transport adapter, and a synthetic second adapter exercises the same
  controller contract. The concrete local adapter contract remains bridge-v1.
- Context-package summaries distinguish direct selected messages from summary-derived
  source coverage. A known local usage limit blocks connected preparation and
  dispatch. Partial or malformed configured signer material fails settings
  validation; an entirely unconfigured signer remains intentionally disabled.

## Verification

| Check | Result |
| --- | --- |
| Backend full suite: `UV_CACHE_DIR=/private/tmp/personal-ai-uv-cache uv run python -m pytest` | **1,330 passed, 82 skipped**, 2 warnings, 76.90s. Six external-turn persistence tests remained skipped. |
| Backend lint: `UV_CACHE_DIR=/private/tmp/personal-ai-uv-cache uv run ruff check .` | Passed. |
| Backend package: `UV_CACHE_DIR=/private/tmp/personal-ai-uv-cache uv build --no-build-isolation` | Passed; source distribution and wheel built. |
| Frontend tests: `pnpm run test` | **21 files, 109 tests passed.** |
| Frontend lint: `pnpm run lint` | Passed. |
| Frontend type checks: `pnpm run typecheck` | Passed for application and test projects. |
| Frontend production build: `pnpm run build` | Passed on Next.js 15.5.23. Next reported the repository's existing missing Next ESLint-plugin warning. |
| Context evaluation: `uv run python -m personal_ai.evaluation.context` | Passed. |
| Context planner evaluation: `uv run python -m personal_ai.evaluation.context_planner` | Passed. |
| `git diff --check` | Passed after the evidence rewrite. |
| DynamoDB Local: `make persistence-test-up` | **Not run:** this host has no `docker` executable (`make: docker: No such file or directory`). The six `tests/persistence/test_external_turns.py` cases remain skipped and M9 is unverified. |

Frontend commands used
`PATH=/Users/jasonkli/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin:/Users/jasonkli/.cache/codex-runtimes/codex-primary-runtime/dependencies/bin/fallback:$PATH`.
Backend `uv` commands used the temporary cache path above because the global cache is
outside the writable workspace. Offline checks do not establish provider, emulator,
cloud, deployment, browser-loopback, or production-security behavior.

## Remaining acceptance gaps

- Phase 15 still lacks complete pre-retrieval authorization for every contributing
  source/provider operation, end-to-end derived history/summary revocation
  dependencies, immutable policy/source references, and an atomic revocation fence.
  The new acceptance setting is default-off to keep external disclosure unavailable
  until those hard gates pass.
- Production DynamoDB conditional-write, transaction, race, restart, and recovery
  semantics remain unverified. The in-memory/service tests do not substitute for the
  six skipped persistence-engine tests.
- The base application injects a deny-all workspace authorizer. Workspace-scoped
  execution remains unavailable until a canonical membership authorizer is
  explicitly composed. Synthetic scope tests establish header propagation only.
- Only the local bridge-v1 transport is implemented. A synthetic adapter verifies the
  registration seam, not another real runtime's protocol, pairing, or send behavior.
- Live ChatGPT OAuth/Responses compatibility, enforceable plan-only billing,
  distribution approval, native browser private-network/mixed-content behavior,
  deployed identity, IAM, signer custody/rotation, and cloud deployment remain
  unverified.
- Phase 25.4 real domain integrations and Phase 31 mutation acceptance remain future
  work. No domain Apply authority was added.

These gaps prevent marking Phase 25.3 complete. Do not describe fixture-backed tests or
the local source gate as production acceptance.

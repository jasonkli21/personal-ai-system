# Repository modularity refactor and compatibility cleanup evidence

This record retains the original refactor's dated verification and adds the
follow-up cleanup verification below. The original evidence describes its own
tested source tree; it is not current evidence for compatibility-path removal.

Date: 2026-10-11

Tested revision: `b0c6bf5` (`main`) plus the uncommitted working tree.

Change type: structural refactor; no commit or staging was performed.

## Changes

- Reorganized concrete persistence into `persistence/dynamodb/` and `persistence/postgres/`, including Postgres usage accounting collaborators. Neutral storage contracts remain in `storage/`; neutral memory-effect contracts now live in `memory/effects.py`.
- Split the LiteLLM gateway into `llm/litellm/` modules for profiles, request shaping, streaming, transport, and accounting. Kept the neutral gateway entry point.
- Replaced active routing phase-number ownership with semantic decision, integrity, and policy modules. Routing now asks its injected repository for database time instead of importing Postgres routing code.
- Moved iterative research into a real package and extracted budget, planner, and sufficiency logic. The service remains the durable run state-machine coordinator.
- Put chat turn orchestration and neutral events in `services/chat/`, with provider-stream lifecycle helpers in `streaming.py`; kept SSE schema conversion in `api/chat_stream.py`. Split external-turn work behind its service façade.
- Split ranking policy and the memory lifecycle namespace, and moved route-specific request admission out of authentication middleware.
- Split the frontend API client into common, conversation, and external-turn modules. Split the continuation sidecar into transport, state, context, recovery, manual-flow, and connected-flow modules.
- Grouped evaluation fixtures and schemas under `evaluation/fixtures/` and `evaluation/schemas/`, and moved active infrastructure under AWS, Neon, and strict-zero policy directories.
- Added package navigation. At the original tested revision, compatibility exports, legacy resource symlinks, and historical Phase 10 infrastructure symlinks remained; the follow-up cleanup below removes those source aliases.

## Verification

- `make backend-test`: **passed**, 1,349 passed, 82 skipped. Two dependency warnings were emitted (Starlette/httpx deprecation and a Pydantic `ReadOnly` warning).
- `backend/.venv/bin/ruff check .`: **passed**.
- `make backend-build`: **passed**; the wheel contains all moved fixture and schema resources. The first attempt used uv's sandbox-denied default cache; the successful retry set `UV_CACHE_DIR` under `/private/tmp`.
- `make frontend-test`: **passed**, 111 passed.
- One earlier combined frontend run intermittently missed the research reconnect timeline. The case passed alone and the final full suite passed; the research UI was not changed.
- `make frontend-lint`: **passed**.
- `make frontend-typecheck`: **passed**.
- `make frontend-build`: **passed**. Next reported that the ESLint configuration does not detect its plugin; compilation and page generation completed.
- Focused infrastructure static/release-gate checks: **passed**, 5 passed. Focused chat-stream/sidecar and iterative-research checks also passed.
- `git diff --check`: **passed**.

## Boundaries and remaining gaps

The offline suite includes 82 skipped tests. No Docker-backed Postgres/DynamoDB integration, live provider, cloud IAM, or deployment acceptance was established by this refactor. Migration ordering and persisted schemas were not changed; target-database migration history remains unverified.

`domains/fixtures.py` remains domain-owned because the runtime API exposes its synthetic comparisons as a demo endpoint. Context assembly/planning and the central routing and iterative-research coordinators remain cohesive owners of authorization, replay, transaction, and state-transition ordering; their independently owned policies and helpers are now separate modules.

## Compatibility cleanup follow-up

Date: 2026-10-11. Tested tree: base revision `f5a4de5` (`Refactor repository module boundaries`) plus the compatibility cleanup working tree. Verification below does not establish cloud, provider, deployed, or database-engine acceptance.

The follow-up migrates repository-owned consumers to canonical modules and resource paths, removes forwarding-only Python and TypeScript files, removes root-level evaluation resource symlinks and `infrastructure/phase10/` aliases, and updates active path guidance. It preserves canonical package APIs, frozen migration 022 and its checksum inputs, persisted identifiers, and historical dated evidence.

### Follow-up validation

| Check | Result |
| --- | --- |
| `PATH="$PWD/backend/.venv/bin:$PATH" make backend-test` | **Passed:** 1,349 passed, 82 skipped; two dependency warnings (Starlette/httpx deprecation and Pydantic `ReadOnly`). |
| `backend/.venv/bin/ruff check .` | **Passed.** |
| `PATH="$PWD/backend/.venv/bin:$PATH" UV_CACHE_DIR=/private/tmp/personal-ai-compatibility-cleanup-uv-cache make backend-build` | **Passed:** source distribution and wheel built. A wheel inspection found all 11 canonical fixture/schema resources and no root-level JSON aliases. |
| `make frontend-test` with the desktop bundled Node runtime on `PATH` | **Passed:** 111 tests across 21 files. |
| `make frontend-lint`, `make frontend-typecheck`, and `make frontend-build` with the desktop bundled Node runtime on `PATH` | **Passed.** Next.js reported that its ESLint plugin was not detected; compilation and static page generation completed. |
| `backend/.venv/bin/python -m pytest -q backend/tests/persistence/test_cloud_static_config.py backend/tests/persistence/test_strict_zero_gate.py` | **Passed:** 5 focused infrastructure static/release-gate tests. |
| Changed Markdown link review and `git diff --check` | **Passed:** 20 changed Markdown files checked; no missing relative links or whitespace errors. |

The final import/path audit found no repository code, test, build, or deployment command referencing a removed compatibility module or alias. Canonical package initializers and `frontend/src/lib/api/index.ts` remain intentional package APIs; the text-delta methods in the neutral LLM protocols remain runtime contracts that require successful terminal status. Other remaining `legacy` references concern durable record decoding or frozen migration behavior. No schema or migration file, persisted routing identifier, or migration 022 checksum input changed. The 82 skipped tests include opt-in engine/provider/cloud coverage; Docker-backed Postgres/DynamoDB, live provider, cloud IAM, and deployment acceptance were not established.

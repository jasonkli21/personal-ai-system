# Phase 26 — Travel context integration evidence

Status: locally implemented and verified; integration gates remain off; live acceptance is open  
Date: 2026-10-11

## Tested revisions and scope

- Personal AI base revision: `78c7e4bc4678bd88a64c029c85f31e3bc66ef2c9`.
- Travel base revision: `c84433b9484133d9e054f8719e6e769e178af614`.
- Both repositories were tested from working trees based on those revisions; no commit was created.
- Personal AI source/test manifest: 35 files, aggregate SHA-256 `fe494f66c0ba4462958ff07dd4aec9ff4ad247b9b1b173c3f41df89def6a4391`.
- Travel backend/frontend source/test manifest: 19 files, aggregate SHA-256 `9dc3eacf3b497c8b39a84fab2458ae60edf65da3ffd4a33827ebc3fae689da80`.

The new Travel read boundary is `POST /v1/integrations/personal-ai/context` with `travel-context-read-v1`. Sidecar launch metadata uses `application-launch-v1`; conversation create, history, context preview, and automatic continuation use the existing Personal AI application-scoped APIs. Existing direct Travel capabilities remain unchanged: `research-v1`, `booking-document-extraction-v1`, `itinerary-proposal-v1`, `travel-itinerary-context-v1`, `itinerary-proposal-policy-v2`, the accepted comparison contracts `domain-lookup-v1`, `domain-comparison-v1`, `domain-module-v1`, `travel-comparison-v1`, `travel-features-v2`, and `travel-sources-v1`, and Travel response `travel-research-comparison-v1`.

## Architecture and behavior delivered

Personal AI composes `travel.trip_context` and `travel.research_context` through the deployment-owned `ContextRuntimeRegistry`, the generic `ContextPlanner`, `ContextProviderCoordinator`, `ContextAssembler`, policy revalidators, and existing conversation lifecycle. Selected entity triggers and entity-type bounds extend the generic planning rule; there is no Travel-name branch in generic orchestration. Shared profile, conversation, and eligible memory remain on their existing providers.

Travel remains canonical for trip, itinerary, place, reservation, authorization, validation, persistence, and all final writes. Its typed HTTP projection is owner-authorized and bounded. It returns requested current records and explicitly selected cited research, with source identity/version, fingerprint, observed/expiry facts, sensitivity, and trip-revision permission dependency. Reservation summaries are minimized, explicitly selected, and sensitive. The new sidecar is preview-first and supports narrowing, Copy, and non-authoritative draft insertion only. The pinned Travel model has no separate persisted travel-preference profile or trip-history store, so no parallel `domain_profile` or `domain_history` source was invented; the shared Personal AI profile, active conversation history, and eligible memory remain on their existing owners and paths.

Identity and scope stay separate: Travel verifies the signed-in user and selected trip; Personal AI verifies the Cloud Run service token as transport identity and carries the Google user assertion separately. The application is `travel`, `workspace_id` remains null, and no trip-to-workspace mapping exists. Stable conversation creation keys reconcile duplicate creation; turn idempotency remains on Personal AI's canonical turn path, and a regression test confirms additive provenance fields do not change pre-existing external authority digest payloads.

Payload-free source snapshots now flow from selected context into canonical assistant attribution and derived conversation summaries. Permission dependencies and expiries are rechecked before source-derived history can re-enter summary selection, counts, or model input. Effective sensitivity includes inherited history before auxiliary disclosure. Source-dependent or time-bound Travel turns are not promoted into durable shared memory. Denied, expired, scope-mismatched, and unverified history fails closed. Repeated identical permission dependencies are checked once within each policy decision, with later assemblies and transitions performing fresh checks. No new database or migration was introduced.

## Verification

Personal AI checks:

- `cd backend && .venv/bin/python -m pytest -q` — **1,365 passed, 82 skipped, 2 warnings**.
- `cd backend && .venv/bin/ruff check .` — passed.
- `cd backend && uv build --no-build-isolation` — source distribution and wheel built.
- `cd backend && .venv/bin/python -m personal_ai.evaluation.context`, `context_planner`, `memory`, and `memory_lifecycle` — all exited successfully with deterministic local fixtures.
- `git diff --check` — passed.

Travel checks:

- `cd backend && uv run --locked pytest` — **193 passed, 124 skipped, 1 warning**.
- `cd backend && uv run --locked ruff check .` — passed; `uv run --locked ruff format --check .` — 160 files formatted.
- `cd backend && uv run --locked mypy src` — no issues in 102 source files.
- Frontend Node tests — **59 passed**; ESLint — passed; Next route type generation and `tsc --noEmit` — passed; production Next build — passed.
- `python3 scripts/check_markdown_links.py` — **222 local links across 72 Markdown files**.
- `git diff --check` — passed. Personal AI changed-document links passed: 213 local links across four updated Markdown files.

The pnpm wrapper first stopped at its no-TTY dependency cleanup guard. A serial install in CI mode then reached the repository's configured ignored `unrs-resolver` build script and stopped with `ERR_PNPM_IGNORED_BUILDS`. To preserve that existing package build-script policy, the same frontend test, ESLint, Next type-generation, TypeScript, and production-build entrypoints were run directly against the installed dependencies and passed.

The skipped test cases are opt-in persistence/provider/cloud checks and do not establish those environments. PAI has no configured backend mypy target; the Travel backend mypy target passed.

## Gates and open acceptance

The following gates default off: Personal AI `TRAVEL_CONTEXT_ENABLED`, Travel backend `PERSONAL_AI_CONTEXT_ENABLED`, and frontend `NEXT_PUBLIC_PERSONAL_AI_CONTEXT_ENABLED`. Existing research, extraction, proposal, and comparison feature/provider gates remain independent.

No deployed Cloud Run invocation, live Google user/service token or audience alignment, live provider or data-use/retention approval, deployed Travel revision behavior, browser interaction, or production authorization/revocation check was performed. These remain unverified. Local fixtures and the local-owner development identity do not establish production readiness.

## Architecture audit and independent review focus

The implementation uses the existing runtime registry, planner, provider coordinator, assembler, permission revalidation, conversation persistence, idempotency, and policy seams. Travel remains the only domain authority. Generic code has no provider-name or application-name decision branch, no parallel conversation store, no shared database, no trip/workspace mapping, no provider-specific routing/accounting, and no model-driven write path. Existing direct Travel capability routes and idempotency remain on their accepted contracts. Phase 27 Shopping can use the same generic selected-entity/provider seams; Phase 31 can later introduce typed mutations without giving this read-only sidecar write authority.

Independent review should focus on:

- source revision and owner-permission revalidation order, including derived summaries and history;
- context sensitivity propagation into count, generation, and memory extraction;
- the exact Travel projection and the sensitive reservation-summary selector;
- service identity versus user identity verification at both HTTP boundaries;
- conversation create idempotency and stable external-turn authority digests for legacy records;
- direct Travel research, extraction, proposal, and comparison compatibility;
- default-off gate behavior and same-origin forwarding of the user assertion only.

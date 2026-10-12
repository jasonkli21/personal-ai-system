# Phase 27 implementation evidence — Shopping integration

**Recorded:** 2026-10-11
**Status:** Locally partial; Phase 27 is incomplete and not accepted.

## Pinned inputs and scope

- Personal AI starting revision: `c2dfe2d` on `main`.
- Shopping integration revision: `5a2c1d3` on `shopping-assistant/main`.
- Cross-repository read contract: `shopping-context-read-v1`.
- Shopping Project IDs remain Shopping-domain entity references. The contract always sets `workspace_id = null`.

The implementation adds a real, bounded read path for the existing Shopping context capability identities. It does not deliver task generation, routed Shopping research, or a Shopping-hosted sidecar; the blockers are documented below and both read gates remain off by default.

## Architectural decisions and interfaces

Shopping owns the versioned `POST /v1/integrations/personal-ai/context` request/response contract and reads its canonical PostgreSQL state. `current` returns only requested project fields and explicitly selected project-product membership IDs. Hard requirements (`must_have`, `constraint`) stay separate from soft preferences; saved/rejected decisions and exact product/variant IDs remain Shopping state. `search` returns persisted selected-product offers and claims as freshness-bearing external evidence, grouped with the project-product, canonical product, and variant IDs. It does not crawl merchants or make external observations authoritative. `verify` checks the selected project revision for later permission revalidation.

Shopping verifies a Google service ID token and a separate forwarded verified user ID token. It checks configured audiences and exact service/user identities, requires an operator-supplied mapping reference, resolves the fixed Firebase owner binding, and checks owner/project authorization before projection. The database read uses a repeatable read-only transaction, a bounded statement timeout, explicit entity/field/result/byte limits, and no-store response headers.

Personal AI maps the external DTOs in `personal_ai.context.shopping` and registers `shopping.product_context` and `shopping.catalog_search` through the existing deployment-owned `ContextRuntimeContribution`. Retrieval uses the existing provider coordinator, deterministic planner, application field policy, shared context assembler, and permission revalidation registry. The Shopping capabilities are marked implemented but have the independent `SHOPPING_CONTEXT_ENABLED=false` gate; Shopping also defaults `PERSONAL_AI_CONTEXT_ENABLED=false`. Application/workspace labels grant no access. The existing barcode lookup/comparison API remains separate.

Shopping's existing owner-scoped current-state projection is extended with selected-only and evidence-only modes and reused by the read contract; no duplicate project store or parallel generation client is added. Shopping's existing `PersonalAIClient.generate(AIRequest) -> AIResponse` remains unchanged, `PERSONAL_AI_MODE=external` remains fail-closed, and `shopping.product_action` remains unavailable.

## Work-package disposition

- **P27.0 read contract/providers:** implemented locally, including owner/project checks, selected entity identity, current versus external evidence authority, provenance/freshness, bounds, and fail-closed permission revalidation.
- **P27.0 task transport:** incomplete. The Shopping worker queue has no delegated-user identity, and Personal AI has no accepted generic typed-task route for Shopping's `AIRequest` contract. No route was inferred from ordinary conversation streaming or the unrelated barcode API.
- **P27.1 routed research baseline:** incomplete. Extraction/rewrite/synthesis are not routed through P21/P24. The P15 membership/revocation acceptance gate still blocks request-workflow integration; no application-specific orchestration or provider shortcut was added.
- **P27.2 shared sidecar:** incomplete. Shopping has no accepted host/embed and identity bridge for the shared sidecar. The implementation does not claim selected-context disclosure, Copy, or draft insertion.
- **Mutations:** no shortlist/requirement write path was added. Typed proposal, confirmation, idempotency, and authoritative mutation remain for Phase 31.
- **README:** reviewed; no README-visible capability changed because context is default-off and generation/UI behavior is unchanged.

Accordingly, this is not Phase 27 closeout. The unresolved work requires accepted routing/identity and host contracts; inventing parallel generation or sidecar mechanisms here would conflict with the established shared architecture.

## Verification record

Tested on 2026-10-11. Personal AI was based on `c2dfe2d`; the cross-repository Shopping contract was pinned to `shopping-assistant` revision `5a2c1d3`.

### Personal AI

- `backend/.venv/bin/python -m pytest -p no:cacheprovider -q` — **1,375 passed, 82 skipped**.
- `backend/.venv/bin/ruff check --no-cache src tests` — passed.
- `uv build --no-build-isolation` — source distribution and wheel built successfully.
- `backend/.venv/bin/python -m personal_ai.evaluation.context_planner` — **9 planner fixtures passed**.
- `git diff --check` — passed.

### Shopping Assistant

- `UV_NO_SYNC=1` with the workspace-bundled Node.js/pnpm on `PATH`, `make validate` — passed. API Ruff check and format check passed; offline API tests **195 passed, 130 deselected**; generated API types were current; web lint passed; web tests **68 passed**; TypeScript typecheck passed; web production build passed.
- Focused context/auth/config tests — **31 passed, 1 database test deselected**.
- `TEST_DATABASE_URL` was absent. The PostgreSQL integration case covering actual owner/project retrieval, hard/soft and rejected state, selected evidence, no-write behavior, and foreign-owner denial was not run against a disposable database.
- Build emitted a bundle-size advisory; API tests emitted one Starlette deprecation warning.
- `git diff --check` — passed.

Google certificate/token verification against live credentials, operator mapping approval, cloud/IAM, deployed Shopping revisions, live provider behavior, and browser/sidecar behavior were not exercised. Those checks remain unverified.

## Architecture audit and downstream compatibility

- Shopping remains canonical for project, requirements, products/variants, decisions, offers, and evidence. Personal AI reads through an authenticated Shopping contract and does not access Shopping persistence directly.
- The cross-service user and service identities are distinct; owner authorization is independent of application/workspace scope. No credential is stored or logged.
- The read path is explicit, bounded, read-only, time-limited, and permission-revalidated. It adds no retry, mutation, or uncertain-write behavior.
- Project state and freshness-bearing external observations stay separate. Catalog observations preserve exact project-product/product/variant identity, source refs, timestamps, freshness, and expiry.
- Generic Personal AI layers use the existing contribution/provider/planner/policy/assembler/revalidation seams. Shopping-specific wire mapping and policy fields stay in the adapter and application manifest; generic routing contains no Shopping-name branch.
- No project/workspace mapping, memory API, task route, new worker identity store, sidecar host, or mutation mechanism was invented. Phase 30 federation and Phase 31 proposals retain their planned extension points; Finance/Health remain free to define their own authorization and source contracts.
- The main review concern is that the Shopping integration currently reuses an internal conversation current-state projection. That avoided duplicate domain reads for this phase; an independent review should decide whether to promote it to an explicitly named shared domain-read seam before additional consumers are added.

## Independent review focus

Review the exact Google-subject-to-fixed-Firebase-owner mapping and its operator attestation/revocation lifecycle; Google audience and claim verification; transaction ordering/isolation and timeout handling; whether all project-child updates advance the permission revision; source-version and observation-fingerprint semantics; field-level sensitivity and selected-only projection; and confirmation that registry metadata cannot bypass either gate. Review P27.1 generation/routing and P27.2 host integration as incomplete work rather than delivered behavior.

## Post-implementation review follow-up — 2026-10-11

The follow-up promotes Shopping's owner-scoped current-state projection to a
public domain context read seam and routes both the legacy conversation helper
and Personal AI adapter through it. Current and catalog records now retain
selected product, variant, and project-product membership identities, source
revisions, and permission dependencies. Catalog records are emitted per
observation with their own expiry; the bounded recent-first selection reports
omitted records and a selection-policy version. Normalized Personal AI context
preserves the selected Shopping entity references. Google token acquisition is
bounded by the shared request deadline, and the certificate request closes its
HTTP session.

The required mapping-version label and exact configured Google/Firebase
identity mapping are now fingerprinted into the Shopping project permission
dependency. Reads and permission verification recompute that fingerprint, so
changing the label or mapped identity invalidates previously derived context.
This is deployment-managed configuration for the current single-owner model,
not a multi-owner grant store. Both context gates remain off pending live
identity and operator-configuration verification. Workflow routing and the
shared sidecar remain blocked on common prerequisites and host/identity
contracts.

Verification on 2026-10-11:

- Personal AI full backend suite: **1,398 passed, 82 skipped**; Ruff passed.
- Shopping offline API suite: **197 passed, 130 database tests deselected**;
  focused context tests **13 passed, 1 database test deselected**; Ruff and
  format checks passed on changed files.
- Health changed-surface suite: **7 passed, 16 database-backed tests skipped**;
  Ruff, Mypy, and generated client TypeScript checks passed.
- Finance context route smoke test: **9 passed**.
- No PostgreSQL-backed integration, live Google/Firebase identity, deployed
  cloud, provider, or browser/sidecar check was established by these runs.

## Cross-repository review correction follow-up — 2026-10-11

The Shopping owner-mapping lifecycle now participates in the dependency
version used by the shared context revalidator. The Health daily Event and
Observation create/edit flow exposes the source-domain cross-domain consent
switch in the mobile app; this does not bypass the default-off integration or
the unavailable delegated-identity capability.

Verification on 2026-10-11:

- Personal AI backend: **1,398 passed, 82 skipped**; Ruff passed.
- Shopping API: **197 passed, 130 database tests deselected**; focused context
  tests **13 passed, 1 database test deselected**; Ruff and format checks
  passed.
- Health API: **179 passed, 75 skipped**; mobile daily model/form tests
  **22 passed**, TypeScript typecheck passed, Ruff and Mypy passed, and the
  Prettier-formatted OpenAPI artifact matched a fresh schema export.
- Finance context smoke test: **9 passed**.

PostgreSQL-backed cases were skipped because no local test database was
configured. CI contains disposable-PostgreSQL jobs for Shopping and Health.
Live identity, cloud/IAM, provider privacy, and sidecar behavior remain
unverified. Phases 27–29 remain incomplete where task routing and sidecar
work depend on shared identity, workflow, and host prerequisites.

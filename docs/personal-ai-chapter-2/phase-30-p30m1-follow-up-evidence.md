# Phase 30 P30-M1 follow-up evidence

Date: 2026-10-11. Tested revisions: Personal AI base `6ad3c05` plus the Phase 30 changes in this commit; Travel `ff3ac4c`; Health `9aa72fe`; Shopping `2268b94`; Finance `495c211`. This is local implementation evidence; it is not phase acceptance.

## Implemented source and broker work

- Travel now owns a revisioned destination and a default-off cross-domain sharing choice per trip. Its `travel-context-read-v2` endpoint has a purpose-bound `shopping_trip_context` export containing only destination, start date, and end date, plus a current-revision verification response. The Personal AI Travel adapter is installed only when `travel_federation_enabled` is set and preserves source/permission dependencies through the generic broker.
- Finance now owns a monthly discretionary budget record containing amount, currency, period, revision, and explicit Shopping-sharing consent (default off). Its Finance context endpoint accepts only the exact three fields for `shopping_discretionary_budget` to Shopping and verifies the same consent/revision. Personal AI's Finance budget adapter shares the existing default-off Finance context gate.
- Health now owns separate, default-off `health-federation-export-v1` reads for dietary restrictions → Travel and ergonomic constraints → Shopping. Each request selects one exact profile item, field, purpose, and destination. Health rechecks owner, item status/validity, AI-use consent, cross-domain consent, current revision, supported value type, and restricted sensitivity. The response is explicitly complete or authoritative-empty and carries source and permission dependencies.
- Shopping remains on the generic destination boundary. Its existing client has no supported typed task transport; external mode fails closed without a request. No direct cross-domain database path or destination-owned source copy was added.

## Acceptance state

P30-M1 remains open. Personal AI authenticates Health with Google OIDC, while Health requires the delegated user's recent Firebase token. No safe exchange or binding exists, so Health's source implementation is not registered as an executable Personal AI adapter. Shopping's queued task path carries no delegated-user identity and has no supported typed upstream route or shared-sidecar host. The three Shopping-bound flows and Health → Travel therefore cannot yet run as product flows. Travel and Finance source adapters are registered behind independent gates, but this does not establish end-to-end identity, grant UX, live revocation, or deployed behavior.

## Checks

- Personal AI focused context/federation suite: **67 passed** (`test_travel_context.py`, `test_finance_context.py`, `test_federation.py`); Ruff passed on changed backend files.
- Travel API context/contract tests: **20 passed**; Ruff passed. Frontend trip workspace regression tests and TypeScript checks are recorded in Travel's companion [evidence](../../../personal-travel-app/docs/releases/phase-30-federation-export.md).
- Finance context and monthly-budget tests: **15 passed**; Ruff passed; Alembic reports `0019_monthly_discretionary_budgets` as head.
- Health export/auth tests: **14 passed, 4 skipped**; Ruff passed. The four skips are PostgreSQL-backed cases, including positive/revocation export coverage, because no disposable `TEST_DATABASE_URL` was configured. Three offline export tests cover the owner/consent query predicates and narrow non-empty, authoritative-empty, verification, and denial results.
- Shopping Personal AI boundary tests: **14 passed, 1 deselected**. They confirm the existing bounded context contract and fail-closed external client; they do not exercise an incoming federation destination path.
- Changed-document checks and `git diff --check` are required before commit. Cloud, provider, domain-deployed identity, browser, and cross-repository end-to-end checks were not run.

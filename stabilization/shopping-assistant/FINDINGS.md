> Historical worker/baseline record. Final2026-10-14 local evidence is in
> [verification](../VERIFICATION.md) and the [review handoff](../REVIEW-HANDOFF.md).
> Preserve these original results; later local checks do not accept external gates.

# Reconciled findings

Baseline revision: `2268b944ffa8fe5c2e6f2787c88dea616160e398` on `main`; date 2026-10-13. Findings were checked against current code, canonical status and plans, current GitHub Actions, and selective local checks. The audit is a starting backlog, not authority.

| Priority | Finding | Reconciliation and evidence |
|---|---|---|
| P0 | Main CI is red from four independent jobs. | Verified on run [38265114836](https://github.com/jasonkli21/shopping-assistant/actions/runs/38265114836), whose head SHA equals current main. The frontend E2E job passes. |
| P0 | Backend formatter gate fails. | Fixed in the local Gate 1 diff: `context.py` was formatted. Ruff lint and format checks pass across all 176 source/test/migration files. Hosted CI has not rerun on this diff. |
| P0 | Personal AI context rejection enum drift. | Fixed in the local Gate 1 diff by changing the test fixture and DB request from `too_heavy` to `too_large`, which already matches the request schema, ORM constraint, browser UI, and Phase 6 plan. The full PostgreSQL suite now passes 129 tests. |
| P0 | Two discovery recovery tests fail in CI. | The objective is now derived synchronously from the loaded project until the user edits it; a saved command initializes the form first and explicit empty edits remain empty. An SSR test verifies the goal renders before passive effects. The full frontend suite passes 69 tests locally, including saved-command replay and same-key retry coverage. Validation used Node 24.19.0; the CI Node 20 environment and hosted retry are still unverified. |
| P0 | Container smoke fails. | The workflow now invokes Alembic with `/app/apps/api/alembic.ini`, matching the Dockerfile's `COPY apps/api/alembic.ini ./alembic.ini` under `/app/apps/api`. The exact explicit-config command passed `upgrade head` and `check` from `/tmp` against local PostgreSQL 17. Docker is unavailable, so the actual image smoke remains unrun. |
| P0 | Generated API type drift. | The canonical generator added the optional `partial_result`, `omitted_count`, and `selection_policy_version` fields to `ContextRecord`; `scripts/generate_api_types.py --check` now passes. |
| P0 | Context expiry equality assertion fails after enum correction. | The full PostgreSQL run exposed a test-only string comparison: Pydantic serializes the top-level aware datetime with `Z`, while the nested observation stores `datetime.isoformat()` with `+00:00`. The test now parses both values, asserts both are present, and compares the aware instants. The full PostgreSQL suite passes 129 tests. |
| P1 | SQLAlchemy table-sort cycle warning. | Verified in backend DB CI among `preference_candidates`, `project_requirements`, and `shopping_preferences`. Decide whether both FK directions are required; if intentional, make migration/drop ordering explicit. CI warning is not itself a test failure today. |
| P1 | External Personal AI mode is unavailable. | Verified in `client.py`, the integration contract, and architecture docs: `UnavailablePersonalAIClient` raises `provider_unavailable` without network I/O. The barcode lookup route is separate and does not provide typed task execution. |
| P1 | Cross-app destination execution is not implemented. | Shopping exposes only a default-off read-only `shopping-context-read-v1` contribution. It has no user-bound typed-task route, queued delegated identity, task result state, or cross-app idempotency contract. The three incoming Health, Travel, and Finance flows remain unavailable per current state and Phase 30 evidence. |
| P1 | Release and cloud acceptance remain open. | Confirmed by current state, Phase 6 review, Phase 9 verification, and the runbook. Manual browser review, phase-specific database/review gates, identity/IAM, hosted recovery, backup/restore, provider, and security evidence remain open. No deployment was performed. |
| P2 | Large files and test modules deserve targeted maintainability review. | Inventory below identifies research execution/persistence, comparison and preference services, discovery UI, and journey tests. Existing domain seams are already clear; split only where ownership or local reasoning improves. |

## Audit claim status

- **Verified at baseline:** latest main was red; the CI PostgreSQL enum failure, two discovery failures, and container config error were recorded on that SHA; the SQLAlchemy cycle warning is present; E2E was green; external mode is a fail-closed stub; cloud is not accepted.
- **Fixed and locally verified in the uncommitted Gate 1 diff:** formatter, enum fixture, discovery initial-goal race, generated type drift, container Alembic invocation, and expiry instant assertion. Offline API, PostgreSQL, and frontend suites pass.
- **Externally unverified:** hosted CI on the diff, Node 20 behavior, and the actual Docker image smoke.
- **No evidence supports** treating Shopping context reads as typed-task delivery, a multi-user grant system, or production readiness.

## Cross-repository consequence

Shopping remains the chosen reference destination, but a generic Personal AI → Shopping task host does not yet exist. The next architectural work depends on a shared envelope and contract/version authority for delegated identity, destination capability, source references/revisions, grant and policy dependencies, expiry, task/request/idempotency identity, and structured results. Shopping must validate authority and invoke its existing domain command layer; Personal AI must not own Shopping records. Until those pieces are jointly accepted, a local Shopping endpoint or fake client does not close Finance → Personal AI → Shopping.

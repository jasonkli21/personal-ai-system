# Phase 28 Finance integration evidence

**Date:** 2026-10-11
**Status:** Local read-only integration implemented; Phase 28 remains incomplete.
**Tested worktrees:** PAI based on `d1460ca9dcf0418676898a8d7264de6f734ed7d3`; Finance based on `7b34529e2f9a9667558cfa6c04cd1a8af96ed8b1`.
**Finance contract:** `finance-context-read-v1`.

## Implemented boundary and data flow

Finance owns the separately versioned read contract, its canonical records, calculations, private originals, authentication-to-principal mapping, and persistence. The existing `PersonalAIClient.extract` remains a distinct disabled candidate-extraction seam. No Finance database, object store, model SDK, or internal Finance module was imported into Personal AI.

The integration contributes four Finance capabilities (`finance.account_context`, `finance.portfolio_context`, `finance.research_context`, and `finance.research_evidence`) through the existing application registry, `ContextRuntimeContribution`, provider coordinator, deterministic planner, context assembler, and permission-revalidation contracts. Finance values are mapped to ordinary shared `ContextItem` records; no Finance-specific planner, routing, accounting, persistence, or context-assembly path was added. The provider availability and Finance endpoint each have independent default-off configuration gates.

The request path uses host-selected entity references and explicit planning rules. Position reads require both an account and a security selection; portfolio-wide reads require the explicit portfolio sentinel and broader-context flag. Finance separately validates a Google service identity and a verified end-user identity, binds the latter to the configured active principal/scope, and performs a bounded read-only transaction. Personal AI revalidates source-version dependencies by asking Finance to verify the selected records before context reuse. The read adapter uses HTTPS, bounded response parsing, a request deadline that includes service-token acquisition, and no application-level redirects or retries. See Finance's [versioned read contract](../../../personal-finance/docs/personal-ai-context-read-v1.md).

Returned fields preserve observed/calculated/assumed/AI-interpreted class, known/unknown/conflict state, unit, currency, as-of/effective time, source identity/version, evidence references, quality/uncertainty, authority, sensitivity, and permission dependencies. Finance's `domain_current` and `external_research` source classes remain distinct. The projection excludes raw documents, transaction/tax-lot history, local paths, object-store URLs, and private originals; it never persists Finance values in Personal AI stores.

## Architecture and downstream audit

- **Ownership:** Finance remains the only canonical owner. Personal AI owns only the request-local assembled context and uses the existing sensitivity, endpoint eligibility, context budget, and permission revalidation policies.
- **Authorization:** Neither wire contract accepts owner/scope authority from the request body. Unknown identity, source, or privacy eligibility fails closed. No local identity or fake establishes deployed personal-data readiness.
- **Orchestration:** Finance-specific declarations extend existing registry/provider/planner seams. Generic layers have no Finance-name branch. The new code adds no alternate dispatcher, context builder, provider selector, or state store.
- **Mutation, retry, and idempotency:** The contract has no write/action method. Reads do not introduce mutation identities or retry behavior; transport and identity failures return unavailable/denied results without replay.
- **Downstream compatibility:** Phase 29 can register Health through the same typed capability and policy seams. Phase 30's federation/grant layer can carry source dependencies without a Finance-specific exception. Phase 31's proposal/action boundary is unchanged; no Finance action capability is registered. This work does not introduce a cross-domain grant model or authorize sidecar persistence.

The plan's P28.2 sidecar work is deferred because Finance has no accepted embed/host contract for its current frontend. The Phase 15 source/revocation-through-derived-context and Phase 21 workflow-routing prerequisites are also open. An embed mechanism or workflow route invented here would bypass those established seams, so the sidecar, Copy/save-as-draft/research-note actions, and automatic chat dispatch remain unavailable. This is a material deviation from the full written plan and keeps Phase 28 explicitly incomplete.

## Verification

Checks ran on 2026-10-11 using synthetic local fixtures. They do not exercise cloud, deployed providers, or private user data.

| Repository / check | Result |
| --- | --- |
| Personal AI focused Finance/planner integration tests | 47 passed |
| Personal AI full backend suite | 1,385 passed, 82 skipped; Starlette/httpx deprecation and Pydantic `ReadOnly` warnings |
| Personal AI `make backend-lint` | Passed |
| Personal AI `make backend-build` | Passed; source distribution and wheel built |
| Personal AI `make context-eval` | 5/5 fixtures passed |
| Personal AI `make context-plan-eval` | 9/9 fixtures passed |
| Finance `tests/test_finance_context.py` | 9 passed |
| Finance full API suite | 237 passed, 55 skipped, 1 unrelated failure |
| Finance infrastructure contract | 6 passed |
| Finance Ruff whole-tree lint/format checks and Mypy | Passed; Mypy checked 113 files |
| Finance web lint, typecheck, format, tests, production build | Passed; 8 files / 22 tests. Vite emitted a large-bundle warning. |
| Finance generated API contract | Direct OpenAPI export and TypeScript generation matched committed JSON/types byte-for-byte |

The unrelated Finance failure is `test_cached_quote_asof_precedence_and_signed_percentages`; its expected portfolio valuation is `None`. It also fails when run alone against an archive of the untouched Finance baseline revision above, so it predates Phase 28. In the aggregate Finance `pnpm check`, the API contract check, lint, format, typecheck, web tests, and infrastructure contract passed with the existing virtual environment; the full API suite then stopped on that baseline failure. The web production build passed separately. An API package build remains unverified because `hatchling` is not cached and network DNS is unavailable. No deployed identity, IAM/private invocation, PostgreSQL read-only, provider privacy/data-use, browser host, cloud recovery, or live model-provider check passed.

`docs/README.md`, `docs/current-state.md`, the chapter index, and root README were reviewed and updated for the local read contract and its default-off/incomplete status. Finance's ADR/current-state/router and versioned contract/evidence record were updated. No new evaluation runner was added.

## Remaining gates

Keep Finance and Personal AI gates off. Phase 28 cannot be marked complete until its remaining local sidecar/host integration and required workflow prerequisites are addressed and accepted, and deployment/provider authorization/privacy behavior is verified. Skipped provider/cloud checks are unverified, not passed.

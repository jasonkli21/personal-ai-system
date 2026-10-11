# Phase 25.2 implementation and verification evidence

Date: 2026-10-10. Baseline: `a7294ed55c9ba5f1fcb61077ef17950910b85adb`.
Tested source revision: `2c9db878b5c4f504bd172be9fb966449a5b16ace`, following
contract/state commit `c243a46`. The subsequent closeout commit changes documentation
only, including a serialization docstring clarification. Existing untracked
independent-review documents were preserved.

**Disposition: internal implementation verified locally; full external execution
acceptance remains open.** No HTTP issuer, provider selector, manual-import UI,
consumer website automation, cloud resource, real account, credential, or live
provider request was enabled or used. External execution defaults deny.

## Model, seams, and requirement coverage

Read the [architecture and rewrite-risk review](phase-25-2-architecture.md) and
[composition guide](phase-25-2-implementation-guide.md). Inspection covered current
conversation/context/authorization/storage contracts, P16 inference, P18 immutable
profiles, P19/P21 accounting/routing, the P25.1 implementation and review fixes,
and downstream P25.3/P25.4/P30/P31 boundaries. This phase extends those seams rather
than introducing another store, ledger, provider registry, or conversation pipeline.

| Work package | Implemented boundary and local evidence |
| --- | --- |
| P25_2.0 | P18 `ProviderAccessPolicy` and frozen schema-3 definitions express authentication, explicit selection, local credentials, account discovery, automation exclusion and hosted-history policy. ChatGPT cannot enter automatic candidates even under misleading cost/free configuration. Existing profiles retain schema-2 identity. Application policy separately permits external modes; default deny and sensitivity/profile checks precede disclosure. |
| P25_2.1 | `ExternalTurnService` delegates preparation to `ChatTurnService` and persists a bounded reservation in the canonical assistant message. Expected-message/branch CAS extends the existing repository transaction. Connected proof issuance fences before delivery; manual import has no proof/connection. Tests cover exact proof binding, profile churn, expiry, authority/source freshness, foreign scope, supersession, duplicate/changed replay, concurrent import and committed-write response loss. |
| P25_2.2 | `TurnAttribution` distinguishes observed, client-reported and user-declared facts. Manual imports reject generation/latency/usage/connection claims. Safe failures and empty uncertain outcomes remain in the canonical message. Coarse usage and recovery hooks extend the protected local registration/projection; there are no reset guesses, account payloads, or P19 updates. Existing credential/redaction tests remain included. |
| P25_2.3 | Neutral continuation requests select automatic, registered connected, or manual mode and optionally narrow complete active-turn candidates. All reuse shared authorization/planning/budgeting, preserve producer attribution, and create new turns. Tests cover connected→automatic, automatic→connected, manual→connected, connected→manual, same-provider and another registered provider, revocation and narrowing. |

Source identity contracts now live in `contracts.context_references`, re-exported
from their original context path. This dependency extraction preserves old contracts
and avoids an entity/context/repository cycle. No canonical store ownership changed.
Reservations and attribution contain payload-free source/version/reference/grant
snapshots and hashes, never copied context payloads or reusable credentials.

## Verification configuration and results

Tests used Python 3.11 in `backend/.venv`, synthetic public fixtures, fake inference,
in-memory repositories, generated ephemeral Ed25519 keys and protected temporary
bridge stores. Frontend commands used the bundled Node runtime. `UV_CACHE_DIR` was
set to `/tmp/personal-ai-uv-cache` for the build because the default uv cache was
outside writable roots. No dependency or lockfile change was required. No backend
typecheck target exists; frontend typecheck is recorded below.

| Command | Result |
| --- | --- |
| `make backend-test` | 1,296 passed, 78 skipped, 2 existing dependency warnings; 75.84 seconds. |
| `make backend-lint` | Ruff passed. |
| `make backend-build` | Source distribution and wheel built successfully. |
| Focused external-turn suite | 30 tests passed, including final hardening of context identity, superseded replay and empty failure transitions. |
| `make frontend-test` | 19 files / 98 tests passed. |
| `make frontend-lint frontend-typecheck frontend-build` | ESLint, both TypeScript configurations and Next.js production build passed. |
| `make context-eval context-plan-eval quota-scarcity-eval cascade-eval` | Passed with synthetic/offline fixtures. Cascade baseline remained 20 accepted, 7 rejected, 54 physical attempts versus direct baseline 20 accepted and 40 attempts; these are simulation results. |
| `git diff --check` | Passed for source and documentation closeout; Phase 25.2 relative documentation links resolve. |

The backend suite retains the existing Starlette/httpx deprecation and Pydantic
ReadOnly warning. Neither is proof of a provider or deployed behavior. Evaluations
are local evidence only and do not change candidate qualification or enable gates.

## Failure, concurrency, and persistence evidence

The canonical reservation states are prepared→dispatched→completed for connected
execution and prepared→completed for explicit manual import. Prepared abandonment
cancels; dispatched abandonment/failure/expiry becomes unknown, with empty content.
Dispatch means durable grant issuance, not a server-observed physical send. The
P25.1 local receipt remains the transport authority. A lost grant is never silently
reissued; explicit new preparation creates a new identity. Completed replay rechecks
current authority and compares a full completion digest without another send/write.
Superseded replay fails; historical producer attribution stays immutable.

Offline tests exercise concurrent identical finalization and reply loss after a
committed write. `tests/persistence/test_external_turns.py` adds opt-in actual
DynamoDB transaction/race/restart and issued-dispatch expiry recovery tests. Docker
is unavailable here and no isolated engine endpoint is configured, so these and
the existing opt-in engine/cloud tests remain skipped and **unverified**. Fakes and
JSON hydration do not establish DynamoDB transaction or deployment acceptance.

## Disabled gates and remaining acceptance gaps

- `ExternalTurnAuthority` is a required policy integration with no permissive
  implementation. Authoritative principal membership, paired runtime/caller/current
  connection revision, source/fingerprint/grant history, derived-memory/summary
  revocation, and atomic cross-store freshness must be established before HTTP
  composition. Existing P14/P15/P30 acceptance gaps remain open.
- Real DynamoDB race/CAS/catalog behavior, immutable Postgres source/policy history,
  signing-key custody/rotation and deployed private API identity remain unverified.
- P25.1 distribution approval, supported OAuth/Responses compatibility, account/model
  eligibility with enforceable plan-only billing, native browser transport and mobile
  remain open. Coarse usage observations prove none of these facts.
- P25.3 owns authenticated UI/HTTP composition and user-visible trust/recovery;
  P25.4 owns host integration. P31 domain Apply must independently validate proposals
  and authority. No imported/connected text confers mutation rights.

Root README was reviewed and updated to distinguish the new internal lifecycle from
enabled end-user execution. The documentation router, API contract and single living
current-state snapshot link this record. An independent reviewer should challenge
authority/source coverage, real transactional fences, expiry/clock semantics,
grant-delivery uncertainty and provenance labels most aggressively; see the detailed
[rewrite-risk review](phase-25-2-architecture.md#independent-review-challenges).

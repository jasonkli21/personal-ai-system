# Delivery and acceptance

**OFFLINE WITNESS / NOT DEPLOYED.** The dated verification record gives the observed results for the synthetic fixture. External admission gates remain proposals or blocked. Production remains `NO_GO` as recorded in [current state](../current-state.md).

## Stage 0 exit and Stage 1 entry

The repaired Stage 0 contract had no independent decision at base revision `e7ff57e695f22d6d790fcee910a0178246f5daa9`. On 2026-11-17, the project maintainer authorized private hermetic implementation. This is implementation authorization only; it does not accept Stage 0 or establish independent review of the actor/permission mapping and both bounded in-process snapshot cases. Stage 1 entry therefore remains `BLOCKED_PENDING_INDEPENDENT_STAGE0_REVIEW`. See the [dated authorization and verification](evidence/2026-11-17-synthetic-application-context.md) and [remediation disposition](evidence/2026-11-18-synthetic-application-context-review-remediation.md).

The accepted slice covers two in-memory synthetic installations and four granted travel/fitness records across two owners. It exercises bounded `describe`/`search`/`fetch`, typed `ContextItem` mapping, the shared planner and assembler, and recipient-bound preview and confirmation with whole-snapshot denial. The composition runs only in backend tests. Network listeners, product endpoints, live OAuth, MCP, SIWC, paid calls, native persistence, real data, and automatic memory writes remain outside this scope.

### Frozen fixture suite

Use the exact five rows and fixed clock `2030-01-02T09:00:00Z` in the [source contract](application-context-contract.md#exact-synthetic-registry-and-clock). The positive authorized item IDs are exactly `(itinerary-demo,r01,v7)` and `(workout-demo,r01,v2)` for owner A, and `(itinerary-demo,r01,v4)` and `(workout-demo,r01,v3)` for owner B, when the matching app/workspace/grant is selected. Results sort by effective time descending, then `record_ref` ascending, then source ID for exact ties. `trip-a-ungranted/r01/v1` is never returned or titled. Replaying an identical authorized request is byte-identical.

The hermetic gate requires all of these outcomes:

| Case | Expected outcome |
| --- | --- |
| Two operator installs with no user workspace | Both install and receive distinct PAS-assigned source IDs/epochs |
| Service credential without verified human RequestScope | `unauthenticated`; zero source lookup |
| Data caller tries install/update/disable | `unauthenticated` or `invalid_request`; no registry mutation |
| Missing/unknown source, disabled installation, unsupported schema | Deny before source lookup |
| Owner A reads owner A matching travel/fitness tuples | Exact A fixture records only |
| Owner B reads owner B matching travel/fitness tuples | Exact B fixture records only |
| Different subject with same email; wrong owner, actor, app, workspace, source, recipient, purpose, grant, epoch, issuer, audience, nonce or signature | Uniform denial; zero foreign titles; no lookup where authority is invalid |
| Owner A reads ungranted workspace | `unavailable`; no title, count, cursor or timing disclosure |
| Search cursor with changed watermark/grant epoch; stale fetch revision | `stale_dependency`; caller must reauthorize and search again |
| Runtime grant used for ChatGPT/manual snapshot | Deny; no recipient reuse |
| New recipient, purpose or field after preview; changed/revoked/stale record | Deny entire export; no partial snapshot |
| Valid separately granted recipient snapshot | Re-fetch exact revisions, preview, explicit digest-bound confirmation, all-or-nothing typed snapshot; content-free receipt |
| Oversized, invalid UTF-8, wrong field type, unknown field/classification, invalid PAS identifier round-trip | `limit_exceeded` or `invalid_request`; no normalization and no disclosure |
| Future/naive/expired observation or invalid effective/expiry interval | Deny |
| Cross-app context, missing source ref, downgraded sensitivity, missing trusted permission dependency | Deny; unchanged `ContextItem` validation |
| Limits exhausted | Existing planner/assembler bounds apply; preserve required history; zero optional records if necessary |
| Every source preparation case | Zero model calls, zero provider sends, zero durable-memory writes |

Error priority is authentication → schema/installation → authorization → cursor/revision → record lookup → bounds. Missing and unauthorized records are indistinguishable. A stale code is returned only after the caller is authorized to know the selected record. Count each source search/fetch against one shared turn deadline and byte/token/result budget; enforce raw UTF-8 message limits before parsing. Confirm deterministic order and counters from the exact installed fake registry. The initial runtime grant is never a ChatGPT export grant.

## Validation classes and evidence

Label evidence by what it actually proves:

| Class | Proves | Does not prove |
| --- | --- | --- |
| Doc/static | Links, strict JSON syntax, balanced Mermaid fences, schema cross-references | Runtime behavior, provider support, authorization correctness |
| Hermetic fake | Deterministic local authorization, limits, fixture behavior and counters | Real identity, TLS, OAuth, external-source rights or production security |
| Installed local | Behavior on a named user-controlled app/host | Shared cloud isolation or other users' settings |
| Native persistence | Atomic local/database reservations, replay and restore behavior | Live provider billing or cloud deployment |
| Live OAuth/provider | Exact installed identity, client/scope, model and observed provider response | Other apps/users, future provider policy, production scale |
| Deployed recovery | Real revocation, deletion/restore, private egress and tenant isolation | Legal approval or untested billing scenarios |
| Billing | Actual account/period/credit and enforceable exposure evidence | Hard cap unless the provider maximum is enforceable |
| Longitudinal quality | Measured quality/latency and drift on an accepted benchmark | Authorization, no-charge behavior, or external approval |

For the first synthetic slice, only doc/static and hermetic fake checks are required. Record evidence under `docs/context-inference-integration/evidence/` or another non-product, content-free dated report path with revision, commands, exit codes, fixture/identity scope, warnings, and skipped gates. Never include personal data, bearer material, credentials or source payloads. The project maintainer maintains the evidence record. Independent review and downstream admission remain separately tracked. No live, OAuth, provider, billing, persistence, deployment, or recovery check is asserted here.

## Revocation, dispatch and billing fail-closed rules

The maintainer authorized private shared application implementation on 2026-11-18 at base `9e2661c483795d05269b62d91117a424d4452d9a`. The authorization covers synthetic identities, application records and inference, plus disposable PostgreSQL verification. Earlier independent decisions remain open, and this authorization leaves production `NO_GO`. See the [scope, observations and review target](evidence/2026-11-18-shared-application-service.md).

Source freshness is checked during preparation and immediately before a single-use, short-lived send permit. The verified host performs its last possible check; send-start is durably fenced. A change seen before send denies. A midstream change stops further PAS-controlled output/reuse, but bytes already transmitted cannot be recalled. This is not an atomic source-to-provider transaction; the residual check-to-wire race remains a live-data blocker. Unknown sends stay pending reconciliation, retain their hold/fence across restart or billing rollover, and never automatically retry or fall back.

Automatic route selection currently supports `STRICT_FREE` only. Future paid execution must bind exact endpoint profile/version, model, payer/account, recipient, data use and price revision and fit both a UTC-calendar-month owner budget and provider-account-specific billing period, including unsettled holds and prior-period unknowns. If either cap cannot be enforced or a send outcome is unknown, deny further spending. Subscription allowance is separate from paid monetary accounting. Offline fake is test-only; no eligible free endpoint means no send, not silent paid/plan selection.

## Decision and gate ledger

Statuses are stable: `DECIDED`, `PROPOSED`, `OPEN`, `BLOCKED_PENDING_APPROVAL`, `BLOCKED_UNVERIFIED`. Every entry names an accountable role, next evidence/action, risk and affected gate. “Owner” below means project maintainer; it assigns accountability, not independent acceptance.

| Area | Status | Owner / next evidence | Risk and affected gate |
| --- | --- | --- | --- |
| Synthetic in-memory source, installation fake and ContextItem mapping | `BLOCKED_PENDING_APPROVAL` | Independent reviewer: accept the exact Stage 0 mapping and both snapshot outcomes at a named revision; maintainer authorization and fixture results are recorded separately | Identity and mapping claims apply only to the hermetic composition; blocks Stage 1 independent entry |
| Source HTTPS identity, delegation verifier and source-side membership | `BLOCKED_UNVERIFIED` | Project maintainer: later produce exact issuer, audience, key rotation, pinned origin and source rights evidence | Cross-tenant reads; blocks live source data |
| ChatGPT-facing protected MCP | `BLOCKED_UNVERIFIED` | Project maintainer: choose a real installed client and registration method; verify issuer, audience, scope, search/fetch and citation isolation | Wrong resource/client could disclose data; blocks MCP |
| Manual export | `PROPOSED` | Project maintainer: review recipient-specific grant, digest preview, all-or-nothing stale handling and offline-copy wording | Irreversible copy; blocks real/manual data export |
| SIWC local connected app | `BLOCKED_UNVERIFIED` | Project maintainer: obtain exact app/user/workspace/host eligibility, zero-credit-spend evidence, serializer and terminal usage result | Allowance/credit charge and custody; blocks SIWC |
| SIWC managed multi-app execution | `BLOCKED_PENDING_APPROVAL` | Project maintainer: obtain written provider approval for exact topology before any execution work | Shared subscription proxy and credential custody; independently blocked |
| Free external inference | `PROPOSED` / existing limited strict-free route | Project maintainer: keep endpoint/model/account zero-charge evidence current and route through current strict-free path | Quota, terms or account drift; no verified route means no send |
| Paid inference | `BLOCKED_UNVERIFIED` | Project maintainer: exact consent plus native atomic accounting, enforceable cap and billing reconciliation | Unbounded spend; blocks paid APIs |
| Shared-host live data | `BLOCKED_UNVERIFIED` | Project maintainer: deployed identity, isolation, private egress, restore/deletion and revocation race evidence | Tenant leakage and irreversibility; blocks shared hosting/live data |
| Latency and longitudinal quality thresholds | `OPEN` | Project maintainer and independent evaluator: establish thresholds from an accepted workload and record measurement method before promotion | Unknown performance/quality; does not block synthetic authorization suite, blocks quality claims |
| Naming-check claim about unavailable companion planning input | `OPEN` / unverified companion reference | Project maintainer: identify a tracked path and exact check output if reproducible; otherwise retain as unverified external-input note | Do not rename unrelated history or claim a repository failure; no Stage 1 blocker |

## Finding disposition

This table records document changes in this remediation; it is not external approval or proof of runtime readiness.

The 2026-11-18 review remediation is complete and accepted as a scoped code/evidence remediation by the project maintainer. That status does not change the independent entry, implementation acceptance, or production decisions.

| Finding | Disposition | Evidence / remaining gate |
| --- | --- | --- |
| R-01 | `DOCUMENTED_BLOCKED` | No independent Stage 0 decision was supplied; Stage 1 entry stays blocked pending an independent review at an exact revision. |
| R-02 | `FIXED` | Authentication now precedes size/schema errors at source, installation mutation, and PAS read boundaries; authenticated size checks remain. Focused hostile-input tests pass. |
| R-03 | `UNVERIFIED` | The test provider still creates a fresh per-provider budget. Mixed-provider aggregate byte/token/result/call accounting is not proven; keep the acceptance gate open. |
| R-04 | `FIXED` | Delegation container, body and signature types/lengths are validated before HMAC; malformed metadata yields opaque `unauthenticated` with no lookup. |
| R-05 | `PARTIALLY_FIXED` | History-dependent CI jobs now fetch full history. Source-lock and sealed-evaluation tests pass locally; no post-change GitHub matrix run is available, so current CI is not declared green. |

| Finding | Disposition | Document location / residual proof gap |
| --- | --- | --- |
| CI-001 | `FIXED` | [Application context contract](application-context-contract.md): separate operator/data planes; only synthetic install fake proposed |
| CI-002 | `FIXED` | [Application context contract](application-context-contract.md), [architecture](architecture.md): five principals and exact delegation claims; actual verifier remains unimplemented |
| CI-003 | `FIXED` | [Application context contract](application-context-contract.md): exact PAS mapping; runtime adapter remains unimplemented |
| CI-004 | `FIXED` | [Application context contract](application-context-contract.md): recipient-bound export flow and copy limitation; runtime handling remains unimplemented |
| CI-005 | `FIXED` | [Application context contract](application-context-contract.md): schemas, bounds, fixtures and stale error; schema has not been consumed by implementation |
| CI-006 | `FIXED` | [Architecture](architecture.md), [routing policy](inference-routing-policy.md): strict-free current boundary; no new route implemented |
| CI-007 | `FIXED` | [Routing policy](inference-routing-policy.md): exact model/profile/payer/account/recipient and price revision; paid execution remains blocked |
| CI-008 | `FIXED` | [ChatGPT boundaries](chatgpt-integration-boundaries.md): proposed URI and two-tool schema; exact installed client conformance remains blocked/unverified |
| CI-009 | `FIXED` | [Routing policy](inference-routing-policy.md), [ChatGPT boundaries](chatgpt-integration-boundaries.md): separate preference/evidence/eligibility; no live account evidence |
| CI-010 | `FIXED` | [Application context contract](application-context-contract.md), [ChatGPT boundaries](chatgpt-integration-boundaries.md): explicit non-atomic race and send fence; live race measurement remains blocked |
| CI-011 | `FIXED` | [Routing policy](inference-routing-policy.md): UTC owner and provider account periods with unsettled holds; no native ledger proof |
| CI-012 | `FIXED` | [Routing policy](inference-routing-policy.md): free status matrix and zero-send behavior; user-facing implementation remains future |
| CI-013 | `FIXED` | This page: frozen fixture outcomes, evidence classes, owners and independent gates; no suite executed here |
| CI-014 | `FIXED` | This page: companion naming assertion explicitly unverified; no unsupported naming-check claim |

## Promotion gates

| Area | Current decision | Minimum independent gate |
| --- | --- | --- |
| Stage 1 synthetic source | `BLOCKED_PENDING_INDEPENDENT_STAGE0_REVIEW`; maintainer authorized offline implementation only | Independently review the exact Stage 0 actor/permission mapping and both snapshot outcomes, then review the scoped implementation and frozen suite evidence, including zero sends, model calls and memory writes |
| Synthetic ChatGPT-facing MCP | E1 implemented under scoped maintainer authorization. Independent acceptance pending. | Review the candidate and its single-installation restriction, separate synthetic recipient grant, URL-free profile and stateless wire evidence at the exact revision. The mixed-provider budget gate remains open. See the [verification](evidence/2026-11-18-synthetic-context-mcp.md). |
| ChatGPT MCP | `BLOCKED_UNVERIFIED` | Installed OAuth/client and live negative isolation/citation checks |
| Manual export of real data | `BLOCKED_UNVERIFIED` | Recipient-bound live grant and disclosure/revocation review |
| Local SIWC | `BLOCKED_UNVERIFIED` | Provider/program eligibility, user-controlled host, zero-credit-spend and terminal usage proof |
| Managed multi-app SIWC | `BLOCKED_PENDING_APPROVAL` | Written provider approval for exact topology and custody |
| Paid APIs | `BLOCKED_UNVERIFIED` | Exact paid consent, hard cap, native holds and reconciliation proof |
| Shared cloud hosting | `BLOCKED_UNVERIFIED` | Real auth, isolation, private ingress/egress, deletion/restore and recovery drills |

No fake, documentation check, or offline result advances these independent gates by itself.

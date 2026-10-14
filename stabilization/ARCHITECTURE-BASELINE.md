# Cross-repository architecture baseline

Draft received 2026-10-13 from the initial worker, interrupted on user direction. Primary-session review is pending. This is a code-inspection checkpoint, not runtime acceptance. Repository checks and CI observations belong in the per-repository baseline/evidence records. No production behavior was changed for this checkpoint.

## Evidence boundary

| Repository | Inspected revision |
| --- | --- |
| Personal AI | `c029194156c570ec55f8173af969702f0265e57b` |
| Health | `7fb84c76217c772b2bce6715744b8294afafa771` |
| Travel | `09584976d46c67c97a19c72d173b2ee88dbcb31c` |
| Shopping | `2268b944ffa8fe5c2e6f2787c88dea616160e398` |
| Finance | `495c21186b68215bf110ab6ab3115cd67190cc67` |

Initial status inspection found pre-existing untracked review/handoff documents in Personal AI, Travel and Shopping, plus Travel's `frontend/pnpm-workspace.yaml`. They were preserved. Health and Finance were initially clean. Concurrent baseline workers may subsequently change their assigned files; the revision tuple above identifies this inspection, not later verification.

The five `*-audit-v2.md` attachments are backlog inputs dated 2026-10-13. Their reports of red CI, native-store failures and recovery failures require independent reproduction. This checkpoint independently confirms the missing Shopping transport and identity heterogeneity in code. It does not independently establish latest remote CI status, browser behavior, database concurrency, cloud identity or deployment readiness. In particular, the Travel audit's `travel_api` paths are stale: current code uses `backend/src/personal_travel`.

## Ownership and existing seams

Personal AI owns shared context assembly, application registration, policy/grant orchestration, provider routing/accounting and mutation control metadata. Domain repositories own domain records, revisions, validation and effects. A common identifier does not authorize cross-domain access, and no integration should share database credentials.

| Concern | Verified code anchor | Current boundary |
| --- | --- | --- |
| PAI request identity | `backend/src/personal_ai/auth/{contracts,verification,scope,middleware}.py` | Verified issuer/subject, derived PAI owner ID, request application/workspace; local identity explicitly unauthenticated |
| PAI signed delegation | `backend/src/personal_ai/auth/delegation.py` | Ed25519, exact request-body hash, service issuer/audience, original user issuer/subject and separately verified authentication time; currently used for narrow Health export |
| Shared grants | `backend/src/personal_ai/federation/{contracts,service,broker}.py`, migration `024_federation_grants.sql` | Owner/actor, source/destination scopes, entities, fields, purpose, expiry, issuance/revision/epoch, source-policy dependency; no redelegation |
| Context composition | `backend/src/personal_ai/context/{runtime,finance,shopping,health,travel}.py` | Domain adapters join the shared provider/planning/revalidation seams; domain payload contracts remain separately versioned |
| Narrow exports | `backend/src/personal_ai/federation/deployment.py` | Declares Health→Travel, Health→Shopping, Travel→Shopping and Finance→Shopping; declared capability and installed implementation are separate |
| Mutation orchestration | `backend/src/personal_ai/mutations/{contracts,service,transitions,registration}.py`, migration `025_mutation_proposals.sql` | Immutable intent/fingerprint, domain validation, explicit confirmation, one reserved physical attempt, uncertain outcome and observation-only reconciliation |
| Shopping domain effect | `apps/api/src/shopping/projects/service.py` in Shopping | Owner-scoped project commands, expected revision, domain money/requirement validation; `apply_ai_proposal(..., commit=False)` allows a surrounding transaction |
| Shopping upstream AI | `apps/api/src/shopping/integrations/personal_ai/client.py` in Shopping | `UnavailablePersonalAIClient.generate` raises `provider_unavailable`; it is not a network transport or inbound task host |
| Finance source | `services/api/app/domains/discretionary_budget.py`, `api/discretionary_budget_routes.py`, `integrations/finance_context.py` in Finance | Canonical revisioned monthly budget, explicit Shopping sharing; bounded amount/currency/period export and permission verification |
| Finance upstream AI | `services/api/app/integrations/personal_ai.py` in Finance | Candidate extraction protocol; runtime disabled; not a Finance→PAI task transport |

Paths without an explicit repository qualifier in this table belong to Personal AI. These anchors describe inspected implementations; their external acceptance remains open.

## Identity models are related, not interchangeable

| App | Native identity and domain ownership | Existing cross-app mechanism |
| --- | --- | --- |
| Personal AI | Google issuer/subject verified into `AuthenticatedPrincipal`; owner derived in `auth/verification.py`; local owner is test-only | Separate service and user identity; request scope; short-lived signed delegation for Health |
| Health | Firebase principal linked to canonical Health owner through provider identity rows | Broad context expects recent Firebase identity; narrow federation resolves the signed Google subject to linked Firebase UID and then existing owner, rechecking source consent |
| Travel | Google verified principal and server-managed session (`auth/contracts.py`, `google_oidc.py`, `sessions.py`) | Typed HTTP `clients/personal_ai.py` obtains service authorization and forwards request-bound user identity context |
| Shopping | Firebase owner binding to Shopping UUID, single configured owner | Read-context auth separately verifies Google service/user tokens and explicit deployment-managed Google/Firebase mapping; no destination task authority |
| Finance | Provider-neutral OIDC/PKCE, revocable DB session and explicit principal/scope binding | Read-context verifier currently restricts to Google issuer, allowed subject and token issue-age; no shared signed task envelope |

A shared stable external identity tuple is the best reuse point. Domain UUIDs must remain local mapping results; matching emails, raw subject strings or the literal `local` must never link accounts. The shared identity contract may carry a PAI canonical identity, but a receiver must verify its versioned binding to the issuer/subject tuple and resolve its own existing owner. Introducing an independent global user database is not justified by the first slice.

Health's `personal_ai_federation_auth.py` and PAI's `auth/delegation.py` already supply much of a reusable signed-delegation seam. They are not yet a suite contract: the signer allows lifetimes up to 120 seconds, while Health accepts at most 60 seconds (the signer's default is 60). Health also requires verified authentication time; Finance's current context verifier instead limits `iat` age. These semantics must be deliberately versioned, not silently equated.

## Task, persistence and retry ownership

PAI's mutation service should be extended before introducing a second task state machine. Its intent already contains operation/version/schema/fingerprint, exact target and expected domain version, source snapshots, bounded payload, expiry and idempotency key. Its state machine has `proposed`, `validated`, `confirmed`, `executing`, `reconciling`, `applied`, `rejected`, `uncertain`, `expired`.

`MutationService.apply` reserves execution before calling the adapter. Exceptions after reservation become uncertain. Repeated application after a possible send calls reconciliation, not execute. `reconcile` obtains its own reservation and only observes the original domain operation key. Contract retirement retains adapters by immutable fingerprint. These are valuable existing safety semantics; a generic typed-task transport must preserve them.

This is not an already-working generic task API: candidate creation currently resolves canonical model/manual output attribution, mutation adapters are not installed for live domain writes, and there is no authenticated Shopping host. Deterministic Finance-origin tasks need an explicit trusted ingress whose provenance cannot impersonate generated output. Whether that ingress is a new constructor on the same aggregate or a thin task facade requires contract review before coding.

PAI Postgres owns grants and mutation control metadata. Shopping PostgreSQL must atomically own destination command deduplication, domain write, revision and receipt. Existing Shopping project commands that commit internally cannot simply be wrapped with a later receipt insert; use a transaction-capable domain entry point. A local receipt is required even if PAI has its own record. Domain receipts and deletion fences must survive the lifetime of retained task/replay metadata.

## Minimal Finance → PAI → Shopping closure

1. Use an existing Shopping project selected by the user, with exact owner and revision. This fits PAI's existing target/post-state identity contract and avoids inventing project-creation allocation semantics in the first slice.
2. Finance selects its explicitly shareable monthly budget and exact revision. Present period, currency and amount as source context. Monthly discretionary money does not automatically mean the whole amount becomes one purchase budget; the user explicitly confirms the bounded target budget change.
3. A Finance server adapter authenticates the initiating user and establishes shared delegated authority with PAI. PAI resolves canonical grant/source policy, target capability, supported contracts and source dependency, then creates an intent through a trusted typed ingress.
4. PAI uses its mutation validation/confirmation/attempt lifecycle and a registered Shopping adapter. A signed, versioned envelope binds exact operation bytes, identities, scopes, source revisions, grant versions and execution key. Service authentication remains separate.
5. Shopping verifies both transport and delegation, resolves its own owner, validates target scope and operation, rechecks applicable current authority, and applies through normal project services in the same database transaction as command deduplication and receipt persistence.
6. PAI records a structured outcome/reference. Finance displays applied/rejected/unavailable/uncertain clearly and can retrieve the same execution. No provider call is necessary to prove this deterministic integration.
7. Kill the transport after destination commit; reconciliation must recover the receipt without a second effect. Test concurrent duplicate keys, key/payload conflict, stale source and target, wrong owner/scope/version/issuer/audience, expiry and revocation before execution.

Extending this to Travel and Health should add source export/payload mapping and stronger source policy where necessary, not separate identity or retry engines. Research job execution can follow only after a durable credential-renewal/revalidation design; do not persist bearer tokens in jobs or treat an expired assertion as long-term authority.

## Decisions and open evidence

See [invariants](CROSS-REPO-INVARIANTS.md), [contract inventory](CROSS-REPO-CONTRACTS.md) and [decision log](DECISIONS.md). Open foundational questions are contract packaging/key rotation, explicit linked-owner lifecycle, trusted non-model task ingress, grant revalidation at the destination, revocation race semantics across databases, receipt retention/deletion replay, and mixed-version recovery.

The minimum navigation path remains each repository's `docs/README.md` → `docs/current-state.md` → owning subsystem README/contract → relevant code and tests. These stabilization records are suite coordination evidence, not a replacement for those canonical status pages. Size/hotspot inventories and current CI verification are delegated baseline deliverables, not claims established by this architecture-only pass.

## Verification of this checkpoint

Worker draft only. References and proposed decisions require primary-session review before acceptance. Linked companion documents were not completed when the worker was stopped. No gate is closed by this draft.

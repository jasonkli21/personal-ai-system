# Phase 36 verification model

This model was established on 2026-10-12 before implementation. The written
[plan](../personal-ai-next-scope-detailed-implementation-plans/plans/phase-36-implementation-plan.md)
and Phase 32–35 evidence govern coverage; code governs the tested boundary.

- Verification is a versioned, strict JSON matrix. Each normative family has
  executable references or an explicit blocker pointing to its original owner.
  `passed` requires all selected parameter cases to execute successfully;
  failures dominate, skips/missing cases remain `unverified`, prerequisites can
  be `blocked`, and `not-applicable` requires a rationale. No external row can
  be closed by the offline runner.
- Evidence classes are `offline`, `local`, `cloud`, `live`, `domain`, and
  `browser`. Local engine tests do not attest cloud concurrency, capacity, IAM,
  costs, or service semantics. Critical privacy/isolation/paid-overflow/authority
  failures and high lifecycle/duplicate-effect/admission failures block their
  capability. Missing mandatory evidence also keeps that capability unavailable.
- The matrix is an evidence index, not a second policy, usage, mutation, or
  persistence authority. Original Phase 9/10/14/15/19/20/25–35 obligations remain
  canonical. Reports and blocker ledgers are projections generated from rows.
- Automatic execution remains limited to offline rows. Separately executed
  `local`, `cloud`, `live`, `domain`, and `browser` evidence can be merged with
  `--external-evidence` only through the typed receipt manifest. A receipt binds
  its row/class, original authority and command, tested revision, matrix/source
  digests, environment/profile identities, artifact digest, freshness, operator,
  and required reviewer provenance. Missing, stale, mismatched, replayed, or
  malformed receipts cannot close a row; this path never provisions or runs an
  external environment.
- Production composition uses `create_app` -> generic application contribution
  catalog -> application registry and authentication middleware -> `main.lifespan`
  context contribution catalog -> FastAPI context dependencies -> planner/coordinator ->
  token-budgeted builder. Routing uses the persistence factory and API dependency
  -> P21 hard admission -> strategy -> P19 reservation/claim/settlement. The
  synthetic app supplies two typed providers, sensitivity and exact scoped
  permission dependencies, and shared launch/action policy through registration.
- DynamoDB owns timeline/runtime/jobs; Postgres owns memory/lifecycle, evidence,
  grants, proposals, routing and usage; GCS owns private bulky bodies with
  Postgres references. Cross-store atomicity is not assumed. No schemas or
  historical migrations are changed for verification metadata.
- Fixtures inject faults at existing prepare/count/dispatch/finalize/reuse seams:
  revocation, stale revisions, malformed output, quota loss, cancellation,
  DB/network/body failures, partial publication, uncertain effects and profile
  churn. Only synthetic records and mocked/local stores are used; no paid/live
  dispatch, provisioning, or destructive external effects are authorized.
- Confirmation binds exact validated intent; P31 reconciles unknown effects with
  the original operation key. Routing physical sends, auxiliary counts and
  cascade lineage retain P19/P21 identities. Credentials, actor and owner,
  account/model/endpoint/serializer/cost/quota and source revisions remain distinct.
- Dependency currentness comes from existing federation, memory, research and
  artifact authorities, including later history/summary/cache reuse. Original
  source records remain authoritative; consolidation and compression are derived.
- Every declared integrated threshold projects to an explicit `passed`, `failed`,
  or `unverified` gate. Combined sequential pipeline measurements cover the
  implemented narrowing, search rewrite/packing, memory retrieval/build and
  internal routing paths. Baseline and candidate latency distributions are
  evaluated separately; post-builder source support, conflict visibility,
  authority scope and dependencies are asserted on the coupled held-out fixture.
  These remain synthetic proxy results, not a promoted end-to-end user workflow.
  Missing live quality, physical quota, native-store operations/headroom or
  assisted-planner observations remain `unverified`; unknown values are not zero.
- Bounded soak measures accumulated synthetic runtime, memory/views/jobs,
  research metadata, routing records and artifact bodies before revoke/expiry/
  cleanup. Native capacity/storage/deletion-aware restore stay external gates.
- The detailed plan index ends at Phase 36; there is no written Phase 37 plan.
  Future domain dispatch, client acceptance, native-store operations and learned
  strategy promotion consume existing seams and this evidence index, not a
  Phase 36 runtime wrapper.
- Review should challenge matrix completeness, parameter-case attribution,
  skipped evidence semantics, exact source/configuration binding, synthetic
  quality claims, aggregate overhead, store cleanup claims and any apparent
  release-ready inference from a disabled feature or a local fake.

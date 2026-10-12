# Phase 36 implementation plan — Integrated evaluation and hardening

Renumbered from former Phase 28. This revision preserves the complete release/operational scope, Phase 10 polyglot data-plane hardening, ChatGPT/domain safety gates, and synthetic app/provider conformance, while converting the phase into an explicit executable verification program with coverage ownership, failure injection, quality/resource thresholds, and release-blocking semantics.

## Scope boundary

**Goal:** Validate that the complete multi-app, multi-provider, strict-free, polyglot-persistence Personal AI platform composes safely and predictably before deeper feature expansion.

Phase 36 should add very little new product behavior. Its primary outputs are:

- regression/conformance suites;
- fault-injection fixtures;
- cross-boundary integration tests;
- benchmark/evaluation results;
- release evidence;
- operational/recovery checks;
- documented blockers;
- targeted fixes for discovered defects.

### Normative commitments

Evaluate all former Phase 28 dimensions:

- application/workspace isolation;
- context relevance and omission;
- provenance/authority confusion;
- permissions, grants, revocation, and derived-context reuse;
- mutation validation/confirmation/idempotency/uncertain outcome;
- strict-free enforcement;
- provider failure/exhaustion/change/removal;
- quota accounting and cascades;
- sensitive routing;
- storage growth/retention;
- artifact authorization;
- deletion/export propagation;
- cross-cloud timeout/retry/cancellation;
- local-vs-cloud semantic gaps;
- ChatGPT credential/bridge/auth/account/model/consent/usage/interruption/explicit-routing/context-minimization/attribution/action boundaries;
- extensibility through synthetic application/provider/task/validator fixtures.

Additionally validate the Phase 32–35 optimization layers together:

- assisted planning cannot widen permission;
- search/evidence compression preserves support/provenance;
- memory retrieval/consolidation cannot resurrect revoked/stale/false context;
- adaptive routing cannot bypass hard admission;
- optimization fallbacks compose deterministically.

### Acceptance criteria

Before any affected capability is described as release-ready:

- no known cross-app/workspace isolation failure;
- no known paid-overflow or sensitivity-unsafe fallback;
- no public/unauthorized artifact path;
- no canonical record class in two stores;
- no bulky raw output accidentally stored in operational/relational DBs where artifact tier is intended;
- provider/storage/network failures degrade explicitly;
- deletion/revocation propagates through derived context;
- mutation uncertain outcomes reconcile safely;
- Firestore is absent from normal runtime after Phase 10 retirement acceptance;
- regression suites cover quality, privacy, mutation, resource, optimization, persistence, and extensibility behavior;
- mandatory external gates have truthful evidence or remain blockers.

### Explicitly out of scope

- new domain/product features;
- new provider families;
- major architecture rewrites;
- compliance/certification claims;
- performance optimization unrelated to a demonstrated release blocker;
- papering over missing external evidence by disabling the feature and calling it passed.

## Current state and reuse

Reuse:

- deterministic evaluation suites;
- Phase 10 persistence/migration verification contract;
- Phase 14 provenance/inspection;
- Phase 15 policy/revocation;
- Phase 18–24 provider/routing/quota/evaluation/cascade contracts;
- Phase 20 artifact tier;
- Phase 25 ChatGPT/sidecar contracts;
- Phase 26–29 domain integrations;
- Phase 30 federation;
- Phase 31 mutations;
- Phase 32 planner baseline/assisted traces;
- Phase 33 evidence evaluation;
- Phase 34 memory retrieval/consolidation evaluation;
- Phase 35 adaptive routing evaluation.

Existing historical Phase 9/account/release obligations remain owned by their original evidence/checklists and must be closed truthfully rather than duplicated or declared complete by renumbering.

## Phase 10 storage dependency

Exercise the three-store target explicitly:

```text
DynamoDB
- conversation/runtime timeline
- checkpoints/idempotency assigned by Phase 10

Postgres + pgvector
- memory/provenance/lifecycle
- research/decisions/proposals/control/evaluation metadata
- federation grants
- compact queryable summaries

GCS
- private bulky artifact bodies
- raw permitted evaluation/trace/export/replay material
```

Validate:

- ownership;
- cross-store references;
- no assumed cross-store transaction;
- idempotent/recoverable retries;
- Postgres migrations/connection/resource behavior;
- pgvector compatibility;
- DynamoDB access patterns/hot-key/capacity/conditional-write semantics;
- GCS authorization/retention/operation count;
- export/deletion propagation;
- local-vs-real-service differences;
- cross-cloud failure behavior;
- Firestore retirement.

## Prerequisites

Required phases: 20, 25.4, 30, 31, 32, 33, 34, and 35, plus the standing Phase 10 foundation and prior provider/routing/policy phases.

## Invariants

- Offline deterministic evidence and real external/cloud evidence are reported separately.
- Strict-$0 applies to models and supporting GCP/Neon/AWS/network resources where the project claims strict-free operation.
- Security/privacy/isolation failures block the affected release.
- A disabled capability with missing mandatory verification is **unavailable**, not passed.
- No test fixture may grant broader authority than production contracts.
- Fault injection must not silently create real paid/provider/domain side effects.
- Synthetic conformance proves seam extensibility, not live provider/domain acceptance.

## Verification program contract

Phase 36 must maintain a machine-readable or structured verification matrix. The implementation may choose repository-appropriate YAML/JSON/Markdown plus runner code, but each required row must identify:

- verification ID;
- requirement/boundary;
- scenario;
- preconditions;
- offline/local/cloud/live classification;
- fixtures/environment;
- expected result;
- release-blocking severity;
- command/test reference;
- evidence artifact/reference;
- last tested revision/configuration;
- status: `passed`, `failed`, `blocked`, `unverified`, or `not-applicable` with rationale.

Skipped external checks are `unverified`, never `passed`.

## Initial verification matrix categories

The concrete matrix should include at least these scenario families.

| Boundary | Example scenario | Required result | Release-blocking |
| --- | --- | --- | --- |
| App/workspace isolation | Travel request attempts Finance context without grant | deny before source fetch/disclosure | yes |
| Federation | grant revoked after prior derived context | fresh and derived reuse blocked | yes |
| Context planning | assisted planner proposes unauthorized field/provider | rejected/narrowed; deterministic safe plan | yes |
| Search evidence | compressed evidence loses source support | strategy rejected/not promoted | yes for promoted path |
| Memory | revoked source remains in consolidated/packed memory | invalidated/excluded | yes |
| Memory | contradictory memories consolidated into false certainty | conflict preserved/no unsafe merge | yes |
| Routing | adaptive strategy ranks ineligible endpoint | impossible because candidate not supplied | yes |
| Strict free | free quota exhausted | no paid/BYOK/ChatGPT automatic fallback | yes |
| Cascade | validator failure triggers retry/escalation | bounded/accounted eligible attempt only | yes |
| Mutation | duplicate Apply/retry | one authoritative effect or safe reconciliation | yes |
| Mutation | external outcome uncertain | same idempotency key reconciliation, no blind resend | yes |
| DynamoDB | concurrent conditional write race | exactly intended winner/idempotent behavior | yes |
| Postgres | migration/schema mismatch | explicit startup/operation failure | yes |
| pgvector | incompatible embedding space | fail closed/no mixed ranking | yes |
| GCS | unauthorized artifact access | denied | yes |
| Deletion/export | owner deletion spans all stores | propagation/reconciliation evidence | yes |
| Cross-cloud | AWS/Neon/GCS timeout | bounded timeout/cancel/retry semantics | yes |
| Provider change | endpoint/model removed | explicit unavailability/reselection under policy | yes |
| ChatGPT | credential absent/expired | capability unavailable, no silent alternate billing | yes |
| Synthetic app | fifth app registration | no generic planner/builder/runtime code branch | yes |
| Synthetic provider | added endpoint/profile | no provider-name generic routing branch | yes |

The final matrix should be more complete than this seed.

## Quality and resource release gates

Integrated evaluation must establish held-out thresholds for the promoted/default strategies actually in use.

At minimum track:

- supported-answer quality;
- context omission/irrelevance;
- evidence support correctness;
- false/stale/superseded memory rate;
- provenance/authority confusion;
- mutation correctness;
- planner/search/memory/routing extra calls;
- total tokens;
- total physical provider attempts;
- quota consumption;
- P50/P95 latency where practical;
- Postgres/DynamoDB/GCS operation/storage growth;
- strict-free headroom assumptions.

Optimization phases are not judged independently only; verify their **combined** cost and latency.

For example, an assisted planner + search rewrite + evidence compressor + adaptive router may each look inexpensive in isolation but still create unacceptable aggregate overhead.

## Failure-injection model

Build deterministic local fixtures for:

- timeout;
- cancellation;
- stale versions;
- quota exhaustion;
- malformed provider response;
- partial persistence success;
- retry after uncertain outcome;
- revocation between prepare/dispatch/finalize;
- artifact-store unavailable;
- database unavailable;
- cross-cloud network failure;
- cache containing now-revoked data;
- endpoint/profile configuration churn.

External destructive tests must use safe test resources and existing authorization.

## Work packages

### P36.0 — Integrated negative, quality, optimization, and polyglot-storage matrix

Create the structured verification matrix and runner mapping.

Exercise:

- app/workspace isolation;
- cross-app grants/revocation;
- relevance/omission;
- provenance/authority;
- Phase 32 planner proposal validation/fallback;
- Phase 33 evidence identity/compression/conflict behavior;
- Phase 34 memory retrieval/consolidation/invalidation;
- Phase 35 hard-filter/adaptive-strategy boundary;
- mutation confirmation/idempotency;
- strict-free exhaustion;
- cascades;
- provider/model change;
- DynamoDB/Postgres/GCS ownership/growth/retention/authorization;
- local-vs-cloud semantics;
- cross-store references;
- cross-cloud timeout/retry/cancellation.

Establish held-out integrated quality/resource thresholds.

**Acceptance:**
- Every normative boundary maps to at least one executable verification row or explicit externally gated blocker.
- Offline and external evidence are distinct.
- Promoted optimization strategies have integrated negative/regression coverage.
- No requirement is "covered" only by prose.

### P36.1 — Close existing operational, account, persistence, and recovery obligations

Use existing authoritative release obligations rather than duplicating them.

Verify lifecycle propagation across:

- DynamoDB messages/summaries/runtime events;
- Postgres memories/research/decisions/proposals/grants/control metadata;
- GCS artifacts;
- jobs/checkpoints;
- bounded replay/audit records.

Verify:

- provider accounting coverage;
- strict-$0 deployment assumptions;
- IAM/service credentials;
- telemetry redaction;
- backup/recovery strategy;
- migration/rollback documentation;
- resource admission;
- Postgres connection/resource limits;
- DynamoDB hot-key/capacity/conditional semantics;
- GCS retention/auth;
- no normal-runtime Firestore dependency.

**Acceptance:**
- Each obligation has truthful evidence or remains an explicit blocker.
- Fake/local parity does not close mandatory real-service gates.
- No accidental dual canonical ownership exists.

### P36.2 — ChatGPT/domain safety and final client gate

Test:

- credential absence/expiry;
- bridge caller authorization;
- auth/account changes;
- missing model/scope/eligibility;
- usage exhaustion;
- interrupted completion;
- explicit-only routing;
- no silent billing/provider switch;
- context minimization;
- revocation after prior package construction;
- attribution;
- Copy/Insert/Apply boundaries;
- mutation exact-confirmation behavior;
- supported-client distribution/plan-only billing/transport gates.

**Acceptance:**
- ChatGPT/domain clients cannot be promoted with failed eligibility, billing, caller, privacy, mutation, persistence-isolation, or context-revocation checks.
- A disabled unverified capability stays unavailable and is not reported as passed.

### P36.3 — Synthetic fifth-application conformance

Validate the completed Application Integration Contract with a synthetic fifth application.

Register:

- application definition/workspace semantics;
- at least two domain-typed context providers;
- sensitivity policy;
- shared sidecar launch;
- optional one cross-app export category;
- optional one safe versioned mutation operation through existing grant/proposal contracts.

Exercise the shared planner/builder/runtime.

The fifth application must require **no application-specific changes** to:

- generic planner;
- builder;
- inference runtime;
- authentication;
- shared sidecar;
- storage architecture;
- generic federation broker;
- generic mutation orchestration.

Application-specific definitions/providers/policy/adapters/validators are allowed and expected.

**Acceptance:**
- Extension uses registration/typed adapters/contracts rather than generic app-name branches.
- Permission denial/revocation, exact confirmation, authoritative post-state, and idempotency remain binding when exercised.
- No live fifth domain product is created or claimed.

### P36.4 — Synthetic provider/task/validator conformance

Reuse Phase 16/18/21/22 extension seams to add a synthetic provider/endpoint and task/validator fixture.

Vary:

- provider/model;
- account/credential scope;
- cost identity;
- endpoint/deployment;
- capability;
- quota bucket;
- quality evidence.

Exhaust free capacity and prove:

- paid/unknown-cost/explicit-only variants do not enter automatic routing/evaluation/cascades;
- BYOK remains representable but explicit-only;
- no provider-name generic branches are needed;
- registered validators execute without task/domain generic branches.

**Acceptance:**
- Extension is configuration/registration/adapter/fixture driven.
- Offline conformance never claims live provider/cloud/billing acceptance.

### P36.5 — Integrated soak/resource-growth and degradation checks

Using bounded synthetic/local fixtures and safe external checks where authorized, simulate longer-lived use:

- conversation/runtime growth;
- memory/consolidation growth;
- research/evaluation metadata;
- artifact retention;
- repeated routing decisions;
- revocation/deletion after accumulated derived state.

Measure resource growth and verify retention/cleanup policies.

Inject provider/database/artifact/network degradation and confirm:

- explicit errors or bounded fallback;
- no authority widening;
- no paid overflow;
- no uncontrolled retries;
- no stale sensitive cache reuse.

**Acceptance:**
- Resource growth has measured bounds/alerts or explicit open blockers.
- Failure modes remain bounded and observable.
- Retention/deletion semantics hold under accumulated state.

### P36.6 — Release evidence, blocker ledger, and closeout

Generate a consolidated release report from the verification matrix.

For each mandatory capability, report:

- passed local evidence;
- passed external evidence where required;
- unverified external gates;
- known failures;
- disabled capabilities;
- release blocker status;
- tested revision/configuration.

Do not collapse `unverified` into `passed`.

**Acceptance:**
- Release status is reproducible from the matrix/evidence.
- Known privacy/isolation/paid-overflow/authority failures block affected release.
- All claims in README/current-state/release docs match actual evidence.

## Release-blocking hierarchy

At minimum treat these as blocking for affected capabilities:

**Critical**
- cross-user/app/workspace unauthorized disclosure;
- paid/unknown-cost silent overflow;
- public/unauthorized artifact access;
- mutation without exact confirmation/authorization;
- deletion/revocation bypass;
- credential/secret leakage.

**High**
- false authoritative state caused by memory/evidence confusion;
- uncontrolled retry/duplicate external effects;
- adaptive routing bypassing hard eligibility;
- persistent stale sensitive derived context;
- canonical dual-store divergence.

Quality/resource regressions may block default promotion even when they are not security failures.

## Requirement coverage

All former Phase 28 commitments remain normative. Phase 10 adds explicit DynamoDB/Postgres/GCS/cross-cloud/Firestore-retirement hardening. Phases 32–35 add planner, evidence, memory/consolidation, and adaptive-routing optimization boundaries that Phase 36 now verifies together. Synthetic app/provider/task/validator conformance validates earlier extensibility rather than introducing it here.

## README maintenance

Review the repository-root `README.md` before closing. Update only when evidence changes current user/developer-visible truth.

## Targeted verification and closeout

Run all applicable backend/frontend/unit/integration/conformance/evaluation commands, lint, typecheck, build, and `git diff --check`.

Use deterministic fakes/synthetic fixtures for broad offline coverage. Credentials/network/private domain data must not be required for the offline suite. External cloud/provider/domain/browser checks are opt-in/explicitly authorized and skipped checks remain **unverified**.

Implementation/release evidence must record:

- matrix version;
- tested commit/revision;
- environment/configuration identities;
- commands/results;
- offline vs external status;
- quality/resource thresholds;
- failure-injection results;
- optimization strategy versions;
- storage/provider/account profiles;
- unresolved blockers;
- disabled capabilities;
- final release scope.

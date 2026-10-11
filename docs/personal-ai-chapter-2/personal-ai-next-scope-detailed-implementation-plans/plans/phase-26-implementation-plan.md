# Phase 26 implementation plan — Travel integration

Updated 2026-10-11 to align the original Phase 26 scope with the current `travel-app` integration state while preserving the complete context/routing/sidecar boundary from former Phase 18.

## Scope boundary

**Goal:** Validate the complete context + routing architecture on a lower-sensitivity domain application without breaking or prematurely rewriting Travel's already implemented Personal AI integrations.

### Normative commitments

- Implement Travel context providers.
- Exercise profile/current state/research/conversation/memory.
- Route through the shared inference runtime and add end-to-end tests/traces.
- Add the shared sidecar to trip/day/place views with active trip/day/entity plus relevant preferences/research.
- Make included trip context visible.
- Support Copy and safe draft insertion where appropriate.
- Keep itinerary writes out of the generic response path until Phase 31.
- Preserve Travel as the authoritative owner of trips, itinerary ordering/state, bookings/reservations, Travel authorization/validation, persistence, and final mutation/application.

### Repo-alignment commitments

- Preserve the existing typed HTTP boundary between Travel and Personal AI. Do not import `personal_ai.*` internals into Travel, couple Travel to Personal AI persistence schemas, or introduce a shared database as the integration mechanism.
- Treat the already implemented research, booking-document extraction/import, itinerary-proposal, and travel-comparison integrations as existing compatibility surfaces, not as proof that the Application Integration Contract is already complete.
- Do not mechanically migrate current direct Personal AI capability calls to `application_id = "travel"` merely because Travel is registered. Existing research, extraction, proposal, and comparison calls remain on their accepted standalone Personal AI application scope until a supported application-scoped replacement is intentionally designed, versioned, and verified.
- Do not assume `workspace_id = trip_id`, encode a trip identifier into a Personal AI workspace field, or otherwise invent Travel workspace semantics. Workspace remains optional/undefined until Travel explicitly adopts and versions a mapping.
- Preserve separation between public research/evidence and authoritative/private Travel state. Research evidence may inform reasoning but never becomes booking, reservation, itinerary, schedule, price, availability, or other canonical Travel truth merely by inclusion in context.
- Keep existing Travel AI feature gates independent from the new Application Integration Contract. A registry declaration or provider registration is not evidence that live identity, service IAM, provider privacy/data-use, or deployment gates have passed.

### Acceptance criteria

- Travel stays authoritative.
- Core has no Travel-specific orchestration branch.
- Provider route is inspectable.
- Existing direct Travel AI flows continue to behave under their accepted contracts unless this phase intentionally migrates one through a separately versioned compatibility design.
- No implementation relies on an invented Travel workspace mapping.
- App/application/workspace labels never substitute for authenticated owner authorization.

### Explicitly out of scope

- itinerary mutation execution;
- cross-app Health/Finance context;
- Travel database migration into Personal AI;
- unrelated new Travel product scope;
- opportunistic migration of existing Travel research, booking-extraction, itinerary-proposal, or comparison endpoints solely for naming/registry consistency;
- defining a universal `trip_id -> workspace_id` mapping without an accepted Travel-side contract.

## Current state and reuse

Travel already has locally implemented, separately gated Personal AI integrations for research, itinerary proposals, booking-document extraction/import, and travel comparison. Those flows use typed HTTP contracts through Travel's `PersonalAIClient` boundary and remain subject to their own feature, provider, identity, service-IAM, privacy, and deployment gates.

Reuse the current gated place-comparison and itinerary-proposal/booking-extraction capability boundaries. Preserve the accepted semantics of the existing research, extraction, proposal, and comparison contracts rather than re-implementing them through a new app-specific path merely to satisfy Phase 26.

Personal AI has a first-class Travel application definition/registry entry, but registry metadata does not by itself convert existing direct endpoints into Application Integration Contract capabilities. Current direct Travel capability calls remain separate compatibility surfaces unless explicitly migrated.

Authoritative trip/day/booking/reservation state comes from the external Travel app contract, not Personal AI storage. Research evidence remains separate from itinerary truth. Travel remains responsible for authorization, validation against current Travel state, preview, and canonical writes.

Before substantive implementation, pin the exact `travel-app` revision and the accepted versions of every existing Travel/Personal AI contract that can be affected. At minimum, inspect the Travel integration documentation, relevant ADRs/release evidence, `PersonalAIClient`, current auth/gating behavior, and the current Personal AI Application Integration Contract.

## Prerequisites

Required phases: 15, 21, and 24. Sidecar work additionally requires Phase 25.4. Phase 10 remains the persistence foundation. Baseline domain/backend work may proceed if optional ChatGPT external gates are still pending, but the phase is not fully complete while intended sidecar work remains pending.

Existing Travel research/proposal/extraction/comparison implementations are compatibility dependencies, not substitutes for these prerequisites.

## Phase-specific invariants

- Providers return bounded typed Travel-owned references.
- Public place evidence is never private booking authority.
- Generic model output cannot mutate itinerary state in this phase.
- Owner authority is server-derived. Browser-supplied owner identifiers, `application_id`, `workspace_id`, and service identity are not owner authorization.
- Service-to-service transport identity and Travel-user identity remain distinct.
- Private booking/reservation data raises effective sensitivity even when surrounding place/entity information is public.
- Original booking documents, confirmation codes, reservation notes, and other private source material are not automatically promoted into shared memory or broader context.
- Existing direct capability contracts are not silently re-scoped or rewritten.
- Travel identifiers may be represented by opaque/versioned references where required; do not disclose internal IDs to model/provider surfaces unless the pinned contract explicitly authorizes them.
- Any uncertain external effect follows the existing stable-identity/reconciliation discipline; this phase introduces no new write path.

## Work packages

### P26.0 — Travel-owned read adapters and contract pinning

Pin the external Travel application revision and the exact read contract used for Phase 26.

Authorize authenticated owner/application scope before retrieval. If workspace scope is absent, operate without it; if Travel later adopts a workspace concept, require an explicitly versioned mapping and membership check rather than assuming a trip is a workspace.

Add bounded typed providers for:

- profile/preferences;
- active trip;
- selected day;
- selected place/entity;
- itinerary state needed for read-only reasoning;
- booking/reservation state only where explicitly authorized and minimized;
- selected history;
- selected research/evidence;
- attributable AI memory where allowed.

Provider requests and responses must preserve enough identity/version/provenance to distinguish:

- Travel authoritative state;
- user-authored preferences/notes;
- Personal AI memory;
- external research/evidence;
- freshness-bearing external observations.

Reuse shared evidence/comparison semantics where applicable. Private booking context raises sensitivity even when surrounding place data is public.

Do not reuse the existing research question projection, proposal context DTO, booking-extraction envelope, or comparison request as a generic Travel context-provider wire format unless a deliberate compatibility review proves that the exact contract satisfies the Application Integration Contract. Those surfaces were designed for narrower tasks.

**Acceptance:**

- only authorized, bounded, typed Travel state is returned;
- public place sources are not treated as booking authority;
- no provider assumes a trip/workspace mapping;
- app/workspace scope does not substitute for owner authorization;
- existing direct capability contracts remain compatible;
- provider payloads preserve source authority, version/freshness, sensitivity, and permission dependencies needed by shared policy.

### P26.1 — Shared runtime integration, routing, and baseline

Register the Travel read capabilities through `ApplicationDefinition` and the shared Application Integration Contract. Prepare selected context via the shared planner/policy/builder and route through the shared runtime/ledger.

Trace:

- authenticated application scope;
- selected provider/capability;
- source authority;
- source/version identity;
- freshness/expiry;
- permission/grant dependencies;
- effective sensitivity;
- actual model/provider/endpoint;
- disclosure decisions and denials.

Exercise profile/current Travel state/research/conversation/memory through shared runtime paths without adding Travel-name branches to generic orchestration.

Extend synthetic end-to-end and evaluation baselines. Include fixtures that distinguish:

- public place evidence from private booking truth;
- current itinerary state from stale/revision-mismatched state;
- optional/absent workspace scope from authenticated owner scope;
- allowed versus denied booking context;
- selected Travel memory versus Travel domain state;
- application-scoped context providers versus existing standalone direct capability calls.

Existing proposal/extraction/research/comparison gates remain separate. Generic response performs no itinerary/booking write.

If migrating any existing Travel direct capability to application scope, do so only as an explicit sub-change with:

1. a versioned replacement contract;
2. a Travel-side compatibility design;
3. preserved idempotency/deadline/size/privacy semantics;
4. dual-path or rollback behavior where needed;
5. targeted regression coverage;
6. release evidence identifying the old and new contract behavior.

Do not make such a migration merely to simplify naming.

**Acceptance:**

- synthetic traces preserve source freshness/privacy and never write itinerary state through generic output;
- the runtime remains application-agnostic;
- no existing Travel AI flow is silently broken or re-scoped;
- denied or revoked Travel context is not disclosed through primary generation, summaries, embeddings, counting, artifacts, history, or other auxiliary paths.

**Reference integration acceptance:** Travel validates broad owner/entity context, optional workspace semantics, private bookings versus public evidence, and shared sidecar integration through the [Application Integration Contract](../../02-target-architecture.md#application-integration-contract). Work primarily implements/registers domain providers, policies, adapters, and validators. Any generic orchestration change must repair a demonstrated shared deficiency, remain application-agnostic, and retain synthetic-app compatibility; the complete Travel scope above remains required.

### P26.2 — Additive shared-sidecar hooks

After Phase 25.4, attach the shared sidecar to trip/day/place views with relevant trip/day/entity/preferences/research categories visible and narrowable.

The UI must:

- make included Travel context visible before disclosure;
- distinguish authoritative Travel state from external research/evidence where practical;
- show or omit sensitive booking/reservation categories according to authorization and policy;
- avoid implying that optional/absent workspace identity is authorization;
- support Copy and non-authoritative draft insertion only.

Do not duplicate sign-in or create an app-specific core orchestration branch. Reuse the shared sidecar/host launch and disclosure-policy hooks.

No generic sidecar action may directly create, edit, reorder, delete, confirm, or otherwise mutate itinerary, booking, reservation, or saved-place authoritative state. Existing narrow Travel proposal/apply flows remain separate until Phase 31 deliberately integrates them with the generic typed mutation framework.

**Acceptance:** shared sidecar previews included trip context, supports only safe actions before Phase 31, exposes no unauthorized booking category, and does not change the behavior of existing Travel mutation/proposal flows.

## Cross-repo compatibility checks

Before closing Phase 26, verify against the pinned Travel revision that:

1. Travel still owns canonical trip/itinerary/booking state and final writes.
2. The typed HTTP boundary remains the only cross-repo integration surface.
3. Existing research, booking extraction/import, itinerary proposals, and travel comparison still satisfy their accepted contracts or have an explicitly documented migration.
4. No new code assumes `workspace_id = trip_id`.
5. Live identity/service-IAM/provider/privacy/deployment gates are represented accurately as verified, unverified, or disabled.
6. Manual Travel workflows remain usable when Personal AI or any AI feature gate is unavailable.

## Requirement coverage

All eight former Phase 18 commitments remain represented across P26.0–P26.2. The 2026-10-11 alignment update adds compatibility and scope rules; it intentionally removes no original functional commitment.

## README maintenance

Review the repository-root `README.md` before closing this phase. Update it only if implementation in this phase changes the truth of user-visible capabilities, architecture, technology stack, prerequisites, local setup, cloud deployment, provider support, or current project status. Keep implementation mechanics in detailed docs rather than the README. If no README-visible fact changes, record that no README edit was required.

Also update the relevant cross-repo integration documentation when a contract, capability availability flag, workspace rule, authentication requirement, or feature-gate truth changes. Do not leave one repository claiming a live integration while the other still documents it as unavailable.

## Targeted verification and closeout

Run the applicable backend/frontend test, lint, typecheck, build, and established evaluation commands for the touched surfaces and finish with `git diff --check`.

Add targeted tests for:

- owner/application authorization;
- optional/absent workspace behavior;
- no implicit trip-to-workspace mapping;
- provider field/result/time/byte bounds;
- source authority and freshness;
- private booking sensitivity escalation;
- public evidence versus booking authority;
- revoked/denied context;
- standalone direct capability compatibility;
- sidecar visibility/narrowing;
- no generic itinerary write.

Add a new runner to documentation only when the implementing phase actually creates it. Use deterministic fakes and synthetic fixtures by default; credentials/network/private domain data must not be required for offline coverage. External provider/cloud/domain/browser checks are opt-in and skipped checks remain **unverified**, not passed.

Record actual files/interfaces, pinned Travel revision/contract versions, tested revision/configuration, command results, disabled gates, existing-direct-capability compatibility, and unresolved external checks in implementation/release evidence.

Completion requires every normative commitment and work package to be locally verified. An externally gated capability may remain unavailable with that gap explicit, but may not be described as complete.

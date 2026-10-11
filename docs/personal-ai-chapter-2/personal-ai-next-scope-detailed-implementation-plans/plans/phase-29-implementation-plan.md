# Phase 29 implementation plan — Health integration

Updated 2026-10-11 to align the original Phase 29 scope with the current `health-app` local preview/search/proposal architecture while preserving all former Phase 21 sensitive-domain requirements.

## Scope boundary

**Goal:** Integrate the most sensitive/flexible domain without weakening memory, provider, artifact, authorization, or mutation policy, and without mistaking Health's existing local AI preview model for the cross-service Application Integration Contract.

### Normative commitments

- Start with read-only Health providers.
- Support flexible structured profile and bounded time queries.
- Apply field sensitivity and strict provider eligibility using minimal context.
- Allow mutation proposals only under domain rules.
- Add read-only sidecar with human-readable sensitive context categories and narrowing controls where practical.
- Require Health authorization before a category can be offered.
- Prevent generic sidecar output from directly editing medications, conditions, measurements, or clinical records.
- Verify native-mobile SIWC support before mobile credential logic; preserve the Health roadmap regardless.
- Keep Health authoritative for canonical health state, authorization, validation, persistence, and health mutations.

### Repo-alignment commitments

- Preserve the current distinction between Health-local AI support and live Personal AI integration.
- `POST /ai/context` and `GET /search` are Health-owned local capabilities. Reuse their authorization/narrowing logic where appropriate, but do not treat either route as the Phase 29 cross-service provider transport.
- `AIContextPack` is not the Application Integration Contract wire model. Do not send it directly to Personal AI, import it into core as the generic provider schema, or treat its `owner_scope` value as an authorization credential.
- The Phase 29 provider projection must carry the full cross-service semantics required by Personal AI: server-derived scope, explicit purpose/category/operation authorization, domain/source identity and version, provenance/authority, temporal semantics, units, uncertainty, field-level sensitivity, permission dependencies, and bounded typed payloads.
- Preserve the current fail-closed live-message state until the supported contract is implemented and reviewed. Enabling `PERSONAL_AI_ENABLED`, `/assistant/messages`, service credentials, delegated-owner identity, or callbacks must be an intentional Phase 29 activation step with tests—not a side effect of provider registration.
- Health's existing owner-authored proposal flow remains distinct from AI-originated mutation proposals. Personal AI cannot submit or execute Health mutations in this phase.
- Cross-app Health context is deny-by-default.
- Sensitive Health information is not flattened into generic memory or an untyped global profile.

### Acceptance criteria

- Health is not flattened into memory.
- Cross-app Health is deny-by-default.
- Routing cannot weaken sensitivity.
- Sensitive verbose artifacts default to minimal/no retention.
- Unauthorized categories are denied before retrieval, not fetched and hidden afterward.
- The local `AIContextPack` preview is not used as the cross-service provider contract.
- Live Health/Personal AI messaging is enabled only after the versioned provider/auth/transport contract is verified.
- Generic inference cannot directly edit medications, conditions, measurements, or clinical records.

### Explicitly out of scope

- direct clinical-record mutation;
- generic medication/condition/measurement edits;
- treating local preview/search DTOs as the external wire contract;
- enabling AI-originated proposal submission before Phase 31;
- weakening existing memory extraction restrictions for medical/sensitive content;
- cross-app Health use without explicit authorization;
- adding native mobile credentials before SIWC/native credential mechanics are verified;
- migrating Health's canonical store into Personal AI.

## Current state and reuse

No live Health app/provider integration exists in Personal AI today.

Health currently implements:

- `POST /ai/context`: bounded owner-scoped local Health preview with item-level AI permission, active-state, temporal-validity, and narrowing checks;
- `GET /search`: owner-scoped search over current resources explicitly allowed for AI use;
- owner-reviewed typed action proposals applied through Health's explicit proposal flow;
- authenticated `/assistant/status` reporting the live Personal AI integration as disabled;
- `/assistant/messages` retained for client compatibility but returning a sanitized unavailable response until the Application Integration Contract exists;
- `PERSONAL_AI_ENABLED=false` with configuration rejecting live enablement;
- no configured live Personal AI endpoint, service credential, delegated-owner token, or callback.

These local capabilities are useful implementation inputs, but they are not the external provider contract.

Existing Personal AI memory policy deliberately rejects sensitive medical extraction. Health integration must not weaken it.

Reuse Health's established domain authorization, item-level AI permission, active/effective-time semantics, search/narrowing behavior, source/provenance data, typed domain models, and owner-authored proposal validation where appropriate. Build a separate provider projection that satisfies the Application Integration Contract.

Before implementation, pin the exact `health-app` revision and inspect:

- `docs/ai/personal-ai-integration.md`;
- current-state and API contract docs;
- local `/ai/context` implementation and `AIContextPack`;
- `/search`;
- assistant status/message routes and feature gating;
- Health proposal validation/apply services;
- authorization and item-level AI permission rules;
- time-series/measurement schemas;
- Personal AI's Application Integration Contract and sensitivity policy.

## Prerequisites

Required phases: 15, 21, 24; sidecar work additionally requires Phase 25.4. Phase 10 remains the persistence foundation.

Live Health activation additionally requires an accepted cross-service auth/transport design. A local context-preview test does not satisfy live owner delegation, service identity, provider privacy, or deployment verification.

## Invariants

- Unauthorized categories are not fetched then hidden.
- Most restrictive field sensitivity governs downstream.
- Medications/conditions/measurements/clinical records remain domain-owned and cannot be edited by generic output.
- Owner/application/workspace/purpose/category/operation authorization occurs before retrieval.
- Owner identity in a request or payload is not authorization.
- `AIContextPack.owner_scope` is not a credential.
- Local preview/search and external provider transport remain separate contracts.
- Cross-app Health use is denied by default unless explicitly authorized.
- Sensitive Health records are not copied into Personal AI as canonical state.
- Health data is not flattened into generic memory.
- Existing medical-memory extraction restrictions remain intact.
- Verbose sensitive artifacts default to minimal/no retention.
- Provider eligibility applies to generation and every auxiliary disclosure path.
- AI-originated Health mutations remain unavailable before Phase 31.
- Health may continue to forbid sensitive operations even after Phase 31 exists.
- Native mobile credential work remains separately gated on verified SIWC/native mechanics.

## Work packages

### P29.0 — Read-only typed Health providers and activation contract

Pin the external Health revision and define/version the cross-service read provider contract.

Do not reuse `AIContextPack` as the wire model. Instead, expose bounded domain-typed provider responses that preserve applicable:

- owner/application/optional-workspace scope;
- explicit purpose;
- category and operation;
- source identity/version;
- entity/item identity/reference;
- provenance and authority;
- effective/source/observed time;
- units;
- uncertainty/quality;
- active/inactive semantics;
- sensitivity and field-level sensitivity;
- permission dependencies;
- freshness/expiry where applicable.

Support flexible structured profile/category reads and bounded time queries without creating one untyped global Health object.

Provider operations should cover only intentionally selected and authorized categories, for example:

- profile/demographic or preference fields where allowed;
- conditions;
- medications;
- allergies/restrictions;
- measurements/time series;
- activity/sleep/nutrition or other domain modules present in Health;
- relevant history;
- explicitly permitted user-authored notes/context.

The exact capability set must be derived from the pinned Health revision rather than assumed from this list.

Authorize before fetch:

1. authenticated owner;
2. application scope;
3. optional workspace scope if defined;
4. purpose;
5. category;
6. operation;
7. item/field permission;
8. temporal/current-state validity as applicable.

The provider must fail closed before domain retrieval when category/operation authorization is absent.

Reuse local `/ai/context` selection/permission logic only behind a dedicated projection where its semantics are still valid. Do not serialize the local preview wholesale into Personal AI.

Keep cross-app use denied by default.

Define the live service/user auth transport before changing Health's current fail-closed assistant integration. Only after the contract is accepted and tested may this phase intentionally update:

- `PERSONAL_AI_ENABLED` semantics;
- Personal AI endpoint configuration;
- service credentials;
- delegated-owner identity;
- `/assistant/status`;
- `/assistant/messages`.

Provider registration alone must not make Health report a live integration.

**Acceptance:**

- Health responses are domain-typed, bounded, and never flattened into memory;
- authorization occurs before category fetch;
- `AIContextPack` is not the wire contract;
- field sensitivity/provenance/time/unit semantics survive projection;
- live assistant status cannot claim availability without a verified transport and capability;
- cross-app Health remains denied by default.

### P29.1 — Minimal sensitive context and routing

Authorize category before offering/fetching it.

Apply:

- field limits;
- time-window limits;
- result-count limits;
- byte limits;
- entity/item narrowing;
- required/optional semantics;
- sensitivity joins using the most restrictive applicable field/source classification.

Enforce eligible disclosure paths for:

- generation;
- structured generation;
- counting/tokenization services;
- embeddings;
- summaries;
- research/search queries derived from Health data;
- artifacts/traces;
- conversation/history;
- evaluation/replay;
- fallback/escalation.

Refuse if no endpoint can safely handle the selected data.

Explicit ChatGPT selection, BYOK, same-owner context, or application registration does not waive Health policy.

Keep memory extraction restrictions and source attribution intact. Do not automatically convert Health records or local preview items into Personal AI memories.

Sensitive verbose artifact retention remains minimal/off by default. Persist only compact metadata needed for audit/reconciliation when policy allows it.

Add fixtures that test:

- permission denied before provider call;
- mixed field sensitivity with most-restrictive join;
- bounded time series;
- units and effective/source time;
- uncertainty/quality;
- inactive/expired records;
- cross-app denial;
- auxiliary disclosure denial;
- revocation between planning and dispatch;
- no memory flattening.

**Acceptance:** sensitive categories are denied before calls; downstream sensitivity cannot be weakened; verbose retention stays minimal/off by default.

**Reference integration acceptance:** Health validates flexible domain-typed records, bounded time-series access, and field sensitivity through the [Application Integration Contract](../../02-target-architecture.md#application-integration-contract). Implement/register domain capabilities and policy rather than app-name branches or planner/builder/runtime/sidecar forks. Any shared deficiency repair remains synthetic-app compatible; all Health read, memory, artifact, proposal, and mobile gates remain binding.

### P29.2 — Sidecar and proposal hooks

After Phase 25.4, show only authorized human-readable Health context categories with narrowing controls.

The sidecar must:

- avoid listing categories the owner is not authorized to use;
- avoid fetching denied categories merely to decide whether to hide them;
- make sensitive inclusion explicit and human-readable;
- support bounded time/category narrowing where practical;
- distinguish domain Health state from Personal AI memory/research when both are present.

Allow Copy and permitted non-authoritative drafts only.

Do not directly edit medications, conditions, measurements, clinical records, or other authoritative Health state.

Medication/condition/clinical edits require a typed Phase 31 proposal plus Health authorization, validation, exact confirmation, idempotency, and authoritative post-state; Health may still forbid the operation.

The current Health owner-authored proposal flow may be reused as a domain validation/apply foundation later, but Phase 29 does not create an AI-originated proposal submission path.

Verify native-mobile SIWC mechanics before adding native credential logic. A blocked optional native-mobile lane must not block the baseline Health read architecture or web/service contract.

**Acceptance:** sidecar offers no unauthorized category or generic clinical edit; AI-originated mutation remains unavailable; mobile capability remains separately gated.

## Cross-repo compatibility checks

Before closing Phase 29, verify against the pinned Health revision that:

1. Health remains authoritative for canonical state and mutations.
2. `/ai/context` remains a local preview unless intentionally superseded and documented.
3. `AIContextPack` is not used as the cross-service wire model.
4. `/search` remains a Health-local feature unless explicitly integrated behind a typed provider.
5. `/assistant/status`, `/assistant/messages`, and `PERSONAL_AI_ENABLED` accurately reflect actual live capability.
6. No live integration is claimed without accepted service/user auth transport.
7. Existing owner-authored proposal flow remains distinct from AI-originated mutation.
8. Cross-app Health is denied by default.
9. Medical/sensitive memory extraction restrictions remain intact.
10. Manual Health flows remain usable when Personal AI is unavailable.

## Requirement coverage

All nine former Phase 21 commitments remain represented across P29.0–P29.2. The 2026-10-11 alignment update intentionally removes no original functional commitment; it clarifies the local-preview-versus-external-provider boundary and the activation gate.

## README maintenance

Review the repository-root `README.md` before closing this phase. Update it only if implementation in this phase changes the truth of user-visible capabilities, architecture, technology stack, prerequisites, local setup, cloud deployment, provider support, or current project status. Keep implementation mechanics in detailed docs rather than the README. If no README-visible fact changes, record that no README edit was required.

Update Health's Personal AI integration/current-state docs and Personal AI registry/current-state docs when provider availability, live assistant status, auth/transport, mobile gates, or configuration behavior changes. Cross-repo documentation must agree about whether live Health integration exists.

## Targeted verification and closeout

Run the applicable backend/frontend test, lint, typecheck, build, and established evaluation commands for the touched surfaces and finish with `git diff --check`.

Add targeted tests for:

- pre-fetch owner/application/purpose/category/operation authorization;
- item/field AI permission;
- local preview versus provider DTO separation;
- no direct `AIContextPack` interchange;
- bounded time-series access;
- source/effective time and units;
- uncertainty/quality;
- sensitivity join;
- cross-app denial;
- revocation;
- generation/counting/embedding/summary/artifact/history disclosure denial;
- no memory flattening;
- feature-gate/live-status correctness;
- no AI-originated mutation;
- sidecar category visibility/narrowing;
- native-mobile gate separation.

Add a new runner to documentation only when the implementing phase actually creates it. Use deterministic fakes and synthetic fixtures by default; credentials/network/private domain data must not be required for offline coverage. External provider/cloud/domain/browser checks are opt-in and skipped checks remain **unverified**, not passed.

Record actual files/interfaces, pinned Health revision/contract versions, tested revision/configuration, command results, feature-gate changes, disabled/unverified live gates, and unresolved external checks in implementation/release evidence.

Completion requires every normative commitment and work package to be locally verified. An externally gated capability may remain unavailable with that gap explicit, but may not be described as complete.

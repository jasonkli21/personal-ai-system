# Phase 27 implementation plan — Shopping integration

Updated 2026-10-11 to align the original Phase 27 scope with the current `shopping-assistant` application boundary and registered Personal AI capabilities while preserving all former Phase 19 project-state, evidence, constraint, routing, and sidecar requirements.

## Scope boundary

**Goal:** Validate project state, external evidence, deterministic constraints, and routed AI assistance through the shared Application Integration Contract without confusing registry declarations, domain lookup APIs, local fakes, or future mutation capabilities with a live Shopping integration.

### Normative commitments

- Implement Shopping providers.
- Feed structured requirements to product research.
- Preserve hard/soft constraints and saved/rejected products.
- Evaluate routing for extraction/rewrite/synthesis.
- Add shared sidecar to project/search/comparison/product views with explicitly selected products and active requirements.
- Show selected context before ChatGPT send.
- Support Copy and non-authoritative draft insertion.
- Keep shortlist/requirement mutations behind Phase 31.
- Keep Shopping authoritative for Shopping Projects, requirements, products/variants, offers, decisions, preferences, evidence, and canonical writes.

### Repo-alignment commitments

- Treat Shopping's existing `PersonalAIClient.generate(AIRequest) -> AIResponse` as the Shopping-owned boundary for AI-dependent generation work. Implement supported external transport behind an intentionally versioned contract; do not bypass the boundary with direct provider SDKs or imports of Personal AI internals.
- Preserve the deterministic fake as test/local infrastructure and the fail-closed unavailable behavior until a supported external contract actually exists. `PERSONAL_AI_MODE=external` is a deployment mode, not proof that the upstream integration is functional.
- Reuse the existing registered capability identities where they match this phase:
  - `shopping.product_context`;
  - `shopping.catalog_search`.
- Keep `shopping.product_action` unavailable for authoritative mutation in this phase. Its registry presence is not permission or implementation; authoritative Shopping changes remain behind Phase 31.
- Do not treat `/v1/domains/shopping/lookup` or the Shopping comparison domain as the transport for Project context, Shopping task generation, memory, or mutation proposals. That API remains a separate exact-lookup/comparison capability.
- Do not assume or encode a Shopping Project ID as `workspace_id`. A project is the natural workspace candidate, but the external mapping remains undefined until an accepted versioned contract specifies it.
- `application_id`, optional `workspace_id`, capability registration, and memory namespace are scope/metadata only; none grants owner/project permission.
- The `shopping` memory namespace is not by itself proof that Shopping memory read/write APIs exist.

### Acceptance criteria

- Recommendations reflect project state.
- Deterministic constraints remain authoritative.
- Personal AI does not own Shopping state.
- Registered Shopping context capabilities become usable only when backed by a real typed provider/transport and authorization path.
- `shopping.product_action` cannot perform authoritative writes before Phase 31.
- No implementation relies on an invented project-to-workspace encoding.
- The separate barcode/domain lookup route retains its existing semantics.

### Explicitly out of scope

- checkout, ordering, payment, or merchant account actions;
- authoritative shortlist/requirement mutation;
- arbitrary merchant crawling;
- treating public catalog/review/offer evidence as canonical Shopping Project state;
- using the existing domain lookup/comparison route as a substitute for the Application Integration Contract;
- inventing a generic memory API merely because the `shopping` memory namespace is registered;
- defining a project/workspace mapping without Shopping-side contract approval.

## Current state and reuse

Shopping is registered in Personal AI as `application_id = "shopping"` with optional workspace scope, `memory_namespace = "shopping"`, Shopping sensitivity defaults, two context-provider capabilities (`shopping.product_context`, `shopping.catalog_search`), one tool/action capability (`shopping.product_action`), and the Shopping comparison domain.

The three Shopping context/action capabilities are currently registry declarations rather than usable Shopping integration surfaces. The context providers and action are unavailable until actual provider/transport/permission wiring is implemented. Registration advertises identity and metadata; it does not grant authorization or implement behavior.

Shopping already has a local `PersonalAIClient.generate(AIRequest) -> AIResponse` boundary. Its deterministic fake supports local development/tests. Its external implementation is intentionally unavailable and fails closed rather than guessing an upstream route.

Personal AI's existing Shopping domain lookup/comparison API is a separate capability. It does not retrieve Shopping Project state, implement `shopping.product_context`, implement `shopping.catalog_search`, provide general Shopping assistant task generation, or accept Shopping mutation proposals.

Reuse current catalog-comparison, identity, evidence, deterministic filtering, ranking, saved/rejected-state, and project-requirements seams. Shopping project/requirements/shortlist authoritative state remains external and arrives only through authorized domain providers.

Before implementation, pin the exact `shopping-assistant` revision, inspect the Shopping `PersonalAIClient`, integration contract/ADR, current registry definition in Personal AI, the domain lookup/comparison contract, and the shared Application Integration Contract.

## Prerequisites

Required phases: 15, 21, 24; shared sidecar work additionally requires Phase 25.4. Phase 10 remains the persistence foundation.

The existence of Shopping registry metadata or the domain comparison API does not satisfy these prerequisites.

## Invariants

- Saved/rejected state is authoritative Shopping domain state.
- Hard constraints remain deterministic and cannot be weakened by model output.
- Soft preferences remain distinguishable from hard constraints.
- Current prices, merchant availability, reviews, promotions, and similar observations remain freshness-bearing external evidence.
- Generic sidecar output cannot mutate shortlist/requirements in this phase.
- Shopping authoritative state remains in Shopping's PostgreSQL domain store.
- Owner/project authorization is checked independently of application/workspace labels.
- Exact catalog/product/variant identity is preserved.
- Unknown/conflicting/stale required attributes remain unknown/conflicting/stale rather than being guessed into compliance.
- Public catalog data does not become current merchant offer/review/availability authority.
- Sensitive/private budget or preference data raises effective sensitivity as declared by policy.
- No internal Personal AI Python types or persistence schemas become Shopping's external contract.
- Any wire contract is versioned and mapped inside the Shopping-owned integration boundary.

## Work packages

### P27.0 — Shopping-owned project providers and external contract

Pin the authoritative Shopping application revision and define/version the read contract needed by Phase 27.

Implement the existing registered context-provider identities where applicable:

#### `shopping.product_context`

Expose bounded typed context for the active Shopping Project, including only explicitly authorized and selected data such as:

- project identity/reference;
- structured requirements;
- hard versus soft constraints;
- explicitly selected products/variants;
- saved products;
- rejected products and rejection state where relevant;
- bounded decision/history context;
- private budget/preferences only when policy permits.

#### `shopping.catalog_search`

Expose or orchestrate bounded catalog-search context consistent with Shopping's evidence/identity semantics. Preserve exact product/variant/entity identity, source references, freshness, and authority. Do not silently treat a catalog record as proof of a current merchant offer, review, inventory, price, or availability observation.

For every provider:

- authorize owner and project before retrieval;
- preserve application scope;
- use optional workspace scope only if the pinned contract defines it;
- preserve domain/source identity and version;
- include authority, freshness/expiry, sensitivity, field-level sensitivity where needed, and permission dependencies;
- bound fields, entity references, result count, bytes, time window, and timeout;
- preserve predictable explicit failures.

If a Shopping Project is adopted as workspace scope during this phase, the mapping must be explicitly versioned and accepted in both repositories. Do not derive it merely because a project ID exists.

Keep `shopping.product_action` registered but unavailable for authoritative writes until Phase 31. Phase 27 may prepare metadata/validation seams needed later, but must not expose a mutation execution path.

Define the supported transport consumed by Shopping's existing `PersonalAIClient` only after the upstream contract exists. The Shopping adapter must map versioned external DTOs into Shopping-owned request/response models rather than importing Personal AI internals.

**Acceptance:**

- bounded project/product context preserves domain ownership and exact identity;
- `shopping.product_context` and `shopping.catalog_search` have real backing behavior before being marked available;
- owner/project authorization is independent of app/workspace labels;
- no project/workspace mapping is invented;
- `shopping.product_action` remains non-executable for authoritative mutation;
- domain lookup/comparison remains a separate API.

### P27.1 — Research and routed task baseline

Feed structured Shopping requirements into bounded product research while preserving hard/soft distinctions.

Unknown/conflicting/stale required attributes remain failures or explicit unknowns rather than guessed values. Model output may propose interpretations or comparisons but may not override:

- deterministic hard constraints;
- saved/rejected project state;
- exact product/variant identity;
- current-evidence freshness requirements;
- Shopping authorization.

Route actual extraction/rewrite/synthesis tasks through the shared runtime/ledger. Keep deterministic filters authoritative.

Record:

- selected Shopping capability/context source;
- source authority/version;
- evidence freshness/expiry;
- evidence rights/usage metadata where applicable;
- effective sensitivity;
- hard/soft constraint evaluation;
- endpoint/model/provider actually used;
- task/validator identity and version;
- quality/evaluation baseline.

Use registered deterministic validators where appropriate for required fields, hard constraints, identity preservation, and cited evidence. Domain-specific validator registration is allowed; generic cascade/routing logic must not branch on Shopping names.

No unbounded merchant crawling or checkout.

Add fixtures covering:

- selected/saved/rejected products;
- hard versus soft constraints;
- exact product/variant identity;
- stale/current/conflicting evidence;
- provider unavailability;
- optional workspace scope;
- private budget sensitivity;
- domain lookup/comparison remaining distinct from Project context.

**Acceptance:** hard constraints, rejections, exact identity, and freshness-bearing evidence remain authoritative through routed fixtures.

**Reference integration acceptance:** Shopping validates deterministic constraints, evidence-heavy comparisons, and saved/rejected project state through the [Application Integration Contract](../../02-target-architecture.md#application-integration-contract). Work primarily implements/registers domain capabilities and validators. Generic orchestration changes must repair a demonstrated shared deficiency without app-name branches and retain synthetic-app compatibility; all existing research/routing/sidecar scope remains required.

### P27.2 — Additive sidecar hooks

After Phase 25.4, attach the shared sidecar to project/search/comparison/product views with explicitly selected products and active requirements visible before send.

The sidecar must make clear:

- which project/requirements are included;
- which products/variants are selected;
- which hard constraints are authoritative;
- when external evidence is stale/unknown where that distinction is material;
- what optional/private context will be disclosed;
- that inclusion does not authorize a write.

Enable Copy and permitted non-authoritative draft insertion only.

Do not:

- directly add/remove/save/reject products;
- edit requirements;
- convert model output into authoritative project state;
- call `shopping.product_action` as a write path;
- bypass Shopping commands/services.

Authoritative shortlist/requirement writes wait for Phase 31 typed proposals plus Shopping validation/confirmation/idempotency.

**Acceptance:** selected context is visible and narrowable, sidecar cannot mutate authoritative Shopping state before Phase 31, and unavailable/denied Shopping capabilities fail closed.

## Cross-repo compatibility checks

Before closing Phase 27, verify against the pinned Shopping revision that:

1. Shopping remains authoritative for project/product/offer/decision/preference state.
2. `PersonalAIClient` remains the app-owned generation boundary.
3. The deterministic fake remains test/local-only and production does not silently use it.
4. `PERSONAL_AI_MODE=external` corresponds to an actually supported adapter before live integration is claimed.
5. `shopping.product_context` and `shopping.catalog_search` availability flags match reality.
6. `shopping.product_action` remains unavailable for authoritative writes before Phase 31.
7. `/v1/domains/shopping/lookup` remains separate from the Application Integration Contract.
8. No project-ID-to-workspace encoding has been invented without a versioned cross-repo decision.
9. Manual/deterministic Shopping workflows remain usable when Personal AI is unavailable.

## Requirement coverage

All nine former Phase 19 commitments remain represented across P27.0–P27.2. The 2026-10-11 alignment update intentionally removes no original functional commitment; it makes the existing registered capability identities and app boundary explicit.

## README maintenance

Review the repository-root `README.md` before closing this phase. Update it only if implementation in this phase changes the truth of user-visible capabilities, architecture, technology stack, prerequisites, local setup, cloud deployment, provider support, or current project status. Keep implementation mechanics in detailed docs rather than the README. If no README-visible fact changes, record that no README edit was required.

Update Shopping's integration contract/ADR and Personal AI registry/current-state documentation when capability availability, transport, workspace semantics, or feature-gate truth changes. Cross-repo docs must not disagree about whether the integration is live.

## Targeted verification and closeout

Run the applicable backend/frontend test, lint, typecheck, build, and established evaluation commands for the touched surfaces and finish with `git diff --check`.

Add targeted tests for:

- owner/project authorization;
- application versus optional workspace scope;
- absence of an implicit project/workspace mapping;
- provider field/result/byte/time bounds;
- exact product/variant identity;
- hard/soft constraints;
- saved/rejected state;
- stale/unknown/conflicting evidence;
- private budget sensitivity;
- provider unavailability;
- correct capability availability metadata;
- domain lookup/comparison separation;
- no `shopping.product_action` authoritative write;
- sidecar disclosure and no mutation.

Add a new runner to documentation only when the implementing phase actually creates it. Use deterministic fakes and synthetic fixtures by default; credentials/network/private domain data must not be required for offline coverage. External provider/cloud/domain/browser checks are opt-in and skipped checks remain **unverified**, not passed.

Record actual files/interfaces, pinned Shopping revision/contract versions, tested revision/configuration, command results, capability availability changes, disabled gates, and unresolved external checks in implementation/release evidence.

Completion requires every normative commitment and work package to be locally verified. An externally gated capability may remain unavailable with that gap explicit, but may not be described as complete.

# Phase 28 implementation plan — Finance integration

Updated 2026-10-11 to align the original Phase 28 scope with the current `personal-finance-and-investments` architecture while preserving the former Phase 20 high-sensitivity, read-only, provenance, routing, and sidecar boundaries.

## Scope boundary

**Goal:** Validate high-value structured Finance state with stricter provenance, minimization, semantic labeling, and provider policy while keeping Finance authoritative and keeping the existing extraction-oriented `PersonalAIClient` distinct from the new read-only Finance context-provider boundary.

### Normative commitments

- Start with read-only Finance providers.
- Distinguish observed/calculated/assumed/AI-interpreted data and use stricter provenance.
- Apply Finance-specific provider eligibility and allow no implicit mutation.
- Add read-only sidecar to portfolio/security/research views with narrow default scope.
- Make broader portfolio/account context an explicit visible inclusion choice.
- Preserve semantic labels in `ContextPackage`.
- Support Copy/save-as-draft/research-note only where domain policy permits.
- Do not execute trades or transactions from generic sidecar output.
- Keep Finance authoritative for financial records, calculations, validation, imports, review, private originals, provenance, persistence, and final publication/write workflows.

### Repo-alignment commitments

- Preserve the current Finance architecture: no shared database/object store and no imports of Personal AI internal Python modules.
- Do not repurpose `services/api/app/integrations/personal_ai.py::PersonalAIClient.extract` into the Phase 28 read-provider transport. It is an outbound candidate/extraction seam with Finance-owned request/candidate envelopes; it is explicitly not a frozen Personal AI wire contract or a generic portfolio-data interface.
- Keep candidate extraction and Finance read-context integration as separate capability contracts even if they share lower-level authentication/HTTP infrastructure later.
- Do not treat candidate envelope/schema validity as financial truth. Existing Finance validation, evidence checks, arithmetic, duplicate detection, review, and publication rules remain authoritative.
- Keep private originals in Finance. Phase 28 does not authorize sending raw statements, local paths, object-store references, or unrestricted source documents into generic context.
- Portfolio truth, AI memory/preferences, and external evidence/research remain distinct source classes.
- No model conclusion may become a canonical position, quote, transaction, tax lot, account balance, or other authoritative Finance record without Finance's validated domain workflow.
- Shared Personal AI outages must leave deterministic/manual Finance workflows usable.

### Acceptance criteria

- Finance remains authoritative.
- Ineligible endpoints never receive sensitive Finance context.
- Narrow selected-security/account scope is the default.
- No whole-portfolio disclosure occurs implicitly.
- The existing extraction `PersonalAIClient` remains semantically narrow and is not turned into a bidirectional catch-all integration layer.
- Read-only Finance provider contracts are independently versioned, authorized, bounded, and provenance-preserving.
- No trade, transfer, order, transaction, or canonical Finance write is reachable from generic inference/sidecar output.

### Explicitly out of scope

- trade/order/transfer execution;
- direct transaction mutation;
- mutation tools or generic Finance agent/plugin frameworks;
- speculative AI memory backfills;
- moving deterministic Finance arithmetic into prompts/models;
- replacing Finance relational authority with Personal AI persistence;
- sharing Finance's database/object store with Personal AI;
- using raw private statement originals as generic context;
- broadening `PersonalAIClient.extract` into a generic Finance read/write API;
- inventing live extraction transport as part of Phase 28 unless separately required by an accepted Finance use case.

## Current state and reuse

No authoritative Finance context provider is implemented in Personal AI today.

Finance has an intentional app-side `PersonalAIClient.extract` protocol for future structured extraction. That seam:

- accepts bounded text and Finance-selected schema identity;
- returns untrusted extraction candidates;
- has disabled and synthetic fake implementations;
- has no live HTTP adapter;
- has no database/publication methods;
- is not consumed by Stage 1 domain routes/services;
- is explicitly not the upstream wire contract.

That extraction boundary exists to support candidate generation followed by Finance-owned validation/review. It does not expose read-only account, portfolio, security, research, or semantic Finance context to Personal AI.

Reuse shared evidence/claims/decision/context contracts in Personal AI and Finance's existing provenance, source/as-of/quality, deterministic calculation, authorization, and validation semantics. Add read-only context adapters only after the external Finance read contract is pinned.

Finance may keep saved research sessions, approved result/evidence snapshots, app settings, and user-authored thesis notes in its own store. Those are not automatically Personal AI memory or canonical portfolio truth.

Before implementation, pin the exact Finance revision and inspect:

- `docs/adr/0001-shared-personal-ai.md`;
- current Finance auth/deployment ADRs;
- `services/api/app/integrations/personal_ai.py`;
- account/portfolio/security/research schemas and authorization services;
- provenance/as-of/calculation metadata;
- current import/review/publication flows;
- Personal AI's Application Integration Contract and sensitivity/provider policy.

## Prerequisites

Required phases: 15, 21, 24; sidecar work additionally requires Phase 25.4. Phase 10 remains the storage foundation.

Real-data deployment must also respect Finance's own authentication/private-storage/deployment gates. A locally passing read-provider fixture is not evidence that live private Finance data is safe to disclose to configured model/search providers.

## Invariants

- Narrow selected-security/account scope is default.
- No trade/transfer/order mutation path is reachable from generic inference.
- Provider eligibility fails closed.
- Finance authoritative state is not copied into Personal AI stores as a substitute for Finance APIs.
- Authoritative account/portfolio snapshots are not stored as generic AI memory.
- Observed, calculated, assumed, and AI-interpreted values remain distinguishable end to end.
- Units, currency, as-of/effective time, source identity, calculation version, and uncertainty/conflict state are preserved where applicable.
- Currency conversions are never invented; conversion source/rate/as-of semantics are explicit when conversion is permitted.
- Private originals remain Finance-owned and are not exposed by generic read providers.
- AI extraction candidates are not Finance read context and are not confirmed mutations.
- Model/provider output is never sufficient authority for canonical financial records.
- Provider, counting, embedding, summarization, artifact, and history disclosures all obey Finance sensitivity policy.
- Unknown authorization, provider privacy eligibility, or source semantics result in denial rather than best-effort disclosure.

## Work packages

### P28.0 — Read-only Finance boundary

Pin the Finance application/revision and the exact external read contract.

Define a Finance-owned read projection/provider contract that is separate from the existing outbound `PersonalAIClient.extract` seam.

The Phase 28 read contract must expose only authorized, minimal, typed Finance data needed for the selected use case, such as:

- selected account summary/context;
- selected portfolio summary/context;
- selected position/security context;
- selected research/thesis/evidence references;
- bounded historical/calculated metrics where explicitly requested;
- user-authored Finance preferences/settings only when policy permits.

Each value or field group must preserve applicable semantic metadata, including:

- observed / calculated / assumed / AI-interpreted;
- units;
- currency;
- as-of/effective timestamp;
- source identity/version;
- source/evidence references;
- calculation/model/method version;
- quality/uncertainty;
- unknown/conflict state;
- authority;
- sensitivity/field sensitivity;
- permission dependencies.

Authorize owner/account/portfolio/entity scope before retrieval. Do not accept a body-supplied owner as authority.

Apply explicit field/entity/result/time/byte bounds. Do not expose unrestricted account tables, transactions, tax lots, statement bodies, local paths, storage URLs, or private originals.

Keep read operations outside authoritative write/publication flows. The provider contract must have no method that can execute a trade, transfer, order, acceptance, import publication, or canonical record write.

If shared lower-level transport code is later reused between extraction and read context, preserve separate typed interfaces, capability IDs, request/response DTOs, authorization rules, and tests. Do not collapse them into a generic `PersonalAIClient.call(...)`.

**Acceptance:**

- read-only fixtures preserve semantic/source/as-of labels and domain truth;
- provider responses are bounded and minimal;
- private originals are never returned;
- existing extraction client/envelopes remain unchanged unless separately justified;
- no Finance write capability exists in the read contract.

### P28.1 — Sensitive preparation and routing

Register strict Finance field-disclosure rules, narrow windows/entity scope, and eligible-provider policy.

Explicit ChatGPT choice does not waive privacy or Finance authorization.

Include all disclosure paths in policy:

- generation;
- structured generation;
- token/counting services;
- embeddings;
- summaries;
- search/research queries derived from private context;
- artifacts/traces;
- conversation/history retention;
- evaluation/replay;
- any auxiliary or fallback endpoint.

Reject when no authorized/eligible endpoint exists. Unknown provider data-use/retention/cost/privacy facts fail closed where required by policy.

Retained verbose artifacts default to minimal/no retention for sensitive Finance context. Any persisted compact trace must avoid raw sensitive values unless explicitly required and authorized.

Enforce narrow-by-default preparation:

- selected security only where possible;
- selected account only where needed;
- selected portfolio slice rather than whole portfolio;
- bounded history window;
- explicit broader inclusion choice for account/portfolio expansion.

Preserve semantic labels through context selection, `ContextPackage`, endpoint-specific assembly, runtime/ledger trace, and sidecar disclosure metadata.

Add deterministic validation/evaluation fixtures for:

- semantic label preservation;
- units/currency;
- as-of staleness;
- calculation version;
- observed vs calculated vs assumed vs AI-interpreted;
- unknown/conflict values;
- whole-portfolio denial;
- provider ineligibility;
- denied auxiliary disclosure;
- source revocation.

**Acceptance:** ineligible primary or auxiliary disclosures and implicit whole-portfolio context are denied; semantic labels survive the complete preparation/routing path.

**Reference integration acceptance:** Finance validates strong sensitivity, narrow read-only defaults, and semantic value labels through typed [Application Integration Contract](../../02-target-architecture.md#application-integration-contract) capabilities/policy. Stricter behavior must not fork the planner, builder, inference runtime, or sidecar. Any shared deficiency repair remains synthetic-app compatible; complete Finance scope and domain authority remain binding.

### P28.2 — Read-only sidecar

After Phase 25.4, launch with narrow defaults and visible explicit broader inclusion.

Attach the sidecar to portfolio/security/research surfaces as appropriate. By default, prefer the current selected security or smallest relevant Finance scope.

Before send, show enough context metadata for the user to understand:

- which account/portfolio/security scope is included;
- when broader portfolio/account data has been explicitly added;
- semantic class where materially relevant;
- as-of/freshness status;
- whether external evidence/research versus Finance authoritative/calculated state is being used.

Preserve semantic labels in packages.

Allow Copy, save-as-draft, or research-note only where Finance domain policy permits and only to non-authoritative destinations. A saved draft/note is not a canonical position, quote, transaction, tax lot, balance, or trade decision.

Authoritative persisted actions require Phase 31 and may remain forbidden even there.

No trade/transfer/transaction/order endpoint is reachable from the sidecar.

**Acceptance:** sidecar cannot execute transactions or auto-save authoritative Finance state; broader context requires explicit visible inclusion; semantic/source/as-of distinctions remain inspectable.

## Cross-repo compatibility checks

Before closing Phase 28, verify against the pinned Finance revision that:

1. Finance remains the authoritative owner of records/calculations/import/review/publication.
2. `PersonalAIClient.extract` remains a narrow outbound candidate boundary rather than the read-provider contract.
3. Extraction candidates still require Finance validation/review before any publication.
4. Private originals remain Finance-owned.
5. No database/object-store sharing or Personal AI internal imports were introduced.
6. Manual/deterministic Finance workflows work with Personal AI disabled.
7. Live auth/provider/privacy/storage/deployment requirements are accurately documented as verified, unverified, disabled, or deferred.
8. The new read-provider contract cannot mutate Finance state.
9. Any research/note persistence remains distinct from canonical portfolio truth and AI memory.

## Requirement coverage

All ten former Phase 20 commitments remain represented across P28.0–P28.2. The 2026-10-11 alignment update intentionally removes no original functional commitment. It clarifies that the existing extraction-oriented `PersonalAIClient` is not the new read-context provider interface.

## README maintenance

Review the repository-root `README.md` before closing this phase. Update it only if implementation in this phase changes the truth of user-visible capabilities, architecture, technology stack, prerequisites, local setup, cloud deployment, provider support, or current project status. Keep implementation mechanics in detailed docs rather than the README. If no README-visible fact changes, record that no README edit was required.

Update Finance's Personal AI ADR/integration documentation and Personal AI current-state/registry documentation when the read contract, availability, auth requirements, or live/deployment gates change. Do not imply that the separate extraction capability became live merely because Phase 28 read integration exists.

## Targeted verification and closeout

Run the applicable backend/frontend test, lint, typecheck, build, and established evaluation commands for the touched surfaces and finish with `git diff --check`.

Add targeted tests for:

- owner/account/portfolio/security authorization;
- narrow default scope;
- explicit whole-portfolio expansion;
- field/entity/result/time/byte bounds;
- private-original exclusion;
- semantic classification preservation;
- units/currency/as-of/calculation version;
- unknown/conflict values;
- provider privacy eligibility;
- denial across generation/counting/embedding/summary/artifact/history paths;
- revocation;
- no mutation endpoint;
- separation from `PersonalAIClient.extract`;
- sidecar no-write behavior.

Add a new runner to documentation only when the implementing phase actually creates it. Use deterministic fakes and synthetic fixtures by default; credentials/network/private domain data must not be required for offline coverage. External provider/cloud/domain/browser checks are opt-in and skipped checks remain **unverified**, not passed.

Record actual files/interfaces, pinned Finance revision/contract versions, tested revision/configuration, command results, disabled gates, provider/privacy assumptions, and unresolved external checks in implementation/release evidence.

Completion requires every normative commitment and work package to be locally verified. An externally gated capability may remain unavailable with that gap explicit, but may not be described as complete.

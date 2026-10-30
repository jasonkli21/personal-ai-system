# PI-0 — Independent Architecture and Platform Boundary Review

**Repository:** [`jasonkli21/personal-ai-system`](https://github.com/jasonkli21/personal-ai-system)  
**Review date:** 2026-10-30  
**Source revision:** [`8571a8af33969f249614c2652a7d29c0c686f2d8`](https://github.com/jasonkli21/personal-ai-system/commit/8571a8af33969f249614c2652a7d29c0c686f2d8), `main` when reviewed  
**Intended in-repository path:** `docs/platform-independence/pi-0-review.md`  
**Review type:** independent code/documentation architecture assessment and **pre-implementation** PI-0 findings. This is NOT the eventual independent review of a Codex PI-0 implementation.

**Document role:** supplied *pre-implementation reviewer assessment*. Its title
refers to the initial architecture review, not independent post-implementation
PI-0 acceptance. The implementation reconciliation below is by the implementer.

## 1. Review verdict

**PI-0 planning disposition: PROCEED WITH NON-RUNTIME PI-0 ONLY.** The platform has useful, real extension seams and substantial invested correctness work. It is not yet demonstrably application-independent as a default distribution. PI-0 should pin and reconcile a baseline, establish code-enforced architectural expectations where safe, and preserve inherited security/review gates. It must **not** prematurely implement PI-1 or modify the live memory behavior.

The primary refactoring target is **composition/packaging**, not a rewrite of chat, memory, context, routing, task state or persistence. A second critical target is **consumer access**: applications should use a stable documented protocol rather than private in-process Python types. Memory cross-app reuse must be a later **authorized view**, not removal of scope checks.

### Findings summary

| ID | Priority | Finding | Owner / target phase | Nature |
| --- | --- | --- | --- | --- |
| PI0-F01 | P1 | Default application registry includes four toy manifests and capabilities | Registry / PI-1 | Architectural coupling |
| PI0-F02 | P1 | Default context runtime auto-installs all four source adapters | Composition / PI-1 | Architectural coupling |
| PI0-F03 | P1 | Generic app factory always mounts domain/proposal/extraction routes and reconciles domain task metadata | API packaging / PI-1 | Architectural coupling |
| PI0-F04 | P1 | Gemini-specific normal generation, counting, summaries and memory composition coexist with neutral contracts | Inference composition / PI-3 | Portability |
| PI0-F05 | P1 | Cross-app personal memory is not an authorized generic capability | Memory access policy / PI-4 | Product gap, *not* privacy defect |
| PI0-F06 | P1 | MEM-2 is narrow, default-off, not fully accepted; inherited safety/evidence blockers remain | Freeze discipline / PI-0 + separate MEM acceptance | Release gate |
| PI0-F07 | P1 | Real external fifth-app portability is not established by synthetic in-process test | API / PI-2 | Acceptance gap |
| PI0-F08 | P2 | Domain/federation metadata contains hard-coded source→destination suite cases | Domain contributions / PI-1 | Coupling |
| PI0-F09 | P2 | Search contract is extensible but installed search options are limited and app-neutral interface incomplete | Search / PI-5 | Capability/portability gap |
| PI0-F10 | P2 | Persistence factory/settings are broad and include example-specific configuration | Deployment/DI / PI-1/7 | Operational friction |
| PI0-F11 | P2 | Free-tier economics and multi-provider behavior not proven by external acceptance | Routing/eval/ops / PI-3/6/7 | Evidence gap |
| PI0-F12 | P2 | Current docs encode older chapter/suite vision; PI doctrine and freeze need a single routed home | Docs/PI-0 | Governance |

**Priority convention:** P1 = material blocker to independence/program advance, not an emergency vulnerability in a currently deployed system. P2 = important maintainability/evaluation issue. No exploitable security defect is claimed based solely on these code excerpts. Rank can change after live tests or adversarial independent review.

## 2. Evidence and assessment methodology

The reviewer inspected the GitHub-connected repository's current branch, commit history, recursive source/document tree, selected source files, test files, `docs/current-state.md`, `docs/memory/*` and stabilization architecture decisions. No container clone was available in this environment, so **pytest, lint, static scanner, native Postgres/Dynamo, runtime start, network/CI verification and cloud tests were NOT run by this review**. Prior repository verification counts are attributed only to their reports and are *not* reproduced here. Not every file was manually audited; this is a targeted architecture review, not a comprehensive exploit audit. A PI-0 Codex session with a local checkout must reproduce the specific assertions and challenge the source-level interpretation.

The latest commit sequence matters:

- [`2df112b`](https://github.com/jasonkli21/personal-ai-system/commit/2df112bf04b8d817c2cfee9c807786161d2fec4f) — MEM-1 implementation (default-off).
- [`7c8f267`](https://github.com/jasonkli21/personal-ai-system/commit/7c8f2671ffc163f803e781b9b34d6c81d466e8fa) — MEM-1 independent review remediation.
- [`c0add2b`](https://github.com/jasonkli21/personal-ai-system/commit/c0add2b15ec7dc6b4879bafdb0ec01e1b0eb68d6) — MEM-2 default-off controls.
- [`8571a8a`](https://github.com/jasonkli21/personal-ai-system/commit/8571a8af33969f249614c2652a7d29c0c686f2d8) — MEM-2 review remediation.

The **feature freeze at MEM-2** begins at the last source revision for this assessment. No newly proposed MEM-3/4/5/6/7 work is authorized. This does not imply MEM-2 received independent acceptance or production clearance.

## 3. Detailed findings

### PI0-F01 — Default registry makes optional applications core (P1)

**Evidence:** [`applications/registry.py:400+`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/applications/registry.py#L400-L460) constructs shared capabilities together with Travel, Shopping, Health and Finance declarations; [`backend/tests/test_applications.py:41-45`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/tests/test_applications.py#L41-L45) asserts that the default includes all five IDs. The registry supports external contributions but composes them *on top of* the hardcoded default.

**Impact:** default product taxonomy, policy surface, installed comparison domains and tests assume four particular consumers. A zero-example core is not the documented/tested default. **Corrective direction:** define a minimal first-party core registry and opt-in reference application contributions. Retain old import IDs under opt-in compatibility to avoid reinterpreting stored records. **PI-0 action:** inventory and decide ownership, not runtime edit.

### PI0-F02 — Source-tree fallback registers example runtime adapters (P1)

**Evidence:** [`context/deployment.py:11-29`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/context/deployment.py#L11-L29) calls four source-specific factories when entry points are not supplied. `ContextRuntimeContributionCatalog` itself is generic ([`context/runtime.py`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/context/runtime.py)).

**Impact:** distribution relies on toy integration source modules even when disabled. A feature flag protects execution but does not establish import/installation independence. **Corrective direction:** no fallback auto-enrollment; explicit installed plugin catalog; deny conflict, preserve current source permissions. **PI-0 action:** mark exact import/call edges and existing default flags.

### PI0-F03 — API factory and lifespan contain example-specific routes/assembly (P1)

**Evidence:** [`main.py:9-24`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/main.py#L9-L24) imports itinerary-proposal, booking-extraction and domain routers; [`main.py:50-115`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/main.py#L50-L115) always composes federation/task metadata and those routes. [`domains/registry.py:48-57`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/domains/registry.py#L48-L57) lazily but unconditionally creates Travel and Shopping modules when called.

**Impact:** `create_app` injection is useful but cannot yet be treated as a minimal independent distro with optional modules physically absent. **Corrective direction:** generic route/service registration and optional module startup paths. Preserve existing mutation reconciliation safety; do not disable legacy compatibility checks to make empty-core boot pass. **PI-0 action:** build dependency/startup route map and define empty-core acceptance test.

### PI0-F04 — Gemini composition bypasses neutral gateway choices in ordinary chat (P1)

**Evidence:** [`api/dependencies.py:180-185`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/api/dependencies.py#L180-L185) always instantiates `GeminiLLMClient`. [`api/dependencies.py:270-290`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/api/dependencies.py#L270-L290) embeds `GeminiTokenCounter`/`GeminiConversationSummarizer`; [`get_memory_adapter` at 315+](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/api/dependencies.py#L315-L322) uses `GeminiMemoryAdapter`. However [`llm/providers.py`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/llm/providers.py) already builds a pinned LiteLLM client based on provider, and the gateway has multiple provider profiles. This is **composition inconsistency**, not an absence of neutral abstractions.

**Impact:** switching primary AI provider in settings does not automatically mean all normal chat/context/memory paths use the same selected capability and budget policy. **Corrective direction:** a single policy-aware provider operation resolver; preserve embedding provenance and explicit count fallback uncertainty. **PI-0 action:** document exact call graph/ownership and list no-network seam tests for PI-3; do not switch in PI-0.

### PI0-F05 — Safe scoping exists; broadly useful shared personal memory does not (P1)

**Evidence:** [`auth/scope.py:80-123`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/auth/scope.py#L80-L123) defines scoped persisted records and deny workspace authority. [`context/authorization.py:51-105`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/context/authorization.py#L51-L105) rejects unauthorized cross-application selections. [`memory/services.py:375-433`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/memory/services.py#L375-L433) validates exact scopes on normal retrieval.

**Impact:** an unrelated application cannot simply reuse all same-user memories, which is **the correct initial security behavior**. The missing capability is a separately authorized cross-app *view* of select user-global context. **Corrective direction:** PI-4 starts with explicit global profile fields and grants, then source-verified views where warranted; no scope bypass or namespace flattening. **PI-0 action:** publish the policy distinction and negative acceptance cases.

### PI0-F06 — MEM-2 freeze and inherited promotion blockers (P1)

**Evidence:** [`docs/current-state.md`, MEM-0/1/2](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/docs/current-state.md#L33-L135), [`MEM-2 remediation report`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/docs/memory/mem-2-review-remediation-2026-10-30.md), and [`MEM-2 original implementation report`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/docs/memory/mem-2-implementation-report.md). MEM-2 is default-off, does **not** have a production model host or trusted live issuer/recoverable source lease, and has not closed separate independent acceptance or inherited MEM-0/1, Phase36 and cloud gates. Review remediation reports focused local tests and 36/36 synthetic control cases; those are not live product proof.

**Impact:** platform work must preserve safety/capacity/replay/erasure gates. Specific unresolved items include unbounded forget-receipt retention and recovery evidence, the 1,024 source tombstone/fence cap, native physical proposal cleanup and backup/replica deletion, provider-send uncertainty and proper host retry identities, actual owner/actor authentication, and independent acceptance. **Corrective direction:** freeze MEM-3+ and keep flags default-off. Carry blockers forward; no silent production promotion. **PI-0 action:** record this freeze in the new PI doc index and `docs/current-state.md` without changing memory code.

**Verification caution:** the remediation states a general `make backend-test-offline` attempt made an unauthorized Google API request. It should **not be rerun unisolated** just because its name includes “offline”. Run focused no-egress tests and record blocked checks until the source of egress is controlled.

### PI0-F07 — Fifth-app test is meaningful but not consumer portability (P1)

**Evidence:** [`test_phase36_integrated.py:79+`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/tests/test_phase36_integrated.py#L79-L180) constructs `synthetic_fifth` using `personal_ai` internal imports and factory injection. [`applications/README.md`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/applications/README.md) documents current entry-point contribution seams.

**Impact:** in-process dependency injection is a good sign but lacks deploy/install/API-version independence. **Corrective direction:** PI-2 requires a separately packaged app that uses only the public API, with true no-toy execution environment and authenticated scope. **PI-0 action:** classify current fifth-app suite as *in-process positive evidence only*.

### PI0-F08 — Federation and mutations retain specific example-case policy (P2)

**Evidence:** [`federation/deployment.py:14-55`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/federation/deployment.py#L14-L55) hardcodes four Health/Travel/Finance/Shopping source→destination cases. [`mutations/deployment.py`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/mutations/deployment.py) includes Shopping-oriented setup, though reusable mutations/reconciliation already exist.

**Impact:** domain-specific declarations risk setting architectural policy. **Corrective direction:** optional federation/task contributor metadata; avoid a second broker or state machine; keep operational confirmation/replay semantics. **PI-0 action:** inventory policy vs implementation vs authority.

### PI0-F09 — Search adapter extension exists, but app-facing retrieval still incomplete (P2)

**Evidence:** [`search/runtime.py`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/search/runtime.py) has `SearchAdapterRegistration`, `SEARCH_ADAPTERS`, `compose_search_adapter`; [`search/providers/brave.py`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/search/providers/brave.py) implements a carefully bounded snippets-only provider.

**Impact:** current small adapter set and research-first API are not yet independently proven as general app retrieval. **Corrective direction:** versioned retrieval/source/citation policies and a local corpus adapter; preserve copyright/rights and cost gates. **PI-0 action:** dependency + acceptance mapping.

### PI0-F10 — Broad settings and persistence composition impede minimal deployment (P2)

**Evidence:** [`settings.py:164-220`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/settings.py#L164-L220) contains example-specific URLs, audiences, enable flags. [`persistence/factory.py:32-65`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/backend/src/personal_ai/persistence/factory.py#L32-L65) includes itinerary and booking repositories alongside generic stores.

**Impact:** one cannot assume truly optional packages or lean config from current default semantics. **Corrective direction:** separate core vs installed extension config and repository factory contribution; decide physically later after dependency graph. **PI-0 action:** classify without breaking old env parsing.

### PI0-F11 — Cost claims and operation-level portability need real evidence (P2)

**Evidence:** `README.md`, current-state's routing/usage gates, LiteLLM adapter and memory/phase36 reports distinguish code and external acceptance. Explicit free-first provider usage policy must apply to generation, embeddings, counting, summary, search and retries, not only one text model.

**Impact:** hardcoded free-model assumptions, accidental paid fallback or unbudgeted ancillary calls could defeat the product goal. **Corrective direction:** PI-3 operation policy, PI-6 paired quality/cost evaluations, PI-7 reproducible local/cloud cost envelope. **PI-0 action:** define metrics and claim levels; do not run billable calls.

### PI0-F12 — Scope and authoritative docs need reconciliation (P2)

**Evidence:** [`AGENTS.md`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/AGENTS.md) gives an authority hierarchy and says domain apps own records; [`docs/README.md`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/docs/README.md) is the docs router; [`docs/memory/memory-architecture-and-research-roadmap.md`](https://github.com/jasonkli21/personal-ai-system/blob/8571a8af33969f249614c2652a7d29c0c686f2d8/docs/memory/memory-architecture-and-research-roadmap.md) still proposes MEM-3..7 as future research.

**Impact:** without a canonical platform-independence charter, Codex may interpret old integration plans or later MEM phases as immediately authorized product work. **Corrective direction:** add PI index, freeze note, phase ownership and status pointers. Preserve historical documents verbatim; mark proposed future MEM work as frozen in living router/status. **PI-0 action:** documentation edits only.

## 4. Architectural decision ledger (proposed for PI-0 ADR)

| Decision | Recommended decision | Status |
| --- | --- | --- |
| D-01 Product boundary | Core runs with no toy apps, examples are optional | **Recommended**; requires PI-1 proof |
| D-02 Extension mechanism | Reuse existing `ApplicationContributionCatalog`, `ContextRuntimeContributionCatalog`, context provider and mutation seams | **Recommended** |
| D-03 Memory freeze | MEM-2 boundary; no MEM-3..7 without explicit unfreeze | **User-directed; record as binding** |
| D-04 Privacy | No cross-app memory by default; explicit global-profile sharing before broader memory views | **Recommended** |
| D-05 Model composition | One operation-level provider resolver, preserving neutral ports and ledger | **Recommended**; PI-3 design review |
| D-06 Domain authority | Domain data/effects stay outside core; no schema-wide suite broker shortcut | **Existing principle** |
| D-07 Historical evidence | Preserve strict evaluator locks, tests, replay receipts, migration identity and open production gates | **Existing invariant** |
| D-08 External integration | Version small public app protocol, not private module integration | **Recommended**; PI-2 design review |
| D-09 PI-0 implementation | Docs, inventory, guardrails; no production runtime behavior changes | **Recommended** |
| D-10 Storage | No PG/Dynamo rewrite justified by independence alone | **Recommended**, revisit PI-7 |

None of these proposed decisions by itself indicates a completed migration. PI-0 Codex should verify conflicts with existing accepted ADRs before adding a normative decision record.

## 5. Architectural ownership map

| Capability | Canonical owner | Existing seam to reuse | Must not own |
| --- | --- | --- | --- |
| Authenticated principal/app/workspace | `auth`, middleware, `applications` registry | `RequestScope`, `ApplicationContextRequest`, `WorkspaceAuthorizer` | Domain user database or assumed email links |
| Context & disclosure | `context`, `applications` policy, source revalidators | `ContextAssembler`, `ContextRuntimeContribution` | Domain data or provider credentials |
| Persistent memory | `memory`, canonical repository/lifecycle | MEM-0/1/2 contracts and context provider | Raw third-party data, cross-app implicit reads |
| Model execution | `llm`, `routing`, `usage` | neutral generation/embedding ports, LiteLLM gateway | User consent or domain business rules |
| Search/evidence | `search`, `agents/research`, `entities` | search adapters, source rights, citation/research entities | Undocumented scraping or granting access |
| Confirmed effects | `mutations`, domain-owned registered adapters | durable idempotency, confirmation, reconciliation | Domain authoritative write transaction |
| Examples | optional packaged contributions | published plugin/API contract | `personal_ai` core modules |
| Persistence & deploy | `persistence`, storage adapters, infrastructure | existing factory and migrations | Separate shadow canonical databases |

## 6. PI-0 deliverables and exit checklist

A PI-0 Codex implementation should produce (under `docs/platform-independence/`): an index, this updated roadmap, findings baseline review, architecture/ownership ADR, reproducible dependency inventory and execution evidence. Add a **small AST-based import inventory/guard** if feasible with stdlib only; it must show existing intentional violations as tracked exceptions, detect at least one newly introduced forbidden import in a negative test, and separately disclose that import scanning cannot detect all dynamic loads/DI composition. If the guard would become a large refactor or break current CI, PI-0 may instead provide a reproducible inventory-only tool plus a recorded follow-up gate. Keep user-provided files intact.

**PI-0 accepted when:**

- The base/current HEAD and changed files are recorded.
- Runtime defaults, feature flags, existing gate status and tests are cataloged with exact evidence.
- Every P1 finding above is either corroborated with current source or explicitly corrected by inspection.
- No new memory features or model host wiring are added.
- No new provider/paid/remote calls, cloud deploy, schema migration or domain app edits are made.
- Existing docs authority is respected; prior evidence is not retroactively rewritten.
- Focused checks are run in isolated offline mode, or explicitly recorded as unavailable/blocked.
- Reproducible architecture/baseline artifacts can be independently checked before PI-1.

**Not accepted merely because:** a handoff exists, a synthetic fifth-app test passes, memory-control fakes pass, or a plugin can be declared in the registry. Those are helpful partial results, not the target product proof.

## 7. Recommended PI-0 execution and independent follow-up

Give the companion [`pi-0-sol-codex-handoff.md`](pi-0-sol-codex-handoff.md) to **Sol High** for a code-structure and authority-sensitive review/implementation; Sol Medium is reasonable if it follows the fixed scope and records escalated decisions without expanding work. After it lands, a **different session** should audit the new dependency inventory for missing dynamic imports, check that default runtime and safe security features are unchanged, reproduce the guards and question whether the proposed PI-1 extraction will work with the real startup/migration/reconciliation path. Do not treat this document as that second review.


## 2026-10-30 implementer source reconciliation (not independent acceptance)

Exact HEAD still matches `8571a8af33969f249614c2652a7d29c0c686f2d8`.
No new runtime revision needed reconciliation. The original assessment and
historical evidence above are preserved. The following dispositions narrow source
claims and assign concrete later gates; no PI-1+ feature is delivered here.

| Finding / severity | Rechecked source / correction | Remaining uncertainty and acceptance gate | Phase |
| --- | --- | --- | --- |
| F01 / P1 | `applications/registry.py:400`, comparison factory at 404; catalog extends base | Five manifests remain default; physically absent examples and old opt-in compatibility need proof | PI-1 |
| F02 / P1 | `context/deployment.py:11`, `context/runtime.py:32`, `backend/pyproject.toml` entry-point table | Both wheel registrations and fallback couple installation; removing fallback alone is insufficient | PI-1 |
| F03 / P1 | `main.py::create_app/lifespan`, `domains/registry.py:48` | Router/exception imports and retained mutation compatibility remain; absent-package lifespan test required | PI-1 |
| F04 / P1 | `api/dependencies.py:180,236,315`; `llm/context.py`, `llm/memory.py`, gateway count/embed | Neutral generation builder already exists; ancillary count/summary/embed portability and paid policy are unproven | PI-3 |
| F05 / P1 | `context/profile.py:199` already offers four whitelisted fields via destination shares; `context/authorization.py:51` and `memory/services.py` retain scope | Correction: narrow global-profile sharing exists. Broad memory views are not authorized. Reuse/validate profile and test explicit consent/revocation before any expansion | PI-4 |
| F06 / P1 | `api/memory_control.py:20`, control/knowledge services, migrations 028–031 and October 30 remediation | Missing production host/issuer/lease, capacity, provider-send, physical deletion and independent gates remain; no promotion | PI-0 freeze; separate MEM acceptance |
| F07 / P1 | `test_phase36_integrated.py` imports internal types and constructs `synthetic_fifth` | Local extension proof only; separately installed public-only consumer + auth negatives required | PI-2 |
| F08 / P2 | Federation `INITIAL_FEDERATION_CASES`; task deployment current/retained Shopping adapters | Declarative hard-coded pairs are not detected by import guard; preserve retained fingerprints and receipts during extraction | PI-1 |
| F09 / P2 | `search/runtime.py::SEARCH_ADAPTERS/compose_search_adapter` | Existing synthetic/Brave seams retained; app-neutral local/external retrieval and cost/rights proof pending | PI-5 |
| F10 / P2 | Settings and persistence factory; shared PG capability row decoders | Type-only imports also matter to packaging. Env names and historical rows require compatibility design | PI-1/7 |
| F11 / P2 | `llm/providers.py`, gateway, routing/usage contracts and owning evidence | No live cost, provider, identity or cloud gate reverified; strictly free operation is a target | PI-3/6/7 |
| F12 / P2 | New PI index, router link and one living current-state freeze note | Documentary routing addressed locally; independent baseline completeness review remains open | PI-0 |

The [inventory](pi-0-dependency-inventory.md) records 20 exact implementation-reviewed
static migration-debt waivers plus runtime/default/factory records. No broad waiver,
automatic new-edge acceptance or independent review verdict is implied. The
[report](pi-0-implementation-report.md) supersedes the initial no-local-check limitation
only for its explicitly executed checks; external limitations remain unchanged.

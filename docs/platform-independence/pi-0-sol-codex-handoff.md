# SOL MEDIUM/HIGH CODEX HANDOFF — Implement PI-0 Platform Independence Baseline

**Deliverable:** a bounded, reviewable PI-0 implementation in the `jasonkli21/personal-ai-system` working tree; architecture baseline, documentary authority, reproducible dependency inventory, and focused regression guardrails. **Do not implement PI-1 through PI-8.**

**Repo:** `https://github.com/jasonkli21/personal-ai-system`  
**Intended docs directory:** `docs/platform-independence/`  
**Reviewed starting point:** `8571a8af33969f249614c2652a7d29c0c686f2d8` (2026-10-30, commit message `Address MEM-2 independent review findings`)  
**Skill level:** Sol **High preferred** for authority/architecture reconciliation; Sol Medium suitable for careful, bounded implementation. One session, **no subagents needed**.  
**Execution model:** implement now, not another planning-only response. Do not ask for follow-up instructions when source is available. If head changed, rebase the review findings mentally against the working revision and explicitly record differences.  
**Inputs:** this entire document is self-contained. The companion `platform-independence-roadmap.md` and `pi-0-review.md` should be placed in the same docs folder if provided; if unavailable, this handoff contains sufficient requirements to do PI-0 without asking for them. Do not invent the previous documents' content or claim to have copied them when absent.

## 1. Product intent and non-negotiable boundaries

`personal-ai-system` is to become a **standalone, mostly-free, application-agnostic AI harness** for verified users. It supplies conversation orchestration, identity and access policy, shared personal context/memory, retrieval and search, model and tool execution, budget/usage management, evaluation and observability. **Travel, Shopping, Health and Finance are optional toy/example applications**, not product requirements. Eventually a separate arbitrary fifth app must use a public, versioned API without importing toy code or modifying the core. Nothing about the current target requires local model hosting or a new datastore.

**MEMORY FEATURE FREEZE:** New memory features are frozen **at MEM-2**. Current `MEM-0`, `MEM-1`, and `MEM-2` code and their original semantics, stored formats, fixtures, permission gates and default-off state are preserved. **Do not build MEM-3+ (episodic capture, dreaming, new retrieval research, promotion engine, autonomous memory governance), do not register a production model memory host, do not expand memory taxonomy or extraction behavior.** Existing review/production blockers remain explicitly open. PI-0 is not an independent MEM-2 acceptance.

**PI-0 is a documentary/diagnostic/baseline implementation:** the allowed production change budget is **zero** (no runtime behavior changes). Static tests or a lightweight diagnostic script may be added if they do not call providers or mutate data. Do not patch the default registry/context runtime, refactor providers, add an external API, migrate schemas, change auth, enable flags, or modify domain app repos. Those are later phases.

Treat `AGENTS.md`, code/tests/migrations, `docs/current-state.md` and dated verification records as authority, in that order subject to security. Do not overwrite source evidence or change strict evaluation locks for convenience.

## 2. State of repository: known, reviewed facts

At `8571a8a`:

1. `backend/src/personal_ai/applications/registry.py::default_application_registry` composes `personal_ai` plus Travel/Shopping/Finance/Health manifests and capability declarations, and loads `personal_ai.domains.registry` for comparison modules. Tests in `backend/tests/test_applications.py` assert the five-app default. `ApplicationContributionCatalog` already has entry-point support. **Decision:** preserve generic registration seam; move examples to opt-in composition only in PI-1.
2. `backend/src/personal_ai/context/deployment.py::default_context_runtime_catalog` falls back to registering four domain context contributions; `ContextRuntimeContributionCatalog` and `compose_context_runtime` are generic. **Decision:** eventually eliminate fallback import of toy adapters, do not prematurely remove it in PI-0.
3. `backend/src/personal_ai/main.py::create_app` installs the default application registry and always imports/mounts domain, itinerary and booking routes, and its lifespan reconciles federation/task metadata. `backend/src/personal_ai/domains/registry.py::registry()` creates Travel and Shopping modules. **Decision:** PI-1 needs explicit absent-package boot tests and compatibility-safe empty-core handling.
4. `backend/src/personal_ai/api/dependencies.py::get_llm_client` currently directly builds `GeminiLLMClient`. `get_context_assembler` uses `GeminiTokenCounter` and `GeminiConversationSummarizer`; `get_memory_adapter` uses `GeminiMemoryAdapter`. Yet `backend/src/personal_ai/llm/providers.py` and `llm/litellm/gateway.py` provide neutral/multi-provider generation. **Decision:** PI-3 unifies runtime composition without inventing a second gateway or modifying existing persisted vector spaces.
5. Scoped memory and context disclosure intentionally restrict app/workspace reads in `auth/scope.py`, `context/authorization.py`, `memory/services.py`, and revalidators. **Decision:** cross-app personal context belongs in PI-4 as consented sharing and explicit user-global views, not disabling security checks.
6. `backend/tests/test_phase36_integrated.py` has an in-process synthetic fifth app using direct `personal_ai.*` imports. **Decision:** credit it as partial evidence, but require a separately installed public-API consumer in PI-2.
7. `backend/src/personal_ai/federation/deployment.py` initializes explicit Health→Travel, Health→Shopping, Travel→Shopping and Finance→Shopping cases. `mutations/deployment.py` includes Shopping-specific task setup; domain writes/reconciliation have important existing safety guarantees. **Decision:** classify ownership and leave behavior intact in PI-0.
8. `backend/src/personal_ai/search/runtime.py` already has a synthetic and a Brave snippet adapter; generic retrieval exposure remains a later phase, with source rights/cost protections intact.
9. `backend/src/personal_ai/settings.py` and `persistence/factory.py` contain example-specific configuration/repository entry points. **Decision:** inventory rather than deleting fields that may still be referenced by historical data or optional examples.
10. `docs/current-state.md` (2026-10-30) explicitly describes **default-off MEM-2** with incomplete correction/issuer/host capability. `docs/memory/mem-2-review-remediation-2026-10-30.md` addresses review findings but retains independently open MEM-0/1/2, Phase 36, source-fence and receipt-capacity, native physical deletion/backup, source grants, actual provider send, cloud and production gates. Do not claim a production memory milestone.

Use the actual current checkout to recheck every assertion. Code-specific claims above are not an instruction to force evidence to match a stale revision.

### Key reading paths (use local checkout)

**Required:** `AGENTS.md`; `README.md`; `docs/README.md`; `docs/current-state.md`; `docs/architecture.md`; `stabilization/ARCHITECTURE-BASELINE.md`; `stabilization/DECISIONS.md`; `docs/memory/memory-architecture-and-research-roadmap.md`; `docs/memory/mem-1-contract-adr.md`; `docs/memory/mem-2-control-adr.md`; `docs/memory/mem-2-implementation-report.md`; `docs/memory/mem-2-review-remediation-2026-10-30.md`; `docs/memory/mem-2-independent-review-handoff.md`.

**Source and tests:** `backend/src/personal_ai/{main.py,settings.py}`; `api/dependencies.py`; `applications/{contracts.py,registry.py,README.md}`; `context/{runtime.py,deployment.py,authorization.py,providers.py,assembler.py}`; `auth/{scope.py,middleware.py,verification.py}`; `memory/{contracts.py,services.py,knowledge_service.py,control_service.py}`; `llm/{client.py,providers.py,litellm/gateway.py,memory.py,context.py}`; `search/{contracts.py,runtime.py}`; `federation/deployment.py`; `mutations/{deployment.py,service.py}`; `domains/registry.py`; `persistence/factory.py`; `backend/tests/{test_applications.py,test_application_scope.py,test_context_runtime_composition.py,test_phase36_integrated.py,test_memory_control.py,test_memory_control_api.py}`; `Makefile`; `.github/workflows/quality.yml`.

## 3. Implementation goals and ordered tasks

Work in the following order. Keep code changes narrowly limited to inventory/guard/testing. When documentation is present, update links and status without reauthoring historic evidence.

### Step 0 — Preflight, clean scope and source-of-truth reconciliation

- Run `git status --short`, `git rev-parse HEAD`, `git branch --show-current`, `git log -8 --oneline`. Preserve and do not clobber pre-existing modifications or untracked user files. Log the exact starting SHA and tree status in the PI-0 report. If HEAD is not `8571a8a`, inspect the delta (especially new memory code/flags) and update findings. Never reset or force checkout user work.
- Read required files above. Trace actual import and injection paths, especially plugin entry points, app factories, request scope, model service composition, store ownership, federation and schema-3 control gates. Distinguish code facts, synthetic test evidence, live operator evidence and future goals.
- List the exact default-off memory and external/provider flags from current `Settings` and frontend gates; do not blindly copy flag spelling from this prompt. Confirm no PI-0 change affects their defaults.
- Check that the `docs/platform-independence/` directory either does not exist or contains user work; merge safely. Do not rewrite or delete existing PI documents without identifying the conflict.

### Step 1 — Establish the canonical documentation route

Create or update:

1. `docs/platform-independence/README.md` — concise index: product definition, review base/current status, links to roadmap, PI-0 review, the architecture ADR, import/dependency inventory, implementation report, Sol handoff and eventual PI-1/2 docs. Explain that the `MEM-*` research roadmap is frozen after MEM-2, and these documents do not supersede memory security/production acceptance.
2. `docs/platform-independence/platform-independence-roadmap.md` — if supplied, reconcile and preserve the 9-phase **PI-0..PI-8** roadmap; if missing, create a concise canonical version directly from this handoff (requirements enumerated below). It must include first-principles product scope; app/core boundary; free-first but paid-extensible provider strategy; memory freeze; memory access vs storage distinction; exact non-goals; phase tasks and exit gates; 20+ cross-cutting negative/positive scenarios; evidence limits; sequencing, rollback and independent review.
3. `docs/platform-independence/pi-0-review.md` — if supplied, preserve and update source anchors as needed; if missing, create a source-backed findings ledger with at least F01–F12 from Section 2, evidence, severity, proposed phase, uncertainty, gate and correction. Clearly label this as the *pre-implementation reviewer assessment* rather than an independent post-implementation acceptance.
4. `docs/README.md` — add a task-route link for Platform Independence. Preserve all other routes.
5. `docs/current-state.md` — add **one concise, clearly labeled Platform Independence / freeze status** pointing to PI docs. State that PI-0 is architecture/documentation/diagnostics (if completed) and that PI-1+ are not delivered, MEM-2 is not promoted and MEM-3+ is frozen. Do not claim tests or deployed operations not run. Do not erase historical Chapter 2/Phase36 or MEM sections.
6. Optionally add a short README pointer only if consistent with the existing documentation router. Avoid adding a competing source of implementation truth.

**Naming:** all *new PI-specific* docs under `docs/platform-independence/`. Other subsystem ADRs, current-state and history remain in their established folders.

### Step 2 — Write the PI-0 architecture/boundary ADR

Create `docs/platform-independence/pi-0-architecture-decisions.md`. Include:

- Accepted product direction vs unproven target behavior, explicit review date and commit.
- A **capability ownership matrix** for identity/request scope, app registry, context, memory, inference, search/research, tools/mutations, evaluation, data and example integrations.
- **Dependency law:** optional example app -> published extension/API contracts -> core services -> neutral ports -> external adapters; core must not depend on example-specific modules. Distinguish imports, runtime loading and deployment/config registration; never assume feature-disabled means install-independent.
- Reuse existing `ApplicationContributionCatalog`, `ContextRuntimeContributionCatalog`, `ContextAssembler`, `GenerationClient`/`EmbeddingClient`, search contracts, usage/routing ledger, `MemoryRepository`/MEM-0/1/2, federation/grants, mutation confirmation/receipts and persistence factory. No second state machine or canonical store.
- Exact authorization vs capability definition: a registered app/provider/tool **does not grant** source access or model disclosure. Deny unknown operations/fields/workspaces; user-global context requires separate consent/revalidation.
- Decision status for **proposed vs committed** boundaries. State that the decision to freeze after MEM-2 comes from the user and is binding, while specific future API/packaging approaches remain provisional.
- PI-1 extraction choices needing later review: independent distribution/plugin packaging; registry default split; optional route and startup reconciliation; historical row compatibility; empty-core physically absent examples. Do not decide a change without source confirmation.
- PI-3 provider-composition choices needing later review: operation selection (generation/count/summary/embed/search), free-strict vs paid-opt-in, embedding-space compatibility.
- PI-4 memory policies needing later review: global-profile whitelist, app-local isolation, purpose/destination/field grants, source revocation, caches, old summaries and erasure.
- Rollback and threat considerations, especially historical data and in-flight task recovery.

### Step 3 — Produce an actionable dependency inventory, preferably machine-readable

Create `docs/platform-independence/pi-0-dependency-inventory.md` (optionally adjacent `.json` with stable schema and sorted entries). At minimum capture **exact current code anchors** for:

- core modules importing example modules; default registration/call paths;
- sample-specific API routes, comparison domain registry, federation and task declarations;
- Gemini-specific construction in normal generation, context counting/summarizing, memory extraction/embedding;
- app-specific env/config entries and repository factories;
- existing generic extension points and how they are installed;
- relevant tests, migrations, default-off flags and historical compatibility requirements;
- external status gates as claims from docs, explicitly not re-verified.

For each edge/finding record: `from`, `to`, `kind` (`static_import`, `runtime_import`, `default_registration`, `factory_call`, `route_mount`, `setting`, `state_contract`), owner, classification (`core`, `adapter`, `example`, `deployment`, `unknown`), compatibility risk, desired PI phase and evidence. **Import graph alone is insufficient**—capture dynamic imports/entry-point behavior and code-level composition separately. Use an allowed current-violation list; a newly documented edge is not automatically waived.

**Optional but preferred executable guard:** add a stdlib-only helper such as `backend/scripts/platform_dependency_inventory.py` plus tests `backend/tests/test_platform_dependency_inventory.py` to parse Python module imports using `ast`, map current import edges, emit deterministically sorted JSON, compare against a reviewed baseline/waiver inventory and fail on unexpected new forbidden *core -> example* edges. Explicit scope, no network, no rewriting of source. A waiver MUST have exact importer/imported module, rationale, owning phase, and review status; never a broad `personal_ai.*` wildcard. Validate with a synthetic fixture that inserts a new forbidden import and is correctly flagged, plus a known existing edge that is tracked as migration debt. Do not assert dynamic imports are fully covered by AST; enumerate known dynamic composition separately in docs.

If the inventory guard would require a new dependency, brittle file hashes or significant CI churn, **implement deterministic inventory only and document a P1 follow-up**; do not force production code changes to satisfy a speculative guard. Keep the tool import-safe (no `personal_ai.main` import on module import) and deterministic across file-order/platform differences. Add a `--check` or equivalent only if a tracked baseline exists and it's reviewed. Optionally wire it into the existing CI if narrow, stable and no network needed; record exact command.

### Step 4 — Define the PI-1/PI-2 independence acceptance contract, without implementing it

Create `docs/platform-independence/pi-0-exit-contract.md` or include in ADR. It must specify how a later reviewer proves:

- Core distribution works with **zero** installed toy modules, not merely their flags disabled.
- `create_app` lifespans, federation metadata, mutation reconciliation and router registration still function or fail clearly when examples absent.
- A generic builtin `personal_ai` conversation/context flow works through fake-only local API.
- One **separately installed** unrelated application using only documented public HTTP/SDK contract can authenticate and run read/turn workflows without private imports.
- Unknown app/workspace, forged actor/owner and unconsented app-to-app sharing fail closed.
- A second provider replaces Gemini in generation/count/summary paths under budgets without silently using Gemini; paid use opt-in only.
- Later PI-4 shares an explicit eligible user-global preference and denies another app's private or sensitive memory.
- A known entry from MEM-2 remains blocked by default and every old source/receipt/memory fence still protects replay, deletion and recovery.

Design tests and gate responsibilities, but DO NOT build these runtime features in PI-0.

### Step 5 — Safe verification and evidence report

Create `docs/platform-independence/pi-0-implementation-report.md`, including pinned exact **ending** SHA or working-tree source identity, changed-file list, code versus docs changes, exact commands, successes/failures/skips, waiver count (if any), permission/security gates and missing external evidence. A report is not a substitute for running checks when available.

**Safe minimum checks:**

```sh
# Run from repository root. Inspect diff and ensure no user files were touched.
git status --short
git diff --check

# If an import inventory/test exists:
python backend/scripts/platform_dependency_inventory.py --help
# Follow the tool's documented inventory/check command.

# Depending on environment, preferably with network egress blocked:
make backend-lint
cd backend && python -m pytest -q \
  tests/test_applications.py \
  tests/test_application_scope.py \
  tests/test_context_runtime_composition.py \
  tests/test_phase36_integrated.py \
  tests/test_memory_control.py \
  tests/test_memory_control_api.py
```

The focused set may require local environment dependencies; **report missing tooling and skipped cases truthfully**. If Python deps are absent, keep doc/check verification and list the exact blockers. Tests requiring local Postgres, Dynamo, Google/Gemini, other provider APIs, live cloud, external app credentials or browser acceptance are opt-in. Do not create production fixtures or use real personal data. Inspect `.env` usage and prefer test-specific env, no secrets in logs.

**Important safety note:** MEM-2 October 30 remediation recorded a `make backend-test-offline` attempt that made an **unauthorized Google API request**. Do **not** uncritically run the full supposedly offline suite without egress isolation and proof of provider-path stubbing. If an unexpected outbound request happens, stop that suite, identify the cause, and report it as open. No provider API calls, paid usage, cloud deploy or live database mutation are authorized by this handoff.

Run frontend typecheck only if you changed frontend routes or files (you should not need to). Confirm exact default memory flags and the historical planner/evaluation fixture identities remain unmodified. No need for a full expensive Phase36/CI matrix for documentation/static changes; label unrun gates explicitly.

## 4. Specific content required in the roadmap if not supplied

Create a self-contained PI charter with this phase sequence and no missing phase:

| Phase | Bounded goal | Required exit |
| --- | --- | --- |
| PI-0 | Reconcile + document + inventory/guard | Verified source-backed boundary baseline, freeze and reproducible checks |
| PI-1 | Zero-example core installation and optional composition | Core boots while example code physically absent; old example opt-in compatibility preserved |
| PI-2 | Public contract + separately installed fifth consumer | No private imports, core patches or unverified owner identity |
| PI-3 | Capability/policy provider composition | Two supported adapters; free-strict/paid-opt-in; budget, no silent ancillary Gemini use |
| PI-4 | Explicit, governed cross-app context via existing memory/profile | Consented user-global field works; app-private/sensitive denied; revocation and deletion tested |
| PI-5 | App-neutral retrieval/search/read-only tools | Local and permitted external source, provenance, citations, cost/freshness, partial status |
| PI-6 | Harness quality/cost/latency optimization | Paired tasks, held-out utility and security cases, known cost envelope |
| PI-7 | Operationally minimal local/cloud profiles | No credentials required for local fake mode; actual identity/cost/backup/deletion evidence distinguished |
| PI-8 | Independent readiness audit | Adversarial zero-example/fifth-app/provider/memory/replay audits and truthful status |

Roadmap must include source-backed current assessment, non-goals, module ownership, import direction, auth/security and canonical-state invariants, provider abstraction, memory governance and freeze, phase entry/actions/gates/rollback, a cross-phase acceptance matrix (at least 20 cases), risks, independent review protocol and documentation layout. Do not claim PI-1..8 done, do not silently thaw MEM-3+, and do not confuse portable synthetic checks with actual cloud/client security.

## 5. Negative requirements (must not happen)

- **No default-registry or context-deployment refactor in PI-0.** Do not start PI-1 because it looks easy.
- No removal of `travel`, `shopping`, `health`, `finance` packages, routes or settings in this phase.
- No new auth bypass, scope wildcard, memory namespace flattening, or permissive cross-app default.
- No new memory capture, schema, extraction/correction/consolidation policy, host tool registration or feature-flag enablement.
- No new provider hardcoding, paid fallback, live-model request or API secret handling.
- No changes to persistence/DB migrations, receipts, source tombstones, evaluator fixture bytes, planner locks, provider usage ledger or mutation state machine.
- No rewrites of historical MEM/Chapter2/Phase36 evidence or blanket claims that inherited gates are closed.
- No edits in other toy-app repositories, no cloud deployment, no force-push, and no automatic push to `main`. Committing locally is optional subject to repository normal process; **do not push without explicit current authorization**.
- Do not spawn subagents or defer completion awaiting another review. Complete bounded PI-0 and report residual risks.

## 6. Engineering judgment policy

This handoff is a **starting architecture hypothesis, not the implementation's unquestionable oracle**. Before writing, check whether the requirement fits an existing abstraction and who owns each state/permission boundary. If a specific source finding proves stale or a better non-intrusive boundary exists, correct the review/ADR and explain why. Do not introduce a second architecture solely to satisfy this prompt or rename modules for cosmetic independence. Carefully distinguish **installed module**, **declared capability**, **enabled capability**, **authorized caller**, **authorized source**, **authorized model disclosure**, and **accepted production operation**.

If a crucial design issue would require breaking trust/replay or a foundational change to resolve, do not opportunistically implement it in PI-0. Record it with concrete evidence and a proposed phase. If tests or environment are unavailable, do the documentation/static work and provide honest unverified statuses, not a request for extra prompting.

## 7. Completion checklist and required final response

- [ ] HEAD/diff/user changes inspected and preserved.
- [ ] `docs/platform-independence/` exists and is coherent with an index, roadmap and PI-0 review.
- [ ] Architecture decision record names **actual** owners, existing seams, freeze and unresolved decisions.
- [ ] Dependency inventory includes static and runtime/default composition edges, selected provider bind points, legacy waivers and phase owners.
- [ ] If feasible, deterministic no-network import inventory/guard and positive/negative tests; otherwise explicit status and follow-up.
- [ ] Clear PI-1 zero-app and PI-2 external-app acceptance gates with auth/privacy negative cases.
- [ ] `docs/README.md` and `docs/current-state.md` updated without historical rewrite.
- [ ] No runtime changes, DB migrations, new memory features, provider calls or flag enablement.
- [ ] Focused checks/evidence report including skipped/blocked tests and exact command names.
- [ ] Self-review finds no orphan docs, dead links, inconsistent statuses, stray sensitive values, or changed data-contract semantics.
- [ ] Outstanding independent PI-0 acceptance, MEM-0/1/2/Phase36/cloud gates preserved.

**Final response to the user must include:** (1) files changed/created and their repo paths, (2) exact verified HEAD and worktree caveats, (3) top findings and decisions, (4) what code—if any—was changed and why it is safe, (5) executed checks with counts/results and unavailable external tests, (6) open blockers and next independent review, and (7) any deviations from this plan. **No final claim that PI-0 is independently accepted.** A separate Sol High review should challenge the resulting baseline before PI-1 implementation.

**Success is an honest, reproducible architectural control point—not a large diff.**

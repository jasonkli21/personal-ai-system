# PI-1 — Independent Core and Optional Reference Extensions: Detailed Implementation Plan

**Repository target:** `docs/platform-independence/pi-1-detailed-implementation-plan.md`
**Prepared:** 2026-10-30 (America/Los_Angeles)
**Inspected source:** [`623327da171d4acd3d48d96a4c50bd40394c1925`](https://github.com/jasonkli21/personal-ai-system/commit/623327da171d4acd3d48d96a4c50bd40394c1925), after PI-0 and its review remediation.
**Status:** proposed plan; no PI-1 implementation or tests performed in preparing it. Refresh against live HEAD before work.

## 1. Outcome, scope, and boundaries

PI-1's result is a **genuinely standalone `personal-ai-system` core**, with an independently buildable/installable distribution and a working `personal_ai` first-party chat/context consumer. Travel, Shopping, Health and Finance are **optional reference/example integrations**—not core runtime or installation requirements. Their manifests, domain rules, source providers, federation cases, specialized routes, persistence adapters and task adapters belong outside the core distribution. The four remain available through an explicit opt-in legacy/reference profile for compatibility.

The decisive proof is a **core wheel physically lacking example implementations and their entry points**, installed and started outside the source checkout, with zero example imports. Disabling flags or supplying an empty catalog while still installing all modules does not count. The default core must exercise conversation, scoped context, working history/summary and permitted existing profile/memory/research through safe offline fakes, without modifying business logic for the examples.

**Out of scope:** PI-2 public versioned API and independently deployed fifth consumer; PI-3 provider-neutral ordinary generation/count/summary/embedding; PI-4 newly governed cross-app memory; PI-5 generalized retrieval/tools; app product feature work; new data stores/migrations for aesthetic reasons; cloud deployment or paid-provider validation. **MEM feature development remains frozen at MEM-2.** Existing MEM-0/1/2 schemas, defaults, permissions, test fixtures and unresolved production gates must survive unchanged except demonstrably necessary correctness/portability repairs.

## 2. Authority, prerequisites, and source map

Read `AGENTS.md`, `docs/README.md`, `docs/current-state.md`, `docs/platform-independence/README.md`, the PI roadmap, PI-0 architecture decisions, dependency inventory (`.md`/`.json`), exact waiver file, exit contract, implementation report and independent-review remediation. Inspect `docs/memory/`, Phase 36 evidence and `stabilization/` contracts only for owned compatibility obligations. Implementation is controlled by actual code/tests/migrations above plans; privacy and anti-replay constraints win conflicts.

**PI-0 acceptance caveat:** the repo currently contains PI-0 and R01–R03 remediation, but its own index and remediation record still say independent final acceptance is pending. Check for subsequent independent signoff at kickoff; do not silently close the gate. A user-directed PI-1 session may prepare a bounded implementation candidate while accurately retaining that gate, but cannot report PI-1 independently accepted/released until PI-0 entry and PI-1 exit are satisfied. Stop for any unresolved P0 security/architectural blocker.

| Evidence at `623327d` | Current problem | PI-1 responsibility |
| --- | --- | --- |
| `applications/registry.py::default_application_registry()` | Always creates five manifests and calls `domains.registry()`; injected contribution catalog extends example-filled base. | Built-in `personal_ai` only by default; example contributions separately selected. |
| `backend/pyproject.toml` | One wheel includes `src/personal_ai` and registers Travel/Shopping/Finance/Health context entry points. | Distinct core and optional distribution, with no example files/metadata in the core artifact. |
| `context/deployment.py` | Source-tree fallback imports four examples; `catalog or default...` ignores explicit empty intent. | No fallback; deterministic installed/selected catalog and `is None` handling. |
| `main.py::create_app` | Eager optional domain, itinerary and booking routers/errors; lifecycle always composes context, federation and tasks. | Default core routers only; trusted opt-in route contributions; lifespan and auth still work. |
| `domains/{registry,fixtures,service}.py` and `api/domains.py` | Travel/Shopping modules and fixture/provider-specific branches in a generic package. | Move example behavior; keep only demonstrably generic contracts and logic in core. |
| `federation/deployment.py` | Hardcoded four Health→Travel/Shopping, Travel→Shopping and Finance→Shopping cases are default. | Generic broker and permission authority with empty default; examples supply exact cases. |
| `mutations/deployment.py` | Imports Shopping adapter/payloads; derives current and retained task fingerprints from Shopping settings. | Move example task composition, preserve generic resolver and reconciliation guard. |
| `persistence/{factory.py,postgres/capabilities.py}` | Example proposal/booking contract imports, readers and writers in core. | Put example-owned repositories/decoders behind an opt-in adapter seam without rewriting durable rows. |
| `settings.py`, frontend routes/proxies | Example-specific configuration and UI assumptions remain in default stack. | No example configuration needed for core; opt-in settings/proxies remain compatible and secure. |

PI-0's guard counts **20 implementation import edges and four facade edges** (24 exact waivers) and separately records dynamic composition. It does not catch `importlib`, entry-point execution, transitive imports or archive contents. Retain and strengthen—not bypass—this guard. Existing synthetic fifth-app tests prove in-process extension only.

## 3. Architectural invariants

1. **One-way dependencies:** reference integration → platform extension contracts → generic services/policy → ports/adapters. Core must not import optional implementation at runtime, statically, under `TYPE_CHECKING`, through dynamic strings or through its package metadata.
2. **Installation is not permission:** installed plugin code is trusted executable code, but a manifest, selected contribution, feature flag or shared owner ID cannot grant workspace membership, source access, mutation permission, sensitive disclosure or paid/provider egress. Distinguish installed, selected, declared, enabled and authorized.
3. **One shared harness:** reuse `ApplicationContributionCatalog`, `ContextRuntimeContributionCatalog`, `ContextAssembler`, request scope, persistence factory, federation broker, mutation receipt/reconciler and memory service. No second chat loop, plugin engine, principal map, task state machine or memory store.
4. **Canonical compatibility:** preserve `personal_ai`, `travel`, `shopping`, `finance`, `health` IDs, nullable legacy scope decoding, actor/workspace boundaries, branch supersedes links, memory namespaces, migrations 028–031 and fences, grant epochs, field policy versions, source revision, vector embedding spaces, operation IDs/versions and immutable task fingerprints.
5. **Retained work must not strand silently:** current task execution may be off while old proposal/receipt reconciliation remains necessary. Missing historical adapter produces a visible safe startup/operation failure with no new effect dispatch, no dropped state and no altered idempotency key. Uncertain outcomes reconcile with the *original* key; they are never resent speculatively.
6. **Security and freezing:** memory controls stay default-off; app-private and sensitive sources remain isolated; final permission revalidation and source/actor fences remain. No MEM-3+, no live memory tool host, no implicit cross-app memory, no paid/cloud calls. Do not claim physical-send/deletion/backup/production issuer gates from fakes.

## 4. Pre-implementation plan challenge (mandatory)

Before changing substantive code, the **same implementation session**, without subagents, must critically review this plan against current source. Produce `docs/platform-independence/pi-1-plan-hardening.md` recording: factual corrections, gaps/risks, module ownership decisions, packaging alternatives, accepted changes to steps/tests and explicitly rejected alternatives. Update this plan if necessary before implementation. Investigate specifically:

- Whether one independently installed reference bundle with four separately selectable contributions is enough (acceptable PI-1 minimum), or separate per-app distributions are safer. Avoid overlapping wheel ownership of the `personal_ai` package and inspect both wheel and sdist contents.
- Where optional FastAPI routers, errors and persistence adapters belong. Prefer a **small composition-root extension of existing catalogs** to a broad new dynamic plugin framework. Detect conflicting routes and contributions.
- How stored itinerary/booking payloads and old type references deserialize after module moves; how old grant/task/receipt identifiers bind to retained implementations without introducing generic code dependency on example models.
- Whether *installing* an extension should auto-activate it. Prefer an **explicit deployment allowlist** with deterministic ordering and fail-closed missing/duplicate registration; installed code must not silently mount routes or grant access.
- Which domain comparison/decision code is truly reusable versus example-specific. Don't move a genuinely generic contract solely to make a test pass; don't retain example-specific branches under the name of a generic facade.
- Whether frontend default build/nav actually depends on example code. Minimum platform UI should work without example backend services; example UX should be visibly optional.
- What tests are safe to run without network. PI-0 recorded an unauthorized Google call from a broader offline-suite attempt; no blanket `make backend-test-offline` until no-egress isolation and fake injections are verified.

Record a migration/rollback decision table with alternatives and evidence, not just a proposed final directory tree. If current code invalidates these steps, change the steps; do not pigeonhole architecture into this plan.

## 5. Implementation sequence

### W0 — Baseline and dependency map

- Pin live SHA and branch; inspect `git status` and preserve all pre-existing edits. Re-run the read-only PI-0 inventory and guard tests.
- Inventory static, transitive/dynamic, entry-point, metadata, route, startup, frontend, SQL decode, retention/reconciliation and worker imports. Verify exact plugin and field contracts. List every file planned to move versus remain in core.
- Define safe no-egress fake fixture setup, build/install strategy and expected negative cases. Complete the plan-hardening note before code.

**Gate:** reviewed design and inventory; no unresolved silent replay/disclosure path.

### W1 — Core application and context composition

- Extract a core-only `personal_ai` manifest plus common context capability definitions. `default_application_registry()` must no longer instantiate examples or a Travel/Shopping comparison registry. Keep the existing immutable registry validation, workspace authorization and default-deny behavior.
- Replace truthy catalog fallbacks with explicit `None` semantics. An intentionally empty application/context catalog stays empty. Select installed contributions deterministically and explicitly (name allowlist or equivalent deployment profile); reject missing/duplicate IDs and invalid capability/provider relationships.
- Keep generic federation authority, permission revalidators, context planning and task registries composable with **zero** example cases/adapters. No source-tree fallback, no example factory imports. All model turns still use canonical shared assembler.

**Gate:** only built-in app and common providers in default runtime; unknown app/workspace fails closed; source and installed composition agree.

### W2 — Physically separated reference distribution and API surfaces

- Create independently buildable/installable optional package(s), in a distinct import namespace (e.g. `personal_ai_reference_apps`, subject to W0 review). Move Travel/Shopping/Finance/Health source/context integration, Health federation export, comparisons/fixtures, Shopping mutation payloads/adapters, itinerary/booking services and example-owned HTTP route implementation there. Keep shared domain/decision contracts and genuinely generic services in core if justified.
- Expose named application/context contributions via the **existing** catalogs, and a minimal explicitly selected router/adapter attachment seam if needed. Preserve historical URL paths, validation, error envelopes, capability IDs, context policy versions and auth middleware on opt-in. When absent, optional endpoints return a controlled `404` or defined unavailable response; they are not advertised as available in OpenAPI.
- Decouple example-specific persistence repositories and decoders from the core factory. Preserve canonical SQL tables, migrations, old payload schema compatibility and retention data. If optional decoder is missing, report unavailable explicitly; never alias, silently delete, or reinterpret persisted records. Refactor example-specific branches in `domains/service.py` out of core if needed.
- Update build metadata, lock/install instructions and artifact exclusion rules. The **core wheel and sdist**, including `dist-info/entry_points.txt` and declared dependencies, must have no example implementation code or mandatory example package dependency. The optional package must not secretly need a source-checkout `PYTHONPATH`.

**Gate:** build and inspect core artifacts; optional bundle separately installs and supports explicit per-app selection.

### W3 — Federation and durable task compatibility

- Move default four-case federation declarations into optional reference contributions. Empty runtime means zero cases; grant/source rights cannot be inferred from app IDs.
- Keep generic confirmation/reservation/effect receipt machinery and `require_reconciliation_compatibility()` in core. Move Shopping task construction and example settings/metadata into opt-in integration; preserve *both* active and retired fingerprints/contract payload versions.
- On fresh empty persistence, core without examples boots. With a retained proposal requiring a removed reconciler, startup fails explicitly without outbound send or state loss. With opt-in compatible adapter, retry/observation uses original operation key/fingerprint and doesn't duplicate effects.

**Gate:** old row/receipt fixtures round trip; missing-reconciler negative test and resumed exact-key reconciliation pass.

### W4 — Standalone value, UI and operator profiles

- In real `create_app` lifespan and HTTP routing, inject fake repos/model/identity; exercise `personal_ai` conversation create/read, streaming/completion, context budget and provenance, profile and existing allowed memory/research paths, branch edit/retry. No separate route through a simplified fake app for the main acceptance proof.
- Import/start the worker where applicable. Keep core health/account/profile/provider usage and gated memory endpoints. Ordinary Gemini composition remains an open PI-3 limitation; tests must use controlled offline fakes, not a new provider mechanism.
- Make default frontend/server navigation not depend on installed reference apps. Preserve optional proxies/pages where necessary, with existing auth/source gates; don't build new Travel/Shopping features.
- Document core-only install/start, reference install/allowlist/flags, clean disable and retained-state failure behavior, known cloud/provider limits and rollback profile.

**Gate:** core is independently useful; opt-in legacy behavior remains compatible.

### W5 — Tests, guardrails, evidence and review handoff

- Update PI-0 inventory/waivers only for **actual** removed edges; keep exact reviewed rationales and classification rules. Add wheel/sdist manifest and runtime import-denial regression checks. Don't simply exempt a relocated importer or use string imports to fool static diagnostics.
- Test from a new isolated environment **outside the checkout**, with `PYTHONPATH` unset; inspect `personal_ai.__file__`, `sys.path`, distribution metadata, entry points and `sys.modules`. Test the core wheel with example imports forbidden and physically absent. An editable install or monorepo in path is not proof.
- Run focused tests, lint/type/build checks and safe broader no-egress regressions. Keep historical assertions and evaluation locks; update paths when ownership changes, never delete cases to force green. Separate skipped/unavailable native DB/cloud/provider/browser checks.
- Write `pi-1-implementation-report.md` with source/commit identities, changed files, artifact hashes/manifests, exact commands/results, negative tests, plan deviations, preserved compatibility, unresolved gates and rollback. Update `docs/platform-independence/README.md`, `docs/current-state.md`, build/package READMEs, frontend operational docs as needed. Leave acceptance pending independent review.

## 6. Minimum acceptance matrix

| ID | Reproducible scenario | Must establish |
| --- | --- | --- |
| P1-01 | Build core wheel **and sdist**; inspect modules, entry points and `Requires-Dist`. | No example implementation, implicit example registration or mandatory example dependency. |
| P1-02 | Install *built* core wheel in isolated venv outside checkout, `PYTHONPATH` unset; log actual module paths. | Core import works; `personal_ai.context.travel` and other classified example imports genuinely fail; no source checkout loaded. |
| P1-03 | Import-deny finder over all example namespaces during real `create_app` lifespan, with offline fakes. | No dynamic, type-only, startup, decorator or entry-point attempt to import example modules. |
| P1-04 | Inspect registry, runtime providers, federation cases, tasks, route table and OpenAPI in core-only mode. | Built-in `personal_ai` only; no example capability, source case, task adapter or mounted optional endpoint. |
| P1-05 | Fake-backed HTTP create/read conversation and turn, context packing, branch edit/retry and profile/authorized memory. | Existing identity/scope, budgets, provenance and single shared assembler preserved; no network or secrets. |
| P1-06 | Clean-store core startup; then retained contract fixture with no reconciler. | Clean starts; missing historical adapter blocks **safely**, with no effect send, deletion or silent drop. |
| P1-07 | Separately install opt-in reference package; select each example contribution independently. | Old IDs, namespaces, provider/tool IDs, policy versions, routes, flags and auth semantics preserved; disabled examples absent. |
| P1-08 | Decode historical nullable/v1 and app/workspace/actor scoped rows, migration 028–031 memory/source fences, grant/context and itinerary/booking payloads. | No reinterpretation, accidental cross-app sharing, data loss or implicit rekey; unavailable extension is explicit. |
| P1-09 | Reconcile active/retired Shopping task fingerprints and uncertain outcome with old receipts, then remove adapter. | Exact original-key recovery or explicit safe refusal; no duplicate external effect. |
| P1-10 | Unknown/duplicate plugins, mismatched runtime provider, route collision, unknown app/workspace, forged owner/actor/app, revoked/disabled source. | Deterministic fail-closed behavior; no unauthorized source read, model send or effect. |
| P1-11 | Core UI/build and worker import (if in deployment scope). | No required reference module or misleading active route; core health and authorizations remain. |
| P1-12 | PI-0 AST guard, injected forbidden edge, packaged artifact inspection, negative import test. | Exact waivers updated downward, no new hidden core→example dependency. |
| P1-13 | Relevant app/context, federation, task, scoped memory/MEM-0/1/2, Phase36 conformance and core regressions. | Existing locks and default-off privacy/replay contracts preserved; skipped tests explicitly listed. |
| P1-14 | Uninstall/disable examples on clean store versus store with pending historic tasks, then restore explicit legacy profile. | Clean core remains functional; retained state fails safely until compatible adapter restored; no data changes. |

P1-01–06, P1-08–10, P1-12 and P1-14 are **non-waivable for architectural exit**. Native-store replay/erasure, production/cloud IAM, actual physical model send, cost and Phase36 acceptance remain separate obligations even if local fakes pass. A missing isolated install or no-egress setup is **BLOCKED**, never a pass.

Suggested commands (adapt to actual environment; **do not** install/download dependencies or contact providers without authorization):

```bash
git status --short
git rev-parse HEAD
python backend/scripts/platform_dependency_inventory.py --check
python -m unittest discover -s backend/tests -p test_platform_dependency_inventory.py -v
make backend-lint
make backend-build
```

Inspect artifacts with `unzip -l`/Python `zipfile`, then use an isolated temporary venv and an already available dependency set (`pip install --no-deps` only when safe). Run from outside the repository, unsetting `PYTHONPATH`. No full test suite is authorized to egress; inject deterministic fake ports and record the isolation guarantee and limitations.

## 7. Rollback, signoff and deliverables

Rollback = disable optional selection/installation or revert to the last accepted **explicit** catalog, retaining all persistent identity, grant, source-fence, forget, receipt and historical reconciler evidence. Never drop/rekey old rows, resend uncertain effects or erase deletion/replay controls. If retained work exists, preserve its reconciler or surface a startup blocker.

Deliver: (1) core and optional distributions plus tested composition; (2) physical-absence and legacy-compatibility tests/scripts; (3) exact guard/inventory and lock/build/operational docs; (4) `pi-1-plan-hardening.md`, architectural decisions as needed and `pi-1-implementation-report.md`; (5) accurate outstanding-gate ledger and ready-to-review diff. **Do not self-mark independent review or PI-1 readiness as passed.** Independent review uses `pi-1-independent-review-prompt.md`, and PI-2 waits for explicit PI-1 acceptance.

All PI artifacts belong in `docs/platform-independence/`. Keep historical MEM, Chapter2 and stabilization evidence in their original owner directories, with links rather than duplicated/revised past claims.

## 8. Same-session implementation hardening — 2026-10-30

The user authorized this plan's implementation in one session and one commit.
[Pre-implementation hardening](pi-1-plan-hardening.md) controls the corrected design:
one separate `personal_ai_reference_apps` distribution with four selected entries;
one JSON `APPLICATION_CONTRIBUTIONS` selection for both existing catalogs;
application contributions attach routers/errors and bounded policy extensions;
reference persistence wraps the canonical factory without core decoder hooks.
Core retains inert validated legacy settings and historical deny/decoder identifiers.
The existing narrow Travel-to-standalone research permission guard is preserved,
not generalized into a new sharing API. Historical data/permission identity is not
an example implementation dependency. Private Python import paths move; wire/data
contracts remain unchanged. See the [report](pi-1-implementation-report.md) for
actual evidence; this addendum and plan do not establish acceptance.

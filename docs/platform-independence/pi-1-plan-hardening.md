# PI-1 pre-implementation plan hardening

2026-10-30, America/Los_Angeles. Reviewed HEAD/main:
`623327da171d4acd3d48d96a4c50bd40394c1925`. This same-session review precedes
substantive implementation. It is not independent acceptance. PI-0 independent
signoff remains absent; the user's explicit PI-1 instruction authorizes a bounded
candidate only. No blocking P0 identified.

Inspected: root guidance/router/current state; PI-0 ADR, exit contract, inventory,
waivers, implementation/review/remediation; supplied PI-1 plan; application/context
catalogs and authorization, startup, settings, domain registry/service/providers,
proposal/extraction routes/services/SQL decoders, federation/task composition,
compatibility guard, persistence factory, worker, frontend gates and test fixtures.
MEM-1/2 ADR/evidence, Phase36 and stabilization contracts remain governing
constraints. Baseline guard: 20 implementation + 4 facade edges, zero issues;
11 guard tests passed. Existing user untracked documents are preserved.

## Findings and precise plan corrections

| Severity | Finding | Hardened requirement |
| --- | --- | --- |
| P1 | Entry-point discovery executes every installed factory through `load()`; installation currently activates integrations. | Existing catalogs take a closed selection list; validate duplicate/missing selection before executing any entry point. Default empty, injected catalogs remain explicit trusted deployment code. |
| P1 | Truthy fallback cannot reliably convey empty composition intent. | Use `is None`, default core manifest only, empty runtime catalog, no source fallback. |
| P1 | Domain provider/service modules are not neutral: OSM/OFF transport, domain-specific validation/mapping and fixtures live there. | Move those implementations and domain evaluation with examples; keep shared comparison contracts/repositories/SQL and decision engine in core. |
| P1 | Global `@app` handlers/health are absent on separately constructed apps. | Every `create_app()` installs core health and safe error handlers; selected contribution routers/errors are checked before attachment. |
| P1 | Factory type-only imports also bind core to optional decoders. | Remove example repository methods/types from core factory; optional adapter wraps the existing factory/database, preserving SQL/row bytes and delegation. No migrations. |
| P1 | Removing task execution alone can strand old fingerprints. | Generic startup guard remains unconditional. Reference Shopping contribution supplies current and retired adapters even when new writes disabled; core refuses incompatible retained state. |
| P2 | Default application policy includes proposal-only fields. | Move specialized policies to references while retaining exact reference policy versions/fields. Core policies authorize only shared providers. |
| P2 | Existing tests assume five defaults. | Update compatibility tests to request an explicit reference profile; add independent core tests. Do not globally fake default registries or remove assertions. |
| P2 | Python offline tests can enter real provider branches. | Clean environment plus checked Python audit fence and inspected fake fixtures; stop/investigate blocked attempts. Native-extension/OS-wide isolation remains unclaimed. |

## Architecture-sensitive alternatives and decisions

| Decision | Alternatives | Accepted design / rejected reason |
| --- | --- | --- |
| Package ownership | Four distributions vs one separately selectable reference bundle; shared namespace overlay vs distinct namespace | One `personal-ai-reference-apps`, namespace `personal_ai_reference_apps`, outside backend build root. Four catalogs entries. Four distributions add dependency/matrix overhead without improving PI-1 trust. Namespace overlays risk uninstall collisions. |
| Composition | New plugin framework vs extend existing application/context catalogs | Extend ApplicationContribution with bounded routers/error handlers; retain catalogs and runtime/federation/task registries. Reject second plugin engine and hardcoded core imports. |
| Selection | Auto-enable installed plugins vs explicit names | Deployment `APPLICATION_CONTRIBUTIONS` and matching context selection; missing/duplicate names fail before code loads. Programmatic catalogs are explicitly trusted composition. Installing a package grants no membership/source permission. |
| Task metadata | Shopping-specific core installer vs generic adapter declarations | Generic installer updates only registered destination manifests and validates declarations; no arbitrary policy invention. Exact reference adapter fingerprints retained. |
| Persistence | Dynamic core decoder discovery vs optional wrapper | Reference wrapper owns proposal/extraction constructors and delegates neutral repositories to canonical factory. Historical tables/schemas/scopes stay unchanged. No alternate store or automatic decoding when extension absent. |
| Python legacy imports | Permanent shims in core vs migrate reference consumers | No core shims: old private Python paths deliberately unavailable. Wire URLs/IDs/versioned payloads and durable data remain compatible. Updated reference tests import the optional namespace. |
| Config/UI | Large settings rewrite vs retain inert validated fields | Retain existing settings/default-false validation and gated frontend proxies. Core needs none of the example configuration; document optional UI flags. Relocating credentials/config is not necessary for installation independence. |

## Updated acceptance and rollback

P1-01–P1-14 remain binding. Add: selected entry point must not execute an
unselected loader; two same-name entry points fail before load; conflicting
router path/method or error handler fails; fresh factory health/error envelope;
per-app selection does not silently authorize another reference application;
missing reference decoder is unavailable rather than dropping data; retained
fingerprint draining remains original-key observation only. Test real wheel AND
sdist from outside checkout, inspect metadata, install with `--no-deps --no-index`
and use only already available dependencies. Report unavailable build/install
prerequisites as BLOCKED, never infer a pass.

Rollback: remove selection on clean stores; if retained tasks exist keep compatible
reference adapters installed/selected (new writes off), or fail startup until
restored. Preserve rows, migrations, source/actor fences, deletion/forget receipts,
original operation keys and all historical evaluation fixtures/locks. No replay,
rekey, down-migration, MEM-3+, provider redesign or independent verdict is authorized.

## Second within-session skeptical review and closure

After implementation, inspected the full core diff plus optional source,
wheel/sdist ownership, entry points/dependencies, persistence construction and
row readers, authorization/source checks, startup and exact retained-task
transitions. This is still implementer self-review, not independent acceptance.

New adversarial cases beyond initial happy paths: lazy included routers with
renamed parameters; catchall overlap; differing settings-file/process selection;
source-only export with unselected destination; duplicate builtin policy extension;
and invalid/duplicate handlers before any route attachment. The lazy-router case
found and fixed a real missed collision. Configuration drift now fails startup;
unused exports are filtered before binding; failure cleanup is unconditional.
Final tests exercise the current source, all existing default-false settings and
frozen files remain preserved, and actual installed artifacts pass absence,
reference install/uninstall/restore and copied compatibility/utility checks.
Exact counts, identities, failures and unresolved native/independent gates belong
to the [implementation report](pi-1-implementation-report.md).

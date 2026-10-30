# PI-1 implementation report

**2026-10-30, America/Los_Angeles. PI-1 candidate pending independent review.**
This is sole-session implementation, plan challenge and self-review, with no
subagents. It supplies no independent verdict and does not close PI-0 acceptance.

## Identity and scope

Initial HEAD/main: `623327da171d4acd3d48d96a4c50bd40394c1925`. Final source is the
single commit containing this report. Its exact final SHA is deterministically
resolved by `git log -1 --format=%H -- docs/platform-independence/pi-1-implementation-report.md`
and supplied in the user handoff; embedding a commit's own SHA in its contents
would create a circular identity. [Source manifest](pi-1-source-manifest.json)
records 93 changed/new implementation, packaging, script and test files with
SHA-256, removed paths, artifact identities and frozen paths. The final Git diff
adds this report, plan/hardening, verification commands, independent-review
instructions, current inventory/manifest and the documentation/router updates.
`git show --stat --oneline <final SHA>` supplies the complete changed-path ledger.
No push or PR is authorized or performed.

Preflight had no tracked modifications and eleven untracked user documents:
the two memory plans; LiteLLM handoff; phase 11/12/13/14/15/17r reviews;
PI-0 independent handoff; and the supplied PI-1 detailed plan. Only the PI-1 plan
is adopted into this task's commit, with a clearly labeled hardening addendum.
The other ten documents remain untracked and untouched. At handoff all task
changes are committed; those pre-existing documents are the only remaining
working-tree entries. No reset, stash, unrelated repository or personal data was
used. The final SHA is checked against the single-commit parent above.

Artifacts built offline with Python 3.11.15, existing Hatchling 1.27.0/editables
0.5, and uv (`UV_OFFLINE=true`, cache in `/private/tmp/pi1-uv-cache`):

| Artifact | Members | SHA-256 |
| --- | ---: | --- |
| `backend/dist/personal_ai_backend-0.1.0-py3-none-any.whl` | 412 | `e39046124f27bbbc7b1bfefceb0495c0c4dffdc1b1088e18ec32291813f3edba` |
| `backend/dist/personal_ai_backend-0.1.0.tar.gz` | 413 | `524143b74bd014f91e9fa9150b344ca7fae011669948768c21debc88320ae9c8` |
| `reference-apps/dist/personal_ai_reference_apps-0.1.0-py3-none-any.whl` | 54 | `bb9fafa59490908d8489fac2834c8f58b764b3603e658470b01a3308f61041fb` |
| `reference-apps/dist/personal_ai_reference_apps-0.1.0.tar.gz` | 54 | `fcb1a2787dddb3fb0109bc4673d35ed8508a4ee6c5a5dcbd3b9aa8a77ec1cb55` |

Generated distributions are ignored build outputs, available locally and
reproducible from source. No dependency was downloaded. Core dependency versions
and the lock remain unchanged; reference metadata requires the matching core.

## Accepted design and behavior

[Pre-implementation hardening](pi-1-plan-hardening.md) was written before code.
Compared one vs four optional distributions, namespace overlays vs disjoint
ownership, automatic registration vs explicit selection, a second plugin system
vs existing catalogs, and core decoder discovery vs reference-owned construction.
The accepted design uses one separately installable reference bundle, four
selectable contributions and the existing application/context catalogs.

Core defaults to `personal_ai` and its five shared providers. It has no reference
entry points, implementations, comparison modules, federation cases or task
adapters. Empty catalogs remain empty via `is None`. Generic federation/mutation
HTTP services remain in core behind their existing authorization/feature gates;
no example HTTP endpoints are mounted or advertised by core OpenAPI.

`APPLICATION_CONTRIBUTIONS` is a bounded JSON list of explicitly trusted names,
read from the process environment before app construction; default `[]`. Missing,
duplicate or malformed selected names fail before loading that catalog's entries;
unselected code is not loaded. Both existing entry-point catalogs use the same
selection. Explicit programmatic catalogs remain trusted composition. Startup
rejects a different settings-file-only selection, preventing silent config drift.
Installation, selection, declarations, feature flags, user/workspace authorization,
source permission and disclosure remain distinct.

The optional `personal_ai_reference_apps` namespace owns all four manifests and
context adapters, narrow Health exports, comparison modules/transports/fixtures/
service, Shopping task payloads/adapter/composition, itinerary/booking routes and
services, their SQL adapters/cleanup and reference evaluations. Core owns neutral
comparison contracts/repositories/SQL, decisions, chat/context assembly, memory,
research, grants/broker, task state/receipts/reconciliation and canonical storage.
No second memory, task engine, provider loop or plugin system was introduced.

Application contributions extend bounded policy declarations and attach trusted
routers/errors. Duplicate policy providers and ambiguous handler/route ownership
fail before mounting. Collision detection handles eager/lazy/nested FastAPI
routers, renamed path parameters and catchalls; shared reference comparison
router objects attach once. Every factory instance receives health and safe core
error handlers. Existing auth middleware, request admission and source checks
remain governing. Failed startup now closes persistence clients too.

Task metadata derives from explicitly configured validated adapters into registered
destinations; it no longer branches on Shopping in core. The optional Shopping
factory preserves current and retained fingerprints, including draining with
new writes disabled. The unconditional compatibility guard rejects retained state
whose original fingerprint resolver is missing. Unknown effects reconcile using
the original execution key; no speculative send/drop/rekey behavior was added.

The optional persistence wrapper owns itinerary/booking constructors over the
existing canonical factory/database. Core has no optional repository methods or
type-only imports. Old JSON/table/schema/scope formats and migrations are unchanged;
missing implementation is explicitly unavailable through absent routes/imports,
not silently decoded, deleted or reinterpreted. The reference SQL reader tests
retain owner/app/workspace checks, including null legacy workspaces.

Deviations/hardening: core sdist is deliberately narrowed to core source,
pyproject and lock; development tests/scripts stay in the repository. Private
Python imports move to the optional namespace without core compatibility shims;
wire IDs/URLs/versioned payloads stay stable. Existing settings and historical
security/decoder identifiers remain inert in core, including the narrow Travel
research-import permission guard; no generalized sharing permission was added.
The 74 existing default-false settings and validation semantics are preserved.

Frontend code is unchanged: normal chat/profile UI needs no reference service;
existing server flags gate reference navigation/pages/proxies. The normal Dockerfile
builds core; optional deployment requires explicitly installing the reference wheel.
[Package operations](../../reference-apps/README.md) covers selection, configuration,
source-tree compatibility, flags and draining/rollback.

## Executed acceptance matrix

[Commands C1–C8](pi-1-verification-commands.md) are exact, reproducible invocations.
PASS below is bounded local/synthetic/installed-artifact evidence, not external
acceptance. Source commands used clean environments with inspected fake ports,
pytest plugin autoload disabled and a checked Python socket audit fence. All
completed selected runs recorded **zero attempted network egress**. The fence
is not OS-wide/native-extension isolation. No .env or credentials were loaded.

| ID | Command/environment and observed result | Result |
| --- | --- | --- |
| P1-01 | C1: inspect real core wheel/sdist members, `METADATA`/Requires-Dist and installed distribution metadata. 412/413 members, no reference implementations, core entry points or reference dependency. Optional 54/54 member archives own no core namespace. | PASS |
| P1-02 | C1 fresh `/private/tmp/pi1-installed-*` venv, dependency files copied without `.pth`/editable hooks/platform packages, built wheel installed `--no-index --no-deps`, PYTHONPATH unset. Core resolves inside isolated site-packages; all 19 classified example imports fail before import denial is installed. | PASS |
| P1-03 | C1 import-deny finder during actual production factory/lifespan, route/OpenAPI traversal, HTTP turns and worker import; zero attempted example imports and network operations. | PASS |
| P1-04 | C1/C2: registry exactly `{personal_ai}`, five shared capability registrations, no comparisons, runtime providers/cases/tasks/reconcilers empty; optional paths absent from OpenAPI and return 404. Unknown app/workspace denied; client owner/actor hints do not change verified scope. Generic gated services remain. | PASS |
| P1-05 | C1: four actual HTTP model turns using fake model/repositories and canonical ContextAssembler; four actual-build manifests, max observed input 165 tokens within recorded budgets; profile PUT/GET, regeneration/edit active-prefix behavior. 49 copied installed-core memory/research/summary tests pass. C2 464, C4 76 checks include permitted core memory/research and source/summary reuse. | PASS |
| P1-06 | C1 clean lifespan succeeds; required `shopping/project.set_budget@1/` + 64 `c` fingerprint blocks actual startup without resolver. Inventory unchanged; no sender exists in core. Failure cleanup tested in C5. | PASS |
| P1-07 | C1 separately installed reference wheel, each entry selected alone: registry exactly core + selected app; Travel-only itinerary/booking routes, Travel/Shopping comparison routes, absent apps denied; explicit legacy profile has exactly four federation cases. 190 copied installed-package compatibility tests pass. | PASS |
| P1-08 | C1/C2/C3: historical scopes/application/actor fixtures, unchanged schemas/fences, four synthetic old SQL row cases through moved proposal/extraction readers (legacy missing app/null workspace and scoped rows), foreign owner/scope denied. Package fixture bytes equal original. No actual SQL migration execution or native row replay claimed. | PASS local; native BLOCKED |
| P1-09 | C1 restored-package 56 task/mutation tests and C3: current/retired Shopping fingerprints, observation-only draining, retirement/restart/uncertain effect original-key reconciliation and missing resolver refusal. No new effect send on uncertain recovery. Synthetic signed clients/repositories only. | PASS local; native/physical effects BLOCKED |
| P1-10 | C2/C3/C5: unknown/duplicate selection before load, unselected loader untouched, provider identity mismatch, duplicate policy/handler, renamed/catchall route collisions, absent comparison despite enabled flag, forged scopes/signed identities, revoked/disabled source and task policy tests. | PASS |
| P1-11 | C1 worker import with physically absent examples; C7 frontend 130 tests/25 files, lint, typecheck and production build pass with bundled Node. Default-off reference frontend gates unchanged. No rendered browser/device claim. | PASS local |
| P1-12 | C6 guard zero implementation/facade edges, zero waivers; 13 guard tests including injected legacy facade/leaf, missing old submodule and moved namespace edges. C1 archive/runtime negatives supplement AST blind spots. | PASS |
| P1-13 | C2 464; C3 298; C4 76; C5 60, all passed with zero blocked network attempts. Groups overlap and must not be added as a unique count. MEM-0/1/2, source grants, task identity and integrated synthetic Phase36 covered. Whole backend suite/provider matrix/native/cloud suites not run. | PASS selected; external BLOCKED |
| P1-14 | C1 install references → core remains default; uninstall → physically absent core probe repeats including missing retained resolver refusal; reinstall → explicit legacy profile and 56 original-key task/mutation checks pass. Stored-state compatibility is synthetic, not native DB recovery. | PASS local; native BLOCKED |

Final installed proof workspace: `/private/tmp/pi1-installed-28865r_n` (the script
prints its actual workspace; inspect the local final log if this run-specific path
is regenerated). Installed modules are `<workspace>/venv/lib/python3.11/site-packages/personal_ai/__init__.py`
and, while installed, the disjoint `personal_ai_reference_apps/__init__.py`.
`sys.path` contains that workspace, standard library and isolated site-packages,
with no repository source. `dependency-files.json` records the copied dependency
inventory. Package artifacts and the source manifest bind the reproducible result;
temporary workspaces/logs are supplemental local evidence, not committed inputs.

Final lint: `make backend-lint`, reference ruff check and `git diff --check` passed.
No backend typecheck target exists. Frontend build used the installed bundled Node
runtime after the shell's initial missing-Node failure. No browser session or cloud
build was run.

## Preservation, self-review and limits

C8 confirms **236 frozen files** unchanged from the initial revision across memory,
contracts, migrations, historical fixtures/locks, experiments and frontend. Sorted
path/NUL/raw-bytes/NUL SHA-256:
`0a247b8447c264f56c6ca6aa1442c9f6c6bbeff4be600fce6c3a042e096734ce`.
All 74 default-false settings are identical. No MEM-3+, schema change, source fence
relaxation, operation-key rewrite or evaluation promotion occurred. Old planner
locks remain historical identities; production replay does not silently accept
this changed source.

Second skeptical within-session review inspected the full core diff and optional
package, metadata/import topology, SQL reader boundaries, auth/source checks,
metadata installation and retirement/uncertain transitions. New negative cases
included lazy routers with renamed parameters, settings-only selection drift,
source exports with unselected destinations, and policy-extension attempts to
replace a builtin policy. Confirmed defects fixed: lazy router collision visibility;
selection drift; filtering unused exports at composition; module-global-only error
handlers; and failure-path cleanup. Rechecked artifacts and relevant tests afterward.
This review is by the implementer and does not replace independent review.

Failure history is retained: baseline guard 11 passed; first reference run had
291 passed/5 failures (moved module/package-import fixture paths and guard test
expectations). First wider core run had 447 passed/9 failures (new test endpoint
callable, explicit legacy-profile selection in old tests); a later run had 460
passed/1 failure exposing lazy-router introspection. Final counts above pass.
One attempted test command named a nonexistent file and collected no tests;
corrected commands are recorded. First build hit the sandboxed uv cache and was
rerun offline with a writable temporary cache. Initial lint/import-order issues
were corrected. The staged whitespace check found three Markdown hard-break
spaces in the adopted supplied plan; these were removed before the final check. All attempted fenced pytest runs, including failures, recorded zero
egress attempts. Initial frontend commands failed because Node was missing from
PATH; reruns with the bundled runtime passed. No failed result is represented as
a pass or hidden by enabling networking.

No unresolved P0/P1 implementation blocker was found within this bounded candidate.
Acceptance remains blocked on independent PI-0 and PI-1 review. Native
PostgreSQL/DynamoDB migration/replay/recovery, cloud/provider/private ingress,
linked identity and deployed source revocation, actual model send/cost, physical
external effects/deletion/backups, production MEM issuer/lease, permanent fence/
receipt capacity and external Phase36 gates remain open. The broad offline suite
was not run because every provider/emulator fixture was not audited for safe fake
injection; only inspected hermetic groups were authorized. No native engine,
credentials, personal chats, cloud resources, real provider, dependency download,
production deployment or external effect was used.

Rollback clears optional selection on clean stores. With retained work, preserve
compatible installed Shopping reconcilers/fingerprints and delegation transport
while new writes are disabled; otherwise startup must refuse until restored.
Never purge/rekey retained rows, remove deletion/forget/source fences or resend
uncertain effects. [Independent-review instructions](pi-1-independent-review-prompt.md)
route the next reviewer to exact source, commands and remaining gates. PI-2 waits
for explicit PI-1 acceptance.

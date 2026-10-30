# PI-0 exit contract for later independence work

2026-10-30; source baseline `8571a8af33969f249614c2652a7d29c0c686f2d8`.
This defines **future tests**, not delivered runtime features or passing results.
PI-0 baseline evidence is in the [report](pi-0-implementation-report.md).
The [roadmap](platform-independence-roadmap.md#7-acceptance-matrix-minimum)
retains the 22 cross-phase scenarios. Each later phase needs pinned source,
artifact/dependency identities, exact commands, observed failures/skips and a
separate reviewer. No gate may be closed using only another gate's evidence.

| Gate / accountable owner | Reproducible proof design | Failure/negative criteria |
| --- | --- | --- |
| PI-0 baseline / implementer, then independent Sol High reviewer | Re-run static inventory and exact waiver check; inject a forbidden edge in a temporary fixture; inspect dynamic composition and source diff | Any production source/default/schema/fixture change or undisclosed edge blocks acceptance |
| PI-1 zero examples / packaging and startup | Build core wheel, inspect archive/entry-point metadata, install into clean environment with all inventory example prefixes physically absent; deny their imports as a second control | Flags disabled in a full source checkout do not count; transitive import of any removed example fails |
| PI-1 lifespan / API composition | Enter and exit real `create_app` lifespan using fake repositories/ports; exercise router registration, empty federation metadata and mutation compatibility reconciliation | Missing optional route is controlled unavailable/404; a retained task lacking a reconciler produces an explicit safe startup error, never silently drops or resends work |
| PI-1 builtin flow / chat and context | Fake-only local HTTP create/read conversation and complete a turn with shared context, history/summary budgets, branch edit/retry and bounded output | No model credentials/network; no private example imports; no alternate context assembly path |
| PI-1 legacy opt-in / extension owner | Separately install examples; replay old scoped rows, null-scope v1, manifests, grants and in-flight/retired task fingerprints | No ID rewrite, cross-app reinterpretation, lost receipt or deletion/source fence; current-off does not remove reconciliation |
| PI-2 unrelated consumer / public API owner | Package unrelated notes/reading app in a separate directory/distribution without `personal_ai` dependencies; install fresh, use only documented versioned HTTP/SDK for authenticated context read and turn stream | Source/import audit forbids private imports; app addition requires no core patch; no hard-coded owner bypass |
| PI-2 identity / auth and app membership | Fake issuer test suite exercises production middleware contract locally; separately authorized staging suite verifies actual user plus service identity | Unknown app/workspace, nonmember, forged owner/actor/app header/token, stale authentication and unconsented app-to-app read all deny; local identity proves no deployment gate |
| PI-2 failure/retry / API and consumer | Same-key retries, lost stream acknowledgement, changed payload, cancellation and consumer upgrade/deprecation probes | No false durable success, duplicated task effect or regenerated operation identity after uncertain send |
| PI-3 operation composition / inference and usage | Inject two distinct adapters; swap Gemini out of generation/count/summary; instrument every model/search/embed dispatch and token budget | No silent Gemini ancillary call; unsupported capability explicitly unavailable; existing memory embedding-space mismatch rejected |
| PI-3 cost / routing and operations | Free-strict exhaustion/429/outage tests, explicit bounded paid-opt-in profile and physical-send accounting | No paid fallback without consent; no dual-send on uncertain outcome; live cost/free-tier claims need separately authorized account-specific evidence |
| PI-4 sharing / profile and memory policy | Explicitly share one eligible user-global preference with app B through existing profile/view seams, then revoke; test private record in app A | App-private/sensitive Health/Finance memory denied absent exact grant even for same owner; unknown field, destination, purpose or actor denies |
| PI-4 derived reuse / context and source authority | Revoke/expire/delete source or change grant/project revision after retrieval, during counting and before send; reuse old cache/history/summary | No stale inclusion or source resurrection; preserve current final checks; fake send probes do not establish physical-send concurrency safety |
| PI-4 MEM-2 default / memory controls | Seed a known schema-3 row via hermetic trusted fixture; normal default flags still block control read/write; deliberately authorized fixture exercises old receipt replay, forget, source deletion and recovery | No production host registration, new intake or MEM-3 work; preserve source tombstone and receipt retention/capacity blockers |
| PI-5..8 / search, evaluation, operators and independent reviewer | Run roadmap A17..A22 with eligible local/permitted external sources, held-out task outcomes, clean credential-free fake install, native recovery and adversarial audit | Synthetic tests cannot establish real task lift, cloud identity/cost/deletion or backup recovery; retain explicit open gates |

PI-1/2 implementation plans should link here rather than duplicate a weaker
contract. Until separately authorized phases are implemented and reviewed, all
these target capabilities remain unclaimed. Rollback disables new optional
composition or sharing while preserving durable compatibility, lifecycle forget,
source fences and receipt history. No provider, cloud or live-store execution is
authorized by this document.

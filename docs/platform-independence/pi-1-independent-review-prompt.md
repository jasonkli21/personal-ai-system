# Independent PI-1 review handoff

Review the single commit containing this file against parent
`623327da171d4acd3d48d96a4c50bd40394c1925`, using actual code/tests/artifacts above
plans. This file supplies instructions, not a review or verdict. PI-0 independent
acceptance remains pending. Scope is a user-directed PI-1 candidate; MEM-3+ stays
frozen, and PI-2–8 are unauthorized.

Read root guidance/router/current state, PI-0 ADR/exit/remediation, PI-1 plan and
hardening, implementation report, source manifest and verification commands.
Preserve unrelated user files and do not contact providers, read credentials,
load .env, install dependencies over the network, touch live stores/cloud, push,
or create a PR. Use inspected fake ports and the network fence for local tests.

Independently rebuild core/reference wheel AND sdist offline. Inspect all members,
metadata, dependencies and entry points. Run the artifact check from the commands
page; challenge its dependency-copy exclusions, installed module paths and
PYTHONPATH absence. Verify examples fail real imports before the deny finder is
installed, and that import-deny/network fences remain active during core lifespan,
worker and actual HTTP chat/history/branch/profile. Check the copied installed
memory/research/summary tests and optional compatibility tests. Install each
reference contribution separately and inspect declared vs enabled vs authorized
behavior. Exercise real entry-point loading, empty catalogs, missing/duplicate
selection and config/factory mismatch; no unselected loader may execute.

Challenge the full diff, particularly:

- Existing ApplicationContribution/ContextRuntimeContribution ownership and bounded
  extensions, policy collisions, generic task metadata, and all new defaults.
- Lazy/eager/nested FastAPI router introspection, renamed/catchall path collisions,
  safe exception handlers on every app instance, and middleware/source admission.
- Selected comparison modules when another app's feature flag is enabled; export
  adapters whose destination is unselected; unknown scope/actor/source revocation.
- Exact wire application/provider IDs, namespace/policy versions, nullable legacy
  scopes, SQL filters and old itinerary/booking payloads after private import moves.
- Active/retired Shopping fingerprints, original operation keys, unknown effects,
  missing reconciler startup refusal, cleanup on failed startup, drain/uninstall/
  restore. No reconciliation retry may resend uncertain effects or delete state.
- Frozen memory/source actor fences, consent and disclosure checks, no-effect replay,
  unchanged migrations 028–031, receipts, fixtures and historical evaluation locks.
- Core sdist narrowing and optional package fixtures; no namespace-overlay ownership
  or hidden source checkout dependencies; core UI and worker absence behavior.

Devise additional negative cases rather than relying on implementer assertions.
Run commands C1–C8 that are safe/available, recording exact revision/artifact hashes,
results and limitations. Native PostgreSQL/DynamoDB, cloud identities, deployed
membership/source revocation, physical model send/deletion, provider costs,
production issuer/lease, memory capacities and external Phase36 acceptance remain
separate open gates; synthetic passing tests cannot close them. Report findings
with severity and source lines, distinguish reproduced facts from inference, and
write your own independent verdict. Do not silently accept a gate because the
implementer's local tests pass.

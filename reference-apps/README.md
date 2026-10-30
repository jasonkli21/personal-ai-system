# Personal AI reference applications

An optional distribution, `personal-ai-reference-apps`, owns Travel, Shopping,
Finance and Health integrations. Its namespace is `personal_ai_reference_apps`;
it owns no files under `personal_ai`. It depends on the matching core version.
Private Python imports moved; wire URLs, application/provider IDs, policies,
SQL schemas and immutable task contracts retain their historical identities.

Build with `make reference-build` after the root README's backend setup.
Install the built core and reference wheels into the same deployment environment.
For an existing dependency-complete development environment, installation can be
fully offline:

```sh
uv pip install --python backend/.venv/bin/python --no-index --no-deps \
  backend/dist/personal_ai_backend-0.1.0-py3-none-any.whl \
  reference-apps/dist/personal_ai_reference_apps-0.1.0-py3-none-any.whl
```

Installation activates nothing. Select trusted entries explicitly before process
startup, for example:

```sh
export APPLICATION_CONTRIBUTIONS='["travel","shopping","finance","health"]'
```

Selection is read from the process environment before app construction; put this
variable in the service environment, not only a dotenv file. Startup rejects a
different settings-file selection. The same names select existing application
and context catalog entries. Any
subset is supported. Missing selected entries or duplicate names fail closed;
unselected entry points are never loaded. Programmatic catalog injection remains
an explicit trusted deployment seam. Plugins execute trusted Python code and
are not a sandbox. Neither selection nor an enabled flag grants workspace,
source, model-disclosure or task permission. Feature flags retain their previous
validation and default-false values. Narrow Health exports and broad Health
context still have distinct identity constraints.

Travel selects itinerary/booking and comparison routes. Shopping selects
comparison routes. Comparison service uses only selected modules even if a flag
for an absent application is true. Finance/Health do not add HTTP routers.
Federation cases are supplied by their selected destination; only installed
source adapters can implement them, and grants/source checks still apply.
Selecting a source without a destination leaves its unused exports unbound.

The explicit source-tree legacy profile is
`personal_ai_reference_apps.main:app`. Production may instead use the usual
`personal_ai.main:app` with installed entry points and the selection above.
The reference profile is useful for historical compatibility tests; it does not
turn feature flags on. Tests in `backend/tests` import the reference namespace
explicitly; pytest adds its source directory for development only. The artifact
probe never uses these source directories.

The optional persistence wrapper delegates to the canonical core factory and
owns only itinerary/booking constructors. No migration, table, payload, source
fence or receipt was rewritten. Example cleanup is now
`python -m personal_ai_reference_apps.booking_extractions.cleanup`.
Reference evaluations use
`personal_ai_reference_apps.evaluation.{domain,itinerary_proposals}`; the itinerary
fixture is packaged with identical bytes to the historical test fixture.

Frontend Travel/Shopping links/pages/proxies retain literal-true server gates
`DECISION_ENABLED`, `TRAVEL_ENABLED`, `SHOPPING_ENABLED` (plus inspection gates).
Keep them off in the core profile; backend authorization remains authoritative.
No frontend plugin build or direct browser-to-backend path is introduced.

To disable examples on an empty store, clear selection and restart; uninstalling
the reference package then removes only its namespace/metadata. With retained
tasks, keep Shopping selected and retain pinned fingerprints while turning
`TASK_SHOPPING_ENABLED` off. Required delegation/transport settings must remain
valid for observation-only reconciliation. Otherwise startup refuses the missing
historical resolver. Restoring the compatible package, selection and fingerprints
recovers the original operation keys. Never delete/rekey rows or resend uncertain
effects as a rollback. Back up and preserve canonical state under existing policy.

PI-1 is a candidate pending independent review. Provider portability (PI-3),
MEM-0/1/2, native-store, physical-send/deletion, cloud identity and Phase36 gates
remain separate; no production readiness is asserted.

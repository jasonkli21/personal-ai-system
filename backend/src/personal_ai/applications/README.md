# Application registry

This package owns typed application manifests and deterministic composition of application, capability, comparison-domain, and workspace metadata. It resolves declared application context before the shared context and capability paths run.

## Ownership and limits

- `contracts.py` defines versioned manifests, workspace requirements, memory namespaces, provider/tool/domain IDs, sensitivity defaults, cross-application references, export declarations, budget hints, and `ApplicationContextPolicy`.
- `registry.py` validates references and exposes immutable registrations.
- `ApplicationContributionCatalog` loads definitions and optional workspace membership authorities through the `personal_ai.application_contributions` entry-point group. `create_app` installs the composed registry before authentication middleware; omitted workspace authority continues to deny membership.
- Capability availability means an implementation exists; deployment gates can still disable it.
- A manifest describes declared providers, tools, and domains. It does not own application records or rules, implement missing providers, select inference providers, or grant cross-application access.
- `ApplicationContextPolicy` is the local membership and revocation source for provider operations, fields, source access, model disclosure, and sensitivity ceilings. Unknown providers/fields and direct cross-application access fail closed. Federation and mutation adapters use separate authorities and exact eligibility checks.
- Sensitivity defaults and budget hints are metadata; enforcement and provider selection remain in their owning runtime layers. See [mutation contracts](../mutations/README.md).
- Domain applications retain authority over their records, rules, and rich UI.

## Entry points and verification

Start with `contracts.py` and `registry.py`. Focused tests cover application composition, request scope, and production middleware. See [system architecture](../../../../docs/architecture.md) and [the API contract](../../../../docs/api-contract.md).

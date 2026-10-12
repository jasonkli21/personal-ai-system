# Application registry

This package owns typed application manifests and deterministic composition of application, capability, and comparison-domain metadata. It lets a request resolve its application and declared workspace shape before the shared context and capability paths run.

## Ownership and limits

- `contracts.py` defines versioned manifests, workspace requirements, memory namespaces, provider/tool/comparison-domain IDs, sensitivity defaults, declaration-only cross-application references and typed federation export declarations, advisory context-budget hints, and the typed `ApplicationContextPolicy` for provider/operation/field access and model disclosure.
- `registry.py` validates references and exposes immutable-by-interface registrations.
- Capability `available` metadata says an implementation exists; feature gates can still disable it in a deployment.
- A manifest describes which providers/tools/domains an application declares. It does not own that application's records or rules, implement a missing provider/tool, select an inference provider, or grant cross-application data access. Capability declarations alone are not authorization; the context coordinator checks the server-owned application policy separately.
- `ApplicationContextPolicy` is the local Phase 15 policy source for known provider operations, selected fields, source access, model disclosure, and the model sensitivity ceiling. Unknown providers/fields and direct cross-application access fail closed. Federation is a destination-scoped registered broker with separate current grant/source-policy authority and exact export eligibility. Domain contributions register executable export adapters independently; startup derives implementation availability for declared exports without granting access. Its version remains a code label, and Phase 30 grants use current relational authority through shared permission dependencies.
- Sensitivity defaults and budget hints remain metadata; context policy enforcement and provider selection stay in their owning runtime layers.
- Phase 31 `mutation_operations` declares operation ID/version, payload schema, target entity types and sensitivity. `ContextRuntimeContribution.mutation_adapters` supplies executable strict payload/authorization/validation/execution/reconciliation adapters independently. Sidecar policy can only narrow declared operation references. Domain atomic authorization, exact revision checks and durable operation receipts remain mandatory; the registry does not grant write authority. See [mutation contracts](../mutations/README.md).
- External domain applications retain authority over their data, business rules, and rich UI.

## Entry points and verification

Start with `contracts.py` and `registry.py`. The principal tests are `backend/tests/test_applications.py` and `backend/tests/test_application_scope.py`; the request integration boundary is described in the [Chapter 2 Phase 2 guide](../../../../docs/personal-ai-chapter-2/phase-2-implementation-guide.md). See also [system architecture](../../../../docs/architecture.md) and [application integration plans](../../../../docs/personal-ai-chapter-2/personal-ai-next-scope-detailed-implementation-plans/README.md).

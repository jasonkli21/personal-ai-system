# PI-0 architecture and boundary decisions

Date: 2026-10-30 (America/Los_Angeles). Source inspected:
`8571a8af33969f249614c2652a7d29c0c686f2d8`, `main`.
Status: implementation baseline; independent PI-0 acceptance pending.
[Inventory](pi-0-dependency-inventory.md) supplies exact source anchors;
[report](pi-0-implementation-report.md) owns executed evidence.

## Committed direction and limits

The user directs a standalone, mostly-free, application-agnostic harness for
verified users. Conversation orchestration, context assembly, scoped memory,
retrieval/evidence, inference/tools, budgets, evaluation and observability are
shared capabilities. Travel, Shopping, Finance and Health are optional examples;
domain applications retain authoritative records, revisions, business rules and
rich UI. This direction is accepted; zero-example installation and independent
consumer portability are **unproven targets**.

The user-directed **freeze after MEM-2 is binding**. Preserve MEM-0/1/2 semantics,
formats, fixtures, default-off gates and outstanding acceptance. MEM-3+ needs a
separate explicit unfreeze. PI-4 may govern access to existing memory/profile;
it does not authorize episodic capture, dreaming, taxonomy/extraction changes,
a production memory host, or promotion. PI-0 changes no production behavior.

## Capability ownership

| Capability | Actual owner and existing seam | Boundary to preserve |
| --- | --- | --- |
| Identity/request scope | `auth/{verification,middleware,scope}.py`, `RequestScope`, workspace authorities | Verified owner/actor, exact app/workspace; development `local` is test-only |
| App registry | `applications/{contracts,registry}.py`, `ApplicationContributionCatalog` | Capability declarations are metadata; missing workspace authority denies |
| Context | `context/{runtime,providers,authorization,assembler}.py`, `ContextRuntimeContributionCatalog`, `ContextAssembler` | All model turns use shared token budgets, sensitivity and final permission revalidation |
| Memory | `memory/{contracts,services,knowledge_service,control_service}.py`, `MemoryRepository`, MEM-0/1/2 and lifecycle | Canonical PG knowledge; lossy branch summaries and time-sensitive evidence remain separate |
| Inference | `llm/client.py`, `GenerationClient`, `TokenCountingClient`, `EmbeddingClient`; `llm/providers.py`, LiteLLM gateway | Provider SDKs in adapters; `routing` and `usage` retain admission and physical-send ledger ownership |
| Search/research | `search/{contracts,runtime}.py`, `agents/research`, `entities`, `evidence` | Source rights, freshness, citations, costs and explicit partial results |
| Tools/mutations | `mutations`, federation/grants and registered destination adapters | Existing confirmation/reservation/receipt/reconciliation state machine; destination owns atomic effect |
| Evaluation | `evaluation`, versioned fixtures/locks and focused tests | Synthetic structure is distinct from held-out real utility and external acceptance |
| Data | `persistence/factory.py`, existing PG/pgvector and DynamoDB adapters; artifact tier | One canonical store per record family; historical decoders and anti-replay fences survive extraction |
| Example integrations | `context/{travel,shopping,finance,health,health_federation}.py`, `domains/{travel,shopping}`, itinerary/booking packages, `mutations/shopping.py` | Future optional contributions; no domain truth or credentials migrate into shared core |

## Dependency law and authorization

Target direction: **optional example → published extension/API contracts → core
services → neutral ports → external adapters**. Ports invert implementation
dependencies; a deployment composition root selects adapters. Core must not import
example-specific implementation. The 20 exact current violations are temporary,
implementation-reviewed PI-1 debt, not proof of compliance. The conservative scan
also counts type-only imports and `domains.fixtures`; extraction classification
needs review, not an automatic waiver.

Static imports, runtime plugin loading and default deployment registration are
separate boundaries. `point.load()` executes installed code. Current wheel metadata
registers four context factories; the source-tree fallback also imports them.
Feature-disabled therefore does not mean install-independent. Application catalog
injection currently **extends** the example-filled base. Even an explicit empty
context catalog still passes through federation/task composition and lifespan
compatibility checks. These are observed facts, not PI-0 refactor instructions.

Installed module ≠ declared capability ≠ enabled capability ≠ authorized caller ≠
authorized source ≠ authorized model disclosure ≠ accepted production operation.
A manifest, provider or tool registration grants none of those permissions by
itself. Deny unknown app/workspace, operations, fields and scopes; derive owner
and actor from verified identity. Separate current source access from disclosure,
including counting, summarization and embedding. Sharing needs explicit destination,
purpose, fields, sensitivity and current consent/revalidation. An equal owner ID
is insufficient. The existing global-profile whitelist and destination shares
already implement a narrow view; arbitrary app-private memory sharing does not.

Reuse the listed registries/assembler, generation/embedding/count contracts,
search adapters, usage/routing ledger, memory repository/lifecycle, federation
grants, mutation receipts and persistence factory. No competing store, principal
map, context builder, task engine or lifecycle state machine is justified.

## Provisional choices requiring later review

| Phase | Decisions still open | Required evidence before committing design |
| --- | --- | --- |
| PI-1 | Independent distributions vs optional packages; default registry split; contribution config; optional routes and startup composition | Build/install a wheel physically lacking all example modules, exercise lifespan and legacy opt-in fixtures; inspect entry points and transitive imports |
| PI-1 | Historical row decoding, absent plugin error policy, retained task adapter installation | Existing rows keep IDs/scope; unavailable current execution must not drop retained fingerprint resolution; startup fails clearly for unrecoverable pending work |
| PI-2 | Public HTTP versioning and optional thin SDK, registration/membership lifecycle | Separately installed unrelated consumer uses only public contract; no private imports, core patches or client-selected identity |
| PI-3 | Per-operation selection for generation/count/summary/embed/search; free-strict vs paid-opt-in | Two adapters under same budgets; missing operation fails explicitly; no hidden ancillary Gemini request, paid fallback or duplicate uncertain send |
| PI-3 | Embedding compatibility | Preserve `EmbeddingSpace`, logical model/version/dimensions; no mixed vectors or implicit re-embedding migration |
| PI-4 | Global-profile whitelist evolution and shared memory views | Build on existing profile fields and source grants; keep app-local isolation, exact actor/project checks and default-off memory controls |
| PI-4 | Purpose/destination/field grants, caches, prior summaries, deletion/erasure | Revoke/expire/delete before packing and send; suppress derived reuse; account for already-sent irreversible disclosure and inherited physical-send gap |

Specific future APIs and packaging mechanisms remain provisional. The freeze,
canonical-state boundaries and fail-closed policy are committed constraints.

## Threats, sequencing and rollback

Installed plugins are trusted executable code, not a sandbox for untrusted apps.
An external HTTP client cannot acquire that privilege through a manifest. Review
plugin provenance and public-contract trust separately. Reject scope/header
spoofing, confused-deputy disclosure, stale source reuse and paid fallback.

PI-1 follows independent PI-0 baseline review. Changes must retain old
standalone/null scope decoding, legacy child payloads, app IDs, branch parent and
supersedes links, vector-space identities, grant epochs and source fences.
In-flight tasks keep immutable intent, original operation key, retained fingerprint
and receipt recovery. An uncertain effect is observed with the original key,
never resent. No down migration or removal of deletion/tombstone/receipt evidence
is a rollback strategy. Disable new composition/sharing/provider profiles and
restore the last explicit catalog while retaining forward-compatible state.

[Exit contract](pi-0-exit-contract.md) specifies later proof. Native databases,
real providers, deployed identity, deletion/backups and Phase 36 remain separately
gated; PI-0 local checks cannot close them.

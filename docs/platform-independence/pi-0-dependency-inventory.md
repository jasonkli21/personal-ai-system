# PI-0 dependency inventory

Inspected 2026-10-30 at `8571a8af33969f249614c2652a7d29c0c686f2d8`.
[Machine inventory](pi-0-dependency-inventory.json) contains 60 sorted records:
exact `from`, `to`, allowed `kind`, owner, classification, compatibility risk,
phase and path/line evidence. The 20 implementation edges and four facade edges use paths relative to
`backend/src/`; other records use repository-relative paths. This is source
inspection plus the [executed local checks](pi-0-implementation-report.md), not
external verification.

## Reproduce the bounded static guard

From repository root (stdlib only; no application import or network):

```sh
backend/.venv/bin/python backend/scripts/platform_dependency_inventory.py --help
backend/.venv/bin/python backend/scripts/platform_dependency_inventory.py
backend/.venv/bin/python backend/scripts/platform_dependency_inventory.py --check
backend/.venv/bin/python -m unittest discover -s backend/tests -p test_platform_dependency_inventory.py -v
```

Output schema 1 is sorted by importer/imported module and includes sorted source
lines. No absolute checkout paths, timestamps or file hashes affect output.
The tool reads Python AST only; it never executes `personal_ai.main`, plugins or
settings. It resolves relative imports and package-submodule imports, including
nested and `TYPE_CHECKING` imports, and fails on missing/malformed source.
It scans non-example production importers conservatively as core, including
composition roots, persistence adapters and comparison fixture builders.
`personal_ai.evaluation` is excluded as diagnostic code; tests/scripts are outside
`backend/src/personal_ai`. The explicit example-prefix and example-facade lists
are emitted in output. No arbitrary module-name substring matching or wildcard
waiver is used.

[Exact waivers](pi-0-import-waivers.json) preserve 20 implementation-edge pairs
and add four separately classified facade-edge pairs. Every waiver has a
nonblank string rationale, exact importer/target, PI-1 owner phase and
`implementation-reviewed; independent-pending` status. They are current
implementation review debt, **not independent acceptance**. `--check` rejects
new edges in either category, stale/duplicate waivers, wildcard records and
malformed metadata. It does not update the baseline. A newly documented edge is
never automatically allowed; a future change needs explicit source review and a
separate exact waiver if still necessary. Hermetic tests cover new leaf and
facade rejection, tracked leaf/facade debt, relative/nested/type imports,
classification boundaries, deterministic output, invalid baselines, malformed
sources and repository-baseline agreement.

Example implementations remain the explicit prefixes emitted as
`example_prefixes`. Example-dependent facades are separately limited to
`personal_ai.api.domains`, `personal_ai.domains.fixtures` and
`personal_ai.domains.registry`; neutral `domains.contracts`, `domains.providers`
and shared decision infrastructure are not classified as example facades. The
new `facade_edges` inventory is a direct-import audit, not transitive closure.
The current source has 20 implementation edges and four facade edges. The
original 20 leaf-edge records and waivers are unchanged.

| Importer | Exact static edge count | Migration risk / PI-1 owner |
| --- | --- | --- |
| `context.deployment` | 4 | Four source-tree factories; context composition |
| `domains.fixtures` | 3 | Example schemas in shared fixture builder; comparison/evaluation |
| `domains.registry` | 2 | Lazy Travel/Shopping construction; comparison registry |
| `main` | 4 | Itinerary/booking routes and error contracts; API packaging |
| `mutations.deployment` | 1 | Shopping current/retained adapters; task recovery |
| `persistence.factory` | 2 | Type-only itinerary/booking contracts; factory packaging |
| `persistence.postgres.capabilities` | 4 | Historical row decoders and repositories; persistence |

## Composition that AST cannot prove

The JSON separately records these source-backed paths:

- `applications/registry.py::default_application_registry` composes five manifests,
  calls comparison `domains.registry()` and extends that base with application
  contributions. Catalog injection does not replace the base.
- Application and context catalogs call `entry_points(...).load()`. The installed
  wheel's `backend/pyproject.toml` declares Travel, Shopping, Finance and Health
  context factories; `context/deployment.py` also has the four-import fallback.
  Disabling flags proves neither absent-package imports nor install independence.
- `main.py::create_app` always mounts domain, itinerary and booking routes.
  Lifespan composes context, reconciles federation metadata, installs task metadata
  and verifies retained operation reconciliation compatibility.
- Federation deployment declares Health→Travel dietary, Health→Shopping ergonomic,
  Travel→Shopping trip and Finance→Shopping budget exports. Shopping task deployment
  builds current and retained operation adapters. Declaration is not authorization.
- Ordinary `get_llm_client`, `get_context_assembler`, `get_memory_adapter` build
  Gemini generation, count/summary, extraction and embedding paths respectively.
  External preparation uses an estimated counter and no summarizer. `llm/providers.py`
  can build three generation adapters; gateway count and embedding implementations
  still describe Gemini. No provider composition was changed here.
- Settings contain source URLs/audiences/accounts/timeouts and Shopping task fields;
  repository factory and shared SQL capability adapter retain example storage
  contracts. Migrations 028–031 and scoped record decoding are compatibility
  obligations, not candidates for removal in an extraction.
- `GlobalProfileContextProvider` already exposes a four-field whitelist through
  per-destination `shared_fields` and permission dependencies. PI-4 must extend
  policy only where needed, not recreate this store or erase memory scope checks.
- Memory API requires memory/selection/management flags and an explicit host
  resolver/project mapping. Flags alone cannot install missing trusted authority.

**Limits:** the guard does not trace `importlib`, `__import__`, wildcard imports,
string references, arbitrary entry-point targets, transitive third-party imports,
Python native extensions, HTTP calls, frontend bundling or names in stored rows.
A newly introduced dynamically loaded example could evade it. Manual composition
records are not automatically checked for completeness or automatically waived.
Review changes to prefix classifications and waiver metadata as security-sensitive
architectural policy. PI-1 must supplement this guard with installed wheel and
physical-absence startup tests from the [exit contract](pi-0-exit-contract.md).

## Exact default-off configuration baseline

The following **74 boolean declarations** are literally `False` in
`backend/src/personal_ai/settings.py` at the inspected revision. This complete
superset includes memory, providers, integrations, attestations, inspection,
account controls and protective kill switches. A false kill switch is not a
permission grant. Environment overrides were not read. Uppercase names are normal
BaseSettings environment names; no aliases alter these fields. All declarations
and validators are unchanged by PI-0.

| Settings field | Environment name | Source line |
| --- | --- | --- |
| `task_delegation_enabled` | `TASK_DELEGATION_ENABLED` | 36 |
| `task_shopping_enabled` | `TASK_SHOPPING_ENABLED` | 46 |
| `artifacts_enabled` | `ARTIFACTS_ENABLED` | 56 |
| `artifact_gcs_preflight_verified` | `ARTIFACT_GCS_PREFLIGHT_VERIFIED` | 60 |
| `routing_shadow_enabled` | `ROUTING_SHADOW_ENABLED` | 70 |
| `gemini_free_tier_verified` | `GEMINI_FREE_TIER_VERIFIED` | 79 |
| `gemini_privacy_approved` | `GEMINI_PRIVACY_APPROVED` | 80 |
| `gemini_counter_compatibility_verified` | `GEMINI_COUNTER_COMPATIBILITY_VERIFIED` | 83 |
| `gemini_structured_output_verified` | `GEMINI_STRUCTURED_OUTPUT_VERIFIED` | 85 |
| `gemini_quota_membership_verified` | `GEMINI_QUOTA_MEMBERSHIP_VERIFIED` | 87 |
| `groq_adapter_enabled` | `GROQ_ADAPTER_ENABLED` | 91 |
| `groq_free_tier_verified` | `GROQ_FREE_TIER_VERIFIED` | 94 |
| `groq_privacy_approved` | `GROQ_PRIVACY_APPROVED` | 95 |
| `groq_quota_membership_verified` | `GROQ_QUOTA_MEMBERSHIP_VERIFIED` | 101 |
| `groq_structured_output_verified` | `GROQ_STRUCTURED_OUTPUT_VERIFIED` | 105 |
| `cloudflare_adapter_enabled` | `CLOUDFLARE_ADAPTER_ENABLED` | 107 |
| `cloudflare_free_tier_verified` | `CLOUDFLARE_FREE_TIER_VERIFIED` | 111 |
| `cloudflare_privacy_approved` | `CLOUDFLARE_PRIVACY_APPROVED` | 112 |
| `cloudflare_quota_membership_verified` | `CLOUDFLARE_QUOTA_MEMBERSHIP_VERIFIED` | 117 |
| `cloudflare_structured_output_verified` | `CLOUDFLARE_STRUCTURED_OUTPUT_VERIFIED` | 121 |
| `external_turn_acceptance_enabled` | `EXTERNAL_TURN_ACCEPTANCE_ENABLED` | 137 |
| `p10_cloud_adapters_configured` | `P10_CLOUD_ADAPTERS_CONFIGURED` | 149 |
| `auth_required` | `AUTH_REQUIRED` | 159 |
| `travel_context_enabled` | `TRAVEL_CONTEXT_ENABLED` | 171 |
| `travel_federation_enabled` | `TRAVEL_FEDERATION_ENABLED` | 172 |
| `shopping_context_enabled` | `SHOPPING_CONTEXT_ENABLED` | 179 |
| `finance_context_enabled` | `FINANCE_CONTEXT_ENABLED` | 186 |
| `health_context_enabled` | `HEALTH_CONTEXT_ENABLED` | 193 |
| `health_federation_enabled` | `HEALTH_FEDERATION_ENABLED` | 200 |
| `worker_push_auth_required` | `WORKER_PUSH_AUTH_REQUIRED` | 208 |
| `worker_maintenance_auth_required` | `WORKER_MAINTENANCE_AUTH_REQUIRED` | 211 |
| `provider_usage_inspection_enabled` | `PROVIDER_USAGE_INSPECTION_ENABLED` | 226 |
| `chat_kill_switch_enabled` | `CHAT_KILL_SWITCH_ENABLED` | 227 |
| `research_kill_switch_enabled` | `RESEARCH_KILL_SWITCH_ENABLED` | 228 |
| `worker_kill_switch_enabled` | `WORKER_KILL_SWITCH_ENABLED` | 229 |
| `external_providers_kill_switch_enabled` | `EXTERNAL_PROVIDERS_KILL_SWITCH_ENABLED` | 230 |
| `maintenance_enabled` | `MAINTENANCE_ENABLED` | 231 |
| `export_enabled` | `EXPORT_ENABLED` | 233 |
| `deletion_enabled` | `DELETION_ENABLED` | 234 |
| `context_inspection_enabled` | `CONTEXT_INSPECTION_ENABLED` | 248 |
| `memory_enabled` | `MEMORY_ENABLED` | 249 |
| `memory_extraction_enabled` | `MEMORY_EXTRACTION_ENABLED` | 250 |
| `memory_inspection_enabled` | `MEMORY_INSPECTION_ENABLED` | 251 |
| `memory_knowledge_admission_enabled` | `MEMORY_KNOWLEDGE_ADMISSION_ENABLED` | 252 |
| `memory_knowledge_selection_enabled` | `MEMORY_KNOWLEDGE_SELECTION_ENABLED` | 253 |
| `memory_agent_tools_enabled` | `MEMORY_AGENT_TOOLS_ENABLED` | 254 |
| `memory_user_management_enabled` | `MEMORY_USER_MANAGEMENT_ENABLED` | 255 |
| `memory_user_mutations_enabled` | `MEMORY_USER_MUTATIONS_ENABLED` | 256 |
| `memory_consolidation_enabled` | `MEMORY_CONSOLIDATION_ENABLED` | 277 |
| `memory_contradiction_automation_enabled` | `MEMORY_CONTRADICTION_AUTOMATION_ENABLED` | 279 |
| `memory_forgetting_enabled` | `MEMORY_FORGETTING_ENABLED` | 280 |
| `memory_lifecycle_worker_enabled` | `MEMORY_LIFECYCLE_WORKER_ENABLED` | 281 |
| `memory_lifecycle_inspection_enabled` | `MEMORY_LIFECYCLE_INSPECTION_ENABLED` | 282 |
| `research_enabled` | `RESEARCH_ENABLED` | 290 |
| `research_inspection_enabled` | `RESEARCH_INSPECTION_ENABLED` | 291 |
| `research_retrieval_experiments_enabled` | `RESEARCH_RETRIEVAL_EXPERIMENTS_ENABLED` | 296 |
| `research_provider_storage_approved` | `RESEARCH_PROVIDER_STORAGE_APPROVED` | 302 |
| `research_brave_prepaid_verified` | `RESEARCH_BRAVE_PREPAID_VERIFIED` | 304 |
| `research_brave_auto_reload_disabled` | `RESEARCH_BRAVE_AUTO_RELOAD_DISABLED` | 305 |
| `research_brave_no_paid_balance_verified` | `RESEARCH_BRAVE_NO_PAID_BALANCE_VERIFIED` | 306 |
| `research_brave_source_rights_verified` | `RESEARCH_BRAVE_SOURCE_RIGHTS_VERIFIED` | 307 |
| `iterative_research_enabled` | `ITERATIVE_RESEARCH_ENABLED` | 325 |
| `iterative_progress_enabled` | `ITERATIVE_PROGRESS_ENABLED` | 326 |
| `travel_enabled` | `TRAVEL_ENABLED` | 348 |
| `shopping_enabled` | `SHOPPING_ENABLED` | 349 |
| `domain_inspection_enabled` | `DOMAIN_INSPECTION_ENABLED` | 350 |
| `travel_provider_policy_approved` | `TRAVEL_PROVIDER_POLICY_APPROVED` | 356 |
| `shopping_provider_policy_approved` | `SHOPPING_PROVIDER_POLICY_APPROVED` | 362 |
| `decision_enabled` | `DECISION_ENABLED` | 368 |
| `decision_inspection_enabled` | `DECISION_INSPECTION_ENABLED` | 369 |
| `itinerary_proposals_enabled` | `ITINERARY_PROPOSALS_ENABLED` | 382 |
| `itinerary_proposal_provider_enabled` | `ITINERARY_PROPOSAL_PROVIDER_ENABLED` | 384 |
| `booking_extractions_enabled` | `BOOKING_EXTRACTIONS_ENABLED` | 391 |
| `booking_extraction_provider_enabled` | `BOOKING_EXTRACTION_PROVIDER_ENABLED` | 393 |

`ai_provider` and `ai_model` are required (no Python default); README/example env
select Gemini. `memory_embedding_model` defaults to `gemini-embedding-001`, dimensions
768; `memory_experiment_variant` remains `fixed`. `research_search_adapter` defaults
to `fake` (the synthetic adapter); domain adapters default to fake. These do not prove strict-free
live behavior. No `.env` contents or credential values were read for this inventory.

Frontend server gates require literal `"true"`; the tracked
`frontend/.env.local.example` declares these false:
`API_IAM_AUTH_ENABLED`, `EXPORT_ENABLED`, `DELETION_ENABLED`,
`CONTEXT_INSPECTION_ENABLED`, `MEMORY_INSPECTION_ENABLED`,
`MEMORY_USER_MANAGEMENT_ENABLED`, `MEMORY_LIFECYCLE_INSPECTION_ENABLED`,
`RESEARCH_ENABLED`, `RESEARCH_INSPECTION_ENABLED`, `ITERATIVE_RESEARCH_ENABLED`,
`ITERATIVE_PROGRESS_ENABLED`, `NEXT_PUBLIC_ITERATIVE_RESEARCH_ENABLED`,
`DECISION_ENABLED`, `DECISION_INSPECTION_ENABLED`, `TRAVEL_ENABLED`,
`SHOPPING_ENABLED`, `DOMAIN_INSPECTION_ENABLED`, `ARTIFACTS_ENABLED`.
`src/lib/{domain-proxy,decision-proxy,research-proxy,conversation-proxy}.ts`,
`src/app/{memory,research,development/context}/page.tsx`, layout and API proxy routes
own the corresponding checks. There is no separately declared frontend
`MEMORY_USER_MUTATIONS_ENABLED` gate; backend controls remain authoritative.
The external-turn sidecar relies on backend acceptance and application policy;
no frontend provider flag switches automatic inference.

## Evidence and historical compatibility

The focused tests listed in the JSON exercise default registry, scope decoding,
context composition, synthetic fifth consumer and memory controls. They are not
physical-absence packaging or separately installed public consumer tests.
Preserve old app/workspace/nullable actor identities, v1 standalone rows and child
payloads, migration 028 knowledge/source edges, 029 actor fences, 030 control
receipts, 031 expiry/backfill, branch lineage and provider vector-space identity.
Preserve existing planner locks and evaluator fixture bytes.

The following are **claims carried from owning evidence, not reverified in PI-0**:
[MEM-1 source-fence capacity](../memory/mem-1-tombstone-capacity-follow-up.md),
[MEM-2 remediation](../memory/mem-2-review-remediation-2026-10-30.md),
[current state](../current-state.md) and
[Phase 36](../personal-ai-chapter-2/phase-36/implementation-report.md).
They retain independent MEM-0/1/2 and Phase 36 review, production issuer/lease and
identity, provider-send, DynamoDB/native-store, cloud, source revocation,
physical erasure/backup recovery and cost gates. Forget receipts grow permanently;
source fences retain a separate 1,024 cap. Proposal cleanup has a maintenance hook
but deployed/native deletion acceptance remains open. No PI inventory edge or local
fake closes these gates.

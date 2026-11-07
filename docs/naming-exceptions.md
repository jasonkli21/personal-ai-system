# Naming compatibility register

Active source, module, test, fixture, script, command, comment, and current documentation names use enduring capability names. Phase labels are not valid new identifiers. The naming-policy check scans active source and tests, command/configuration surfaces, current module READMEs, and current documentation. It has no broad phase-file or fixture-directory allowlist.

Historical plans, dated reports, the earlier root reasoning-engine PRD, and frozen locks remain at their original paths so their provenance and citations stay intact. They are historical records, not active naming examples.

## Frozen evaluation identities

The following fixture files were renamed to capability-oriented paths while preserving their exact bytes. The naming check pins each file to its SHA-256 digest and fails if any frozen content changes. Their suite, rubric, and case identifiers remain readable by the evaluator because historical measurements and paired denominators refer to them.

- `evaluation/fixtures/offline_information_handling/cases-v1.json`, `cases-v2.json`, `manifest-v1.json`, `manifest-v2.json`, and source generations 2 through 9 preserve `pi6-*`, `PI-6`, and `P6-*` corpus identities.
- `evaluation/fixtures/memory/memory-task-cases-v1.json` and `memory-task-cases-v2.json` preserve the `mem0-*` benchmark, rubric, schema, and case identities.
- `evaluation/fixtures/memory/memory-knowledge-pairs-v1.json` and `memory-knowledge-consumer-v1.json` preserve the `mem1-*` suite identities.
- `evaluation/fixtures/memory/memory-control-v1.json` preserves the `mem2-*` control-suite identity.

The active offline source manifest is schema 3, source contract `offline-benchmark-source-closure-v1`, generation 10. It records the frozen corpus identity separately from current source paths. Its `legacy_corpus_identity` keeps `pi6-offline-v2` and `pi6-rubric-v2` so unchanged case bytes remain loadable; generation 10 changes source identities and is not validated by prior measurements. Prior manifests and cases are never rewritten. Planning locks v1 through v35 are historical, unchanged evidence; the new lock is additive.

## Persisted identifiers and migration boundaries

| Exact identifier or record | Owner and technical reason | Compatibility boundary |
| --- | --- | --- |
| `phase8-run:` and `phase8-research-session` | Iterative research UUIDv5 seeds derive IDs already stored in run/session records. | Changing either seed would orphan existing records; retire only with an explicit ID migration. |
| `phase21-root-v1` and `phase21-reselection-v1` | Routing UUIDv5 seeds derive persisted decision IDs used for replay and idempotency. | Keep byte-for-byte while existing decisions remain addressable. |
| `phase9-owner-v1` and `phase9-chat-owner-v2` | Owner migration versions select the established migration and owner-binding identities. | Existing local identities and migration receipts rely on these exact values. |
| `pi3-execution-v1` and `pi3-local-json-bytes-v1` | Serialized execution profile and local usage-counter identities appear in execution and evidence records. | A future counter/profile migration must read old values and version new ones. Internal code and provider-facing names are capability-oriented. |
| `mem2:` | Memory-control idempotency-key namespace. | Retry identity depends on the prefix; keep until receipts are migrated. |
| `mem1_verified_knowledge` | The context-inspection response exposes this established `requested_variant` and `applied_variant` wire value. Internal selection uses `verified_knowledge`; the inspection serializer preserves the prior response value for existing consumers. | Retain until a separately versioned API migration changes the response contract. |
| `phase5-{provider}-snippet-v1` and `phase5-research` | Source adapter and research-provider IDs are retained in citation attribution and provider registrations. | Display labels use provider names; data IDs remain stable for existing source records. |
| `mem0-*`, `mem1-paired-v1`, `mem1-consumer-v1`, and `mem2-control-v1` | Frozen memory suite, rubric, case, and consumer identifiers remain inside the byte-pinned corpora above. | Evaluator contracts accept these exact historical values; current filenames and output labels are capability-oriented. |
| `phase13-envelope-byte-estimate-v1` | Historical planning locks bind this metric identity; the current additive lock carries the same label so prior measurements are not reclassified. | Current runtime code emits the neutral `planning-envelope-byte-estimate-v1`; historical measurements keep their recorded identity. |
| `phase36-matrix-v1`, `phase36-external-evidence-v1`, `phase36-verifier-environment-v1`, and `P36-*` | Serialized verification schemas and row IDs are already used by matrices and release receipts. The active matrix also points to immutable historical authority documents by their original paths. | Keep schemas, row IDs, and historical authority paths stable; a future evidence migration must be explicit and versioned. |
| `phase-36` verification artifact paths | The verifier reads and writes artifacts under an established historical evidence directory; moving the records would break review links. | Preserve these artifact paths while new current-state reports use capability-oriented paths. |
| `P8-*`, `pi-8-verification`, `pi-8-review-verification-v2`, `pi8-audit-v1`, and `pi8-command-receipts-v2` | The release evidence checker validates the existing ledger and receipts. | These are immutable evidence identifiers, not new command or module names. |
| `P10_CLOUD_ADAPTERS_CONFIGURED`, `P10_NEON_RUNTIME_DSN`, `P10_NEON_POOL_MAX_SIZE`, `P10_DYNAMODB_REGION`, `P10_DYNAMODB_TABLE_NAME`, `P10_DYNAMODB_ROLE_ARN`, `P10_DYNAMODB_IDENTITY_TOKEN_AUDIENCE`, and `P10_SCHEMA_POSTGRES_DSN` | Deployed environments may still provide the earlier persistence configuration names. Canonical names are now `DEPLOYED_*` and `POSTGRES_SCHEMA_DSN`. | Old aliases remain accepted during configuration migration; remove only after deployed environment inventory confirms migration. |
| `p10_runtime` and `p10_storage_migration` | These are existing Neon/Postgres IAM role names referenced by infrastructure grants and deployed policies. | Renaming them requires a coordinated cloud IAM/database role migration, which is outside local naming cleanup. |
| `p19-resource-projection-v1` | Serialized quota/resource projection schema used by existing usage observations. | Keep until stored projections and their consumers have a versioned migration. |
| `p22-selected-executed-route-only-v1` | The adaptive-routing snapshot records the historical labeling policy used to create its immutable observation set. | Do not relabel existing measurements; new data uses the capability-oriented policy identity. |
| `Phase 33` in the retrieval baseline's `tested_revision` | This is provenance for a frozen historical measurement, not an active capability name. | Preserve the recorded test revision; the source manifest binds its exact fixture bytes. |

The verifier schemas, historical verification paths, persisted IDs, legacy environment aliases, and frozen measurement provenance above are the only phase-coded text exceptions in active files. The import-waiver policy itself now uses the capability name `platform-independence`. `backend/scripts/naming_policy_check.py` scopes each exception to exact identifiers and owning paths or contract fields. It rejects new names and does not exempt the renamed offline evaluator paths, scripts, tests, modules, or fixture directory.

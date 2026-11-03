# Documentation router

Read [current state](current-state.md) for implementation and release boundaries. Then read only the task route below, the owning module README, executable contract, and focused tests. The [root README](../README.md) and [Makefile](../Makefile) own setup and commands.

## Authority

Code, executable contracts, migrations, and tests → dated verification/review evidence → accepted ADRs → architecture/product intent → authorized plans → history. Security and privacy constraints apply throughout. Plans and fake tests do not prove delivery or external acceptance.

## Routes

| Task | Start here |
| --- | --- |
| Architecture and boundaries | [Architecture](architecture.md), [current state](current-state.md) |
| Core startup and API | [API contract](api-contract.md), `backend/src/personal_ai/` |
| Harness excellence, SDK and Checklist | [HXE-0 capability inventory](harness-excellence/README.md) |
| HTTP consumers and reference apps | [Consumer contract](platform-independence/consumer-v1.md), [reference apps](../reference-apps/README.md), [Reading Logbook](../examples/reading-logbook/README.md) |
| Inference and routing | [LLM README](../backend/src/personal_ai/llm/README.md), [routing README](../backend/src/personal_ai/routing/README.md) |
| Context and chat | [API contract](api-contract.md), `backend/src/personal_ai/context/`, `services/chat/`, focused tests |
| Memory | [Memory README](../backend/src/personal_ai/memory/README.md), [memory docs](memory/) |
| Retrieval and tools | [Retrieval README](../backend/src/personal_ai/retrieval/README.md), [retrieval contract](platform-independence/retrieval-v1.md) |
| Research | [Research guide](research-agent.md), `backend/src/personal_ai/agents/research/` |
| Authentication and security | [Threat model](phase-9-threat-model.md), `backend/src/personal_ai/auth/`, [security policy](../SECURITY.md) |
| Persistence and recovery | [Persistence README](../backend/src/personal_ai/persistence/README.md), [operations](../stabilization/OPERATIONS.md) |
| Frontend and sidecar | [chat feature README](../frontend/src/features/chat/README.md), [API contract](api-contract.md) |
| Evaluation and experiments | `backend/src/personal_ai/evaluation/`, fixture/lock and focused tests; [current status](current-state.md) |
| Operations and release gates | [Current verification](../stabilization/VERIFICATION.md), [operations](../stabilization/OPERATIONS.md), [current state](current-state.md) |
| Platform-independence review | [PI index](platform-independence/README.md), then the specific gate and dated evidence for the task |
| Maintainability or future work | [Quality assessment](../stabilization/CODE-QUALITY.md), then the specifically authorized plan |

## Evidence and history

Use the owning code and tests first. Dated reports preserve what was checked at a particular revision; they do not override current behavior or close a gate without explicit acceptance. Historical plans and predecessor indexes remain discoverable under `docs/history/` and `docs/personal-ai-chapter-2/` but are not default context.

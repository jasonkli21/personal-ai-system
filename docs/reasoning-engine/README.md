# Reasoning policy and offline evaluation

The reasoning package provides versioned, bounded strategies over prepared context. Execution authority remains with the shared context assembler, routing, inference gateway, and registered verifiers. The available synthetic comparison is offline and does not establish real-model utility.

## Current boundaries

- Direct response is the default behavior.
- Decomposition, critique, candidate comparison, evidence research, and tool verification remain bounded and read-only or proposal-only.
- Adaptive recommendations remain disabled for normal execution. Existing evaluation recorded `NO_PROMOTION`; the available features do not establish safe selection for a user workflow.
- Synthetic preview and workflow integrations remain separately gated. Local fake checks do not establish source permissions at physical send, installed hosted inference, rollback-safe restore, or real-task quality.

Read [architecture](architecture.md), [benchmark contract](benchmark-contract.md), [adaptive selection](adaptive-selection.md), and the [threat model](threat-model.md). The [current implementation state](../current-state.md) is the living readiness source. Dated evidence remains in its historical location and retains its original measurements and provenance.

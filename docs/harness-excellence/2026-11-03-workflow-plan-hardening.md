# Workflow plan hardening — 2026-11-03

Baseline: `6d9fd3c4252e3e2bde6563af76d7a896af7de5f8`. Three untracked
companion plans belong to the user and are excluded from the commit.

- **NOW, design blocking.** RE-2 does not exist as a lifecycle owner. ADR 0025
  assigns strategy to future reasoning and physical workflow lifecycle to PAS.
  Preserve continuation keys, domain delegation and P19. Reuse PI-5 exact tool
  registration, source snapshot and retrieval service. MCP remains its own
  installation boundary. Chat events are live turn events and cannot serve
  as workflow replay. OpenCode execution is outside PAS.
- **NOW, design blocking.** Use one additive PostgreSQL migration and one row
  per scoped original key. Serialize updates with row locks and fence writers
  with a lease token. Commit the attempt before entering the handler, and
  commit its receipt with progress. An expired in-flight attempt goes to
  uncertainty. A takeover between attempts may continue. Cancellation
  serializes with admission and is rechecked at cooperative boundaries.
- **NOW, design blocking.** The versioned contract closes the tool set to
  installed local retrieval, with static typed inputs and order-only
  dependencies. Bound total storage admission, step count, time and bytes.
  Keep outputs transient and replay canonical metadata. This removes retained
  source-body disclosure and avoids a new evidence store. Fresh source
  authorization and snapshot checks still apply to execution and disclosure.
- **BEFORE_ENABLEMENT, live only.** Existing receipts leave issuer/send
  linearization, trusted installed peers and monotonic original keys across
  restore open. A subprocess is not an isolation boundary. Generic effects
  remain unavailable and domain confirmation stays with its current owner.
- **DEFER.** Public API/SDK, model/strategy selection, dynamic dataflow,
  scheduling, parallel dispatch, MCP peer dispatch and native adapters.
  No external-consumer compatibility or live-source claim follows from tests.

Deliverables are `contracts/workflow.py`, `workflow/service.py`,
`persistence/postgres/workflows.py`, migration 034, `tests/test_workflow_contract.py` and
`tests/persistence/test_workflow_postgres.py`, ADR 0025, and dated verification. E1 needs a bounded
multi-step query, durable key replay/conflict, cancellation, rights and
lease-loss cases, cursor gaps and zero external/effect sends. A missing native
store means partial E1. A local database does not close E2 installed/native
isolation or E3–E5 gates.

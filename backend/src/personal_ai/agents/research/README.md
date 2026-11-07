# Research orchestration

This package coordinates bounded, owner-scoped research. Search/provider calls remain in adapters; evidence validation and shared context/inference contracts remain in their owning packages. Research sessions do not write chat messages or durable memory.

## Module map

- `contracts.py` and `repositories.py` define research request/session state and the repository contract.
- `service.py` runs a bounded single-pass request: query planning, provider attempts, evidence selection, synthesis, expiry, and fenced session persistence.
- `personal_ai.search.planning`, `runtime`, and `authority` own query envelopes, adapter composition, and source-rights dependencies.
- `iterative/` contains the typed iterative run, budget, event, state, repository, and fixture modules.
- `iterative/service.py` owns sufficiency and gap assessment, follow-up sequencing, run transitions, resource reservations, cancellation/recovery fences, and safe progress events.

## State and verification

Research sessions store queries, attempts, observations, selected evidence, citations, and answers in expiring owner-scoped records. Iterative runs are separately versioned and linked to a session. Transactions and fences protect state transitions and stale-worker recovery; uncertain external calls are not silently retried. Iteration, progress, and decision gates remain off by default; single-pass research is the normal path.

Use `backend/tests/test_research_pipeline.py`, the route tests, and the iterative research tests for focused coverage. `make research-eval` and `make iterative-research-eval` run synthetic baselines. See the [research task router](../../../../../docs/README.md) and [research guide](../../../../../docs/research-agent.md).

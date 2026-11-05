# RE-2 independent-review remediation

2026-11-05, America/Los_Angeles. Remediation for the three P2 findings in the
independent review handoff. The synthetic profile remains default-off. This
report records local evidence only; it does not close independent E1
acceptance.

## Findings addressed

| Finding | Repair |
| --- | --- |
| F01 — pure verifier crash/cancel treated as an uncertain external effect | The canonical workflow row recognizes only the registered `reasoning.verify.v1` operation as a deterministic local predicate. A dispatched predicate consumes verifier budget conservatively. Lease recovery can recompute it under the same plan, fence, step binding and checkpoints only if remaining finite verifier budget allows. Otherwise the run ends `budget_exhausted`. Cancellation during a verifier settles as `cancelled`; unknown inference dispatch remains `uncertain_effect` and is never resent. |
| F02 — durable verifier identity and decision lost | Successful verifier attempts now persist an optional `reasoning-verifier-receipt-v1` containing the catalog verifier ID, objective verdict, bounded defect count and sufficiency decision. The receipt is written with the canonical step success. It contains no candidate text, operands, prompts or source text. The extension is additive; prior v1 payloads without it still decode. |
| F03 — benchmark seal can be advanced with its fixtures | The test suite pins the external v1 seal SHA-256 and semantic result SHA-256, tests synchronized case/seal mutation, and runs always-pass and always-inconclusive verifier canaries. Existing v1 cases, manifest, runner, fixture and seal bytes remain unchanged. |

The synthetic profile keeps the existing workflow row, original key, stable
child identities and atomic attempt/event transitions. No migration or second
ledger was introduced. Authority loss at a committed boundary still suppresses
output and retains the conservative reconciliation outcome. No E2–E5 claim is
made.

## Verification

| Command | Result |
| --- | --- |
| `make reasoning-orchestrator-check` | 57 passed; offline network audit: zero attempts. Includes crash-before/after-predicate recovery, verifier-budget exhaustion, cancellation, receipt compatibility, seal tampering and degeneration canaries. |
| `make reasoning-orchestrator-eval` in two fresh processes | Both: 60 pairs, 28 held out, 36 eligible, +22 eligible exact completions, +7 held-out, zero vetoes, zero simple-cohort extra calls; `OFFLINE_SIGNAL_ONLY`; semantic SHA-256 `660e5130374a633d9ac5001293393d1950d5b99b6f694ec8e42840f7bcbc0db5`. Original v1 seal SHA-256 remains `b09605c139eee55730e51625e556959a98570187814d859589afbfe01fe4c414`. |
| `make reasoning-check` twice | 122 passed each run; both offline network audits recorded zero attempts. |
| `make reasoning-eval` twice, sequential fresh processes | Both: 64/64 valid; historical semantic SHA-256 `9c1335f421c00b36f863f7c55c2321d92a02d68358f5887c6bcf8cd8c8fb2ae2`. |
| `make workflow-check` | 70 passed. |
| `make backend-lint`; `make naming-policy-check`; `git diff --check` | Passed. |
| `make sdk-check` | 354 passed, 25 failed, 12 deselected; zero Python-network attempts. Failures are inherited planning/PI-6 source-identity gates and are not attributed to RE-2. |
| `make consumer-contract-check` with a writable temporary UV cache | Package builds and dependency inventory passed; the core evaluation probe stopped at inherited `planning_baseline_changed_requires_new_version`. |
| `make provider-isolation-check` | Blocked: the sandbox denied binding the local probe socket (`PermissionError: Operation not permitted`). |
| `make backend-test-offline` with SDK and example paths | 2,969 passed, 36 failed, 159 errors, 1 skipped, 198 deselected. Failures/errors cluster in inherited planning/PI-6 identity assertions and sandbox-constrained retrieval/HTTP listener tests. The run is not attributed to RE-2. |

The native PostgreSQL gate is **BLOCKED**, not passed. No
`PERSISTENCE_TEST_POSTGRES_DSN` is configured. A disposable PostgreSQL 17
cluster could not initialize because the sandbox denies shared-memory creation
(`shmget: Operation not permitted`), and the local pgvector installation has
extension control files but no `vector.so`. `make workflow-postgres-check`
stopped at its DSN preflight. The two native crash-boundary tests were added
but could not be independently executed here. Native multiprocess durability,
leases and atomic receipt behavior therefore remain unproven in this session.

## Remaining gates

E1 durability requires the focused PostgreSQL suite against a disposable,
migrated PostgreSQL/pgvector database, including independent process recovery
before and after the pure predicate. E2 installed inference/accounting, E3
provider and source authorization, E4 deployment/restore, and E5 real-model
utility remain unverified or blocked as recorded in the living
[implementation status](../current-state.md). Keep the profile disabled until
those gates receive their required evidence and review.

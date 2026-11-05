# RE-3 independent-review remediation receipt

2026-11-05. Remediation of the independent review findings against
`9cd3e433150547bf9231148cb1eb5fc2920a276d`.

## Findings addressed

**RE3-01 — result-set completeness.** Grounded retrieval accepts only the
registered local source. After validating the returned items' provenance, it
rebuilds the bounded `LexicalIndex` from the same pinned snapshot and current
scope, then compares the complete deterministic `RetrievalOutcome`, including
ordered items, state, reasons, and byte counters. The comparison uses the
original query and report-limit behavior. It is read-only and does not invoke
the retrieval tool again. A mismatch or unavailable proof fails closed before
coverage, synthesis, or sufficiency can proceed. Existing authority, deadline,
attempt, and cancellation guards remain in place.

Regression cases cover omission of a conflicting authorized item with
recomputed counters, forged complete and budget-reason claims, a clipped
source, reordered results, and a valid item from a different query. Existing
tests continue to cover per-item revision, quote, rights authority and epoch
validation; conflict abstention; no-extra-follow-up when already sufficient;
rights changes; cancellation; and fake dispatch boundaries.

**RE3-02 — benchmark interpretation.** The frozen fixture, seal, runner, and
case identities were not changed. The verification report now labels the
`direct` arm as a source-free abstention safety negative control and excludes
its 0/30 from task-utility comparisons. It describes the 18/30 versus 30/30
one-shot/grounded result as a scripted within-grammar ablation, discloses 60
versus 84 actual local reads, and distinguishes this work from their shared
permitted resource envelope.

## Verification

- `make reasoning-grounded-check`: **77 passed**, network fence reported 0
  attempted operations.
- `make reasoning-grounded-eval`, twice: both passed, 180 rows each,
  0 safety vetoes, original semantic SHA-256
  `29d2f779ea9ee127e134a2c4fd4555a8772f2e3ca77d9fdcf86f71bbf27b9e99`.
  Original sealed fixture identities were unchanged.
- `make reasoning-check`: **122 passed**, network fence reported 0 attempts.
- `make reasoning-eval`: **64/64 rows valid**; semantic SHA-256
  `9c1335f421c00b36f863f7c55c2321d92a02d68358f5887c6bcf8cd8c8fb2ae2`.
- `make reasoning-orchestrator-check`: **57 passed**, network fence reported
  0 attempts.
- `make reasoning-orchestrator-eval`: **60 pairs**, semantic SHA-256
  `660e5130374a633d9ac5001293393d1950d5b99b6f694ec8e42840f7bcbc0db5`.
- `PATH="$PWD/backend/.venv/bin:$PATH" make workflow-check`: **70 passed**.
- `PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint`: passed.
- `make naming-policy-check`: passed.
- Focused retrieval/context/chat/inference/usage checks with inherited proxy
  variables unset: **130 passed**. `git diff --check`: passed.

Native PostgreSQL/pgvector validation is **BLOCKED**: this session has no
`PERSISTENCE_TEST_POSTGRES_DSN`. No database was created or targeted.

## Disposition

The code remediation addresses the demonstrated conditional E1 result-envelope
failure at the local fixture boundary. It does not independently establish
E1 acceptance. A separate review of the resulting commit is still required.
The grounded profile remains default-off; live issuer and physical-send
authority, deployment and rollback evidence, and real-model utility remain
open or blocked as recorded in [the release gates](re-3-blockers.md).

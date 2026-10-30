# MEM-2 independent review remediation

Date: **2026-10-30**, America/Los_Angeles. The implementation changes are based on
reviewed entry commit `c0add2b15ec7dc6b4879bafdb0ec01e1b0eb68d6`. This is remediation
evidence, not independent acceptance. The separate
[review handoff](mem-2-independent-review-handoff.md) remains unchanged.

## Disposition

The review's local, code-addressable findings were handled as follows:

| Finding | Remediation |
| --- | --- |
| F1 — receipt quota blocks forget | The 256-row quota now applies only to proposal/review receipts. Forget receipts remain durable and do not consume it. A hermetic regression fills the ledger with 256 conflicting forget receipts, then verifies a correct forget and exact replay. All operation receipts remain unpruned; unbounded ledger growth and native physical-capacity/restore behavior are still P1 promotion blockers. |
| F2 — project revision drift breaks retry | New receipt fingerprints bind project ID and immutable intent, not the mutable project revision. Migration 031 backfills project IDs for existing receipts whose target rows remain; exact user-action retries still pass through current owner/actor/project authorization. |
| F3 — idle proposal text is retained | Added a bounded `purge_expired_proposals` repository operation, invoked by the existing authenticated scheduled-maintenance pass, plus migration 031's global expiry index. Expiry remains immediately hidden. Native idle-GC/concurrency, deployed scheduler execution, backup and replica deletion were not verified. |
| F4 — stale history cannot be forgotten | Current project authorization and exact owner/actor binding still apply. Forget no longer requires source evidence to be current, allowing suppression after expiry or source revocation without restoring readability. Lost project membership still needs a separate owner-authorized erasure path. |
| F5 — candidate 33 denies search | Reads check at most the first 32 recent candidates and set `truncated=true` whenever more may exist. Search remains lexical and candidate-limited; query-cost reduction and task utility are not claimed. |
| F6 — proposal retry identity | No live dispatcher or new orchestrator was added. A trusted run/tool-call/attempt identity and durable pre-dispatch operation-key contract remain prerequisites to registering a model host. |
| F7 — reload loses unknown operation | The browser stores only the path, operation ID, expected version, confirmation, decision and a non-secret actor binding in tab-scoped `sessionStorage`. It stores no token or proposal content, restores the same request after reload, and clears on terminal results or actor change. Server authorization remains authoritative. |
| F8 — broad evaluator label | The evaluator separates active-knowledge, pending-proposal and control-receipt mutation counters. Its output states that the 36 scenarios are author-visible and the six tagged holdouts are not blind. Source/lineage and native SQL effects are outside these counters. |

Flags remain default-off. No provider, cloud, account, production or live model action
was run. The MEM-0, MEM-1, Phase 36, issuer, project lease, provider-send and deployed
deletion gates remain open.

## Verification

The source changes were tested on the working tree based on
`c0add2b15ec7dc6b4879bafdb0ec01e1b0eb68d6`; this report and related status-document
updates do not change runtime source. The corresponding single commit is identified
by the repository history after commit.

| Check | Result |
| --- | --- |
| `PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint` | Passed. |
| `backend/.venv/bin/python -m pytest tests/test_memory_control.py tests/test_memory_control_api.py tests/test_memory_control_context.py tests/test_phase9_controls.py -q` from `backend/` | **82 passed**; three dependency deprecation/future warnings. |
| `backend/.venv/bin/python -m personal_ai.evaluation.memory_control` from `backend/` | **36/36 passed**; corpus SHA-256 `7d2e93b33904ddb81bef6e4f8f3ffff89a51b7d63b85b5e88c21877c4b6c2a9d`. All five reported counters were zero. This remains synthetic evidence, not blind security evidence or model utility. |
| `pnpm exec vitest run tests/features/memory/memory-panel.test.tsx tests/app/api/memory/route.test.ts tests/lib/auth.test.ts` from `frontend/` | **12 passed**, three test files. |
| `pnpm run typecheck` from `frontend/` | Passed. |
| `git diff --check` | Passed. |

The focused tests used the bundled Node/pnpm runtime where needed. Native PostgreSQL
tests were not run because `PERSISTENCE_TEST_POSTGRES_DSN` is not configured. The
general `make backend-test-offline` suite was not run: the independent handoff reports
that it attempted an unauthorized Google API request and says not to retry until
provider paths are isolated and egress is blocked. No cloud or provider result is
inferred from local fakes.

## Remaining blockers

- **P1 — operation ledger capacity and recovery:** The artificial 256-row ceiling no
  longer blocks forget. Forget receipts remain indefinitely to preserve replay
  protection; safe churn, restore behavior, physical storage headroom and native
  concurrency need verification. The separate 1,024 source-fence cap remains.
- **P1 — physical proposal retention:** Migration 031 and the maintenance hook are
  present, but native transaction/concurrency evidence and deployed scheduler,
  replica, backup and account-erasure behavior remain unverified.
- **P1 — independent review and inherited gates:** This implementation's checks do
  not constitute MEM-2 independent acceptance or close MEM-0, MEM-1, production
  identity/issuer, host registration, physical provider-send, cloud or Phase 36 gates.
- **P2 — host retry identity:** Before any model dispatcher registration, persist a
  trusted run/tool-call/attempt-to-operation mapping before first dispatch and test
  crash-before-ack recovery. Model-supplied operation IDs remain forbidden.
- **P2 — bounded search cost and usefulness:** Candidate results are now marked
  incomplete, but no index, query consolidation, p95 SQL envelope or model utility
  improvement is claimed.
- **P2 — browser and physical deletion acceptance:** Unit tests cover tab-scoped
  recovery; actual browser identity switching and deployed cleanup/backup behavior
  remain separate verification.

Keep all memory-control flags disabled until the owning independent and deployment
gates are closed.

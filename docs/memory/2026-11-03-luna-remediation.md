# Terminal-step review remediation

Date: 2026-11-03 (America/Los_Angeles). Reviewed baseline: `09f3ef1158645c3c350ea5ea0e52a2a88b32585b`, parent `42f00b0f93b0987f615657d4d8b9c145c6c6b016`. This report records the local remediation of the supplied independent review. It does not claim independent acceptance, a complete MEM-3 implementation, or production readiness.

## Decision and changes

The review's source-withdrawal witness is possible because there is no authenticated monotonic source epoch and no automatic withdrawal/purge integration. The service therefore no longer allows host booleans to enable capture or selection: both methods always return `disabled`. The PostgreSQL bucket and in-memory adapter remain experimental, read-disabled projections. Existing rows are not eligible for read; no migration re-enables or rewrites them. A future enablement requires an issuer-backed source generation, canonical memory lifecycle/erasure integration, stale-restore handling and native evidence.

Authenticated local maintenance now derives the same namespace from the verified owner, app, workspace, exact actor, audience, client and supplied project identity without resolving the source project. Maintenance remains available when the memory feature flag is off. Exact-namespace forget can suppress a retained lifecycle state and delete its payload; purge deletes all payloads in that namespace and writes forgotten states where available. Both retain original-run receipts. These operations do not grant read access. PostgreSQL owner-wide erase remains an operator seam requiring the canonical owner deletion fence; automatic account-erasure registration is still absent.

The structural validator now enforces a 16 KiB combined input bound. A whitespace-padded valid pair test proves that two individually bounded inputs whose combined size exceeds the limit are rejected. The frozen 38-case corpus digest remains `a3caf35b5b59b20e9e932a87fa1a1cb1719036a15ccf077e1cc04eedae459e77`.

## F-01–F-10 disposition

| Finding | Disposition |
| --- | --- |
| F-01 withdrawal/regrant resurrection | **Mitigated by hard disable; source epoch contract remains blocked.** Capture and selection cannot be enabled by constructor options. Old stored rows remain inaccessible; purge can erase payload when the exact namespace is known. No live issuer, stale clone, or concurrent source mutation test exists. |
| F-02 deleted/unresolvable project blocks erasure | **Fixed for exact-namespace forget/purge.** Maintenance no longer calls `authority.project`, requires a source lease, or depends on the memory feature flag. Wrong owner/app/workspace/actor/client/project maps to another namespace and cannot erase the seeded record. Account-wide orchestration and owner erasure remain external/operator work. |
| F-03 separate lifecycle store | **Resolved by disabling use.** Migration 035 and JSON lifecycle projection remain experimental and are explicitly not described as canonical lifecycle integration. A typed adapter and atomicity design are blocked follow-up work. |
| F-04 replay status before current source validation | **Mitigated by hard disable.** Capture emits only `disabled`, so saved/replayed/conflict outcomes are not exposed. Exact retry and changed-intent semantics require redesign with the trusted issuer before capture returns. |
| F-05 producer, issuer, source edges and physical send | **Blocked.** No producer, model context, external send, trusted original-submission binding or monotonic issuer exists. |
| F-06 frozen source identity mismatch | **Blocked and reproduced.** Historical lock expectations were not changed. The final isolated source-lock test fails: expected v35 digest `4eb58162ae39387382c18b524017886c1be4e4fc27de5203ac064f5c6e889cc9`, computed committed-tree digest `6ede19fb2162d6a7f7ba939daa5405d6ae8eed65f1fe8d35901eb09b5011e74a`. An earlier run before the final focused-test adjustment computed `a3bf052cd3ed3dfba641a16227592a7bacc2d1875f16757ef6f2549a37e987de`. The prescribed `make provider-isolation-check` could not start because this sandbox denied its local socket bind (`PermissionError`); the provider-isolation suite was not run. |
| F-07 combined input size | **Fixed.** The validator and README agree on at most 16 KiB combined. Boundary regression passes; corpus bytes and scores were not edited. |
| F-08 native/adversarial/utility evidence | **Partially addressed; phase gate blocked.** Synthetic tests now cover disabled capture/selection, source-project lookup failure during exact maintenance, namespace isolation, and the combined-size boundary. PostgreSQL DSN is unset. Native migration, concurrency, rollback across processes, restore, issuer lease and task utility are not established. |
| F-09 status story | **Fixed in living status and module README.** Only source-only local E0/E1 synthetic development is described as unfreezed. The older extension report remains historical and is explicitly superseded where it describes capture/selection as usable. |
| F-10 useful procedure/outcome absent | **Blocked.** No prose or raw tool data was added. A future utility study needs a separately verified narrow procedure/outcome, trusted original submission and source contract, plus a matched task evaluation. |

## Verification

Commands ran from the repository with `PATH="$PWD/backend/.venv/bin:$PATH"` unless shown otherwise. Python was 3.11.15 on macOS arm64. The focused pytest run emitted dependency deprecation warnings; they did not affect results.

| Command | Result |
| --- | --- |
| `make memory-episode-check` | PASS, 93 tests |
| `make memory-episode-candidate-eval` | PASS, 38/38 structural cases, 0 false support, fixture digest unchanged; synthetic consistency only |
| `make backend-lint` | PASS |
| `make naming-policy-check` | PASS, checker plus 2 tests |
| `make workflow-check` | PASS, 70 tests |
| `make memory-task-eval` | PASS, deterministic replay; scripted synthetic task proxy only |
| `make memory-knowledge-eval` | PASS, synthetic proxy only |
| `make memory-knowledge-causal-eval` | PASS, deterministic packed-context proxy only |
| `make memory-control-eval` | PASS, existing synthetic evaluation |
| `make memory-eval` | PASS, existing synthetic evaluation |
| `cd backend && .venv/bin/python -m pytest -q tests/test_planning_experiment.py::test_current_planning_lock_binds_owner_portability_source_without_promoting` (final committed tree) | FAIL, 1 test; computed digest `6ede19fb2162d6a7f7ba939daa5405d6ae8eed65f1fe8d35901eb09b5011e74a` differs from frozen v35 expectation |
| `PATH="$PWD/backend/.venv/bin:$PATH" make provider-isolation-check` | BLOCKED before suite: sandbox denied local socket bind; no provider-isolation pass claimed |
| `make memory-episode-postgres-check` | NOT RUN: `PERSISTENCE_TEST_POSTGRES_DSN` is unset |
| `make workflow-postgres-check` | NOT RUN: no disposable PostgreSQL DSN; no native workflow claim |
| `git diff --check` | PASS |

No source-withdraw/regrant lease race, stale database restore, cross-process PostgreSQL transaction, physical deletion, E2–E5 evidence or model utility was established. E1 here means local synthetic regression only. Full MEM-3 is **BLOCKED/PARTIAL**, independent acceptance **pending**, and production **NO_GO**.

## Adversarial matrix and rollback

Forged internally consistent receipts remain consistency-only and cannot reach capture or selection. Scope mismatch is covered by authenticated namespace isolation tests; selection stays disabled for all scopes. Withdrawal/regrant without purge cannot make an old row readable through this service because reads are disabled, but the source epoch invariant itself is not proven. Resolve/current replay distinctions cannot be observed because capture exposes no replay result. Deleted-project forget/purge is covered for a supplied exact namespace; unavailable project identity still requires the owner-fenced operator erase route. In-memory repository rollback behavior remains covered. Lost ACK, changed-intent conflict, native concurrent mutation, expiration/restore quarantine and physical deletion remain blocked. No runtime producer, API/model tool, context append, export, provider call, external send or MEM-4 behavior was added. No destructive migration or historical lock/corpus edit was made.

Rollback is to keep capture and selection disabled, preserve the migration as additive (do not down-migrate), and retain canonical workflow receipts, memory tombstones, owner fences and historical source locks. Payload cleanup uses the exact-namespace maintenance operation or existing owner-fenced operator erase; do not restore an old bucket as readable without issuer/lifecycle reconciliation.

This same-session remediation includes self-review and the verification above. No independent follow-up review is scheduled by this change; the remaining blocked gates are explicit.

# MEM-1 independent-review remediation evidence

Date: 2026-10-29 (America/Los_Angeles). Review target: baseline
`2df112bf04b8d817c2cfee9c807786161d2fec4f`. The attached review's findings
were used as remediation requirements; its no-go remains the acceptance
disposition. This record covers local synthetic/offline remediation only.
Admission and selection remain default-off. No model provider, cloud service,
deployed database, or production identity system was exercised.

## Finding dispositions

| Finding | Disposition and evidence | Remaining gate |
| --- | --- | --- |
| F1 P1: source-fence mutations crossed acting-user boundaries | Migration 029 adds an acting-user key to source fences and reverse edges. Repository and PostgreSQL paths bind get/list/revoke/erase/retention to the request's exact owner, app, workspace and acting user. Synthetic coverage includes nullable and non-null actors, cross-actor revoke/erase denial, and preservation of legacy tombstones. | Production identity and deployed database acceptance remain open. Legacy tombstones without retained actor identity remain global anti-replay denies. |
| F2 P1: late permission revocation could reach packed context | Context permissions and expiry are checked after final token counts; chat rechecks the source snapshot at the provider dispatch boundary. Barrier tests revoke or expire selected sources during the final count and verify omission or fail-closed behavior. A separate dispatch test verifies that a revoked snapshot prevents provider invocation. | Native concurrent transaction behavior and live provider boundaries have not been exercised. |
| F3 P1: Task B benchmark could use data outside packed content | The old `mem1-paired-v1` 20-case fixture and digest are preserved and explicitly labeled a structural/stateful proxy. New `mem1-consumer-v1` passes only packed messages and narrow read/execute handles to a deterministic consumer; the companion fixture has 16 paired cases and content-tampering controls. | Synthetic parser results do not establish real-model utility; independent fixture review remains open. |
| F4 P2: permanent tombstones can exhaust quota | No unsafe compaction was added. The per-namespace cap remains 1,024 source fences, including tombstones. Under the follow-up's stated three-distinct-fence assumption, 341 complete admissions consume 1,023 entries; a 342nd admission needs three more and is denied atomically. | Promotion is blocked until a durable issuer watermark, namespace epoch, or equivalent replay-safe ledger supports safe compaction. See [capacity follow-up](mem-1-tombstone-capacity-follow-up.md). |
| F5 P2: production adapter, policy and native coverage are incomplete | Local PostgreSQL 17.11 with pgvector 0.8.7 exercised the forward migration and actor-scoped SQL. Default-off gates remain closed. | No trusted production issuer/lease, deployed app-grant policy, DynamoDB Local, cloud identity/deletion, provider, or production acceptance. Eight DynamoDB-dependent tests were skipped. |
| F6 P3: memory header gave historical content instruction-like semantics | Header now explicitly marks historical source-derived content as untrusted, time-scoped information that does not establish current facts or authorize actions. Existing context-fit behavior is covered by regression tests. | None identified within the bounded local remediation; downstream model behavior remains unverified. |

## Evaluation identities and results

The original `mem1-paired-v1` fixture remains byte-identical at SHA-256
`587e87f11422719e8ad2f512ede7020c0bae937cb555b1035cd8eb386866756e`; its
semantic digest and replay remain
`7787f8be9434f078fd257af4a35045e5e3ac0cde39e9d2af34118117edd26d92`.
MEM-0 v2 fixture and semantic digest remain
`592a0e3799aeafc32ebf7cba0c7e162ff0af98d0049af2cf683de653e5fc02e1` and
`f961fd6335397f3efb6ccacc8f6ac9b4a357d949a1671426399014c6dc470f28`.
The planner's v16 lock remains historical; active non-promoting v17 only rebinds
the changed source identity, with source digest
`aa06f7e78fe85944c3dad85d6167d91f2266987b4773276af96ff76c677b2ce0`.

The new `mem1-consumer-v1` fixture SHA-256 is
`ff94f67f8889f13887128003d21e5f1b89078e806c12a1d148c4ac7d1d3470664`.
Its consumer source-tree identity SHA-256 is
`ccdc580857e761e483e0cd9d7455b9cbfb538748a997c64444d5ecc00a4c5a4e`; its
semantic digest and independent replay are
`865a871cb81ebadb4dc7584e48aed2391a5a5409e7920f12d313106c7e61099b`.
It completed 16/16 cases for knowledge and eligible history, 0/16 for no
memory, with 16 paired knowledge wins versus no memory, no regressions, 16 ties
versus history, and zero invariant violations. Revoked, stale, wrong-actor,
missing-grant, forged, expired, unconfirmed, dropped, redacted and misleading
content abstained; swapped and reversed visible content changed the outcome;
duplicate content did not duplicate effects. These are deterministic synthetic
consumer results, not real-model lift.

## Verification

All commands below used the repository's existing local virtual environment.
The full offline suite completed serially at baseline plus this dirty patch:

| Command | Result |
| --- | --- |
| `PATH="$PWD/backend/.venv/bin:$PATH" make backend-test-offline` | **1,923 passed, 99 deselected**, 4 warnings, 186.28 s. |
| `backend/.venv/bin/python -m pytest backend/tests/test_memory_knowledge.py backend/tests/test_context_builder.py backend/tests/test_memory_knowledge_consumer.py backend/tests/test_chat_stream_lifecycle.py::test_context_permission_is_rechecked_at_the_actual_model_send_boundary -q` | **80 passed**, 2 warnings. |
| `backend/.venv/bin/python -m pytest backend/tests/test_memory_knowledge.py backend/tests/test_memory_knowledge_evaluation.py -q` | **77 passed**, 2 warnings. |
| `backend/.venv/bin/python -m pytest backend/tests/test_mem0_task_baseline.py backend/tests/test_memory*.py backend/tests/test_postgres*.py backend/tests/test_planning_experiment.py backend/tests/test_artifacts.py -q` | **491 passed**, 3 warnings. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make memory-knowledge-eval memory-task-eval memory-eval memory-lifecycle-eval memory-optimization-eval planning-eval` | All six evaluations exited successfully; MEM-0 and the original MEM-1 fixture/digests remained unchanged; planning remained non-promoting. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make memory-knowledge-causal-eval` | Passed with the `mem1-consumer-v1` identities and results recorded above. |
| `make backend-lint` | Passed: `All checks passed!`. |
| `PERSISTENCE_TEST_POSTGRES_DSN='postgresql://jasonkli@127.0.0.1:55491/postgres' backend/.venv/bin/python -m pytest backend/tests/persistence/test_verified_knowledge_postgres.py backend/tests/persistence/test_local_persistence.py backend/tests/persistence/test_memory_lifecycle_projection.py backend/tests/persistence/test_account_export.py -q` | **32 passed, 8 skipped**, 2 warnings. Local synthetic PostgreSQL 17.11 + pgvector 0.8.7; skips are DynamoDB-dependent. |
| `git diff --check` | Passed. |

The PostgreSQL migration test applies migrations 027, 028, then 029, seeds a
synthetic 028-shaped legacy row, verifies the row survives, checks actor-key
backfill and migration idempotence, and exercises actor A/B authorization and
retention behavior. The tests use a local synthetic database and do not prove
cloud persistence, production IAM, physical deletion beyond tested adapter
paths, or provider behavior.

An earlier full offline attempt recorded in the implementation report failed
one provider-matrix test; this clean full run is recorded as a rerun, not proof
that the earlier timing issue's root cause was fixed. No check here authorizes
promotion. Independent review, production policy/identity, safe tombstone
compaction, deployed source deletion, and real-model utility remain unresolved.

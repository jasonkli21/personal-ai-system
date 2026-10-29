# MEM-0 independent-review remediation

Date: 2026-10-29. Implementation/evaluation base revision:
`987bba5f6479791b54ac626d9959b1b39e23fbb3`; all checks below ran with the
remediation source present in a dirty tree. The independent report is preserved
unchanged at [`mem-0-independent-review.md`](mem-0-independent-review.md). This
document records the implementation response; it is not a new independent review
or acceptance sign-off.

## Findings and dispositions

| Finding | Disposition | Evidence and boundary |
| --- | --- | --- |
| F1 — P1: action order, duplication, and forged result/verification claims were not enforced | **Addressed in the finite harness.** Action-specific payload contracts and a post-run validator bind order, cardinality, revision checks, evidence, results and workflow receipts. Trace invariant failures mark execution failed; the CLI exits nonzero. | `test_workflow_action_trace_mutations_fail_grade_and_run_status`, `test_forged_non_workflow_verification_fields_fail_grade_and_runner`, and `test_trace_invariant_failure_is_written_as_failed_and_cli_exits_nonzero`. Synthetic only; no provider/tool dispatch. |
| F2 — P2: reconciliation could treat a generic current fact as proof of the original effect | **Addressed in v2 evaluation data and harness.** The request and canonical observation must match effect key, run, command, revision and complete scope. Missing/wrong identity stays unknown and abstains. An idempotent synthetic ledger proves one effect per key in the fake. | `test_reconciliation_policy_depends_on_canonical_observation`, `test_keyed_reconciliation_confirms_without_replaying_and_ledger_is_idempotent`. This does not prove native transaction, idempotency, recovery or receipt-issuer behavior. |
| F3 — P2: derived diagnostic support checked permission edges but not the derived fact | **Addressed with a narrow declared recipe.** `exact_all_v1` requires nonempty supports whose exact structured claims match the derived subject/value. Missing or mismatched semantics become unavailable to the answer policy. Production schema 2 and `support-v1` were not changed. | `test_derived_diagnostic_claim_requires_exact_nonempty_support`, alongside `test_scope_revoke_forget_and_derived_support`. The recipe is not semantic entailment for generated summaries. |
| F4 — P2: several negative controls confounded the guard they named | **Addressed in the new v2 corpus and counterfactual checks; v1 remains frozen.** WF-04 matches revisions so workspace is the deciding guard; TF-03 is observed by task time but effective in the future; AU-02 is app-only and a workspace-only twin is separately tested; CO-04 has two independent failure receipts plus a one-failure control; IR-03 traverses evidence with useful and adversarial content. Positive twins and single-guard mutation probes are included. | `test_scope_guards_have_single_dimension_negative_and_positive_twins`, `test_effective_time_guard_has_observed_future_negative_and_positive_twins`, `test_repeated_failure_case_and_one_failure_control_are_distinct`, and `test_useful_answer_and_untrusted_instruction_are_mixed_in_history`. The supplemental counterfactuals do not inflate the 30-case denominator. |

No production `Memory` or `DerivedMemory` schema, migration, support policy,
permission policy, or disabled default changed. MEM-1, cloud/provider operations,
credentials and deployments were out of scope. No Phase 36 acceptance rows were
updated from these offline checks.

## Frozen identities and v2 replay

- The v1 fixture is unchanged: SHA256
  `043edaae3461286b49bcb4fda4f73bdc5059e528361bad3fa670a3b1c4e58b18`.
- Active v2 fixture SHA256:
  `592a0e3799aeafc32ebf7cba0c7e162ff0af98d0049af2cf683de653e5fc02e1`.
- `make memory-task-eval` passed with two matching semantic runs. Manifest result
  digest: `f961fd6335397f3efb6ccacc8f6ac9b4a357d949a1671426399014c6dc470f28`;
  source SHA256 `23fcf288ff995adc98d728bedd5dd1c8c67c96aab65f1ea49c2cd621b8084f2f`.
  Manifest status is `passed`, evidence class `offline`, tested revision is the
  base above, and `source_tree_dirty` is true.
- Results: none 19/30; fixed 22/22 with 8 unsupported; full eligible history
  29/29 with 1 truncated; gold-authorized 30/30. Fixed versus none has 3 wins,
  19 ties, and 0 regressions on 22 common evaluable cases. These are finite
  `synthetic_scripted_task_proxy` observations, not model-quality estimates.
  All 120 arm/case executions passed and none recorded an invariant violation.
- Active planning lock is v16 with source identity
  `fc73dc999e509cc493a511987dcbfb8cbd30cb6d1e0c1c0c86c96a06c1288ac7`.
  Historical v15 remains unchanged. V16 preserves its predecessor's
  configuration, corpus, fixture/runtime identities, non-promotion decision,
  and strict `current-or-direct-child-with-identical-source-identity` guard.
  `make planning-eval` passed; no coverage is promoted.

## Checks run

All Makefile commands used
`PATH="$PWD/backend/.venv/bin:$PATH"` from the repository root.

| Command | Result |
| --- | --- |
| `pytest backend/tests/test_mem0_task_baseline.py backend/tests/test_memory*.py -q` | **281 passed** (3 warnings), 16.18s on the final attempt. An earlier attempt exposed one test assertion in the new malformed-payload regression and one timeout in an existing provider-adapter test; the assertion was corrected, and the exact command then passed. |
| `pytest backend/tests/test_mem0_task_baseline.py backend/tests/test_planning_experiment.py -q` | **135 passed** (3 warnings), 9.21s after regenerating the v16 source identity. |
| `make memory-task-eval` | **passed**; v2 manifest and replay identities above. |
| `make memory-eval memory-lifecycle-eval memory-optimization-eval planning-eval` | **passed**; all four existing offline evaluation targets exited 0. Planning reported non-promotion. |
| `make backend-lint` | **passed**; Ruff: “All checks passed!” |
| `make backend-test-offline` | **failed**: 1,833 passed, 3 failed, 90 deselected (1836 selected; 363.26s). Failures: `test_provider_task_evaluation_and_validator_use_production_routing_factory` (70 synthetic vs 80 expected), `test_matrix_uses_generic_profiles_task_contract_and_p21_p19_seams` (71 vs 80), and `test_identical_run_resumes_without_repeating_a_settled_send` (3 failed cases vs 1). |
| Isolated retry of those 3 failed tests together | **3 passed**, 72.33s. This does not convert the full offline run to a pass. |
| `git diff --check` | **passed** after documentation and source review. |

The full-suite failures are in existing provider-matrix code/tests, outside the
MEM-0 diff. Their isolated retry passed, but the failures recurred in the full
run after the independent reviewer had seen a different provider-matrix case
fail under the same full-suite target. Deadline or load sensitivity is
plausible, not demonstrated. The full offline suite is therefore a remaining
verification gap; no timeout was weakened and no test was skipped to obtain a
green result.

## Remaining evidence gaps

Fresh independent re-verification of F1–F4 remains outstanding. The full offline
suite must be investigated until a clean run is obtained or a root cause is
established. Fakes do not establish model behavior, native Postgres/Dynamo
resources, provider quota or latency, deployed identity/grants, cloud behavior,
physical deletion, transaction/idempotency or recovery semantics. The planner
freeze promotes no coverage. These results do not authorize MEM-1 implementation
or production enablement.

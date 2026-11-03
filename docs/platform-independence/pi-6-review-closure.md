# PI-6 review closure — 2026-11-02

**Disposition:** `remediation_complete_no_further_review_required`.

The user directed that this scoped review be completed without a review
handoff and marked as not needing further review. This document records the
local remediation and final verification. No fresh independent-review prompt
is being issued. It does not claim an independent verdict or expand the scope
of the synthetic evidence.

## R01–R11 dispositions

| Finding | Disposition | Evidence |
| --- | --- | --- |
| R01 factual/provenance grading | Fixed; facts and source evidence must be positively present and task-specific. | `test_score_rejects_unknown_or_missing_source_evidence`, `test_source_dependency_is_required_for_selected_and_cited_content`, `test_answer_digest_is_checked_against_frozen_expected_value` |
| R02 self-reported effects | Fixed; the isolated observer counts effects independently and excess or forbidden effects veto. | `test_observer_detects_duplicate_send_without_driver_self_attestation`, `test_frozen_forbidden_effects_veto_even_when_driver_reports_success`, `test_observer_vetoes_duplicate_memory_mutation_and_requires_expected_attempt` |
| R03 incomplete denominators | Fixed; expected arms come from the frozen corpus, and missing/duplicate/unknown/unmeasured/incomplete rows invalidate coverage. | `test_aggregate_requires_all_arms_and_reports_quality_separately`, `test_aggregate_rejects_duplicate_unmeasured_and_unknown_rows` |
| R04 resource limits | Fixed; 5-second per-operation deadline, 300-second suite deadline, source/input/output caps, bounded worker capture and termination. | `test_budget_enforcement_and_source_bytes_are_hard_limits`, `test_worker_deadline_kills_blocking_driver_without_orphan_child`, `test_suite_deadline_marks_remaining_required_arms_unmeasured` |
| R05 exposed v1 holdout | Addressed by preserving v1 as development-exposed history and freezing a new v2 protocol/corpus before its final measurement. V2 remains agent-authored, synthetic and non-blind. | `test_v1_history_is_byte_preserved_and_v2_has_new_agent_authored_cases`; first and final v2 result hashes in the verification ledger |
| R06 memory comparison | Fixed; both arms attempt the same protected read under revocation; positive recall proves content and current dependency. | `test_memory_revocation_executes_same_denied_read_on_both_arms`, `test_memory_positive_recall_checks_content_fingerprint_not_only_id` |
| R07 runtime/package identity | Fixed; runtime identity uses installed package versions and hashes, without Git/source-root dependence; installed full evaluator is exercised. | `test_runtime_identity_uses_packages_without_git_or_checkout_paths`; `make pi6-check` installed-wheel phases |
| R08 native-fence claim | Fixed; the canonical runner verifies native denial in each measured child. A forgeable Python sentinel is not accepted as a capability. | `test_native_launcher_has_no_python_flag_capability`; native IPv4/IPv6 denial in `make pi6-check` |
| R09 threaded logging | Fixed within the bounded child boundary; worker logs and stdout are capped and cannot escape to the parent or later measurements. | `test_child_logs_are_bounded_and_never_escape_to_parent`, `test_worker_exception_text_and_stdout_are_not_retained` |
| R10 percentile | Fixed to nearest-rank p95. | `test_nearest_rank_p95_uses_ceiling_index` |
| R11 planning revision guard | Fixed additively with v27. V10–v26 bytes and semantics remain unchanged; v27 binds the final source digest and preserves non-promotion. | `test_v26_pi6_additive_source_binding_preserves_v25_and_non_promotion`, `test_v27_pi6_review_rebind_preserves_v26_and_non_promotion` |

## Final local evidence

The final `make pi6-check` passed 54 focused tests and measured 68/68 expected
source rows under the native loopback-only fence. The installed core-only phase
reported 52 optional-host arms as ineligible and incomplete, so it did not pass
coverage. The separately installed core, Reading Logbook client and host full
evaluator passed with 68/68 rows and complete coverage. Both full measurements
had zero safety vetoes. The source report is
[pi-6-benchmark-report-v2.json](pi-6-benchmark-report-v2.json); the first v2
run with 13 evidence-incomplete arms is preserved at
[pi-6-first-v2-measurement-2026-11-02.json](pi-6-first-v2-measurement-2026-11-02.json).

Other final checks include `make backend-lint`; `make pi5-check` (147 native
tests and 34 signed HTTP tests); `make pi3-check` (788 tests); `make pi4-check`
(898 tests); `make pi2-check`; `make platform-independence-check`; the focused
60-test planning suite; `make planning-eval`, `make retrieval-eval`,
`make research-eval`, `make memory-task-eval`, `make memory-control-eval` and
`make memory-knowledge-causal-eval`; and the full native loopback-fenced
`make backend-test-offline` (2,385 passed, 119 deselected, four warnings).
Detailed results, skipped gates, runtime, hashes and preserved iterations are
in [pi-6-verification.json](pi-6-verification.json).

## Remaining evidence boundary

The local evaluator is complete for this synthetic scripted scope and remains
`not_promoted`. V2 is not blind or independently authored; no real-model utility,
live cost, deployed identity, distributed source/send authority, cloud recovery
or physical deletion is established. PI-5 remains `blocked_unverified`, the
offline sequencing exception remains `conditional_go`, and production
promotion remains `no_go`. P6-02/P6-29 and distributed/live P6-15/P6-32
obligations remain deferred.

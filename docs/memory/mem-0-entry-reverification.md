# MEM-0 entry verification attempt for MEM-1

Date: 2026-10-29 (America/Los_Angeles). Inspected HEAD:
`293a5910827d9a1f70e1342ee3b98f24ab615e4d`. The initial tracked tree was clean;
eight pre-existing untracked planning/review documents were preserved. The
implementation prompt and companion plan required independent MEM-0 v2
acceptance and disposition of the full-suite failure before MEM-1 work.

No new independent acceptance record was present. The
[original review](../personal-ai-chapter-2/memory/mem-0-independent-review.md)
requires independent re-verification, and the
[remediation](../personal-ai-chapter-2/memory/mem-0-review-remediation.md)
explicitly leaves it open. The user then instructed “continue without
acceptance,” followed by an attempt to resolve MEM-0 first and continuation
with MEM-1 if still incomplete. This authorizes sequencing only. This file is
implementation-session QA, not an independent verdict or a change to historical
MEM-0 evidence.

## Checks and finding disposition

All commands ran from the repository root with
`PATH="$PWD/backend/.venv/bin:$PATH"`. No live provider call was made.

| Check | Observed result |
| --- | --- |
| Initial serial `make backend-test-offline` | **1,836 passed, 90 deselected**, 4 warnings, 176.93 s; `/tmp/mem1-entry-offline.log`. Existing runtime code was unchanged when collected; only new unimported MEM-1 modules/docs were being prepared. |
| Initial `python -m pytest backend/tests/test_mem0_task_baseline.py backend/tests/test_memory*.py -q` | **281 passed**, 3 warnings, 15.08 s; `/tmp/mem1-entry-focused.log`. This ran before MEM-1 was connected to existing runtime modules. |
| Final expanded MEM-0/memory/Postgres/planner/artifact regressions | **484 passed**, 3 warnings, 14.40 s; exact command in the [MEM-1 report](mem-1-implementation-report.md). |
| Final `make memory-task-eval` | **passed**; active identity remains `mem0-v2`; two semantic replays match the unchanged v2 result digest below. |
| Existing memory, lifecycle, optimization and planner evaluations | **passed** on final source; planner decision remains non-promotion. |
| Final MEM-1 serial `PYTEST_ADDOPTS='--durations=5' make backend-test-offline` | **1,911 passed, 99 deselected**, 4 warnings, 207.56 s; `/tmp/mem1-offline-stable.log`. An earlier MEM-1 full run failed in the existing provider matrix; see the report for both attempts and clock triage. |

The initial full-suite clean run supplies the clean rerun alternative requested
by the entry gate. It does **not** establish a root cause for earlier provider
matrix failures or promise the timing issue is fixed. An expanded intermediate
regression run later observed the existing mocked disclosure test timing out;
its timeout was not changed. The complete expanded command subsequently passed.
Final full-suite results and every remaining limitation are in the MEM-1 report.

| Prior finding | This session's inspected/executed control | Remaining acceptance |
| --- | --- | --- |
| F1: action causality and forged verification | Reversed/check-after-use/duplicate/wrong-revision/forged-receipt mutations are rejected at grader and runner levels; malformed non-workflow verification and CLI invariant-failure tests pass. | Separate independent sign-off remains open. |
| F2: original-key reconciliation | Correct-key uncertain/success observations, wrong-key/missing/wrong-owner controls and the stateful one-effect ledger tests pass. | Native external-effect authority is not inferred from the fake. |
| F3: source eligibility versus support truth | Empty/missing/mismatched exact support is rejected; unverified diagnostic-derived facts are excluded. Production `support-v1` is unchanged. | No generic semantic entailment claim. |
| F4: confounded safety controls | App-only/workspace-only and effective-time positive twins, guard-removal probes, repeated-failure controls and mixed useful/adversarial history tests pass. | Independent review of case design remains separate. |

The executed tests are the named remediation regressions in
`backend/tests/test_mem0_task_baseline.py`, not newly invented acceptance scores.
No baseline result was improved by changing expected answers, removing negative
cases, relaxing timeouts or skipping required offline tests.

## Preserved identities

- V1 fixture SHA256:
  `043edaae3461286b49bcb4fda4f73bdc5059e528361bad3fa670a3b1c4e58b18`.
- V2 fixture SHA256:
  `592a0e3799aeafc32ebf7cba0c7e162ff0af98d0049af2cf683de653e5fc02e1`.
- Final v2 semantic result digest, unchanged from remediation:
  `f961fd6335397f3efb6ccacc8f6ac9b4a357d949a1671426399014c6dc470f28`.
- Final MEM-0 backend source SHA256:
  `3fbc2f227d7e2d9e64c0a97669ce8c08705725563bfc01eb28b559f16f4301a3`.

The first in-session CLI replay correctly failed `inputs_changed_during_evaluation`
because source edits overlapped its two runs. That attempt is not a pass. A
subsequent diagnostic replay and the final supported command completed with
stable inputs and the preserved result identity. Native/cloud/model evidence is
not added to MEM-0 by this implementation-session replay. Independent acceptance
of MEM-0 remains unclaimed; the user's explicit sequencing override was used.

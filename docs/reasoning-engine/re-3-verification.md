# Grounded reasoning verification and independent review

2026-11-05, America/Los_Angeles. Author verification on macOS 27.0.1,
arm64, Python 3.11.15. Base commit
`4e28b433ea1a0b129701d6da9cf6560f1ea80f9a`, base tree
`f3220eba98e07f80ca00df1e905dcb7976fb142f`. Review the single commit
containing this report and its parent diff. Use
`git show --format=fuller --stat HEAD` and `git rev-parse HEAD 'HEAD^{tree}'`
from the exact review checkout. The pre-existing PRD move and untracked
planning documents were kept outside the change.

## Sealed E1 observations

The runner prints all 180 redacted rows and the summary. The 60 paired cases
include 30 held out and 30 eligible, with 15 eligible holdouts. They cover
simple lookup, multi-source joins, missing and stale facts, contradiction,
source instructions, fabricated and misbound citations, unsupported facts,
pre/post-send revocation, and wrong scope. The one-shot arm uses the exact
candidate plan and initial query and suppresses the optional query. The
The `direct` arm is a **source-free abstention safety negative control**: it
makes one canonical fake call per case without authorized evidence and
abstains. It is not a matched-task estimate of direct versus grounded utility.
The `one_shot` and `grounded` arms use the same grounded task and permitted
resource envelope. The independent scorer receives the separate sealed gold
after candidate execution. Cases are authored variants of a narrow fixture
grammar. The split tests replay and limited transfer within that grammar.

| Measurement | Source-free abstention control | One-shot grounded | Grounded |
| --- | ---: | ---: | ---: |
| Exact completions, eligible | 0/30 | 18/30 | 30/30 |
| Exact completions, eligible holdout | 0/15 | 9/15 | 15/15 |
| Complete / partial / unavailable / denied, all rows | 0 / 0 / 60 / 0 | 18 / 6 / 36 / 0 | 30 / 0 / 30 / 0 |
| Retrieval / fake generation / verifier attempts | 0 / 60 / 60 | 60 / 33 / 30 | 84 / 39 / 36 |
| Reserved operation rows / unknown attempts | 120 / 0 | 123 / 3 | 159 / 3 |
| Observed quote bytes / conservative retrieval token bound | 0 / 0 | 3,111 / 56,358 | 3,627 / 67,014 |
| Exact fake input / output bytes | 14,580 / 780 | 95,148 / 5,031 | 119,400 / 6,339 |
| Reserved fake input / output bytes | 61,440 / 7,680 | 540,672 / 16,896 | 638,976 / 19,968 |
| Count calls / exact bytes counted | 420 / 78,540 | 399 / 571,128 | 483 / 732,558 |
| Reserved count input bytes | 430,080 | 6,537,216 | 7,913,472 |
| Elapsed milliseconds, first / second process | 1,501 / 1,473 | 3,883 / 3,792 | 4,709 / 4,579 |

The one-shot comparison records 18/30 exact eligible completions and 9/15
eligible holdout completions; grounded records 30/30 and 15/15. This is a
scripted within-fixture-grammar follow-up ablation, not a generalized utility
estimate. It consumed 60 local reads in one-shot and 84 in grounded, despite
sharing the same permitted envelope. The source-free arm's 0/30 is an
abstention safety result and is excluded from utility comparisons. Simple and
objectively sufficient cohorts incurred zero extra queries. The observed veto
count is zero. The verdict is `OFFLINE_SIGNAL_ONLY`. The unknown attempts are
revoked local reads that lost their final observation. Reported quote and
token-bound totals cover received and retained observations. All fake
generation byte receipts were observed. The fake counts serialized bytes
and the retrieval token bound uses UTF-8 bytes conservatively. Real
provider tokens, reservations, settlement and cost remain unknown.

Two fresh runs returned semantic SHA-256
`29d2f779ea9ee127e134a2c4fd4555a8772f2e3ca77d9fdcf86f71bbf27b9e99`.
The independent source pin is seal SHA-256
`f9653be85d2f642faa21025bd31efd210aaeca25d892b47f24d165e26c83724f`.
Cases SHA-256 is
`a378e43c6d2b5afb0ed5bc094e39559cfc5204dcefb0f96298d6e5ff752caace`
and oracle SHA-256 is
`363fc902d9a83028591bae56eb700ff5ea7c544c35dec7e8a74ad939e752196d`.
The [seal](../../backend/src/personal_ai/evaluation/reasoning_grounded/seal.json)
covers the manifest, corpus, oracle, fixture and runner. The provisional
observer flagged the numeric workflow lease-claim counter as candidate
text. The observer was corrected to recognize the structured response array,
and the fixture authority signature was finalized before measurement.
Corpus, split, oracle and thresholds stayed fixed across that correction.
Synchronized fixture/seal tampering and both degenerate verifier controls
are exercised by the focused target.

## Commands and disposition

Use the provisioned backend environment. For Make commands that use
`python`, first prepend `"$PWD/backend/.venv/bin"` to `PATH` at repo root.

| Command | Result |
| --- | --- |
| `make reasoning-grounded-check` | 71 passed, exit 0. Includes strict admission, source and citation attacks, budget, claim fencing, lost acknowledgements, cancellation, receipt redaction, and benchmark controls. |
| `make reasoning-grounded-eval` twice | Exit 0 in both fresh processes. Semantic hashes matched. |
| `make reasoning-check` | 122 passed, exit 0. |
| `make reasoning-eval` | Exit 0, 64/64 rows valid. Semantic SHA-256 `9c1335f421c00b36f863f7c55c2321d92a02d68358f5887c6bcf8cd8c8fb2ae2`. |
| `make reasoning-orchestrator-check` | 57 passed, exit 0. Includes v1 receipts with and without verifier extensions. |
| `make reasoning-orchestrator-eval` | Exit 0, 60 pairs. Semantic SHA-256 `660e5130374a633d9ac5001293393d1950d5b99b6f694ec8e42840f7bcbc0db5`. |
| `make workflow-check` | 70 passed, exit 0. |
| `make backend-lint`, `make naming-policy-check`, `git diff --check` | Exit 0. |
| Focused retrieval, context, auth, chat, usage, inference and disclosure command below | 554 passed, 34 deselected, exit 0. |
| Bounded backend command below | 1,964 passed, 310 deselected, eight setup errors, exit 1. Stopped at the inherited longitudinal source-lock mismatch. The same `study_source_changed_requires_new_generation` setup error was reproduced from the pinned baseline in `test_memory_research_contracts.py -x`. The sealed inventory at HEAD already differed in three tracked dependencies and included an extra finite reasoning contract. |
| `make workflow-postgres-check` | 54 passed, two failed, Make exit 2. The existing finite profile's `test_cancellation_keeps_classification_and_prevents_follow_on_sends[queued]` and `[reserved]` assert one physical send and observed zero. Both failed with the same assertion on the pinned baseline. |
| `cd backend && python -m pytest -q tests/persistence/test_reasoning_grounded_postgres.py` | Three passed, exit 0. Native JSON row and receipt replay, competing claims, and a spawned process lost after committed retrieval dispatch. |

The Python network fence recorded zero attempted network operations for the
offline runs above. Native runs used PostgreSQL 17.11 and pgvector 0.8.7
with normal migrations and an isolated private Unix socket. The sandbox
first denied PostgreSQL shared memory. The approved isolated fixture could
start, and using a URL DSN resolved the repository validator's rejection of
the first keyword-form DSN. The test fixture was shut down after verification.

```sh
LITELLM_LOCAL_MODEL_COST_MAP=True backend/.venv/bin/python -B backend/scripts/offline_test_runner.py \
  -q -m 'not loopback_http' \
  backend/tests/test_retrieval_{context,http,integrations,query_planning}.py \
  backend/tests/test_context{,_authorization,_builder,_planner,_provider,_routes,_runtime_composition,_sources,_traces}.py \
  backend/tests/test_auth.py backend/tests/test_inference_execution.py backend/tests/test_provider_usage.py \
  backend/tests/test_chat*.py backend/tests/test_memory_disclosure_authorization.py

LITELLM_LOCAL_MODEL_COST_MAP=True \
  PYTHONPATH=sdk/python/src:examples/project-checklist/client/src:examples/project-checklist/host/src \
  backend/.venv/bin/python -B backend/scripts/offline_test_runner.py -q --maxfail=8 \
  -m 'not persistence_integration and not cloud_smoke and not loopback_http' backend/tests \
  --ignore=backend/tests/test_gemini_manual.py --ignore=backend/tests/test_context_manual.py
```

## Independent review handoff

Review the [request and gap policy](../../backend/src/personal_ai/reasoning/grounded.py),
[receipt projection](../../backend/src/personal_ai/reasoning/grounded_receipts.py),
[trusted source adapter](../../backend/src/personal_ai/workflow/grounded.py),
[template execution](../../backend/src/personal_ai/workflow/grounded_execution.py)
and [row transitions](../../backend/src/personal_ai/persistence/postgres/workflows.py)
together. Use the [host contract](re-3-implementation.md) for startup and
disablement, and the [gate table](re-3-blockers.md) for limits of the claims.

1. Change one source, quote span, rights epoch, app capability, workspace
   or fixture callback after admission. Probe after retrieval, before pack,
   between dispatch commit and fake send, after send and after terminal
   commit. Check that no stale claim crosses the live return boundary.
2. Race cancel, deadline and stale fence against initial/focused retrieval,
   synthesis and pure verification. Compare the exact attempt UUID and
   child UUID before and after process loss. Restore a copy after dispatch
   and expire its lease. A replacement claim should expose only uncertainty.
   If both row history and source authority are rolled back, treat
   original-key protection as unproven.
3. Mutate an excerpt or drop it from canonical context, substitute a
   wrong-slot citation or fill a clipped source with conflicting records.
   Inspect both the actual fake wire and the verifier's typed results.
4. Compare terminal SQL rows, progress/event tails, replay and debug traces.
   Search for quote, prompt, candidate or query payloads. Verify that the
   terminal evidence adapter denies grounded rows to memory.
5. Run the sealed evaluation twice and run the negative controls. Confirm
   that all 180 rows count, including partial, withheld and unsupported
   results, and that no oracle values are handed to the fixture candidate.
   Reproduce the two inherited native assertions from the parent before
   drawing conclusions about the combined target.

Independent acceptance and live, deployment, anti-rollback and real-model
evidence remain open. This report records author observations at the local
fixture topology.

## Independent review correction

The independent review found that per-item provenance checks did not prove
that the local result set was complete. A same-shaped reply could omit one
conflicting authorized item and forge completion while retaining valid
provenance and byte counters. The remediation replays the deterministic local
search, with the same query and caps, against the pinned authorized snapshot
and requires the full result envelope to match before grounded execution can
continue. This read-only proof adds no retrieval tool call. Full regression
and remediation evidence is recorded in
[the review remediation receipt](re-3-review-remediation.md).

# HXE-2 scoped development verification

2026-11-03. Base commit `35c26de9b75d9eab1ebef2d7f4aad30b72ae5d11`,
tree `d31ba4a5441f7fba7b0e79d1ae5db134e9a612f5`. Two pre-existing untracked
planning files were kept outside the patch. The commit containing this receipt
identifies the candidate. Verification used macOS 27.0.1 arm64, Python 3.11.15,
pytest 8.4.2 and uv 0.11.13.

## Design decisions

- Use llama.cpp's native Unix socket and integer-token completion contract.
  This lets the existing context budget, authorization and reservation paths
  operate over exact prepared input. The tested application seam is normal
  chat with a bounded buffered completion. The socket and the model server's
  runtime identity are explicit operator configuration.
- Keep registry profiles, quota, durable attempts and settlement in canonical
  accounting. The migration adds separate local cost and execution identities.
  The local rate ceiling is 60 operations per minute and the existing
  request budgets continue to apply.
- Keep observations with usage ownership. Trace capture is bounded, opt-in and
  ephemeral. The evaluator owns the additive versioned corpus and the export
  CLI. The [operator guide](local-inference.md) covers the transport trust
  boundary, limits, and rollback.

## Original candidate checks

The following receipts describe the candidate before the independent-review
remediation. The final results below supersede source-lock failures where they
were repaired.

## Checks

| Command or reproduction | Result |
| --- | --- |
| `make backend-lint`, `make naming-policy-check`, `git diff --check`, guide link check | Passed. |
| `UV_CACHE_DIR=/private/tmp/pas-build-uv-cache make backend-build` | Backend source distribution and wheel built. |
| `make real-task-eval REAL_TASK_FLAGS='--trace <new-basename>.jsonl'` | Passed. 33 fake completions, three branch denials, zero forbidden markers, and no positive literal-rubric passes. Selected and eligible arms included the expected source, and only eligible included the stale distractor. In this run median elapsed time was 2 ms and maximum 41 ms, including preparation. |
| `backend/.venv/bin/python backend/scripts/provider_isolation_checks.py --only test_local_inference.py test_real_task_evaluation.py test_inference_execution.py test_retrieval_context.py` | 84 passed under native IPv4, IPv6 and Unix socket denial, with zero forbidden Python network attempts. The transport tests inject synthetic responses and exercise redirects, identity changes, malformed and oversized payloads, quota denial, cancellation, source revocation after reservation, and uncertain ledger settlement. |
| `make mcp-adapter-check` | 44 passed, zero blocked network attempts. |
| `make provider-isolation-check` | Candidate sweep before the final settlement-canary addition: 832 passed and one failure for the frozen planning source digest. Native network denial passed and zero forbidden Python network attempts were recorded. |
| `make backend-test-offline` | Candidate sweep with backend venv, checkout SDK/reference/Checklist/Reading Logbook source paths and loopback fixtures: 2,448 passed, 27 failed, one skipped and 119 deselected. The 27 failures were 25 frozen PI-6 protocol checks, one frozen planning lock, and one restore fixture failure. |
| `UV_CACHE_DIR=/private/tmp/pas-build-uv-cache make offline-benchmark-check` | Built backend, reference and Reading Logbook artifacts. Frozen PI-6 checks reported 29 passed and 25 failed with `frozen_protocol_mismatch`. Native and same-process egress denial passed, with zero forbidden Python network attempts. The installed benchmark step did not run. |

On a clean archive of the base, the representative PI-6 corpus test and
planning source-lock test both passed. Both locks hash the current core source
tree, so the candidate changes cause a deliberate evidence mismatch. Their
source identities, manifests, corpora, scoring, thresholds and historical
receipts were preserved. The restore test
`test_stale_derived_restore_keeps_revocation_and_original_keys` reproduced
on the clean base with HTTP 422 `context_explicit_source_unavailable` using
the same loopback fixture and checkout client packages.

## Acceptance boundary

- **E1 synthetic plumbing exercised.** Fake model output supplies no task
  quality result. The experiment corpus uses synthetic history and a public
  held-out split. The retrieval and MCP checks exercise separate synthetic
  issuer and permission boundaries.
- **E2 real local inference remains unfulfilled.** This session had no
  `llama-server` or `ollama` on PATH and no verified, provisioned model/server
  with a native server fence and migrated disposable persistence. No model
  was downloaded or run. Model accuracy, source citation quality, time-to-first
  token, server CPU/RAM, cold-start and disk footprint have no measured values.
  The local runtime operator owns that evidence.
- **E3 hosted is `BLOCKED_UNVERIFIED`.** No hosted account or current
  operation-level zero-charge evidence was verified and no hosted call was made.
  No provider charge was observed in the synthetic checks. Account billing,
  production release, and independent review remain open.

## HXE-2 independent review remediation

Reviewed base and parent: `35c26de9b75d9eab1ebef2d7f4aad30b72ae5d11`.
The remediation preserves the two pre-existing untracked planning files and
does not include them in its commit. It adds source generation 5 and planning
baseline lock v31 as additive identities; v1/v2 PI-6 cases, scorers, thresholds,
and source generations 2–4 remain unchanged. Lock v31 binds the reviewed parent
and exact source digest. The final commit is its direct child, and the
post-commit `make planning-eval` check passed.

| Finding | Disposition |
| --- | --- |
| F1 source/planning locks | Fixed with source generation 5 and planning lock v31. Canonical source and installed full-consumer checks cover 68/68 rows with valid coverage, no safety veto, native loopback-only fence, and `not_promoted`. Planning evaluation passes under v31. |
| F2 tokenizer reservation | Fixed. The full serialized `/tokenize` request is capped at 4,096 bytes before dispatch. P19 reserves the 4,096-token ceiling plus exact `tokenizer_request_bytes`; malformed or over-context token arrays settle conservatively. Unicode/multi-message, oversized request, and oversized response cases are hermetic. |
| F3 manifest integrity | Fixed. Runtime loading checks the immutable SHA-256, closed manifest shape and allowed IDs/families/splits/arms/tools/sources/marker types before composition. Duplicate, unauthorized, malformed, or drifted copies fail closed. |
| F4 E1 semantics | Fixed. E1 output reports coverage, safety canaries, and fake natural-language quality separately. Completed fake rows produced zero positive literal-rubric passes; a fake E1 pass cannot claim model utility. Forced forbidden output, unauthorized completion, timeout/incomplete, and duplicate/missing rows fail the integrity gate. |
| F5 trace semantics | Fixed. Context observations are labeled `selected_budget`; exact count, P19 reservation, tokenizer request bytes, reported usage, and unknown settlement remain separate. Read-only retrieval grant success/revocation emits content-free source checks. |
| F6 trace export | Fixed. Export writes and fsyncs an owned private temporary file, then atomically publishes with no-replace hard-link semantics and cleans up on failure. Overwrite/symlink and mid-publish failure tests pass. |

### Final remediation checks

Environment: macOS 27.0.1 arm64, CPython 3.11.15, pytest 8.4.2. No
`llama-server`/`ollama`, verified model, native model-process egress fence, or
disposable migrated ledger was available. No model download, hosted send, or
private-data disclosure was attempted.

| Command | Result |
| --- | --- |
| Focused regression selection: local inference, task evaluation, retrieval context, inference execution, planning-lock preservation, and PI-6 tests excluding `loopback_http` | 133 passed, 11 deselected. |
| `make backend-lint` | Passed. |
| `make naming-policy-check` | Passed; 2 checker tests passed. |
| `make planning-eval` | Passed with planning lock v31; source identity `57f448e2ead4bc00453b2ed120f502aa02db6eebb0198cbb37cb350224ab5236` at final source verification. |
| `make provider-isolation-check` | 838 passed; native IPv4/IPv6/Unix denial passed; 0 forbidden Python network attempts. |
| `make real-task-eval` | Exit 0. 36 rows: 33 fake completions and 3 branch denials; coverage/safety passed, 0 forbidden markers, 0 positive completed-row rubric passes, `natural_language_rubric=not_applicable_fake`. |
| `make offline-benchmark-check` | Source suite 54 passed; source and installed full-consumer evaluations each covered 68/68 rows with no missing, duplicate, unknown, unmeasured, or incomplete rows. Native loopback-only fence passed; 0 forbidden Python network attempts; safety veto false; real-model utility unmeasured; promotion `not_promoted`. The installed core-only probe correctly reported optional consumer dependencies unavailable and was ineligible; the installed full-consumer phase passed. |
| Initial `make backend-test-offline` with checkout SDK/reference/Checklist/Reading Logbook paths | Broad run before the last two historical-lock assertion updates: 2,375 passed, 13 failed, 1 skipped, 119 deselected, 92 setup errors. The two planning assertion failures were updated to preserve v19/v30 as history and assert v31 as current. Most setup errors were local HTTP bind denials in this sandbox. A clean final broad rerun was not completed. |
| `git diff --check` | Passed before commit. |

E1 synthetic plumbing and safety checks pass; fake task quality remains
unmeasured, with zero positive literal-rubric passes. E2 is
`BLOCKED_UNAVAILABLE`; no real model identity, useful-task output, baseline,
hardware, or server-fence measurements exist. E3 is `BLOCKED_UNVERIFIED` and
no hosted call was made. E4/E5 are not claimed; production remains NO-GO.
Local `LOCAL_NO_CHARGE` means no provider charge under the operator-owned
endpoint contract; hardware and power costs are unknown. P19 timeout and
settlement uncertainty remains conservative. Rollback remains: disable local
selection/approval, drain sends, reconcile unresolved reservations, stop the
server and trace export, and retain canonical ledger/source-grant records.

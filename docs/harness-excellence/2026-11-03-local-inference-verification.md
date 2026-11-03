# HXE-2 scoped development verification

2026-11-03. Base commit `3e9c9581d3ed4de7a0f5897584c28f5adf8d7ea4`,
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

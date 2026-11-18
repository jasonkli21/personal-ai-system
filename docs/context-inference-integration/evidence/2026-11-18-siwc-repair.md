# SIWC independent review repair record

2026-11-18 · Synthetic E1 repair candidate. **Independent re-review pending.** Local live SIWC remains `BLOCKED_UNVERIFIED`; managed SIWC remains `BLOCKED_PENDING_APPROVAL`; production remains `NO_GO`.

## Scope and starting revision

This repair addresses S3-001 through S3-004 from `pas-phase-3-siwc-independent-review.md`, starting at reviewed `main` commit `be9dcee9b565d74199802c65c5437d2fd5846546`. The original `/workspace/personal-ai-system` checkout was clean at unrelated commit `c1500ce9be41a789131ef1fca323e9d97bdf11fe`; it was preserved. Work was performed in a separate worktree based on the reviewed `origin/main`.

No live OAuth, account registration, provider model discovery, Responses request, credit/payment check, external source, managed host, deployment, or user data was used. Frozen fixtures, evaluation identities, source locks, signing claims, and migrations were not regenerated or changed. The finalized companion Phase 3 plan and prompt were unavailable in the supplied materials; the review's crosswalk remains its own candidate evidence, not independent plan acceptance.

## Finding disposition

| Finding | Repair | Evidence and remaining boundary |
| --- | --- | --- |
| S3-001 | Only an explicit closed set of documented subscription/admission error codes yields `rejected`. Generic statuses such as 400, 403, 408, 409, 429, 500, and 503 yield `incomplete` with `bridge_transport_unknown`; diagnostics retain the bounded provider observation. The bridge therefore retains `send_started`, reconciles as unknown, and denies a re-signed replay. Documented usage-limit rejection settles as `rejected` and also denies replay. | Added table-driven transport and bridge tests. Transport-only cases passed; filesystem-backed bridge tests were blocked by the sandbox path constraint described below. No retries or fallback were added. |
| S3-002 | Preview now uses `_request_sources`'s trusted `source_free` result for its initial source snapshot and history-authorizer snapshots. | Added source-free preview regression for clean and inherited source-attributed history, plus inherited selected-memory denial. Not executable here because test credential state must be created outside any `.git` ancestor. |
| S3-003 | Catalog display-name UTF-8 failures are normalized to `bridge_catalog_invalid`; the loopback model endpoint returns a bounded error. | Added escaped lone-surrogate tests for `\ud800` and `\udfff`, and an ASGI response check. Direct catalog tests passed; ASGI test requires the protected store and was blocked by the same sandbox path constraint. Valid Unicode is still accepted by the existing catalog tests. |
| S3-004 | Safe account projection rechecks account labels against access, refresh, and ID tokens, the registered subject, and the issued client ID. Missing credentials cause a conservative generic label. | Added legacy/restored label, disconnected label, Unicode label, public payload, and no-projection-I/O cases. Filesystem-backed tests were blocked by the sandbox path constraint. |
| S3-005 | No remote receipt or provider-attestation service was added. Existing connected completion remains client-reported; the SIWC local route stays disabled. | Existing default composition and local-operator tests continue to assert no managed SIWC option, no execution listener, and no live provider factory. `service.finalize` in the synthetic local-turn test receives a trusted fixture completion; it is not evidence of externally verified browser-to-PAS terminal proof. E2 stays blocked pending an accepted receipt handoff. |
| S3-006 | No frozen source identity, evaluation, or historical lock was changed. | Current source-dependent gates remain non-green or blocked; see command record. Separate versioned source identity work requires its own review. |

## Validation record

Commands were run in Linux with Python 3.12.14 and dependencies resolved from the existing `backend/uv.lock` using `uv sync --locked --extra dev`. This differs from the review's supported Python 3.11 environment.

| Command | Result |
| --- | --- |
| `backend/.venv/bin/python backend/scripts/offline_test_runner.py -q backend/tests/test_chatgpt_bridge_transport.py::test_admission_and_usage_errors_are_normalized_without_body_or_billing_fallback backend/tests/test_chatgpt_bridge_transport.py::test_generic_rate_limit_is_not_recorded_as_plan_usage_limit backend/tests/test_chatgpt_bridge_transport.py::test_malformed_model_label_is_a_bounded_catalog_denial` | Exit 0; 14 passed; `OFFLINE_RUNNER_BLOCKED_NETWORK_ATTEMPTS=0`. |
| Focused eight-file command from the review handoff | Exit 1; 166 passed, 109 failed, 5 setup errors; `OFFLINE_RUNNER_BLOCKED_NETWORK_ATTEMPTS=0`. The filesystem-backed cases could not create test credential state because `/tmp` and `/workspace` have a `.git` sentinel in the sandbox; protected storage correctly rejects all descendants. This does not validate the full focused suite. |
| `backend/.venv/bin/python -m ruff check backend` | Exit 0. |
| `make naming-policy-check` | Exit 0; `NAMING_POLICY=PASS`, 5 checker tests passed. |
| `make source-contract-check` on the committed repair | Exit 2. Planning `source_identity_digest` is expected `e7f7cb4b24e981d6549444f5c5ca794154851b3b77e479d1c0d01ed9b9dc96e8`, current `90c0856a686593e88b845a99fefccc68fbabe5e8c7fdefb381a2d54306c1d3d6`; offline `core_runtime` is expected `a535e9f72ba6bee57b74af246517401985a5847cf1d554ba54336a1de12ff2e3`, current `0296d05803494248f0dd2f7344b52ebdb51a6cdaf1dd4628166adf8114b49672`. |
| Clean reviewed-base source-contract comparison | Exit 1 using `/tmp/pas-siwc-phase3-repair/backend/.venv/bin/python -I backend/scripts/source_contract_check.py --check` in a detached worktree at `be9dcee9b565d74199802c65c5437d2fd5846546`. The baseline already had planning identity drift (`48c42cc17485adc2a233ffa838a9c3bdc5540b7137e4175ec1b1115d6c72387b` current vs the same expected `e7f7...`), as well as drift in files untouched by this repair. Therefore S3-006 predates this repair. The repair adds drift only to the three intentionally edited bound files and the owning README; historical identities remain unchanged. |
| `make hermetic-capability-check` | Exit 2 at `backend/tests/test_reasoning_grounded.py::test_sealed_evaluation`; 16 offline-runner tests, 123 reasoning tests, 57 orchestrator tests, and 76 grounded tests passed in earlier substeps, with zero blocked Python network attempts. The failing sealed fixture reports internal failures under Python 3.12; it is unrelated to SIWC. |
| `make provider-isolation-check` | Not run. This sandbox did not provide verified native OS socket-isolation support. |
| `git diff --check` | Exit 0. |

The focused suite and native checks need a supported POSIX host where protected temporary storage can be created outside a repository and where Python 3.11 and native network isolation are available. No full-suite pass is claimed.

## Independent re-review prompt

Review the single repair commit whose exact SHA is provided with this record. Independently inspect its diff against `be9dcee9b565d74199802c65c5437d2fd5846546`. Reproduce S3-001 through S3-004's positive and adverse tests in the repository's supported Python 3.11 POSIX environment using synthetic fixtures only. Verify physical sends, receipt states, replay fences, source-free preview denial, malformed catalog handling, and status/public-payload label sanitization. Run the review's relevant source-contract and native-isolation checks without regenerating frozen identities. Verify S3-005 remains client-reported and E2-blocked, S3-006 is accurately classified, and `offline_fake`, `STRICT_FREE`, `free_only`, local `BLOCKED_UNVERIFIED`, managed `BLOCKED_PENDING_APPROVAL`, and production `NO_GO` remain unchanged. Do not use live OpenAI OAuth, model discovery, Responses, credit, payment, real source data, hosted service, or production. Report exact commands, exits, blocked network attempts, physical POST counts, and remaining external gates. Do not call this candidate independently accepted unless those checks pass at this exact SHA.

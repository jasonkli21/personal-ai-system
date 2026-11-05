# RE-1 independent-review remediation

**Date:** 2026-11-05 (America/Los_Angeles)
**Reviewed base:** `307ae5cdf163ead57dcae4e3886f68b32b3abee3`
**Disposition:** Local P1 findings remediated for a default-off E1 development candidate. Independent acceptance is still required; E2–E4 remain blocked.

## Findings

| Finding | Disposition |
| --- | --- |
| R1-01 best-effort trace could report a false successful zero-attempt turn | The versioned observation is now `reasoning-observation-v2`. Attempt counts for admitted turns come from the selected generation receipt, and the service refuses to persist a completed assistant turn when that receipt is absent, malformed or not exactly one attempt. Pre-dispatch denials report zero; post-dispatch receipt gaps report unknown. Reservation, settlement, count and quota values remain unknown because the trace observer is diagnostic only. Observer failure and missing-receipt tests cover these paths. |
| R1-02 app, workspace and user ceilings were unrestricted | Until trusted scope grants are installed, the selected runtime supplies `low` ceilings for application, workspace and user. Operator and endpoint limits continue to narrow the result. The authenticated HTTP test requests `max` with an operator ceiling of `max` and verifies effective `low`. |
| R1-03 deterministic input-budget denial could consume a user key | For the local deterministic fake counter, the current-message minimum is checked before the durable message turn is prepared. An impossible tiny budget leaves no active message and can be retried with the same key. Later failures preserve the original key and are not auto-retried. |
| R1-04 typed Python SDK and built-in frontend cannot negotiate effort | These clients remain unsupported for effort. The consumer contract documents the exact negotiated raw HTTP header and request, and HTTP tests cover negotiation and unchanged no-field behavior. No reference app is opted in. |
| R1-05 synthetic native `applied` status overstated fixture delivery | The E1 adapter now parses and uses the serialized bytes at its fake receiving boundary. The observation documentation limits `applied` to that fixture boundary and makes no real provider claim. Mutated, dropped or upgraded controls fail before a generation request. |

No RE-0 benchmark locks, cases, scorer, or driver were changed. No provider credentials, paid calls, external writes, SDK installs, or cloud/emulator operations were used. The default remains `REASONING_ENABLED=false`.

## Verification

Environment: repository `backend/.venv`, Python 3.11.15, macOS arm64. The offline test runner recorded zero network attempts.

| Check | Result |
| --- | --- |
| `make reasoning-check` | 122 passed; zero network attempts. |
| `make reasoning-eval` | 64/64 scripted rows valid; semantic SHA-256 `9c1335f421c00b36f863f7c55c2321d92a02d68358f5887c6bcf8cd8c8fb2ae2`. |
| `make workflow-check` | 70 passed. |
| `make real-task-eval` | 36 scripted rows; coverage and safety canaries passed; no natural-language rubric evidence. |
| `make backend-lint` | Ruff passed. |
| `make naming-policy-check` | Policy passed; 2 tests passed. |
| Focused chat, local inference, gateway, routing, usage, consumer HTTP, federation and external-turn offline suites | 370 passed; zero network attempts. |
| Consumer OpenAPI generation/check | Passed; checked-in schema identifies observation v2 with nullable unknown work counters. |
| `git diff --check` | Passed. |
| `make sdk-check` | 354 passed, 25 failed, 12 deselected. Failures are the planning source-identity and PI-6 frozen-protocol failures identified by the incoming review handoff. The handoff reports the same selection reproduced on its baseline; this remediation did not alter those frozen files. |
| `make consumer-contract-check` | Build step blocked because the sandbox could not access the existing uv cache under `~/.cache/uv`. The direct consumer contract check and the `sdk-check` contract stage passed. |

E0/E1 local verification only. No real private-local model, provider account, issuer, cloud deployment, durable production database, recovery, or native effort honoring was tested. E2 and E3 remain blocked; E4 remains **NO_GO**. Keep higher effort and hosted/production opt-in disabled pending trusted scope-grant integration and independent acceptance.

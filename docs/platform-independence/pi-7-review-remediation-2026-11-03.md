# PI-7 independent review remediation — 2026-11-03

This is implementation follow-up evidence for the independent review received
as `pi-7-independent-review-2026-11-03.md`. It is not an independent review or
an acceptance decision. The reviewed starting revision was
`5c7e377827572a4e7770c10fd9bd91e71a7851b4`, parent
`57fc5ea53af6540c86f6f0df7ef2ff23b67a1d62`, branch `main`. The initial tree
had no tracked modifications and these two untracked user files, both
preserved byte-for-byte:

- `docs/platform-independence/pi-6-conditional-offline-development-codex-handoff.md`
- `docs/platform-independence/pi-7-detailed-implementation-plan.md`

## Dispositions

| Finding | Implementation disposition | Remaining evidence boundary |
| --- | --- | --- |
| R01 subprocess egress | Smoke now requires the reviewed macOS native fence before build or child dispatch. The probe runs TCP and UDP IPv4/IPv6 denial from a child. `--allow-degraded` is development-only and always exits blocked. | `sandbox-exec` was rejected by this managed environment. Native installed core/consumer checks are blocked; no degraded acceptance run was counted. DNS and Unix-domain denial were not independently exercised. |
| R02 local stores | Integration services use a dedicated internal bridge. Wrapper requires operator-approved local image config IDs and registry digests, uses `--pull never --no-build`, fences host bootstrap/tests or refuses, and reports physical sends as prohibited-by-configuration rather than observed zero. | Docker is unavailable here. Compose internal-network behavior, registry provenance, image bytes and native store denial are not reproduced. Do not run up/down on an unverified daemon. |
| R03 ownership and teardown | Container checks now bind immutable image ID, expected command/entrypoint, sensitive environment, capabilities/devices, namespace and mount/port/network settings and runtime state. Teardown re-inventories and compares exact IDs/network immediately before stop/remove. Adversarial fake-CLI tests cover drift, spoofed IDs, extra networks, paused state, duplicate service collision and a teardown race. | Fake Docker tests are not daemon evidence. Container image Entrypoint expectations still require verification against the approved local images before any native use. |
| R04 cloud policy | Success is `static_policy_validated_only`; result includes an empty verified-live-binding list and explicit unverified project, audience, IAM, image, storage, network and billing bindings. Consistent but unbound identifiers remain static syntax/policy input only. Apply remains refused. | No live resource binding or deploy readiness is claimed. |
| R05 dependency provenance | Before copying, every installed distribution file except `RECORD` itself must have a matching RECORD hash. Missing files, edited bytes, `.pth`, startup hooks and editable distributions refuse. Added same-version modified-byte regression. | The prepared environment and its RECORD files remain trust roots. This is an offline operability probe, not a clean reproducible installer or provenance-verified wheelhouse. |
| R06 privacy/evidence | Added canaries for streamed prompt output, trace representation, denied send response, startup exception and child stderr. Existing planner tests cover fixed refusal output and no CLI invocation. The ledger now separates historical author evidence from this follow-up's rerun status. | No exhaustive scan of all application logs, exports, caches, traces, CI artifacts or every SSE/error branch was run. The broad backend run was blocked by sandbox loopback permission errors. |

## Follow-up commands and results

Environment: Darwin arm64, Python 3.11.15, uv 0.11.13, managed Codex
sandbox. No package downloads, provider calls, cloud calls, Docker operations,
personal data, restore or deletion were used.

| Command | Result | Evidence class |
| --- | --- | --- |
| `PATH="$PWD/backend/.venv/bin:$PATH" backend/.venv/bin/python -m pytest -q backend/tests/test_pi7_operations.py backend/tests/test_deployment_script.py backend/tests/test_pi7_core_http.py` | 65 passed, 1 installed-only skip, 2 environment deprecation warnings. | Local synthetic/fake CLI; not native acceptance |
| `PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint` | Passed, all checks passed. | Static |
| `bash -n infrastructure/gcp/deploy.sh` | Passed. | Static |
| `PATH="$PWD/backend/.venv/bin:$PATH" make pi7-cloud-plan` | Passed with `static_policy_validated_only`, apply blocked, no verified bindings, 8 unverified binding classes. Manifest SHA-256 `912051145eb28c95ead41108927e2a0e094294e8bab440f010977165626aba80`. | Static policy only |
| `PATH="$PWD/backend/.venv/bin:$PATH" make pi7-local-smoke PI7_SMOKE_FLAGS=--require-native` | Blocked before build/child dispatch: `sandbox_launcher_rejected`. | Native fence unavailable |
| `PATH="$PWD/backend/.venv/bin:$PATH" make pi7-check` | 221 passed, 4 warnings; zero forbidden Python network attempts. | Python audit-fenced synthetic tests, not OS fence |
| `PATH="$PWD/backend/.venv/bin:$PATH" make platform-independence-check` | First attempt failed opening default uv cache (sandbox permission). Retried with `UV_CACHE_DIR=/tmp/codex-pi7-uv-cache UV_OFFLINE=1`; builds and static inventory passed, then historical planning guard refused with `planning_baseline_source_revision_mismatch_requires_new_version`. | Build/static; expected frozen revision guard |
| `UV_CACHE_DIR=/tmp/codex-pi7-uv-cache UV_OFFLINE=1 PATH="$PWD/backend/.venv/bin:$PATH" make pi2-check` | Builds and inventory passed, then the same planning revision guard refused. | Build/static; no PI-2 installed acceptance |
| `UV_CACHE_DIR=/tmp/codex-pi7-uv-cache UV_OFFLINE=1 PATH="$PWD/backend/.venv/bin:$PATH" make pi3-check` | Blocked on loopback bind: `PermissionError: [Errno 1] Operation not permitted`. | Native fence/permission unavailable |
| `UV_CACHE_DIR=/tmp/codex-pi7-uv-cache UV_OFFLINE=1 PATH="$PWD/backend/.venv/bin:$PATH" make pi4-check` | Blocked on loopback bind with the same permission error. | Native fence/permission unavailable |
| `UV_CACHE_DIR=/tmp/codex-pi7-uv-cache UV_OFFLINE=1 PATH="$PWD/backend/.venv/bin:$PATH" make pi5-check` | Consumer contract passed; native suite blocked on loopback bind with the same permission error. | Static contract passed; native suite unavailable |
| `UV_CACHE_DIR=/tmp/codex-pi7-uv-cache UV_OFFLINE=1 PATH="$PWD/backend/.venv/bin:$PATH" make pi6-check` | Builds passed; `sandbox-exec: sandbox_apply: Operation not permitted`. | Native fence unavailable |
| `UV_CACHE_DIR=/tmp/codex-pi7-uv-cache UV_OFFLINE=1 PATH="$PWD/backend/.venv/bin:$PATH" make backend-test-offline` | 2,347 passed, 1 skipped, 119 deselected, 11 failed and 92 errors. All 103 failures were loopback HTTP tests unable to bind due `PermissionError: Operation not permitted`; a focused PI-6 rerun confirmed 43 passed / 11 failed for this reason. | Broad offline suite, environment-blocked |
| `git diff --check` | Passed before commit. | Static |

The first focused test run exposed a syntax error in the host-fence probe,
another exposed a simulated teardown mismatch, and lint exposed import/style
issues. All were fixed and the final focused run above passed. Initial failures
are retained here rather than erased.

## P7-01–36 follow-up matrix

The prior `scenarios[].status` values in `pi-7-verification.json` remain the
historical implementer report. The new `independent_followup` field records
this session's narrower status; it does not inherit those PASS values.

| Case | Follow-up | Evidence / reason |
| --- | --- | --- |
| P7-01 | BLOCKED | Native installed build denied before build. |
| P7-02 | BLOCKED | Installed physical-absence probe requires the native profile. |
| P7-03 | BLOCKED | Installed loopback HTTP smoke requires the native profile. |
| P7-04 | BLOCKED | Complete installed import/egress probe not rerun. |
| P7-05 | BLOCKED | The modified-byte rejection regression passed, but full offline install/bootstrap evidence was not rerun because native smoke was blocked. |
| P7-06 | NOT_RUN | Full startup/config failure matrix not rerun. |
| P7-07 | NOT_RUN | Repeat cold-start matrix not rerun. |
| P7-08 | NOT_RUN | Native child timeout/signal matrix not rerun. |
| P7-09 | BLOCKED | Docker unavailable; no native dual-store boot. |
| P7-10 | BLOCKED | Docker unavailable; no native restart/bootstrap. |
| P7-11 | BLOCKED | Docker unavailable; no native network/teardown. |
| P7-12 | BLOCKED | Installed unrelated consumer smoke denied by native fence. |
| P7-13 | NOT_RUN | Full consumer identity matrix not rerun. |
| P7-14 | NOT_RUN | Full audience/membership source-scope matrix not rerun. |
| P7-15 | NOT_RUN | Consumer original-key matrix not rerun in installed mode. |
| P7-16 | NOT_RUN | Consumer lost-ack/cancel/restart matrix not rerun. |
| P7-17 | PASS | Fake CLI tripwire and static no-apply tests passed in focused and PI-7 checks. |
| P7-18 | PASS | Malformed and unbound-but-consistent static policy cases passed. |
| P7-19 | BLOCKED | Live IAM/network binding is outside authorized local evidence. |
| P7-20 | PASS | Fake CLI apply/default/legacy refusal tests passed. |
| P7-21 | NOT_RUN | Installed profile test not rerun under native fence. |
| P7-22 | NOT_RUN | Physical provider-send behavior not rerun; no live provider calls. |
| P7-23 | NOT_RUN | Cross-worker/provider budget behavior not rerun. |
| P7-24 | NOT_RUN | Full provider timeout/retry matrix not rerun. |
| P7-25 | NOT_RUN | Canary checks are partial; all sink classes were not scanned. |
| P7-26 | NOT_RUN | Full source rights matrix not rerun. |
| P7-27 | BLOCKED | Actual provider billing and account caps remain unobserved. |
| P7-28 | PASS | Bounded refusal/output and untrusted manifest tests passed. |
| P7-29 | NOT_RUN | Full revocation/send/retrieval matrix not rerun. |
| P7-30 | NOT_RUN | Full retained-history/replay matrix not rerun. |
| P7-31 | BLOCKED | Native/distributed stale restore and erasure remain unavailable. |
| P7-32 | NOT_RUN | Full persistent journal matrix not rerun. |
| P7-33 | NOT_RUN | Installed uninstall/rollback matrix not rerun. |
| P7-34 | PASS | `git diff --check`; no PI-6 evaluation fixtures, locks, API contract or migrations changed. Planning's historical guard refusal was preserved. |
| P7-35 | NOT_RUN | Full MEM-2 default-off integration not rerun. |
| P7-36 | NOT_RUN | Full kill-switch matrix not rerun; hosted stop remains blocked. |

## Gate and compatibility state

Local PI-7 acceptance remains `changes_required` pending fresh independent
review. Hosted deployment, provider/account billing, IAM, native store
recovery/deletion, distributed receipts, PI-5 completion, PI-6 production,
real-model utility A19 and PI-8/A22 remain blocked or no-go. MEM-3+ stays
frozen. No backend runtime, public wire contract, migration, dependency lock,
historical evaluation fixture, threshold, or default-off flag was changed.
Rollback is limited to this tooling/docs commit; do not remove unverified
Docker resources or alter canonical data, receipts, quotas, or tombstones.

A fresh independent Sol High review requested by the supplied handoff was not
performed in this implementation session. This record does not substitute for
that separate review and does not grant local acceptance.

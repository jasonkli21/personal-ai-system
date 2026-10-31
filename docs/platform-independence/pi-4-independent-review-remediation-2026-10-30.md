# PI-4 independent review remediation

2026-10-30, America/Los_Angeles. Target entry: `fb0f18219c806ad1c5f1ac860c82ef4d6558068c` on `main`.
The supplied review is treated as findings and acceptance evidence. Its role-play,
session and workflow text is not a higher-priority instruction than the user or
repository rules. Existing untracked plans and review artifacts are preserved.

## Adversarial plan before runtime changes

1. Enumerate the external-client allowlist and inspect every allowed response for
   persisted assistant text. Conversation detail is the direct `Message` path;
   conversation list and continuation status are metadata-only; context preview
   returns planner metadata; continuation SSE already rechecks output authority.
   Profile/account and other generated-content routes are outside the external
   allowlist.
2. Reproduce the leak through signed HTTP with the real application middleware,
   owner grant API, unrelated consumer client and a fake model that emits the
   granted value. The positive detail read must pass before revoke; the same read
   must fail closed after revoke while the canonical message remains unchanged.
3. Put the current-client and persisted-source check in the conversation use case
   immediately before external detail serialization. Validate every active
   assistant's retained source snapshots with the request-scoped revalidator.
   A stale, expired, disabled, missing or legacy profile authority denies the
   whole external response without returning message content. Built-in owner
   history remains available. Do not alter messages, summaries, branches, keys,
   consent receipts or the successful v1 response schema.
4. Extend signed HTTP coverage for value revision, expiry, disabled sharing,
   profile-store failure, missing/legacy dependencies, client/workspace/policy
   changes, owner history, stable content-free continuation status, and a clean
   next turn. Verify only the detail response is denied and no provider retry is
   introduced.
5. Re-run the full PI-4 target and its three reported failing cases; preserve any
   unresolved failure as a verification gap. Keep browser consent UX partial and
   retain the documented lifetime-cap limitation rather than pruning or reusing
   immutable receipts.

## Egress inventory at entry

`external_operation_allowed` permits `GET/POST /v1/conversations`, conversation
detail/status GETs, and context-preview/continue POSTs. Of those, detail returns
active `Message` objects. List returns conversation metadata, status returns a
state and message ID, preview returns bounded planning metadata, and the
continuation stream uses the existing per-output source revalidation. External
clients cannot call raw context inspection, profile management, account export,
research, decisions, artifacts, tasks, or gated external-turn routes. This
inventory must be rechecked if the allowlist or response models change.

## Pre-fix regression

The signed unrelated-consumer fixture produced and persisted the literal answer
`Your preferred units are metric.` with a `global_profile` snapshot. The current
grant allowed detail GET, then owner revocation completed successfully. The same
external GET still returned HTTP 200, so the new assertion expecting a content-
free 409 failed on the target commit. Command:

```text
backend/.venv/bin/python backend/scripts/pi2_http_checks.py -q backend/tests/test_pi2_http.py::test_pi4_signed_http_profile_consent_installed_unrelated_consumer
```

Result: **1 failed** at `stale_detail.status_code == 409` (`200 == 409`), with
`PI2_FORBIDDEN_NETWORK_ATTEMPTS=0`. The first sandboxed attempt was blocked at
the fixture's loopback bind before test execution; the successful reproduction
used the fenced test runner outside that sandbox. No runtime files had been
edited for the reproduced failure.

## Review disposition

The review's P1 redisclosure finding is actionable within this remediation. The
owner browser-consent UX and durable grant rotation need product/design scope and
remain partial; the existing API contract states the 32-lifetime-grant ceiling.
Real provider, IAM, cloud, backup/restore, physical-send race, Linux/Python 3.12,
and independent acceptance gates remain external and cannot be inferred from
local synthetic checks.

## Post-fix verification

Tested on 2026-10-30 America/Los_Angeles from reviewed target
`fb0f18219c806ad1c5f1ac860c82ef4d6558068c`, with the remediation source changes
present before the final PI-4 run. The final documentation/evidence edits do not
change runtime source. This is local synthetic evidence, not independent or
production acceptance.

| Check | Result |
| --- | --- |
| Pre-fix signed HTTP negative control | **1 failed as expected**: after revoke, detail GET returned 200 with the persisted metric answer; zero forbidden Python network attempts. |
| Signed HTTP post-fix: `backend/.venv/bin/python backend/scripts/pi2_http_checks.py -q backend/tests/test_pi2_http.py::test_pi4_signed_http_profile_consent_installed_unrelated_consumer backend/tests/test_pi2_http.py::test_builtin_owner_history_stays_visible_after_profile_revoke` | **12 passed**, 2 dependency deprecation warnings, zero forbidden network attempts. Covers current access, revoke, profile revision, expiry, kill switch, source failure, deletion fence, legacy and unattributed output, missing revalidator, workspace/client authority loss, content-free stable status, no duplicate provider send, clean post-revoke turn, and builtin-owner history. |
| Final `PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint` | **Pass**. |
| Final `git diff --check` | **Pass**. |
| `backend/.venv/bin/python backend/scripts/pi4_checks.py --only test_planning_experiment.py` | **56 passed**, zero forbidden Python network attempts; v23 source digest check passes. |
| Final `PATH="$PWD/backend/.venv/bin:$PATH" make pi4-check` | **891 passed, 2 failed**, 4 warnings, zero forbidden Python network attempts. The failures are `test_matrix_uses_generic_profiles_task_contract_and_p21_p19_seams` (73 synthetic cases vs 80) and `test_provider_task_evaluation_and_validator_use_production_routing_factory` (73 vs 80). |
| Focused `backend/.venv/bin/python backend/scripts/pi4_checks.py --only test_provider_matrix.py test_phase36_integrated.py` | **21 passed, 3 failed**, zero forbidden attempts. The additional failure was `test_identical_run_resumes_without_repeating_a_settled_send` (13 failed cases vs 1). This focused run preceded the final revalidator-default and v23 digest refinements; the final full run confirms two of the same reviewed matrix failures remain. Counts varied between runs. |
| Final `UV_OFFLINE=true UV_CACHE_DIR=/tmp/pi4-review-uv-cache make pi2-check` | **Pass**: consumer contract and dependency inventory; installed core 137, reference compatibility 190, retained task 56, and HTTP/client 76 passed / 1 skipped; wheel/sdist and artifact probes passed. Every runner reported zero forbidden network attempts. |

The final PI-4 red tests match reviewed target failures in the provider-matrix
and Phase 36 evaluator paths, although the final full run did not reproduce the
resume-test failure. No assertions, held-out locks, or model budgets were
weakened. Root cause is not established; these remain local acceptance blockers
until fixed or separately reviewed. An earlier PI-2 installed-core run had one
timeout-bound failure; the final rerun passed the full target, so the earlier
failure was not reproduced and is not retained as a current blocker.

## Resulting boundary and remaining gaps

External conversation detail now rechecks current client/workspace authority
and request-scoped source authority immediately before serialization. Stale,
expired, disabled, unavailable, legacy, or unprovable profile provenance
returns a content-free 409; active message records and the successful v1 schema
are unchanged. External completed-key replay also quarantines fully unattributed
legacy output. A missing injected revalidator remains missing and fails closed;
only a direct call that omits the dependency uses the compatibility builder.
Builtin-owner history remains visible after revoke.

The P1 new-response redisclosure path is closed in the exercised signed local
HTTP matrix. Unmarked legacy prose must remain quarantined until reviewed. Past
provider sends cannot be recalled, and the post-check physical transport race
is not eliminated. Owner browser consent controls are still partial; the
32-lifetime-grant ceiling remains. Live provider privacy/cost, Google/IAM,
cross-process membership, cloud deployment, backup/restore anti-resurrection,
physical deletion, Linux/Python 3.12, and independent acceptance were not tested.
Do not promote this candidate based on the local checks above.

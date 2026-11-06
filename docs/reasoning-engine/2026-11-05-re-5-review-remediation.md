# RE-5 independent-review remediation

2026-11-05 America/Los_Angeles. This remediation addresses review findings
RE5-F01 and RE5-F02 from the review of `6bca65313f8df9511465af5dc2feb49e6eb83c2a`.
The changes remain within the standalone E1 loopback preview and release test
surface. They do not change the HTTP service, frozen RE-4 evidence, source locks,
provider routing, or production gates.

## Findings addressed

**RE5-F01 — SDK receipt validation.** The public SDK now validates the pinned
E1 progress identity and policy, UUID and digest syntax, direct/low strategy,
cursor and outcome/state consistency, bounded ordered attempt records and their
resource ceilings. Submit validates unique integer slot/value pairs; status and
cancel reject any result field. Malformed or contradictory successful responses
raise `UncertainTurn` and retain the original operation key. The SDK does not
retry a POST. Table-driven tests cover missing identities, malformed versions,
strategy, cursor, state/outcome and result pairs, plus valid partial results and
metadata-only responses. The installed wheel consumer passes without private
core imports.

**RE5-F02 — hermetic artifact test.** The dirty-checkout test now injects a
controlled dirty state and confirms the native installer fence is not reached.
The untrusted-toolchain pin test injects a clean state and expects the
`untrusted_install_toolchain` rejection, also before the native fence. No
installer safety check was relaxed.

## Verification

| Check | Result |
| --- | --- |
| SDK synthetic receipt tests | 15 passed |
| `make synthetic-reasoning-check` | 3 passed; blocked network attempts 0 |
| `make synthetic-reasoning-install-check` | Installed wheel consumer passed over IPv4 loopback; only SDK and fixture auditor installed |
| `make release-profile-check` | 10 profile tests and 15 artifact tests passed |
| `make reasoning-check` | 122 passed; blocked network attempts 0 |
| `make reasoning-adaptive-check` | 75 passed; blocked network attempts 0 |
| `make reasoning-adaptive-conformance` | 75 passed; blocked network attempts 0; `NO_PROMOTION` retained |
| `make reasoning-adaptive-eval` | Historical replay passed; 182 cases, 924 rows, original semantic/source seals matched, `NO_PROMOTION` retained |
| `make backend-lint` | Passed with the backend lock-pinned Ruff |
| `make naming-policy-check` | Passed |
| `make sdk-check` | Failed: 367 passed, 25 failed, 12 deselected. Failures remain one planning source identity mismatch and 24 PI-6 frozen protocol identity mismatches; historical seals were not changed. Offline audit attempts: 0. |

The `make workflow-check` wrapper could not start because this checkout's shell
has no `python` command on PATH. The equivalent invocation,
`backend/.venv/bin/python -m pytest -q backend/tests/test_workflow_contract.py
backend/tests/test_mutations.py`, passed 70 tests. The first installed-consumer attempt was blocked by the
sandbox's loopback socket restriction; the same check was rerun with approved
local socket access and passed.

## Remaining evidence and gates

RE5-F03 remains blocked by the inherited planning and PI-6 source identity
failures reported above. RE5-F04 did not reproduce in this environment:
`make reasoning-check` completed with zero blocked network attempts. Native
PostgreSQL process-loss acceptance and the separate-process durable consumer
journal/restart drill were not run because no disposable migrated PostgreSQL
cluster was provisioned. They remain `BLOCKED_UNVERIFIED`.

E2–E5 remain `BLOCKED_UNVERIFIED`; adaptive promotion remains `NO_PROMOTION`;
general SDK/HXE release and production remain `NO_GO`. The in-memory HTTP
preview remains limited to development within one process epoch. This
remediation is not independent phase-exit or release approval.

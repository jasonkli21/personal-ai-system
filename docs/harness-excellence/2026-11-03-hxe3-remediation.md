# HXE-3 workflow lifecycle remediation — 2026-11-03

Target implementation: `61e88a308c6d2f965e261a5a86ab2bd909f0bc95`, the
reviewed direct child of `6d9fd3c4252e3e2bde6563af76d7a896af7de5f8`. This
receipt records the local remediation session and does not replace the original
[implementation verification](2026-11-03-workflow-verification.md).

## Remediation

**F1 — durable operation binding.** New attempts persist a nonsecret binding
with the registered tool ID/version and trusted effect class, canonical
validated step digest, pinned source snapshot digest and scoped original-intent
digest. Reservation and dispatch compare the same binding. Receipts without the
optional binding remain readable and are not backfilled. Source passages and
query text are not added to receipts.

**F2 — ambiguous dispatch.** Exceptions and cancellation after dispatch without
an observed tool result now terminalize the run as `uncertain`, retain the
attempt binding and prevent replay from dispatching again. Failures before
dispatch and failures after the handler returned an observed result remain
known failures. The immutable registry still permits only local read-only
retrieval.

**F3 — independent processes.** Added a barrier-synchronized two-process test
using separate PostgreSQL connections. It covers one winning claim, stale
fence rejection, dispatched-attempt recovery to uncertainty, and bounded
replacement of a reserved-but-undispatched attempt. The test was not executable
in this session.

Focused regression cases also cover binding integrity, legacy receipts,
same-key intent conflicts, cancellation, timeout, source revocation, observed
tool failure, terminal replay and no duplicate execution. The legacy receipt
test ran directly without a database; the remaining persistence cases require
the blocked disposable PostgreSQL fixture.

## Verification performed in this session

| Command/check | Result | Detail |
| --- | --- | --- |
| `git rev-parse HEAD` and `git log -5 --oneline` | PASS | HEAD was the exact reviewed target; no intervening commit. |
| `python3.11 -m py_compile backend/src/personal_ai/contracts/workflow.py backend/src/personal_ai/persistence/postgres/workflows.py backend/src/personal_ai/workflow/service.py backend/src/personal_ai/evaluation/planning.py backend/src/personal_ai/evaluation/pi6_contracts.py backend/tests/persistence/test_workflow_postgres.py backend/tests/test_planning_experiment.py backend/tests/test_pi6.py` | PASS | Changed Python files passed standard-library syntax compilation. This is not test execution. |
| `git diff --check` | PASS | No whitespace errors. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make workflow-check` | PASS, 70 passed | Focused workflow contract and synthetic domain effect tests. |
| `cd backend && .venv/bin/python -m pytest -q tests/persistence/test_workflow_postgres.py::test_legacy_attempt_without_operation_binding_remains_readable` | PASS, 1 passed | Confirms a historical receipt without the optional binding remains parseable. No database used. |
| `make workflow-postgres-check` | BLOCKED, 0 tests | `PERSISTENCE_TEST_POSTGRES_DSN` is unset. The local PostgreSQL 16.15 binaries have no installed `vector` extension; `pg_isready` reported no server at `/tmp:5432`. No database was started or used. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make naming-policy-check` | PASS | Naming checker and its 2 unit tests. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint` | PASS | Ruff passed across the backend after correcting import ordering. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make provider-isolation-check` | PASS, 840 passed | Native IPv4/IPv6/Unix denial; zero forbidden Python network attempts. The sandboxed first attempt could not bind its local test socket; the final run used the repository's native harness. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make retrieval-security-check` | PASS, 148 + 34 passed | Consumer contract parity, native-fenced retrieval checks, and signed loopback HTTP; zero forbidden network attempts. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make mcp-adapter-check` | PASS, 44 passed | Offline adapter suite; zero forbidden network attempts. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make planning-eval` | PASS, 30 rows | Lock v33 binds the remediation source; planner calls 0; decision remains `non_promotion`. |
| `PATH="$PWD/backend/.venv/bin:$PATH" UV_CACHE_DIR=/tmp/pas-uv-cache make offline-benchmark-check` | PASS | Source PI-6 suite: 55 passed, 68/68 rows. Installed full consumer: 68/68 rows, native loopback-only fence, no safety veto, not promoted. Core-only's unavailable optional dependencies were correctly ineligible. |
| `PATH="$PWD/backend/.venv/bin:$PATH" PYTHONPATH="$PWD/sdk/python/src:$PWD/reference-apps/src:$PWD/examples/project-checklist/client/src:$PWD/examples/project-checklist/host/src:$PWD/examples/reading-logbook/client/src:$PWD/examples/reading-logbook/host/src" make backend-test-offline` | FAIL, 2,499 passed, 1 failed, 1 skipped, 154 deselected | The sole failure is `test_stale_derived_restore_keeps_revocation_and_original_keys`, with HTTP 422 `context_explicit_source_unavailable`; this matches the inherited failure reported on the archived baseline. No PI-6 failure remained with the required loopback permission. |
| `PATH="$PWD/backend/.venv/bin:$PATH" UV_CACHE_DIR=/tmp/pas-uv-cache make backend-build` | PASS | Backend source distribution and wheel built. |
| `git diff --check` | PASS | No whitespace errors. |
| Local Markdown links in five updated documents | PASS | Zero missing local targets. |
| Frozen planning and PI-6 fixture files | PRESERVED | New additive planning lock v33 and source generation 7 were added. v31/v32 and source generations 1–6, corpus/case bytes, scoring, thresholds and non-promotion remain preserved. |

The existing broad-suite failure
`test_stale_derived_restore_keeps_revocation_and_original_keys` was reproduced
in this session with HTTP 422 `context_explicit_source_unavailable`. This
matches the implementer-reported archived-baseline failure; the archived
baseline was not rerun in this session. The failure remains outside this
remediation scope.

## Acceptance and remaining gates

| Level | Status after this session |
| --- | --- |
| E0 static | PASS for the reviewed static boundary; this remediation adds no external executor or effect permission. |
| E1 synthetic | PARTIAL — contract/domain checks and PI-6 offline evidence passed; workflow PostgreSQL lifecycle and two-process cases remain blocked by the missing disposable PostgreSQL/pgvector endpoint. Do not report F1–F3 as fully reproduced. |
| E2 installed/native | BLOCKED — no installed consumer or native workflow isolation proof. |
| E3 live | BLOCKED — no live issuer, external send, hosted provider or real mutation. |
| E4 deployed | BLOCKED — restore-safe key authority, deployed identity and recovery/erasure remain open. |
| E5 utility | NOT RUN. |

The `NOW` F1–F3 verification gate remains open until focused tests and the
two-process PostgreSQL test run against the repository's disposable native
fixture. The existing enablement gates remain open. Real effects, hosted
providers, external execution, native sandboxing, background workers and
production remain disabled; production remains **NO-GO**.

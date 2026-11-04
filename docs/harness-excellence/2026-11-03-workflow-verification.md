# HXE-3 workflow implementation evidence — 2026-11-03

Baseline `6d9fd3c4252e3e2bde6563af76d7a896af7de5f8`. The implementation
commit is its direct child. Scope and sequencing are recorded in the
[plan hardening note](2026-11-03-workflow-plan-hardening.md) and
[ADR 0025](../decisions/0025-workflow-lifecycle-authority.md).

## Acceptance boundary

| Level | Decision | Evidence |
| --- | --- | --- |
| E0 static | PASS | Versioned closed tool and graph, exact verified scope and source snapshot, additive workflow migration, no registered background/native/effect path or external send |
| E1 synthetic foreground | PASS for the local slice. Overall scope is PARTIAL E1 | A disposable PostgreSQL 17/pgvector database exercised the full migration chain, bounded local multi-step task, original-key replay after reconnect, changed-body conflict, competing submissions and claims, cancellation, live revocation, cursor gaps, and a process exit after dispatch followed by uncertainty. The test scope had no provider calls or mutating dispatch. Canonical domain effect tests used synthetic adapters only |
| E2 installed/native profiles | BLOCKED | No installed workflow consumer or tool adapter isolation proof. Native PostgreSQL tests cover the database lifecycle only. There is no workflow API/SDK addition to consumer v1.2.0 |
| E3 live | BLOCKED | No live source issuer, external send, MCP peer, provider call, or real mutation was exercised |
| E4 deployed | BLOCKED | Mixed-age restore, monotonic keys outside the restored database, deployed identity, erasure, and recovery are open |
| E5 utility | NOT RUN | No longitudinal evidence or promoted model behavior |

**Production remains NO-GO.** Local fixture scope includes synthetic
public-classified sources and authenticated test identities. The local
source/client check is cooperative. Deadline checks bound dispatch and disclosure
at those boundaries, with bounded in-process lexical work between checks.
Remote send/revoke linearization remains an enablement gate. Replays contain
terminal status and receipts. Source text is transient and withheld on
detected revocation. The subprocess test simulates a committed dispatch
receipt followed by process loss and covers database recovery.

## Verification

The backend used the checkout's macOS ARM64 CPython 3.11.15 environment.
For the broad offline run, `PYTHONPATH` included the checkout SDK, reference
apps, Project Checklist client/host and Reading Logbook client/host source
directories. The test runner used a native loopback-only network fence.
The native store target used a disposable local PostgreSQL 17/pgvector
cluster and the repository's isolated database fixture.

| Command | Result |
| --- | --- |
| `make workflow-check` | PASS, 70 passed. Includes 16 workflow contract tests and 54 existing synthetic domain effect cases |
| `make workflow-postgres-check` | PASS, 29 passed. Disposable PostgreSQL 17 with pgvector, separate databases, local loopback, competing connections and a child process. Default sandbox denied shared memory; a disposable PostgreSQL 16 attempt lacked pgvector |
| `make naming-policy-check` | PASS, checker plus 2 checker tests. Manual scope covers contract names, SQL, test names and the module guide |
| `make backend-lint` | PASS |
| `make provider-isolation-check` | PASS, 839 passed. Native IPv4/IPv6/Unix denial passed with zero forbidden Python network attempts |
| `make backend-build` | PASS with a writable temporary UV cache and offline mode. The wheel contains the workflow contract, service and SQL migration |
| `make retrieval-security-check` | PASS, consumer OpenAPI parity, 148 native-fenced offline cases and 34 signed loopback HTTP cases. Both reported zero forbidden network attempts. The final run preserved the legacy zero-argument tool guard and exercised explicit workflow snapshot pinning |
| `make mcp-adapter-check` | PASS, 44 passed and zero fenced network attempts. Existing adapter regression only |
| `make offline-benchmark-check` | PASS on the isolated retry. The source suite passed 54 tests and measured 68/68 arms. The installed full consumer also measured 68/68 arms with valid coverage, native loopback-only fencing, and no safety veto. Core-only correctly reported optional dependencies unavailable. The overlapping attempts recorded two source arm timeouts and one installed arm timeout before the isolated retry. Frozen scoring and time limits were preserved |
| `make backend-test-offline` | FAIL, 2,497 passed, 1 failed, 1 skipped, 148 deselected. The sole failure reproduces on the archived baseline under the same loopback fence |
| `make planning-eval` | PASS, 30 rows with zero planner calls and `non_promotion`. Additive lock v32 and benchmark source generation 6 retain prior identities and frozen case/scorer bytes |
| `git diff --check` and local documentation link targets | PASS, 117 local targets checked |

The baseline reproduction used the checkout interpreter against `git archive
6d9fd3c4252e3e2bde6563af76d7a896af7de5f8` and ran `python -m pytest -q
backend/tests/test_application_lifecycle.py::test_stale_derived_restore_keeps_revocation_and_original_keys`
under the same loopback-only fence and checkout client-source paths. Both
runs fail at the initial continuation with HTTP 422
`context_explicit_source_unavailable`. The restore gate remains open.

## Rollback and review

Disable the internal foreground caller or return it to its default-off
setting. Preserve the additive table and original keys, including uncertain
receipts. If reverting the application, deploy the baseline artifact while
leaving the additive migration in place. Recover uncertain runs from their
original receipts and keep stale snapshots quarantined.

**NOW** is exact-commit review. **BEFORE_ENABLEMENT** requires independent
approval, installed workflow and native isolation evidence, durable issuer
permits and restore-safe original-key authority. **DEFER** covers public
consumer operations, unattended dispatch, generic effects, parallel execution,
MCP workflows, and adaptive reasoning. See the
[gate registry](../platform-independence/pi-cross-phase-gate-registry.md).

One Sol High independent review of the exact implementation SHA should
produce a single self-contained Luna High/XHigh remediation handoff. Luna
handles review fixes and final verification in one pass.

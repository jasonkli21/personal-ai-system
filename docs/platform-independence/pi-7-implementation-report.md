# PI-7 implementation report

2026-11-02 (America/Los_Angeles). Local implementation candidate for fresh
independent review. Base and expected parent
`57fc5ea53af6540c86f6f0df7ef2ff23b67a1d62` on main. The review target is the
single child containing this report. A commit cannot embed its own SHA.
Run `git log -1 --format='%H %P' -- docs/platform-independence/pi-7-implementation-report.md`
to resolve the exact commit and parent. The [machine ledger](pi-7-verification.json)
pins the tested executable files, original input hashes, commands, artifact
identities and P7-01–36 dispositions.

The [hardened plan](pi-7-implementation-plan.md) is committed separately
from the two pre-existing untracked inputs. The PI-6 handoff and original
PI-7 detailed plan remain untracked with their original bytes.
The [pre-code critique](pi-7-plan-hardening.md) records the plan delta, source
inspection, risk model and rejected alternatives. The attached implementation
prompt governed the authorized repository task. No separate review session
or delegation was used.

## Implemented scope

| Area | Change |
| --- | --- |
| Core and consumer | Build the wheel and sdist in an owned directory, rebuild from the sdist, install against prepared lock-checked dependencies, and run real FastAPI/lifespan and loopback chat/context. Install Reading Logbook's host and client separately, exercise signed v1 HTTP and original-key recovery, uninstall both and rerun core. |
| Disposable persistence | Add explicit local Docker doctor/up/bootstrap/smoke/down over the existing integration services. Validate Compose labels, image mode, mounts, bridge membership, port bindings and readiness. Stop and remove by inspected IDs. Docker was unavailable for native validation. |
| Cloud | Replace the legacy mutating deploy entrypoint with a static planner. Validate desired identity, numeric AWS claims and service-account separation, private ingress, secret reference, egress, digests, quotas and features. Report redacted static drift and refuse apply. The prior imperative entrypoint remains available in the pinned parent for audit. |
| Quota and diagnostics | Keep canonical owner admission and P19 attempts, quota and usage. Test concurrent synthetic daily exhaustion/reset, P19 reservation refusals, mock transport failures and retry safety, local chat kill switch and redacted planner/HTTP diagnostics. The only admitted PI-7 plan has zero remote provider budget. |
| Recovery and topology | Exercise stale derived messages against revoked source authority, retain unknown/completed original keys outside the restored data, and document all relevant copies plus the isolated recovery drill. Retain the Postgres/DynamoDB split. |

The installed core source tree, public consumer contract, dependency lock,
migrations, historical fixtures, default-off flags, source revalidators and
receipt semantics retain their pinned bytes. The deploy entrypoint deliberately
refuses the old positional apply invocation.

## Gates

| Gate | Disposition |
| --- | --- |
| `pi5_completion` | `blocked_unverified` under the inherited gate |
| `pi6_offline_evaluation` | `locally_complete` for its frozen synthetic benchmark |
| `pi6_production_promotion` | `no_go` |
| `pi7_offline_operability` | `local_candidate` for installed synthetic core and consumer. Native persistence is blocked. |
| `pi7_cloud_preflight` | `plan_validated` for the static synthetic profile |
| `pi7_hosted_operations` | `blocked_unverified` |
| `pi7_native_recovery_deletion` | `blocked_unverified` |
| `pi7_release_promotion` | `no_go` |
| PI-7 independent review | Pending |

## Verification and retained failures

Run the [operations commands](pi-7-operations-runbook.md) with the prepared
backend virtualenv. The local platform was Darwin arm64, Python 3.11.15 and
uv 0.11.13. The managed shell refused nested sandbox setup and numeric
loopback bind. The initial degraded smoke built and installed the core,
then stopped at bind with one failed and five passed tests. A separately
approved execution used the macOS loopback-only sandbox and native IPv4/IPv6
probes. The first consumer attempt then exposed a copied runner basename
mismatch. It passed 75 tests with one skip and one failed subprocess test.
The corrected run passed 77 tests with one skip for the source-only second
synthetic app registration. The wheel and sdist rebuild each passed six
core tests and uninstall recovery passed another six. Both the native
core and native consumer runs recorded zero forbidden Python network attempts.
The initial lint run found an implicit string concatenation in the child probe.
A later lint run found a redundant lambda in the Docker test fixture.
The final lint run passed. The first full offline suite exposed that the
new deployed-startup test depended on ambient AI_PROVIDER and AI_MODEL.
It now injects explicit synthetic settings. The source-only fixture check and
both installed profiles passed after that correction.

The final five listener-to-health samples were 99.73, 39.96, 171.21,
50.01 and 29.99 ms. Nearest-rank p50 was 50.01 ms and p95 was 171.21 ms.
These samples begin after factory creation. Build, install and Python import
time are outside the measurement. The first isolated build omitted the
repository's VCS exclusions, so Hatchling included duplicate wheel members.
The final launcher carries the exclusions into the build and rejects
duplicates. The wheel and sdist SHA-256 values match the standard build,
and the wheel rebuilt from the sdist matches the built wheel. The tested
platform was macOS 27.0.1 on arm64. Linux and Python 3.12 remain unverified.

Docker was absent. The doctor command refused before any daemon operation.
The Compose/DynamoDB path remains blocked. A separate native test used a
fresh loopback PostgreSQL 17.11 cluster with pgvector 0.8.7 and no Unix
listener. An inserted marker survived `pg_ctl` stop/start. All 17 P19 native
tests passed using database-per-case isolation. For reproduction, initialize a
new owned temporary cluster with
`LC_ALL=C initdb -D "$test_dir/data" -A trust -U pi7_test --locale=C --encoding=UTF8`.
Start it under the native loopback fence with
`LC_ALL=C pg_ctl -w -D "$test_dir/data" -o "-h 127.0.0.1 -p $test_port -k ''" start`
on a fresh port. Verify `SHOW data_directory` against the owned path before
writing. Use its numeric-loopback test DSN for the ledger's exact pytest
target. The first startup failed without a valid locale. The next cluster
booted and restarted, but the C locale's default SQL_ASCII encoding caused
16 P19 namespace comparisons to fail because psycopg returned bytes.
The UTF-8 rerun corrected the test environment.

The preflight CLI, native fenced runtime, standalone PostgreSQL, in-process
fake ports and synthetic stale recovery have separate evidence classes.
Native restore/deletion, live provider/IAM/cost and hosted smoke remain
blocked. The P7-01–36 ledger records the command results.

The corrected full offline run passed 2,436 tests with one installed-only skip
and 119 deselections. The final PI-7 check passed 207 tests. PI-2 through PI-6
passed their requested regressions. The source and full installed PI-6
evaluators measured 68/68 rows each. The first PI-1 packaging run failed one
inherited reference test when immediate itinerary replay returned
`proposal_busy` after an unknown generation outcome. This is consistent with
the terminal write missing its short reserved window. A rerun passed with
the original assertions and deadlines. Planning, retrieval, research, memory
control and memory knowledge causal evaluations passed at the pinned
pre-commit revision.

## Skeptical review and rollback

- The core package is loaded from the isolated install. The startup guard
  still refuses an unavailable retained reconciler. The consumer subprocess
  lacks the core and host packages, and the core works after both optional
  distributions are removed. Build reproducibility still depends on a
  prepared, trusted dependency installation.
- The legacy Cloud Run script changed global project configuration and
  enabled services before checking references. Its Gemini label diverged
  from the explicit inference default. The new entrypoint has no mutation
  path. Static topology validation does not attest to live ingress,
  reachable private routes, registered OAuth applications, AWS federation
  or secret versions. An approved deployer and live checks must establish
  those before use.
- The route limiter's owner-only estimates miss ancillary and multi-worker
  effects. P19 and the attempt journal remain the owning authorities.
  Uncertain reservations are retained. The test fence proves zero remote
  dispatch for the installed smoke. Provider usage caps, actual billed
  costs and the outcome of a switch racing an already reserved send remain
  open. Existing app request logs have their separate correlation fields.
- A stale snapshot of source authority and receipts can undo a revocation
  and re-admit the original key. The synthetic drill kept those authorities
  outside the restored messages and observed detail/replay/send denial.
  The [native drill](pi-7-data-lifecycle-runbook.md#operator-approved-native-drill)
  requires approved isolation, retained monotonic authority and cross-store
  recovery evidence.
- Roll back the smoke/plan tooling without touching canonical stores, source
  authority, original keys or tombstones. Stop the disposable profile only
  through verified ownership. Keep cloud apply quarantined during rollback.
  The original PI-6 and planning lock bytes are retained. Planning v27's
  current-or-direct-child rule binds its frozen source revision to
  `c22c646a30dc62d1e9dd8eec7747453e45b7071b`. The pre-commit run can use
  its direct child `57fc5ea`. The PI-7 commit is two generations after that
  frozen revision and is outside the guard. Reproduce the historical
  planning check at the pinned PI-7 parent. A new source binding would need
  separate planning and PI-6 evaluation versioning.

Use the [review handoff](pi-7-independent-review-prompt.md) against the exact
implementation commit in a fresh session. Production gates require separate
authorization and evidence for account/provider/source rights, deployed IAM
and network, distributed receipts and anti-rollback, physical deletion,
native restore and all predecessor blockers.

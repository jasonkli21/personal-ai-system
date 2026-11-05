# RE-2 verification record v1

2026-11-05, America/Los_Angeles. Implementation candidate for independent review.

| Revision | Identity |
| --- | --- |
| Base commit | `d063980bd588f94194c55918be06b722ccf7adde` |
| Base tree | `fab3a2ae5f40c2c738e5624c852ca26fc694c3c6` |
| Target implementation tree, excluding this report | `a8d3d9af0924803a54e8407c0c6d16e4f50eda10` |

The target commit is the single commit that introduces this report. Resolve it
with `git log -1 --diff-filter=A --format='%H %T' -- docs/reasoning-engine/re-2-verification.md`.
The implementation tree fingerprint excludes this report so it can be recorded
without a recursive hash. The pre-existing PRD move and planning files were
left outside the commit.

| Gate | Disposition |
| --- | --- |
| E0 | Candidate verified. Closed requests and fixed templates, scoped original intent, compatibility and rollback tested. |
| E1 | Synthetic candidate verified locally. Four templates and matched-budget fixture signal. Native PostgreSQL tests used separate claimants and process exits. Independent review pending. |
| E2 | Unverified. Actual model profile, resource isolation and installed accounting require separate evidence. |
| E3 | Blocked. Real provider eligibility, issuer-bound physical send and actual external-source authority remain outside the synthetic profile. |
| E4 | NO_GO. Deployment, mixed-age restore and monotonic revocation across restored authority stores require separate evidence. |
| E5 | Unverified. Real-model quality, latency and cost at matched budgets require separate trials. |

## Checks

| Command | Result |
| --- | --- |
| `make reasoning-check` and `make reasoning-eval`, each twice | 122 tests each run. Frozen v2 measured 64/64 valid rows with semantic SHA-256 `9c1335f421c00b36f863f7c55c2321d92a02d68358f5887c6bcf8cd8c8fb2ae2`, matching the parent. |
| `make reasoning-orchestrator-check` and `make reasoning-orchestrator-eval`, each twice | 47 tests each run. Both fresh evaluation processes produced the same semantic digest below. |
| `make workflow-check` | 70 passed. |
| `make workflow-postgres-check` | 51 passed against disposable PostgreSQL 17.11 with pgvector 0.8.7. Normal migrations applied. Includes 35 legacy cases and 16 new cases. |
| `make backend-lint`, `make naming-policy-check`, `git diff --check` | Passed. Existing migration and frozen reasoning files have no changes. |
| Auth, context, chat, inference, usage and continuation offline selection | 375 passed, 1 skipped. Python network audit recorded zero attempts. |
| `make provider-isolation-check` | Native IPv4, IPv6 and Unix denial probes passed. The suite recorded 845 passes and the inherited planning source-lock failure, with zero forbidden Python attempts. |
| `UV_OFFLINE=1 make consumer-contract-check` with a writable temporary UV cache | Built the consumer artifacts. The core evaluation probe stopped at inherited `planning_baseline_changed_requires_new_version`. |
| `make sdk-check` | 354 passed, 12 deselected, 25 inherited planning/PI-6 source-lock failures. Same failure set on the pinned parent. |
| `make backend-test-offline` with SDK and example paths on `PYTHONPATH` | Broad run before the final receipt binding hardening had 2,957 passes, 36 failures, 159 errors, 1 skip and 193 deselections. The matching parent archive reproduced the same planning/PI-6 failures and sandbox loopback errors. Two additional archive-only failures came from inherited Git environment variables in tests that initialize temporary repositories. The plain parent command initially failed SDK import during collection. |
| Stale-derived-restore test with an approved local loopback fixture | Passed individually on both parent and target. |

Checks ran on macOS with the repository environment's Python 3.11.15. The
PostgreSQL tests used a disposable Unix socket and no TCP listener. The
sandbox required approval to start the local database and access its socket.
The isolated restore test used a synthetic loopback HTTP listener. The
provider-isolation suite created a Unix listener for its nested denial probe.
No provider, emulator, cloud or paid request was made. Existing dependency
warnings were retained.

## Paired evidence

The independently scored cohort preregistered 60 pairs, with 28 held out.
Both arms used the same scripted response fixture, task, caps and canonical
workflow/chat path. The runner alternated arm order and withheld expected
answers from runtime. The hermetic evaluator uses a transaction double around
canonical workflow rows. Durability evidence comes from the separate native
suite. Outcomes are fixture comparisons.

| Measure | Verified direct | Automatic strategy |
| --- | ---: | ---: |
| Exact completions, all pairs | 26 | 48 |
| Verified constraints | 44 | 66 |
| Abstentions | 22 | 12 |
| Witnessed physical fake sends | 54 | 96 |
| Witnessed pure checks | 53 | 65 |
| Count operations reserved | 378 | 672 |
| Input/output bytes reserved for inference | 55,296 / 6,912 | 98,304 / 12,288 |
| Uncertain inference receipts | 1 | 1 |
| False claims / critical safety vetoes | 0 / 0 | 0 / 0 |

Gain was +22 exact completions across 36 eligible pairs, including +7 on the
12 eligible held-out pairs. The simple cohort had zero extra calls. The
preregistered verdict was `OFFLINE_SIGNAL_ONLY`. Semantic SHA-256 was
`660e5130374a633d9ac5001293393d1950d5b99b6f694ec8e42840f7bcbc0db5`.
The seal file SHA-256 was
`b09605c139eee55730e51625e556959a98570187814d859589afbfe01fe4c414`.
Elapsed work was measured separately from the digest.

The native suite separately witnessed physical fake sends during process
races and crash recovery. Loss after committed dispatch or acknowledgement
remained uncertain on the original attempt and produced no replay body or
resend. Cancellation and authority loss withheld live output. Provider
reservation, settlement and USD cost remain null. Known synthetic generation
bytes are attached only to the exact terminal receipt consumed by chat.
Events and receipts carry identifiers and resource facts. The live profile
admits no external source and its terminal commit clears numeric checkpoints.

Rollback follows the [workflow guide](re-2-implementation.md#rollback). Keep
the original keys and uncertain receipts and disable the reasoning host.

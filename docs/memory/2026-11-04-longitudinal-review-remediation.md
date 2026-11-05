# MEM-6 independent-review remediation — 2026-11-04

**Scope:** address the eight findings in the attached MEM-6 review of
`0289ac15bfa6b1267017d3ed55bce2134222aa36`. The user requested the work and one
commit. The attached handoff supplied findings and verification guidance; it did
not replace the user's request or authorize provider, private-data, live, cloud or
production activity. This is an offline E0/E1 remediation only. Production remains
**NO_GO** and MEM-6 scientific phase exit remains **BLOCKED**.

## Findings addressed

| Review finding | Remediation |
| --- | --- |
| M6-R01 — expected denial/fault could leave a clean safety score | `grade` now records explicit boundary mismatch and source-disclosure violations; every terminal status is checked against scorer-only expected status, with a narrow named no-memory abstention allowlist requiring unchanged state and no selection, packing, consumption or effect. `analyze` and `evaluate_decision` carry boundary mismatch counts as independent critical vetoes. |
| M6-R02 — supported runtime failures could shrink denominators | A pre-outcome support matrix is pinned in the run manifest. Structural unsupported reason/status must match it; supported unsupported rows stay in the paired denominator as failed outcomes and trigger safety/accounting vetoes. Reports expose requested, structurally eligible, started, terminal-completed and scored pair counts. |
| M6-R03 — no-memory wasted a call checking a missing hint | Protocol v2 preregisters `oracle_free_discover_apply_with_fenced_currentness`. No-memory uses `discover→apply` within the two-call budget. Memory arms retain the same final authority fence. The earlier +20 pp result is strategy-confounded and historical; it is not accepted as memory lift. |
| M6-R04 — command receipt stood in for Task B state | Task B now uses a distinct synthetic target and original intent, a bounded state/version transition, and a driver-owned read-back. The scorer binds target, task, intent, before/after state hash, revision, effect ID/count and authorization. Forged state, old intent, wrong target, stale revision, missing read-back, duplicate and aborted effects are negative cases. |
| M6-R05 — policy received a source-task handle | The policy receives frozen query/messages and a slot-based `current`/`discover`/`apply` facade. Source task, cohort, host and gold remain driver/scorer-side. Hostile inspection tests check public attribute, `dir`, `vars`, and reflected member access. This is an E1 scripted boundary, not a Python sandbox; any model-selected policy needs a serialized tool boundary. |
| M6-R06 — revision/dirty metadata was not verified | Runs bind Git commit/tree, the full research-input source snapshot, the input dirty bit and provenance digest. Historical replay verifies the recorded commit rather than requiring today's HEAD. A changed revision or dirty claim is rejected. |
| M6-R07 — canonical knowledge late-revoke/no-effect coverage was thin | The campaign now uses canonical `KnowledgeService`, `MemoryControlService`, `ContextBuilder` and repository seams for revoke before rank, after rank/before pack, and after pack/before consume; forget, source erase, expired evidence, changed grant/project epochs, owner/app/workspace/actor scope changes, and pending-proposal exclusion. Decision/canary/rollback tests snapshot settings and synthetic repository/lifecycle/effect state before and after. |
| M6-R08 — package inventory was incomplete | Package verification requires exactly nine indexed payload members plus `package.json`, verifies every indexed digest, rejects missing/extra/unindexed paths and symlinks, and retains predecessor source locks unchanged. |

The additive study identity is dataset `memory-longitudinal-study-v3`, protocol
`memory-longitudinal-protocol-v2`, and source lock v3. The v1/v2 locks and old
evidence remain unchanged. Current source-lock v3 SHA-256:
`10b46a3a08ef8123e882673b710e44e8d65580ab4bb1739ba8e4de9f3a99cfb0`.

## Corrected interpretation

The old lexical versus no-memory estimate (+20 percentage points on 25/48
eligible scenarios) is preserved as **pre-remediation, strategy-confounded**.
No-memory previously checked a missing current hint before discovery, consuming
one of two available calls. With the preregistered oracle-free `discover→apply`
baseline, lexical versus no-memory is **0 pp** (0 wins, 0 losses, 25 ties; fixed
descriptive interval [0, 0]). The matched scripted proxy therefore shows no
incremental action-quality lift. Topic versus lexical is -4 pp on 25 pairs
([-12, 0]); adaptive and full-history are 0 pp on their eligible subsets;
verified knowledge versus no-memory is 0 pp on eight pairs; tool lookup versus
verified knowledge is -100 pp on eight pairs under the shared call ceiling. No
threshold or hypothesis was changed after measurement. These remain author-visible
scripted outcomes, not model utility.

The corrected primary denominator is reported side by side: 48 requested
scenarios, 40 structurally eligible, 25 started pairs, 25 terminal-completed pairs,
and 25 scored pairs. The full grid retains 3,528 rows: 2,304 setup, 342 complete,
696 structural unsupported, 144 denied, 12 incomplete, ten cancelled, ten timed
out and ten expected interruption errors. There are zero safety failures,
unexpected supported-arm unsupported rows, boundary mismatches or unaccounted
supported outcomes. All 16 critical/campaign checks pass. The decision remains
**blocked** with `quality_threshold_not_met`; effective policy is unchanged and
live promotion is false.

Two independent fresh `make memory-research-eval` processes produced the same run
SHA `4e4ae79f3cc5805c7d1b3446a623ae9d8445ce058999b2169dcd260eb1ad839d` and semantic
SHA `4a42baf547556ec4dd51eff9e859cb200c24b77f5d9983aea30e2e5e5489efc3`. Both
packages replayed in fresh processes with `verified: true`. Their ignored local
package paths and package-index hashes are in the [machine-readable receipt](2026-11-04-longitudinal-review-measurements.json).
An unindexed-file tamper copy failed with `package_inventory_mismatch`.

## Verification

The runs used macOS 27.0.1 / arm64, Python 3.11.15, Pydantic 2.13.5 and pytest
8.4.2. The bound dependency lock is `backend/uv.lock` SHA-256
`43e6b75954501a599000b192fd0075073716e893eed01dfadcd544069735cb7a`. Source fixture
SHA-256 is `da7ccb44d7cf6076d33d4a14dfda04b2f907d5bb529fe05ee177bfc1abae8d6c`, scorer
SHA-256 is `69a3f4d91335ec3f72e9b8e5188b1cc221d7c5bd26bb72aaabff746fdf2dffeb`,
protocol SHA-256 is `00c70e86bf79cce7053dab9a98c30acf6839d102fbd411e66af91e2b8c008e11`,
and support-matrix SHA-256 is
`fe5e9c21108cb6b747870f531ed3cadf9da0318c8445bbe38c321e80fcf1c9c9`. Source
snapshot SHA is `4d9236a973e12432df9152406a3632a199be78a366d9351597318630c23bafc6`;
provenance SHA is `c30d8220908524c3b1018315fbd3a2d9ed0526066c3aa562f67a5500a34bf903`.
The run records revision `0289ac15bfa6b1267017d3ed55bce2134222aa36`, tree
`258f5a32355798d2ecde9a49abc61253b9f679db`, and `dirty=true` for the research inputs;
that dirty source snapshot is content-hashed and is included in the remediation
commit. Actual model tokens, billed cost, native resources and deployed latency
remain unobserved.

`make memory-research-check backend-lint naming-policy-check` passed: 111 focused
tests, Ruff, naming policy and its two unit tests. `memory-task-eval`,
`memory-knowledge-eval`, `memory-control-eval`, `memory-navigation-check`,
`memory-navigation-eval`, `memory-consolidation-check` and
`memory-consolidation-eval` exited 0; adjacent navigation and consolidation suites
passed 57 and 107 tests, and the control evaluation passed 36/36. `make planning-eval`
still exits 2 with the preserved `planning_baseline_changed_requires_new_version`
failure.

The first `make backend-test-offline` attempt stopped at collection because the SDK
source path was absent (`ModuleNotFoundError: personal_ai_sdk`). Retrying with
SDK/Checklist source paths collected 2,880 tests: 2,751 passed, one skipped, 36
failed, 92 errored, and 180 were deselected. The failures are unchanged PI-6 and
planning frozen-identity assertions; HTTP fixture errors cannot bind loopback
under this sandbox (`PermissionError`). No files for those inherited baselines were
changed. `PERSISTENCE_TEST_POSTGRES_DSN` is unset, so native E2 checks were not run.

No provider send, private data, database, cloud, external account, live flag or
production write was used. Full command outcomes, both package anchors, all
comparisons and remaining gates are retained in the
[machine-readable receipt](2026-11-04-longitudinal-review-measurements.json).

## Remaining gates

No offline code-level P0/P1 finding remains known. This does not close independent
blind E1 acceptance, native E2/source verification, real semantic comparison,
private/live E3 issuer and transport, deployed E4 forget/restore, or real-model
longitudinal E5 utility. The 12 author-visible challenge slots are not blind.
MEM-3 stays hard-disabled, MEM-4 proposals remain pending-only, other memory flags
remain default-off, and no policy is promoted. Production and scientific phase
exit remain **NO_GO / BLOCKED**.

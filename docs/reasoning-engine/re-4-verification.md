# Adaptive fixture verification — 2026-11-05

Implementation baseline `811ee3995ef8577514270b21d62eb399fe19cff3`, tree
`15351219f26cdade1e9261336400a5ed37e6936a`. The V1 finite and grounded
plans, frozen evaluator inputs and seals were retained. The [operator
contract](adaptive-selection.md) describes the default-off host and local
control. [ADR 0029](../decisions/0029-adaptive-fixture-selection.md) records
the execution and approval boundary.

## Sealed result

The [preregistered protocol](adaptive-experiment.md) ran 182 author-visible
synthetic cases, including 160 held-out cases, and 924 arm rows. There
were zero safety vetoes, zero shadow differences in physical work and no
extra simple-task work in the installed adaptive arm. Both fresh processes
produced semantic SHA-256
`d94c8b8aab6f582661035842b6353e511a8ac169f7a526ef3b5f09f397ac3253`.
Seal SHA-256
`b11768e98878eeee4b8f091c7338357bf8cfc102887d861a0c9f4d9df46d5064`.
Per-case quality, ledger, paired deltas and P50/P95 are emitted by
`make reasoning-adaptive-eval`. Timing is excluded from the semantic hash.

| Arm | Exact / all | Model | Verifier | Retrieval | Count | Work units |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| Finite baseline and shadow, each | 36 / 126 | 198 | 108 | 0 | 1,386 | 16.512365 |
| Finite adaptive | 54 / 126 | 162 | 144 | 0 | 1,134 | 13.997975 |
| Finite without family filter | 54 / 126 | 171 | 153 | 0 | 1,197 | 14.780680 |
| Finite without early exit | 54 / 126 | 171 | 153 | 0 | 1,197 | 14.794285 |
| Finite without alternative | 27 / 126 | 108 | 90 | 0 | 756 | 9.280055 |
| Grounded baseline and shadow, each | 21 / 56 | 35 | 28 | 70 | 406 | 7.518385 |
| Grounded one-shot ablation | 14 / 56 | 35 | 28 | 49 | 385 | 6.441225 |

Operation counts are dispatched fixture operations. Fault injections leave
18 unknown generation outcomes per finite baseline, shadow and adaptive
arm. The work calculation charges their reserved fake bytes. Provider
tokens, billing, quota, reservations and settlement are unknown in this
offline lane. The grounded one-shot comparison uses the same source and
maximum caps and retains citation verification.

Across all 112 held-out finite cases the candidate added 16 exact
completions. The paired difference was +14.3 percentage points, with a
scripted 95% bootstrap interval of +5.4 to +24.1 points. The eligible-only
difference was +20.0 points across 80 cases, with an interval of +6.3 to
+32.5 points. Mean net utility over all 112 cases rose by 0.163, with an
interval of 0.070 to 0.258. Decomposition won all eight held-out cases
in its favorable stratum, a promotion veto. Grounded one-shot lost all
six held-out focused-recovery cases and gained none across 48 pairs.
The fixture report is `OFFLINE_SIGNAL_ONLY` and `NO_PROMOTION`. These
results establish effects under the scripted arithmetic and citation
grammars.

## Commands

| Command | Result |
| --- | --- |
| `make reasoning-check` | PASS, 122 tests. |
| `make reasoning-eval` | PASS, 64 valid rows in the frozen lane. |
| `make reasoning-orchestrator-check` | PASS, 57 tests. |
| `make reasoning-orchestrator-eval` | PASS, 60 pairs. Frozen semantic hash `660e5130374a633d9ac5001293393d1950d5b99b6f694ec8e42840f7bcbc0db5`. |
| `make reasoning-grounded-check` | PASS, 77 tests. |
| `make reasoning-grounded-eval` | PASS, 60 cases and 180 rows. |
| `make reasoning-adaptive-check` | PASS, 68 focused tests. |
| `make reasoning-adaptive-eval` | PASS, two fresh runs of 924 rows. Python network fence recorded zero attempts. |
| `make reasoning-adaptive-rollback` | PASS, signed disposable pointer disabled at generation 2, repeat safe no-op, absent configuration safe no-op. |
| `make workflow-check` | PASS, 70 tests. |
| `make workflow-postgres-check` | FAIL, 56 passed and two failed in the final run. Both V1 cancellation assertions reproduced at the exact parent. The two new native adaptive tests passed. |
| `make backend-lint`, `make naming-policy-check`, `git diff --check` | PASS. Naming policy self-tests passed 2/2. Local links checked across eight changed documents. |
| Adjacent retrieval, context, auth, chat, inference, disclosure and usage command below | PASS on full rerun, 554 passed and 34 deselected. The first concurrent run passed 553 and failed one 20 ms retrieval timeout case. That case also passed alone on the exact parent and on this change. |

The native fixture ran PostgreSQL 17 with pgvector, UTF-8 encoding, normal
migrations, and a disposable Unix socket. The focused native run passed
six tests including two adaptive process exits and three grounded tests.
An earlier concurrent full native run also failed a timing-sensitive V1
process-exit case, which passed in the final full run and in isolation on
both revisions. The two remaining V1 failures expect one physical send
after queued or reserved cancellation. Both revisions observe zero sends.
No existing assertion was modified. The disposable server was stopped.

The adaptive receipt decoder lives under reasoning to avoid changing the
longitudinal memory experiment's locked dependency inventory. The 121
current inventory entries matched the exact parent byte for byte. The
adaptive seal pins the final module layout. No corpus, outcome, policy
threshold or scorer changed after the first holdout run.

```sh
LITELLM_LOCAL_MODEL_COST_MAP=True backend/.venv/bin/python -B backend/scripts/offline_test_runner.py \
  -q -m 'not loopback_http' \
  backend/tests/test_retrieval_{context,http,integrations,query_planning}.py \
  backend/tests/test_context{,_authorization,_builder,_planner,_provider,_routes,_runtime_composition,_sources,_traces}.py \
  backend/tests/test_auth.py backend/tests/test_inference_execution.py backend/tests/test_provider_usage.py \
  backend/tests/test_chat*.py backend/tests/test_memory_disclosure_authorization.py
```

## Evidence and unresolved gates

| Tier | Disposition | Evidence needed |
| --- | --- | --- |
| E0 | Local implementation and focused contract checks | Independent exact-commit review remains open. |
| E1 | Author-visible sealed synthetic observations, local pointer and native workflow fixtures | Independently authored blind holdouts, approved exact slice and resolution of the subgroup regression. Existing native cancellation assertions are open. |
| E2 | `BLOCKED_UNVERIFIED` for installed-model utility | Authorized real endpoint, held-out real-model tasks and measured token, quota and output evidence through the canonical path. |
| E3 | `BLOCKED_UNVERIFIED` for live sources/providers | PI-5 issuer-bound rights and atomic send permit, approved account, provider reservation and settlement, strict-free/quota proof and HXE-1/HXE-2 acceptance. |
| E4 | `BLOCKED_UNVERIFIED` for deployment and recovery | PI-7 private deployment, distributed revocation, monotonic restore and retained original-key/attempt evidence. |
| E5 | `BLOCKED_UNVERIFIED` for task utility | Independent matched-budget real tasks, resource-adjusted lift with a positive lower bound and no safety or subgroup regression. |

Grounded [release gates](re-3-blockers.md), PI/HXE acceptance and MEM
promotion remain separate. Production remains `NO_GO`. The external
coding-harness comparison is `NOT_RUN` because no independently
controlled comparator or authorized model/account was available. Local
review signatures in tests are disposable mechanical witnesses. No
independent approval or canary authorization ships in this change.

## Independent Sol High review handoff

Use the exact implementation commit containing this record. Review
[selection and features](../../backend/src/personal_ai/reasoning/adaptive.py),
[the V2 plan](../../backend/src/personal_ai/reasoning/adaptive_plan.py),
[control and evidence](../../backend/src/personal_ai/reasoning/adaptive_control.py),
[host binding](../../backend/src/personal_ai/workflow/adaptive.py), and the
[workflow](../../backend/src/personal_ai/workflow/service.py) together.

1. Reproduce both fresh semantic hashes and check split and oracle
   separation. Evaluate subgroup harm using independently authored
   blind tasks before considering any fixture approval.
2. Try forged scope, fixture binding, policy version, approval key and
   known-cost claims, including corrupted and stale local pointer writes.
   Verify that shadow makes no extra physical calls.
3. Crash or cancel each candidate boundary. Verify the exact child key,
   remaining reserve, uncertain accounting, V1 compatibility and
   terminal data cleanup. Exercise rollback during admission and recover
   an already admitted run with its pinned approval.
4. Try incomplete retrieval results and revocation after retrieval and
   final verification. Reproduce the native failures from the pinned
   parent and retain production and independent-acceptance gates.

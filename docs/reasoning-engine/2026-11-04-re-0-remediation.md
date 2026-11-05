# RE-0 independent-review remediation · 2026-11-04

**Disposition:** R01–R04 are addressed in the additive `reasoning-offline-v2`
local benchmark. This is a remediation receipt, not independent acceptance.
E2 remains unmeasured; native/E3/E4 and production remain blocked or NO_GO.

## Frozen and new identities

The historical v1 artifacts and sealed source were not modified:

- v1 manifest SHA-256: `2749b02f37b32571e913bbd2240942cfbe3e1032f424823e3f950219f6a888a9`
- v1 corpus SHA-256: `4b3815d5d23511d66e5089ca0cccc5c1c830097f597e55cd80be0d127741fc0b`
- v1 scorer SHA-256: `b23f2889528fd98898c93b0384cde3ccd66de72fdd6c476fadc11853748b9ad6`
- v1 driver SHA-256: `a40c00e30fda9b096efc3b227bd3005c7622c5a13e3a0bb1ea62f08c8ca65923`

The v2 manifest SHA-256 is
`5e10f3a456dc47687030344ed1554e522c8a5f895dc3075bb50fab7387456ea4`.
The v2 corpus is a separately versioned copy of the same 32 author-visible
synthetic cases. The source lock covers its corpus, contracts, driver, harness,
scorer, baseline, launcher and package marker. The literal manifest digest is
anchored in the v2 seal loader. The canonical semantic report SHA-256 from two
fresh processes was
`9c1335f421c00b36f863f7c55c2321d92a02d68358f5887c6bcf8cd8c8fb2ae2` in both
runs: 64/64 rows, four matched eligible numeric pairs and 28 retained
unsupported diagnostic rows. Pairing uses the same prepared-task digest and
one fake attempt per eligible arm. Native fencing remains unverified.

## Finding disposition

| Finding | Remediation and regression evidence |
| --- | --- |
| R01 input disclosure observer | The trusted harness records prepared source identities and compares them with the case's allowed slots before scoring. A metamorphic test injects the foreign source while preserving the correct `cedar` answer; the row receives a safety veto and cannot pass. Bodies are not emitted in the scored row. |
| R02 scenario-only denials | The fake gate records an attempted policy operation and observed denial reason. The scorer requires the expected attempt, gate result, source and operation; an empty neutral task cannot pass as a denial proof. |
| R03 verifier integrity | The scorer independently computes the closed sum/product oracle and compares it with the transient candidate and verifier result. Always-false and always-true checker canaries both make coverage incomplete. Check candidates are not persisted. |
| R04 checkout provenance | The baseline compares supplied commit/tree IDs with Git and checks the actual v2 source-directory dirty state against the supplied dirty label. Forged identities and a clean-label spoof of a dirty source tree are rejected. |

## Checks and limits

- `make reasoning-check`: 51 tests passed under the repository backend
  environment; the offline runner observed zero network attempts.
- Two fresh-process semantic replays: identical SHA above; 32 cases and 64
  rows, with 28 unsupported and four eligible matched diagnostic pairs.
- `make naming-policy-check`: passed (two policy unit tests).
- `backend/.venv/bin/python -m ruff check backend/src/personal_ai/evaluation/reasoning_v2 backend/tests/test_reasoning_v2.py`:
  passed.
- `PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint`: passed.
- `PATH="$PWD/backend/.venv/bin:$PATH" UV_OFFLINE=1 AI_PROVIDER=fake APP_ENVIRONMENT=test PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 make real-task-eval`:
  passed as an E1 fake evaluation; 36 synthetic rows, no live-model claim.
- The same offline environment with `make workflow-check` and
  `make memory-governance-check`: passed, 70 and 105 tests respectively.
- The same offline environment with `make planning-eval`: inherited
  `planning_baseline_changed_requires_new_version`; no planning lock or fixture
  was changed.
- `make backend-lint` without the repository virtual environment on PATH could
  not find `python`; the PATH-qualified command above passed.
- `git diff --check`: passed. v1 manifest/corpus/scorer/driver hashes above
  were recomputed from the checkout.

This local work does not measure real-model utility, paid cost, blind
generalization, native network isolation, physical dispatch/revoke races,
installed consumers, cloud behavior or production security. Those gates remain
outside this RE-0 remediation and production remains NO_GO.

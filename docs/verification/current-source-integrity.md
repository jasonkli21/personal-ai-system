# Current source integrity and verification results

Updated 2026-11-06. This report records the W0 source-identity repair and checks run on macOS arm64 with Python 3.11.15, CPython, `uv 0.11.13`, and the locked backend environment. The source changes were prepared from parent anchor `adb5b744a8a17bdc22e3953bfaa1903b927ce38c`. The exact implementation commit is the commit containing this report; the independent-review handoff explains how to resolve its SHA without introducing a self-referential hash.

## Identity diagnosis and additive repair

The inherited SDK suite had 367 passes, 25 failures, and 12 deselections. Twenty-four failures came from a frozen evaluator source/protocol identity mismatch; one came from the planning source digest. The earlier evaluator manifest expected core digest `edca874e3d9330468bd9ce5667a9f6a7e221806d3624b1275edf39fe8c6638c9`, while the audited source bytes computed to `380c0ef5b5c75d4b2dc3f76378e2cbe0db8e23c832c571237e27d3bb372c9d43`. Planning lock v35 expected `4eb58162ae39387382c18b524017886c1be4e4fc27de5203ac064f5c6e889cc9`, while its then-current source closure computed to `714f278f2cdc274ec6c76f9c478592299bdafa11a7e9e4aab616676ab3b57e88`.

| Contract | Prior frozen expectation | Prior recomputation | Current additive identity |
| --- | --- | --- | --- |
| Planning evaluator source | Lock v35, `4eb58162ae39387382c18b524017886c1be4e4fc27de5203ac064f5c6e889cc9` | `714f278f2cdc274ec6c76f9c478592299bdafa11a7e9e4aab616676ab3b57e88` | Lock v36, source digest `ed5a68424a2d0343fc5dca4c18fab76f9e1a111eff0cdc28022b5f56d864db08`; 558 normalized source entries |
| Offline information handling source | Generation 9, core digest `edca874e3d9330468bd9ce5667a9f6a7e221806d3624b1275edf39fe8c6638c9` | `380c0ef5b5c75d4b2dc3f76378e2cbe0db8e23c832c571237e27d3bb372c9d43` | Generation 10, core digest `4cc4d51e1116e7df61341cb560c49e3cb9ba3a58bf367a0ad99adc8f86ed6eae`; 544 core files, 4 consumer files, 1 host file |
| Frozen offline cases | Prior case digest | Same bytes after descriptive path migration | `25df654eda27040c3b52695fd6ec695b53238a7cf76b82e1ed4e5d442b55205d` |

The root cause was stale source identity after evaluator files and paths changed, compounded by a planning source closure that also includes the planning lock and evaluator tree. The repair defines deterministic closures and field-level path comparison, uses an additive planning lock first, then derives the new offline manifest after that lock exists. The offline closure excludes all versioned offline manifests from its recursive package digest, so neither identity hashes itself. Runtime fingerprints remain strict planning-replay provenance; portable source conformance does not compare machine-specific installed distributions.

Planning lock v36 supersedes v35 and retains its strict Python 3.11.15/macOS runtime fingerprint and non-promotion decision. Its `source_revision` is the reviewed ancestry anchor; exact source bytes are identified by the 558-entry map and aggregate digest. Offline manifest generation 10 supersedes generation 9, keeps frozen case and scoring identities, and records that prior measurements do not validate the new source identity. No new task-quality measurement is claimed. Planning locks v1–v35, offline manifests before generation 10, frozen corpora, scorers, thresholds, and earlier decisions remain historical evidence.

The same additive rule now protects adjacent identities: the longitudinal memory source lock v5 supersedes v4 while preserving v1–v4; reasoning source identity v2 supersedes v1; adaptive developer conformance v2 supersedes v1. Each old manifest remains byte-preserved, and none of its measurements is rebound to the new source paths.

## Current-source check and controlled proposals

The read-only check validates active planning and offline identities, schema and source-closure versions, exact source maps, unchanged case identity, predecessor relationship, changed protocol list, and clean status for bound files. It does not execute a benchmark or update a lock.

```bash
make source-contract-check
```

The direct command is:

```bash
backend/.venv/bin/python -I backend/scripts/source_contract_check.py --check
```

To review a candidate without writing it, use one of the explicit proposal modes:

```bash
backend/.venv/bin/python -I backend/scripts/source_contract_check.py --propose-planning
backend/.venv/bin/python -I backend/scripts/source_contract_check.py --propose-offline-benchmark
```

To write a candidate, specify only the next versioned target with `--output`; the helper refuses an occupied path. Finalize source and selectors first, write the planning candidate, then derive the offline candidate so it includes the planning lock. Review the complete diff and change summary before commit. Never replace prior locks or manifests. After commit, run the read-only check from a clean checkout.

## Verification results

| Gate | Result | Evidence and limits |
| --- | --- | --- |
| `make backend-lint` | **PASS** | Ruff checks passed. |
| `make naming-policy-check` | **PASS** | Active source, tests, commands, configuration, current docs, experiment guides, and stabilization guides scanned; 4 naming-policy regression tests passed. |
| `make sdk-check` | **PASS** | 402 passed, 12 deselected by the target's loopback marker selection; forbidden network attempts: 0. The inherited 25-failure cohort is resolved. |
| `make backend-test-offline` | **PASS** | 3,332 passed, 1 skipped, 204 deselected by the target's persistence/cloud/manual-test filters. The run used the source SDK and reference consumer import paths and authorized local loopback for signed HTTP fixtures. |
| `make consumer-contract-check` | **PASS** | Consumer partitions: 142, 190, 56, and 192 passed; 1 skipped; no network attempts. Installed probes and cleanup completed. |
| `make offline-benchmark-check` | **PASS** | 59 tests passed. The check executed all 68 expected synthetic arms, coverage was valid, no safety veto occurred, native remote denial passed, and forbidden Python network attempts were 0. The core-only wheel probe correctly remained ineligible; installing the declared client and host wheels yielded valid 68/68 coverage. This verification output is not sealed as a new task-quality measurement. Promotion remains `not_promoted`. |
| `make sdk-install-check` | **PASS** | SDK and Checklist wheel/sdist builds and isolated installs passed. |
| `make synthetic-reasoning-check` and `make synthetic-reasoning-install-check` | **PASS** | 3 focused tests passed; installed SDK consumer built and ran against loopback, then completed its probe and cleanup. |
| `make release-profile-check` | **PASS** | 10 tooling tests and 15 artifact tests passed. This is profile tooling evidence, not release approval. |
| Reasoning capability suite | **PASS** | `reasoning-check`: 123 passed; orchestrator: 57; grounded: 77; adaptive: 75; synthetic preview: 3. Adaptive conformance passed with `NO_PROMOTION`; historical replay covered 182 cases and 924 rows, also `NO_PROMOTION`. |
| Adaptive evaluation | **PASS / BLOCKED_UNVERIFIED** | 1 passed and 68 unavailable cases deselected; replay integrity passed. Live gates remain `BLOCKED_UNVERIFIED`. |
| Memory capability suite | **PASS** | Episode: 93; consolidation: 107; navigation: 57; research: 112; governance: 105 tests passed. Memory governance was also run independently: 105 passed. |
| `workflow-check` | **PASS** | 70 passed. |
| `make planning-eval` | **PASS / NO_PROMOTION** | Strict current runtime check passed; the quality-case denominator was zero, so it produces no quality or promotion evidence. |
| `make source-contract-check` | **PASS** | Run after commit from the clean local checkout and from a fresh clone; active planning and offline identities matched. |
| Workflow YAML, modified-document links, and whitespace | **PASS** | Ruby YAML parser accepted `.github/workflows/quality.yml`; relative links in 80 modified Markdown files resolved; `git diff --check` passed. |
| Native PostgreSQL integration gates | **BLOCKED_UNVERIFIED** | No disposable test DSN or Docker executable was available locally. Workflow, episode, consolidation, navigation, migration, and recovery PostgreSQL checks were not run. CI now provisions a disposable pgvector service for its integration lane. |
| Hosted CI, independent review, providers, cloud, production, external-source sends, restore and physical erasure | **NOT RUN / BLOCKED_UNVERIFIED** | No push, paid/live provider call, cloud operation, external disclosure, or production action was authorized or performed. CI definitions were validated locally but no hosted workflow run occurred. Independent review remains pending. |

Python emitted the upstream support-window warning for Python 3.11.15 and a Starlette/httpx deprecation warning. These warnings did not fail the local gates. The full offline test's 204 deselections are target-level exclusions, not passing results for the excluded native/cloud suites.

## Acceptance boundary

The local source repair is **READY_FOR_INDEPENDENT_REVIEW**. It is not independent sign-off, hosted acceptance, or production readiness. Production remains `NO_GO`; provider, identity, native database, cloud, distributed restore, physical deletion, external-source, and E2–E5 acceptance gates remain open or `BLOCKED_UNVERIFIED`. Reasoning adaptation is not promoted, and experimental memory, workflow, source disclosure, and reasoning capabilities remain default-off wherever their owning contracts require it.

See [the independent-review handoff](independent-review-handoff.md) for commit resolution, reproduction commands, changed-path inventory, and reviewer checks.

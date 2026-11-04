# Memory longitudinal research implementation — 2026-11-04

**MEM-6 status: IMPLEMENTED_E1_RESEARCH / PHASE_EXIT_BLOCKED. Production: NO_GO.**

The owner's request authorized implementation and one commit, with no subagents.
All work was performed in this session. The bounded offline scope follows the
[hardening decision](2026-11-04-longitudinal-hardening.md) and
[ADR 0026](../decisions/0026-offline-memory-research-custody.md).
No production factory, route, flag, migration, source issuer, episode reader,
provider transport, scheduler or memory writer was added. Nothing was pushed,
deployed or promoted. Existing unrelated untracked plans are excluded from the
commit. The tested source is parent revision
`619d724bd91d9f633714b576a3fef8e7a8841b6d` plus the source-hashed working tree
contained in this implementation commit; receipts honestly record `dirty=true`.

## Implementation

- `memory/research/experiments/contracts.py` supplies bounded versioned dataset,
  task, model, policy, environment, protocol, run, receipt, report and decision
  contracts. Portable receipts contain opaque synthetic identifiers and aggregate
  observations, without raw prompts, personal text, source bodies or credentials.
  A protocol-only model manifest is inert; executable runs reject non-scripted
  model spaces. Host environment flags do not configure this synthetic study.
- `artifacts.py` provides bounded canonical JSON/SHA-256 identities, exclusive
  immutable writes, complete-grid validation, source verification, package
  integrity and append-only decisions. Duplicate keys, deep/oversize input,
  unknown schemas, conflicting receipt IDs, missing attempts, source drift and
  environment/model mismatch fail closed. Failed evidence cannot be renamed to
  bypass vetoes; new evidence links the prior failure. The chain is bounded to
  128 records and has no automatic pruning or native durability claim.
- `decisions.py` provides pure decision, canary and rollback functions. Custody
  and independent review require separate trusted host inputs; imported metadata
  cannot self-attest. Any failed/unknown critical gate vetoes quality. Canary
  stages/stop conditions/monitors cannot be lowered. Neither a positive proposal
  nor rollback performs an effective write. No independent reviewer issuer is
  installed in this package.
- `evaluation/memory_longitudinal/` supplies the sealed source-only loader,
  stateful driver, isolated scorer, fault campaign, source locks and CLI. Scoring
  observes new terminal state under stable original intent keys; historical
  actions and setup receipts are excluded from task-quality scoring. Retry
  reconciles the original effect instead of creating another. Invalid attempted
  actions are separately counted and vetoed, even when the domain tool rejects
  them before an effect.

The additive corpus has **48 distinct author-visible cases**, eight in each of
six families, with **at least three steps and separate simulated sessions in every
case**. Splits are 24 development, 12 author-visible validation and 12 author-visible
challenge slots. All splits were inspected. External challenge packages of 12–96
tasks have a strict import/custody interface, without automatic trusted-source
installation or independent-authorship certification. Shared templates, a small
correlated sample and an authored scorer limit any scientific interpretation.

There are twelve requested arms. Navigation compares sealed fixture records using
the existing lexical/topic/adaptive engine and canonical ContextBuilder. Eight
canonical source-cohort cases independently exercise KnowledgeService admission,
MemoryRetriever selection, MemoryControlService read, builder packing and final
KnowledgeService.consume. Cross-schema adapters are not invented. Legacy fixed
cannot represent these project facts; real semantic/hybrid/rerank have no genuine
embedding adapter; pending consolidation's sealed extractor cannot accept these
sources or approve proposals. Their unsupported rows remain in every denominator.
The existing consolidation evaluation was separately run as pending-only diagnostic
coverage over its own supported corpus.

## Measurement and retained evidence

The protocol was author-locked before the measured run: primary lexical versus no
memory, five descriptive secondary contrasts, identical query/rights/time/tool/
context ceilings, two repetitions, fixed bootstrap seed 719 and 1,000 percentile
scenario-cluster samples. The two-call task budget includes explicit memory-tool
lookup, and the 1,024-word-estimate memory / 4,096 total context ceilings apply to
full eligible history. Setup and repetitions do not inflate the independence unit.
No inferential significance claim is made.

The initial source generation and receipts remain immutable. Self-review then
strengthened fresh-package verification to recompute metrics, human reports,
decisions and blocked plans, including five malicious packages that recompute
their own hashes. This creates **an additive second source generation**, with the
same corpus, scorer, protocol and semantic outcomes. The first lock is retained
unchanged and checked by its successor. The original package passed fresh-process
verification before this hardening; current-code verification appropriately rejects
its older source identities. This is source drift, not a new blind utility study.

Final package:
`artifacts/memory-research/a7f60636f3fd7b6a693941e401607536d1b350a6f8b23d8fb0a23c80ef1a1656/80bb886850ee443285e9b128f63f901b/`.
The retained [machine-readable evidence](2026-11-04-longitudinal-measurements.json)
includes report, exact unsupported/status counts, per-arm resource observations,
model/environment manifests, package-index anchor and both generation identities.

- Final run: `a7f60636f3fd7b6a693941e401607536d1b350a6f8b23d8fb0a23c80ef1a1656`.
- Semantic digest, both generations and both repetitions:
  `f99823a9ae8c67011d2fa28112895e54798122c9e0adfccf2b9d1390370991dc`.
- Final source lock: `4a19369b4eb997b3dbda7a37f1febd9a2e8e5165a1cc53c6a2584b1ada92d95f`.
- Package-index anchor: `98af52dbdb7b501e470554e431306fd1358a6a5e409143b24fdf7e52e5ae5e41`.
- **3,528 attempted rows**: 2,304 setup, 342 complete, 696 unsupported, 144 denied,
  12 incomplete, ten cancelled, ten timed out and ten intentional interrupted-refresh
  errors. The fault errors are explicit expected outcomes, not completed task wins.
  All eleven critical campaign groups pass; there are zero reported invariant
  violations, rejected unsupported actions, provider calls or duplicate target effects.

| Contrast | Eligible scenarios / 48 | Wins / losses / ties | Delta percentage points | Descriptive 95% interval |
| --- | --- | --- | --- | --- |
| Lexical vs no memory | 25 | 5 / 0 / 20 | +20 | [4, 36] |
| Topic vs lexical | 24 | 0 / 0 / 24 | 0 | [0, 0] |
| Adaptive vs lexical | 25 | 0 / 0 / 25 | 0 | [0, 0] |
| Full history vs lexical | 23 | 0 / 0 / 23 | 0 | [0, 0] |
| Verified knowledge vs no memory | 8 | 6 / 0 / 2 | +75 | [37.5, 100] |
| Tool lookup vs verified knowledge | 8 | 0 / 8 / 0 | -100 | [-100, -100] |

The lookup regression is retained: spending a call on lookup leaves insufficient
budget for both the mandatory current read and action. It is an E1 resource-parity
negative control, not a claim that memory tools are generally harmful. Full-history
overflow and topic page caps exclude affected pairs explicitly; unsupported arms
have no measured quality, rather than zero utility.

Index peaks are 10,805 serialized bytes for indexing arms and zero for no-memory,
fixed, canonical and pending-only arms. Synthetic local p95 row latencies range
from about 1.39 to 5.42 ms in this invocation; machine-readable receipts include
setup and unsuccessful work, stage timings, maintenance and estimated tokens.
Retained bytes count serialized synthetic knowledge and derivative indexes, not
RSS/native storage. Corpus bytes are common pinned inputs. Actual model tokens,
billed cost, native resources and deployed latency remain **null/not observed**.

The resulting decision is **needs_independent_review**, with
`independent_review_missing`. The generated canary request is blocked and rollback
is a dry-run identity/retention plan. No proposal is effective. All evidence is
E0/E1 public/synthetic; there is no independently blind cohort, real-model task
utility, native durability, hosted rights/cost, physical send, cold restore or
private-data erasure proof.

## Verification

Commands use the pinned backend virtualenv (Python 3.11.15, Pydantic 2.13.5,
pytest 8.4.2, arm64 Darwin). `PATH` starts with `backend/.venv/bin`.
The full-suite source-path invocation additionally supplies SDK/Checklist sources
through `PYTHONPATH`; this is source-tree coverage, not installed-wheel proof.
Exact command outcomes are recorded in the verification table completed below.

## Independent review and remaining gates

The [blocker registry](2026-11-04-longitudinal-blockers.json) names owners, required
evidence and re-entry tests. The [source drift proposal](2026-11-04-longitudinal-source-proposal.json)
preserves frozen planning/compatibility identities; it is not acceptance.

Review should try to falsify, in order:

1. **Authority and leakage:** `LongitudinalAuthority`, `KnowledgeCohort.pack`,
   `consume_knowledge`, `run_policy` and the scorer-only loader. Attempt current
   grant/source mutation after rank, pack and immediately before use; verify no
   gold/canary marker reaches policy input and no current hint becomes memory authority.
2. **Custody and vetoes:** `verify`, `validate_grid`, `evaluate_decision`,
   `plan_canary` and `append_decision`. Delete/duplicate rows, forge terminal effects,
   rewrite all package hashes, self-certify review, rename failed evidence and lower
   canary gates. Use the focused tampering and broken-scope-control tests as reproducers.
3. **Scientific validity:** `paired`, `grade` and the source/scorer fixtures. Check
   matched information and budget, scenario independence, final-step aggregation,
   expected faults, negative controls and all unsupported denominators. Challenge
   whether these small closed action proxies generalize at all; no real utility
   or phase-exit acceptance is claimed.
4. **Resources and operational limits:** attempt corpus/term/card/artifact/ledger
   overflow, interruption and fresh-process replay. Verify the resource scopes,
   unchanged runtime defaults and retained forget authority. Native/deployed tests
   require separate infrastructure and approval; synthetic passes cannot close them.

Reproduce using `make memory-research-check memory-research-eval` and then
`make memory-research-replay MEMORY_RESEARCH_PACKAGE=/absolute/package/path`.
The package contains no private-source or model dispatch path. Any later real
trial or effective promotion needs separate source/permission, resource, independent
review, owner and release authority; no safely independent E1 work was deferred
for those external gates.

## Recorded command outcomes

`make` exits 2 when an invoked recipe fails; pytest's underlying failure code is
1 (collection error is 2). Retained local logs are under
`artifacts/memory-research/verification/`; the machine-readable evidence above is
committed. Provider/emulator/cloud/production checks were not run.

| Command / configuration | Exit | Outcome |
| --- | --- | --- |
| `make memory-research-check memory-research-eval` (final generation) | 0 | 91 tests pass; 3,528 rows; two equal semantic repetitions; zero reported safety violations; no transport |
| `make memory-research-replay MEMORY_RESEARCH_PACKAGE=<final absolute package>` | 0 | Independent fresh process validates source/grid/scorer/summary/decision/plan custody and repeats both runs with the same digest |
| `make memory-task-eval memory-knowledge-eval memory-control-eval memory-navigation-check memory-navigation-eval memory-consolidation-check memory-consolidation-eval` | 0 | Existing baseline/knowledge/control studies pass; navigation 57 tests and 400 retained attempts with its unchanged v2 digest; consolidation 107 tests and existing proposal/quality studies pass |
| `make backend-lint naming-policy-check` (final code) | 0 | Ruff passes; naming policy passes, including two checker unit tests |
| `make backend-test-offline` with bare environment | 2 | Initial collection error: SDK is not installed; no suite PASS claim |
| `make backend-test-offline` with SDK/Checklist source paths, sandboxed | 2 | 2,726 pass, one skip, 36 failures and 92 socket setup errors; 180 deselected. Local bind denied; pre-custody-hardening source generation |
| Same full offline suite with source paths and allowed synthetic loopback binding (final code) | 2 | **2,834 pass, one skip, 26 failures**, 180 deselected, no socket setup errors. Twenty-five failures are PI-6 `frozen_protocol_mismatch`; one is the frozen planning source-identity assertion |
| `make planning-eval` | 2 | Inherited `planning_baseline_changed_requires_new_version`; historical identity unchanged |
| `make memory-navigation-postgres-check` | 2 | **BLOCKED before DB contact**: no disposable `PERSISTENCE_TEST_POSTGRES_DSN` |
| Changed Markdown local-link/content checks and `git diff --check` | 0 | Links resolve and no whitespace errors; completed before commit |

The loopback retry was automatically approved as a local synthetic test run; it
created no production counterpart or native-persistence acceptance. The full suite
still fails, and this change does not weaken its gates. To distinguish baseline
failure from this additive source change, the original HEAD's core tree was
recomputed directly from a read-only `git archive HEAD`. Its PI-6 digest already
mismatches `manifest-v2-source-9.json`. The exact frozen, original-HEAD and final
working identities are retained in the source proposal. No historical PI-6 or
planning manifest was edited. SDK source paths establish source-tree coverage only.

Final focused runs emitted two upstream Google Python-version support warnings.
The full suite emitted four upstream deprecation/type-generation warnings. These
were not suppressed. Local timings are environment observations, not external
latency or performance acceptance.

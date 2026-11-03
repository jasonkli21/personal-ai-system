# PI-6 conditional offline implementation and review closure — 2026-11-02

**Current disposition:** R01–R11 remediation complete; the user directed that
no further review is required for this scope. The local v2 evaluation covers
all 68 expected rows in both source and full installed-wheel runs. PI-5 remains
`blocked_unverified`; PI-6 production promotion remains `no_go`.

The sections below preserve the c22c646 implementation report and its historical
test iterations. The final review remediation, tests and identities are recorded
in [Review remediation completion](#review-remediation-completion) and the
[verification ledger](pi-6-verification.json). No independent acceptance is
claimed; none is required to close this scoped review per the user's direction.

The user authorized the handoff's bounded offline sequencing exception. The
[entry decision](pi-6-conditional-entry-decision.md),
[hardening/preregistration](pi-6-plan-hardening.md) and
[contract](pi-6-benchmark-contract.md) were written before code. There were no
historical PI-6 plan/prompt files in this checkout. The preserved user handoff
supplies the original scenario matrix; the [revised plan](pi-6-detailed-implementation-plan.md)
adds a separate offline interpretation without passing predecessor obligations.

## Source and changes

Start and end HEAD are `093e3b6816581e0b975e74e498dab99a2ac9a4b6`, parent
`6056a9c9f18750d2044e2fd47bc5ca67fb16633b`. No commit, push or PR was created.
Initially tracked files were clean; the sole untracked user file was
`docs/platform-independence/pi-6-conditional-offline-development-codex-handoff.md`.
Its bytes are unchanged. Final work remains a dirty additive candidate, with exact
paths/hashes/status in the ledger and a local patch at `artifacts/pi6/implementation.patch`.
All 52 captured predecessor fixture/lock/dependency/input hashes are preserved.
Root/backend setup was checked; `backend/README.md` does not exist in this checkout.

The old PI-5 verification source map has 595 matching files, no missing files,
and five differences: the already-present R05 route/test fix, plus this phase's
Makefile and planning evaluator/test identity change. Old review results are not
attributed to this candidate. Original absent workstation inputs remain a P5-28
ownership blocker; hashing this session's input cannot prove their ownership.

New implementation files:

- `evaluation/pi6_contracts.py`, `pi6_scoring.py`, `fixtures/pi6/`: strict bounded
  input/observation contracts, frozen 32-case corpus/scorer/split identity and
  exact outcome/fact/citation grading with noncompensatory vetoes.
- `evaluation/pi6_http.py`, `pi6_driver.py`, `pi6.py`: real signed HTTP app/auth,
  existing API/context/chat/local retrieval, MEM-2 controls and research-v1
  service composition; fake I/O only; isolated state and content-free observations.
- `scripts/pi6_checks.py`, `pi6_installed_checks.py`, `tests/test_pi6.py` and
  `make pi6-check`: native/Python fences, adversarial contract/privacy/scoring
  checks, packaged core/HTTP probes and reproducible measurements.
- Additive planning v26 and its source-preservation regression; documentation,
  gates, benchmark/verification and a standalone independent-review prompt.

No production API, schema/migration, policy/feature default, provider adapter,
SDK dependency, memory semantics or historical fixture/threshold is changed.
All runtime code is under evaluation; routes/services remain their existing owners.
Optional Reading Logbook imports are deferred until its example task runs; core
installation and fixture validation work without that optional client/host.

## Architecture and eligibility

The public consumer never imports platform internals. The trusted test host
composes `create_app`, a real signed JWT verifier with fake signing-key transport,
exact client/app/workspace policy, existing repositories as I/O fakes, the normal
API assembler/planner/packer and matching offline generation/count pair. The
scripted generator reads only packed messages; it has no fixture oracle, imports,
URLs, side-effect tools or live provider path. Active-branch editing uses the
builtin authenticated public API because external consumer policy correctly
denies that operation. External context inspection likewise returns policy 403;
R05 is separately exercised by source-aware route tests.

Profile grants go through the builtin owner API and exact destination/purpose/
whole-profile revision checks. Baseline source selection is ablated; grants/facts
remain matched. Local retrieval uses actual source snapshots and retained
permission dependencies, exact citation IDs, public standalone retrieval and the
registered read-only tool. External model attachment remains inaccessible.
Temporary synthetic operator files are disposed with each case and never copied
into observation artifacts. Memory tasks use the existing local control service;
research uses actual research-v1 synthesis/validation with fake source/LLM I/O.

Physical P19 accounting is not part of the admitted fake profiles. Adding a
second evaluator ledger or disguising fake sends as provider attempts was rejected.
The runner marks reservations, settlement and live quota/cost unknown; inherited
P19/P21 negative tests are a separate evidence class. No arbitrary external
provider, scoring import, path, URL, tool registry or fallback is fixture-selectable.
The eligibility table is in preregistration and canonical observations.

Two bounded configuration variants are source selection and compact research
packing. Fake profile identity comparison is plumbing only. Each case/arm receives
new state, cache, journal, profile and HTTP host. Fixed relative authority epochs
support deterministic transitions; HTTP tokens use a captured wall-clock epoch.
Same corpus/scorer/contract hashes bind calibration and held-out execution.

## Measurements and limits

The [benchmark report](pi-6-benchmark-report.md) and
[canonical machine report](pi-6-benchmark-report.json) contain 68 observations:
64 paired-arm records and four standalone controls. Sixteen held-out pairs give
2 wins, 14 ties, 0 losses; baseline succeeds 14/16, candidate 16/16. No final safety
veto. This is scripted source availability, not real-model task lift. Templates
are shared across some source/lineage groups and families; the small corpus does
not justify a statistical confidence interval or population claim. Uncertainty
is inconclusive and all policies remain not_promoted.

Fake input bytes, estimated output, local latency and synthetic monetary zero
are explicitly separated from unknown real tokens/quota/USD. There is no real
model, live latency/free-tier/billing, deployed Google identity, private IAM,
native distributed source/attempt authority or deletion/restore evidence.
Held-out memory denial controls do not establish correction utility; long-context
branch selection does not establish summary quality. Those limits remain in
force after this review closure; the measured counts do not support broader claims.

## Verification and preserved failures

The [machine ledger](pi-6-verification.json) owns exact commands, durations,
exit codes, warning summaries, source/fixture/artifact hashes and all 33 scenarios.
Preflight R05: 17 passed under native deny-network; initial PI-5: 147 native/Python
and 34 signed HTTP passed. Initial workspace socket/sandbox failures were local
execution restrictions; approved reruns retained the repository's network fences.

Implementation lint initially caught SIM117/F841 and import ordering; these were
fixed and final Ruff passes. Calibration bringup corrected a synthetic auth-domain
configuration, resolved trusted temporary paths (without weakening the production
symlink guard), used the builtin branch-edit API where external policy denies it,
handled failed SSE completion, and applied the registered research caps. No
fixture/scoring threshold or production guard was relaxed for those corrections.

The first compatibility run overlapped additive implementation. PI-3/4 and
PI-2/platform/planning checks failed the expected v25 source lock. A full
moving-source run had 2260 passes and two failures: v25 identity and MEM-0's
`inputs_changed_during_evaluation` guard. Do not call these final-source passes.
No historical lock was rewritten. These runs did not isolate the old lock against
the pre-code R05 base, so the failure is not attributed solely to PI-6: R05 also
changed bound source and advanced the revision beyond the old lock. Planning v26
explicitly binds the current R05 base plus new PI-6 source,
preserving old configuration/corpus/rubric/thresholds and v10–v25 bytes. The
current-source assertion moved to v26; the v25 test still verifies its exact
historical digest and semantic predecessor identity.

The first PI-6 measurement passed 35 adversarial tests but produced four
conservative false vetoes on an empty required source. The exact driver
normalization was fixed from the calibration case and regression-tested; frozen
scoring/corpus bytes were not changed. Its original report/source hash remain in
the ledger and local artifact. Final PI-6 passes 37 adversarial tests and reports
zero forbidden Python network attempts with native remote denial proved.

A pre-final stable-source checkpoint passed 2264 no-network backend tests. The
first exact full Make target had 2365 passes and one settings-example failure:
this session's sanitized environment explicitly set `AI_PROVIDER=fake`, which
correctly overrode the example file's expected `gemini` value. The test and
production settings were preserved; the final canonical rerun uses a minimal
credential-free environment without that override and retains the native fence.

Self-review also strengthened the forget task oracle: an empty read is no longer
sufficient. It now requires the actual applied mutation result bound to the
operation ID and invalidated source dependency. A failure-plus-unavailable-read
regression prevents false success. Corpus/scorer bytes remain frozen; the v26
source binding and all affected final checks were refreshed. Checkpoint results
remain separately labeled and are not attributed to the final driver.

Final checks use stable implementation source. Canonical PI-3/4 passed 787/897
with zero forbidden Python network attempts. The installed PI-6 core-only and
separate Reading Logbook probe passed: 64 observations, 58 task successes,
no safety veto, reference apps physically absent, offline no-index installation,
native loopback-only HTTP. Remaining final command details are recorded directly
in the ledger; no earlier result is silently substituted for a final check.

| Final command | Result / evidence class |
| --- | --- |
| `make backend-test-offline` under native loopback-only fence, minimal credential-free environment | **2367 passed, 119 deselected**; exact Make target including HTTP tests |
| Explicit offline pytest excluding loopback/native/cloud/manual suites under native deny-network | **2265 passed, 221 deselected** |
| `make pi6-check` | **37 passed**, 68 observations, 16 held-out pairs, zero vetoes and forbidden Python attempts; native remote denial proved |
| `make pi5-check` | **147 native/Python + 34 signed HTTP passed**, zero forbidden Python attempts |
| `make pi3-check`, `make pi4-check` | **787 / 897 passed**, zero forbidden Python attempts |
| `make pi2-check`, `make platform-independence-check` | **Passed**, built wheel/sdist, installed core/reference/retained-task/public consumer and uninstall/absence probes |
| `make planning-eval`, `make retrieval-eval`, `make research-eval` | **Passed**, synthetic/offline; no promotion |
| `make memory-task-eval`, `make memory-control-eval`, `make memory-knowledge-causal-eval` | **Passed**, existing local memory proxies |
| Focused R05/provider-matrix/Phase35/36 command | **96 passed** under native deny-network |
| `backend/.venv/bin/python backend/scripts/pi6_installed_checks.py` after final builds | **Passed**, core-only plus 64 signed HTTP observations, 58 successes, no safety veto, no reference apps; native loopback-only |
| `make backend-lint`, `git diff --check`, source/content/link checks | **Passed** |

Native-store/cloud suites and the two manual provider suites remain deliberately
excluded. Runtime is the pinned macOS arm64 / CPython 3.11.15; no Linux/Python
alternate was relabeled canonical. There are no outstanding final local failures;
the earlier failures above remain preserved evidence.

Warnings are the inherited Google Python 3.11 support notices, Starlette/httpx
TestClient deprecation, and Pydantic TypedDict ReadOnly warning where exercised.
They do not establish Python 3.12 compatibility or cloud/provider acceptance.

## Self-review, remaining gates and rollback

Same-session self-review inspected auth/source/current-key boundaries, literal
citation/factual grading, split/denominator limitations, missing versus zero cost,
redaction/emit/exception paths, temporary-state isolation, tool effects, package
isolation, historical hash preservation, provider SDK/dependency creep, and hidden
transport/fallback paths. The disabled external path remains uncallable by task
inputs. Native/Python and installed/source evidence classes stay separate.
This is a local remediation closure, not an independent review or proof of
real-model injection resilience. The user directed that no further review is
required for this scoped work.

Mandatory PI-5 F01/F02/F03, P5-04/11/14/19/22/26/27, P5-24 independent canonical/
causality evidence, P5-28 absent-original-input ownership and independent
acceptance remain open. P6-02/29 are blocked_deferred; P6-15/32 production
obligations remain blocked_deferred; local partial rows preserve external gaps.
The [PI-6 gate](pi-6-completion-gate.md) records local evaluation completion
and production denial. The [review closure](pi-6-review-closure.md) records that
no further review handoff is requested.

Rollback disables/removes PI-6-only runner/config and retains PI-5 guards,
receipts/tombstones and historical locks. No destructive cleanup or down migration.
No PI-7 or MEM-3+ work, real provider/search/cloud/billable request, deployment,
production-data access, database restore or physical deletion was performed.

## Review remediation completion

R01–R11 are addressed in the evaluator and covered by focused regressions. The
closed observation schema requires positive factual/source proof; effect counts
come from the isolated observer; coverage requires every predeclared arm; and
each operation has a hard five-second deadline with a fixed 300-second suite
limit and enforced source/input/output caps. Memory revocation runs the same
protected read on both arms and recall checks content and current dependency.
Runtime identity no longer requires Git or a source checkout. The installed
probe executes the full evaluator from the installed core and optional wheels.
Native fencing is verified in each measured worker; logging and output capture
are bounded inside that killable process.

V1 corpus, manifest and prior observations remain unchanged. V1 held-out content
was exposed during development and is historical only. V2 uses a new 32-case,
agent-authored synthetic corpus frozen against the full protocol before its final
run. It is not blind or independent validation. The first v2 run with 13
evidence-incomplete arms is preserved separately. The final source and full
installed-wheel runs each recorded 68/68 expected arms, complete coverage and
zero safety vetoes. The core-only installed run correctly marked 52 optional
host-dependent arms ineligible.

Final remediation verification on the canonical macOS arm64 / CPython 3.11.15
environment includes: 54 focused PI-6 tests passed; `make pi5-check` passed its
147 native/Python tests and 34 signed HTTP tests; `make pi3-check` passed 788
tests; `make pi4-check` passed 898 tests; PI-2 and platform-independence package
checks passed; the full native loopback-fenced offline backend suite passed
2,385 tests with 119 deselected; planning, retrieval, research and memory
evaluations exited successfully without promotion. The exact commands, warnings,
wheel hashes and intermediate failures are in the [verification ledger](pi-6-verification.json).

The user explicitly closed this scoped remediation without a review handoff and
directed that no further review is required. This closure records local
implementation evidence; it does not convert synthetic results into live-model,
independent fixture, cloud, distributed authority, PI-5 completion or production
evidence. See the [review closure](pi-6-review-closure.md) and
[current gate](pi-6-completion-gate.md).

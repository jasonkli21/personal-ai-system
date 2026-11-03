# PI-6 plan hardening and preregistration — 2026-11-02

Written before runtime/evaluation code and held-out measurement. Scope is the
[conditional entry](pi-6-conditional-entry-decision.md). W0–W5 are one implementing
session without delegation. Requested model is Sol / High; the session cannot
independently attest the hosting model setting and makes no model-identity claim.

Architecture: reuse `create_app`, verified JWT middleware, public Reading Logbook
client, API dependency composition, planner/packer/counter, `ChatTurnService`,
retained source snapshots, local retrieval index/tools/journal. Synthetic ports
replace persistence, signing-key transport and generation only. Reuse existing
MEM-2 `ControlRuntime` and research-v1 `measure` service composition for bounded
control/citation tasks; neither becomes a new policy engine. Explicitly isolate
state per arm and restore all environment/catalog/transport patches. Clock is
fixed for memory/research; HTTP identity uses a captured epoch with deterministic
relative expiry events. Timing is local instrumentation, not repeatable/live SLA.

Rejected: an evaluator-only authorization engine; a fake marked external/live;
client-selected imports, scoring callables, URLs or paths; golden answers supplied
to generation; adding SDKs/migrations; changing historical locks; automatic
production promotion. Existing fake profiles do not invoke P19 physical-provider
accounting: report those counters as unknown/not_applicable rather than invent
reservations. Exercise inherited P19/P21 negative tests separately.

32 synthetic cases: eight families × four cases, grouped by task lineage/source
configuration. Two calibration and two held-out cases per family; distinct source
configurations, no held-out tuning. Both one-turn and transition tasks. Separate
warmup uses a disposable non-corpus task. At most two candidate configurations:
existing selective context (versus no selected source) and compact research
packing (versus literal). Routing comparison is plumbing only. Non-applicable
arms carry explicit eligibility and never enter matched denominators.

Preregistered primary endpoint: held-out hard-constraint-valid task success on
eligible paired tasks. A success requires exact task outcome plus hard constraints
and citation support where applicable. Minimum meaningful scripted gain: one
additional held-out task without any family loss or safety veto. A zero gain is
inconclusive. Wins/ties/losses, count and risk difference by family; no confidence
interval or generalization from this small deterministic corpus. Never claim real
model utility, live cost or production eligibility.

Noncompensatory veto: unauthorized/stale disclosure, missing retained dependency,
unauthorized tool, duplicate effect, hidden fallback or nonlocal provider attempt.
Any veto denies the candidate independently of mean score. Missing observations
are unknown, never zero. V1 caps were 32 cases, two measured arms per task plus
explicit standalone retrieval controls, 32768 input fake-byte units, 256 output
units, 5 second operation deadline, 8192 source bytes and a 120 second suite
deadline. V2 uses a fixed 300 second suite deadline after the installed full
evaluator demonstrated that 120 seconds did not permit complete measurement.
No candidate changes caps between arms. Report synthetic monetary zero separately
from unknown real USD, estimated/upper-bound cost and quota.

| Seam/arm | Eligibility | Missing prerequisite / evidence boundary |
| --- | --- | --- |
| Fixed context / no selected source | measured when task supports it | Synthetic facts, identical scopes/budgets |
| Selective whole profile / local retrieval | measured | Exact local consent and source dependencies; public HTTP |
| MEM-0/1/2 control tasks | measured for existing local controls | No new embeddings or production host; recall/correction coverage separately identified |
| Research-v1 literal / compact | measured | Fake source/LLM transport; literal citation correctness only |
| offline_fake / offline_fake_alt | measured plumbing | No model quality or physical P19 sends |
| Standalone local retrieval / no retrieval | measured control | Does not establish generation utility |
| External model context, live providers/search | blocked_capability | Distributed rights/send permit and authorized account absent |
| Paid routes, arbitrary tools, exports, MEM-3+ | denied_policy | Outside authorized scope; no callable runner path |
| Live latency, real USD, cloud identity, physical deletion/restore | unmeasured | Separate explicit authority and environment required |

Local structure, causal scripted success, real-model utility, live cost and
production promotion are five different evidence classes. Preserve the original
P6 matrix and add interpretation/disposition, never rewrite historical intent.

Post-code source-identity note: the v25 lock includes all core source and its old
revision guard. Final v26 binds the actual R05 entry base plus additive PI-6
source. Initial lock failures were not isolated against the pre-code R05 base;
no causal claim attributes them solely to new PI-6 files. Historical lock bytes,
fixtures, scoring, configuration and promotion decisions remain preserved.

## Review remediation addendum — 2026-11-02

The review of `c22c646` is treated as evidence to reconcile, not as authority to
replace repository contracts or to claim unavailable external acceptance. The
original v1 corpus, manifest, measurement exposure and first failed observation
remain unchanged. v1 is now classified as development-exposed because the
held-out answers were seen before the driver correction. The remediation freezes
the complete v2 scorer/contract/driver/runner/HTTP protocol before running a
newly authored synthetic corpus. The v2 cases are prospective relative to that
protocol but are not blind or independently authored; they can support only a
local scripted harness check.

Chosen fixes:

- **R01/R02:** score from frozen task/arm semantics, hashable answer/source
  evidence and evaluator-owned effect observations. `None` factual evidence,
  missing source provenance, forbidden effects and excess model dispatches
  fail closed. Driver-provided expected dispatch counts are removed.
- **R03:** declare the expected arms from the frozen corpus before dispatch;
  reject duplicate, unknown, missing, unmeasured and evidence-incomplete rows.
  Keep task-quality losses separate from structural coverage errors and safety
  vetoes.
- **R04/R09:** isolate each driver operation in a killable child with a hard
  five-second deadline, Python and native network fences, bounded output sinks,
  and a 300-second suite limit. The child owns all driver threads and exits as a
  unit on return or timeout. Enforce the 8 KiB source and 32,768/256 unit caps.
- **R05:** preserve v1 as exposed history and bind the v2 manifest to all
  evaluator code plus the installed Reading Logbook client/host source. No
  confirmatory or population-level claim is made from agent-authored cases.
- **R06:** issue the same revocation read on both memory arms and verify the
  denied status; positive recall compares exact expected content fingerprints,
  not record IDs.
- **R07/R08:** derive runtime identity from installed distribution versions and
  package file hashes, remove Git/source-root dependence from evaluation, and
  require a real native denial probe in each measured process. The Python flag
  is not treated as a capability. Core-only missing HTTP packages are explicit
  ineligible observations and invalidate coverage.
- **R10/R11:** use nearest-rank p95 with a unit test. Add planning lock v27 as a
  source-only non-promoting child of v26's reviewed PI-6 entry; v10–v26 remain
  byte-for-byte historical evidence. Its planner digest excludes the v2
  measurement manifest to avoid coupling planning identity to run output.

The implementation reran the canonical source and installed-wheel evaluation
after protocol stabilization: 68/68 rows in both full environments, exact
coverage, no safety veto. The first v2 run with 13 incomplete-score arms remains
preserved separately. The review remediation is closed by user direction with
no further review required; no independent review handoff is requested.

Deferred conditions remain: PI-5 F01/F02/F03 and P5-04/11/14/19/22/26/27,
P5-24/P5-28, live provider/account cost and privacy, deployed IAM, physical
dispatch authority, distributed receipt recovery, restore anti-rollback,
deletion and production promotion. V2 cases are not blind or independently
authored, so they support only local scripted harness verification. No memory
defaults, migration, public API, PI-7, MEM-3+, or provider path is authorized.

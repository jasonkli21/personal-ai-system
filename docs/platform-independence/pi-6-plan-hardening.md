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
are unknown, never zero. Fixed caps: 32 cases, two measured arms per task plus
explicit standalone retrieval controls, 32768 input fake-byte units, 256 output
units, 5 second operation deadline, 8192 source bytes, 120 second suite deadline.
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

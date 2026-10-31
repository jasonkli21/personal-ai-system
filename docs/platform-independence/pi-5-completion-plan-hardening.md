# PI-5 completion hardening — 2026-10-31

Written before runtime changes. Base `af233c5672d204e1ad080250a89ad7b921c79716`.
Entry has only 22 pre-existing untracked planning/review documents; preserve their
bytes and ownership. The original PI-5 plan SHA-256 is
`3f5f3bd83390c4681037e282652bc7230983ae43c572e0be17d75b3db72c3af5`.
Python is the existing 3.11.15 macOS arm64 virtual environment. Exact entry
manifest is captured for the final verification record. No dependency install.

The human asks for sequential completion and review in this session, overriding
the attached prompt's session scheduling. Self-review still cannot constitute
independent signoff. Mandatory live/provider, IAM and recovery evidence is absent
and live execution is explicitly unauthorized. PI-6 must remain gated if those
requirements cannot be satisfied; do not create a substitute benchmark.

## Decisions, alternatives and authority graph

Code inspection confirms F01 and F02 are real blockers. `retrieval/service.py`
returns source-neutral exact passages but `ContextProviderInputs.retrieval` is
MEM retrieval, not PI-5 retrieval. Do not overload it or cache source bodies.
Reuse `ContextProviderCoordinator`, `ContextBuilder`, `ContextPermissionDependency`,
`ContextSourceSnapshot` and the `llm/disclosure.py` dispatch guard. No second grant,
evidence, billing or model execution store is justified.

Implement an explicit local retrieval context provider and optional continuation
choice. Source access for interactive quotes does NOT imply model disclosure:
require a separately declared exact owner/actor/app/workspace model-context grant,
app capability and field/sensitivity policy, and document model permission.
Defaults remain off. Use the pending question for bounded real lexical search;
never infer selection from untrusted quoted text. A payload contains exact
citation/quote/revision/rights/expiry metadata. Pack as inert structured data via
the existing builder. No tool selection by a model; no new memory extraction.

Bind dependencies to the configured installation's complete digest, scope and
issuer-qualified source identity. Reload on every check; fail on missing file,
changed source, expiry, grant removal, client/owner fence, disabled feature or
unavailable authority. Conservative whole-installation invalidation is preferable
to accepting partial stale revisions. A file replacement between the final check
and transport is NOT a distributed atomic source lease: local check/dispatch is
an observation boundary, not production linearizability. A monotonic distributed
issuer/lease and restore anti-rollback remain mandatory acceptance blockers.
External snippets cannot safely enter this provider until that authority exists.
Never manufacture it from a mock or an in-process lock.

Trace: authenticated continuation -> explicit selection -> current installation
and lexical search -> typed ContextItem -> shared source/global pack/count with
permission checks -> canonical snapshots -> shared P19/disclosure guard -> normal
model stream -> snapshot-bearing assistant -> summary/history filtering -> SSE,
original-key replay, detail and export checks. Audit failure persistence too:
failed partial assistant content must retain authority or be removed. Account
export must not bypass checks by serializing message or summary JSON directly.

Read-only tools: use an immutable versioned operator registry with trusted Python
registrations, closed request/result schemas, byte/deadline budgets, declared
read-only effect and existing app capability checks. Client/manifests supply no
code, imports, URLs, paths or handlers. Keep the existing exact public route;
registry extensibility alone does not justify a generic public executor.

Receipt growth: retain irreversible old intent fences; do not prune or recycle
keys. Bound the number of operator-admitted scopes and reserve equal per-scope
lifetime capacity so one scope cannot consume another's allocation. Exhaustion
fails closed. This does not establish native distributed P19, backup safety or
physical deletion. Restored stale journals remain unsafe; keep external execution
local/test-only. No production guarantee based on SQLite tests.

## Threat model and minimal change map

Malicious source instructions, same-owner foreign apps/actors/workspaces, stale
source/revoked grants, forged snapshots, source collisions, disappearing authority,
partial failed output, summaries and export are disclosure threats. Unknown sends,
SDK retries and receipt exhaustion are cost/availability threats. Hidden error
paths and logs must not expose source paths/content or credentials.

Changes: retrieval context/authority adapter, existing provider inputs/composition,
additive continuation contracts, detail/output/export guards, closed tool registry,
local journal admission; focused PI-5/context/HTTP tests, existing fenced runner,
consumer contract generator and minimal docs. No memory feature, old lock/corpus,
threshold, provider route, paid policy or domain changes. Regressions may require
narrow owning evaluator corrections only after reproducing unchanged baseline.

## Verification and acceptance

Run one serial native-network-fenced provider-matrix/Phase36 baseline first.
Initial sandbox cannot bind the runner's Unix probe socket; retry with permission
to execute the existing runner, which then denies IPv4/IPv6/Unix network itself.
Record all failures rather than changing old expectations. Exercise local sources,
pack/count and physical guard races, revoke after persistence, history/summary,
SSE/replay/detail/export, foreign scopes, missing validator, malformed provenance,
injection, kill switch, changed intent, restart and capacity fairness. Run PI-5,
PI-2/3/4, lint, installed core/reference absence, relevant MEM/Phase35/36 and full
offline backend as feasible. Separate synthetic, native, installed and not-run
live/deployed/recovery evidence. Preserve original untracked inputs by hash.

No destructive migration: additive defaults deny old installations. Rollout needs
all strict readers deployed before opt-in, and synthetic corpus only until accepted.
Rollback disables selection and execution while retaining strict readers, dependency
validation, old receipts and deletion fences. Never restore an older permissive
binary or re-enable a stale backup. Existing output cannot be recalled.

External prerequisites: separately approved exact provider/account/free-tier/privacy/
rights/count limits; real verified identity/private invocation; native distributed
source and P19 original-attempt storage; independently tested backup revocation/
delete anti-rollback and physical erasure; distinct reviewer signoff on the exact
source identity. No local pass closes P5-04/11/14/19/26 production obligations.

## Source-identity migration decision before remeasurement

The first PI-2 aggregate stopped at `planning_baseline_changed_requires_new_version`;
PI-4 passed 893 cases and failed only the v24 current-source assertion. This is an
introduced source-binding mismatch, not an inherited score/count regression.
Append v25 as a source-identity migration, preserving v10–v24 byte-for-byte and all
corpus/configuration/counter/evaluator/scoring/threshold identities. Move the v24
assertion to its historical file with its original digest pinned and add a separate
v25 current-source assertion. No expected result/count or promotion changes. This
migration does not repair or conceal any task-quality regression. Rerun the same
checks after the source binding is frozen, and retain the original failed runs.

## Regression review refinement

A full pre-fix offline run had 2 failures/2,323 passes/119 deselections, including
Phase35 `routing_label_identity_mismatch:prepared_input,metrics_missing,case_status`
and Phase36 75 instead of 80 synthetic cases; another native run reported 74.
The test store's SQL clock was frozen at construction, whereas permit expiry
correctly used actual UTC. The narrow correction is an evaluation-only test
repository implementing advancing PostgreSQL `clock_timestamp()` semantics, also
selected by the Phase36 factory test. Other intentionally frozen routing tests
remain unchanged. No production clock, TTL, deadline, corpus, oracle, expected
count or score is modified. The added stale-construction-marker probe tests the
clock contract without sleeps; its reduced suite is explicitly registered by
exact suite digest, preserving the existing approval gate. This fixes a real
fake-contract mismatch but does not prove every historical cold-start/30 ms quota
failure had that cause. Keep that uncertainty and the original failures.

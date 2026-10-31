# PI-5 standalone retrieval/read-only tool implementation candidate

2026-10-30–31 America/Los_Angeles. **Incomplete mandatory phase acceptance;
independent review pending.** The user authorized implementation and one local
commit in this session, with no subagents. No push, merge, deployment, real secret
access or live/billable provider request was performed. MEM-3+ stays frozen.

Entry/test base: `e5412a85e58fdf0a9d7b58d1361a23b37e477190` on `main`.
The tested patch is identified by the runtime/source/artifact fingerprints in
[verification JSON](pi-5-verification.json). Resolve the final single implementation
commit with `git log -1 --format=%H -- docs/platform-independence/pi-5-implementation-report.md`;
its parent must equal the entry SHA. That commit's tree binds this report and the
machine evidence without an impossible self-referential commit hash. Initial
tracked tree was clean; eighteen existing untracked user documents (including
plan/prompt) were preserved unchanged and left unstaged.

## Implemented boundary

- Additive closed `retrieval-v1` request/item/outcome contracts. Local sources use
  real source IDs, exact substring offsets/UTF-8 hashes, revision and rights
  identity/epoch, license, sensitivity and observation/publication/expiry. Public
  URLs are optional for local sources and never fabricated. External HTML snippet
  normalization and observation-hash revisions are explicitly labeled. Tuple
  identities use canonical JSON hashing, avoiding delimiter ambiguities.
- Real bounded lexical inverted index over an operator-installed inline corpus.
  Exact owner, actor, application and workspace grants apply independently to
  endpoint and document access. No wildcard, same-owner or profile-consent shortcut.
  Only authorized documents contribute index statistics. A separately configured
  corpus uses the same implementation. An operator demo CLI creates fresh synthetic
  data with explicit scope; there is no client path/upload/ingestion API.
- Existing operator-selected search registration/Brave snippet bridge, preserving
  domain intersection/exclusions, safe URLs, rights and P19 accounting. A trusted
  custom registration is exercised without core app-specific branches. The Brave
  adapter repeats the owning source/client guard after rate wait/P19 reservation
  before its physical request. Missing/legacy rights, credentials, privacy/cost
  admission or usage identity deny. Existing closed strict-free policy is unchanged.
- Single-host SQLite original-intent receipts for local/test external attempts:
  reserve before dispatch, concurrent/restarted/cancelled retries do not resend,
  changed input conflicts, unknown stays unknown, completed retries return no cached
  external bodies. No automatic retry/rekey/provider fallback. Receipts are private,
  content-free and never pruned; 4,096 lifetime capacity refuses new attempts.
- One actual executable tool binding `retrieval.query.v1`. A fixed implementation
  registry, matching application read-only metadata and operator source/tool grants
  are all required. Closed schemas reject dynamic imports, arbitrary URLs/paths,
  mutation/memory calls, undeclared fields and excessive bounds before execution.
- Two exact protected POST routes, additive consumer OpenAPI v1.1.0, and independent
  Reading Logbook client/CLI/optional host metadata. Original conversation path
  and schema JSON objects are unchanged. Existing auth/client/workspace binding,
  safe errors, body limits, no-store/correlation and request-rate infrastructure
  remain. Tool selection does not register a context provider or model tool loop.
- Final snapshot digest, current source rights/settings/credentials, actor/client/
  workspace and owner-directory checks precede disclosure. Replacing/deleting/
  corrupting the corpus denies all in-flight bodies. Builtin and external owner
  deactivation both deny. Whole-request item/quote/serialized-evidence byte token,
  deadline and process-slot bounds apply. Source text remains inert quoted data.

See [pre-code hardening](pi-5-plan-hardening.md) for the authority graph, eight
questions, flaws/deferrals and revised sequence, and [wire/operator instructions](retrieval-v1.md)
for setup, retry, installation and rollback semantics. The original plan/prompt
were not rewritten. No canonical research/memory migration or new provider
eligibility was introduced.

## Deliberately unavailable / acceptance gaps

General model-context integration is unavailable: no retrieval context factory,
summary/history persistence, SSE stream, automatic memory capture, model counting
or send path consumes these results. This is a security boundary, not completion
of mandatory context/replay scenarios. A source issuer/lease and retained derived
provenance are needed before adding that path. Existing PI-4 profile/history
quarantine remains intact. Explicitly pasted user text is fresh user input and
cannot be retroactively presented as governed source provenance.

Live Brave eligibility, actual billing/quota/privacy, real Google/IAM, distributed
source authority and attempt storage, production recovery, deletion and backup
anti-rollback remain unproven. Current Brave P19 strict-free profile is closed;
mock transport with a fake P19 storage port proves only serialization/admission
wiring. External execution is local/test only. Local corpus rights are single-host
operator authority; stale snapshots or receipts must not be restored/replaced to
re-enable revoked rights or attempts. Native P19/store and cloud acceptance were
not run. The bounded lifetime receipt cap is an operational limitation, not permission
to prune fences. No atomic revocation/network-send guarantee or recall of past
transmissions is claimed.

Accordingly P5-04, P5-11, P5-14, P5-19 and P5-26 remain blocked in their full
mandatory form. A17/A18 full acceptance and PI-5 full completion are not claimed.
The machine matrix records individual dispositions and evidence; it does not
convert absent integration or synthetic provider ports into passes.

## Self-review and fixes

Inspected every changed source and neighboring auth, application metadata,
research persistence, context source/tool projections, count/send, history/replay,
usage, provider policy and packaging callers. This is implementing-session review,
not an independent verdict.

Corrected before handoff: explicit normalized-snippet/revision basis; actor-scoped
P19 invocation identity; credential/policy rotation fencing; refusal of historical
opaque rights strings; regular/non-symlink bounded files; strict boolean source
flags; synchronous work deadline checks; no provenance-body cache; final builtin
owner-directory revalidation; external error attempt IDs; canonical tuple hashing;
tool result metadata/schema bounds; the correct builtin request-body timeout code; partial malformed-snippet handling with retained attempt IDs; timezone-aware publication constraints; and explicit SQLite connection cleanup. Race tests remove or mutate source/client/
workspace authority after index search and after P19 reserve and observe zero
stale bodies or physical provider sends. Prompt-injection passages stay literal;
no model, memory or domain mutation is invoked.

The original v23 planner guard correctly rejected changed source. Appended v24 is
an explicit source-only non-promoting binding to the entry SHA; v10–v23 bytes,
planner configuration, held-out corpus, fixture dependencies and count expectations
remain unchanged. The v23 historical-preservation test now reads/pins its historical
file, and a new v24 test checks the current source. No guard is waived.

## Verification

Exact commands, log hashes, source/artifact identities, check results and P5-01–28
are recorded in [machine evidence](pi-5-verification.json). Counts overlap and
must not be added as unique cases. Python 3.11.15/macOS arm64; dependency builds
used the existing offline environment. No dependency downloads or real secrets.
The native runner denies IPv4/IPv6/Unix networking; signed HTTP/client checks use
numeric loopback only and synthetic JWT certificate transport. Neither proves
real identity/provider/cloud behavior. Sandboxed loopback binds initially failed;
the authorized fenced runner was then used outside the enclosing tool sandbox.

| Check | Observed result |
| --- | --- |
| Final PI-5-only native + signed HTTP (`pi5_checks.py --only test_pi5_retrieval.py`) | **56 unit + 27 HTTP passed**, zero forbidden attempts. Includes real local corpus, malformed contracts, rights/client/owner races, exact tool execution, restart/concurrency and builtin body deadline. |
| Final serial offline `make pi2-check` | **Pass**: wheel/sdist, dependency guard and source-bound planner; installed core **137**, reference **190**, retained task **56**, independent HTTP/client/provider **172 passed / 1 existing skip**. Physical reference absence, client-only interpreter and post-uninstall core recheck passed; zero forbidden attempts. |
| Delivery `make pi5-check` including old research | **110 passed / 1 failed**: `test_partial_plan_keeps_completed_observations_without_answer_or_replay[quota]`; its 30 ms budget returned `running` instead of `failed`. The runner stops before HTTP on this failure; the independent final PI-5-only command above ran all 27 HTTP cases. |
| Earlier complete PI-5 checkpoint | **111 native + 26 HTTP passed**, zero forbidden attempts; predates the final safe-error normalization and its additional HTTP test. |
| PI-3 compatibility checkpoint | **781 passed / 3 failed**: the two provider-matrix tests (including resume) and Phase36 synthetic count. Zero forbidden attempts. |
| PI-4 compatibility checkpoints | **891 passed / 3 failed**, then **890 passed / 4 failed**, zero forbidden attempts. The latter additionally hit the legacy inference cold-start timeout. These started before the final body-error normalization; the affected final branch was separately tested and included in the final installed proof. |
| Full offline backend selection through loopback audit runner | **2,273 passed / 5 failed / 119 deselected**, zero forbidden attempts. Three matrix/Phase36 failures plus two adaptive-routing label-identity failures. This is a broad checkpoint, not an assertion of a fully green final suite. |
| Focused research/auth/scope/planner | **106 passed / 1 failed**, the same 30 ms research quota case. Planner v24 and inherited auth/scope checks passed; no timeout/assertion was relaxed. |
| Exact entry source archive controls | Research deadline pair **2 passed / 21 deselected**; both adaptive-routing cases **failed / 36 deselected** with the identical `routing_label_identity_mismatch:prepared_input,metrics_missing,case_status`. Entry code imports were proven from the archive; git revision metadata was supplied read-only from the unchanged entry repository. |
| Existing research/retrieval evaluations | **Exit 0** under native network denial; research reports `passed=true`, retrieval retains `not_promoted`, with live answer quality/quota unmeasured. |
| Backend + client/host lint, OpenAPI generation/check, old-contract JSON comparison and whitespace | **Pass**. Every old conversation path/schema object is unchanged; four new schema types and two exact operations are additive. |

The documented PI-4 891/2 and focused 21/3 failures remain historical evidence.
This run reproduced the same matrix/resume/Phase36 failure families with varying
counts (not fixed by PI-5). The additional adaptive failures reproduced on the exact
entry source, establishing they precede this patch. The research 30 ms case varies
between broad/focused/isolated runs; entry controls and the earlier native target
passed, so no root cause or fix is claimed. No fixture, budget, count expectation,
held-out data or historical lock was changed to hide a failure.

A final-artifact attempt and the last PI-4 checkpoint also hit
`test_explicit_legacy_uses_separate_count_and_generation_attempts_and_prepared_reservations`:
a 10-second cold-start budget reached zero before generation (`LLMInvalidRequestError`).
The final serial artifact rerun passed its complete core and installed suites. The
failed attempt remains evidence; a later pass does not establish its root cause.
The earlier adaptive archive attempt lacked git metadata and failed setup; only the
subsequent read-only-git comparison supports the entry-failure claim. Initial new
fixture setup also omitted required `ai_model` (14 pass / 34 setup errors), which
was corrected. Sandbox loopback failures and these intermediate runs are not passes.
No frontend code changed; frontend/browser, native PostgreSQL/DynamoDB, cloud and
live provider checks were not run. Real temporary SQLite receipt transactions,
concurrency and restart were exercised.

## Rollout and independent review

Keep default-off pending a separate independent audit. Publish only a synthetic
single-host installation first, enable explicit exact grants, then opt into the
host tool separately. Disable retrieval/host flags and drain for rollback; retain
all original-intent receipts, current source/deletion/rights epochs and existing
PI-4/memory fences. Never restore old grants/receipts or delete a journal to clear
an uncertain attempt. No database down migration is needed.

Review this single commit against its entry parent. Reproduce `make pi5-check`,
`UV_OFFLINE=true UV_CACHE_DIR=/tmp/pi5-review-cache make pi2-check`, inherited PI-3/4,
backend lint and research/retrieval evaluations with the documented network fences.
Attempt cross-owner/actor/app/workspace probing, missing/expired/corrupt rights,
source/credential/owner/client races, original-key process restart/provider switch,
manifest-only execution, malicious tools/URLs/text, capacity/deadline denial and
rollback/restore. Recheck unchanged conversation OpenAPI objects, every historical
lock/fixture hash and physical reference absence. Audit the explicit missing
context and production authorities before expanding scope. No independent P0/P1
clearance is supplied here; inherited red tests and production gates stay open.

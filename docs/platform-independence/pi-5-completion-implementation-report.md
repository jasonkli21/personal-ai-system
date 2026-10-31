# PI-5 completion candidate — 2026-10-31

Status: **blocked_missing_authority**, not full PI-5 acceptance. The human subsequently directed PI-6 local implementation despite this gate. Base/tested HEAD is `af233c5672d204e1ad080250a89ad7b921c79716`;
verification used the uncommitted source manifest in
[verification](pi-5-completion-verification.json). The human subsequently authorized
a separate PI-5 commit; resolve its identity with `git log -1 --format=%H --
docs/platform-independence/pi-5-completion-implementation-report.md`. No push or deployment,
live provider, personal-data or destructive persistence action occurred.

The human requested completion and review here, then explicitly authorized a
Luna XHigh reviewer only after implementation/verification. That overrides the
attachment's separate-session scheduling, but cannot turn synthetic evidence into
production acceptance. The human later cancelled that review and explicitly directed PI-6 implementation.
No independent signoff exists. This changes sequencing, not the evidence classes.

## Implemented local boundary

- Explicit optional continuation selection routes real operator-file lexical
  retrieval into the standard context coordinator, field/sensitivity projection,
  packer, source/global counters and normal neutral model stream. Two sanctioned
  exact offline execution profiles and an unrelated signed HTTP consumer exercise
  this path; there is no alternate executor or automatic tool loop.
- Independent model-purpose scope grants, per-document model permission and a
  separate default-off feature gate. Exact quotes/citations/revisions/rights and
  expiry are packed as source data. A whole-installation digest and issuer-qualified
  source bind existing permission dependencies; current request authority and app
  policy/capability are required on every recheck. No duplicate source/grant store.
- Successful answers retain canonical snapshots. Count/send/SSE/detail/replay and
  history/summary use the shared source checks. Failed source-bearing turns drop
  partial text, avoiding provenance-free retained output. Durable memory extraction
  rejects retrieval-derived assistant context. Account exports and export artifacts
  containing retrieval dependencies fail closed pending export-purpose consent.
- Immutable versioned trusted read-only registrations replace the single hardcoded
  handler map. Closed typed input/output, current capability metadata, byte/time
  limits and registry identity checks surround execution. The public endpoint stays
  the exact typed retrieval route; arbitrary plugins/code/imports/URLs or model
  execution loops are not accepted from client data.
- SQLite retains 32 lifetime scope allocations × 4,096 original intents with equal
  operator reservation, preserved old receipts and a 128 MiB future page-allocation
  ceiling. Restart retains uncertain intent denial. There is no receipt pruning,
  rekeying, distributed guarantee or stale-backup safety claim.
- Consumer v1.2.0 adds only optional explicit selection, preserving false/absent
  continuation intent digests. Reading Logbook uses the stable host extension
  facade; its HTTP client has no private backend import. All MEM defaults stay off.

Full operator details and limits: [retrieval contract](retrieval-v1.md).

## Critical review and fixes

[Hardening](pi-5-completion-plan-hardening.md) preceded runtime changes. It rejects
an in-process lock as proof of distributed revocation or restore safety. The last
source check is a local observation/dispatch boundary: a concurrent replacement
between check and wire remains possible. Deploying this local authority is denied
by code (`local|test` only). Missing native lease/source/P19 and provider/IAM/
restore/delete evidence remains a P1 acceptance blocker.

Self-review found and addressed source-bearing failure-body retention, completion
emission after persistence, count rechecks, built-in detail/replay reuse, raw account
and artifact-export bypasses, captured default tool registries and changing registry
identity. Export currently denies rather than inventing a new consent purpose.
The existing metadata-only tool denial test now removes the actual executable
registry, preserving the old negative assertion on the replacement seam.

Initial authoring failures were a wrong fake import and test scope setup, missing
required Settings values, and an internal/browser payload shape mismatch; corrected
before final verification. Initial PI-5 HTTP testing also caught the old binding-map
removal test still targeting a discarded seam; its equivalent registry denial is
now tested. An initial Ruff invalid-type exception style error was corrected.

The historical provider-matrix/Phase36 count/resume baseline passed 24 cases
serially before runtime changes. The broader run reproduced Phase35 missing labels
and a matrix count failure. Inspection found that their shared test database
returned one construction timestamp forever while dispatch correctly compared
permits against advancing UTC. The evaluation-only fake now implements advancing
`clock_timestamp()`, matching PostgreSQL. A regression starts its construction
marker two minutes in the past and proves new permits have current deadlines;
production time checks, 30-second permits, fixtures, expected counts and scoring
are unchanged. This does not prove every historical cold-start/30 ms research
quota failure had that cause. Original failed runs are retained in the command ledger. This is a
fake-contract correction, not a production deadline relaxation.

The first PI-2/4 aggregate also rejected changed source identity under frozen v24.
An explicit v25 source-identity migration preserves all historical v10–v24 bytes,
corpus/configuration/counter/evaluator/rubric/threshold identities and no-promotion.
Its own current-source assertion is distinct from the historical v24 digest pin.
This does not supply answer-quality or promotion evidence.

## Verification and acceptance gaps

The full offline checkpoint passed **2,326 tests / 119 deselected**, with zero
forbidden network attempts. PI-5 passed **147 native-fenced + 34 signed HTTP**
cases; PI-2 installed core/reference/retained-task/consumer/uninstall proofs passed.
Existing planning/research/retrieval/MEM-0 evaluations, Ruff and contract generation
passed. The subsequent registry-object freeze was covered by fresh PI-5, installed
package and 58 planning tests; the broad checkpoint is separately identified in
the ledger. Native PI-3/4 compatibility passed 896 tests. Warnings concern Python 3.11 support, Starlette TestClient and Pydantic
ReadOnly annotations, not live acceptance.

The machine ledger records commands, summaries, classes, failed intermediate runs,
source/test/artifact hashes and all P5-01–28 dispositions. Native-network fences,
signed loopback and installed synthetic identity/model/persistence are distinguished.
They do not establish real Google identity, private cloud invocation, live Brave,
free-tier/billing/counter privacy, native distributed source/P19, backup recovery or
physical deletion. No real-model utility or citation correctness claim is made.

External source-to-model authority remains unimplemented. Account export lacks
source-specific export consent and is explicitly unavailable for derived content.
An operator can restore an old local corpus/journal; the local digest cannot prove
monotonic anti-rollback. Broader native/distributed authority cannot be accepted
from these local implementations. Those mandatory gaps prevent full completion and
PI-6 entry even if every permitted local test passes. See [gate](pi-5-completion-gate.md).

## Findings F01–F08

| Finding | Disposition |
| --- | --- |
| F01 | Local source-to-model and derived reuse implemented; full external/native source lease and source-specific export remain blocked. |
| F02 | Open P1: no approved live/provider/IAM/native/restore/delete acceptance. External model context remains unavailable. |
| F03 | Local aggregate growth bounded with retained equal allocations; durable distributed and backup safety unresolved. |
| F04 | Earlier P19 failure-ID preservation retained and retested. |
| F05 | Earlier issuer/scope citation authority retained; dependencies add exact installation/source revision binding. |
| F06 | Trusted immutable versioned registry implemented/tested. It is not a sandbox or generic public/model executor. |
| F07 | Earlier title-only irrelevant-passage exclusion retained and retested. |
| F08 | All 22 entry untracked user documents preserved byte-for-byte, including original detailed plan and review prompts; no staging/ownership takeover. |

## Migration and rollback

Installation additions are default-deny and old files remain readable. SQLite adds
only retained scope allocations; no attempt row is deleted. No SQL migration,
embedding-space change or MEM schema/fixture change is introduced. Deploy all strict
readers before opting in; mixed old permissive readers are unsupported. Keep the
local/test profile disabled for real data.

Rollback disables `RETRIEVAL_CONTEXT_ENABLED`, `RETRIEVAL_ENABLED`, external
retrieval and host selection, drains active work, and retains strict source-denial
readers, receipts, dependencies and deletion fences. Do not downgrade to a binary
that ignores retained retrieval dependencies or restore old receipts/corpus and
resume external sends. Past provider disclosures cannot be recalled.

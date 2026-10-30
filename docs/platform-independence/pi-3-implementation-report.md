# PI-3 local implementation and verification

2026-10-30, America/Los_Angeles. Entry/tested base:
`0dbe7406fda20c58c784339647ca15c4c7ab3f7e` plus the implementation source digest
and artifact identities in [verification](pi-3-verification.json). One implementing
session, no subagents, no independent verdict, no push/merge/deployment/live call.
The user's explicit phase-entry exception does not close independent PI-0/1/2
acceptance, memory, Phase36, identity, native-storage or production gates.

[Plan hardening](pi-3-plan-hardening.md) was written before runtime edits. Entry
tracked state was clean. Fourteen pre-existing untracked planning/review files,
including the supplied PI-3 plan/prompt, remain untouched and outside this commit.
No other repositories were edited.

## Delivered architecture

`llm/execution.py` composes a closed installed catalog over existing generation,
counting, endpoint registry and accounting contracts. FastAPI caches one exact
pair per request and passes it to the normal model/context dependencies. Chat,
edit/regenerate and automatic external-consumer continuation retain the original
ChatTurnService, ContextAssembler, durable branches, UUID keys and SSE protocol.
No request or manifest can register a factory, select credentials or override the
operator profile. There is no new router, provider loop, quota ledger or migration.

Two deliberately distinct local fake profiles execute canonical normal chat with
matched local JSON-byte counters and estimated synthetic output usage. Those
counts are authoritative only for the defined fake serialization; they are not
remote provider tokens. The explicit `legacy_gemini` profile requires strict-free
mode, exact original Gemini serialization/count mapping, P19 accounting and
current registry facts. Generation additionally counts its own exact serialized
input/schema with a bounded output and shared remaining timeout. Unsupported
Groq/Cloudflare normal profiles reject before any provider disclosure. No estimated
counter is admitted into the strict path; `preparation.py` and `DeadlineCounter`
requirements remain unchanged.

Remote count and generation admission reuses EndpointRegistry hard requirements
before disclosure and again immediately before P19 physical-attempt reservation.
Admission also requires explicit privacy approval, evidence reference and a finite
current account-specific free attestation. Unknown/stale/mismatched policy denies.
Count reservations cover the approved input ceiling; generation reservations cover
the exact prepared input plus bounded output. Provider-reported output usage keeps
the existing ledger confidence vocabulary (`exact` for reported, `derived` for
estimates); fake output remains `estimated`. Endpoint/profile version, account and
credential scope, owner/app/workspace, operation, task, invocation and attempt IDs
stay in the existing bounded attribution. No content or secret diagnostics added.

Conversation summary is a separately selected same-endpoint operation with its
own count/send and `conversation_summary` task attribution. It retains full
preparation sensitivity, including history covered by a prior summary. Structured
extraction checks capability before any counter disclosure and requires actual
schema approval. Research's remote branch and memory workers use shared policy;
research's literal-excerpt local fake stays local. Optional booking/itinerary
remote factories also use the same pair; their explicit task fakes and gates stay.

New memory embedding work is explicitly unavailable: there is no approved exact
embedding-input counter. A different chat choice cannot trigger covert Gemini
embedding or a fake-vector fallback. The original direct embedder, persisted
`EmbeddingSpace` identity, query/document tasks, dimensions, normalization and v1
vectors remain unchanged. Existing vector compatibility/mismatch tests are retained.
Schema-3 lexical selection remains independent. MEM-0/1/2 flags remain default-off;
no taxonomy, intake, source fences, forget receipts or tombstones were migrated.

Paid and mostly-free modes always deny. The canonical ledger has quota/token
reservations but no audited USD price upper bound, dual-consent authority and
per-operation/period monetary reservation/reconciliation. Adding booleans/caps in
settings would not make paid execution enforceable. No fallback is selected after
429, timeout, partial output, cancellation, missing terminal or unknown outcome.

A discovered pinned SDK bypass required a transport fix: LiteLLM's async handler
catches ConnectError/RemoteProtocolError and retries with a new client outside the
bounded transport even with zero retry flags. `_BoundedAsyncTransport` now converts
those errors to its own safe fault before the SDK sees them. Tests assert that no
replacement client is created, rather than merely counting mock requests. Existing
physical-attempt accounting conservatively retains uncertain outcomes.

## Diff inventory and compatibility

- `llm/execution.py`, `llm/disclosure.py`: closed profiles, exact pairing, canonical
  admission/usage facade and service-owned source revalidation callback.
- API dependencies, chat service, worker, research and optional booking/itinerary
  factories: shared composition; no second lifecycle or changes to the v1 wire.
- Summary/memory adapters, assembler and extraction: neutral ports, full summary
  sensitivity, explicit disabled capabilities and structured-capability preflight.
- Settings, `.env.example`, root/inference docs: explicit offline defaults and
  opt-in legacy configuration; inactive credentials are not required.
- Bounded async transport/gateway tests: prevent SDK replacement-client retries.
- PI-3 tests/runner/Makefile and installed PI-1 probes: normal installed fake API
  path with physically absent examples, native/Python fences, negative tests.
- Planning v22 and its history test: source-only rebind. v10–v21, MEM fixtures,
  held-out corpus, configuration, scoring and non-promotion are preserved byte for
  byte. The current-or-direct-child revision guard is unchanged.
- Current state/router/PI index plus these evidence files: local candidate only.

No message/application/task IDs, receipts, branch/supersedes records, database
schemas, source or actor fences, vectors, consumer version or frozen corpus changed.
Direct compatibility adapter constructors remain for existing explicit tests and
opt-in provider/cascade evaluation; they do not grant normal dispatch authority.
Phase35/adaptive/shadow and manual/connected external-turn promotion stay disabled.

## Skeptical same-session review and dispositions

| Finding | Disposition / evidence |
| --- | --- |
| Proposed byte estimate cannot prove Groq/Cloudflare tokens | Rejected; profiles unavailable before count/network, strict contracts unchanged |
| Old memory embedder cannot prove exact input bound | New vector dispatch unavailable; old space/vectors preserved; no migration/fake fallback |
| Summary could understate historical sensitivity | Full preparation ceiling retained; negative summary test |
| Null schema could downgrade structured to plain generation | Explicit schema/capability validation before count; negative test |
| Missing endpoint limits could become a raw TypeError | Controlled configuration denial before remote count |
| Extra synchronous generation count could block the event loop | Streaming preparation offloaded; timeout remains bounded |
| Source revocation during extra generation count | Service callback before/after preparation and at physical reservation; zero delegate sends in negative test |
| Registry policy changes after preparation | Revalidate before physical reservation; count-only attempt in revocation test |
| SDK connection failure escapes one-attempt transport | Remediated in bounded transport; replacement-client and native/Python fence tests |
| Remaining optional factories construct Gemini directly | Remote branches now use canonical pair; references remain separately installed |
| Claims of paid/free production acceptance from mocks | Rejected; paid disabled, finite operator attestation required, live gates remain open |

Remaining limits: source checks and registry reads are not an atomic deployed
source lease. Rights/policy changes after final reservation cannot recall an
in-flight request. Operator attestations are trusted configured evidence, not a
live account/bill verification. No live non-Gemini counter, embedding counter,
production identity, physical deletion, native recovery or billing acceptance is
claimed. No independent review was performed here.

## P3 acceptance matrix

Every pass below is local/synthetic unless explicitly described as installed.
Exact commands, outcomes, failed runs and identities are in the JSON record.

| ID | Observation / remaining gap |
| --- | --- |
| P3-01 | Entry SHA/dirty state, pre-code hardening and user-directed gate exception recorded |
| P3-02 | Installed wheel/sdist probe exercises normal fake API/context with examples physically absent and no credentials; ports remain explicitly in-memory |
| P3-03 | Two different non-Gemini local fake identities execute canonical chat; live Groq/Cloudflare unsupported, not accepted |
| P3-04 | Closed operation selection, matched counters, explicit summary/extraction; embedding unavailable, no covert Gemini |
| P3-05 | Exact fake serialization/Unicode/schema and original Gemini matching; unknown/incompatible/missing counter fails before send; no remote estimate waiver |
| P3-06 | Separate summary task/count/send and full sensitivity test; existing branch/source compatibility retained; deployed source races open |
| P3-07 | No new embedding dispatch/space; original persisted identity and mismatch tests pass; approved embedding-input counter remains missing |
| P3-08 | Unknown/stale/future/expired tier/privacy/account/counter/quota denies; quota exhaustion/429/outage exercised; no fallback |
| P3-09 | Paid/mostly-free explicitly denied; USD authority/reservation/reconciliation unsatisfied and not accepted |
| P3-10 | Operator literal catalog only; PI-2 authentication/app/workspace/client claim isolation and unchanged v1 contract exercised |
| P3-11 | Separate canonical count/generation/summary attempts/reservations and confidence tested; extraction uses existing task port; embedding has no send/attempt because unavailable |
| P3-12 | Concurrent distinct profiles, wrapper cancellation/missing terminal, SDK retry prevention, canonical original-key replay, and existing PI-2 unknown-outcome cases |
| P3-13 | Source/policy changes during count/pre-reservation and original PI-2 per-delta/completed replay fences retained; atomic deployed source lease open |
| P3-14 | Missing/untrusted profile/counter/credentials/current endpoint fail closed; no dynamic import/duplicate registration surface |
| P3-15 | Explicit legacy mocked transport, edit/regenerate, reference package and retained tasks, independently installed Reading Logbook/original v1 regressions |
| P3-16 | Frozen memory/actor/source/forget/receipt/context suites, unchanged memory flags and corpus/lock history; no MEM-3+ |
| P3-17 | macOS/CPython 3.11.15 OS/Python fences, artifact probes, dependency guard, lint/build/diff; Linux/Python 3.12/hosted CI not run |
| P3-18 | Live non-Gemini/provider/billing smoke not run; no separately verified authorization/cost/privacy environment |
| P3-19 | Core API/worker/research/optional factories audited; direct adapter constructors confined to compatibility/explicit experimental paths; no promotion |
| P3-20 | No durable migration/rekey; disable/drain new selection, retain all original keys, unknown reservations, receipts, branches and spaces; cloud rollback not exercised |

## Verification and failed-run history

Final inspected OS-fenced regression: **780 passed**, zero forbidden Python
network attempts, native IPv4/IPv6/Unix denial probes passed. The final focused
execution suite passed **38**; the owning gateway/execution OS rerun passed **113**.
`UV_OFFLINE=true UV_CACHE_DIR=/tmp/pi3-uv-cache make pi2-check` passed: installed
core **87**, optional references **190**, retained-task **56**, and independently
installed HTTP/client **64 passed, 1 skipped**. The skip is the existing source-only
second synthetic host; it is not an installed-consumer acceptance claim. Python
fences reported zero unexpected network attempts in these final installed runs.
The PI-2 target also rebuilt all wheel/sdist packages, checked the original v1
contract and dependency guard, and passed the 30-case non-promoting planner probe.
Backend/reference/logbook lint and `git diff --check` passed. The standalone
`platform-independence-check` target also passed; artifact hashes are recorded in JSON.

The OS/Python fence applies to the inspected PI-3 suite. PI-2/platform installed
probes retain their original Python-only fences; do not infer native isolation or
real-storage acceptance from them. The final repeatable PI-3 script is the exact
command behind `make pi3-check`; the final direct script invocation is recorded.

See [machine record](pi-3-verification.json) for final command results, source and
artifact hashes. No provider, cloud, native database or deployed identity check was
run. Frontend code did not change; frontend build/browser/device acceptance was
not rerun. The installed HTTP fixture uses synthetic signing keys/membership and
loopback, not real Google OAuth/IAM or production storage.

Failures were retained, not reclassified as passes: an initial edit helper used
an unavailable `python` executable; subsequent commands used the bundled venv.
The first focused run had six failures (fixture scope/repository/turn shape,
confidence vocabulary, constructor-time rejection, and a test patch targeting the
wrong counter method). Subsequent intermediate runs had four then one failures;
those fixture errors were corrected and the focused suite passed. Native probe
setup first failed because a nonexistent Unix path returned ENOENT before sandbox
policy evaluation; it now proves denial against a real temporary Unix listener.
The nested sandbox launch also needed execution outside the enclosing tool
sandbox; all network-denial policy remained enabled.

The first broad run had 658 passing tests and one inherited provider-matrix count
failure (77 synthetic rows instead of 80), plus three forbidden DNS attempts.
Isolated matrix rerun passed 17 tests; this does not establish a clock/root-cause
fix. A later broad run passed 716 pytest cases but the **target failed** because
its fence still detected the same three attempts. They were traced to the pinned
SDK replacement-client behavior and fixed, not waived. The owning transport/
execution rerun passed 113 tests with zero forbidden attempts. Final reruns are
recorded separately in JSON.

An initial `pi2-check` completed builds/offline installed portions but its loopback
fixture produced 45 setup errors because socket bind was denied (20 tests passed).
A subsequent attempt stopped at the intentionally strict stale source-binding
guard during final source edits. Neither run counts as a pass. The final source
binding was refreshed without changing any historical lock or fixture.

## Rollback and separate independent review

Stop/drain new sends, disable the selected profile or choose the last explicitly
approved compatible endpoint. Keep all conversation/task UUIDs, unknown attempts,
quota reservations, embedding identities, receipts and source fences. Read original
canonical status; do not choose a new key/provider after possible dispatch.

Commission a **separate session** against this single implementation commit.
Read the hardening/report/JSON and current state, rerun `make pi3-check`,
`UV_OFFLINE=true make pi2-check`, `make platform-independence-check`, lint and diff
checks. Independently attempt wrong-counter/schema/provider injection, stale
free/privacy facts, policy/source changes at reservation, SDK replacement clients,
uncertain-send replay and embedding-space bypasses. Verify historical fixture and
lock hashes and physical package absence. Review narrowed/blocked P3 rows without
calling them live acceptance. PI-4 requires its own authorization and unresolved
PI-0/1/2/3 independent acceptance remains open.

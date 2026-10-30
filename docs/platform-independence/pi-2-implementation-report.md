# PI-2 local implementation candidate

2026-10-30, America/Los_Angeles. Base/entry HEAD on `main`:
`2746ea711248603b484f5985ab561978c4ec34bc`. Tested source is that revision plus
this single implementation commit's runtime file identities, recorded in
[verification JSON](pi-2-verification.json). Resolve the exact target commit with
`git log -1 --format=%H -- docs/platform-independence/pi-2-implementation-report.md`.
The delivery message supplies its SHA. The report cannot embed its own commit hash.

The user explicitly authorized implementation despite pending independent PI-0/1
acceptance, no subagents, and one commit. All work, plan challenge, implementation,
verification and skeptical self-review occurred in this session. This is **not
independent signoff or release readiness**. The worktree initially contained only
untracked planning/review documents; they were preserved and excluded from the
commit. No push, deployment, real provider invocation, dependency download, cloud
credential access or native database mutation was performed. Hosted CI status was
unavailable (`gh run list --limit 3 --json headSha,status,conclusion,url` could not
connect); no passing hosted result is claimed.

## Design and delivered boundary

[Plan hardening](pi-2-plan-hardening.md) preceded code and records the trust model,
two registration and two client-binding alternatives, entry exception, revised
sequence and rollback. Existing catalogs were smaller than a new descriptor or
plugin framework. Verified Google public-client audience/azp binding was smaller
than generalizing signed service/task delegation to chat. Existing task identity
keeps its separate verified-service/body/replay restrictions.

There are three separately built distributions:

- **Core** retains principal mapping, scoped repositories, conversation/branch
  lifecycle, token-budgeted context assembler, provider/usage and source checks.
  Generic new behavior is client/app authorization, a metadata-only key-status
  read, safe external body bounds and a supported host metadata facade.
- **Trusted host** pins the core package and imports only
  `personal_ai.extensions.v1`. Existing explicitly selected application/context
  entry points declare Reading Logbook with history-only policy and independently
  checked exact issuer/subject/workspace membership. It contributes no source
  transport, domain schema, database, route, mutation, grant or memory intake.
- **Untrusted HTTP client** has no runtime dependencies and no platform/reference
  imports, copied platform schemas or checkout hooks. SQLite books/notes and the
  original-operation journal belong to the client. Only explicitly entered ask
  text is sent. A client-only interpreter without core/host executes the CLI.

The server verifies Google signature, issuer, allowed scalar audience, time,
verified email and principal directory before interpreting retained client claims.
An operator-owned bounded policy file binds exact audience and effective azp to
one application, with expiry and disable/revoke. The reserved builtin UI audience
cannot be reassigned by this policy. Its effective azp must match its audience;
canonical builtin/reference callers retain their existing selection behavior.
External owner/actor headers are rejected, JSON schemas forbid identity fields,
and independently installed workspace authority checks membership. The external
client is limited to documented create/list/get, context-preview, automatic
continue and original-key status routes. It cannot reach global/account/memory
administration, tasks, raw context inspection, legacy `/messages` or gated
external-turn preparation by changing headers or paths.

Policy is reread after signature-cache hits and before inference, model handoff,
completed replay and final commit. Workspace/directory/token expiry are rechecked
with it. Async stream checks use the existing I/O thread helper. Existing final
source-snapshot/disclosure revalidation remains intact. No newly granted
cross-app memory/profile/federation access is introduced. Operator files and
selected Python are trusted; clients cannot register plugins or edit policy.
These checks cannot recall context already sent or establish physical-send race
safety in production.

The [v1 contract](consumer-v1.md) and [generated OpenAPI](consumer-v1.openapi.json)
record actual models, middleware errors/limits, SSE schemas, request examples and
compatibility policy. Preview exports planner metadata only. A minimal
`GET .../continuations/{key}` reads existing canonical messages, including an
inactive branch; it has no provider dependency, new ledger, reservation, repair
mutation or migration. It reports not_found/in_progress/unknown/completed and an
optional message UUID. Existing deterministic assistant UUID derivation is shared
byte-for-byte with continuation execution. Original request/digest replay rules
remain authoritative. SSE is provisional until validated terminal, normal stream
exhaustion and matching durable status. There is no Last-Event-ID resume.

The CLI journals/prints the key before sending, refuses changed local intent,
keeps tokens out of the journal, follows no redirects/environment proxies and
requires HTTPS outside explicit numeric-loopback fixtures. Recovery observes the
original key and replays only canonical completion. Incomplete/failed/streaming
keys do not auto-send, refresh identity or mint a replacement intent.

## Observed acceptance matrix

Local results below are limited to inspected fakes and built artifacts. Exact
commands, artifact/fixture hashes, runtime and stdout summaries are in the
[verification JSON](pi-2-verification.json). No row closes independent acceptance.

| ID | Observed result / limit |
| --- | --- |
| P2-01 | Entry/source/dirty state, pending PI-0/1 and user exception recorded; same-session hardening completed before code |
| P2-02 | Core/reference/client/host wheel-from-sdist builds; fresh outside-checkout environments, no editable hooks or PYTHONPATH; client-only interpreter has no core/host/reference dependency |
| P2-03 | Separately installed selected fifth host; real HTTP and independent CLI workflow; no Reading Logbook conditionals/imports in core |
| P2-04 | Explicit catalog selection, unknown/duplicate/unselected loaders, invalid host contract/config; existing installed collision/registration compatibility tests preserved |
| P2-05 | Signed synthetic user creates/lists/gets exact owner/app/workspace records; same-owner other-app UUIDs and nonmembers deny |
| P2-06 | Valid fifth-client token cannot select builtin/unknown app; builtin client cannot select fifth app; no client header grants app authority |
| P2-07 | Wrong audience/azp/issuer, expiry, invalid signature/unsigned bearer, service email, unsigned delegation, forged identity and client-chosen membership deny; cached-token binding revocation fails closed |
| P2-08 | Metadata-only preview; history-only host, no raw memory/global-profile provider or federation choice access; inherited context/source and frozen memory denial regressions pass |
| P2-09 | HTTP continuation uses actual ChatTurnService/ContextAssembler with deterministic fake generation/counting/storage; retained manifests prove app/workspace and actual input budget |
| P2-10 | Fragmented UTF-8/CRLF, invalid/duplicate/missing/oversized terminal, delayed stream, abrupt disconnect and explicit client timeout remain unconfirmed unless canonical completion agrees |
| P2-11 | Identical-key creation and completed replay, changed input, racing create/continue, in-progress 409, lost terminal and client restart journal/status recovery; no second logical fake-model send |
| P2-12 | Provider failure/partial output, 429+Retry-After, storage/identity outage, malformed/revoked policy and authority revocation during counting fail safely; no false completion. Native storage crash/uncertain commit and OS-level provider-send races are unexercised |
| P2-13 | Local books/notes stay in consumer SQLite; explicit message only; no platform domain schema/store or memory expansion |
| P2-14 | Generated spec check and SSE conformance; original builtin/reference APIs tested. Additive status fields accepted; incomplete HTTP/JSON remains unconfirmed |
| P2-15 | Installed reference removal/restoration and original task keys; fifth host/client uninstall leaves core healthy; no data rekey or migration |
| P2-16 | Focused MEM-0/1/2 controls/forget/source/actor, branch, task receipts/fingerprints and scope regressions; PI-1 installed core/legacy profiles and zero import edges |
| P2-17 | Recorded source/artifact/fixture hashes and installed origins; final fenced commands have zero observed forbidden network attempts. Python audit hook does not cover arbitrary native/OS egress |
| P2-18 | macOS arm64/Python 3.11.15 observed. Linux/Python 3.12 and hosted CI remain **open**; CI artifact matrix now invokes pi2-check |
| P2-19 | Real Google login/client registration, private service IAM, deployed membership/revocation and production identity remain **open** |

The installed fixture patches only signing-key **transport**, not Google JWT
verification or identity middleware. It uses freshly generated RSA test keys,
synthetic claims, exact fake membership, a closed persistence factory and explicit
repositories/counter/model. All four original reference applications are
physically absent for PI-2; origins and dependency/entry-point metadata are
asserted. The separate stdlib-only client CLI subprocess also installs its Python
network fence. Dependencies are copied from the existing pinned environment,
excluding platform packages and `.pth`/editable hooks; this is package independence
proof, not fresh internet dependency resolution.

## Verification and failures retained

Final command results are recorded in the verification JSON:

| Final check | Observed result |
| --- | --- |
| Serial focused fake regression | 593 passed, zero blocked network attempts |
| Installed PI-2 HTTP/protocol | 55 passed: 35 real HTTP cases and 20 protocol/host checks; zero forbidden attempts |
| Installed PI-1 core / legacy / restored task-key subsets | 49 / 190 / 56 passed; core/worker/lifespan/uninstall probes passed |
| Core context / planner fixtures | 9 / 30 cases, non-promotion, zero planner/provider calls |
| Dependency/import inventory | Zero core/example/facade edges, no issues |
| Backend and client lint, whitespace, document links, recorded file identities | Passed |
| Preserved pre-existing fixtures and frozen migrations | 47 tracked files byte-identical to entry revision |

Main reproducible commands from repository root:

```sh
UV_OFFLINE=true UV_CACHE_DIR=/tmp/pi2-uv-cache make pi2-check
PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint
backend/.venv/bin/python -m ruff check examples/reading-logbook
git diff --check
```

The exact explicit fake regression file list is in the JSON, invoked through
`backend/scripts/pi1_offline_checks.py`. It covers auth/controls, application and
SQL scope, composition, memory knowledge/control/consumer/proxy, chat lifecycle,
external turns, task/delegation/receipts, federation, planning and Phase36. The
broad whole suite was deliberately not used as fake-only evidence: PI-1 already
records forbidden DNS attempts in that broader command. No native/cloud/manual
suite was run or silently converted to passing fakes.

Failures discovered and repaired in this session:

1. Two initial collection attempts used an incorrect summary-repository import;
   corrected to the actual fixture repository. Initial loopback binding
   was denied by the filesystem/network sandbox; allowed loopback execution was
   obtained for the synthetic runner. These were not passing HTTP checks.
2. A forged federation handle reached an unconfigured native PostgreSQL lookup
   in the first HTTP fixture (30 passed/1 failed). This attempt invalidates that
   run's hermeticity despite zero Python-audit events: native sockets are outside
   the audit fence. The fixture now rejects unconfigured persistence ports.
   External federation choices are denied before lookup. An initial over-broad
   denial broke one installed legacy federation test (189 passed/1 failed); the
   repair is scoped to the external lane and preserves trusted legacy resolution.
3. The strict planner correctly rejected changed source under v19. A new v20
   source-only binding preserves **all v10–v19 bytes**, configuration, corpus,
   fixture dependencies and non-promotion; runtime/source/current-or-direct-child
   guards were not weakened. No experiment was promoted.
4. Artifact helper discovery included uv's generated `.gitignore`; restrict
   inventory to wheel/sdist artifacts. A copied OpenAPI fixture used the wrong
   temporary root (50 passed/1 failed); fix the copy location. These helper
   failures were rerun rather than reported green.
5. Skeptical protocol review repaired malformed created-event handling,
   duplicate-assistant acceptance, incomplete HTTP/JSON normalization and an
   overly strict whole-object status comparison. Unknown additive status fields
   no longer break a valid completion. Added adversarial conformance checks and
   rebuilt/retested the affected client artifacts.

6. Overlapping verification runs exposed two deadline-sensitive fixture failures:
   the 50 ms chat protocol case expired during preparation (592 passed/1 failed),
   and an installed memory mock returned timeout (48 passed/1 failed). Neither run
   attempted forbidden Python network operations. The two owning files passed
   30 tests in isolation; a fresh serial full focused run passed **593 tests**
   with zero blocked attempts, without code/threshold changes. This is rerun
   evidence, not a demonstrated timing fix or proven root cause.

Self-review also inspected public/private imports, selected loader behavior,
reserved builtin audience, delegated task bypass boundaries, app/owner/workspace
scopes, policy rereads, async I/O, final source checks, stable UUID/digest bytes,
status read-only behavior, no-store headers and redirects/logging. No unresolved
material P0 was found in the bounded candidate. This is an implementer's review,
not an independent security verdict.

## Preservation, rollback and separate review

No existing migration, memory implementation, historical evaluation fixture/lock,
receipt/fingerprint, tombstone or schema-3 record format changed. MEM-0/1/2 flags
remain default-off; production-host, source/send fencing and tombstone/receipt
capacity blockers stay open. Tests with injected verified principals now supply
explicit verified client/expiry fields; their owner/actor/recent-auth assertions
remain intact. v20 only rebinds this candidate's source; no provider-neutral
composition, PI-4 sharing, PI-5 tools, MEM-3+, cloud IAM or domain feature was added.

Changed-file inventory and SHA-256s of runtime/fixture artifacts are in the JSON;
`git diff BASE TARGET --stat` is the definitive full inventory. Changes group as:
client-policy/auth claims and ASGI admission; generic context/send checks;
conversation/status/request/SSE contract; public host facade; two sample package
roots; test/build/CI scripts; auth compatibility fixtures; source-only planner
binding; root/index/current-state/contract/operations/review evidence.

Upgrade/uninstall/rollback is documented in the
[sample quickstart](../../examples/reading-logbook/README.md). Revoke policy and
membership, stop/drain ingress as appropriate, unselect/uninstall host and client,
and preserve all durable rows/scopes, original keys, journals and historical
reconcilers. There is no down migration, delete/rekey or replay-with-new-key step.
Already disclosed model input is irreversible. Real OAuth/native login, actual
private service invocation, native PostgreSQL/DynamoDB restart/races, real model
sends/cost, cloud recovery/deletion and production source revocation remain open.

The [separate independent-review prompt](pi-2-independent-review-prompt.md) names
the exact base/target resolution, commands, likely risk areas and obligations
outside the supplied matrix. PI-0/1/2 acceptance and all production/security gates
remain pending. No later phase is authorized by this implementation.

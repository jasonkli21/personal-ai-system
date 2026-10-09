# Phase 25.1 implementation and acceptance evidence

Date: 2026-10-09. Review baseline revision: **f98be4ec6037596cd603fe278e88d1308b1437f8**.
Contract/design commit: 6fe8898. The original implementation verification below
covers runtime revision 4ff5ee445b1f3c2779dd29a723e01afacd675d45; review-fix checks
cover the baseline plus the complete review-fix source changes documented here.
Those reviewed changes were committed together as one commit after checks.
Existing untracked independent-review documents were preserved.

**Disposition: local implementation verified; full Phase 25.1/live acceptance remains
open.** No real ChatGPT account, reusable provider credential, provider request, cloud
resource, database migration, or application workflow was used or enabled.

## Architectural model and rewrite-risk review

Read the [architecture model](phase-25-1-architecture.md), written before substantive
runtime implementation, and [operator/interface guide](phase-25-1-implementation-guide.md).
The implementation was checked against the current P10 persistence cutover, P11–15
context/policy boundaries, P16 neutral inference contracts, P18–24 routing/accounting
ownership, and downstream P25.2–25.4 plans.

The bridge consumes a bounded prepared value and emits neutral generation events.
It does not build context, authorize cloud sources, persist conversations, route
automatically, manage a quota ledger, or orchestrate domain actions. Shared policy
and the P12 builder remain future cloud preparation authority. Existing DynamoDB
turn transactions remain canonical conversation authority. Postgres remains the
future store for permitted safe connection/control metadata; no managed store was added.

Generic seams extended additively:

- ChatMessage accepts developer instructions; existing messages/adapters remain functional.
- GenerationMetadata has optional execution provenance. ExecutionProvenance and
  ExternalCompletion distinguish connected observations from credential-free manual
  declarations and reject fabricated connected identity/usage for manual results.
- PreparedExecution extends existing application scope and validates InferenceContext.
  It binds branch/source-authority digests, scoped reservation, provider/model/connection
  revision, exact messages, sensitivity/policy and limits. This is a connected execution
  value, not a new prepared-turn repository or prerequisite for manual persistence.
- DispatchGrantVerifier checks a provider-neutral, domain-separated Ed25519 format
  against pinned local issuer/key/runtime/caller authority. It revalidates typed values
  and binds the whole canonical package. Cloud issuance is absent until Phase 25.2
  can authorize and reserve the canonical turn.

No foundational orchestration or persistence abstraction changed. The local receipt
is an execution-boundary replay fence, not a second cloud turn state machine.
P25.2 must bind it to existing scoped turn reservations and treat client-reported
output as an observation rather than server-verified billing evidence.

Alternatives considered: ordinary LiteLLM API-body translation cannot safely represent
restricted SIWC requests without unverified semantics; Codex app-server adds unneeded
tools/history orchestration. Direct supported Responses transport therefore lives in
the provider adapter behind the narrow bridge. Protected POSIX files use the documented
local storage option; unsupported platforms fail explicitly. Pinned asymmetric proofs
avoid sharing a cloud signing secret or forwarding Google/IAM tokens. Optional ID-token
hints are omitted rather than putting retained tokens into browser URLs/history.
Distribution, plan-only billing and native transport uncertainties leave live gates closed.

Rewrite-risk conclusions: responsibility remains in the appropriate layer; applications
can use the same scoped proof/output contracts, and future connected providers can supply
their own adapted transport without changing cloud conversation control flow. Manual
results need no bridge/account. Provider protocol stays out of generic policy/routing.
Future phases must extend shared policy/context/conversation seams rather than copying
the bridge into managed services. Proof/package versioning and conservative receipt
retention remain explicit compatibility/operational concerns, not retry permission.

## State, concurrency and external effects

| State | Canonical owner / behavior |
| --- | --- |
| Host/runtime UUID, client and verified issuer/subject | Protected local store. Host identifies installation; client binds provider registration/workspace; subject identifies verified account. Random connection/runtime references alone cross the caller boundary. |
| Access/refresh/ID tokens and scopes | Protected local credentials. No browser/cloud response, API key, Secret Manager or managed repository path. |
| OAuth state/nonce/PKCE | Process-local, bounded, expiring and one-use. Returning sign-in matches selected client/account/revision; disconnect invalidates pending reauthorization. |
| Rotating refresh | Cross-process lock, durable marker before IO, atomic full replacement. Terminal revocation clears tokens; temporary failure retains them; uncertain rotation/crash/persistence requires reauthorization. |
| Connection lifecycle | Connected, disconnected, permission-required, unavailable, configuration-error or reauth. Reauthorization/disconnect advance revision; rotation preserves it. Local disconnect and remote revocation confirmation are separate. |
| Caller pairing | Local approval for exact origin/connection revision; five-minute capability; hashed memory-only lookup. Restart drops sessions. |
| Compatibility/privacy | Protected local evidence tied to connection/client/model/distribution/expiry. Package denial precedes refresh; verified client is checked after credential resolution. Defaults deny. |
| Physical send | Scoped owner/app/workspace/conversation/reservation digest, independent of proof ID. A typed pre-send claim is recoverable after a process crash; the locked send-start transition occurs only after the final authority and connection checks. |
| Send settlement | Known terminal outcomes settle and are available to the paired caller for reconciliation/acknowledgement. Generic server/gateway failures, terminal loss, timeout, cancellation, protocol/output cutoff or credential echo remain send-started and single-use. No retry/fallback/output replay. |
| Turn, active branch, source authority and domain actions | Existing cloud/application owners. No bridge implementation or bypass; cloud issuance/finalization remains P25.2 work. |

Atomic replacement plus file/directory fsync is tested through injected persistence
failure; real power-loss/filesystem behavior remains unverified. Typed hash/status
receipts cap at 4,096. Uncertain sends are never evicted; settled receipts are
collectible after proof expiry and caller acknowledgement or a 24-hour terminal
retention interval. A persisted clock high-water mark prevents proof replay after
clock rollback. Deleting state is not recovery. A durable admitted send cannot be
undone by disconnect; revision/expiry checks stop further output.

## Independent review disposition — 2026-10-09

The current post-implementation handoff was reviewed as a finding set; its process
instructions were treated as document context, not as authority to broaden the task.
An independent code pass confirmed the major lifecycle, profile-binding, streaming,
recovery, and state-migration issues and checked for additional correctness/security
gaps in the touched store, runtime, OAuth lifecycle, HTTP routes, and provider parser.
No unrelated cleanup was added.

| Finding | Disposition |
| --- | --- |
| F1 — settled receipt capacity exhaustion | Fixed: settled receipts are collected only after proof expiry and acknowledgement or 24-hour terminal retention; unresolved send-started receipts remain fenced. |
| F2 — “unknown” before final no-I/O checks | Fixed: claimed_pre_send and send_started are separate durable states; the latter follows final checks under the pre-send lock. Orphaned pre-send claims recover as not_sent only once the process lock is free. |
| F3 — no safe recovery surface | Fixed: active pairing capability plus persisted exact origin, connection revision, dispatch identity and fingerprint scope reconcile/terminal acknowledgement. After restart and re-pairing to the same origin/revision, a caller can recover terminal status without resending; another allowed origin cannot read that receipt. Status only is returned. |
| F4 — terminal parsing waits for EOF | Fixed: a validated Responses terminal is emitted immediately and closes the stream. |
| F5 — refusal/reasoning content parts rejected or refusal deltas misclassified | Fixed: refusal deltas/finals are visible assistant output; refusal and reasoning content parts are accepted; reasoning text is withheld. |
| F6 — missing exact Phase 18 execution binding | Fixed: PreparedExecution schema v2 and the local compatibility gate carry and compare endpoint, deployment, serializer, runtime, and model identity. |
| F7 — provider recovery facts discarded | Fixed: safe bounded status, code, parameter, request ID, and response-shape facts are retained without diagnostic body text. |
| F8 — external live acceptance absent | Remains explicitly open: real-account interoperability, plan-only/no-credit enforcement, hosted distribution, native browser/PNA, mobile, cloud, and provider checks were not claimed or enabled. |
| F9 — compatibility gate too broad | Fixed: gates select an exact model and profile identity; provider transport support is checked before credentials are used. |
| F10 — no safe account label | Fixed: a bounded verified email/name label has a short connection suffix; subject and credential values remain private. |
| F11 — consent and OAuth retry recovery | Fixed: plan-use scope can be requested only through explicit operator action with prompt=consent; transient revocation has bounded retries; invalid_client becomes non-retrying configuration_error. |
| F12 — stale pairing could read /connection | Fixed: connection reads enforce the paired revision and return bridge_connection_changed when it is stale. |
| F13 — no receipt schema migration | Fixed: v1 state migrates atomically to v2; legacy unknown statuses remain send_started and credentials/terminal facts are retained. |
| F14 — receipt state was untyped | Fixed: LocalState receipts validate a typed DispatchReceipt with explicit status, scope, claim, proof-expiry, terminal, and acknowledgement fields. |
| F15 — fake implied integration authority | Fixed: FakeChatGPTPlanBridge is documented as an output-contract-only fake; authorization integration uses LocalChatGPTBridge with synthetic I/O. |

The additional pass found one consequential edge within F3: receipt lookup originally
used the random per-process caller ID, which prevented a fresh pairing from recovering
the same authorized origin's receipt after runtime restart. The receipt is now scoped
to its persisted origin and connection revision, while the new active pairing
capability authenticates each lookup. Tests cover same-origin recovery after restart
and reject a different allowed origin. Tests were also added for the HTTP recovery
routes and stale connection revision, receipt capacity/migration, pre-send recovery,
explicit OAuth consent, profile binding and terminal/refusal event behavior.

## Work-package coverage

| Plan package | Local code/evidence | Remaining acceptance |
| --- | --- | --- |
| P25_1.0 | Dated official SIWC revalidation, restricted transport decision, exact peer/Host/Origin/pairing/capability checks; closed PNA and plan/distribution gates. | Hosted approval, enforceable account/model plan-only/no-credit control, real browser mixed-content/PNA and native mobile. |
| P25_1.1 | Provider OAuth; protected store/lifecycle; pinned dispatch proof; independent fake; generated JWT/JWK and lifecycle fixtures. | Real registration, scopes/identity/workspace, refresh and revocation interoperability. Cloud issuance belongs to P25.2. |
| P25_1.2 | Account-visible models; versioned text-only serializer; non-persisting streaming; bounded HTTP/SSE; strict terminal/model/text/usage validation and errors. | Real discovery/Responses/limits/wire compatibility and billing eligibility. |
| P25_1.3 | Safe outputs/representations/errors, split-delta echo guard, operator/callback fixtures, fake/neutral contracts, process contention/restart. | Native browser storage/history/logging/callback, device backup/disk protection, deployed no-token inspection and independent review. |

Implementation resides in backend/src/personal_ai/llm/chatgpt/, local_bridge/,
llm/external.py, llm/client.py and auth/dispatch_grants.py. Dependencies add maintained
PyJWT/cryptography support. No frontend code, managed composition, migrations, registry,
quota ledger, evaluation runner or application workflow changed.

## Verification

Configuration: macOS/POSIX, Python 3.11.15, locked backend dependencies; synthetic
accounts/keys/transports only. Local test directories and generated keys are ephemeral.
Frontend checks used the bundled Node runtime. The following original implementation
checks covered runtime revision 4ff5ee445b1f3c2779dd29a723e01afacd675d45. Frontend and
evaluation commands were not rerun for the review-only backend changes.

| Command / check | Result |
| --- | --- |
| make backend-test | **1246 passed, 76 skipped**, 2 dependency warnings. Skipped persistence/provider/manual tests remain unverified. |
| Focused pytest tests/test_chatgpt* and tests/test_external_execution_contracts.py | **137 passed**, 1 Starlette/HTTPX deprecation warning. |
| make backend-lint | Passed. |
| Ruff formatting check on contracts/runtime/fixtures | Passed. |
| UV_CACHE_DIR=/tmp/personal-ai-uv-cache make backend-build | Passed: source distribution and wheel. Default user-cache sandbox access failed; writable cache resolved it. |
| make frontend-test | Passed: **98 tests / 19 files**. |
| make frontend-lint frontend-typecheck | Passed. |
| make frontend-build | Passed; existing Next ESLint-plugin warning remains. |
| make context-eval context-plan-eval quota-scarcity-eval cascade-eval | Passed existing synthetic baselines; no provider/emulator/cloud acceptance inferred. |
| python -m personal_ai.local_bridge --help | Passed CLI import/argument smoke check. |
| Composition/source inspection and safe-output fixtures | Bridge absent from managed API/worker/settings/automatic provider composition; returned state/provenance/events/errors exclude tested credentials/account material. |
| Documentation links/content and git diff --check | Passed for changed documents/diff. |

### Review-fix verification

Tested source revision: baseline f98be4ec6037596cd603fe278e88d1308b1437f8 plus the
complete review-fix source changes in this commit. Documentation evidence was
finalized after the checks; implementation and tests were unchanged.

| Command / check | Result |
| --- | --- |
| `UV_CACHE_DIR=/tmp/personal-ai-uv-cache uv run python -m compileall -q src/personal_ai` | Passed. |
| `UV_CACHE_DIR=/tmp/personal-ai-uv-cache uv run python -m pytest -q` | **1266 passed, 76 skipped**, 2 existing dependency warnings. Skipped persistence/provider/manual checks remain unverified. |
| `UV_CACHE_DIR=/tmp/personal-ai-uv-cache uv run python -m pytest -q tests/test_chatgpt* tests/test_external_execution_contracts.py` | **157 passed**, 1 Starlette/HTTPX deprecation warning. |
| `UV_CACHE_DIR=/tmp/personal-ai-uv-cache uv run ruff check .` | Passed. |
| Ruff format check on modified runtime/store/test files | Passed: 6 files already formatted. |
| `UV_CACHE_DIR=/tmp/personal-ai-uv-cache make backend-build` | Passed: source distribution and wheel. |
| HTTP reconciliation/acknowledgement and stale-pairing tests | Passed through the loopback FastAPI test client; no provider/browser account was used. |
| `git diff --check` | Passed. |

Fixtures cover nonce/state/issuer/audience/client/account/scope/key mismatch, public
PKCE/discovery capabilities, refresh/revocation/rotation persistence, denial before
refresh, literal IPC authorization/PNA denial, edited/expired/foreign proofs,
model churn, unsupported tools/fields, terminal loss/post-terminal events,
compression/oversized/malformed streams, deadlines/cancellation, split credential
echoes/model labels, and unknown-dispatch restart fences. Two real spawned local
processes contend for one durable claim; only one wins. Other provider/browser/HTTP
behavior uses synthetic transports/controllers.

During final review an older 503 fixture expected generic unavailability rather than
unknown physical outcome. It failed after the conservative semantics change, was
updated, and focused/full regressions above were rerun successfully. No unresolved
failure is suppressed.

## Open gates and reviewer challenges

- This repository has **not established an enforceable plan-only/no-credit control**.
  Never turn a documentation assumption or synthetic fixture into a positive attestation.
- Hosted distribution approval is unverified. Public-client code alone does not establish
  the project's open-source distribution eligibility. See the dated
  [official sources](phase-25-1-architecture.md#external-gates-and-alternatives).
- Challenge strict OIDC/JWKS/audience/client/scope/discovery and Responses assumptions
  against a real approved account/runtime. Drift fails explicitly, never via fallback.
- Native callback/loopback binding, Origin/Host, PNA/mixed-content, interruptions and
  token non-exposure require opt-in end-to-end testing. Synthetic CORS proves no
  browser capability. Mobile remains unverified.
- POSIX permissions are not a keychain, encryption, backup exclusion or protection
  against a compromised same-user process. Device and filesystem crash protections
  need independent review before personal data.
- Challenge refresh uncertainty and durable claim/send boundaries: crashes, clocks,
  disconnect races and receipt capacity. A local fence cannot atomically commit remote IO.
- P25.2 must issue grants only through current shared membership/source/sensitivity
  checks and canonical branch reservations. Replay/finalization/revocation remain in
  existing turn transactions. A valid signature is not itself policy.
- Bridge-observed provenance is trustworthy only inside the local boundary.
  Browser reports cannot establish server-authenticated identity, billing, quotas
  or retention rights.
- P25.3–25.4 must preserve credential-free manual provenance and shared authorized
  continuation/domain hooks; P30/31 retain derived-context revocation and authoritative
  domain mutation. No independent reviewer was run as a subagent in this task.

The root README, router and living current-state record were reconciled. The plan
remains a requirement document; unmet external acceptance is not recorded as delivery.

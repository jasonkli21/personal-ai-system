# Phase 25.2 implementation guide

This phase implements an internal, gated external-turn state machine. Its review
fixes tighten idempotency, authorization replay, provenance, account model
selection, output bounds, and completion lifecycle. **The phase remains incomplete**
until Phase 15 supplies authoritative pre-retrieval and revocation checks and the
canonical DynamoDB behavior is tested against an isolated engine. Do not compose an
HTTP issuer or Phase 25.3 UI/API on the current authority callback. See the
[architecture and rewrite-risk review](phase-25-2-architecture.md) and
[verification evidence](phase-25-2-implementation-evidence.md).

`contracts.execution.ExecutionChoice` selects automatic, connected-provider, or
manual-external execution. `ContinuationRequest` binds canonical intent—including
content, execution choice, and active-turn narrowing—to its idempotency key.
Ordinary continuation enters `ChatTurnService.continue_turn`; external choices
enter `ExternalTurnService.prepare`, which delegates to the same chat preparation
machinery. Same-key retries resume a partially persisted preparation and changed
intent fails. A completed automatic same-key retry replays the committed turn.
Provider choice never authorizes disclosure.

Compose external preparation with the same conversation/message repositories,
resolved authenticated application context, planner, registered context providers,
and permission revalidator. Use `EstimatedTokenCounter` and no summary generator.
`ExternalTurnAuthority` remains a required but unimplemented production
integration: a post-assembly recheck alone cannot prove denial before context or
memory retrieval. Phase 15 must provide the canonical pre-retrieval membership,
source-access, grant, and revocation seam and retain a freshness check before
disclosure/replay. No permissive implementation is included. Default app policies
allow no external modes.

Register exact P18 endpoint profiles and access/data-use policy. Explicit endpoint
choices use shared fact-based registry admission and revalidate the exact profile
version/body, never a provider/model name alone. A connected request carries a
separate account-discovered `model_id`; the profile identifies the stable transport,
serializer, runtime, and data policy. The local bridge must confirm that selected
model is still visible and compatible immediately before physical send. ChatGPT
plan use requires public-client OAuth, explicit selection, user-local credentials,
account-specific discovery, subscription cost, automation exclusion, and no
hosted history. Do not register it as a P19 strict-free bucket or route it through
automatic evaluation/fallback.

A prepared result contains transient exact messages, an estimated count label, the
canonical reservation, and either a versioned connected package or a portable
manual prompt. The package binds a character limit aligned to canonical message
storage and a separate transport-byte limit; the local bridge enforces both.
Connected dispatch requires a server-only `DispatchGrantSigner` with a pinned
public verifier at the bridge. The service signs only after policy/profile checks
and returns proof only after branch/message CAS. Keep signing-key custody outside
source code and out of browser/bridge credentials. The bridge still owns its
authenticated physical-send fence, credential-echo guard, and immediate
compatibility/model checks.

Manual import requires an explicit import action and the matching prepared
reservation/fingerprint. Optional provider/model labels arrive at import and are
user-declared, unverified facts; they cannot claim model verification, account,
billing, usage, or latency. Connected completion metadata must match the reserved
producer, selected account model, connection and source snapshots; it remains
client-reported, not server billing/model evidence. `report_failure` uses the
shared bounded external-failure taxonomy and stores only safe client-reported
status/latency. It does not change uncertain external-effect semantics.

Connected prepared-turn lifetime is separate from the short-lived (at most
120-second) dispatch proof. Manual import reservations have a bounded 24-hour
lifetime. Both modes recheck current authority at finalization; completed-result
replay rechecks current visibility without requiring the original dispatch TTL.
Abandonment and stale recovery preserve terminal fences with empty text. All
successful modes invoke the shared post-completion lifecycle once after the
canonical completion CAS.

Safe local connection projections retain coarse usage/recovery hooks
(`local_operator`, `local_operator_new_pairing`, `provider_account_ui`). No URLs,
auth secrets, or reset guesses are copied to managed metadata. Account/scope/model
changes require fresh preparation; connection revisions invalidate local pairing,
and prior completed producer attribution remains immutable.

Focused offline policy, provenance, lifecycle, replay, and continuation tests cover
the local behavior. `tests/persistence/test_external_turns.py` supplies opt-in
DynamoDB race/restart/expiry checks using
`PERSISTENCE_TEST_DYNAMODB_ENDPOINT`. Synthetic tests do not establish target-store,
provider, browser, cloud, or account acceptance.

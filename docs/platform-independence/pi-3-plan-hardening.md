# PI-3 pre-implementation hardening

2026-10-30. Reviewed HEAD `0dbe7406fda20c58c784339647ca15c4c7ab3f7e`.
Written before runtime edits, in the implementing session; no delegation.
Entry status: no tracked edits; fourteen pre-existing untracked planning/review
files (including the supplied PI-3 plan/prompt) are preserved and excluded from
the implementation commit. PI-0/1/2 independent acceptance remains pending.
The user's PI-3 request is an explicit phase-entry exception, not acceptance.

## Findings and decisions against the supplied plan

1. The named API factories exist. Worker `_components` and research
   `compose_research_inference` also construct Gemini directly. Chat dispatch is
   `services/chat/service.py`, not a second provider loop. Keep it and the
   assembler, PI-2 original-key journal/status and SSE fences intact.
2. Existing `EndpointProfileResolver`, `EndpointRegistry.revalidate`, P19
   reservations and bounded LiteLLM physical transports already provide the
   required endpoint and ledger seams. A new router/ledger/dynamic factory loader
   is unnecessary. Use a closed, versioned operator profile selection, neutral
   generation/count pairs, and a small admission facade delegating to these seams.
3. Groq/Cloudflare have generation but no same-serialization authoritative
   counter. UTF-8 bytes do not prove a provider token upper bound (hidden framing,
   transforms and special tokens remain unverified). Reject these profiles before
   any remote count/send. Do not change `preparation.py` or `DeadlineCounter`.
   Two distinctly identified local fake profiles may prove canonical composition;
   they cannot establish live non-Gemini compatibility. Their deterministic local
   serialization uses byte units and is authoritative ONLY for that fake runtime.
4. P19 reserves tokens/quota units, not audited USD prices and period spend.
   Paid/mostly-free modes will be recognized but denied unconditionally. Neither
   dual consent alone nor a settings cap establishes an enforceable monetary cap.
5. Existing fixed Gemini transport admission is primarily quota accounting;
   privacy/strict-free facts must also be checked before ancillary count and again
   at the physical reservation. Require an approved, current account-specific
   attestation and policy even for public data; no implicit free branding.
6. Summary currently uses base sensitivity rather than all reused history's
   sensitivity. Do not allow a separately selected weaker provider. Bind summary
   to the same exact chat profile and use the full preparation sensitivity.
   Run the summary request through its own bounded preparation/usage task.
7. Keep embedding identity, normalization, tasks and version in the original
   Gemini embedder. Selection is independent and explicit; offline profiles do
   not construct Gemini memory. No new vector space, migration or re-embedding.
   Default embedding profile is unavailable; existing memory flags remain off.

## Operation/capability matrix and active-send audit

| Surface | Selection / capability | Admission / limitation |
| --- | --- | --- |
| Normal API chat, edit/regenerate, PI-2 automatic continue | offline_fake, offline_fake_alt, legacy_gemini; streaming + exact counter | canonical ChatTurnService/ContextAssembler; no fallback |
| Context count | same exact profile/model/serializer; token_counting | local fake units or strict Gemini count; source authorization precedes preparation |
| Conversation summary | disabled or same chat profile; bounded_generation + count | separate task/count/send; full history sensitivity; incompatible provider selection denied |
| Existing extraction | disabled or explicitly selected legacy_gemini; structured_generation + count | existing bounded extractor, separate task and schema capability; no new intake |
| Existing memory query/document embedding | disabled or explicitly selected legacy_gemini | original persisted space only; separate endpoint/usage; unknown default endpoint facts deny |
| Worker lifecycle embedding/extraction | same memory composition | existing worker gates and source fences; no Gemini fallback |
| Research synthesis | same normal pair for remote; existing literal fake research | existing research assembler and source checks; search remains its separate registry |
| External manual/connected turns / local bridge | existing explicit gated contracts | no promotion; external assembler remains local count/no summary |
| Cascade/provider matrix/evaluation | existing opt-in constructors and guards | experimental, not normal core; fixture semantics unchanged |
| Optional reference apps | booking/itinerary API factories use the canonical pair for their gated remote branch; explicit task-specific local fakes remain | remain separately packaged; no imports added to core |

## Counter, disclosure and cost invariants

Remote preparation retains exact authoritative identity requirements. No estimated
remote counter is admitted. Before a counter receives source text, check capability,
policy, profile version, privacy sensitivity, current free attestation and configured
input ceiling; at physical reservation recheck the same requirements against the
current registry before delegating to P19 atomic quota admission. Generation also
prepares its own exact input (including structured schema) before dispatch.
Unknown/stale/free-tier/quota facts deny; cancellation, 429, outage, missing terminal
or unknown outcome never selects a second endpoint. Attempt attribution stays in
existing LiteLLM/P19; offline fakes have estimated output usage and no physical
provider billing attempt. No prompts/secrets enter new diagnostics.

Source rights remain under existing assembler/consumer checks. Those checks and
registry reads cannot prove an atomic deployed source/transport fence; retain that
external gate. Policy and quota mutations after the final reservation remain an
in-flight race, not retroactive cancellation. Explicit profile changes require
request re-composition; retain original keys after any possible dispatch.

## Implementation sequence and verification

1. Add bounded settings and `llm/execution.py` for closed composition, fake matched
   counter, canonical registry admission, physical-reservation facade and disabled
   paid selection. No SQL migration or public HTTP field.
2. Parameterize neutral summary and existing memory composition. Wire API, research
   and workers. Fix summary sensitivity propagation without widening source access.
3. Add `test_inference_execution.py` covering distinct canonical fake streams,
   unsupported counters/profiles/modes, privacy/attestation/stale-policy/physical
   reservation failures, summary and extraction capabilities, embedding identity.
4. Add `pi3-check` with Python and native persistence fences; reuse PI-1/2 artifact
   checks and original contract. Run relevant chat/context/memory/provider/routing
   suites serially, lint/build/dependency guard and diff checks. Preserve every
   failure and distinguish synthetic, installed, native and live evidence.
5. Review complete diff adversarially, remediate and rerun owning checks; record
   P3-01–P3-20 plus source/runtime/artifact hashes in report and JSON. If the strict
   planner guard requires a new source-only lock, preserve historical bytes and
   bind a new version with unchanged cases/configuration/non-promotion.

Rollback disables new profiles/drains sends and explicitly selects the last safe
compatible profile. Preserve all rows, scopes, source fences, receipts, embeddings,
unknown reservations and continuation keys. No push/deploy/live provider operations.
Independent review, Linux/Python 3.12, live non-Gemini counters, billing, source leases,
MEM/Phase36 and cloud/native acceptance remain separate gates.

## Implementation deviations and self-review follow-through

The generic embedding port is installed as explicitly unavailable: even the old
Gemini embedding transport has no approved exact embedding-input counter. Retaining
its raw constructor does not justify normal disclosure or invent a new space.
The original direct adapter is unchanged for compatibility/opt-in evaluation;
normal worker/API composition never falls back to it. This deliberately narrows
P3-07/P3-11 acceptance rather than silently using a character estimate.

The closed catalog replaces a proposed extensible adapter registry: there is no
dynamic import or duplicate factory registration surface. FastAPI caches one
exact pair per request; direct Python composition uses the same builder.

Self-review added a source-disclosure callback across chat's provider preparation
and physical reservation, offloaded synchronous stream preparation from the event
loop, corrected summary sensitivity to retain the full preparation ceiling,
refused null structured schemas before counting, and made missing endpoint bounds
a controlled configuration denial. Tests cover these negative cases. Existing
assembler/summary source checks remain non-atomic; this is not a deployed source
lease, cross-process policy linearization or recall of already disclosed data.

The strict planner source guard requires v22 because all backend source bytes are
bound. v10–v21, the held-out corpus, fixture dependency bytes, planner configuration
and non-promotion are preserved; v22 pins entry HEAD plus the final source digest.
The final report records all failed runs, self-review dispositions and reruns.

The full native/Python fence exposed a pinned LiteLLM AsyncHTTPHandler retry on
ConnectError/RemoteProtocolError that escapes its injected bounded client despite
zero retry flags. Production bounded transport now converts those errors to its
own safe fault before the SDK sees them. The strengthened gateway test observes
replacement-client construction, not merely calls to a mock transport; isolated
OS-fenced verification passes with zero DNS/network attempts. This is a remediation
of a discovered dispatch bypass, not a network-fence waiver.

The final optional-package audit located direct Gemini construction in booking and
itinerary API factories. Their gated remote branches now use `compose_pair` too;
the task-specific explicit local fake branches and existing feature gates remain.
No example package became a core dependency.

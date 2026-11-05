# RE-2 implementation decisions

The starting revision was `d063980bd588f94194c55918be06b722ccf7adde`, tree
`fab3a2ae5f40c2c738e5624c852ca26fc694c3c6`. The working tree already held a
PRD move and six untracked planning handoffs. Those changes stay outside the
implementation commit. The moved PRD supplied the planning context.

The new catalog has a separately versioned `tool-verify-pure.v1` strategy
with a closed arithmetic predicate and read-only effect. The historical
proposal-only catalog and frozen comparators retain their version identities.
Typed synthetic integer requirements give the four templates objective
sufficiency criteria without granting source, tool, or spend authority.

The internal host profile uses the existing PostgreSQL workflow intent,
row lock, claim, fence, reservation, dispatch, progress and terminal
transitions. Chat owns each deterministic continuation message identity and
uses the shared context assembler and selected inference lane. The installed
offline fake binds its terminal physical receipt to the reservation. No
provider ledger entry is applicable to this in-process fixture.

## Operator use

Construct the [workflow service](../../backend/src/personal_ai/workflow/README.md)
with an explicit `ReasoningHost` and enable it for a synthetic local/test
request. Use the verified request context, a live authority callback and
registry, and explicit application, workspace and user ceilings. Use a
disposable PostgreSQL database with the repository's normal migrations. The
internal `reasoning-run-request-v1` carries a UUID original key, typed arithmetic
requirements, effort, strategy and finite limits. Ordinary requests select
`auto`. The comparator pin requires trusted host configuration.

| Strategy | Compiled path |
| --- | --- |
| Direct | Answer and validate typed slot coverage. |
| Decompose | Two or three independent slots, synthesis and coverage check. |
| Critique and refine | Draft and objective defect check. Revise once and check again only for a measured defect with budget. |
| Pure tool verification | Verify the proposal against the registered arithmetic predicate. Accept, repair once and recheck, or abstain. |

The plan reserves capacity for synthesis and its verification before admitting
a decomposition. All model steps have fixed per-step byte and local count
ceilings. These are exact bytes in the installed fake's serializer and do not
estimate a vendor tokenizer. No verified predicate, unresolved ambiguity or
an exhausted mandatory envelope yields a closed refusal. An unparseable
proposal yields an inconclusive check. Partial results contain only verified
slots. Each run has at most five planned steps, depth three by dependency edges,
one step in flight, four inference calls, two pure checks and a 30-second
deadline. The workflow allows one replacement claim for pre-dispatch recovery.

The original request key and scoped request digest identify intent. The
versioned compiled plan, step, operation, fixture and empty source set are
pinned independently. An inference reservation also binds the installed
endpoint, canonical continuation message ID, child key and child request
digest. A pre-dispatch recovery reuses those child bindings. Unknown dispatched
inference remains `uncertain_effect` with an unknown physical-attempt count and
is never resent. Dispatched registered pure checks consume verifier budget
conservatively and may be recomputed after lease recovery only under the same
plan and when the finite verifier envelope permits it. Cancellation during a
pure check settles as canceled and suppresses output. Reported synthetic
input and output bytes come from the matching terminal operation receipt.
Count reservations and successful exact byte measurements are persisted
separately. Provider reservation, settlement and cost stay null.

Only typed synthetic operands and bounded numeric checkpoints are kept while
the run is active. Checkpoints and the spec clear at terminal commit. Verifier
attempt receipts retain a versioned verifier ID, objective verdict, bounded
defect count and sufficiency decision. These are additive optional fields; old
v1 progress payloads and rows without the extension still decode. Older
database versions and backups may contain the synthetic typed data. Events and
receipts contain no prompts, raw fixture outputs, results or source text.
Verified answers are live-only. Replay returns redacted status and receipts
under current verified scope and emits no answer bytes.

## Rollback

Stop new admissions by omitting the reasoning host or disabling its workflow
service. If draining is necessary, use the original scope and cancel queued or
reserved work. Keep uncertain attempts and all original keys for observation.
Return callers to the established direct continuation or retrieval workflow
profile. The additive JSON format uses the existing table and requires no
migration or data rewrite. The synthetic profile is outside episode capture
and carries no memory or external source dependencies.

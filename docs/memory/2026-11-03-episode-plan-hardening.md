# MEM-3 plan hardening and development decision

The structural-only implementation boundary below is superseded by the
[authorized local extension](2026-11-03-episode-extension.md). Historical checks
and findings remain as originally recorded.

Date: 2026-11-03 (America/Los_Angeles). Status: accepted for the bounded
implementation below; independent review pending. Entry HEAD:
`42f00b0f93b0987f615657d4d8b9c145c6c6b016`, identical to the handoff pin.
The owner's direct implementation request explicitly unfreezes E0/E1 local
synthetic/source-only development. It does not authorize live/private capture,
external disclosure, production promotion, or MEM-4. No agents are delegated.
Six pre-existing untracked planning documents remain owner work and are excluded.

## Findings that narrow the plan

`WorkflowRow.terminal` clears `spec`. Migration 034 retains the scoped original
key, intent digest, source snapshot digest, deadline, attempts and eight-event
progress tail. An attempt's binding retains tool/version, effect and step/source/
intent digests. These prove a handler observation only when the trusted execution
path recorded success. They do not prove task correctness. A failed receipt may
have failed before dispatch, so this component excludes failures altogether.
Canceled/uncertain runs and any non-success attempt are excluded, including
abandoned recovery history. Tail events cannot reconstruct omitted causality.

The row does **not** retain completion/observation timestamps, original project
or branch, source-level permission edges, source classification or a
memory-forget identity. Its deadline is not a completion timestamp. Equal
installation hashes do not prove a synthetic origin or a project grant.
`KnowledgeResolver` defaults to unsupported; its existing decision resolver
verifies completed user turns, not workflow receipts. `KnowledgeService` admits
only verified repository-test procedures or confirmed decisions. The lifecycle
repository accepts Memory/DerivedMemory/KnowledgeRecord, not arbitrary episodes.
The source guard protects conversation extraction; it cannot silently issue a
workflow source lease. Reusing these by pretending an episode is schema 3 would
weaken their contracts. The remediation's native workflow tests remain unverified.

## Decision before implementation

Implement the independently useful **structural validation component only**:
a pure, bounded, versioned terminal-step candidate projection. It compares an
exact original plan against a minimal canonical receipt envelope, recomputes all
operation fingerprints and topological order, and emits only opaque identifiers,
closed categories and fingerprints. The envelope must come from a trusted future
adapter; the function does not authenticate it. Neither successful validation nor
a digest is permission, independent verification, an admitted episode or a source
lease. The type/name and result explicitly preserve that distinction.

No durable episode projection, database migration, capture/search/fetch/forget
service, runtime flags, host registration, context injection, embeddings or model
calls are installed. No feature can be enabled by a boolean. Existing memory
flags and fixed retrieval remain unchanged. There is no new source of truth or
second execution/lifecycle state machine. Original query/step names and arbitrary
receipt prose never enter the output. The original RunSpec is transient input,
never archived by this component. A closed allowlist replaces heuristic redaction.
Bounds: <=8 steps/attempts, <=2 KiB encoded per candidate, <=16 KiB combined,
zero durable bytes, no raw text fields. Retention of candidate values is solely
call-local; callers must not persist or disclose them as authorized memory.

## Blocking seams and required next evidence

A completed searchable E1 slice needs a trusted original submission binding for
project/branch/purpose/actor/client, exact source dependencies and public synthetic
origin, observed completion time, a host-resolved lease spanning final validation
and commit/disclosure, and canonical memory owner/source/forget integration. These
must be designed and tested together before storing anything. Missing evidence
must deny, never be reconstructed from current project state. No new permissive
issuer is introduced to make a synthetic end-to-end demonstration pass.

For future persistence: original scope/key and fingerprint, payload, normalized
edges and receipt must commit atomically; pre-commit failure leaves none; lost ACK
reconciles the original key; changed intent conflicts. Revoke/forget must erase
payload/edges while retaining bounded monotonic anti-replay authority. Saturation
must deny admission, never prune keys. Source lease and owner fence ordering need
native concurrent tests. Stale restores must remain quarantined until that
original authority is reconciled. Existing 1,024-fence/receipt capacity and physical
backup/replica deletion blockers are not solved here. A transient searchable view
also needs durable forget suppression and source leases; it is not a shortcut.

## Accepted, rejected and evidence limits

Accepted: additive synthetic fixture frozen before candidate scoring, behavior
names, exact receipt/plan comparison, conservative rejection and preservation of
old fixtures/locks. Rejected: fabricated timestamps, inferred project membership,
failed-as-success, archived trace reconstruction, schema-3 repurposing, unguarded
transient lookup, source text summaries and model-supplied grants. Deferred:
durable admission, unknown-commit recovery, lifecycle/revoke/restore, internal
lookup, causal utility comparisons and independent fixture review.

The E1 evaluator tests only structural consistency, including positive/negative
twins and an author-visible reserved split. It cannot measure capture precision,
lookup quality, model utility, disclosure safety or native durability. E2–E5 and
independent MEM-0/1/2 acceptance, HXE-3 F1–F3 native reproduction, production
issuer/lease, host registration and physical-send fencing remain open. No
baseline or release gate is weakened. Full MEM-3 remains partial/NO_GO.

Rollback: remove use of the pure validator; no persisted episode data, migration,
flag or host registration exists to undo. Preserve canonical workflow original
keys, memory tombstones and old release evidence. The readiness findings and
blocked capabilities remain reviewable in the implementation report and ledger.

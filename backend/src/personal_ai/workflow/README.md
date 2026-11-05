# Local workflow execution

`WorkflowService` is an internal host seam for operator-owned local/test
fixtures. There is no HTTP route, SDK operation, CLI, worker loop, or deployment
registration. A trusted host must opt in, bind the verified principal and
request scope through the existing auth boundary, and supply a
`RetrievalService` with a current source-authority check and the current
application registry. Use the existing PostgreSQL migration runner on a
disposable database. Use synthetic queries and a v2 operator installation
containing only public-classified fixtures.

Submit a `RunSpec` for a run ID, explicitly await `execute(run_id)`, poll
`status(run_id, cursor=...)`, or call `cancel(run_id)`. Submit the original
spec and key to recover a lost submission acknowledgement. Keep the run ID
and cursor for observations after disconnect. Run deadline starts at submission.
Ready steps use declaration order and dependencies gate ordering only.
Each step supplies an exact local-only retrieval query and fixed timeout and
result ceiling. There are at most eight steps, two claims, one step in flight
per run, and 256 total original-key records per disposable database. The
existing retrieval service also caps concurrent local reads per process.

A cursor is the last seen sequence for that run. `gap=true` signals that
earlier events are outside the retained eight-event tail. The reply includes
attempt states and the durable terminal outcome even after a gap. Duplicate
observations are expected. Source passages exist only in the successful live
claim, and a recovered claim can return results only for steps it completed.
Status and terminal replay return receipts alone. Each attempt receipt carries
the immutable tool ID/version and trusted effect class, canonical step digest,
source snapshot digest, and original intent digest. These fingerprints contain
no query text or source passages and remain available after the persisted spec
is cleared. Historical receipts without fingerprints remain readable and are
not backfilled. PostgreSQL backups and old row versions may still hold input,
so use synthetic fixtures.

`uncertain` requires operator investigation. A dispatched operation with an
unknown external result remains uncertain and is never resent through replay.
For the synthetic reasoning profile, a dispatched registered pure verifier is
charged conservatively and can be recomputed under the same fenced plan only
when the remaining verifier budget permits it. Otherwise recovery stops as
budget exhausted. Cancellation during verification settles as canceled and
withholds output. Stop the trusted caller to disable the profile and preserve
the database and original keys. Background, native and effect profiles are
unavailable. See
[authority and release boundaries](../../../../docs/decisions/0025-workflow-lifecycle-authority.md).

Run `make workflow-check` for contract and synthetic effect tests.
`make workflow-postgres-check` uses the opt-in
`PERSISTENCE_TEST_POSTGRES_DSN` local test role with CREATEDB and pgvector.

The memory package has an offline structural terminal-step validator. It does
not read this store, issue permissions or admit episodes. Terminal rows lack
original project/branch and observation-time evidence; their deadline and event
tail must never be used to fabricate that evidence. The workflow contract and
original-key authority remain unchanged.

`PostgresWorkflowStore.terminal_evidence` is an internal scope-filtered minimal
receipt adapter for trusted episode hosts. It returns original key, intent/source
fingerprints and attempt metadata without query, event tail or result copying.
It grants no project/source authority; hosts must authenticate original submission
bindings separately. Historical rows still lack original observation timestamps.

## Synthetic reasoning profile

A trusted local/test host can construct `WorkflowService` with `enabled=True`
and a `ReasoningHost` holding the current bound `ApplicationContextRequest`,
scope ceilings and a closed scripted fixture. The host must use the live
registry and request-authority callback and select `offline_fake` for both
inference profile and cost mode. The same `submit`, `execute`, `status` and
`cancel` methods then address a separate synthetic reasoning purpose. Submit a
`reasoning-run-request-v1` with an original UUID, typed task and explicit
resource ceilings. Omitted work limits are zero. The service compiles the
versioned plan internally.

The live result is a tuple of verified `(slot, value)` pairs. Partial results
contain supported slots only. Progress and replay are metadata-only and
include workflow fences' resulting attempt states, exact synthetic resource
observations, cursor gaps and terminal stop reasons. The original request
recovers the same run ID. An interrupted reserved attempt can be abandoned
and resumed under the stable child key. A dispatched attempt without a
committed result remains uncertain. See the
[reasoning workflow guide](../../../../docs/reasoning-engine/re-2-implementation.md).

## Grounded fixture profile

Use the [grounded host guide](../../../../docs/reasoning-engine/re-3-implementation.md)
to opt in with a separate `GroundedHost` and public synthetic v2 source
installation. The existing foreground lifecycle owns the run and replay.
The live response contains only verified slots with citations. Source bodies
and candidate values are request-local. Run `make reasoning-grounded-check`
for the network-fenced fixture tests and `make workflow-postgres-check` for
native workflow tests with the disposable DSN.

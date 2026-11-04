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
Status and terminal replay return receipts alone. The persisted spec is cleared
at terminal transition. PostgreSQL backups and old row versions may still hold
input, so use synthetic fixtures.

`uncertain` requires operator investigation. An expired dispatched attempt
cannot be taken over or retried using its original key. Stop the trusted caller
to disable the profile and preserve the database and original keys. Background,
native and effect profiles are unavailable. See
[authority and release boundaries](../../../../docs/decisions/0025-workflow-lifecycle-authority.md).

Run `make workflow-check` for contract and synthetic effect tests.
`make workflow-postgres-check` uses the opt-in
`PERSISTENCE_TEST_POSTGRES_DSN` local test role with CREATEDB and pgvector.

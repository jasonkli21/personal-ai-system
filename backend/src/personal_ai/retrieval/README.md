# Standalone retrieval v1

Default-off, operator-installed lexical corpus and selected snippet search.
`contracts.py` owns the additive source-neutral public wire; `installation.py`
owns bounded snapshot rights and lexical indexing; `service.py` owns admission,
aggregate budgets and final source/client checks. `external.py` reuses existing
search factories, Brave and P19; `journal.py` provides single-host content-free
original-intent fences. Deterministic no-dispatch preflight runs before reservation;
the durable 4,096 receipt cap applies per authenticated scope. Aggregate journal
growth across distinct scopes remains unbounded, so external use stays local/test-only.
Local citation authority binds an operator issuer to exact authenticated scope.
`tools.py` binds one closed read-only executable; a generic operator-extensible
executable registry remains future work.

No model/context, summary/history, memory, generic plugin execution or URL fetch
integration exists. Tool metadata never grants source or execution authority.
Research-v1 persistence is unchanged. Keep source and receipt files together
through rollback/recovery; never prune/reuse receipts or republish stale grants.
See [wire and operator contract](../../../../docs/platform-independence/retrieval-v1.md)
and [implementation evidence](../../../../docs/platform-independence/pi-5-implementation-report.md),
including [2026-10-31 review remediation](../../../../docs/platform-independence/pi-5-independent-review-remediation-2026-10-31.md).

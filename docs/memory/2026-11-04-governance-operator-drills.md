# Memory governance operator drills — 2026-11-04

This is an inert runbook. No step here authorizes a live actor, private data,
cloud, paid call, provider, deployment or effective flag change. Status remains
IMPLEMENTED_E1_GOVERNANCE / PHASE_EXIT_BLOCKED / PRODUCTION_NO_GO. Stop at any
missing authority, ambiguous result, unauthorized disclosure or stale dependency.

## E1 reproduction

From the repository root, use `backend/.venv/bin` on PATH and
`LITELLM_LOCAL_MODEL_COST_MAP=True`. Run `make memory-governance-check`, then:

```sh
make memory-governance-eval GOVERNANCE_FLAGS='--output /tmp/governance-a.json'
make memory-governance-eval GOVERNANCE_FLAGS='--output /tmp/governance-b.json'
make memory-governance-eval GOVERNANCE_FLAGS='--verify /tmp/governance-a.json'
make memory-governance-eval GOVERNANCE_FLAGS='--verify /tmp/governance-b.json'
```

Each invocation starts a fresh process. Expect 69 retained cases, six families,
eight distinct canonical source observations with positive/negative pairs, no
boundary mismatches and matching semantic digests. Expected failed, incomplete,
cancelled, unavailable and unsupported rows remain visible; none is a successful
native operation. Source drift, missing rows, altered receipts or rehashed forged
outcomes must fail verification. Native DB latency, model usage, storage/egress
cost and independent utility remain null. The committed run reports are author
evidence; authenticate their hashes separately before relying on them.

## Inventory and E2 component reentry

Before any native work obtain a separately approved disposable DSN and inventory
canonical owner deletion locks, source issuer, owner/project/app mappings,
registered recipient principals and policy epochs. Record storage, indexes,
Dynamo jobs, replica and backup topology, original-key retention, safety capacity
and resource budgets. There is no native grant adapter/migration in this slice.
A future adapter must join the canonical owner lock, source guard and original-key
transaction; unknown schema/type readers deny access. Migration must be additive;
backout must preserve grant generations, receipts and source/owner tombstones.
An older schema or snapshot cannot become the surviving authority.

Register concurrency, grant/key/fence byte ceilings, read/fan-out bounds,
maintenance backlog, retry/export/index budgets and observation windows before
the drill. No SLO or paid budget is invented here. Run independent-process CAS,
duplicate first-submit, crash before/after commit, lost ACK, disk-full and
unavailable-DB tests. Reconcile the identical original operation/body. Stop on
unknown commit status without a recovery receipt, safety receipt eviction,
original-key collisions or inability to exclude owner deletion. E1 mutexes are
not SQL/process-crash proof. A disposable PostgreSQL test does not prove Dynamo
or cloud behavior.

## E3 registered issuer, internal use and physical send

Requires independently verified host/service identity, source membership and
registered recipient proof, explicit owner purpose/expiry/ceiling, and approved
no-charge/cost-bound transport. Select a public synthetic dedicated owner and
agent/project pair. Revoke between retrieval, selection, packing, token counting
and actual physical send; mutate source version, target membership, source rights,
owner deletion and grant generation. Use the canonical context assembler and
provider attempt accounting. Observe the actual transport boundary and reconcile
uncertain effects; a pre-send rights lookup is insufficient. No external delivery
can execute through this implementation. Stop until the real permit protocol
proves atomic fencing or recoverable ordering at that boundary. Never call a
model-supplied principal, imported receipt or matching UUID a verified identity.

## E4 deletion, recovery and resource soak

Use approved deployed topology and independently retained monotonic owner/source
and grant authority. Snapshot before revoke/forget; restore mixed-age canonical
records, projections, Postgres indexes and Dynamo work. Assert no managed read
while authority is missing or stale. Reconcile current epochs and original keys
before reopening. Delayed jobs and replay cannot resurrect old generations.
Advance through all twelve inventory stores, attaching topology-specific purge
proofs. Report logical suppression, pending purge, verified physical deletion and
unknown separately. Replicas, MVCC history, backups and external copies require
actual observations; do not promise recall of copies outside managed systems.

Soak the preregistered concurrency and per-owner storage envelope, including
long-idle cost, p95 latency, growth, erase backlog, recovery duration and resource
cleanup. Exhaust grants, original keys, fences and maintenance capacity during
forget/revoke. Deny new grants; preserve safety state or return explicit
pending/unavailable. Stop on unmeasured topology, quota deadlock, implicit safety
compaction, leakage or fabricated erasure success.

## E5 value, canary and rollback

Independent reviewers must register matched multi-agent tasks, blind custody,
actual downstream outcomes, observed tokens and native costs. Correct grant
policy is no answer-quality evidence. Preserve the corrected earlier 0 pp / 25
paired scripted result. Phase 36, applicable PI source/send/restore and HXE-5
release gates remain independently owned.

The pure planner stages synthetic preflight, independent review and a separately
authorized native drill; it executes none. Before a future live canary register
finite observation windows, cohort/budgets, abort thresholds and exact rollback
target. Any unauthorized read, stale epoch, missing authority or unknown cost
vetoes progress. No reviewer JSON can install itself as an authority.

On a separately authorized rollback, stop new managed reads and physical sends,
revoke outstanding permits, retain all safety receipts, reconcile uncertain
operations and restore only a reviewed current-state-compatible configuration.
Do not roll back safety epochs or delete canonical owner data. Publish exact
observations and blockers for independent review. This runbook and its planner
cannot mutate settings, flags, databases, storage, lifecycle or networks.

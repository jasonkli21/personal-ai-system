# Memory governance overlay

This unregistered E0/E1 seam references canonical knowledge without copying it.
There is no production adapter, route, tool, issuer, flag or physical send permit.
The default authority is absent; calls return unavailable. Python interfaces are
host API boundaries, not a sandbox against arbitrary Python code execution.

`ShareIntent` is untrusted requested data, including recipient identifiers and a
user-decision reference. It cannot instantiate `GrantAuthority` or `HostState`.
A server adapter must authenticate the request independently, resolve the exact
source and registered recipient, verify the explicit user decision, and fence
all owner/source/registry/permission mutations under `guard`. The only adapter is
`evaluation/governance_simulator.py`; it uses exact registered request objects,
canonical `KnowledgeService` records/lifecycle and the shared `ContextBuilder`.
No runtime composition imports it.

`GrantRepository.transaction` must atomically exclude canonical owner deletion,
original-key races and CAS changes. Grants retain the original actor/body digest;
replay observes a receipt and never reapplies a grant. Replacement and revoke
permanently suppress older coverage; a new ID and generation are required to
regrant. A separately surviving monotonic authority must reconcile restored
state before any read **or mutation**. These are protocol obligations; the
in-memory simulator establishes no durable SQL or cold-restart guarantee.

Call `observe` at selection, packing and final internal use. A prior decision is
only an exact dependency observation; recheck it against current authority. Hold
the authority and canonical source guards across actual internal content use.
There is deliberately no callback executor in this service. External delivery is
always denied, including after a successful observation. Integrating a live
reader or dispatcher requires separately reviewed source and send fencing.

Limits cap retained grants and source fences per owner; accepted grants reserve
permanent revoke capacity. Original keys and tombstones are never compacted or
evicted here. `admit_work` models finite read/fan-out/job/retry/export/index
ceilings; it starts no jobs and creates no indexes. Native storage economics and
cross-process quotas remain unverified. Store unavailability produces uncertain
mutation outcomes; retry the identical original key/body after recovery.

`owner_preview` is a host-private rendering helper, not a new owner route. It
never returns source text or enables export/import. `retention_inventory` names
twelve stores with synthetic logical suppression or unknown/inventory statuses;
it never claims global physical erasure. Backups and external copies need actual
topology proofs. `operator_plan` returns inert canary/rollback proposals only.

Run `make memory-governance-check` and `make memory-governance-eval` from the
repository root using the existing backend virtual environment on PATH. For a
report, pass `GOVERNANCE_FLAGS='--output /tmp/governance.json'`; verify/replay in a
fresh process with `GOVERNANCE_FLAGS='--verify /tmp/governance.json'`. Source
hashes cover runtime Python dependencies and the additive author-visible corpus.
Changed sources require new evidence; no frozen benchmark lock is rebound.

Full phase exit remains BLOCKED; production NO_GO. Independent review, native
transactions, deployed issuer/registry, physical sends, erasure/restore and real
multi-agent task/cost evidence remain required.

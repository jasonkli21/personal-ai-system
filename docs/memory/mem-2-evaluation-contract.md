# MEM-2 synthetic control evaluation contract

Date: 2026-10-29. Version `mem2-control-v1`; independent fixture assessment pending.
This is deterministic control correctness evidence, not LLM utility or deployment
acceptance. Existing MEM-0/MEM-1 fixtures and historical reports stay immutable.

The JSON corpus has 36 cases: authorization 7, proposal injection 8, CAS/conflicts 5,
idempotency/partial commit 5, forget/revocation 5, quota/deletion 6. Each family
contains one public tagged holdout (6 total); the other 30 are development. These
are author-visible partitions, not a blind evaluation. Each row identifies threat,
negative control, driver input and independently editable expected observation.
`run_probe(Probe)` receives only scenario/value. It receives no rubric, split,
expected status, case ID or family. The scorer compares status, durable lifecycle
version, knowledge cardinality, disclosure count, pending/receipt counts and replay
bit after execution. Runtime behavior cannot be inferred from a stored pass label.

The actual service/tool adapter and canonical in-memory lifecycle run behind a
synthetic scoped host and synthetic authenticated principal. Source success comes
from the existing hermetic issuer's stateful action, never candidate text. Poison
fields/malformed JSON use the actual tool schema. No provider dispatcher is added.
Fault hooks inject before commit, after commit and during exact-key reconciliation.
The read positive/negative controls differ only in query content. All guessed-ID
and foreign-actor reads expose no record or source metadata. Review/reject tests
assert knowledge count unchanged. Unsupported revision is an explicit abstention.

Supplemental tests are separate from the 36-case denominator: HTTP middleware,
recent-auth and strict intent; user actor rejection at raw lifecycle entry points;
thread and native process/session CAS races; source revocation at transaction entry;
receipt-insert failure rollback; final packing and provider handoff; queue and replay
key exhaustion/retention; account export and fenced operator erasure; UI explicit
confirmation, no optimistic success and exact-intent retries. Revision/revision and
revision/forget races cannot execute because every revision is unsupported: no
replacement, lineage or receipt is written. No successful correction sequence is
claimed. Real production authority and physical-send serialization remain gates.

Hard failures are an unexpected disclosure, agent-origin knowledge admission,
state overwrite, false applied response, duplicate effective transition, missing
atomic receipt, stale-context acceptance in the exercised boundary, or mutated
legacy fixtures. All must produce a nonzero evaluator/test exit. The CLI emits
actual observations and checksum, partitions and p50/p95/max scenario latency.
Latency includes synthetic host setup/seed; it is not isolated database latency.
Native resource probes separately report N=0/1/32/128, application SQL calls, read
outcome/latency, and proposal/receipt bytes without claiming a performance SLA.

Limits: one bound project; 32 candidates (33rd sentinel denies whole read), eight
returned records, 200 query characters, two-second cooperative operation deadline;
ten calls/ten seconds per explicit tool run, 4,096-byte JSON input. Pending content
expires at 24 hours; 32 retained proposals and 256 receipt keys per exact actor
namespace. Receipt keys retire after 24 hours for proposals and 30 days otherwise,
remain quota-counted and cannot be reused. Content is erased on the next bounded
write or fenced account purge; idle namespaces have no automatic physical eraser.
Known false positives: conservative ASCII/sensitive-term/instruction policy rejects
legitimate non-ASCII text, discussion of verification/receipts and some ordinary
technical vocabulary. No semantic relevance or model task-quality lift is measured.

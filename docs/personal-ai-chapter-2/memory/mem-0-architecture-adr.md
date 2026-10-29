# MEM-0 architecture reconciliation and MEM-1 options

Date: 2026-10-28 (PDT). Status: accepted for the bounded MEM-0 harness;
MEM-1 schema preference is a hypothesis pending independent review. Inspected
base: `ad7c5004294b34df6acffd154509a402e2626659`. No runtime migration.

## Ownership and executable boundary

| Boundary | Owner and executable anchors | Capability / evidence |
| --- | --- | --- |
| Request identity | `auth/scope.py:RequestScope`, authentication middleware, application registry | implemented; local identity is test-only; deployed membership unverified |
| Conversation originals and branches | DynamoDB message adapter; `storage/branches.py:active_path`, `memory/services.py:source_messages` | implemented; active complete turns only; native Dynamo remains external |
| Narrow admission | `memory/policy.py:candidate_reason`, `MemoryExtractionService` | implemented-but-off; exact standalone user assertions, sensitive/external exclusions |
| Original memory | Postgres memory adapter, `memory/contracts.py:Memory`, `memory/repositories.py` | implemented-but-off; schema 1, immutable source fingerprint and scope identity |
| Derived memory | `DerivedMemory`, `lifecycle/policy.py:DeterministicMemoryConsolidator` | implemented-but-off; schema 2, 2–4 originals, exact `support-v1`, no generative synthesis |
| Source validity | `memory/dependencies.py:original_reason`, `record_dependencies`, `MemoryPermissionRevalidator` | implemented; scope, complete branch, sensitivity, epochs and all view supports rechecked |
| Retrieval | `memory/services.py:MemoryRetriever`, `MemoryQuery`, Postgres exact pgvector adapter | implemented-but-off; hard checks precede ranking, fixed default; synthetic vectors do not establish real relevance |
| Context and later reuse | `context/assembler.py:ContextAssembler`, `context/builder.py:ContextBuilder`, `context/authority.py`, history/summary source snapshots | implemented; one final budget and dependency check; memory-bearing artifact writes rejected |
| Maintenance and jobs | Postgres lifecycle events/projections/source edges; DynamoDB operational jobs; `lifecycle/jobs.py`, `memory/effects.py` | implemented-but-off; stable intents, fenced lease/commit, receipt reconciliation; no global transaction |
| Current domain truth | Owning domain repositories and typed context contributions | implemented separately; historical memory cannot override current canonical revisions |
| Procedures, project decisions, experiential traces | No admissible v1 type or production source policy | missing; do not relabel tool outcomes as episodic user observations |
| Native resource use, model-mediated task lift | Phase 36 external receipts | unknown/unverified in MEM-0 |

Flow: active completed source turn → conservative candidate validation → original
memory → lifecycle projection / optional exact derived view → server-built query →
retriever → source dependency graph → shared assembler/builder → revalidated later
history/summary reuse. Summaries are lossy branch context, not durable knowledge.
Cross-store failure means reconcile the original intent/receipt, never assume a
Dynamo checkpoint and Postgres commit were atomic. No second scheduler or memory
database is introduced by this evaluation.

## Authority dimensions and minimal future receipt

Source classes are `user_asserted`, `tool_receipt_verified`,
`canonical_domain_version`, `model_proposed`, `historical_derived`, and
`untrusted_external`. Keep these independent from (1) verification
`verified/failed/unknown`, (2) observation/effective/expiry times and revision
currentness, (3) owner/app/workspace/actor and current permission epoch, and (4)
task outcome `success/failure/partial/uncertain`. Confidence cannot replace any of
these dimensions. A user reporting success remains a user assertion.

A candidate MEM-1 procedure needs a trusted task/run ID, source revision and
preconditions, command/tool identity, sanitized result category, independently
resolvable receipt ID/hash, verification actor and timestamp, scoped original
source refs and permission versions, limitations, and explicit failed/unknown
outcomes. Bind receipt to command, revision, run and outcome; an assistant's
statement is never such a receipt. Unknown write outcomes require observation of
the original effect key before retry. MEM-0 receipts are synthetic simulations.

## MEM-1 alternatives

| Alternative | Compatibility and tradeoff | Migration / rollback |
| --- | --- | --- |
| A: versioned knowledge family in existing memory domain | Preserve v1/v2 readers; explicit procedure/project contract, kind-specific source policy and retrieval adapter. Normalize arbitrary bounded provenance edges instead of stretching 2–4-source views. More adapter work, clearer authority. Preferred hypothesis. | Additive tables/versioned readers; backfill only authorized sources; default-off writer/read capability; rollback disables new path while preserving original records and receipts. Native concurrency and erasure tests required. |
| B: compatible subtype/metadata extension | Fewer storage seams, but legacy validators and narrow extraction semantics risk silently accepting tool records. Must still use a new discriminator and exhaustive provenance; cannot add arbitrary metadata to schema 1. | Versioned additive fields/edges and dual-read compatibility; reject unsupported subtype in old readers; rollback must not reinterpret new records as old user assertions. |

Rejected: procedure text disguised as `episodic_observation`; gold fixtures granting
access; independent vector store/context builder; model self-verification; raw
tool payload retention. Both alternatives retain canonical lifecycle epochs,
scope-first retrieval and dependency-aware packing/reuse. Neither is implemented.

Threats: stale revision reuse, malicious instructions in logs, spoofed receipts,
partial writes, duplicate effects, source revocation during packing, forgotten
source resurrection, conflicting domain/user claims and cross-workspace names.
The harness exercises synthetic source transitions and actual production memory
revalidation where representable. It does not reproduce deployed grants/IAM.

Unresolved before MEM-1: receipt issuer/resolver and cancellation semantics;
first authorized source and source-policy review; version compatibility; complete
provenance bound/erasure; query specialization; concurrency/rollback tests.
Specify native Postgres tests for simultaneous admit/forget, epoch CAS, duplicate
receipt replay, transaction rollback and complete reverse-edge invalidation.
Start with one two-session repository test-workflow transfer, source revision
check and negative unknown-outcome control. Defer traces, dreaming, indexes,
agent writes and multi-agent sharing to separately authorized later phases.

Phase 36 remains not release-ready. Its native stores/resources, live quality,
identity/version authority, cloud recovery/telemetry and physical deletion gates
are not closed by this harness. No production defaults or schemas change.

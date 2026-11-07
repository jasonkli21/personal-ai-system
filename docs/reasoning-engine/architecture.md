# Reasoning architecture

[ADR 0028](../decisions/0028-reasoning-policy-and-execution-ownership.md) governs
the separation of strategy policy, execution, and independent measurement.

| Boundary | Owner | Future interaction |
| --- | --- | --- |
| Effort, task features, sufficiency, strategy | Reasoning | The orchestrator narrows requested effort, compiles bounded specifications, verifies results, and keeps promotion behind explicit evidence. |
| Run, step, original intent, attempt, cancel, uncertainty, replay and events | PAS workflow | The orchestrator submits a typed versioned specification and consumes ordered receipts. |
| Model continuations and physical model attempts | Existing chat and usage accounting | Inference steps bind the canonical continuation and physical operation identity. |
| Provider admission, disclosure, strict-free proof, quota, reservations and settlement | LLM routing | Recheck exact provider/account/operation and outbound data at physical send, retaining uncertainty on missing acknowledgement. |
| Sources, identity, citations, freshness and final-send authority | Retrieval, authentication and context | Resolve against current grants, assemble token-budgeted context for every model turn and recheck dependencies before dispatch, disclosure or replay. |
| Memory lifecycle, use rights, research and promotion | Governed memory lifecycle | A future eligible experiment uses governed memory reads and preserves their distinct provenance. |
| Telemetry and evaluation infrastructure | Evaluation infrastructure | Use safe observation and resource conventions. Reasoning owns this cohort and its rubric. |
| HTTP/SDK and app identity | Verified consumer boundary | Version any future exposure and bind principal and workspace on the server. |
| External edits, shell, tests, Git, retries and sessions | External coding harness | Receive separately authorized, read-only PAS assistance and opaque correlation. |

The [workflow contract](../../backend/src/personal_ai/workflow/README.md)
admits bounded foreground retrieval DAGs and a separate default-off synthetic
reasoning profile. The reasoning profile uses closed inference and verifier
step kinds, bounded context and resource envelopes, and canonical continuation
and exact-attempt bindings. It carries an empty source set. The workflow owns
original-key collisions, committed event order, cancellation, uncertain
attempts, cursor gaps and terminal receipts. Chat still owns continuation
identity and selected inference owns the operation boundary. Domain mutation
proposals remain under their authoritative domain transitions.

## Strategy and task descriptors

The [typed catalog](../../backend/src/personal_ai/reasoning/catalog.py) is
the authoritative versioned vocabulary. It contains bounded static shape
and effect descriptions. Availability records whether an entry is an offline
comparator or inert. The catalog carries no imports, execution paths, plugin
installation or strategy promotion state.

The finite policy uses typed synthetic arithmetic slots, declared ambiguity,
a fixed sensitivity and registered objective predicates. A future grounded
policy needs measurable, explainable descriptors for external dependencies. Record
ambiguity as missing/conflicting/complete required slots, freshness as a
class derived from source age and policy thresholds, objective-check
availability as registered predicate/verifier ID, constraints as count and
type, sensitivity as verified data class, and dependency depth from a
validated acyclic specification. Estimate marginal check value from
preregistered cohort error classes and measured added cost. Treat unknown
descriptors conservatively. Avoid retaining raw inputs in these descriptors.

Reserve a final synthesis call, token and time envelope before allocating
optional branches when synthesis requires inference. Include checking,
retry limits and concurrency in the same ceilings. Prefer early stop on
objective sufficiency. Evidence gaps, failed verification or inadequate
remaining synthesis budget lead to a bounded partial result or abstention.
Agreement or self-confidence alone cannot establish factual support.

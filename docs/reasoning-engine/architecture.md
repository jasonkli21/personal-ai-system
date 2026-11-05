# Reasoning architecture

[ADR 0028](../decisions/0028-reasoning-policy-and-execution-ownership.md) governs
the separation of strategy policy, execution, and independent measurement.

| Boundary | Owner | Future interaction |
| --- | --- | --- |
| Effort, task features, sufficiency, strategy | Reasoning | RE-1 narrows requested effort, RE-2 compiles bounded specs, RE-3 supplies verifiers, RE-4 owns promotion, RE-5 owns rollout evidence. |
| Run, step, original intent, attempt, cancel, uncertainty, replay and events | HXE-3 / PAS workflow | RE-2 submits a typed versioned spec and consumes ordered receipts. |
| Model continuations and physical model attempts | Existing chat/P19 | Inference step binds the canonical continuation and physical operation identity. |
| Provider admission, disclosure, strict-free proof, quota, reservations and settlement | PI-3 routing and LLM | Recheck exact provider/account/operation and outbound data at physical send, retaining uncertainty on missing acknowledgement. |
| Sources, identity, citations, freshness and final-send authority | PI-4/5, HXE-1, auth and context | Resolve against current grants, assemble token-budgeted context for every model turn and recheck dependencies before dispatch, disclosure or replay. |
| Memory lifecycle, use rights, research and promotion | MEM, including MEM-6 research | A future eligible experiment uses governed memory reads and preserves their distinct provenance. |
| Telemetry and evaluation infrastructure | HXE-2 | Use safe observation and resource conventions. Reasoning owns this cohort and its rubric. |
| HTTP/SDK and app identity | HXE-0 and verified consumer boundary | Version any future exposure and bind principal and workspace on the server. |
| External edits, shell, tests, Git, retries and sessions | External coding harness | Receive separately authorized, read-only PAS assistance and opaque correlation. |

The current [workflow contract](../../backend/src/personal_ai/workflow/README.md)
admits bounded foreground retrieval DAGs. The future extension needs a
versioned inference-step kind with a closed payload, bounded context and
resource envelope, canonical continuation and exact-attempt binding, and
source dependency references. Older hosts reject unknown kinds before
admission. Revalidate at reservation, dispatch and disclosure. Preserve
original-key collision semantics, committed event order, cancellation,
uncertain attempt reconciliation, cursor gaps and terminal receipts.
Model continuation and attempt records remain under existing owners. The
workflow owns ordering across steps. Domain mutation proposals remain under
their authoritative domain transitions. This phase defines the seam.

## Strategy and task descriptors

The [typed catalog](../../backend/src/personal_ai/reasoning/catalog.py) is
the authoritative versioned vocabulary. It contains bounded static shape
and effect descriptions. Availability records whether an entry is an offline
comparator or inert. The catalog carries no imports, execution paths, plugin
installation or strategy promotion state.

A future policy starts with measurable, explainable descriptors. Record
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

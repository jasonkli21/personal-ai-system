# Grounded iterative reasoning

The default-off grounded profile serves public synthetic fixtures in a local
or test host. It uses the existing foreground workflow, PostgreSQL row,
retrieval tool and isolated canonical chat continuation. See the
[entry decision](re-3-decision.md), [verification](re-3-verification.md)
and [open gates](re-3-blockers.md).

## Host contract

Construct `WorkflowService` with `enabled=True` and a `GroundedHost`.
Bind the verified principal and request scope through the existing auth
boundary. Supply a `RetrievalService` with a current request-authority
callback and a current application registry. Register `retrieval.query.v1`
and `retrieval_context` for the bound app with its normal read-only tool and
excerpt disclosure policies. Use a disposable, normally migrated PostgreSQL
database. Set `retrieval_enabled` and `retrieval_context_enabled` and select
`offline_fake` for both inference profile and cost mode. The source must be an
operator-installed v2 snapshot. Its local read, quote and model-context
grants must match the scope. Every document must be public and marked
`public-synthetic-fixture-v1`. The trusted fixture callback must return
`True` for the current scope, fixed purpose, exact snapshot digest,
credential-free endpoint digest and typed fixture task. Install and authorize
only known fixture subjects. A fixture label or capability advertisement
confers no grant by itself. The
[hermetic composition](../../backend/src/personal_ai/evaluation/reasoning_grounded/fixture.py)
shows the inputs and uses a transaction double for offline measurement.

Submit a `reasoning-grounded-request-v1` with an original UUID, a registered
synthetic subject, one to three distinct integer fact requirements
(`capacity`, `duration`, `quantity`), and explicit resource ceilings.
The only source mode is `local_fixture`. Trusted user, application, workspace,
operator and endpoint ceilings intersect with request and runtime limits.
Omitted work limits contribute zero. The fixed destination uses the
credential-free in-process fake with a zero permitted paid-cost ceiling.

The service compiles `reasoning-grounded-plan-v1` under
`grounded-evidence-policy-v1` and `evidence-research-bounded.v1`.
The closed template is initial retrieval, optional focused retrieval,
synthesis, then verification. The two retrieval slots use the subject's
`<subject>_overview` and `<subject>_<field>` tags. Whole fixture records have
the form `FACT <subject> <field> <signed integer>;` on their own
newline-terminated line. Arbitrary prose has no factual interpretation.
The initial assessment identifies supported, missing, stale, conflicting or
inconclusive slots. An eligible missing or stale slot can trigger one query
with its exact tag when the final stages still have time and resources.
A complete initial result skips follow-up at every effort. `low` also skips
follow-up when a gap remains. Bounds are two local reads, one fake
generation, one charged final predicate, eight returned items, 4 KiB of
quotes, four sequential steps and a deadline of at most 30 seconds from
submission. The canonical builder and exact fake byte counter can further
limit what fits. Clock and fence checks gate new work and disclosure at each
boundary.

Each operation binds the scoped original intent, plan, source snapshot,
prior evidence and exact child UUID. Retrieval validates the tool reply
against the submitted query and independently rebuilds each item's literal
span, fingerprint, revision, issuer-derived authority, rights epoch and
reference from the current installation. Expired or unauthorized documents
cannot supply a fact. Truncation yields inconclusive coverage where omitted
evidence could change the answer. Conflict detection covers the bounded,
retrieved evidence set. A pinned context provider passes those same items
and permission dependencies through the shared assembler. The fake reads
the packed untrusted-data block. The verifier checks each structured slot and
its exact citation against the retrieved fact records and rejects fabricated,
cross-slot, duplicate, conflicting or unsupported candidates.

## Receipts, recovery and disabling

`execute(run_id)` returns redacted progress and live supported claims from
the successful authorized claim. Each claim carries a citation ID that
joins to the retrieved passage metadata in the attempt receipt. Authority
is rechecked before reads, packing, counting, dispatch, checking and
disclosure. If authority changes after terminal commit, the historical
receipt remains observable to the authorized caller and the live body is
withheld. Terminal replay and status expose metadata only. The generic
retrieval outcome retains `context_integration=unavailable`. Grounded
context flows only through the internal fixture continuation.

The row retains bounded revisions, rights identifiers, digests, gap classes
and quantitative resource receipts. Raw queries, candidate responses, source
text, and prompts do not enter progress, telemetry or replay. The active
plan stores a typed synthetic subject and requirements, and terminalization
clears the plan. Older row versions and backups can still contain that
structured input. Retrieval and candidate bodies exist only in the claiming
process. A replacement claim can abandon a pre-dispatch reservation under
the same child key. After successful prior work, lost ephemeral state ends
the run. A dispatched retrieval or inference without a settled observation
remains uncertain under the original key. A dispatched local predicate is
charged and fails closed if its candidate was lost.

Stop new grounded admissions, cancel or drain active work with the existing
workflow methods, and remove the grounded host opt-in. Preserve original keys,
redacted receipts and uncertain attempts for reconciliation. A source-rights
change or either external-provider or research kill switch prevents further
grounded processing. The source-free finite profile is separately configured.

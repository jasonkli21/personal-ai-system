# ADR 0028 — Reasoning policy and execution ownership

Accepted for local development on 2026-11-04. The [architecture](../reasoning-engine/architecture.md)
applies [ADR 0023](0023-external-consumer-and-execution-authority.md),
[ADR 0025](0025-workflow-lifecycle-authority.md), [ADR 0026](0026-offline-memory-research-custody.md)
and [ADR 0027](0027-memory-governance-overlay.md).

## Decision

Reasoning owns effort semantics, task descriptors, strategy selection,
sufficiency and strategy promotion. A strategy describes a bounded policy.
The workflow lifecycle owns execution of PAS runs and the durable ordering of
their steps, attempts and receipts. A future reasoning host submits versioned
specifications to that lifecycle and delegates physical inference to existing
chat continuation and P19 attempt authority. The current workflow spec admits
local retrieval steps. A future inference step needs an explicit versioned
contract and current authorization at the canonical adapter.

Effective reasoning work must fit the intersection of verified user, app,
workspace and operator ceilings and current provider/source permissions.
Provider routing and accounting retain admission, strict-free proof,
disclosure, reservation, retry and settlement authority. Context and source
owners retain preparation, provenance and final-send checks. Memory retains
lifecycle, use rights and memory promotion authority. External coding
harnesses retain control of sessions, shell, edits, tests and Git.

Use an inert closed catalog and a proposed, versioned request sketch. Measure
a one-generation direct comparator in a frozen additive offline corpus.
The scorer receives objective oracles that the candidate never receives.
Safety vetoes invalidate evidence. Reports carry no source passages,
transcripts, identity payloads or hidden reasoning. Require independent
reproduction before accepting the candidate and evidence at the claimed
topology before enabling it.

## Consequences

The first stage adds specifications and offline measurement. Future stages
must demonstrate compatible step admission, shared context packing, native
recovery and send-time authority before real multi-step dispatch. Synthetic
proxy scores provide a benchmark plumbing baseline. They grant no rollout,
provider, spend, tool, source or memory permission.

## Finite synthetic workflow extension

The default-off synthetic profile implements the versioned seam under the
existing workflow authority. Its executable `tool-verify-pure.v1` variant
uses a registered pure predicate over typed synthetic data. The historical
catalog's proposal-only `tool_verify` remains reserved for later grounded or
proposal work. The synthetic profile has an empty source set and uses only the
installed offline fake. Requests for external sources, provider spend or
arbitrary executable steps fall outside its closed contract.

The workflow binds its original key and plan to a canonical child
continuation and reserves its attempt before the fake transport can dispatch.
The installed fake uses the reserved physical ID for its terminal receipt.
Canonical provider accounting remains responsible for any future real
operation. Scoped live disclosure rechecks authority and replays expose only
redacted metadata. The JSON row extension uses the existing PostgreSQL table
and lease/fence state machine.

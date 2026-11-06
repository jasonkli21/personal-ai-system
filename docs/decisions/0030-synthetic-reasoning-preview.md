# ADR 0030 — Synthetic reasoning preview boundary

Accepted for development on 2026-11-05. This extends [ADR 0028](0028-reasoning-policy-and-execution-ownership.md)
and preserves the promotion gate in [ADR 0029](0029-adaptive-fixture-selection.md).

A separate, explicitly launched loopback process owns the preview HTTP
boundary. One operator-configured credential grants access to one fixed
synthetic app and workspace scope. The normal API and its application grants
have no preview routes. No caller may bring an identity, provider, source,
prompt, executable step, or fixture. The launch instance is part of the
protocol scope so a restart cannot silently turn a lost acknowledgement
into a fresh execution.

Reasoning owns the grammar, ceilings, fixed strategy and objective check.
Workflow owns original intent, status events, attempts and cancellation.
Chat and the context assembler own continuation and packing. Provider
admission and settlement retain authority over real inference, and retrieval
owns source rights. The preview installs only the existing offline fake and
uses its canonical workflow path. The consumer SDK owns negotiation and
transport. Experiment scoring and adaptive promotion remain separate.

The single-process preview shares bounded in-memory workflow rows. Native
PostgreSQL drills exercise the same transitions separately. Any topology
requiring durable public recovery, verified deployed app/workspace grants,
provider quota or source-send authority needs its own acceptance evidence.

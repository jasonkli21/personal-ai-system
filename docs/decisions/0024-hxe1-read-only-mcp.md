# ADR 0024 — Read-only MCP pilot

Accepted for local HXE-1 development on 2026-11-03. Enablement follows
[ADR 0023](0023-external-consumer-and-execution-authority.md) and the
[cross-phase gate registry](../platform-independence/pi-cross-phase-gate-registry.md).

The optional `personal-ai-hxe1` distribution owns protocol translation and
source preparation. It is absent from core composition. The current pilot
uses the official Python SDK 2.3.0. Modern 2026-07-28 traffic is stateless
with discovery when available. Legacy 2025-11-25 uses initialization.
The fixture client uses SDK auto negotiation, requires known peer metadata
and checks the effective revision. Protocol changes require a new tested
pin and compatibility run before rollout.

The outbound client and inbound PAS server are separate trust zones. Both
require the host's verified request scope and current external-client
authority. The server also requires PI-5 request authority and the
application's installed read-only capability. Only the canonical
`retrieval.query.v1` executable mapping is available, with local sources
and a public synthetic corpus. The host owns authentication for any
transport. Stdio locality, HTTP Host and peer implementation metadata
confer no permissions. No backend route is registered.

Outbound fixture reads use an exact operator registration of transport,
peer identity, PI-5 document and issuer. One no-argument tool is supported,
with exact schemas and explicit closed-world, non-destructive read hints.
Hints help detect drift. They confer no authorization. Untrusted text,
descriptions, tool output and metadata never drive execution. Resource
URIs, prompts, pagination, status and memory are outside the supported
surface. The outbound catalog is fetched per exchange and the inbound
catalog has zero TTL. There is no response cache.

Local loading reads pinned UTF-8 text or Markdown through no-follow
directory descriptors and validates the bytes against the existing PI-5
document contract. Installation v2 carries the operator issuer.
Publication, access, source revision, quote fidelity, rights reference,
epoch and expiry stay with PI-5. The synthetic external fixture can only
return the exact previously approved bytes and issuer. Installation is
an explicit operator step and model disclosure uses existing PI-5 context
and provider policy independently.

Admission and disclosure recheck current authority. Errors disclose fixed
unavailable messages, and cancellation propagates. No application retry
follows an interrupted call. The pilot does not dispatch to a live source.
Future live transport requires existing P19 admission, real issuer rights
and an atomic physical-send permit. Third-party MCP consumers can retain or
forward returned bytes outside PAS enforcement. These local checks cannot
establish send/revoke atomicity, restore monotonicity or physical erasure.

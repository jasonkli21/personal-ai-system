# Harness excellence · HXE-0

The [ownership ADR](../decisions/0023-external-consumer-and-execution-authority.md)
defines the durable boundaries. Start with the [SDK](../../sdk/python/README.md)
and [Project Checklist](../../examples/project-checklist/README.md) for the
developer flow. The [gate registry](../platform-independence/pi-cross-phase-gate-registry.md)
owns release restrictions. The [implementation receipt](2026-11-03-implementation.md)
records the original candidate checks; the [review remediation record](2026-11-03-remediation.md)
records the scoped fixes and current evidence.

## Capabilities and evidence

E0 is static inspection. E1 is hermetic synthetic conformance. E2 is separate
install/native evidence, scoped to the operation actually exercised. E3 is
approved real-provider or real-source evidence. E4 covers deployed recovery,
deletion and cost. E5 measures longitudinal utility. An installed client smoke
does not establish egress fencing, server acceptance or trusted build origins.

| Capability and owner | Public seam and default | HXE-0 evidence and threat tested | Before enablement |
| --- | --- | --- | --- |
| Auth, API and SDK | Provisional consumer v1.2.0. Verified app binding required | E1 generated spec, signed Checklist ASGI and client parser. Spoofed actor, owner, client, workspace and app, ambiguous terminal and changed-body retry | Independently installed signed HTTP, trusted provenance and deployed identity |
| Trusted host catalog | Operator-selected `personal_ai.extensions.v1`. Checklist opt-in, history only | E1 registered Checklist fixture. Membership and exact client binding evaluated independently | Reviewed installation, issuer and workspace configuration |
| Provider composition, P19 usage | Internal neutral ports, offline profiles available only by explicit selection | E1 `test_inference_execution.py`. Alternate fake, exact count, strict-free and P19 denial before send | Actual account/counter/cap proof, native multi-worker reservation |
| PI-5 retrieval and read-only tools | Exact v1 retrieval and tool operations, default off | E1 `test_pi5_retrieval.py` and `test_pi5_context.py`. No implicit source grant, revocation, expiry, stale revision, poison text and closed effects | Trusted issuer, operation-specific rights, send/revoke atomicity |
| Retained dependency checks | Canonical history/detail/replay, controlled export | E1 `test_retained_output_detail_replay_history_and_export_deny`. Stale derived data withheld | Legacy provenance and deployed withdrawal across sinks |
| Governed memory | MEM-1/2 ports and first-party controls, default off. Checklist unavailable | E1 `test_memory_knowledge.py`, `test_memory_control_api.py` and `test_memory_control_context.py`. Default-off, actor/owner/project/source and forget | MEM-2 acceptance and native issuer, restore and erasure |
| Canonical attempts | Scoped original-key continuation and status. Future run lifecycle internal | E1 Checklist replay with one fake dispatch, incomplete SDK observations | Native restore and independently monotonic key/forget authority |
| Packaging and diagnostics | SDK and app offline build, CLI preflight | E2 isolated SDK/app install and local CLI smoke. E0 redacted configuration | Origin-pinned wheelhouse, native-fenced installed server and independent review |

## Reusing the conformance scaffolds

- Alternate provider canary uses operator settings `inference_profile=offline_fake_alt`
  and `inference_cost_mode=offline_fake` in the [neutral composition test](../../backend/tests/test_inference_execution.py).
  Each fake profile exercises the shared assembler. Strict-free rejection and P19
  reservation are exercised through the existing admission tests in the same file.
- Source and tool canary starts with the synthetic `access`, `document` and
  `install` fixtures in [PI-5 retrieval tests](../../backend/tests/test_pi5_retrieval.py).
  Use exact issuer, actor, workspace, purpose, revision and expiry. The
  [operator retrieval contract](../platform-independence/retrieval-v1.md) defines
  the read-only registry and on-disk schema. Start with synthetic excerpts and
  replay denial after changing revision or withdrawing the grant.
- Memory canary exercises the existing [governed memory](../memory/mem-1-contract-adr.md)
  and [control](../memory/mem-2-control-adr.md) boundaries. Checklist has no
  installed memory issuer or public memory operation. Its preflight reports
  unavailable.

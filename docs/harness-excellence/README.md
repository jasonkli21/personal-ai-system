# Harness excellence

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

| Capability and owner | Public seam and default | Local evidence and threat tested | Before enablement |
| --- | --- | --- | --- |
| Auth, API and SDK | Provisional consumer v1.2.0. Verified app binding required | E1 generated spec, signed Checklist ASGI and client parser. Spoofed actor, owner, client, workspace and app, ambiguous terminal and changed-body retry | Independently installed signed HTTP, trusted provenance and deployed identity |
| Trusted host catalog | Operator-selected `personal_ai.extensions.v1`. Checklist opt-in, history only | E1 registered Checklist fixture. Membership and exact client binding evaluated independently | Reviewed installation, issuer and workspace configuration |
| Provider composition, P19 usage | Internal neutral ports, offline profiles available only by explicit selection | E1 `test_inference_execution.py`. Alternate fake, exact count, strict-free and P19 denial before send | Actual account/counter/cap proof, native multi-worker reservation |
| Retrieval and read-only tools | Exact v1 retrieval and tool operations, default off | E1 `test_retrieval_integrations.py` and `test_retrieval_context.py`. No implicit source grant, revocation, expiry, stale revision, poison text and closed effects | Trusted issuer, operation-specific rights, send/revoke atomicity |
| Retained dependency checks | Canonical history/detail/replay, controlled export | E1 `test_retained_output_detail_replay_history_and_export_deny`. Stale derived data withheld | Legacy provenance and deployed withdrawal across sinks |
| Governed memory | Project knowledge and first-party controls, default off. Checklist unavailable | E1 `test_memory_knowledge.py`, `test_memory_control_api.py` and `test_memory_control_context.py`. Default-off, actor/owner/project/source and forget | Independent acceptance and native issuer, restore and erasure |
| Canonical attempts | Scoped original-key continuation and status | E1 Checklist replay with one fake dispatch, incomplete SDK observations | Native restore and independently monotonic key/forget authority |
| Local workflow execution | Bounded serial reads, scoped keys, leases and resumable cursor. [Operator seam](../../backend/src/personal_ai/workflow/README.md) | Local PostgreSQL migration, key replay and fencing tests. Receipts contain no source passages | Installed workflow consumer, unattended execution, native sandbox and live effects |
| Packaging and diagnostics | SDK and app offline build, CLI preflight | E2 isolated SDK/app install and local CLI smoke. E0 redacted configuration | Origin-pinned wheelhouse, native-fenced installed server and independent review |

## Reusing the conformance scaffolds

- Alternate provider canary uses operator settings `inference_profile=offline_fake_alt`
  and `inference_cost_mode=offline_fake` in the [neutral composition test](../../backend/tests/test_inference_execution.py).
  Each fake profile exercises the shared assembler. Strict-free rejection and P19
  reservation are exercised through the existing admission tests in the same file.
- Source and tool canary starts with the synthetic `access`, `document` and
  `install` fixtures in [retrieval integration tests](../../backend/tests/test_retrieval_integrations.py).
  Use exact issuer, actor, workspace, purpose, revision and expiry. The
  [operator retrieval contract](../platform-independence/retrieval-v1.md) defines
  the read-only registry and on-disk schema. Start with synthetic excerpts and
  replay denial after changing revision or withdrawing the grant.
- Memory canary exercises the existing [governed memory](../memory/mem-1-contract-adr.md)
  and [control](../memory/mem-2-control-adr.md) boundaries. Checklist has no
  installed memory issuer or public memory operation. Its preflight reports
  unavailable.


## Private local inference

See the [operator guide](local-inference.md) for the optional, private Unix
socket profile, exact-token preparation, and the task experiment and trace
command. The [verification receipt](2026-11-03-local-inference-verification.md)
tracks the scoped evidence.

## MCP source adapter

| Capability | Default and evidence | Before enablement |
| --- | --- | --- |
| Outbound MCP fixture | Off. Bounded stdio and in-process Streamable HTTP use the pinned SDK and an exact issuer/document registration. | Verified remote transport, trusted issuer, per-attempt physical-send permit and P19 eligibility. |
| Inbound retrieval | Off. Local retrieval through the selected executable tool, synthetic verified bindings, and modern and legacy SDK clients. | Standalone installed authenticated hosts, recipient grants and independently reproduced native conformance. |
| Source ingestion | Off. Digest-pinned UTF-8 and Markdown prepare canonical v2 installation inputs. | Current external rights, withdrawal and recovery evidence for real data. |

See the [adapter guide](../../adapters/mcp_source/README.md), [plan hardening](hxe-1-plan-hardening.md)
and [verification receipt](2026-11-03-hxe1-implementation.md).

## Profile evidence and operator tooling

The [release operator guide](release-operator-guide.md) documents versioned profile
manifests, closed evidence validation, repeat SDK builds, operator-pinned native
installation and opt-in bounded synthetic measurement. `make release-profile-check`
checks the new tooling; `make release-preflight` reports missing prerequisites
without network execution. Current profile decisions remain release NO_GO with
independent acceptance pending. Synthetic conformance does not close native,
origin, signed installed server, real-model, hosted or cloud gates.

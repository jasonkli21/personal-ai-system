# Current implementation state

Updated 2026-11-06. This page is the living implementation and release boundary. Code, executable contracts, migrations, and tests control behavior; dated reports preserve the evidence collected at their revisions. Local synthetic checks do not establish provider, cloud, deployment, or production behavior.

## Product and safety boundary

PAS is a reusable AI platform with optional reference applications. Routes and user interfaces remain thin; domain modules own authoritative application records and rules. Shared services own context assembly, provider-neutral inference, routing, evidence, memory, and evaluation contracts.

The fixed `local` owner is only a local/test identity. Deployed requests require verified Google user or service identity and private API invocation. Do not use local code or synthetic IAM to establish readiness for personal data. Credentials remain in untracked environment files or Secret Manager.

Provider SDKs stay behind the LLM and adapter boundaries. Every model turn uses the shared token-budgeted context assembler. Summaries remain lossy, branch-scoped working context. Durable user memory stays separate from time-sensitive external evidence, with source, observation time, freshness, and permission dependencies retained.

## Capability status

| Capability | Current behavior | Acceptance boundary |
| --- | --- | --- |
| Chat and context | Shared branch-aware context assembly, authorization, budgeting, and edit/retry behavior are implemented. | Local tests do not establish deployed identity, live model quality, or cross-device behavior. |
| Inference and routing | Provider-neutral execution and quota-aware routing enforce explicit profiles, disclosure checks, and bounded dispatch. | Live provider eligibility, billing, native network isolation, and production admission remain separate evidence. |
| Research and retrieval | Bounded source reads retain provenance, freshness, and rights; iterative workflows are gated. | Synthetic sources and fake providers do not establish external-source rights or live utility. |
| Memory | Durable memory contracts retain provenance and lifecycle boundaries. Experimental knowledge, controls, and optimization remain separately gated. | Synthetic evaluation does not establish native resource behavior, physical deletion, restore safety, or model-mediated utility. |
| Reasoning | Direct response is the default. Bounded synthetic strategies and preview flows remain opt-in; adaptive selection is not promoted. | Independent review, trusted source permissions at physical send, hosted model evidence, and restore acceptance remain open. |
| Persistence and recovery | Local Postgres/pgvector and DynamoDB Local paths support development and focused native checks. | Neon, AWS IAM, account recovery, distributed restore, backups, and physical erasure have not been established by local fakes. |
| SDK and consumers | Capability-oriented packages and HTTP contracts support independent local consumers. | Installed checks cover only the consumer profiles that actually ran; external identity and hosted acceptance remain open. |

Experimental capabilities remain off until their owning acceptance evidence is complete. No cloud deployment or paid/live provider call is implied by this status.

## Current-source verification repair

The current planning source lock is `planning-baseline-v36.json`; the current offline information-handling source manifest is generation 10. Both bind descriptive paths and exact file hashes. Historical planning locks, prior benchmark manifests, frozen case bytes, scoring, and non-promotion decisions remain preserved. Prior measurements remain bound to their original source identities and do not validate the renamed source tree.

The longitudinal memory study now uses additive source lock v5, which supersedes v4 by SHA-256 and preserves locks v1 through v4. The reasoning baseline and adaptive conformance use source identity v2 while preserving their v1 manifests and frozen cases. These source migrations preserve the existing protocols and decisions; they do not reclassify earlier measurements as evidence for the new source identities.

[Current source integrity and verification results](verification/current-source-integrity.md) records the before/after hashes, commands, environment, executed counts, and remaining blockers. `make source-contract-check` is read-only and fails if bound files are dirty or drifted. The explicit proposal commands create a new versioned candidate and refuse to overwrite an existing identity.

## Release boundary

Production remains **NO_GO**. Independent final review remains pending. External acceptance for real identity, model/provider rights, cloud IAM and billing, distributed restore, physical deletion, and hosted operation remains open or `BLOCKED_UNVERIFIED`. Existing memory, reasoning, workflow, and source-disclosure gates stay disabled where their contracts require it.

The preserved historical release matrix recorded 24 passed offline rows. That figure is revision-specific evidence, not a result for the current source tree or a release approval.

The [documentation router](README.md) points to current contracts and owning modules. The [naming compatibility register](naming-exceptions.md) is the complete list of phase-coded identifiers retained for compatibility. Historical plans and dated reports remain available at their original paths and are not current implementation status.

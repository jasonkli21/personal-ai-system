# Current implementation state

Updated 2026-10-14. This is the living implementation boundary. Code, contracts,
migrations and tests control behavior; dated evidence controls acceptance. The
[suite handoff](../stabilization/REVIEW-HANDOFF.md) records this change and its
verification. Independent final review and external acceptance remain open.

## Delivered locally

The Next.js frontend proxies the FastAPI API. Services own chat, active message
branches, token-budgeted context assembly, summaries, durable memory, research,
time-sensitive evidence, decisions and domain contributions. Provider SDKs stay
inside inference adapters. Summaries remain lossy branch context; memory and
external evidence retain different authority and freshness semantics.

| Area | Implemented boundary | Remaining acceptance |
| --- | --- | --- |
| Context and inference | Shared assembler, deterministic planner, bounded inspection, field/sensitivity policy, provider-neutral gateway and LiteLLM transport | Immutable source/policy references and deployed membership/revocation; live provider token/account/privacy semantics |
| Persistence and artifacts | PostgreSQL/pgvector adapters, DynamoDB adapters, private artifact tier, owner lifecycle and retention operations | DynamoDB engine, cloud object storage, physical deletion and cloud recovery beyond the exercised PostgreSQL subset |
| Routing and evaluation | Endpoint admission, physical-send accounting, deterministic routing, bounded tasks, shadow experiments and paired evaluators | Workflows remain gated; no adaptive, memory or search coverage is promoted by synthetic evidence |
| External and domain context | Typed Travel, Shopping and Finance reads; separate broad Health read and narrow signed Health exports; owner-scoped grants and opaque choices | Broad Health still requires a Firebase user token; native linked identity, cloud IAM, domain/browser and grant UX acceptance |
| Delegated Shopping tasks | Canonical closed wire, signed source ingress, domain capability metadata, existing confirmation/reservation/reconciliation lifecycle; budget and append-note adapters | Default-off, deployment-managed single-owner origin trust; actual cloud identity and browser/device acceptance |
| Application hosts | Shared sidecar and user-local external-turn composition behind their existing gates | Shopping sidecar, general Shopping AI generation/research transport and connected workflow routing remain incomplete |

The new source paths are Finance monthly budget → Shopping budget, Travel
consented destination/dates → Shopping note, and Health consented ergonomic
constraint → Shopping note. Domain apps retain canonical data, UI, revisions,
validation and consent. Personal AI persists only orchestration intent and
outcomes. Tasks do not invoke model providers or automate purchases.

## Identity and effect boundaries

Deployed requests require independently verified service IAM plus a bounded,
request-bound Ed25519 delegated Google identity. Authentication time comes from
the verified upstream event, never token issue time or a local session timestamp.
Source/destination mappings are explicit; email and UUID similarity never link
accounts. Shopping and Health recheck current linked Google provider membership,
disabled status and Firebase revocation time. Local identity is test-only.

Grants retain issuance, revision, purpose, destination and source policy. Source
consent/revision and target permission are checked before reservation and again
by the Shopping receiver. Confirmation binds immutable intent. One execution key
owns one reserved send. Receipt and effect commit together in Shopping. Lost
acknowledgements become uncertain; reconciliation observes the original key and
never resends. Retained fingerprints support observation of known receipts;
retirement does not reinterpret an old payload as a new write.

## Verification and rollout

At base `c029194156c570ec55f8173af969702f0265e57b`, the dated stabilization patch
passed **1,747 offline tests** and **75 native PostgreSQL tests**. The native run
skipped 14 unavailable DynamoDB cases. The all-five loopback HTTPS matrix uses
real migrations, PostgreSQL state, signatures and HTTP listeners; Google/Firebase
lookups remain synthetic. Exact final commands, source identities, revisions,
counts and limitations are in [verification](../stabilization/VERIFICATION.md).

Planner locks v10/v11/v12 remain historical. v13 binds the reviewed source and exact
runtime while preserving all 30 held-out cases, the deterministic planner and its
configuration. Production replay still rejects source, runtime and unrelated
revision changes. Portable tests use an explicitly test-only lock. Nothing is
promoted from this freeze.

Phase36 retains its earlier **24 passed offline rows**; its exact soak counts
remain in the generated evidence. These rows do not establish cloud, provider
or production acceptance.

Keep task, context, connected inference, private ingress and experimental gates
off until their owning acceptance evidence is complete. Provider SDK mocks,
synthetic IAM and JS bundles do not establish deployed security, live identity,
native device behavior or production readiness. No cloud deployment was run.
The user authorized local commits and pushes to remote main; hosted CI outcomes
are separate evidence and never inferred from local checks.

## Minimum context and history

Use [the router](README.md), the owning package README, its executable contract,
and focused tests. Use [operations](../stabilization/OPERATIONS.md) for the
synthetic suite and future staging prerequisites. Use [review handoff](../stabilization/REVIEW-HANDOFF.md)
for cross-repository review and [roadmap](../stabilization/ROADMAP.md) for remaining
acceptance and maintenance priorities. Plans authorize no new product work.

The [previous status snapshot](history/stabilization/current-state-before-2026-10-14.md)
preserves detailed phase history. The existing Chapter2 phase guides/evidence and
ADRs remain historical records at their tested revisions; this shorter status
does not revoke their unresolved gates.

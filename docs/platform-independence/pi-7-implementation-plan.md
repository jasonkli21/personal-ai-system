# PI-7 hardened implementation plan

2026-11-02. Base `57fc5ea53af6540c86f6f0df7ef2ff23b67a1d62`.
This is the reviewable derivative of the supplied detailed plan. The original
untracked file remains in the authoring workspace, pinned by SHA-256 in the
[pre-code hardening](pi-7-plan-hardening.md). The plan authorizes sequencing.
Use the [ledger](pi-7-verification.json) for observed results.

## Scope and sequencing

PI-7 prepares a credential-free operational profile for the installed AI
substrate, a separately installed consumer and disposable test persistence.
It also establishes a static preflight and recovery procedure. PI-5 remains
`blocked_unverified`. PI-6 synthetic evaluation remains locally complete,
and PI-6 production promotion remains `no_go`. Retain core contracts,
optional application selection, source revalidation, P19 ownership, original
keys, tombstones, historical fixtures and the MEM-2 freeze. PI-8 is a
separate audit.

| Workstream | Required local implementation | Acceptance |
| --- | --- | --- |
| W0 Baseline | Record Git state, original inputs, code and authority paths. Separate predecessor, offline, static cloud, hosted and native recovery gates. | Source and fixture identity with explicit open gates. |
| W1 Offline core | Build a core wheel and sdist with prepared lock-selected dependencies, reinstall from the sdist, and exercise real HTTP over the actual app factory and shared context/inference ports. Strip user environment and exclude optional packages. Use native macOS egress fencing where supported and state any degradation. | P7-01–08 cover installed origin, physical absence, chat/context, startup refusal, malformed setup, restart and bounded owned cleanup. |
| W2 Store and consumer | Reuse the existing Compose integration services with per-run identity, loopback bindings and ephemeral mounts. Install Reading Logbook host and client separately and verify its signed versioned HTTP contract, including uninstall. | P7-09–12 cover store boot/restart/isolation, volume safety and installed consumer. P7-13–16 cover scope, registration, original-key retry and lost stream. |
| W3 Static cloud preflight | Use a closed proposal schema with pinned digests/secret versions, exact user and service audiences, IAM edges, numeric AWS claims, private API/worker ingress, restricted egress, budgets and disabled features. Compare a supplied baseline and emit a redacted result. | P7-17–20 cover zero cloud CLI access, malformed input, privilege expansion and drift, and refusal of legacy/default/explicit apply. |
| W4 Quotas and diagnostics | Reuse existing owner admission and P19 quotas and attempt tracking. Test bounded local admission and the mock send boundary. The plan supports fake inference only and denies remote budget. Keep synthetic, estimated, provider-reported and billed usage distinct. | P7-21–28 cover profile selection, 429, quota exhaustion, concurrency, uncertain retry, canaries, provenance and bounded metrics. |
| W5 Recovery and topology | Inventory copies, owners, rights and retention. Restore stale derived state in a synthetic test while keeping current authority and original keys outside the snapshot. Retain PG/pgvector and DynamoDB. Write a separately authorized native drill. | P7-29–32 cover revoke-before-send, retained history denial, stale restore and capacity/original-key denial. |
| W6 Compatibility and evidence | Exercise optional uninstall, inherited regressions, strict lock preservation and kill switches. Publish exact command outcomes and separate review handoff. | P7-33–36 cover rollback, preserved history, default-off MEM-2 and cost/stop controls. |

## Changes from the supplied proposal

- Build against a prepared virtualenv and verify lock-selected installed
  versions. The command refuses missing inputs and never fills an offline
  cache from the network.
- Use the existing tmpfs/in-memory Compose services for the test topology.
  Durable restart and restore need independent storage authority and evidence.
- Keep the legacy cloud mutation path quarantined in history. The revised
  entrypoint has no apply backend. Static validation alone cannot authorize
  its restoration or certify deployed drift and IAM.
- Leave physical admission with P19. Local synthetic quotas and zero remote
  egress give meaningful local evidence. Provider/account caps, a truly
  global actor/app budget, and measured billed charges remain externally gated.
- Restore derived messages only in the simulation. Native anti-rollback
  requires an independently retained source and receipt authority.
- Preserve frozen evaluation bytes. If the commit lies outside the historical
  planning revision window, record the guard outcome rather than weakening it.

## Gates and rollback

A local candidate can pass installed synthetic core and consumer checks while
native persistence is unavailable. Static preflight has its own gate.
Hosted operations and native recovery/deletion remain `blocked_unverified`
until authorized proof. Release promotion remains `no_go` pending those gates,
inherited obligations and fresh independent review.

Follow the [operations](pi-7-operations-runbook.md) and
[lifecycle](pi-7-data-lifecycle-runbook.md) runbooks. To roll back, remove the
local launcher/plan features and keep cloud apply quarantined. Preserve
original keys, source authority, retained receipts and canonical storage.

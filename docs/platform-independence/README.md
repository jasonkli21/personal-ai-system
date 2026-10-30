# Platform Independence — Documentation Index

**Intended repository path:** `docs/platform-independence/`  
**Initial review base:** [`8571a8af33969f249614c2652a7d29c0c686f2d8`](https://github.com/jasonkli21/personal-ai-system/commit/8571a8af33969f249614c2652a7d29c0c686f2d8), October 30, 2026.  
**Status:** bounded PI-0 architecture/documentation/static diagnostics implemented locally; independent post-implementation acceptance is **pending**. Review remediation is recorded separately in the [2026-10-30 remediation evidence](pi-0-independent-review-remediation-2026-10-30.md). PI-1 is an implementation candidate pending independent review; PI-2 is a user-directed local implementation candidate pending independent review; PI-3 through PI-8 are not delivered. See the [implementation report](pi-0-implementation-report.md) for original-baseline checks and worktree caveats.

`personal-ai-system` is to become an application-independent, mostly-free AI harness. Travel, Shopping, Health, and Finance are **optional toy/reference clients**, not core platform requirements. Feature development for the separate memory program is **frozen at MEM-2**: preserve default-off MEM-0/1/2 and their outstanding acceptance gates; MEM-3+ requires a separate explicit unfreeze.

## Read in this order

1. [Platform Independence Charter & Phased Roadmap](platform-independence-roadmap.md) — first-principles product direction, current assessment, invariants, ownership, freeze and PI-0 through PI-8 implementation plan.
2. [PI-0 Independent Architecture Review](pi-0-review.md) — evidence-backed findings, code paths, risk classification and review limitations; **not** a completed post-implementation review.
3. [PI-0 Sol Medium/High Codex Handoff](pi-0-sol-codex-handoff.md) — standalone implementation instructions and acceptance checks for PI-0, suitable for direct use in one Codex session.

## Source-of-truth boundaries

The owning repo's `AGENTS.md`, code/tests/migrations, [`docs/current-state.md`](../current-state.md), historical memory records under [`docs/memory/`](../memory/), and stabilization evidence are authoritative for implemented behavior and gate status. The PI roadmap is a **future implementation plan**, not a declaration that PI-1–8 or production memory capabilities are delivered.

## PI-0 baseline outputs

- [Architecture decisions and ownership](pi-0-architecture-decisions.md) — committed constraints and provisional extraction/provider/sharing choices.
- [Dependency inventory and guard](pi-0-dependency-inventory.md), [machine records](pi-0-dependency-inventory.json), [exact import waivers](pi-0-import-waivers.json) — static and dynamic/default composition, flags and historical obligations.
- [Later-phase exit contract](pi-0-exit-contract.md) — PI-1 physical absence and PI-2 separately installed consumer proof, plus provider/privacy/replay gates.
- [Implementation evidence](pi-0-implementation-report.md) — source identity, preservation, executed checks and remaining review.
- [Independent review remediation](pi-0-independent-review-remediation-2026-10-30.md) — R01–R03 dispositions, updated guard evidence and residual limits.

## PI-1 candidate

- [Detailed plan](pi-1-detailed-implementation-plan.md) and [pre-implementation hardening](pi-1-plan-hardening.md).
- [Implementation report](pi-1-implementation-report.md), [current import inventory](pi-1-dependency-inventory.json), and [verification commands](pi-1-verification-commands.md).
- [2026-10-30 review-remediation evidence](pi-1-review-remediation-2026-10-30.md) — reproduced findings, code and CI corrections, local offline checks, artifact identities and remaining acceptance.
- [Independent-review instructions](pi-1-independent-review-prompt.md); no verdict supplied by the implementer.
- [Optional package operations](../../reference-apps/README.md).

PI-0 independent acceptance remains pending. The roadmap and exit contract retain all gates. This index does not supersede memory security or production acceptance.

Do not move or duplicate the historical MEM/Chapter2 evidence into this folder. Link to those records and preserve their version and provenance.

## PI-2 external consumer candidate

- [Same-session plan hardening](pi-2-plan-hardening.md), including the PI-0/1 gate exception and threat model.
- [Implementation/verification report](pi-2-implementation-report.md), observed limitations and artifact identities.
- [2026-10-30 independent-review remediation evidence](pi-2-review-remediation-2026-10-30.md), fixes, fresh offline checks and remaining acceptance gates.
- [External v1 HTTP contract](consumer-v1.md) and [generated OpenAPI subset](consumer-v1.openapi.json).
- [Independent Reading Logbook quickstart](../../examples/reading-logbook/README.md), operator identity/membership policy and rollback.
- [Separate independent-review prompt](pi-2-independent-review-prompt.md); self-review supplies no independent verdict.

The new client does not grant access to global profile, app-private memory, tasks,
account administration or gated external turns. Existing MEM-0/1/2 flags, schemas,
source/actor fences, receipts and fixture/lock history remain preserved. PI-2 v20
and remediation v21 are source-only planner rebinds with no promotion. Real identity/IAM, providers,
native storage recovery, Linux/Python 3.12 CI and independent acceptance stay open.

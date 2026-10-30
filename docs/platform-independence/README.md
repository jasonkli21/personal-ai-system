# Platform Independence — Documentation Index

**Intended repository path:** `docs/platform-independence/`  
**Initial review base:** [`8571a8af33969f249614c2652a7d29c0c686f2d8`](https://github.com/jasonkli21/personal-ai-system/commit/8571a8af33969f249614c2652a7d29c0c686f2d8), October 30, 2026.  
**Status:** bounded PI-0 architecture/documentation/static diagnostics implemented locally on the review base; independent post-implementation acceptance is **pending**. PI-1 through PI-8 are not delivered. See the [implementation report](pi-0-implementation-report.md) for exact checks and worktree caveats.

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

Future PI-1/PI-2 plans and evidence will be linked here when created; the roadmap and exit contract specify their gates now. This index does not supersede memory security or production acceptance.

Do not move or duplicate the historical MEM/Chapter2 evidence into this folder. Link to those records and preserve their version and provenance.

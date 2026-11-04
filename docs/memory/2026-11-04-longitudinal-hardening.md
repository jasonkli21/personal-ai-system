# Memory longitudinal research scope decision — 2026-11-04

Implementation starts at `619d724bd91d9f633714b576a3fef8e7a8841b6d` on `main`.
Existing untracked implementation plans are user material, excluded from the commit.
The owner's explicit implementation request authorizes this bounded E0/E1 slice;
wording in the attached plan about a planning-only session does not replace that
request. No external access, provider dispatch, enablement or live promotion is authorized.

## Accepted hardening

- Add an immutable study generation; preserve all predecessor fixture/source locks.
- Use 48 synthetic scenarios, eight per family, with separate source and scoring
  files and three or more time steps across separate simulated sessions. Every
  split is author-visible; 12 challenge slots exercise an import/custody interface,
  and do not constitute an independently blind cohort. Forty-eight small correlated
  scenarios establish a harness, not adequate statistical power or real utility.
- Policy consumers receive only serialized packed cards and a narrow task-tool
  interface. Scenario metadata, mutations and gold remain host/scorer side.
- Compare navigation only on the public fixture profile; canonical verified
  knowledge and control reads use their own admission/selection contracts.
  Incompatible arms retain unsupported rows. Pending proposals are diagnostics,
  never approved context. No invented embedding or legacy schema adapter.
- Preregister six contrasts, scenario-clustered bootstrap, two replay repetitions,
  matched budgets and safety vetoes before measuring. Setup is never Task B success.
- Local content-addressed artifacts and an append-only decision chain suffice.
  The existing scoped 30-day `research_experiments` summary store is unsuitable
  for complete trajectory custody. No database, migration or mutable policy registry.
- Research identities are integrity checks, never source grants or reviewer
  credentials. Reviewer approval is external trusted input, not a manifest field
  that can self-authorize. Canary and rollback are pure offline plans.

## Architecture and gate matrix

| Seam | Current authority | Research use / retained gate |
| --- | --- | --- |
| Original memory / fixed | schema-1, canonical lifecycle | incompatible project fixtures explicitly unsupported |
| Verified knowledge | KnowledgeService, trusted hermetic issuer, final consume guard | E1 admission/selection/control reads only; production issuer absent |
| Controls | explicit MemoryControlService host | read only; default-off runtime unchanged |
| Episodes | capture/read hard-disabled | no episode intake or enablement |
| Consolidation | sealed pending-only proposals | diagnostic reference; no trusted injection |
| Navigation | sealed synthetic source, canonical ContextBuilder | additive sealed authority, bounded lexical/topic/adaptive comparisons |
| Shared experiments / HXE telemetry | immutable 30-day summaries, sanitized usage | compatible aggregate counters; actual model/cost observations null |
| Reasoning promotion | separate reasoning authority | no strategy change |
| Permission / forget / restore | canonical owners and host source fences | deterministic revoke/regrant/tombstone tests only; no deployed proof |
| Native verification | disposable DSN absent | E2 blocked, no DB contact |
| Independent / live evidence | no independent challenge/reviewer or E3–E5 | phase exit and all release profiles remain NO_GO |
| Planning baseline | inherited source identity failure | run and retain failure; do not rebind historical locks |

Rejected expansions: real history, private data, network/model trials, runtime
flags/writers, scheduler, alternate lifecycle, automatic promotion, self-review
as independent acceptance. Local Python is 3.11.15; pinned backend environment
and Makefile commands own verification. No disposable PostgreSQL DSN is configured.

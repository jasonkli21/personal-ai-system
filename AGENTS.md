# Development instructions

This is a personal learning and research project for reusable AI capabilities around chat, context, memory, retrieval, evidence, and evaluation. Start at [the documentation router](docs/README.md), then read only the relevant task route, owning module README, executable contract, and adjacent tests. Do not preload the documentation tree.

## Authority and scope

Use this order when sources disagree: code, executable contracts, migrations, and tests; dated release/review/verification evidence; accepted ADRs; architecture and product intent; active plans; historical documents. Plans authorize sequencing but do not prove implementation. Security and privacy constraints take precedence. Chapter 2 describes future work unless current code and evidence show otherwise.

Inspect `git status` before editing and preserve user changes. Keep patches focused. Do not add features beyond the authorized scope or loosen tests and release gates to obtain a pass. Readability improvements must preserve behavior and persisted or wire identities.

## Durable boundaries

- Keep routes and UI thin. Services and domain modules own behavior; browser calls use the Next.js API proxy.
- Keep provider SDKs inside `backend/src/personal_ai/llm` and provider adapters. Services depend on neutral contracts.
- Route every model turn through the shared token-budgeted context assembler.
- Treat summaries as lossy, branch-scoped working context, not long-term memory. Regenerate and edit/retry use only the active branch as model context while preserving parent/supersedes links.
- Keep durable user memory separate from time-sensitive external evidence. Preserve source, observation time, freshness, and permission dependencies; enforce hard constraints before preference ranking.
- Domain applications own authoritative records, rules, and rich UI. Shared modules provide reusable AI-side capabilities.
- Keep experiments and sensitive capabilities gated until evaluated. Fakes and offline checks do not establish provider, emulator, cloud, deployment, or production-security behavior.
- Preserve authorization, consent/revocation, disclosure, idempotency, dispatch ordering, retries, replay, recovery, quotas, provenance, and evaluation integrity.

## Identity and data handling

The fixed `local` owner is only a local/test development identity. Deployed requests require verified Google user/service identity and private API invocation; local code does not establish readiness for personal data. Do not commit credentials, personal chats, or private data. Keep credentials in untracked environment files or Secret Manager.

## Documentation and checks

Keep [docs/current-state.md](docs/current-state.md) as the single living implementation status and [docs/README.md](docs/README.md) as the task router. New user behavior changes user docs/contracts. Implementation status and verification changes update current-state/evidence. Durable design rationale belongs in accepted ADRs; module usage belongs in the owning README; plans and dated reports remain historical. Do not put implementation notes, review history, or phase commentary in the root README.

Run checks relevant to changed code using the Makefile. For documentation-only changes, check links and content and run `git diff --check`. Keep provider/emulator checks opt-in; never report cloud, emulator, or provider checks as passed based on fakes.

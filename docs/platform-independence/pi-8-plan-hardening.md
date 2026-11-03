# PI-8 pre-implementation hardening

2026-11-03. HEAD `9b4b0f4db358ac97c156a615831dbb81a0a636a9`,
parent `5c7e377827572a4e7770c10fd9bd91e71a7851b4`.
No tracked changes at entry. Root AGENTS.md governs. The three untracked files
below are pre-existing inputs under this directory and stay outside the commit.

| Input | SHA-256 |
| --- | --- |
| User attachment `~/Downloads/pi-8-implementation-prompt.md` | `d9e87967b5cbec0164e42929a8ae0fc6b53637678a5aaaf4a3742aa9359d4bb9` |
| pi-8-detailed-implementation-plan.md | `894def644ea5b39bc9aa38e3484c97de2e5964baae6a154811d5aab3ff6baa86` |
| pi-7-detailed-implementation-plan.md | `40f26ae872db031f2e167aed3bb3a66b124683ec189dca47669493d17c204029` |
| pi-6-conditional-offline-development-codex-handoff.md | `6855d4cb55a5ea2b9d0eecda01c2714b8c45ac5c5e3208d0337474b0d2fc33f1` |

The user authorizes a local, single-commit audit. The attachment specifies scope.
The roadmap §6–7 supplies acceptance, consumer OpenAPI supplies the public
contract, and current code and migrations govern actual behavior. Reading
Logbook lives in `examples/reading-logbook`; the optional domain distribution
is `reference-apps`. Git blobs and the recorded source inventory distinguish
checkout inputs from installed dependencies and historical runs.

## Challenge and scope

| Plan assumption or gap | Frozen response |
| --- | --- |
| A fresh local run can substitute for earlier open gates | Split individual observations from release decisions. PI-0–4 independent gates stay open. PI-5 stays blocked, PI-6 synthetic stays locally complete and unpromoted, PI-7 stays a local candidate. |
| An ordinal evidence ladder can model acceptance | Require the exact evidence class per case. Native storage, installed isolation, live operator proof and independent acceptance answer different questions. |
| Available executables mean a safe environment | macOS sandbox launcher exists but the deny-network probe returned `sandbox_apply: Operation not permitted`. Docker is absent. Attempt canonical fail-closed PI-7 commands, withhold dynamic probes that require that fence, and use standalone static checks. |
| Prepared dependencies or an offline wheel imply provenance | Separate package content, clean install, prepared RECORD integrity and independently trusted wheelhouse. Build only from prepared dependencies with offline flags and no install, if available. |
| Consent rechecks serialize rights through physical sends | Inspect timing between recheck and dispatch and between delivery and revocation. Existing tests exercise representative interleavings. Atomic distributed issuer/dispatch requires separate evidence. |
| Local attempt journals establish recovery | Inspect original-key semantics and storage. A restored journal may predate the key. Restore proof requires external monotonic authority and both native stores. |
| Citation or accessible source implies rights | Treat model processing, delivery, replay, export and third-party transfer as distinct grants. Local fixtures carry no live rights or pricing authority. |
| Mock counts and static policy prove cost | Separate mock attempts, billing evidence and account-enforced caps. No external research or provider access required to record missing authorization. |
| Automation should orchestrate every historical command | A standard-library ledger validator with exact-class rules, source hashes and focused contract tests suffices. Reuse existing scripts for probes. Avoid generic command execution and new lifecycle burden. |
| Same-session skeptical review can close the audit | Deliver findings and a fresh-session handoff. Maintain independent acceptance as its own blocked gate. |

In scope are local source/contract inspection, safe static package and preflight
checks, fail-closed native preflight attempts, historical evidence indexing,
bounded ledger validation and a skeptical readiness assessment. Live providers,
pricing measurements, hosted IAM, external sources, Docker operations, real
restore/deletion, product remediation and memory promotion are outside this run.

## Frozen matrix

Each row records exact reproduction, roadmap links and required versus observed
evidence. PASS requires fresh matching evidence. Historical observations are
identified in the narrative and cannot supply PASS. Missing prerequisites
produce BLOCKED. A failing assertion with its required setup produces FAIL.
A deliberate omission without a blocker produces NOT_RUN.

| Cases | Required evidence |
| --- | --- |
| 01 provenance, 05 version, 28 cloud refusal, 32–36 audit integrity and verdict | Static |
| 02 distribution, 03 core turn, 04 separate consumer, 27 child fence and clean dependency provenance | Installed hermetic |
| 06–12 signed authority, retries, provider transport/capabilities/dispatch, embeddings | Deterministic synthetic |
| 13 retrieval authority, 15 real quality/cost, 29–30 deployed IAM and caps | Operator authorized live |
| 14 tool authority, 16–17 sharing/isolation, 19–22 disclosure, MEM-2 and original-key accounting | Deterministic synthetic |
| 18 atomic revoke/send | Operator authorized live |
| 23–24 two-store and stale restore | Native store |
| 25 physical erasure | Operator authorized live |
| 26 audit artifact redaction, 31 outage and rollback review | Static |

Roadmap mapping follows the attachment, with operations rows additionally tied
to the relevant A cases. P8-36 records the verdict, independent acceptance
remains a separate gate.

Order is baseline and hardening, static and fail-closed probes, evidence
validation, skeptical source review, profile disposition and handoff. Stop at
launcher rejection, missing dependencies, unknown daemon ownership, unexpected
egress or any risk of secret capture. Preserve failures. Reject degraded smoke,
relaxed authorization, new idempotency keys, or changed fixture thresholds as
ways to pass. Roll back the audit commit as a unit if needed, withdraw the
verdict and retain attempt, revocation and deletion evidence.

Same-session hardening completed before audit implementation on 2026-11-03.

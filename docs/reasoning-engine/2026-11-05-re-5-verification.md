# Synthetic reasoning preview implementation and verification

2026-11-05 America/Los_Angeles. Base
`bf9c7eecd74eefce24aaa05be23e2b315366e677`, tree
`92e3c7c57eec7303788466174c4a6b203be99a16`. The implementation is the
single commit containing this report. Use `git rev-parse HEAD 'HEAD^{tree}'`
from that commit for exact identity and `git diff-tree --no-commit-id
--name-status -r HEAD` for inventory. A pre-existing PRD relocation and ten
untracked predecessor plans/prompts were excluded from the implementation.

## Profile and evidence

| Tier | Status | Scope and outstanding proof |
| --- | --- | --- |
| E0 | Tested, inherited aggregate failures | Closed preview request, workflow and SDK contracts. Scope, original intent and permission denial tests passed. The SDK aggregate retains inherited planning and PI-6 seals that reject the current tree. |
| E1 HTTP | `DEVELOPMENT_ONLY`, tested | One IPv4 loopback process and credential. Fixed V1 arithmetic fixtures, synthetic principal, zero external-source or real-provider work. Fresh wheel-only consumer, cancellation after injected dispatch, backpressure, original-key replay, epoch rejection and operator disable tested. Independent acceptance open. |
| E1 native | Tested | Disposable local PostgreSQL 17.11 with pgvector, migrated isolated databases, real spawned processes, fake generation only. Recovery, cancellation, terminal cleanup and rollback verified in the internal workflow, separately from HTTP. |
| E2 installed model | `BLOCKED_UNVERIFIED` | Requires an authorized installed endpoint, matching tokenizer, actual resource and latency measurements, and held-out real-model tasks against a matched direct baseline. No installed-model attempt was made. |
| E3 hosted inference or source | `BLOCKED_UNVERIFIED` | Requires account-specific eligibility and settlement, authorized endpoint and budget, PI-5 issuer-bound atomic source-send rights and HXE acceptance. No live source/provider attempt was made. |
| E4 distributed | `BLOCKED_UNVERIFIED`, production `NO_GO` | Requires verified deployed principals and app/workspace grants, replica-wide fair admission, monotonic grant/intent restore, private ingress and fenced egress, and topology-specific cancellation and retention drills. |
| E5 independent utility and promotion | `BLOCKED_UNVERIFIED`, `NO_PROMOTION` | Requires independently custodied blind paired tasks, a trusted pre-generation cohort feature, mechanically verified rows and preregistered bounds and vetoes tied to the exact build, endpoint and scope, plus independent approval. |

The [preview protocol](synthetic-preview.md) and [ADR](../decisions/0030-synthetic-reasoning-preview.md)
define the chosen topology. In-memory HTTP receipts last one launch epoch.
The single authenticated scope uses immediate rejection and zero application
queue. Fairness across multiple independent actors or replicas and durable
public reconciliation remain outside this profile. The operator switch
blocks new original keys while pinned work retains its admission and
receipt. The canonical workflow owns the only attempt record. No second
provider usage balance or refund rule was introduced.

Canary publication fails before writing a pointer. Restored canary pointers
select fixed V1, and already-stored signed V2 plans fail before any count,
generation, retrieval or verifier operation. An artifact verifier remains
blocked by absent independent corpus custody, authoritative artifact
bindings and a separately approved scoring protocol. Adding a parser for
author-generated rows would provide no independent verification. V2 remains
executable in the isolated offline comparator. Grounded shadow changes no
physical work or source authorization.

## Adaptive baseline reconciliation

`make reasoning-adaptive-check` on the base produced 42 failures, 28 passes
and one historical evaluation deselection. Every failure falls into these
groups. Counts are from the baseline parametrizations.

| Baseline tests | Count | Cause and current evidence |
| --- | ---: | --- |
| Candidate comparison, corrupt V2 decoder, reservation cancellation/deadline, unknown second generation | 19 | Setup published a signed fabricated canary before the behavioral assertion. The current tests exercise the same comparison, parser, reservation and original-key assertions in the explicitly offline host. |
| Narrowed limits, slice mismatch, rollback, corrupt pointer | 20 | Setup published a fabricated canary. Current tests cover installed shadow and V1 limits, scope/policy/build/fixture/staleness and rollback. Additional restored-pointer cases cover valid signature, forgery, wrong scope/protocol/endpoint and expiry. |
| Forged publication | 1 | The expected signature-specific error was superseded by unconditional evidence denial. Current assertion requires rejection and no new generation. |
| Degenerate verifier and evaluator input boundary | 2 | The historical seal refused changed runtime bytes. Current developer controls use explicit authored inputs under a distinct non-promoting source seal, and retain the objective invalid-output and oracle separation assertions. |

The historical manifest, split, cases, oracle, scoring and lock remain
unchanged. `make reasoning-adaptive-eval` archives its original commit
`992118dd43cf7225541b1eb9866374a79fa6ec58`, tree
`02c2f7af50e783159026e381fe2458e82b859f5e`, and runs the historical test
from that tree. Replay returned 182 cases, 924 rows, zero safety vetoes and
`NO_PROMOTION`. The original semantic digest
`d94c8b8aab6f582661035842b6353e511a8ac169f7a526ef3b5f09f397ac3253`
and seal `b11768e98878eeee4b8f091c7338357bf8cfc102887d861a0c9f4d9df46d5064`
matched. The decomposition-favorable subgroup regression remains in the
[historical report](re-4-verification.md). The additive
`adaptive-development-conformance-v1` source seal is
`dc525f49295aade18e58c243ec60519b1a371c6d9b7ed89640a1a81f612ad0f1`.
It binds the current conformance tests and execution sources and carries no
paired usefulness or promotion claim.

## Native baseline and final run

The base full suite produced 54 passes and four failures. Two adaptive
process tests stopped at stale canary setup. The queued and reserved
cancellation assertions expected one send. Running the cancellation tests
at parent `992118d` reproduced two passes and the same two failures,
with the send witness recording zero in both failed cases. The fixed
assertions require zero for queued/reserved and one for dispatched/checking,
and retain cancellation and receipt checks. The adaptive and grounded
hermetic crash simulations use a dedicated base exception because raising
`SystemExit` inside an asyncio child task intermittently stranded an AnyIO
worker during interpreter shutdown. The simulated crash still bypasses
workflow exception recovery, and the native drills use actual process exit.

The final run passed 59 tests against a fresh PostgreSQL 17.11 cluster
listening only on a private Unix socket. The process cases cover loss before
reservation, after reservation, after the dispatch marker, after fake
acknowledgment, between steps and after terminal commit. The terminal test
exits a worker after the transaction commits and observes metadata-only
original-key replay. The shadow recovery drills roll back after process loss
and compare exact child IDs, send counts, pinned strategy and plan digest.
A dispatched operation without a committed observation retains its
original binding and unknown physical accounting. The standard sandbox
blocked PostgreSQL shared-memory setup. The successful native runs used an
approved local execution environment and disposable clusters.

## Commands and results

| Command | Observed result |
| --- | --- |
| `make reasoning-check` and `make reasoning-eval` | 122 passed. Offline benchmark 64/64 valid rows. |
| `make reasoning-orchestrator-check` and `make reasoning-orchestrator-eval` | 57 passed and 60 scripted pairs. |
| `make reasoning-grounded-check` and `make reasoning-grounded-eval` | 77 passed. Evaluation selection 1 passed, 76 deselected, 60 pairs and 180 rows. |
| `make reasoning-adaptive-check` and `make reasoning-adaptive-conformance` | 75 passed each. Active source seal and restored signed-plan denial verified. |
| `make reasoning-adaptive-eval` | 1 passed, 68 deselected in the historical checkout. |
| `make workflow-check` and `make workflow-postgres-check` | 70 hermetic and 59 native tests passed. |
| `make synthetic-reasoning-check` | 3 HTTP tests passed. Includes active cancellation, unknown resource accounting, queue denial, capacity, scope and epoch checks. |
| `make synthetic-reasoning-install-check` | Clean SDK and consumer wheels passed over loopback. Exactly three fake sends, including a stalled third send canceled through the public SDK. The fixture auditor and SDK were the only installed project packages. |
| Standalone server `SIGUSR1` drill | Same epoch became disabled, new keys returned 403, original receipt and exact replay remained available. |
| `make sdk-check` | Contract check passed. Test run had 357 passed, 12 deselected and 25 failed. An archived base run of the affected tests with the same selector reproduced the exact same 25 failures (84 passed, 11 deselected). Failures are one planning source identity assertion and 24 PI-6 frozen-protocol mismatches. Existing unrelated seals were preserved. |
| `make sdk-install-check` | Wheel and rebuilt sdist passed with an isolated writable UV cache after the default cache failed sandbox access. |
| `make release-profile-check` | 10 profile and 14 artifact tests passed. The SDK allowlist admits the new named module while retaining the strict artifact boundary. |
| Targeted auth, context authorization, context, inference execution, provider usage, privacy usage, retrieval context and LiteLLM gateway | 215 passed. Existing conformance covers missing capabilities/counters, account eligibility, reservation, count failure, fallback, cancellation and revoke-before-send. Zero Python network attempts under the offline runner. |
| `make backend-lint`, `make naming-policy-check`, `git diff --check` | Passed. |

## Independent review handoff

Review the exact commit containing this report against the recorded base.
Reproduce `make reasoning-adaptive-conformance`,
`make synthetic-reasoning-check`, `make synthetic-reasoning-install-check`
and the disposable PostgreSQL workflow target. Challenge the restored
V2 plan denial, epoch and original-key bindings, and the cancellation and
disable races. Inspect the installed package boundary, verify the historical
source seal at its original revision, and compare the SDK aggregate failures
against the base. Return a severity-ranked remediation report tied to the
exact revision and topology. Use
`re-5-sol-medium-independent-review-prompt.md` when supplied to the separate
reviewer. It was not among the two implementation attachments.

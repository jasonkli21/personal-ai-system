# MEM-7 independent-review remediation — 2026-11-04

**Result: `ACCEPT_E0_E1_CANDIDATE`; separate review of the revised commit is
required. Full MEM-7 exit remains `BLOCKED`; production remains `NO_GO`.** This
remediation addresses the three confirmed local findings in the attached review.
It adds no runtime route, issuer, flag, migration, dispatcher, or external send.

## Findings addressed

| Finding | Change |
| --- | --- |
| M7-R01 — missing recovery anchor treated as a fresh empty owner | The synthetic store now keeps an explicit registered-owner set outside restorable ledgers. `SyntheticHost` bootstraps a new fixture owner by seeding its empty ledger and surviving anchor. Missing registration or anchor makes recovery unavailable; mutation cannot infer freshness from an empty ledger. Shared-store scenarios explicitly bootstrap their second owner. |
| M7-R02 — deterministic resource evidence omitted from replay | Report schema v2 adds ledger representation estimates and per-case resource envelopes to semantic evidence. Verification checks source and semantic digests, report version, exact case IDs, envelope cardinality, and estimate cardinality before accepting replay. Runtime timing, platform, Python version, and unavailable native measurements remain outside semantic equality. Failed attempts retain an explicit empty baseline envelope. |
| M7-R03 — unsubstantiated physical deletion receipt accepted | The v1 `StoreVerification` contract rejects `physical_verified` for every currently modeled topology, even with a syntactically valid hash. The twelve-store inventory remains unknown, pending, or logical suppression as applicable. Actual observed-topology proof requires a future independently reviewed contract. |

Regression coverage reproduces the lost-anchor state, confirms explicit bootstrap
still works, rejects a dummy backup proof, rejects modified resource evidence and
incomplete envelopes, and allows runtime timing variation. Existing stale-ledger,
lost-ACK, concurrency, per-owner isolation, inventory graph, and campaign failure
behavior remain covered.

## Verification

Environment: repository `backend/.venv`, Python 3.11.15, pytest 8.4.2, Ruff
0.16.10. The shell did not initially have a `python` command on `PATH`; the first
Make target attempt exited 127 before tests started. Re-running with
`backend/.venv/bin` prepended to `PATH` succeeded.

| Check | Result |
| --- | --- |
| `make memory-governance-check backend-lint naming-policy-check` (with venv on `PATH`) | PASS: 105 tests, Ruff clean, naming policy PASS, 2 naming-policy unit tests OK |
| Fresh evaluator process A | PASS: 69/69 matched; semantic SHA-256 `3ad560ddda01d2e86fde1bc6f18b8fd09d2597f1b1e0fac0d601f141643e2863`; output SHA-256 `2853938b604716033a6dfcd160102a6f107b26190055ad3cfab5c6f7da302c6c` |
| Fresh evaluator process B | PASS: 69/69 matched; same semantic SHA-256; output SHA-256 `6af20185f7fe56ca17a724fc61a25faaf3a5f19cba4e24f8ed00bd571ba48fa1` |
| Fresh-process verification of A and B | PASS: both `verified: true` with the same semantic SHA-256 |
| `git diff --check` | PASS |

Each replay retained 69 attempted rows and seven noncompletion outcomes. Two
Python 3.11 end-of-support future warnings appeared during tests/evaluations; they
did not affect results. The broad backend offline suite, provider checks, native
database/restore tests, and cloud/deployment checks were not run in this
remediation. The attached independent review's adjacent network-fenced invocation
reported 327 passing tests but exited 3 because one socket creation was attempted;
it was not a clean zero-attempt pass. Its broader backend run was interrupted and
has no complete result.

## Acceptance boundary

The local evidence supports only an E0/E1 candidate. No E2 durable transaction or
cold-restart proof, E3 deployed issuer or physical send, E4 physical deletion and
restore proof, or E5 blind real-agent utility and measured cost was established.
Keep the 2026-11-04 independent-review matrix's G15, G19, and G22 local
counterexamples closed by these changes, while G25–G27 and full phase exit remain
blocked pending separate review and external evidence. The production decision
remains `NO_GO`.

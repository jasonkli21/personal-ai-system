# PI-8 independent review remediation — 2026-11-03

## Decision and scope

This commit addresses PI8-R01–R04 as additive audit-tooling and documentation
work. It changes no application runtime, migration, dependency lock, public API,
default-off flag, fixture, or historical evidence. PI-8 independent acceptance
remains `pending`; production and all external/live/native profiles remain
`no_go` or `blocked_unverified`. R05–R08 are carried forward with explicit
owners and preconditions in the [cross-phase gate registry](pi-cross-phase-gate-registry.md).

The review target/pre-fix SHA is
`a80236648e2635a267f122ba0fd958cafa09c096`. Its parent is
`9b4b0f4db358ac97c156a615831dbb81a0a636a9`. The original v1 ledger remains
byte-identical to Git blob
`cd4c4dda26b878e8b1ea35843d9032c68d143b69`; the SHA-256 of the file at the
review target is `2ee32831363adde9bcce91cbe8bcaa2e71b2a4f027bbb5122042490116de5f18`.
The remediation commit is the single commit that adds this report. Git cannot
store that commit's own SHA inside its tree without a hash cycle; resolve its
full SHA with:

```sh
git log --diff-filter=A -1 --format=%H -- docs/platform-independence/pi-8-independent-review-remediation-2026-11-03.md
```

The delivery records the resolved post-fix SHA. Its tree binds this report and
all changed/new audit files.

## Findings and disposition

| Finding | Disposition |
| --- | --- |
| R01 — mutable/incomplete input inventory | Fixed in `backend/scripts/pi8_check.py`: the checker requires a full reviewer-supplied exact commit SHA descended from both the PI-7 baseline and PI-8 review target, checks `HEAD`, rejects staged/unstaged/untracked state and hidden/unmerged index entries, returns the pinned tree ID, and verifies the v1 blob at both the historical and target commits. It also rejects ignored untracked files within audited paths except interpreter bytecode and `.DS_Store`. Every tracked file in the target is thereby bound by the Git tree. The v1 ledger's self-reference is excluded from content hashing by using its immutable blob ID; Git path listing does not follow symlinks or read private materials. |
| R02 — mandatory cases can be N/A'd | Fixed: the closed status set excludes `NOT_APPLICABLE`; A01–A22 mappings and evidence classes are fixed in code; all installed/native/live cases must remain blocked or failed because those evidence classes were unavailable in the dated run; `NOT_RUN` requires `observed=none`; summary counts must equal rows; release remains hard-coded `pending`/`no_go`. P8-26/28 remain truthful static PASS rows, and P8-36 may describe the static no-go verdict without changing the release rollup. |
| R03 — prose claims can masquerade as proof | Fixed within the audit's limits: the success message says `LEDGER_STRUCTURE=VALID`, `EXECUTION_EVIDENCE=AUTHOR_REPORTED`, `INDEPENDENT_ACCEPTANCE=PENDING`, `PRODUCTION=NO_GO`. A versioned command-receipt register validates argv, tested revision, prerequisites, evidence class, fence, exit/counts/warnings, digest and provenance. It rejects self-asserted `INDEPENDENTLY_REPRODUCED`; only a fresh external reviewer can supply that evidence. The checker executes no ledger-supplied command. |
| R04 — archive provenance wording | Fixed: the report table now says both the wheel and sdist were built from the offline checkout. No sdist-to-wheel round-trip or clean installed acceptance is claimed; P8-02/03/04/27 remain blocked. |
| R05 — source revoke/send race | Deferred `BEFORE_ENABLEMENT`. No live leak was reproduced; atomic issuer-backed attempt permits and concurrency evidence require a separate security/operator gate. |
| R06 — stale original-key journal restore | Deferred `BEFORE_ENABLEMENT`. Native monotonic authority and mixed-age two-store recovery were not run. |
| R07 — marker-free legacy export | Deferred as a bounded hypothesis `BEFORE_ENABLEMENT`. Existing export guard checks retrieval attribution markers; no unmarked leak is established. Legacy serializer/row inventory and canary are still required; unknown origin must remain quarantined before external export/replay. No runtime behavior was broadened. |
| R08 — dependency origin | Deferred `BEFORE_ENABLEMENT`. Prepared RECORD checks and archive inspection are not independent build provenance. A pinned wheelhouse, clean no-index install and native fence remain outstanding. |

The [cross-phase gate registry](pi-cross-phase-gate-registry.md) names the
owner role and exact prerequisite for R05–R08 and the predecessor gates,
including PI-5 R01–R03/P5-24/28, PI-6 P6-02/15/29/32, PI-7 native fence,
wheelhouse, Docker, IAM/billing, recovery/erasure and fresh review, and the
MEM-2 default-off/MEM-3+ freeze. Roadmap, PI index and current state now point to
that registry. No predecessor is promoted.

## Changed paths

- `Makefile`
- `backend/scripts/pi8_check.py`
- `backend/scripts/test_pi8_check.py`
- `docs/current-state.md`
- `docs/platform-independence/README.md`
- `docs/platform-independence/platform-independence-roadmap.md`
- `docs/platform-independence/pi-8-implementation-report.md`
- `docs/platform-independence/pi-8-review-verification-v2.json`
- `docs/platform-independence/pi-cross-phase-gate-registry.md`
- `docs/platform-independence/pi-8-independent-review-remediation-2026-11-03.md`

At start, three pre-existing untracked user files were preserved and excluded
from this remediation commit: `pi-6-conditional-offline-development-codex-handoff.md`,
`pi-7-detailed-implementation-plan.md`, and `pi-8-detailed-implementation-plan.md`.
The user's pre-existing edits to `Makefile`, `backend/scripts/pi8_check.py`,
and this PI-8 report were completed in place. No existing file was discarded.

## Checks and results

All execution below was local and offline. No provider, search, cloud, Docker,
deployment, private-data, billing, restore, deletion, or destructive operation
was performed.

| Command | Result |
| --- | --- |
| `backend/.venv/bin/python -I -m unittest discover -s backend/scripts -p test_pi8_check.py` (first attempt) | Failed: 11 test methods; the initial draft incorrectly required an observed class for P8-03, whose historical row is blocked with `observed=none`. |
| Same focused unittest command (second attempt) | Failed: 11 methods; one summary-laundering regression expected the wrong validation branch. |
| Same focused unittest command (third attempt) | Passed: 11 tests. |
| Same focused unittest command (final source) | Passed: 15 tests, 0 failures, 0 skips. Includes exact SHA/ancestry/clean tree, dirty/untracked and divergent HEAD, ignored source, duplicate/missing case, fixed mapping/class/dispositions, PASS downgrade, N/A/counterfeit live/native evidence, count manipulation, no-go rollup, receipt provenance/schema, duplicate/oversize JSON, and immutable v1 identity. |
| `git diff --check` | Passed; no whitespace errors. |
| `make pi8-check` before commit | Not run: checker intentionally refuses a dirty/untracked checkout and requires the independently pinned final commit SHA. |
| `make backend-lint` | Attempted; failed at `/bin/sh: python: command not found` (exit 2), before lint ran. The equivalent prepared-environment command `backend/.venv/bin/python -m ruff check backend/scripts/pi8_check.py backend/scripts/test_pi8_check.py` passed. |
| `bash -n infrastructure/gcp/deploy.sh` | Passed syntax parse only; deployment was not invoked. |
| `make -n pi8-check PI8_EXPECTED_COMMIT=0123456789abcdef0123456789abcdef01234567` (first attempt) | Failed (exit 2) because the initial target-specific export syntax was parsed as a prerequisite. The Makefile now exports the variable globally; the same dry-run passes and shows quoted shell-variable expansion. |
| Same `make -n` command after correction | Passed; printed the required-SHA guard, checker command and focused unittest command without executing them. |
| Native fence, installed consumer, Docker, live provider, cloud, billing, restore, physical erasure | Not run; prerequisites/authority unavailable or not granted. They remain blocked, not passed. |

Receipt `artifact_sha256` values in
[`pi-8-review-verification-v2.json`](pi-8-review-verification-v2.json) hash the
normalized result summaries stated here, not raw prompts, private data or
command transcripts. `revision=WORKTREE:<pre-fix-sha>:<digest>` pins the
concatenation of checker source, checker tests and Makefile as they were tested
(SHA-256 `eb7e8a921071cadfa401b76f4fcdfbc565d4db7b6bff8852b3d18de3cfe43b9e`);
it is not represented as a clean committed revision. Receipts are explicitly
`AUTHOR_REPORTED`.

The initial failed test attempts are retained above. The fix did not erase the
original v1 failures, hashes, fixture history or predecessor gate evidence.

## Rollback and remaining acceptance

Rollback is limited to this audit-tooling/documentation commit. Reverting it
restores the pre-fix checker and wording; it must not alter v1 evidence,
fixtures, locks, receipts, tombstones, logs, or the three preserved user files.
No change to runtime was made.

Independent PI-8 acceptance is still required. Before enabling any external or
live profile, close the gates in the registry with separately authorized
identity/source, provider/cost, native install/network, distributed journal,
cloud/IAM, restore/erasure and real-utility evidence. Static/synthetic checker
success cannot promote those gates.

## Fresh-session independent review handoff

Start a new GPT-6.1 Sol / High session and resolve the exact remediation SHA
with the report-path Git command above. Verify its parent and full diff. Inspect
the v1 ledger at both commits and prove the blob ID is unchanged. Run
`make pi8-check PI8_EXPECTED_COMMIT=<resolved-sha>` in a clean checkout; the
expected result is a structural-validity line that still says author-reported,
independent acceptance pending, and production no-go. Run the focused 15-test
suite, then independently challenge malformed/duplicate JSON, N/A and count
laundering, fake live evidence, missing/added/edited paths, untracked/staged
state, descendant HEAD, forged independent receipt, and changed no-go rollup.
Inspect the complete cross-phase registry and verify all inherited blockers
remain. Reassess R01–R08 separately. Do not infer native, installed, provider,
cloud, billing, restore, deletion or production acceptance from local tests.

Possible verdict: a scoped static/synthetic audit may be accepted while all
installed/live/native/cloud/private-data profiles remain `BLOCKED_UNVERIFIED`
or `NO_GO`. No subagents are needed; this is a fresh independent session, not
the implementer's self-review.

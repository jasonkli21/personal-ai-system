# Reasoning offline verification · 2026-11-04

**IMPLEMENTED_E0_E1_REVIEW_PENDING.** Evidence covers the proposed contracts
and the frozen synthetic benchmark. Task quality is proxy-only. Production
remains NO_GO. Review the single implementation commit against its parent.

## Provenance and measurements

The implementation base was `4c76377e2cb3e37673ff8a393bf9ca2125534a06`
with tree `16179c5a8a2887a9c7e07f9597e9696605ab8b`. Both prereview
measurements used that checked-out parent, a dirty worktree and the same
byte-verified implementation sources. Entry included a user PRD relocation
and two user-authored planning documents. Those changes were excluded from
the implementation commit. See the [entry inventory](2026-11-04-re-0-plan-hardening.md).
The resulting commit identifies the reviewed source without embedding its own
SHA in the evidence. The locked generation was sealed before measurement.

- Darwin arm64, CPython 3.11.15, offline deterministic fixture responder.
- [Manifest](../../backend/src/personal_ai/evaluation/fixtures/reasoning/manifest-v1.json)
  SHA-256 `2749b02f37b32571e913bbd2240942cfbe3e1032f424823e3f950219f6a888a9`.
- Both fresh-process runs produced semantic SHA-256
  `112d25c406f91eacf789910ca780c0210d4cc5c0859f2b2f07d53413353389dd`
  and byte-equivalent semantic JSON after canonicalization. Elapsed time,
  Git provenance and fence environment are separate.
- 32 cases across eight families, eight author-visible holdouts, 64/64 rows
  retained. Outcomes were 29 scored, 28 unsupported, four denied, two failed
  (cancel and uncertain), and one timed out. No internal errors, coverage
  failures, safety vetoes, blocked Python effect attempts or console leaks.
- Direct covered 32/32 cases with 26 fake attempts, 25 observed fake results
  and 21/25 exact proxy successes. It ran zero checks. Numeric direct was
  exact on two of four pairs. The diagnostic added four local checks to four
  matched fake attempts, accepted two results and abstained twice. It also
  achieved two of four exact successes. All 28 unsupported pairs remain in
  the grid. The difference is abstention behavior on this fixture, with
  no real-model quality or uplift claim.
- Estimated input/output units were 80/31 direct and 4/4 diagnostic. The
  lost acknowledgement contributes an attempt without an observed result.
  No billed cost, actual model tokens or native recovery were measured.
- Seatbelt returned `sandbox_apply: Operation not permitted` on this host.
  The run used the Python effect audit and subprocess deadline. Native
  network isolation is unverified in this evidence.

## Reproduction and regression checks

Use the repository root with `backend/.venv/bin` on PATH. For existing
offline targets use `LITELLM_LOCAL_MODEL_COST_MAP=True UV_OFFLINE=1
AI_PROVIDER=fake APP_ENVIRONMENT=test PYTEST_DISABLE_PLUGIN_AUTOLOAD=1`.
For the full offline suite, add the absolute `sdk/python/src`,
`examples/project-checklist/client/src` and `examples/project-checklist/host/src`
directories to `PYTHONPATH`. The reasoning launcher scrubs its environment
and needs no model configuration.

| Command | Observed result |
| --- | --- |
| `make reasoning-check` | 44 passed, no Python network attempts. |
| `make reasoning-eval`, repeated in a fresh process | Both passed, 64/64, identical semantic digests. |
| `make real-task-eval` | E1 scripted, 36 retained rows, coverage and safety canaries passed. |
| `make workflow-check` | 70 passed. |
| `make memory-governance-check` | 105 passed. |
| `make planning-eval` | Inherited `planning_baseline_changed_requires_new_version`, also reproduced using a Git archive of the base. |
| `backend/.venv/bin/python -B backend/scripts/offline_test_runner.py -q -m 'not loopback_http' backend/tests/test_pi6.py` | 22 passed, 24 failed, 11 deselected. Same failure count and protocol mismatch on the base. PI-6 fingerprints the whole Python/JSON package tree. No historical lock was changed. |
| `backend/.venv/bin/python -B backend/scripts/offline_test_runner.py -q backend/tests/test_memory_research_study.py backend/tests/test_memory_research_governance.py` | 11 passed, 59 setup errors. Inherited `study_source_changed_requires_new_generation` reproduced on the base. Current longitudinal v4 inventory differs at the preexisting memory governance contracts file. |
| `make backend-test-offline` | Initial collection lacked `personal_ai_sdk`. With the source import paths above, 2,649 passed, 221 failed, 159 errors, one skipped and 180 deselected. All 380 failing/error test IDs also failed on the archived base under the same settings (236 failed and 161 errors there). The archive lacked Git checkout metadata. Sandbox socket permission errors also blocked loopback fixtures. All 44 reasoning checks passed within the broad run. |
| `make backend-lint`, `make naming-policy-check` | Passed. |
| Changed documentation local link validation and `git diff --check` | Passed. |

The PI-6, real-task, context/planning and memory corpora and historical
source locks have no patch. PI-6 and planning include recursive package
identity in their locks, so the added sources also change those inventories.
A new generation for those previously blocked experiments requires
separately scoped revalidation and evidence.

## Independent review

Start with `git show --stat <commit>` and `git diff <commit>^ <commit>`.
[ADR 0028](../decisions/0028-reasoning-policy-and-execution-ownership.md),
the [proposed request](api-contract-v1-proposed.md), the inert catalog and
the [threat map](threat-model.md) are the design surface. The change also
contains the fixture/manifest, seal, candidate, fake port/observer, scorer,
launcher, focused tests, Make targets and documentation routing/status.

Save each ignored report before the next invocation and compare the
`semantic_sha256` and `semantic` fields. Confirm both process exits were
zero. Inspect coverage and resource equality on the four numeric pairs
using `prepared_sha256` and observed attempts. Inspect scope negatives
in the third and seventh families and logical fault/replay in the eighth.
The test file maps malformed wire values, effect audit, forged citations,
counter discrepancy, input isolation, missing/duplicate rows, manifest/
fixture/scorer/driver drift, and stored privacy to executable assertions.
The synthetic port models pre-dispatch cancel/deadline and provider
acknowledgement loss. It has no live provider handoff, native timeout race
or post-dispatch recovery capability. The scorer and benchmark host are
trusted local code. The byte lock and Python audit protect against drift
and accidental side effects in that code.

## Blocker ledger

| Gate | Disposition and evidence still needed |
| --- | --- |
| Independent E0/E1 acceptance | Pending separate Sol High review of the exact commit, with a single Luna remediation handoff if needed. |
| E2 local model, measured utility, native fencing | Blocked/unverified. Needs separately authorized local inference, calibrated held-out study, accountable usage and effective native network/process/filesystem isolation. |
| E3 installed/issuer/native workflows | Blocked/unverified. Needs signed source-free installed consumer, current issuer-bound atomic send/revoke, native DB cancellation/recovery and mixed-age restore. |
| E4 hosted/cloud and production | NO_GO. Needs verified deployed identity, billing/privacy, physical restore/erasure, independent acceptance and operator authorization. |
| External coding study | Protocol only. Needs independently authorized external harness, controlled task/model/workspace and matched paired runs. |
| Future reasoning execution and promotion | Deferred to RE-1–5 by scope. This phase supplies versioned contracts and E1 observations. |

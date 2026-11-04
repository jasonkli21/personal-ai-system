# HXE-5 review remediation receipt

**Date:** 2026-11-03 (America/Los_Angeles)
**Reviewed input:** `hxe-5-independent-review-luna-remediation-handoff.md`
**Baseline:** commit `578ef8fe4a11bacc8bed56a58669f6816a4f5a70`, tree `a56cad7d2459583611eafb3276b767902e6626e9`, parent `60bcacb6cac1a252ecb2001b9324eab9dfd198c3`
**Scope:** release tooling, focused tests and operator/current-state documentation only.

## Findings

| Finding | Disposition |
| --- | --- |
| P1-01 process-group lifecycle | Added SIGTERM/SIGINT handling, TERM grace period, exact invocation-group cleanup, leader reaping, and child/grandchild plus concurrent-supervisor tests. Forced group signaling denied by a host returns `BLOCKED_SIGNAL_PERMISSION`; the fallback kills only the owned leader. |
| P1-02 resource envelope | Added a finite 4 GB per-process address-space cap on Linux. This macOS Python host cannot safely apply it. Process count, aggregate process-tree memory and session escape remain unenforced; results say E2 `BLOCKED` on every host. Missing controls make preflight `BLOCKED`, never PASS. |
| P1-03 exact source/tool identity | Install now requires externally supplied commit/tree and exact release-tool digests, a clean checkout, and matching probe bytes before native fencing or installer invocation. Final identity/cleanliness is checked again. Synthetic install output is `NON_ACCEPTANCE` with acceptance `BLOCKED`. Build/install reports include tool hashes. |
| P2-01 RSS semantics | Per-invocation RSS is null. The remaining observation is named as the supervisor's cumulative terminated-child high-water mark. |
| P2-02 stdout trust | Parsed counts and network-attempt lines are explicitly display-only and untrusted; tests forge both values. They do not establish test results or native network isolation. |
| P2-03 artifact digests | Clarified that the closed receipt validator authenticates receipt bytes only. Digests inside the receipt are assertions until an operator independently inspects and pins output bytes. No reviewer identity or release authority is inferred. |

## Verification

- `make release-profile-check`: PASS, 10 profile tests and 14 artifact/process tests.
- `make naming-policy-check`: PASS, naming check and 2 tests.
- Focused Ruff check of changed Python files: PASS.
- `git diff --check`: PASS.
- `make release-preflight`: expected exit 3 (valid but incomplete; release remains NO_GO).
- `make release-canary-check`: expected exit 3. Measurement exit 0; 140 displayed passes and 0 displayed Python network attempts. These stdout values are untrusted display data. Address-space control was unavailable on this macOS host; aggregate resource status remains BLOCKED. No model/provider was run.
- `make release-build-report`: exit 0; repeated SDK outputs bitwise equal. Tool/dependency origin and license review remain BLOCKED. The report recorded the dirty checkout.
- `make backend-lint`: BLOCKED because the Makefile invokes `python`, which is absent from this shell PATH. Direct Ruff check of all changed Python files passed.
- Not run: native source-free install, signed-server/issuer acceptance, full offline suite, native benchmark, provider/model/cloud/peer paths. The worktree is dirty and the externally controlled install pins are not available, so E2 install acceptance must remain BLOCKED.

## A01–A13 disposition

| Gate | Current disposition |
| --- | --- |
| A01 profiles/defaults | Focused profile suite passes; defaults and NO_GO behavior retained. |
| A02 validator | Receipt-byte validation remains; output-file digest values are explicitly unverified assertions. |
| A03 frozen history | No frozen PI-6/PI-8 evidence changed. Exact clean-checkout historical verification not rerun. |
| A04 reproducibility/origin | Repeat build succeeded; independent toolchain/dependency origin and licenses remain BLOCKED. |
| A05 source-free install | Dirty/unpinned paths are denied before installer invocation; native install not run; E2 BLOCKED. |
| A06 contract/identity | Synthetic protocol does not establish signed issuer/server identity; E2 BLOCKED. |
| A07 canonical read-only safety | Canary command completed at E1; no provider or real-send authority established; inherited gates remain open. |
| A08 resources | Signal and reporting defects remediated; macOS address-space and aggregate process-tree controls remain BLOCKED. |
| A09 real local model | NOT_RUN; remains BLOCKED. |
| A10 hosted/cloud/erasure | NOT_RUN; remains BLOCKED/NO_GO. |
| A11 documentation/rollback | Resource, RSS, signal and evidence claims corrected in operator guide and current state. |
| A12 optional peers | Deferred and unchanged. |
| A13 exact provenance | Source/tool pins are now required for install acceptance; external pin authority and a clean reviewed checkout remain owner prerequisites. |

**Decision:** all profiles remain `NO_GO`; independent acceptance remains `PENDING`. This remediation closes tooling defects without establishing local-preview E2, hosted, cloud or production readiness. The five pre-existing untracked HXE plan files were preserved and are not part of the remediation commit.

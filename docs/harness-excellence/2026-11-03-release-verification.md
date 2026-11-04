# Operational release implementation receipt — 2026-11-03

**AUTHOR_REPORTED. Independent acceptance pending. Every release profile NO_GO.**
HXE-5 was implemented in one session without subagents. This delivers the
hardened offline evidence/tooling slice, not independently accepted preview or
production deployment. The external review must assess these limitations rather
than treat this report as signoff.

Entry: `60bcacb6cac1a252ecb2001b9324eab9dfd198c3`, tree
`b11c6538bd9dc4d6b565393ba2e5e8981694d822`, branch `main`. Target is the single
commit containing this receipt; the delivery records its exact SHA/tree outside
the commit to avoid a hash cycle. The source-free SDK package inputs remain
identical to entry; committed build observations therefore bind that exact entry
source. Worktree canary observations include exact tooling content hashes and
checkout-status digest, never claim a clean committed execution. User's five
untracked planning documents remain excluded and unchanged.

## Decisions and changed contracts

The [same-session hardening decision](2026-11-03-release-plan-hardening.md) preceded
functional edits. Chose stdlib-only compositional tooling instead of a new domain
ledger or an installer that bootstraps its own trust. No runtime, SDK or HTTP
contract changed. Provisional SDK 0.1.0 / HTTP v1.2.0 remain unchanged. Frozen
planning v35, benchmark source generation 9, cases, thresholds, prior manifests
and the historical 21 PASS / 15 BLOCKED receipt remain byte-faithful.

New developer contracts: `release-profile-v1`, `release-receipt-v1`,
`release-trust-v1`, `release-scorecard-v1`, `sdk-origin-v1`, `artifact-build-v1`,
`release-preflight-v1` and `source-free-install-v1`. Their closed definitions live
in the release scripts. The release validator is intentionally incapable of
emitting GO or independently accepted, even with a review-artifact digest. A digest
binds bytes; reviewer authentication and final release authority remain external.
No command can fill the independent-review case with an author execution receipt.

Inventory: four release scripts (`release_profiles`, `release_artifacts`,
`release_preflight`, `release_process`), one unrelated `source_free_sdk_probe`, two
focused unittest files and one corrected existing auth fixture; four capability-named Make targets; operator guide and
owning SDK/inventory/router/current-state/gate-registry updates; this receipt,
hardening note and two dated machine reports. No new dependency or migration.

Narrowed delivery: repeatability and native installer support cover the
**dependency-free SDK only**. Backend/optional artifacts reuse existing build and
consumer checks; their independently authenticated transitive wheelhouse and
repeat-build acceptance are not delivered here. Synthetic public-wire proof is
separate from installed signed server acceptance. No real local model, full idle/
setup/TTFT measurements, E3–E5 proof, public distribution or optional peer work.

## Commands and observed results

All commands run from the repository root. For existing commands needing the
prepared environment, use:

```sh
export PATH="$PWD/backend/.venv/bin:$PATH"
export UV_OFFLINE=1
export UV_CACHE_DIR=/tmp/pas-release-uv-cache
export LITELLM_LOCAL_MODEL_COST_MAP=True
```

| Ref | Exact command | Exit / observation |
| --- | --- | --- |
| C1 | `make release-profile-check` | 0; 9 profile tests plus 9 artifact/process/probe tests; adversarial subcases included |
| C2 | `make naming-policy-check backend-lint` | 0; naming and two checker tests; Ruff pass |
| C3 | `make sdk-check` | 0; 379 passed, 12 deselected; zero Python forbidden network attempts |
| C4 | `backend/.venv/bin/python -E -s backend/scripts/release_artifacts.py build --uv /opt/homebrew/bin/uv` | 0; two bitwise-identical SDK wheels and sdists; origin/license review BLOCKED |
| C5 | `make sdk-build sdk-install-check` | 0 after writable offline cache configuration; legacy wheel/sdist SDK and Checklist install pass; not independent origin/native acceptance |
| C6 | `make consumer-contract-check` | Make 2 / child 1; core probes and 142/190/56-test installed stages passed; final signed HTTP stage 102 passed / 91 setup errors from loopback bind EPERM; zero forbidden remote Python attempts |
| C7 | `make operations-check` | 0; 222 passed, zero forbidden Python attempts; cloud plan static-only, no live apply |
| C8 | `make offline-benchmark-check` | Make 2 / sandbox launcher 71; sandbox_apply EPERM, no native benchmark result |
| C9 | `make planning-eval memory-control-eval` | 0 individually in keep-going sequence; synthetic planning source matches v35, non-promotion retained; memory-control evaluation completed |
| C10 | `make mcp-adapter-check` | 0 in prepared optional environment; 44 passed; zero Python network attempts |
| C11 | `backend/.venv/bin/python -E -s backend/scripts/release_preflight.py --measure-synthetic` | 3 by design, measurement child 0; 140 passed; zero Python network attempts; readiness remains BLOCKED |
| C12 | `backend/.venv/bin/python -I -m unittest discover -s backend/scripts -p test_release_evidence_check.py` | 0; 15 tests; historical release command itself NOT_RUN without reviewer SHA/clean checkout |
| C13 | `git diff --exit-code 60bcacb -- backend/src backend/uv.lock backend/pyproject.toml backend/scripts/release_evidence_check.py docs/platform-independence/pi-8-verification.json docs/platform-independence/pi-8-review-verification-v2.json` | 0; no runtime/evaluator/ledger changes; historical ledger blob `cd4c4dda26b878e8b1ea35843d9032c68d143b69` |
| C14 | `make backend-test-offline` | See broad-suite disposition below; no full-suite pass claimed |
| C15 | `git diff --check` and local Markdown target check on changed docs | 0 |

Initial failures are retained: lint first lacked `python` on PATH (Make 2, shell
127), then passed with prepared PATH. SDK build first could not write default uv
cache (Make 2), then passed with `/tmp` cache and offline mode. The original
measured canary exited 1: its 2 MB file cap conflicted with the existing 2.1 MB
oversized-corpus negative. The wrapper cap became 4 MB; product test and thresholds
were unchanged. A direct diagnostic run observed 1 failed / 139 passed; corrected
measurement observed 140 passed. Formatting briefly moved a lint suppression;
placing it on the guarded argument restored lint. These are not hidden passes.

## Minimum acceptance matrix

Status describes this delivery's scope; a PASS does not close inherited production
gates. All observations below are author provenance. E2 blocked rows are not E1
passes counted as native acceptance. E3 hosted, E4 cloud and E5 longitudinal tasks
have no executed evidence.

| Case | Status / tier | Evidence command and observed result | Remaining owner |
| --- | --- | --- | --- |
| A01 | PASS E0 | C1/C2; executable settings-default assertions, fixed profile/owner/gate inventory | Release reviewer checks mapping and inherited rows |
| A02 | PASS E1 | C1: unknown/duplicate/oversize/nonfinite/deep JSON, source/profile/scope/toolchain mismatch, waiver/downgrade, tamper/exit contradiction and forged review denials | Independent reviewer authenticates external pins/signoff |
| A03 | PASS E0/E1 | C3/C12/C13: unchanged frozen runtime, source identity, locks and historical ledger/checker | Evaluation owner retains freeze |
| A04 | BLOCKED E2; PASS E0 SDK repeat | C4: equal outputs and hashes; no independently authenticated input origin or complete transitive license approval | Build/release operator |
| A05 | BLOCKED E2; PASS E1 negatives | C1/C5: inert tamper/hook/dependency/tool-pin/source-import negatives and unrelated extracted-layout probe pass; native fence unavailable, no accepted clean install | Native/build operator |
| A06 | BLOCKED E2; PASS E1 protocol | C1/C3 scope binding, typed errors, incompatible versions, uncertain SSE/original-key status/replay; C6 signed installed server blocked by listener EPERM | Identity/build operator |
| A07 | PASS E1 only | C11/C3/C10: canonical retrieval/context/source/tool/admission tests; expired/revoked/stale/wrong scope and poison denials, no live send | Source/security operator for real issuer/atomic send/revoke |
| A08 | PASS E1 only | C11/C7: canonical physical attempts, strict-free, ancillary counts/reservation denial/retries; wrapper finite wall/CPU/output and timeout negatives C1 | Inference/storage operator for native multiworker/restore proof |
| A09 | BLOCKED E2 | C11 reports real-task prerequisites; only synthetic child resource data measured | Runtime operator: approved build/GGUF, fence, store, hardware |
| A10 | PASS E0/E1 denial; BLOCKED E3/E4 | C1/C7 defaults fixed off, static-only cloud, all profiles NO_GO; no account/privacy/billing/restore/erasure proof | Provider/cloud/data lifecycle owners |
| A11 | PASS E0 | C2/C15 plus operator guide: provisional migration/support, licenses, source limits, redacted diagnostics and rollback; exact observed limitations | Operator validates instructions on supported host |
| A12 | NOT_RUN E3 | Optional peers remain default-off; no OpenClaw/OpenCode dependency or send; P0 native gates not complete | Product/source owner for future separately authorized peer |
| A13 | PASS E0 author/target separation | Entry SHA/tree above, final SHA/tree in delivery, C12 retains pending signoff; no author-filled independent acceptance | Independent Sol reviewer, then Luna remediation session |

## Build, measurement, safety and profile decisions

[Build report](2026-11-03-release-build.json) records every SDK source input,
archive/member hashes, interpreter/uv hashes and prepared dependency/license
inventory. These are observations, **not trusted origin pins**. Fixed epoch is
1700000000. Wheel SHA256:
`c49ef7fb8f67b8602737c91960d74ba8ac2f3af0543fc2d9d612bfb5e90f1f1b`;
sdist SHA256:
`8f617638da784c3017c6cdc754f428d16ca1d3facadf4dbdabbe5adb19a82ec2`.
No archive or member differences observed. Input authenticity, dependency closure
license review and broader package reproducibility remain operator blockers.

[Canary report](2026-11-03-release-canary.json): macOS arm64, Python 3.11.15,
wall 5.306149 s, aggregate child CPU 5.183658 s, child high-water RSS 309149696 bytes.
One attempt/concurrency 1, 120-second caps, 4 MB file/output cap, 140 passed,
zero Python network attempts. Output digest
`a5c35294e5d9640e67041928c17987b88c27c1d80335d28c006fa72de1adc4d9`.
RSS is the OS child high-water observation, not total process-tree or idle RAM.
Setup/startup/idle, TTFT, real-model requests/tokens/utility remain unmeasured.

Native launcher probe was attempted without invoking an installer and returned
BLOCKED. No operator pin manifest was fabricated. No live model/source/peer send,
paid request, cloud operation, personal data, publication, migration or backup
deletion was performed. Zero-attempt claims apply only to the named Python-audit
suites; they do not prove native subprocess egress, provider billing or deployment
privacy. Existing broad offline command is not itself a native fence.

`offline_development`: E0/E1 local synthetic development candidate only; machine
preflight conservatively BLOCKED until operator-pinned receipts are supplied;
release **NO_GO**, independent acceptance pending. `local_developer_preview`:
**BLOCKED / NO_GO** on origin/licensing, native installation and signed server,
real-model/resources and review. `hosted_opt_in`: **BLOCKED / NO_GO**, including
account/issuer/privacy/cost authority. `cloud_operator`: **BLOCKED / NO_GO**, also
native restore/erasure/deployed controls. E5 utility NOT_RUN. No blanket readiness.

The [operator guide](release-operator-guide.md) supplies exact no-example install
and evidence commands, provisional version range, default-off matrix and finite
remediation queue. Rollback stops this disposable tool and removes only its own
temporary directories; keep authority/journals and original keys. No runtime flag,
public endpoint, database or historical evidence is replaced.

## Independent reviewer handoff

Review the **exact delivery commit/tree**, not this receipt's claimed conclusions.
Read AGENTS/router, this report, hardening decision and owning scripts/tests. No
new subagent/session or review was started by the implementer. Suggested prompt:

> Independently review the exact delivered operational-release commit against
> the original HXE-5 handoff, hardened slice and A01–A13. Attack trust provenance,
> schema/type/downgrade/waiver handling, wheel/import/startup-hook boundaries,
> native-fence/measurement claims, source identity, default-off behavior and
> historical evidence preservation. Reproduce only authorized offline commands.
> Treat environment failures and unsupported native claims as BLOCKED. Do not
> enable live accounts, spend, private data, cloud or publication. Output one
> self-contained Luna High/XHigh review-fix/final-verification handoff with exact
> target SHA/tree, prioritized valid findings, reproduction and remaining owners.
> Do not certify implementation-author evidence as independent acceptance.

Run C1–C5, C7, C9–C13 and C15 using the prepared environment. C6/C8/native install
need an approved host. C14 needs the public SDK and Checklist source paths for
collection (documented below). Historical exact-commit gate additionally needs
externally reviewed SHA and a genuinely clean checkout; user untracked plans and
prepared ignored artifact environments must not be hidden or deleted to obtain
success. Never self-fill `RELEASE_EVIDENCE_EXPECTED_COMMIT` as independent approval.
After review, the single Luna session owns valid fixes and final verification;
no follow-up independent review is claimed or scheduled here.

## Broad-suite disposition and compatibility fixture correction

Initial C14 could not collect the SDK HTTP test without SDK/Checklist imports
(Make 2). Prepared collection used the following exact environment prefix:

```sh
PATH="$PWD/backend/.venv/bin:$PATH" \
PYTHONPATH="$PWD/sdk/python/src:$PWD/examples/project-checklist/client/src:$PWD/examples/project-checklist/host/src" \
LITELLM_LOCAL_MODEL_COST_MAP=True make backend-test-offline
```

Observed Make 2 / pytest 1: **2408 passed, 12 failed, 92 errors, one skipped,
155 deselected** in 209.80 seconds. Eleven failed cases and 92 setup errors were
socket-bind EPERM. One auth test was stale after the entry portability remediation:
its settings override exposed a `**updates` query parameter to FastAPI, its mock
principal lacked upstream authentication time, requests omitted expected_revision,
and error repositories lacked the canonical CAS keyword. This session corrected
only that fixture/request data/signature and retained all status, auth, conflict
and redaction assertions, adding explicit CAS assertions. The production route
and evaluator source remain unchanged. The corrected auth file passed **20 tests**
with zero forbidden Python network attempts via:

```sh
backend/.venv/bin/python backend/scripts/offline_test_runner.py -q backend/tests/test_auth.py
```

The original full target remains **not passed**; the socket cases need a capable
host. A separately scoped Python-fenced rerun excludes the already marked
unavailable loopback/integration/cloud cases, preserving every release gate:

```sh
PYTHONPATH="$PWD/sdk/python/src:$PWD/examples/project-checklist/client/src:$PWD/examples/project-checklist/host/src" \
LITELLM_LOCAL_MODEL_COST_MAP=True backend/.venv/bin/python backend/scripts/offline_test_runner.py \
  -q -m 'not persistence_integration and not cloud_smoke and not loopback_http' \
  --ignore=backend/tests/test_gemini_manual.py --ignore=backend/tests/test_context_manual.py backend/tests
```

Its result is recorded below; excluded/skipped cases never count as PASS.

Final scoped rerun: **exit 0, 2404 passed, 264 deselected, four warnings, no skips**
in 227.86 seconds; **OFFLINE_RUNNER_BLOCKED_NETWORK_ATTEMPTS=0**. This is an E1
Python-fenced supported-scope pass, not a successful rerun of the original C14
full target or any native/cloud/provider gate. Final release tooling: **18 tests
passed**, plus two naming checker tests; Ruff and diff/link checks passed.

Final diff self-review checked all added code and changed contracts, bounded
process cleanup, trust/source binding, redaction, absence of runtime/provider/
authority/default changes, frozen identity preservation and documentation limits.
The only existing test patch repairs the auth fixture described above.

Author log digests (local ephemeral logs, not independent receipts):

- `release-focused.log`: `2d7ad34f47efbfd6b109a8e631c693800be01440e180102a94bb572b5130bf8e`
- `release-focused-retry.log`: `1cdaa1abf939f30f647a9853c75ae0663e35315993097f3604df1c34210adacd`
- `release-regression.log`: `be5b63e1d03dc276ff11c392f964664260174e1651856442da8f699b248dee99`
- `release-offline.log`: `fb57ad86c0923104cbd4b9de9fca057ec955ccbe50d84b616ed6e9bcb3bfc037`
- `release-offline-prepared.log`: `1b5562483067dfa350bcaa06305e8e7f049bfb9274b1ab3f73a8a422e32a97e8`
- `release-offline-fenced.log`: `e71fe1dd2f2e34f2c7b61f099c8c51d0ab220c225159b0e2415c4349e5fc41dc`
- `release-last-check.log`: `ca6cb4855b4c469ac5f63dee4053b1bc9087626fb7c408b902bfb51832c0c404`

# Release profiles and offline operator guide

This tooling produces evidence candidates, never release authority. Consumer
contract **v1.2.0** and SDK **0.1.0** remain provisional. No artifact is published
or stable version tagged. Start with the [capability inventory](README.md) and
[gate registry](../platform-independence/pi-cross-phase-gate-registry.md).

The single versioned `release-profile-v1` manifest comes from
`backend/scripts/release_profiles.py:template`. Its code-owned inventory fixes
mandatory gates, owners, evidence tiers, topology and defaults. It projects
existing evidence; it creates no grant, provider attempt, memory or workflow
ledger. Missing observations stay BLOCKED. E0 is static, E1 synthetic, E2 native
install/local task, E3 live account, E4 deployment/recovery and E5 longitudinal
utility. Higher tiers do not automatically substitute for a differently scoped
operation or source. NOT_APPLICABLE is allowed only outside the selected profile.

| Profile | Mandatory evidence | Current decision |
| --- | --- | --- |
| `offline_development` | Inventory, validator, immutable history, public protocol, canonical source and attempt safety | Local synthetic development only; candidate evidence available, independent acceptance pending, release NO_GO |
| `local_developer_preview` | Above plus repeat builds, operator-pinned origin, native source-free install, signed installed identity, real-task/resources and independent review | BLOCKED; release NO_GO |
| `hosted_opt_in` | All local gates plus operation/account-specific issuer, rights, privacy, exact counters and cost proof | BLOCKED; release NO_GO |
| `cloud_operator` | Above plus deployed identity, storage/backup, native mixed-age restore, anti-rollback and physical erasure | BLOCKED; release NO_GO |

These aggregate gates compose every inherited registry requirement. They do not
close any detailed registry row. A name or digest in a review reference does not
authenticate a reviewer. Even completely pinned candidate receipts produce
`release=NO_GO`, `independent_acceptance=PENDING`. The independent reviewer and
operator must make the separate release decision. There is no promotion switch.

## Credential-free quickstart

Use the existing prepared Python/build environment; no command below bootstraps
network dependencies. Do not create `.env` files for these synthetic checks.

```sh
export PATH="$PWD/backend/.venv/bin:$PATH"
export UV_OFFLINE=1
export UV_CACHE_DIR=/tmp/pas-release-uv-cache
make release-profile-check naming-policy-check backend-lint sdk-check
make release-build-report
make release-preflight
make release-canary-check
```

Preflight and canary deliberately exit **3** for missing readiness evidence;
measurement regressions exit **1**; unit checks exit 0 on pass. Run the underlying Python command directly when
saving JSON, because Make echoes its recipe:

```sh
backend/.venv/bin/python -E -s backend/scripts/release_preflight.py \
  --profile local_developer_preview > /tmp/release-preflight.json
backend/.venv/bin/python -E -s backend/scripts/release_preflight.py \
  --measure-synthetic > /tmp/release-measurement.json
backend/.venv/bin/python -E -s backend/scripts/release_artifacts.py build \
  --uv "$(command -v uv)" > /tmp/release-build.json
```

Preflight contacts no provider, source or peer and starts no service. Measurement
explicitly runs four inspected canonical fake suites under the Python socket
audit hook, one attempt, 120-second wall/CPU caps and 4 MB output/file caps. Linux
also applies a 4 GB per-process address-space limit; this macOS host cannot apply
that limit safely to its Python runtime and reports it unavailable. Signal
cancellation sends TERM, then attempts KILL after a short grace period, only to
the invocation's owned process group. If the host denies group signaling, the
report marks cleanup BLOCKED and only the owned leader receives a direct-kill
fallback. The portable runner cannot enforce aggregate process-tree memory or
process count, or prevent descendants from creating a new session; its E2 result is
therefore always BLOCKED. Unsupported per-process limits fail closed. This Python
socket audit is synthetic evidence, not a native network fence or complete
resource sandbox. Parsed test counts and network-attempt lines are untrusted
display hints, not authenticated results. RSS is a supervisor-cumulative
terminated-child high-water mark and per-invocation peak RSS is null. Setup,
startup/idle CPU/RAM, TTFT and token/request counts remain null when unmeasured.

## Trust and machine-readable evidence

The validator accepts bounded JSON, rejects duplicate and unknown keys, pins
exact commit/tree, profile, scope, toolchain and receipt digest, and requires all
gate rows in fixed order. A PASS/FAIL receipt includes schema `release-receipt-v1`,
source `{commit, tree}`, profile, gate, scope, toolchain, nonempty argv and
prerequisites, fence, integer exit, output artifact digest map and provenance
`AUTHOR_REPORTED`. The validator binds receipt bytes to an external receipt
digest. Values in its `artifacts` map are author-reported digest strings; the
validator does not fetch or hash those output files, so they do not prove artifact
identity or origin. Operators must independently inspect and pin output bytes
before treating them as artifact evidence. PASS needs exit 0; blocked/unrun cases
have no observations.
Source scope includes issuer, actor, application, workspace, purpose and operation.
Use only content-free identifiers. No raw request, source passage, credential,
endpoint or hidden reasoning belongs in diagnostics or evidence.

An independent operator may supply a separately controlled trust file:

```json
{"schema":"release-trust-v1","receipts":{"validator":{"file":"validator.json","sha256":"<externally verified receipt SHA256>"}},"review_sha256":null}
```

Receipt filenames are local basenames adjacent to that file. Pins are never read
from the candidate itself. The operator must authenticate their origin out of
band; a locally invented pin is not independent evidence. A review reference can
bind a different reviewer label, exact source/profile, digest of canonical JSON
with `review:null`, and externally pinned review-artifact digest. This still
reports `PINNED_UNAUTHENTICATED`; no review case can be passed by a command receipt.

```sh
backend/.venv/bin/python -E -s backend/scripts/release_profiles.py /tmp/profile.json \
  --expected-commit "$REVIEWED_COMMIT" --expected-tree "$REVIEWED_TREE" \
  --trust /operator/controlled/trust.json
```

Exit 0 means candidate mandatory evidence passed, 2 means invalid/untrusted input,
3 means valid but incomplete/failed candidate. No exit means release approval.

## Builds, attribution and no-example install

`release-build-report` builds the **committed SDK** twice in separate disposable
source directories with fixed SOURCE_DATE_EPOCH, offline uv and prepared pinned
hatchling/editables. It excludes example apps and untracked files. The report
records source SHA/tree, input/output hashes and the prepared distribution/license
inventory, including Requires-Dist for transitive audit. This is a superset of
build tools, not an authenticated dependency closure/SBOM or legal certification.
Unknown metadata needs owner review. Backend/optional/frontend reproducibility
is not established by the SDK report. First-party SDK license is Apache-2.0;
preserve its packaged LICENSE and inspect transitive notices before distribution.
Reproducible outputs cannot prove input origin or safe third-party code.

The source-free consumer is unrelated to the examples and imports only the
installed public SDK. It tests scope headers, typed workspace denial, unsupported
versions, interrupted SSE, original-key status and explicit replay through
synthetic public HTTP frames. It never issues a token or claims real identity.
Actual signed HTTP authority is tested separately by the canonical server suite;
installed signed server acceptance remains an independent prerequisite.

For native clean installation, an operator must independently approve the local
uv executable, Python, SDK wheel and its origin. Prepare a separate pin file:

```json
{"schema":"sdk-origin-v1","source":{"commit":"<externally verified commit>","tree":"<externally verified tree>"},"origin":"operator-reviewed immutable origin reference","filename":"personal_ai_sdk-0.1.0-py3-none-any.whl","sha256":"<independently verified wheel SHA256>","name":"personal-ai-sdk","version":"0.1.0","tools":{"uv_sha256":"<externally verified uv SHA256>","python_sha256":"<externally verified interpreter SHA256>"}}
```

```sh
backend/.venv/bin/python -E -s backend/scripts/release_artifacts.py install \
  --uv /operator/approved/uv --wheel /operator/wheelhouse/personal_ai_sdk-0.1.0-py3-none-any.whl \
  --pins /operator/controlled/sdk-origin.json \
  --expected-commit "$REVIEWED_COMMIT" --expected-tree "$REVIEWED_TREE" \
  --tool-digests /operator/controlled/release-tool-digests.json
```

The expected source identity and release-tool digest map must come from an
independently controlled source review. Install refuses dirty checkouts, source
mismatches or changed release scripts/probe bytes before native fencing or
installer invocation. The tool map covers `release_artifacts.py`,
`release_preflight.py`, `release_process.py`, `release_profiles.py` and
`source_free_sdk_probe.py`. A local build report remains a reproducibility
observation and does not establish authenticated tool or dependency origin.

The externally controlled tool-digest file is a closed filename-to-SHA256 map:

```json
{"release_artifacts.py":"<sha256>","release_preflight.py":"<sha256>","release_process.py":"<sha256>","release_profiles.py":"<sha256>","source_free_sdk_probe.py":"<sha256>"}
```

This path inspects inert wheel bytes before installation, rejects unexpected
modules, dependencies, `.pth`, startup hooks, entrypoints, links and metadata,
then requires the existing native child TCP/UDP IPv4/IPv6 denial probe. Installation
is no-index/no-deps in an unrelated pip-free venv with a credential/proxy-free
environment. Installed files and import origins are checked. There is no editable,
source-path or network fallback. Only dependency-free SDK 0.1.0 is supported by
this installer. It cannot accept a backend wheelhouse with unreviewed dependencies.
Exit 3 means BLOCKED; no degraded-success option exists.

## Support, upgrades, diagnostics and rollback

Python package support is 3.11+; this run observes macOS arm64/Python 3.11 only.
The evidence schema admits Python 3.11–3.14 and pinned hatchling 1.27.0; admitting
a new toolchain requires a reviewed schema/tooling change.
Native acceptance is implemented for macOS sandbox-exec only and is BLOCKED if
its effective probe fails. Other OSes require separately reviewed fences.
The SDK accepts operator-configured v1.2+ within major 1; this is configuration
compatibility, not remote version discovery or a grant. Only v1.2.0 is exercised
here. Breaking SDK/HTTP changes require explicit version negotiation, migration
instructions and cross-version error/replay tests; preserve original operation
keys and journals on upgrade or rollback. Never infer server compatibility from
constructor success. No stable support window is promised for this provisional
SDK. Read the [SDK guide](../../sdk/python/README.md).

All sensitive capabilities remain default-off: retrieval/source integrations,
MCP, local models, workflow, memory control/portability, hosted inference, cloud,
peer disclosure and mutating effects. Profiles describe permitted evidence scope,
not configuration activation. Existing authorization, context assembler, physical
attempt accounting, consent, revision checks, retries and reconciliation are
unchanged. No extra model calls or fallback paths are installed.

Rollback means stop the disposable process and discard only the temp directory
created by that invocation; TemporaryDirectory owns cleanup. No store, backup,
journal, migration or user package is deleted. Retain original keys for uncertain
operations and use the existing status endpoint rather than resend. Never
rollback revocation/attempt authority from an old backup. This tooling does not
deploy, migrate, publish, tag or enable flags. Optional peers stay off: downstream
retention/deletion and provider cost cannot be controlled after disclosure.

Finite remediation queue: (1) independent exact-commit review, (2) authenticated
build-tool/wheelhouse origins and transitive license review, (3) effective native
source-free SDK plus signed installed server proof, (4) pinned real-model/fence/
store task and measured idle/setup/TTFT resources, (5) separately authorized
hosted/account or cloud/restore/erasure evidence. E3–E5 and production personal
data remain NO_GO. No peer work is needed to close the core preview gates.


## Synthetic reasoning preview

The [loopback operator guide](../reasoning-engine/synthetic-preview.md)
covers the separate development process, one-command admission disablement
and original-epoch reconciliation. Its [evidence and blockers](../current-state.md)
are scoped to fixture HTTP and the internal native workflow. All deployed
release and adaptive promotion gates keep their existing dispositions.

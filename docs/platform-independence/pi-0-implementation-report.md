# PI-0 implementation report

Date: **2026-10-30**, America/Los_Angeles. Bounded PI-0 implemented locally;
**independent acceptance pending**. PI-1..8 are not delivered. No production
behavior, identity, provider selection, default flags, memory semantics or data
contracts changed. No commit or push was made.

## Source and working-tree identity

Starting and ending HEAD: **`8571a8af33969f249614c2652a7d29c0c686f2d8`**, branch
`main` (`Address MEM-2 independent review findings`). The handoff's reviewed source
matches exactly, so there was no intervening runtime delta to reconcile.
The work remains an uncommitted patch, with new files untracked. HEAD alone does
not identify the PI-0 deliverable.

[Source manifest](pi-0-source-manifest.json) binds 13 baseline files (including the
unchanged supplied handoff) and the original four PI documents. Its SHA-256 is
`53ed9b5d2c7ca257b0a3e914ad16b04b1388b2445356dd950769173f9679867e`.
The manifest excludes itself and this report to avoid circular identity. Its
per-file hashes identify the diagnostic and documentary patch; this report records
commands/results. Future edits require regenerating identity and re-verifying
relevant checks, not reusing these results for changed source.

All **694 tracked files** under `backend/src`, `frontend`, `experiments` and
`backend/tests` match HEAD byte-for-byte (tracked diff verified; new guard test is
separately hashed). Their sorted path/content SHA-256 is
`7db9d2bc6440658bc296f988a2abeaa4d10668319dbb4fb3246906236d1e7310`.
The manifest records the digest algorithm and Git tree objects. This includes
memory/planner source and historical evaluation fixtures/locks: none was modified.
No migrations, ledger, receipt, tombstone, mutation state machine or frontend file
changed. No tests/evaluators were weakened to accept a new source identity.

Preflight `git status --short` had **no tracked modifications**, and these
pre-existing untracked user files:

```text
docs/memory/plans/mem-1-detailed-implementation-plan.md
docs/memory/plans/mem-2-detailed-implementation-plan.md
docs/personal-ai-chapter-2/litellm-routing-review-handoff-2026-10-08.md
docs/phase-11-independent-review-2026-10-07.md
docs/phase-12-independent-review-2026-10-07.md
docs/phase-13-independent-review-2026-10-07.md
docs/phase-14-independent-review-2026-10-07.md
docs/phase-15-independent-review-2026-10-07.md
docs/phase-17r-independent-review-2026-10-08.md
docs/platform-independence/
```

The last directory contained `README.md`, `platform-independence-roadmap.md`,
`pi-0-review.md`, `pi-0-sol-codex-handoff.md`. Those four were copied to a temporary
baseline before edits. The index's stale “outputs not included” status was updated;
the roadmap/review were preserved and received labeled implementer reconciliation
addenda. The handoff is byte-identical. The other nine user documents were untouched.
No reset, checkout, staging, other repository edit, subagent or external review
was used. Normal `git diff --stat` omits the untracked PI documents and scripts;
use the file list and manifest below when reviewing this patch.

Preflight commands: `git status --short`, `git rev-parse HEAD`,
`git branch --show-current`, `git log -8 --oneline`. Last eight commits:
`8571a8a`, `c0add2b`, `7c8f267`, `2df112b`, `293a591`, `169c697`, `987bba5`, `ad7c500`.

## Deliverable files

| Path (repository-relative) | Change |
| --- | --- |
| `docs/README.md` | Add one Platform Independence task route |
| `docs/current-state.md` | Add one concise PI/freeze status section; retain historical evidence |
| `docs/platform-independence/README.md` | Reconcile supplied index and link actual baseline outputs and later-phase contracts |
| `docs/platform-independence/platform-independence-roadmap.md` | Preserve supplied PI-0..8 charter/A01..A22; append source corrections, entry gates and rollback precision |
| `docs/platform-independence/pi-0-review.md` | Label supplied pre-implementation assessment; append F01–F12 source dispositions, uncertainties and gates |
| `docs/platform-independence/pi-0-architecture-decisions.md` | New ownership, reuse, authority, committed/provisional boundaries, threat and rollback ADR |
| `docs/platform-independence/pi-0-dependency-inventory.md` | New reproduction/scope, 20 static edges, dynamic/default composition, all 74 default-false settings and frontend gates |
| `docs/platform-independence/pi-0-dependency-inventory.json` | New schema-1 sorted inventory, 56 evidence-anchored records |
| `docs/platform-independence/pi-0-import-waivers.json` | New exact 20-edge implementation-reviewed PI-1 debt baseline; independent-pending |
| `docs/platform-independence/pi-0-exit-contract.md` | New later-phase physical-absence, unrelated consumer, identity/privacy/provider/replay proof obligations |
| `docs/platform-independence/pi-0-source-manifest.json` | New baseline hashes and frozen tracked-source identity |
| `docs/platform-independence/pi-0-implementation-report.md` | This implementation evidence and reproduction instructions |
| `backend/scripts/platform_dependency_inventory.py` | New stdlib-only read-only AST diagnostic/guard; no app import, provider call or mutation |
| `backend/tests/test_platform_dependency_inventory.py` | Eight new hermetic guard tests, also runnable via stdlib unittest |

These are **14 changed/created files**, plus the unchanged supplied handoff.
The only code additions are the diagnostic and its tests. Existing pytest CI
collects the test file; no workflow, Makefile, dependency or production change
was necessary.

## Findings and decisions

- Default application registration, installed context entry points, source-tree
  fallback, routes, lifespan and federation/task declarations remain example-coupled.
  The guard tracks 20 exact static violations with rationale, PI-1 phase and explicit
  implementation-review status. It rejects new edges and stale/invalid waivers;
  manual dynamic composition is recorded separately, not automatically waived.
- Ordinary generation/count/summary/memory factories remain Gemini-bound despite
  existing neutral interfaces and three generation adapters. PI-3 must address
  operation composition and cost without a second gateway or vector-space rewrite.
- Correction to the broad initial sharing gap: a four-field global-profile provider
  and per-destination sharing already exist. Reuse that boundary; arbitrary private
  memory sharing remains unimplemented and must not bypass scope/source checks.
- Freeze after MEM-2 is binding. Formats, defaults and semantics are unchanged;
  no MEM-3+ work, tool registration, production host or memory promotion occurred.
  Optional packaging, public API details and expanded sharing remain provisional.

## Executed checks

Existing Python environment: `backend/.venv`, Python **3.11.15**. No dependency
installation. No `.env` contents, API keys, local account data or credentials were
read. `backend/.env` was absent; the test runner asserts absence. A clean environment
supplies only synthetic model names and test controls. Tests use existing fake
providers/repositories and the existing empty startup mutation inventory fixture;
no live database operations were authorized or exercised.

| Command/check | Observed result |
| --- | --- |
| `PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint` | Final **passed**, all checks passed. Initial attempt found `PLW1510` in the new test; added explicit `check=False`, then reran successfully. |
| `env -i PATH="$PWD/backend/.venv/bin:/usr/bin:/bin" make backend-lint` | **Passed**; macOS `confstr` temp-dir warnings only. |
| `backend/.venv/bin/python -m ruff format backend/scripts/platform_dependency_inventory.py backend/tests/test_platform_dependency_inventory.py` | Formatted only the two new code files; final lint and stdlib tests rerun. |
| `backend/.venv/bin/python backend/scripts/platform_dependency_inventory.py --help` | **Passed**, CLI usage available. |
| `backend/.venv/bin/python backend/scripts/platform_dependency_inventory.py` | **Passed**, deterministic schema-1 JSON, 20 sorted static edges; repeated output compared byte-for-byte. |
| `backend/.venv/bin/python backend/scripts/platform_dependency_inventory.py --check` | **Passed**, 20 edges, zero issues, 20 exact waivers. |
| `backend/.venv/bin/python -m unittest discover -s backend/tests -p test_platform_dependency_inventory.py -v` | **8 passed**, final diagnostic source; synthetic forbidden edge exits 1, tracked legacy debt passes. |
| Focused pytest command with Python network fence, reproduced below | **102 passed**, **3 warnings**, 37.09 s; **0 blocked network attempts** after deliberate fence self-test. Six requested files supply 94 tests; new guard supplies eight. |
| First isolated focused attempt, plugin autoload disabled without explicit AnyIO | **99 passed, 3 failed**, six warnings; async tests could not execute because their plugin was disabled. Zero network attempts. Fixed runner to load installed `anyio.pytest_plugin` explicitly; no product/test assertions changed. |
| `/usr/bin/sandbox-exec -p '(version 1) (allow default) (deny network*)' backend/.venv/bin/python -c 'print("network-denied process started")'` | **Unavailable**, exit 71, `sandbox_apply: Operation not permitted`; process did not start. Used a Python audit fence instead; no OS-level egress-isolation claim. |
| Local Markdown links, JSON schema/path/line anchors and whitespace validation | **Passed**: 101 local links, 56 inventory records with valid schema/path/line anchors, all JSON parsed; nine new files and changes against four original PI documents passed whitespace checks. Initial link probe found the not-yet-written report; final rerun passed. |
| `git diff --exit-code HEAD -- backend/src frontend experiments backend/tests` | **Passed**, no tracked runtime/fixture changes. The new untracked guard test is separately inventoried. |
| `git status --short`, `git diff --check`, untracked-file whitespace checks | **Passed** on final patch; no unrelated user files altered. |

Dependency warnings concern Google library Python-version support (two) and
Starlette/httpx test-client deprecation (one). They are not provider acceptance.
The successful focused run tested unchanged production runtime; subsequent
formatting/path-expression simplification was limited to the diagnostic, whose
final eight tests and lint were rerun. No need to rerun the costly unchanged
runtime cases for documentary edits.

### Reproduce the focused Python network fence

The temporary harness was outside the repository. Exact creation and invocation
are included so the result does not depend on retained `/private/tmp` files.
It blocks Python IPv4/IPv6 socket creation, DNS and connect/send audit events,
including Python subprocesses inheriting `PYTHONPATH`. It does **not** establish
OS-wide or arbitrary native-extension egress isolation. The selected tests were
inspected for fake injection; no network attempt was observed. Do not use this
result to authorize the full offline suite or live operations.

From repository root, create:

```sh
mkdir -p /private/tmp/pi0-isolation
cat > /private/tmp/pi0-isolation/sitecustomize.py <<'PY'
import os
import sys

def network_fence(event, args):
    denied = event in {'socket.connect', 'socket.getaddrinfo', 'socket.sendto', 'socket.sendmsg'}
    if event == 'socket.__new__' and len(args) > 1:
        denied = args[1] in (2, 10)
    if denied:
        with open('/private/tmp/pi0-isolation/blocked-attempts.log', 'a') as stream:
            stream.write(event + '\n')
        raise PermissionError('PI-0 network fence: network operation forbidden')

sys.addaudithook(network_fence)
os.environ['PI0_NETWORK_FENCE_ACTIVE'] = '1'
PY
cat > /private/tmp/pi0-isolation/run_focused.py <<'PY'
import os
from pathlib import Path
import sys
assert os.environ.get('PI0_NETWORK_FENCE_ACTIVE') == '1'
assert not Path('.env').exists(), 'Do not load a local environment file'
import socket
try:
    socket.socket(socket.AF_INET, socket.SOCK_STREAM)
except PermissionError:
    pass
else:
    raise RuntimeError('network fence inactive')
log = Path('/private/tmp/pi0-isolation/blocked-attempts.log')
assert log.read_text().splitlines() == ['socket.__new__']
log.unlink()
import pytest
result = pytest.main(['-q', '-p', 'anyio.pytest_plugin',
    'tests/test_applications.py',
    'tests/test_application_scope.py',
    'tests/test_context_runtime_composition.py',
    'tests/test_phase36_integrated.py',
    'tests/test_memory_control.py',
    'tests/test_memory_control_api.py',
    'tests/test_platform_dependency_inventory.py',
])
count = len(log.read_text().splitlines()) if log.exists() else 0
print(f'PI0_BLOCKED_NETWORK_ATTEMPTS={count}')
sys.exit(3 if count else result)
PY
```

Then from `backend/`:

```sh
env -i PATH="$PWD/.venv/bin:/usr/bin:/bin" \
  PYTHONPATH=/private/tmp/pi0-isolation PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 \
  AI_PROVIDER=gemini AI_MODEL=pi0-fixture \
  .venv/bin/python /private/tmp/pi0-isolation/run_focused.py
```

Stop if any unexpected attempted network event occurs; do not retry with network
allowed. The event log intentionally contains no addresses/tokens. Delete a stale
blocked-attempt log only after investigating it, not to conceal an earlier attempt.

## Unrun gates, review and deviations

The full `make backend-test-offline` was **not run** because the inherited MEM-2
handoff reports an unauthorized Google request. PI-0 has not established that all
provider paths in that suite are stubbed. No native PostgreSQL, DynamoDB/emulator,
provider/live-model, cloud identity/IAM, deployment, cost/free-tier, browser/device,
backup/physical deletion or external consumer acceptance was run. Frontend checks
were unnecessary: no frontend files changed. The full Phase 36 matrix, expensive
evaluations and planner replay were not rerun; their bytes and existing gate status
were preserved. No synthetic pass is presented as external proof.

Residual blockers: independent PI-0 source/inventory review; PI-1 physical-absence
boot and retained-task compatibility; PI-2 independently installed public consumer;
PI-3 ancillary provider operations and cost; PI-4 consent/source/derived reuse;
all inherited independent MEM-0/1/2, Phase 36, issuer/lease, source-fence capacity,
permanent receipt storage/recovery, physical provider-send and cloud deletion gates.
The prior reports remain the owners of those limitations.

A separate **Sol High review** should challenge this baseline, missing dynamic
edges, classification/waiver scope, profile correction, plugin trust, startup
reconciliation and reproduction before PI-1 implementation. This session supplies
no independent verdict and does not start or wait for that review.

Deviations: none in product/runtime scope. The supplied roadmap/review existed and
were reconciled rather than recreated; this was anticipated by the handoff. The
optional guard was feasible without dependencies or CI edits. OS sandboxing was
unavailable, so focused checks used the documented Python fence with its narrower
coverage. Initial runner/lint failures are preserved above. Rollback removes only
PI diagnostics/docs/status pointers; no durable runtime rollback is needed.

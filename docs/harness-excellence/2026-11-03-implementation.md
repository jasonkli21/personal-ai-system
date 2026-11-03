# HXE-0 implementation receipt · 2026-11-03

**PARTIAL E1.** Base `b61d69890255ca3de736e7236581cee559358f32`. The
candidate is the single commit containing this receipt. This session hardened
the plan, implemented and self-reviewed it without delegation. The five
pre-existing untracked planning inputs were preserved outside the commit.

## Delivered and reviewed

- [Hardened plan](2026-11-03-plan-hardening.md), [capability inventory](README.md)
  and [ownership ADR](../decisions/0023-external-consumer-and-execution-authority.md)
  identify the provisional external boundary, current-state and inherited gates.
- [Python SDK](../../sdk/python/README.md) implements typed consumer operations,
  bounded SSE and original-key status reconciliation. It derives its parser
  from Reading Logbook, whose package bytes were preserved. The published v1.2.0
  OpenAPI is byte-identical. Version compatibility and retrieval configuration
  are local operator inputs. There is no added discovery route or schema change.
- [Project Checklist](../../examples/project-checklist/README.md) owns its
  SQLite records and turn journal. Its separate opt-in host uses
  `personal_ai.extensions.v1`. The shared PI-2 fixture verifies signed test
  identity through real middleware and the canonical continuation service.
  ASGI transport replaces real loopback for this session. The test includes
  authority spoofing, no implicit source access, changed-body conflict and
  lost completion followed by original-key replay with one fake send per intent.
- The neutral PI-3 alternate fake and P19 admission paths, PI-5 deterministic
  read-only source/tool ports and MEM-1/2 controls supply the other three
  canaries. The Checklist host exposes history only. It reports memory and
  retrieval unavailable in preflight. No new provider factory, source issuer,
  memory grant or lifecycle engine was introduced.
- Build and check entrypoints are in the [Makefile](../../Makefile). The installed
  smoke runs the CLI in clean client-only environments. It checks preflight,
  local records and absence of server and reference packages. Installed signed
  server/client exchange, trusted dependency origins and native egress evidence
  are pending.

## PI-6 transition

The baseline v27 test failed with expected `d099f766…a679` and computed
`3199e902…83a6`. Reconstructing the digest from Git blobs at the HXE-0 base
and substituting only the previous `backend/pyproject.toml` blob recovered
the exact v27 digest. The Apache-2.0 metadata stays in place.

[Planning v28](../../backend/src/personal_ai/evaluation/fixtures/context/planning-baseline-v28.json)
binds current source and the base/current-or-direct-child revision under the
original evaluator and runtime guards. Its source digest is
`b0713dabcb3ddde272228e7edae00bd6d379506378ecb9a56ef684d48e25cd7a`.
The [PI-6 source generation 2 manifest](../../backend/src/personal_ai/evaluation/fixtures/pi6/manifest-v2-source-2.json)
binds the changed loader and core tree including v28. The generated protocol
manifest stays outside the planning digest to avoid a circular dependency.
Tests pin historical v26, v27 and v2 manifest bytes and assert equality of
the unchanged cases, scoring, driver and optional consumer hashes. Historical
scores, thresholds, reports and non-promotion are preserved.

## Verification

Managed macOS 27.0.1 arm64, CPython 3.11.15, uv 0.11.13, prepared local build
environment. Build/check invocations used a cleared environment with the
virtualenv and system tools on PATH, temporary uv cache and `UV_OFFLINE=1`.
The HXE-0 test target uses the existing deny-network Python audit fence.
The clean client install uses no index and isolated interpreters.

| Command or probe | Result | Evidence |
| --- | --- | --- |
| `git diff --check`, `make backend-lint`, `backend/.venv/bin/ruff check backend sdk/python examples/project-checklist` | PASS | E0 |
| `backend/.venv/bin/python backend/scripts/pi2_contract.py --check` via `make hxe0-check` | PASS. Generated subset byte-identical | E0 |
| `make hxe0-check` | PASS. 360 passed, 12 loopback tests deselected, 15.94 s, zero attempted fenced operations. Includes OpenAPI, SDK, signed ASGI, Reading Logbook unit regression, PI-6 identity/structural cases, strict-free and P19, source and memory negatives | E1 |
| Exact pre-license identity reconstruction and direct `planning.evaluate()` under v28 | PASS. Recovered original v27 digest and evaluated 30 synthetic rows under strict source and runtime checks | E0/E1 |
| `UV_OFFLINE=1 make pi2-build hxe0-build` | PASS. Wheels and sdists for core, reference apps, Reading Logbook and HXE-0 packages | E2 build |
| `UV_OFFLINE=1 make hxe0-installed-check` | PASS. Two isolated client-only install and CLI smoke profiles, direct wheels and wheels rebuilt from sdists | E2 client install only |
| Loopback fixture probe through the PI-2 Python launcher | BLOCKED. Managed sandbox returned `EPERM` at `bind(127.0.0.1)`. Initial combined attempt also surfaced a circular digest while assembling the new locks. That defect was fixed and the final strict offline checks passed | Native/installed exchange unmeasured |
| `make pi2-check`, `make pi6-check` | SKIP/BLOCKED. Loopback prerequisite unavailable. Native launcher preflight `sandbox-exec -p '(version 1)(allow default)(deny network*)' /usr/bin/true` returned 71 and `sandbox_apply: Operation not permitted`. No PI-6 measurement of source generation 2 | E2 native unmeasured |
| Live provider/source, deployed identity, native restore/deletion, spend and real utility | SKIP. Outside authorization and before-enablement gates remain open | E3–E5 unmeasured |

## Rollback and handoff

Deselect and uninstall the optional Checklist host and uninstall the client/SDK
to withdraw the preview. Retain the journal for original-key reconciliation.
Revert the single implementation commit to withdraw the source transition.
Reproduce prior locks on their own recorded revisions and runtime profiles.
The change adds no core migrations and authorizes no production enablement.
Independent exact-commit review and native-fenced installed conformance are
pending. Issuer-bound send/revoke atomicity, monotonic original-key and forget
authority after restore, verified deployment identity and account caps remain
before-enablement gates.

The subsequent Luna remediation is documented in the
[2026-11-03 remediation record](2026-11-03-remediation.md). Its local results do
not supersede the external gates above.

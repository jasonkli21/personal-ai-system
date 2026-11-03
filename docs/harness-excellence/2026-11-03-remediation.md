# HXE-0 independent-review remediation · 2026-11-03

This is a local remediation record for the five findings in the Luna handoff.
It does not establish independent acceptance, native installed conformance, or
production readiness. The reviewed base was
`9c90c1d844e9126cb494f286e5f0f80e4be9a6a0`. The exact fix commit and tree are
reported in the session handoff; this receipt is part of that single commit and
cannot contain its own SHA.

## Findings and changes

| Finding | Disposition |
| --- | --- |
| R01 · P1 | The SDK treats `response.completed.message.content` as canonical, independently bounded to 20,000 characters and required to be nonblank. Deltas remain provisional callbacks. Added zero-delta and superseding-final-text tests plus invalid terminal cases. Ordered created events, strict UTF-8/framing, one terminal, normal EOF, no data after terminal, and original-key status/UUID reconciliation remain required. |
| R02 · P1 | The signed Checklist canary imports the host, SDK, and store normally. The HXE-0 target passes with the host installed and collection fails with `ModuleNotFoundError` when the host is absent. No global skip policy was added. |
| R03 · P2 | The current-state introduction now describes the old v27 digest failure as historical and links this record. v26–v28 remain preserved; local remediation verification and open external gates are stated separately. |
| R04 · P2 | Added only the documented `origin_denied` safe error code. The client returns status 403 and that code without reflecting server message/body or request data. |
| R05 · P2 | The signed ASGI test expires the same Checklist user's current workspace membership after authorized create/preview/turn. Detail, preview, and attempted continuation are denied; fake-provider dispatch count remains unchanged and error text contains no token or local record content. This tests new host revalidation only, not atomicity with a physical send. |

## PI-6 identity

The previous v28 current-or-direct-child identity would reject this grandchild.
An additive planning lock v29 binds the unchanged reviewed base as the direct
parent and its exact remediation source digest. An additive PI-6 v2 source
generation 3 manifest binds current protocol/core hashes while retaining the
same cases, scorer, driver, optional consumer hashes, thresholds and
non-promotion. Historical v26–v28 locks, v2/source-2 manifests, and fixture
bytes remain unchanged. The guard itself was not loosened. A direct evaluator
run was repeated after the final commit; it produced 18 rows and passed the
strict source/runtime identity check. This is synthetic local evidence only.

## Local verification

Environment: managed macOS 27.0.1 arm64, CPython 3.11.15, prepared
`backend/.venv`; commands ran from the repository root. `hxe0-check` uses the
repository's deny-network Python audit fence, not a native OS fence.

| Check | Result |
| --- | --- |
| R01 red-before, two new parser cases | Both failed before the parser fix with `invalid_terminal` (2 failed). |
| Missing-host collection probe | Exit 2 with `ModuleNotFoundError: project_checklist_host`; the mandatory canary cannot silently skip. |
| `PLATFORM_PYTHON=backend/.venv/bin/python make hxe0-check` | PASS: consumer contract, 367 passed, 12 loopback tests deselected, 3 warnings, 0 fenced network attempts. Includes parser, signed Checklist, planning identity, PI-6 structure, OpenAPI and selected security/effects suites. |
| Direct `planning.evaluate()` with prepared optional package paths | PASS: 18 rows; v29 exact source digest matched. Repeated against the committed HEAD after commit. |
| Full `backend/tests/test_pi6.py` without filtering loopback | BLOCKED by sandbox `EPERM` at `bind(127.0.0.1)` in native loopback tests. Canonical HXE-0 excludes those 12 tests; this does not count as native PI-6 evidence. |
| Client build/install, native signed exchange, provider/source, cloud, restore/deletion, and real-task utility | Not rerun or not available here. E2 native and E3–E5 remain blocked; no external gate is promoted. |

`git diff --check`, `make backend-lint`, and changed-document link checks passed.
No live accounts, secrets, paid calls, cloud operations, or production actions
were used.

## Final commit receipt

- Commit: the single remediation commit containing this record; exact SHA and
  tree are in the session handoff.
- Production: **NO-GO**. HXE-0 remains a partial E1 development candidate.
- Before enablement: issuer-bound send/revoke atomicity at physical send,
  monotonic original-key/revocation/forget authority across restore, trusted
  dependency origin, native OS egress fence, independently installed signed
  exchange, deployed identity/IAM, provider caps/privacy, physical deletion and
  restore, and longitudinal utility remain unproven.

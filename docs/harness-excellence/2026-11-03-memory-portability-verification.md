# HXE-4 owner memory portability implementation evidence

2026-11-03. Entry `51cfda1c9ad7c610364454e405cbfe5769a8e11e`. The target is the
single commit containing this report. Compare the entry and target with
`git diff --stat <entry> <target>`. This is implementer evidence.

The [design decision](2026-11-03-memory-portability-design.md) defines the
audience and release boundary. The [owner contract](../memory/owner-portability.md)
defines the format, limits, recovery and rollback. No schema migration or
external consumer API change was required. The additive planner v34 lock and
source generation 8 manifest bind the changed implementation while preserving
historical locks, cases, scoring, thresholds and non-promotion.

## Acceptance matrix

| Capability | Disposition | Evidence |
| --- | --- | --- |
| Bounded owner inspection, proposal disposition and forget | Local candidate | Signed middleware fixture, denied external audience, stale authentication, unavailable host and exact-key recovery |
| Explicit profile correction | Local candidate | Owner API/UI and native concurrent CAS; editing advances the existing revision and invalidates old consent |
| Portable v1 explicit profile copy | Local candidate | Canonical digest, no grant material, post-serialization profile/fence recheck and bounded attachment |
| Import preview | Local candidate | Invalid UTF-8/JSON/digest, foreign scope, forged authority metadata, duplicates and stale revision; no storage changes |
| Verified knowledge revision, project export and applied import | Blocked | Current code has no authorized replacement or transfer issuer, deployed source fence or atomic replacement/import lineage |
| Production owner browser flow, distributed release fencing, restore and physical erasure | Before enablement | Real Google recent-auth flow, transport races, mixed-age restore and downstream retention require separate evidence |
| External consented use and utility | Synthetic only | Two separately registered synthetic consumers using the existing consent boundary. No provider, deployed client, or user utility test |

## Synthetic transcript

The matched task asks for preferred units. The deterministic consumer answers
from the packed projection. The allowed record was `preferred_units=metric`,
with `user_asserted` provenance, the canonical standalone source scope and an
exact destination-bound dependency.

| Stage | Recipient | Result | Projection bytes | Local elapsed |
| --- | --- | --- | ---: | ---: |
| No grant | unrelated_reader | No preference available | 0 | 1.59–2.77 ms |
| Granted | unrelated_reader | metric | 99 | 3.63–6.27 ms |
| Same task, separate application | separate_reader | No preference available | 0 | 1.00–2.02 ms |
| Revoked, expired, corrected or membership removed | either | No preference available | 0 | 0.88–2.33 ms |

Reproduce with `cd backend && .venv/bin/python -m pytest -q -s
tests/test_profile_consent.py -k two_consumer_profile_projection_canary`.
Timing measures local assembly and projection handling. The byte count measures
the serialized field payload. Existing tests exercise history and summary reuse,
external stream/replay, detail and provider-admission denial. No additional
authority or sharing surface was added.

## Verification

- E0 covers lint, frontend type checking, naming policy, consumer contract,
  documentation links and patch whitespace.
- E1 covers the focused signed-middleware/control/consent suite and browser
  component/proxy fixtures. The focused memory and consent run passed 61/61.
  The frontend run passed 133/133. The SDK check passed 376 with 12 loopback
  cases deselected and zero blocked network attempts. The consent check passed
  957 with native IPv4, IPv6 and Unix egress denial and zero Python network
  attempts. The memory-control evaluator passed 36/36.
- The broad offline command completed with 2,405 passed, one skipped, 11 failures
  and 92 errors in loopback cases denied by the sandbox. The isolated loopback
  rerun completed with 106 passed, one skipped and two failures. Both reproduced
  on the entry revision. The derived restore case got
  `context_explicit_source_unavailable`. The client timeout case observed the
  expected 409 but zero model requests at its one-request assertion.
- E2 covers disposable local PostgreSQL 17 with pgvector. The final targeted
  profile, control and verified knowledge suites passed 30/30. The initial
  native run found stale migration fixture boundaries after later migrations
  were added. The rerun checks the original version transitions and current
  migration idempotence. The temporary database server was stopped on exit.
- E3 through E5 have no new deployed identity, real provider, cloud restore,
  physical erasure or real-task evidence. Independent acceptance remains pending.

Before enabling, the memory/security owner owns identity, issuer and release
evidence. The storage owner owns restore and erasure. Keep both adapter flags
off when restoring and retain canonical authority and operation receipts.
See the [gate registry](../platform-independence/pi-cross-phase-gate-registry.md).

# Phase 25.2 implementation and verification evidence

Date: 2026-10-10. Review set: `a7294ed55c9ba5f1fcb61077ef17950910b85adb`,
`c243a46f8bffd75085ba07bec2b4be9e3cae5608`,
`2c9db878b5c4f504bd172be9fb966449a5b16ace`, and
`60c261a2df59148049fa3566ab863c1175710f94`. The focused review-fix tests recorded
here ran against source revision `03fa8c4188c6f2d57132fc2d01de059f2d91505f`. The
final commit is a documentation-only closeout amendment that records this tested
source revision.

**Disposition: Phase 25.2 remains incomplete.** The local review fixes below are
implemented and offline-verified, but Phase 15 has no production pre-retrieval
membership/source/revocation authority, and the canonical DynamoDB transaction
suite could not run without an isolated engine. The current `ExternalTurnAuthority`
callback is still a required integration point, not an implementation, and its
post-assembly check cannot satisfy pre-retrieval authorization. Do not compose an
HTTP issuer or begin Phase 25.3 UI/API work on this seam. No provider, account,
browser, cloud, or physical execution was enabled.

## Review fixes implemented

- Continuation intent uses a canonical digest across automatic and external modes.
  A same-key retry resumes the persisted trailing user message after partial
  preparation or repository restart; changed input conflicts; completed automatic
  retries replay. A later new request safely supersedes a failed orphan user turn.
- Completed-result replay rechecks current authority, sensitivity, policy and
  profile state in both normal and lost-CAS-response paths, without requiring the
  original dispatch TTL. Real Phase 15 authority/revocation is still missing.
- Bridge provider error fields pass the local credential-echo guard before IPC.
  Canonical persistence enforces reservation-bound provenance, package/profile,
  connection and source snapshots. External completions use the same eligible
  post-completion hook as automatic turns after the winning CAS.
- Connected model selection is per paired account and separate from the stable P18
  endpoint profile. Packages enforce both canonical character and transport-byte
  output bounds. Manual producer labels are supplied at import; manual reservation
  lifetime is separate from the short connected dispatch proof lifetime.
- External failures use a shared bounded taxonomy and persist safe client-reported
  status/latency observations. Generic HTTP 429 no longer claims ChatGPT-plan
  exhaustion. Explicit endpoint choices use shared fact-based registry admission.
- Durable source snapshots retain a hash of provider reference identity, not raw
  IDs or URIs, so signed URLs and secret-bearing references do not enter message
  reservations or attribution.

No new external-turn store, permission registry, credential path, automatic
ChatGPT routing, or P19 quota path was added. Uncertain physical-send behavior
remains conservative. After proof expiry and one day of retained reconciliation
detail, unresolved sends compact into protected hash-named tombstones. These remain
permanent resend fences and reconcile as `unknown`; new sends can use the bounded
detail table after compaction. The local-store format migrates forward from schema
versions 1 and 2 to version 3.

## Verification

Python 3.11 tests use `backend/.venv`, synthetic fixtures, fake providers, and
in-memory repositories. These checks establish local contracts only.

| Check | Result |
| --- | --- |
| Focused external-turn, bridge transport, local lifecycle, execution-contract, and persistence tests | 177 passed, 2 skipped |
| Full backend pytest suite | 1,312 passed, 78 skipped, 1 failed; the single provider-matrix assertion is described below (the full run began before three final focused regression cases were added) |
| Isolated provider-matrix failure case | Passed (1 test) |
| Ruff | Passed (`.venv/bin/python -m ruff check .`) |
| `git diff --check` | Passed for the review-fix source and documentation |
| DynamoDB external-turn transaction/race/restart tests | 2 skipped; unverified |

The full backend run began before the final three focused regression cases and the
last taxonomy values were added. Its one failure was
`tests/test_provider_matrix.py::test_matrix_uses_generic_profiles_task_contract_and_p21_p19_seams`:
the full suite produced 77 synthetic cases where the fixture expected 80. The
isolated rerun passed. This test's provider profiles do not include ChatGPT-plan;
the failure was not reproduced outside the full suite and remains a suite-level
verification gap. The final focused rerun included the added local-store schema-2
migration case, which landed after collection began for the full run.

The skipped DynamoDB tests require `PERSISTENCE_TEST_DYNAMODB_ENDPOINT`. Docker and
an isolated DynamoDB-compatible engine were unavailable, so transaction/catalog
CAS, concurrent finalize, stale recovery, restart/hydration and the new direct
provenance checks have not been verified against a real engine. Fakes and JSON
hydration do not establish this behavior. The Makefile backend targets also assume
a `python` executable on `PATH`; this host lacks it, so checks were run through
`backend/.venv/bin/python` instead.

## Required gates and remaining acceptance gaps

- Phase 15 must provide one authoritative authorization path that denies before
  context, memory, source, summary, count, or generation reads, and that rechecks
  current relevant grants/dependencies before disclosure and completed replay.
  Negative tests must prove denial occurs before those calls. Do not replace this
  dependency with a permissive Phase-25-only implementation.
- Run the external-turn persistence suite against DynamoDB Local or an equivalent
  isolated engine, including transaction/race/restart and reservation-provenance
  cases, before describing Phase 25.2 as complete.
- Phase 25.1 distribution approval, real OAuth/Responses compatibility,
  account/model plan-only eligibility, native browser transport, signing-key
  operations, deployed identity and cloud acceptance remain external gates.
- The compact tombstone directory is durable local filesystem state. File-system
  exhaustion remains a host-level limit; failures creating a fence fail closed.
- Phase 25.3 still owns authenticated HTTP/UI composition and visible trust/recovery;
  Phase 25.4 owns domain integration. Imported or connected content grants no
  mutation rights.

See the [architecture and rewrite-risk review](phase-25-2-architecture.md) and
[composition guide](phase-25-2-implementation-guide.md). The living status is in
[`docs/current-state.md`](../current-state.md).

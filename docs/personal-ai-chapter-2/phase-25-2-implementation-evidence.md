# Phase 25.2 implementation and verification evidence

Date: 2026-10-10. Review basis: commits `a7294ed55c9ba5f1fcb61077ef17950910b85adb`,
`c243a46f8bffd75085ba07bec2b4be9e3cae5608`,
`2c9db878b5c4f504bd172be9fb966449a5b16ace`,
`60c261a2df59148049fa3566ab863c1175710f94`, and review target
`100353d79f5f608211f4a5d0d2d33838419c9ee9`. Follow-up source fixes and regression
coverage were verified at `03d967a`; this evidence update makes no behavior changes.

**Disposition: Phase 25.2 remains incomplete.** The local review fixes below are
implemented and offline-verified, but Phase 15 has no production pre-retrieval
membership/source/revocation authority, and the canonical DynamoDB transaction
suite could not run without an isolated engine. In the reviewed P25.2 baseline, the
`ExternalTurnAuthority` callback was still a required integration point rather than
an implementation, and its post-assembly check could not satisfy pre-retrieval
authorization. The user later directed Phase 25.3 HTTP/UI work to proceed over a
scoped request authority despite those gates. See its [decision review](phase-25-3-readiness-review-2026-10-10.md)
and [implementation evidence](phase-25-3-implementation-evidence.md). The P25.3
composition does not establish production authorization or close P15/DynamoDB
acceptance. No live provider, account, browser, cloud, or physical execution was
enabled by this P25.2 verification.

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
| Focused external-turn, bridge transport, local lifecycle, execution-contract, and persistence tests | 178 passed, 6 skipped |
| Full backend pytest suite | 1,317 passed, 82 skipped |
| Ruff | Passed (`backend/.venv/bin/python -m ruff check .`) |
| `git diff --check` | Passed |
| DynamoDB external-turn transaction/race/restart and provenance tests | 6 skipped; unverified |

The focused run used `backend/.venv/bin/python -m pytest` over external turns,
execution contracts, ChatGPT bridge transport, local lifecycle, and external-turn
persistence. The full backend suite then passed with no failures. Two warning
classes were reported by dependencies during the full suite; neither caused a
test failure.

The six skipped DynamoDB tests require
`PERSISTENCE_TEST_DYNAMODB_ENDPOINT`. This host has no `docker` executable and no
isolated DynamoDB-compatible endpoint, so transaction/catalog CAS, concurrent
finalize, stale recovery, restart/hydration, and the new negative provenance cases
remain unverified against a real engine. Fakes and JSON hydration do not establish
this behavior. Checks used the repository's `backend/.venv/bin/python` because a
system `python` executable is not available on `PATH`.

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

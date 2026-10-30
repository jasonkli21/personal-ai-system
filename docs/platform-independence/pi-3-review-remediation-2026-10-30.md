# PI-3 independent review remediation

2026-10-30, America/Los_Angeles. Remediation base: `57d3d40baba6766b51f53a8d2abcf024000864ff`.
This is implementation evidence for the supplied Luna review, not an independent
acceptance verdict. The resulting commit SHA and exact checks are recorded after
commit in this document.

## Findings addressed

- **R01, partial source-race closure:** chat context assembly now binds a
  service-owned disclosure revalidator across assembler count and summary calls.
  It checks current client authority, base disclosure, candidate-history source
  snapshots, and that candidate messages remain active. The callback is checked
  after assembly; the selected source snapshots continue to be checked during
  generation and output/replay. This closes the history-source ordinary
  pre-send window identified by the review, not atomic source leases, source
  additions in provider-derived fragments before their exact set is known, or
  already-transmitted requests.
- **R02, remote synthesis fence:** standard and iterative research bind a
  request-local revalidator across evidence selection/count and synthesis
  preparation/count/generation.
  Each check re-reads exact snippet-rights authority, selected-evidence expiry,
  accepted observation dependencies, and, for iterative research, the live run
  lease. Literal local-excerpt fake research remains separate.
- **R03, partial credential rotation fence:** strict-free admission captures a
  process-local one-way fingerprint of the exact Gemini key used at composition
  and compares it at every admission check. A changed key denies before count or
  physical send; the fingerprint is neither persisted nor logged. This does
  **not** independently prove that the initial environment key belongs to the
  account named by configured operator evidence. Strict-free production/account
  acceptance therefore remains blocked pending a trustworthy secret-version or
  equivalent account-specific binding.
- **R04, explicit unavailable capability:** the unavailable embedding adapter
  advertises the missing capability. Enabled vector retrieval returns
  `memory_embedding_unavailable`; extraction preflights the required embedding
  continuation before calling its extractor, preventing futile extraction,
  disclosure, or quota use. Existing vector bytes and identities are unchanged.
  Schema-3 lexical-memory behavior still requires a separately supported path;
  this remediation does not silently claim it works when the configured
  retriever requires the unavailable vector query.

## Deferred acceptance items

R05 (bounded attestation freshness/provenance), R06 (future adapter registration
contract), R07 (tracked source-control evidence for the pre-existing detailed
plan/prompt and independent fixture review), and R08 (installed Linux/Python 3.12
and deployment evidence) are not represented as passes. The detailed plan and
prompt remain pre-existing untracked user files. Local synthetic profiles do not
prove a real non-Gemini provider, billing, account identity, cloud, or production
privacy behavior. PI-3 remains a local candidate and PI-4 implementation remains
gated by independent acceptance and separate authorization.

## Verification

Environment: macOS 27.0.1 arm64, CPython 3.11.15. Focused review regression:

```text
backend/.venv/bin/ruff check <six changed source/test paths>: passed
pytest test_inference_execution.py test_memory.py test_chat_stream_lifecycle.py
       test_research_routes.py test_research_provider.py test_iterative_research.py
153 passed, 4 upstream warnings
```

`make pi3-check` initially reported 781 passed and one failure because the v22
source-only planning identity still described the pre-remediation source. The
v22 lock is now rebound after the final source edits to digest
`6d9ec1a937ad290b2683343fddb5fe916fba18b956d8d003b02061a5db45f18c`; v10–v21,
corpus, and held-out fixture bytes were not changed. The focused v22 preservation
test passed. One intermediate full run also had 781 passes and one stale digest
failure after later source edits. The final-source `make pi3-check` passed **782
tests** in 145.39 seconds, with zero forbidden Python network attempts; native
IPv4/IPv6/Unix denial probes passed. The first sandboxed launch could not bind
the temporary listener; the authorized native-fence run was executed outside
the tool sandbox. The suite ran on macOS 27.0.1 arm64 / CPython 3.11.15.

`UV_OFFLINE=true make pi2-check` passed installed core (88), optional reference
applications (190), retained-task (56), and installed HTTP/client (64 passed,
1 existing skip). `UV_CACHE_DIR=/tmp/pi-remediation-uv-cache
make platform-independence-check` passed the platform inventory, source and
artifact checks, and installed core/reference probes. The first platform-check
launch used the unavailable default uv cache and could not read it; rerunning
with the task-local cache passed. `git diff --check` and backend Ruff checks
passed. These installed probes use local synthetic identities, Python 3.11 and
their documented network fences; they do not establish Linux/Python 3.12, live
provider, account, billing, cloud, or production behavior.

No deterministic barrier test was added for each specific review schedule
(revocation during first context count, summary refresh/count/send, rights loss
between research count and physical reservation, or lease loss at those same
boundaries). The implementation has request-bound checks at the relevant
operations and the owning suites pass, but those exact interleaving negatives
remain an acceptance gap alongside the initial credential-to-account binding.
No independent review or production acceptance is claimed.

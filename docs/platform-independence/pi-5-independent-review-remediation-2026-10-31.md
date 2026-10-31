# PI-5 independent-review remediation

2026-10-31 America/Los_Angeles. Review target: `851a60d46c1b90d20a4992c19ec5801f26a9c403`, parent `e5412a85e58fdf0a9d7b58d1361a23b37e477190`. This local remediation addresses the review findings without changing the PI-5 acceptance boundary, attaching retrieval to chat/model context, using live credentials/providers, or changing memory behavior. MEM-3+ remains frozen.

The original detailed implementation plan remains at
`docs/platform-independence/pi-5-detailed-implementation-plan.md` as a pre-existing
untracked user file. Its SHA-256 is
`3f5f3bd83390c4681037e282652bc7230983ae43c572e0be17d75b3db72c3af5`. It was
preserved unchanged and excluded from this commit. The plan is input, not committed
acceptance evidence.

## Finding dispositions

| Finding | Disposition | Evidence and remaining boundary |
| --- | --- | --- |
| F01 — context and derived-output provenance (P1) | Deferred; acceptance blocker remains | Retrieval stays disconnected from context counts, model sends, generated answers, persistence, SSE, history, replay and export. A retained source issuer/lease and end-to-end revocation design are still required. |
| F02 — eligible external source and deployment (P1) | Deferred; acceptance blocker remains | No live Brave, paid provider, cloud/IAM, native P19/store, restore or physical deletion check was run. Strict-free Brave admission remains closed and external execution remains default-off/local-test only. |
| F03 — no-op journal exhaustion and cross-scope starvation (P1 availability) | Fixed for the reported attack | Empty typed/literal domain intersections and deterministic adapter preflight happen before receipt reservation. The 4,096 lifetime limit now applies per authenticated owner/actor/application/workspace scope, so one scope cannot consume another scope's quota. Receipts remain durable and unpruned. Aggregate journal storage across distinct scopes is unbounded; external execution remains local/test-only and operator-controlled pending a durable production ledger/capacity design. |
| F04 — Brave usage IDs lost on failures (P2) | Fixed | Timeout, transport, malformed-response and unexpected adapter failures preserve the P19 invocation and reserved attempt IDs in `SearchError` and `RetrievalOutcome`. P19 admission denied before reservation returns the invocation ID only; it does not invent an attempt ID. Errors remain non-retryable through the original-intent journal. |
| F05 — local citation authority collisions (P2) | Fixed for independently identified authorities | New operator installations use v2 with an operator-generated issuer UUID. Citation authority hashes bind that issuer, authenticated owner/actor/app/workspace and source ID. Existing v1 files remain readable with an opaque hash of the trusted configured file path as their namespace. No citation outputs are persisted by PI-5. |
| F06 — general tool extensibility (P2 product limitation) | Deferred; broader roadmap goal remains incomplete | V1 retains one fixed executable read-only tool. The implementation does not load client or manifest-supplied code, and no generic operator registry was added. The manifest-only and unknown-tool denial boundary remains closed. |
| F07 — title-only irrelevant quote (P2) | Fixed | A title match without a matching body token no longer returns a body passage. Exact body offsets, quote hash and deterministic citation validation remain in place. |
| F08 — missing committed plan (P2 evidence limitation) | Recorded; original file preserved | The detailed plan was already untracked at task entry. Its exact path/hash/status are recorded above; it was not staged or modified. |

F03's fixed behavior is bounded per scope, while total retained rows are intentionally
not globally capped: a global cap would let unrelated scopes exhaust one shared
quota again, and pruning/reuse would weaken indefinite original-intent replay fences.
Production external execution remains blocked until persistent storage, fairness,
retention and restore anti-rollback have an accepted design.

## Verification

Environment: repository's existing Python 3.11.15 macOS arm64 virtual environment;
no dependency installation, credentials, live providers, cloud services or native
database were used.

The tested source identities are:

| File | SHA-256 |
| --- | --- |
| `backend/src/personal_ai/retrieval/journal.py` | `d495e7dcf91c177c1be92d00035400f4b9b835c59b9b31111e03d3222c87d9fb` |
| `backend/src/personal_ai/retrieval/external.py` | `6aa0a47c82a75614a70b7343503284aa4d25476923915c44b2e70e44abf58d41` |
| `backend/src/personal_ai/retrieval/service.py` | `e22836482cc9577b71e2f3ee45bd95e94287e7710492d6e6bb010b475d62717b` |
| `backend/src/personal_ai/retrieval/installation.py` | `7a92c8345c8a2cbd84e919cf12e09917acc5eaa284bfc1824556fa1528f77242` |
| `backend/src/personal_ai/search/providers/brave.py` | `878b64407bd2fb4e052cf3fe2863bbf98b1f2e626bb0cdcfc056d5695a8f27d8` |
| `backend/scripts/pi5_install_demo.py` | `81563b9627a46913c62f1c0b212eeb0afc3cd710d70ab107ddd4773b4a6f570d` |
| `backend/tests/test_pi5_retrieval.py` | `52ce16bdaa2197ceb1b0d0b34cac4627c6512a3f5526ba1b6f7ee5640190b4e2` |
| `backend/tests/test_pi5_http.py` | `41ae463512f83fbb0fadd106c2d0ca977969f55a81b7350cf20ecddfec4d882a` |

| Command | Result | Interpretation |
| --- | --- | --- |
| `backend/.venv/bin/python backend/scripts/pi5_checks.py --only test_pi5_retrieval.py` | **66 unit + 27 signed HTTP passed** | Native IPv4/IPv6/Unix denial passed; zero forbidden Python and HTTP attempts. Two Python 3.11 support `FutureWarning`s per stage. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make pi5-check` | **124 native + 27 signed HTTP passed** | OpenAPI consumer contract check passed. Native network denial passed; zero forbidden Python and HTTP attempts. Two Python 3.11 support `FutureWarning`s per stage. The prior recorded 110/1 research quota failure did not recur. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint` | **passed** | Repository-wide Ruff check. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make research-eval` | **exit 0** | Synthetic offline evaluation reported `passed=true`; no live provider or answer-quality evidence. |
| `PATH="$PWD/backend/.venv/bin:$PATH" make retrieval-eval` | **exit 0** | Synthetic paired evaluation; candidate remains `not_promoted`, live quality and quota unmeasured. |
| `git diff --check` | **passed** | Whitespace validation after the remediation docs and report edits. |
| Signed installed artifact rebuild/PI-2, PI-3, PI-4 full suites, full backend, native persistence, cloud and live-provider checks | **not_run** | Outside this bounded remediation. Prior historical evidence remains in the PI-5 implementation report and verification JSON; it is not a new pass. |

The source revision is the review target above plus the code/test changes recorded in
the commit containing this evidence. Resolve the remediation commit with
`git log -1 --format=%H -- docs/platform-independence/pi-5-independent-review-remediation-2026-10-31.md`.
An initial run of the fenced script could not bind its probe socket in the default
enclosing sandbox; rerunning through the approved command runner launched the existing
macOS network-denial harness and completed. The implementation report preserves prior
failed B01 checkpoints and their variable counts. The broad current PI-5 target passed without reproducing the prior intermittent
30 ms research failure; that result does not establish its root cause or clear inherited
PI-3/4 acceptance.

One intermediate run after adding the positive P19-ID assertion had 124 native tests
pass and one signed HTTP test fail with a `NameError`: the fixture had not retained its
`Accounting` instance for the assertion. The fixture was corrected, and the final full
PI-5 rerun passed all 124 native and 27 signed HTTP tests. That transient test failure
is retained in the machine verification record.

## Acceptance decision

The result remains an incomplete standalone retrieval/tool candidate. F01 and F02
remain P1 acceptance blockers; F06 and F08 remain documented scope/evidence gaps.
Independent PI-5, deployed identity, external source eligibility, durable distributed
rights/attempt storage, restore and deletion acceptance remain open. The next safe
step is an independently reviewed design for retained source leases/provenance and
production attempt storage before any context integration or external deployment.

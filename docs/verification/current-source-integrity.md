# Current source integrity and verification results

Updated 2026-11-06 (Pacific). This report records remediation for the independent review of commit `3b92dfbbd27ee1735e8957d2acc65d084230c100` (reviewed 2026-11-07 UTC). That review rejected the commit. This remediation is a new commit with parent `3b92dfbbd27ee1735e8957d2acc65d084230c100`; prior review findings are treated as requirements, not as instructions to rewrite history.

## Review findings addressed

- Restored the exact parent bytes for eight released SQL migrations, the Python half of migration 022, and three frozen decision/research fixtures. The naming checker now permits only their exact pinned historical hashes. Migration tests check the known checksums and that recorded parent checksums are recognized as already applied.
- Hardened the active source check against false or incomplete evidence metadata. It verifies the closed planning schema, fixed evidence fields and non-promotion decision, recomputed configuration/corpus/fixture/source digests, exact source maps, immutable predecessor hashes, revision ancestry, and matching planning/offline source anchors. Offline generation 11 retains the frozen corpus and scoring identity and states that no new measurement is claimed.
- Restored closed offline suite, rubric, seed, and case-ID validation, with negative tests for arbitrary suites, rubrics, and mismatched IDs.
- Corrected the two backend workflow working directories and fetched full Git history in both source-contract jobs so ancestry checks have the required objects.
- Initialized urllib3's local IPv6 capability probe before installing the offline test network fence. The test-time fence remains active; the hermetic target now records zero blocked network attempts.

## Active source identities

| Contract | Active identity | Evidence boundary |
| --- | --- | --- |
| Planning evaluator source | Lock v37 supersedes v36; source digest `3478da59eb78a6e3a3a3f8a8d56a823d6c2d615503002384c25380eaf547ebfb` | Strict runtime replay is checked separately. The frozen lock retains `non_promotion; no model-answer quality evidence or promoted coverage`; the observed quality-case denominator is zero. |
| Offline information handling source | Generation 11 supersedes generation 10; core runtime digest `ab8c4053ae3e363ca1af70b1e5447b05a5a32819afb7ee457e7d130df4175815` | Frozen case digest remains `25df654eda27040c3b52695fd6ec695b53238a7cf76b82e1ed4e5d442b55205d`; generation 11 claims no new measurements and no promotion. |
| Historical artifacts | Planning v1–v36, offline generations before 11, the three fixtures, and released migrations retain pinned bytes | New identities are additive; historical evidence is not rebound to current source. |

The read-only source check is deliberately split from strict runtime replay and installed/native capability checks. It passed twice from the committed remediation tree with:

```text
PORTABLE_SOURCE=PASS
STRICT_HISTORICAL_RUNTIME_REPLAY=NOT_RUN
INSTALLED_NATIVE_CAPABILITY=NOT_RUN
```

Run it from the committed tree with `make source-contract-check`. It verifies active metadata and source bytes; it does not run a benchmark or establish installed/native behavior.

## Verification results

| Gate | Result | Evidence and limits |
| --- | --- | --- |
| `make hermetic-capability-check` | **PASS** | All reasoning, memory, and workflow lanes completed; each offline runner summary reported `OFFLINE_RUNNER_BLOCKED_NETWORK_ATTEMPTS=0 events=[]`. |
| SDK offline suite | **PASS** | 442 passed, 12 deselected, zero blocked network attempts. |
| Source, migration, and planning regression tests | **PASS** | 117 passed; covers active evidence tampering, immutable migration checksums and recorded predecessor checksums, planning identity, and portable source validation. |
| Offline information contracts | **PASS** | 54 passed, 11 loopback HTTP tests deselected because this managed environment does not permit local socket binds. |
| `make naming-policy-check` | **PASS** | Exact-path, exact-hash exceptions for immutable fixtures and released migration bytes; five naming-policy tests passed. |
| `make backend-lint` | **PASS** | Ruff passed. |
| `make planning-eval` | **PASS / NO_PROMOTION** | Strict runtime replay passed, but there were zero quality cases; it provides no model-answer quality or promotion evidence. |
| Workflow YAML and `git diff --check` | **PASS** | YAML parsed locally; whitespace checks passed. `actionlint` was not available. |
| Native PostgreSQL and full loopback suites | **NOT RUN / BLOCKED_UNVERIFIED** | The managed sandbox disallows local loopback binds; no disposable PostgreSQL service was available. The recorded migration test is a unit-level recorded-history check, not native PostgreSQL upgrade evidence. |
| Hosted CI, installed native consumers, external providers, cloud, and production | **NOT RUN / BLOCKED_UNVERIFIED** | No hosted workflow result or external/provider/cloud/production action was performed. |

Python 3.11.15 emitted upstream support-window and Starlette/httpx deprecation warnings. They did not fail the local checks. Do not interpret deselected or unrun lanes as passes.

## Historical report boundary

The prior text in this report, including planning v36, offline generation 10, the 402-pass SDK result, the old full-suite counts, and the `READY_FOR_INDEPENDENT_REVIEW` statement, described the rejected commit only. Those results do not describe this remediation. The independent review's W0 verdict remains authoritative until a separate review accepts the new commit. Production remains `NO_GO`; no W1, provider, cloud, identity, restore, or physical-erasure gate is closed here.

See [the independent review handoff](independent-review-handoff.md) for the corrected commit scope, commands, and remaining acceptance boundary.

# PI-6 offline benchmark contract v1

Preregistered 2026-11-02 before candidate measurement. Suite `pi6-offline-v1`;
fixture directory `backend/src/personal_ai/evaluation/fixtures/pi6/`. Frozen
manifest binds cases, split, rubric and scoring source before held-out execution.
Any change requires a new explicit identity; no historical fixture is mutable.

Strict, bounded JSON only. No executable scoring expressions, import strings,
source paths, arbitrary URLs or transport selection. The driver receives task
inputs, never expected outcomes. The scorer sees ephemeral observations and
oracles; persisted output is an allowlisted schema with opaque case digest,
family/split/arm, categorical outcome, numeric scores/counts/timings, identities
and explicit confidence. No raw prompts, source excerpts, profile values,
answers, credentials, headers, identities or exception text may be retained.
Optional `emit` receives the same safe schema. Errors are fixed codes.

Eight families: one-app context; consented public-HTTP profile; MEM-0/1/2
controls; branch/long context; research citations/conflicts; PI-5 local context
and standalone retrieval; provider unavailability; original-key/source transition.
Each has independent calibration/held-out lineages and task-specific outcome,
forbidden action, citation oracle, rights/expiry event and budget. Raw synthetic
fixture data may be versioned as input, never copied into observations.

Eligible pairs alone enter held-out denominators, grouped by family. No cross-arm
state/cache/history. Same facts/rights/budget per pair; only preregistered selection
or packing configuration differs. Baseline/current context and candidate labels
do not imply either production promotion or an improvement. No fabricated CI;
uncertainty is `inconclusive`, real-model utility `unmeasured`, promotion
`not_promoted`. All safety vetoes dominate utility. Full original P6-01–33
obligations remain in the verification ledger, including blocked production rows.

Run `make pi6-check` from the root with the backend virtualenv on PATH. The
launcher provides a native loopback-only network sandbox and a Python audit
fence; benchmark execution requires that launcher. Unit checks use deny-network.
Native and Python fence evidence are reported distinctly. Inherited verification
does not get relabeled as PI-6 task measurement.

## Prospective v2 protocol and review remediation — 2026-11-02

V1 remains immutable historical evidence. Its held-out content was exposed
during development, so it is not confirmatory. V2 uses 32 newly authored
synthetic cases and IDs in `cases-v2.json`. They were authored by the same
implementation session, are not blind and are not independent validation.

The v2 manifest freezes the case bytes, closed observation contract, scorer,
driver, runner, HTTP adapter, audit module, full core runtime, and available
Reading Logbook client/host source trees before the final measurement. Drivers
do not receive expected outcomes. Expected effects derive from case/arm
semantics; the isolated observer counts model dispatch, tool writes, stale
disclosure, denials, memory access and mutations. Forbidden effects veto the
row regardless of quality. Facts require positive task-specific answer and
source evidence. Denials and memory controls require an attempted operation and
explicit resulting status.

Coverage is calculated from the immutable corpus before dispatch. Each expected
case/arm must appear once and score completely; unknown, duplicate, missing,
unmeasured or evidence-incomplete rows invalidate evaluation and produce a
nonzero check result. Task-quality losses remain distinct from structural
coverage failures and safety vetoes.

Each operation is isolated in a killable process with a hard five-second
deadline. The whole suite has a fixed 300-second deadline. It enforces 8,192
source bytes, 32,768 input units and 256 output units. Suite or operation
timeouts stay visible in the expected denominator. Bounded log/stdout handling
and child termination prevent output or background threads from escaping into
later measurements.

`make pi6-check` is the canonical measured entrypoint. Each measured worker
proves native loopback-only fencing in its own process and installs the Python
audit hook. A Python sentinel is not treated as a security capability. The
installed probe runs the same full evaluator/scorer from wheels outside the
checkout; core-only mode reports missing optional HTTP dependencies as explicit
ineligibility and cannot pass coverage.

The local v2 evaluation is complete for its 68 scripted rows. Its score is not
real-model utility, independent fixture validation, live provider behavior or
production acceptance. The user closed this scoped review remediation with no
further review required; the evidence boundary remains unchanged.

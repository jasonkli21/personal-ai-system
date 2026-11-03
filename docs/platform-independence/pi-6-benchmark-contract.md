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

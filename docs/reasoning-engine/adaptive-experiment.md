# Adaptive strategy fixture experiment

This is the preregistered protocol for the author-visible E1 experiment.
The [machine-readable manifest](../../backend/src/personal_ai/evaluation/reasoning_adaptive/manifest.json)
defines the splits, seeds, work weights and thresholds. The sealed lane
binds that manifest, the independently invoked scorer, case inputs, split,
oracle, installed strategy policies and execution code. A separate
checksum pins the seal. This corpus and scorer were authored in the
implementation session. A clean rerun checks reproducibility. Blind,
independently authored cases and approval require a separate review.

## Arms and custody

| Profile | Baseline | Shadow | Offline arms |
| --- | --- | --- | --- |
| Finite arithmetic | Existing V1 selection, templates and predicates | Actual V1 execution plus the installed redacted recommendation | Selected candidate comparison, then separate runs without the family filter, early exit, or alternative |
| Grounded | Existing V1 source snapshot, bounded focus and exact-citation verification | Actual V1 execution plus the installed single-gap recommendation | One-shot retrieval ablation with the same maximum caps |

Each arm starts a fresh fixture, scope and row store, uses a distinct stable
original key and gets the same task, scripted endpoint, source facts and
maximum requested envelope as its pair. Arm order is shuffled with seed
82753. Grounded arms reset the same source rules and relative freshness.
The existing grounded path uses the current verified snapshot and current
clock. Random run and citation identifiers and elapsed time are excluded
from the semantic digest.

The finite split has 14 development and 112 held-out cases across 14
strata. The grounded split has eight development and 48 held-out cases
across eight strata. Task operands and source facts use seed 81017.
The fixture executor receives only the synthetic input and arm. The runner
applies the separately stored oracle after the arm finishes. The production
policy has no dependency on the evaluator, labels, oracle, traces or
candidate content. There are eight applicable finite development templates
and at least four grounded coverage scenarios. The predeclared utility table
uses a conservative design prior of 25 quality points, a ten-point
uncertainty penalty and ten-point marginal work cost. These are fixture
policy constants, with development support checked by the cohort design.
They are not estimates of production success probabilities.

## Scoring and decision rule

The primary outcome is exact supported completion. The scorer verifies
each supported integer slot, and for grounded claims checks the cited
wire item, fixture source and exact value independently. Failures, partials
and abstentions remain in the full denominator. Eligible paired estimates
are reported separately. The scorer also checks physical witnesses against
the workflow ledger, including reserved, dispatched, observed and unknown
operations and exact fake bytes. An uncertain generation is charged its
entire reserved byte envelope in the work score. Real provider tokens,
quota and charges remain unknown.

Work costs 0.05 per dispatched generation, 0.02 per retrieval, 0.01 per
verifier operation, 0.0025 per count and 0.000005 per measured fake byte.
Net utility is exact completion minus work. Report paired deltas and
two-sided percentile 95% intervals using 4,000 paired bootstrap draws
(seed 84623), separately for all held-out pairs and eligible held-out
pairs. The promotion slice requires at least 64 independent matched
pairs. Planning at paired difference standard deviation 0.4 yields an
approximate 95% half-width of 0.098 at that sample size. Report wider
intervals as observed. The authored, templated pairs are dependent by
construction. Their intervals describe this scripted corpus and carry
no model or external task inference.

A technical E1 pass requires all pairs, zero safety vetoes, zero changes
to physical work in shadow, zero extra simple-task work in the installed
adaptive arm, and stable semantic hashes across fresh processes. A
reviewer considering local canary approval must additionally require
positive lower 95% bounds for both held-out exact completion and net
utility on the exact approved slice, zero subgroup regressions, zero
unknown fixture effects and no unnecessary work after objective
sufficiency. The fixture report has no promotion authority. Real-model
quality, live dispatch and deployment require separate evidence.

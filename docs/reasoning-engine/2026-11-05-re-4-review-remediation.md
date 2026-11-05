# RE-4 review remediation — 2026-11-05

This change addresses the two findings in the independent review of
`992118dd43cf7225541b1eb9866374a79fa6ec58` by failing closed. It does not
grant independent acceptance or promotion.

## Changes

- Finite runtime selection abstains because the installed trusted
  pre-generation features do not distinguish the known
  `multi_decompose_wins` subgroup. It retains the V1 baseline for every
  finite family. Holdout IDs, labels, oracle data, source text and candidate
  outputs do not enter this decision.
- Local canary pointer publication is blocked until an independent artifact
  verifier and separately held blind evidence are available. Ed25519 still
  authenticates a reviewer but is not treated as proof that signed metrics
  were measured from rows. A missing verifier leaves the pointer disabled.
- The author-visible V1 result, corpus, oracle and scorer were not edited.
  No new performance result is claimed for the changed runtime. The original
  sealed evaluation can be reproduced from its exact historical commit;
  running it against modified runtime source correctly fails the source seal.

## Verification

- Targeted policy and publication regressions: **2 passed**, 69 deselected;
  offline runner reported **0** network attempts.
- `make reasoning-adaptive-check`: **42 failed, 28 passed**, 1 deselected.
  The failures are existing tests that publish fabricated signed certificates
  and then expect the now-blocked canary execution, plus the frozen evaluator
  test that rejects the changed source bytes. These failures remain visible;
  they are not reported as passes.
- `git diff --check`: passed.
- No independent corpus, artifact verifier, native PostgreSQL, installed
  model, provider, issuer, deployment, restore or real-task evidence was
  available or created here.

## Disposition

F-01 is contained by abstaining from finite adaptive selection. F-02 is
contained by blocking canary publication. E1 independent acceptance remains
**WITHHELD**; canary status remains **NO_PROMOTION**; E2–E5 remain
**BLOCKED_UNVERIFIED**; production remains **NO_GO**. A future change must add
an independently custodied, mechanically checked evidence generation and
tests for it before relaxing either block. Do not retune or relabel the frozen
author-visible V1 corpus.

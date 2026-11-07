# Frozen reasoning offline benchmark v1

`reasoning-offline-v1` preregisters 32 synthetic cases, four per family.
The last case in each family is a holdout. All content is author-visible.
The [manifest](../../backend/src/personal_ai/evaluation/fixtures/reasoning/manifest-v1.json)
pins the ordered case/split grid, rubric implementation, input data, driver,
harness, runner, model identity and protocol. Its expected digest lives in
the version-specific seal loader. Record its source commit/tree externally to
avoid a hash cycle. The trusted checkout and seal loader are the integrity
anchor. Hashes detect drift and supply no authentication against replacing
that anchor. Changes to frozen sources or fixtures require an additive version.
Historical offline information-handling, real-task, planning and memory artifacts
retain their original identities.

## Arms and scoring

Both eligible arms get identical prepared facts, scope, responder, unit
limits and a fresh one-attempt port. The direct arm generates one result from
the prepared input when admitted. It has no check or retry. The check arm
does the same generation and performs one bounded arithmetic check on the
numeric family. It abstains on disagreement. Its extra deterministic work
is counted within the same one-check ceiling. All 28 unsupported pairs
remain in the attempted grid. The fixture responder uses a simple fixed
heuristic that can produce wrong answers. Holdouts are descriptive.

| Family | Objective rubric |
| --- | --- |
| Extraction | Exact value of requested field |
| Planning | Number of frozen requirements met by selected option |
| Citations | Exact value and matching fixture support slots |
| Debugging | Hermetic boundary vectors over a closed set of predicate proposals |
| Numeric | Frozen exact arithmetic value, checked-arm acceptance/abstention |
| Uncertainty | Abstention for conflicting or missing support, exact value and slots when supported |
| Scope | Wrong app, revoked and stale rights stop before attempt. Injected content carries no authority. Foreign evidence excluded from preparation. |
| Resources | Quota, cancellation and logical deadline stop before attempt. Simulated provider acknowledgement loss retains one uncertain attempt with same-intent observation and changed-body conflict. |

Candidate generation sees prepared task data without labels, split, original
scope labels, oracle or scoring functions in its inputs. The trusted scorer
compares the closed observation with fixed expectations and checks independent
port counters. A numeric abstention is not exact success. Objective task
scores are proxies. Expected denials and failures are valid observations.
A missing/duplicate row, broken custody, unexpected status, uncounted attempt,
forbidden effect or unsupported assertion from the check arm invalidates the
run. Scored quality misses in the direct arm are reported as misses.

## Bounds, output and replay

One model attempt, one local check, four slots, 512 estimated input units,
64 estimated output units and no real sends, billed spending or source
lookups. The deadline scenario uses three logical ticks. A separate
30-second supervisor bounds the whole finite script. No provider, installer,
source service or production dispatch runs. The launcher attempts a native
network-denial profile on macOS, verifies local socket denial if applied and
records unavailable native fencing distinctly. Python audit blocks sockets,
subprocess and common filesystem mutations during measurement. It is a
regression guard on trusted code, with no claim about hostile native code.

`make reasoning-eval` writes an ignored report under `artifacts/reasoning/`.
It contains hashed case identifiers, closed status codes, cohort and pair
counts, observed fake attempts/results/checks, fixture word-unit estimates,
and provenance. Python audit attempts and unsafe disclosure attempts veto
success. Actual model tokens and provider cost are unknown. Local fake row
elapsed times characterize this script only. Compare `semantic_sha256`
across fresh processes. Timing, checkout metadata and fence environment are
outside the semantic digest and must be inspected separately. No percentage
lift, calibrated quality, native recovery or model evidence follows from
these scripted measurements.

## Optional external coding study

Preregister paired tasks and an acceptance rubric. Compare an unchanged
OpenCode-style harness with the same harness plus separately authorized
read-only PAS context/evidence advice. Match model and exact profile,
workspace snapshot, hardware, tool access, elapsed/token/call limits,
retries, interventions and scoring. Randomize arm order and reset state
between pairs. Track accepted patches, independent tests, stale or incorrect
source help, privacy incidents, interventions, failures and total overhead.
Credit only marginal accepted outcomes after subtracting work the harness
already does. Disclose exclusions and null or adverse results. PAS supplies
read-only advice while the external harness owns execution and edits.
Independent rights, installed isolation and actual model access are
prerequisites for running this protocol.

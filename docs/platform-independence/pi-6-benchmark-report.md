# PI-6 offline benchmark results — 2026-11-02

Status: **partial offline evaluation; not_promoted**. PI-5 remains
`blocked_unverified`; PI-6 production promotion is `no_go`. This is a scripted
service/context proxy, not model quality, live price or deployment evidence.
See [canonical observations](pi-6-benchmark-report.json),
[verification](pi-6-verification.json) and [preregistered contract](pi-6-benchmark-contract.md).

The frozen corpus has 32 entirely synthetic tasks across eight families, split
16 calibration / 16 held-out source configurations. Two arms yield 64 records;
four additional standalone retrieval controls yield 68 observations. Warmup is
outside the corpus. Every arm gets new repositories, source files, journal,
profile/consent state, HTTP host and transport. The driver receives only task
inputs, never the oracle. Scripted generation consumes actual packed messages.

| Held-out family | Matched pairs | Wins | Ties | Losses | Success risk difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| One-app context | 2 | 1 | 1 | 0 | +0.5 |
| Consented profile | 2 | 0 | 2 | 0 | 0 |
| Existing memory controls | 2 | 0 | 2 | 0 | 0 |
| Long context / active branch | 2 | 0 | 2 | 0 | 0 |
| Research citations/conflict | 2 | 0 | 2 | 0 | 0 |
| Local retrieved context | 2 | 1 | 1 | 0 | +0.5 |
| Fake provider availability | 2 | 0 | 2 | 0 | 0 |
| Original-key/source transitions | 2 | 0 | 2 | 0 | 0 |

Held-out baseline task success is 14/16; selected-context candidate is 16/16.
The two additional held-out standalone controls both succeed and are excluded
from those pairs. No safety veto occurred in the final run. These are record
counts, not independent task populations: one-app/retrieval share the same narrow
source-availability mechanism, and some task templates span splits. Unique
source/lineage identifiers do not establish independent fixture authorship.
Uncertainty is **inconclusive**; no statistical interval or real-model lift is
claimed. The minimum scripted gain condition is met, but cannot promote a policy.

The profile held-out tasks check edit/expiry denial; memory held-out tasks check
unsupported revision and revocation. Calibration contains positive profile/recall
and forget tasks. The branch cases prove active-history selection, not summary
quality. A deterministic fake ignoring malicious instructions does not establish
live-model prompt-injection resistance. Independent review must challenge these
coverage limits, oracles and the shared-template structure.

Both research arms preserve literal support and conflicting sources. Across the
two held-out research tasks, synthesis input estimates total 2213 for literal
packing and 2130 for compact packing (83 fewer estimated units); output estimates
remain 367 aggregate. This is bounded synthetic packing overhead, not a vendor
count or dollar saving. No default is changed.

Input units for HTTP fake generation are exact bytes of the declared local JSON
serialization, **not vendor tokens**. Output units are estimates. Memory control,
failed/denied and tool operations may have unknown or inapplicable counts; null
never means zero. The fake profiles bypass physical-provider P19 accounting.
Reservations/settlements and live quotas remain unmeasured; separate inherited
P19/P21 tests provide structural evidence only. Every row separates synthetic
USD 0 from null real USD, upper bound and estimated USD.

Final local instrumentation over 68 heterogeneous observations has p50 318.612 ms
and p95 403.690 ms, including disposable host setup. These values are local fake
latency, vary by run/load and do not establish a live SLA. The canonical JSON
binds its own runtime source digest, fixture/scorer/contract hashes and dirty base
revision; timing changes do not change the frozen semantic oracle.

The first measurement had four conservative vetoes because the driver did not
normalize `required_context_source_empty`: two calibration and two held-out
irrelevant-source cases. Production correctly denied before any fake send.
The calibration-observed exact error mapping was fixed without changing fixture
or scorer bytes. The initial report is retained locally at
`artifacts/pi6/initial-benchmark.json`, with its hash and source identity in the
verification ledger. The final rerun passes. This correction is driver evidence,
not a production security fix or a tuned utility gain.

The launcher proves native IPv4/IPv6 remote denial and permits numeric loopback
HTTP only; its Python audit self-test is separate and reports zero forbidden
attempts. Installed PI-6 probes use the native loopback fence with examples
physically installed separately and reference/toy files absent. Existing
PI-2 installed public HTTP checks have their own Python-fence evidence. No class
is silently upgraded to cloud, live identity or provider acceptance.

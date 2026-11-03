# PI-6 benchmark results — 2026-11-02

Status: **local scripted evaluation complete; `not_promoted`**. PI-5 remains
`blocked_unverified`; PI-6 production promotion remains `no_go`. The v2 result
is a synthetic service/context proxy, not model quality, live price, deployment
or population-level evidence. See the [v2 observations](pi-6-benchmark-report-v2.json),
[preserved first v2 run](pi-6-first-v2-measurement-2026-11-02.json),
[verification ledger](pi-6-verification.json) and
[benchmark contract](pi-6-benchmark-contract.md). The original v1 observations
remain at [pi-6-benchmark-report.json](pi-6-benchmark-report.json).

## Frozen v2 measurement

The prospective v2 corpus has 32 new, synthetic, agent-authored cases across
eight families. It was frozen against the repaired scorer, contracts, driver,
runner, HTTP adapter, audit module, backend runtime and available Reading
Logbook client/host sources before its final measurement. It is not blind and
was not independently authored. V1's previously exposed held-out examples and
its original fixture/manifest hashes remain unchanged; v1 is developmental
history, not confirmatory evidence.

The final source-tree run recorded all **68 expected arms** with zero missing,
duplicate, unknown, unmeasured or evidence-incomplete rows. It had no safety
veto. The eight held-out families each contain two matched pairs:

| Family | Pairs | Candidate wins | Ties | Losses | Risk difference |
| --- | ---: | ---: | ---: | ---: | ---: |
| One-app context | 2 | 1 | 1 | 0 | +0.5 |
| Consented profile | 2 | 0 | 2 | 0 | 0 |
| Memory controls | 2 | 0 | 2 | 0 | 0 |
| Branch and long context | 2 | 0 | 2 | 0 | 0 |
| Research | 2 | 0 | 2 | 0 | 0 |
| Local retrieval | 2 | 1 | 1 | 0 | +0.5 |
| Provider availability | 2 | 0 | 2 | 0 | 0 |
| Replay and source transition | 2 | 0 | 2 | 0 | 0 |

Across the 16 held-out pairs, baseline succeeds on 14 and candidate on 16. The
2 wins are scripted outcomes tied to source selection; they do not measure
model lift. The four standalone retrieval controls are reported separately and
are excluded from the paired denominator. Shared templates and source
availability mechanics limit the effective diversity. Uncertainty remains
`inconclusive`; no confidence interval or generalization claim is made.

The research arm uses fixed local fake sources and a fake research model. The
branch arm checks active history behavior, not summary quality. The memory arm
checks current content, dependency and revocation outcomes, not broad correction
utility. Fake provider profiles do not exercise physical P19 accounting. Real
USD, provider quota, upper-bound cost, deployed identity and distributed send or
source authority remain unmeasured. Promotion stays `not_promoted`.

Final local synthetic latency was p50 **1,445.813 ms** and nearest-rank p95
**1,542.133 ms** over 68 records, including isolated worker and disposable
service setup. These measurements do not estimate a live SLA or vendor latency.
Synthetic USD zero is kept separate from unknown real USD and quota.

## Installed-wheel checks and identities

`make pi6-check` built the core and optional wheels, ran 54 focused adversarial
tests, and verified native IPv4/IPv6 remote denial plus same-process Python
denial. The installed core-only evaluator produced 68 rows and explicitly marked
52 host-dependent arms ineligible; its incomplete coverage correctly did not
pass. With Reading Logbook client and host wheels installed separately, the
full evaluator passed with 68/68 rows, complete coverage and native fencing.
The temporary environments contained no reference-app package in the core-only
phase, and installation used `UV_OFFLINE=1`, `--no-index` and `--no-deps`.

| Artifact | SHA-256 |
| --- | --- |
| v2 cases | `25df654eda27040c3b52695fd6ec695b53238a7cf76b82e1ed4e5d442b55205d` |
| v2 manifest | `ad69387bca873df3e9b3522ff15d222122d49ed572d8a113423cae5fd0af336c` |
| planning v27 lock | `f15dd0ee032d2013e9caa06fb82de9ec7d68ef5290f5ba352f510ec268ec24e8` |
| final v2 observations | `57783d392d53d740c7a07e61366ffba319d394a677f5b4da5a3f9ac9b8ba30f1` |
| source runtime identity | `2c6a52f0ac002042c1881738749d26006d3b8a6f2122241aa9c6c7f31194539a` |
| installed runtime identity | `181c3b81cdd898f293441296f71574740da3ba7587f5b4ed334b6f6aaf46b798` |
| backend wheel | `ec505abe871c0268589ef47ca3366a3462b8bf1dec8a6a88c42952f36130c1b0` |
| Reading Logbook client wheel | `a0b341030c33201999a575795a2ed98e4f103281cc5a5c5b34be86d1d87fa933` |
| Reading Logbook host wheel | `76e83ee390bf9ecb5dbf8613c5a93fb44354625ebe2f699a7a35d4bf0f87531f` |

## Preserved failed iteration

The first v2 measurement is preserved separately with SHA-256
`f8e7a91401adcbfa55b4c353a12c33c41abe629734cf88255499dc31500a0d2c`. It
recorded 68 rows but 13 evidence-incomplete arms, including all eight research
arms and unsupported-fact baselines. Coverage failed and evaluation was
incomplete; no safety veto occurred. The follow-up fixes changed effect
instrumentation and unsupported-fact classification, not case oracles. The
final report is a new measurement with a separately frozen protocol identity.

The original v1 case, manifest and planning locks remain preserved byte for
byte. Planning v27 binds the final remediation source identity
`d099f766bf4b85c4d7b843f04f0615291240018205ead0daef6f8e7fc9c6a679`; historical
v26 remains unchanged at SHA-256
`d3503c40af9aa122e80c1cd9d99da0e7236b29ed404cf8c3c20f9e8f6dff6c85`.

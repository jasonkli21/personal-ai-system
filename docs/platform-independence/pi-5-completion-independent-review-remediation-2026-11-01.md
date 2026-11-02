# PI-5 completion review remediation — 2026-11-01

This entry addresses the independent review dated 2026-10-31 for target
`6056a9c9f18750d2044e2fd47bc5ca67fb16633b`. The starting checkout was exactly
that target with a clean worktree. The review is input and evidence; its
standalone Luna prompt is not evidence that its operational prerequisites exist.

## Local defect fixed

Finding R05 identified that `GET /v1/conversations/{id}/context` called
`ConversationService.get_conversation` without the request-bound source
permission revalidator. The regular detail route already passed this dependency.
The inspection route now passes the same dependency. The service's existing
fail-closed behavior remains unchanged: retrieval-derived history is denied if
any retained source dependency is expired, stale, or cannot be revalidated.

Route tests cover an authorized retrieval-derived history, a revoked permission,
and an absent revalidator. The two denial cases return the content-free
`conversation_source_authority_changed` response and do not include source
identifiers or generated answer text. These synthetic route cases do not
independently exercise every source mutation, actor, application, workspace,
or deployed client-policy race from the review's adversarial list.

## PI-5 disposition

R05 is fixed locally. The review's mandatory P1 findings remain open:

- **R01 / F01 / P5-11 and P5-14:** local file snapshots are not a monotonic,
  distributed source lease atomic with physical model dispatch. External source
  context and source-specific export consent with provenance-bearing artifact
  revalidation are not implemented.
- **R02 / F02 / P5-04, P5-19 and P5-26:** no approved provider/account,
  source rights, live privacy/free-tier/quota evidence, physical attempt proof,
  deployed private IAM/network, or real provider verification is available.
- **R03 / F03 / P5-22 and P5-27:** the SQLite journal does not establish
  cross-worker durability, monotonic recovery, stale-backup anti-rollback, or
  physical deletion. No native restore or deletion action was attempted.
- **P5-24:** the canonical macOS/Python 3.11 planning evaluation and causal
  resolution of the previously intermittent inherited regression remain open.
- **R07 / F08 / P5-28:** this checkout cannot independently establish
  workstation ownership or original bytes for files that were untracked at the
  reviewer's clone.

No new migration or runtime authority was added. Paid/fallback and external
provider execution remain default-deny. No provider, cloud, production data,
restore, deletion, or deployment action was performed. Prior PI-0–4, MEM,
Phase35/36, native persistence, and production gates retain their own status.
PI-5 remains `blocked_unverified`; this change does not authorize PI-6 runtime
work or constitute independent acceptance.

## Concrete prerequisites to close the blockers

1. Name the exact provider, account/project, permitted source domains, allowed
   operation, privacy/licensing basis, request cap, spend cap, rate cap, and
   operator authorization record before any live request. Verify eligibility,
   quote rights, P19 invocation/attempt identity, SDK retry behavior, aggregate
   quotas, and unknown-outcome handling at that exact operation.
2. Provide the deployed identity and private invocation environment, including
   the approved Google user/service role, API ingress policy, network boundary,
   and monitoring needed to prove that only the authorized caller can dispatch.
3. Provide an approved native transactional store and source issuer with
   monotonic issuer/revision/rights epochs, leases, revoke/delete fences, and an
   authoritative physical-send permit tied to the P19 original-intent record.
   Demonstrate concurrent workers, lost acknowledgements, cancellation, SDK
   retries, restart, capacity exhaustion, and fair admission without a second
   physical effect or recycled intent key.
4. Provide a disposable, approved backup/restore fixture and a separately
   authorized recovery exercise. Demonstrate high-watermark anti-rollback,
   physical deletion, and post-restore rejection of stale source and attempt
   state. Do not use production data for this fixture.
5. Define export-purpose consent, provenance-bearing export artifacts, and
   current-authority revalidation on reads before implementing derived export.
   Keep current export denials in place until this contract and its evidence
   exist.
6. Run the canonical pinned macOS/Python 3.11 commands for PI-2 through PI-5
   and inherited provider-matrix, Phase35/36, research, retrieval, and full
   offline suites. Preserve the historical fixtures, scores, thresholds and
   locks. Obtain a separate independent review of the exact committed source
   and operational evidence.

## Verification

Environment: repository `backend/.venv`, macOS arm64, CPython 3.11.15. No live
network, provider, cloud, database, restore, or deletion checks were run.

| Command | Result | Evidence class |
| --- | --- | --- |
| `backend/.venv/bin/python -m pytest backend/tests/test_context_routes.py -q --tb=short` | **17 passed, 3 warnings in 1.78 s**. Warnings: Starlette/httpx deprecation and two Google client Python 3.11 support notices. | Local synthetic route tests |
| `PATH="$PWD/backend/.venv/bin:$PATH" make backend-lint` | Initial run found import ordering in the new test; sorted the imports and reran. Final run: **All checks passed.** | Static |

The tested change is intentionally narrow. Review cases covering real provider
rights/cost, distributed authority, stale restore, physical deletion, and
deployed IAM/network remain unrun and are not inferred from these tests.

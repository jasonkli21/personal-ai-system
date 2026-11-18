# User inference routing policy v1

**DRAFT / NOT DEPLOYED.** The proposed effective policy is materialized per verified owner/app/workspace. The service derives and validates identity from the authenticated session, uses revision-checked owner edits and binds every decision to the stored policy revision. An app may narrow a task's candidates. Only the owner can change consent or increase a budget.

## Policy shape

Each example is a complete synthetic policy. Identifiers refer to operator-reviewed catalog entries. Model aliases in these examples represent exact fixture IDs. Materialize a factory policy for each scope from installed free candidates. An empty eligible set stops the operation.

```json
{
  "version":"inference-policy-v1","revision":1,"preset":"free_only",
  "scope":{"owner":"owner-a","app":"travel-demo","workspace":"trip-a","operation":"answer"},
  "required":["text","stream"],"routes":["free_api"],"models":{"free_api":["fixture-free"]},
  "recipients":["free-endpoint-a"],"plan":null,"background":null,"paid":null,
  "fallback":"safe_only"
}
```

```json
{
  "version":"inference-policy-v1","revision":2,"preset":"subscription_first",
  "scope":{"owner":"owner-a","app":"travel-demo","workspace":"trip-a","operation":"answer"},
  "required":["text","stream"],"routes":["subscription","free_api"],
  "models":{"subscription":["fixture-plan"],"free_api":["fixture-free"]},
  "recipients":["host-a","plan-endpoint-a","free-endpoint-a"],
  "plan":{"connection":"plan-a","host":"host-a","account":"account-a","plan_only":true},
  "background":null,"paid":null,"fallback":"safe_only"
}
```

```json
{
  "version":"inference-policy-v1","revision":3,"preset":"custom",
  "scope":{"owner":"owner-a","app":"travel-demo","workspace":"trip-a","operation":"answer"},
  "required":["text","stream"],"routes":["subscription","free_api","paid_api"],
  "models":{"subscription":["fixture-plan"],"free_api":["fixture-free"],"paid_api":["fixture-luna-text"]},
  "recipients":["host-a","plan-endpoint-a","free-endpoint-a","luna-demo"],
  "plan":{"connection":"plan-a","host":"host-a","account":"account-a","plan_only":true},
  "background":null,
  "paid":{"opt_in":true,"payer":"payer-a","account":"billing-a","endpoint":"luna-demo","currency":"USD","per_request_micros":40000,"monthly_micros":1500000},
  "fallback":"safe_only"
}
```

`version` and `fallback` are literals, revision is a positive integer. Scope is four exact IDs. Routes is an ordered, duplicate-free list of up to three external classes. Models maps each route to a nonempty array of exact model IDs. Recipients are exact approved host/endpoint IDs. No wildcards. Required capabilities intersect with the task's independently established requirements (including modality, streaming, context size, supported tools and quality floor). Empty disclosure permissions deny. Null plan, background or paid objects disable that use. A plan object requires all shown keys and a current connection bound as described in [ChatGPT boundaries](chatgpt-integration-boundaries.md).

A background grant, if enabled, contains consent ID, operation, app, workspace, host, maximum runs per UTC day and UTC expiry. Authenticate the originating owner and decrement the run limit atomically. An interactive grant cannot authorize scheduled work. The paid object requires every shown key, positive integer micro-unit limits and verified payer/account authority. The monthly limit caps aggregate owner spending across apps, hosts and policies. Apply the strictest active owner, payer and operation caps across concurrent reservations. Store price revision, currency and grant epoch with each attempt. Reject unknown fields, classes, currencies or inconsistent presets on read/write. Version incompatible changes explicitly. Read older policies only via reviewed conservative migration. Unsupported policies deny all external sends.

## Eligibility before preference

1. Apply system, deployment, kill switch, provider program, security and operator admission gates.
2. Resolve owner, app, workspace, requested operation and current source-purpose-recipient grants. Require permits for each hop, including host and ultimate model. Reassemble for a different recipient and revalidate at physical send. A revoked required source ends the operation.
3. Enforce current user policy, client/account/host binding, disclosure ceiling, background consent, model allowlists, price and quota. Require current task capability and quality evidence. Exclude a candidate on missing facts.
4. Visit eligible routes in user order. Within a class use the existing deterministic router with stable endpoint ID as final tie-break. Record policy revision, exclusions and attempt IDs without content or secrets. End on exhaustion.

| Class | Dispatch condition and accounting |
| --- | --- |
| offline_fake | Explicit local/test profile only. Simulated output is never used as a successful external fallback. |
| free_api | Exact model, credential, quota window and zero-charge/no-overage attestation are current. Recheck quota at reservation and send. A free marketing label provides no evidence. |
| subscription | Eligible connected application, account-visible model, plan-only evidence, bound user runtime and current user activity or background grant. Track plan allowance separately. |
| paid_api | Operator enables an admitted paid profile and user explicitly opts in for the exact endpoint/model/payer. Reserve an enforceable upper bound before send. |

**Factory invariant.** Validate free_only as routes exactly [free_api] with paid, plan and background null. At dispatch independently require a paid authorization and monetary reservation for every endpoint classified as paid. Reject class mismatches, stale attestations, missing policy and unknown costs. Exhaustion leads to stop. Neither an app-supplied model nor a quota failure creates a transition to paid.

## Reservation and fallback state machine

Bind one durable intent to actor, scope, logical operation and request digest. Idempotent replay returns its receipt. A different payload with the same identity conflicts. Maintain an atomic active-attempt fence across workers, restarts and providers. Disable hidden SDK retries.

| State/event | Durable transition and allowed next action |
| --- | --- |
| Prepared, candidate denied before send | Record exclusion. Select next unvisited eligible candidate, or stop. Revalidate grants, cost and disclosure each time. |
| Candidate admitted | Pin policy, endpoint, pricing and source revisions. Reserve quota and any money atomically. If authority or price changes before send, release only against proof of no send. |
| Reserved | Persist single-use send claim before network I/O. Commit fence before handing off. Only its holder may send once. |
| Terminal success | Persist terminal receipt and verified usage once. Settle reservation and return result. Replays read it. |
| Definitive rejection | Advance only if authoritative evidence proves no execution, no disclosure conflict and no charge or allowance consumption. A status code alone is insufficient. Release verified unused reservation. |
| Timeout, ambiguous 429, disconnect, partial stream, crash after claim or missing terminal usage | Mark unknown, retain reservation and stop all retries/fallback. Reconcile same intent and attempt against authoritative provider/billing evidence. If unavailable, retain fence and escalate to accounting owner. |
| Known execution with failed output | Record terminal failure, reconcile charge, stop. Revocation fences further sends/output and reuse. Already transmitted data and consumed usage remain external. |

Calculate the upper bound in integer USD micros with rounding up from a current price revision for the exact endpoint/model/payer. Bound serialized input and enforced output, all billable token categories, fixed fees and multiplicities. Refuse unbounded tools, unverifiable pricing or unenforceable maxima. In a single transaction check per-request maximum and UTC billing-month capacity against settled plus outstanding holds, then reserve worst-case cost. Key holds by payer, owner, accounting period and attempt. Anchor the period to the provider billing rule and deny if the period cannot be determined. Carry unresolved exposure through rollover without resetting the fence. Settle exactly once using verified actual usage and release only the proven difference. Unexpected excess freezes that account and triggers investigation. Provider invoice behavior and hard-cap enforcement require independent [acceptance](delivery-and-acceptance.md).

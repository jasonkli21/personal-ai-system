# Inference route policy

**DRAFT / NOT DEPLOYED.** This policy describes future route eligibility and billing requirements. Current implementation status is in [current state](../current-state.md). The production factory is not proof that an external free provider is available or authorized.

## Current behavior and default

The automatic `RoutingDecisionService.route()` currently accepts only automatic `STRICT_FREE` requests. The normal inference factory does not admit `explicit_paid`; SIWC uses a separately gated local bridge. Automatic subscription and paid route composition is future work and remains disabled. It must extend the same canonical endpoint registry, authorization, reservation/usage ledger, replay and dispatch lifecycle. Do not add a second router, bypass cost mode, or reclassify subscription/paid routes as free.

New owner policy is `free_only`. It opts into neither paid calls nor subscription allowance use. Routes are ordered user preferences, not provider permission. Eligibility is the intersection of immutable system/operator/provider rules, exact owner grant and recipient, current task capability/quality, account/price evidence and the app's narrowing request. Apps can narrow but never widen. A subscription-first order requires an explicit owner edit after that route is admitted.

If no verified free route exists, stop with an actionable, content-free `no_authorized_external_inference_route` state and zero provider sends. Distinguish these states:

| State | Meaning and behavior |
| --- | --- |
| `free_available` | At least one exact free endpoint is currently verified and eligible; normal strict-free selection may continue |
| `free_unverified` | A candidate lacks current evidence; do not call it |
| `free_exhausted` | Verified free capacity is unavailable/exhausted; stop or try another verified free route only |
| `offline_fake_test_only` | Synthetic local response for tests; never describe or account it as external inference |

Quota exhaustion does not trigger paid or plan fallback. A new account makes zero paid and subscription calls by default.

## Owner policy shape

The following is a complete example of a future custom policy. It is not accepted by the current factory. Null values are explicit denial. `models` and `recipients` are additional restrictions and cannot expand the exact endpoint consent.

```json
{
  "schema_version": "inference-policy-v1",
  "mode": "free_only",
  "routes": ["free_api"],
  "free": {"endpoints": ["free-endpoint-a"], "models": ["free-model-a"]},
  "plan": null,
  "paid": null,
  "recipients": ["travel-demo"],
  "background_use": null,
  "owner_monthly_cap_micros": null
}
```

Future paid consent is exact and per approved endpoint. This example illustrates the required binding; it does not enable paid routing:

```json
{
  "schema_version": "inference-policy-v1",
  "mode": "explicit_paid",
  "routes": ["paid_api"],
  "free": null,
  "plan": null,
  "paid": {
    "endpoint_profile_id": "provider-a-prod",
    "profile_version": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "endpoint": "https://api.provider.example/v1",
    "model": "model-a-2026-10-01",
    "payer": "owner-a-provider-account-1",
    "account": "acct-opaque-1",
    "recipients": ["travel-demo"],
    "allowed_data_use": "inference_only",
    "max_cost_micros_per_call": 10000,
    "owner_monthly_cap_micros": 500000,
    "currency": "USD",
    "price_revision": "price-v4"
  },
  "recipients": ["travel-demo"],
  "background_use": null,
  "owner_monthly_cap_micros": 500000
}
```

Exact endpoint profile/version, endpoint, model, payer, account, recipient and price revision must match at dispatch. Price or account drift, unknown maximum cost, missing consent or data-use mismatch denies before send. A future schema may support a bounded list of separately approved endpoint consents; no wildcard or model substitution is allowed. Matching consent is necessary but not sufficient: operator admission, a hard enforceable cap, atomic holds and reconciled dispatch are also required.

## SIWC eligibility is distinct from a preference

Three independent records must not be collapsed into a `plan_only` boolean:

1. **Owner preference:** this owner asks to use an eligible connected-app plan route for the exact app, operation and host, with separate explicit background consent.
2. **Provider-observed account/workspace/app evidence:** current account, workspace, model, usage state and whether included allowance can be exhausted without credits or another charge. Record evidence source, observation time, expiry and approver. Unknown or unobservable credit controls deny the route.
3. **Distribution and host eligibility:** verified connected-app/program approval and user control of the runtime and persistent credentials under current provider terms. A plan name or local byte/time limit is not evidence of no incremental spend or provider-side hard usage cap.

SIWC use must be user-controlled, for the authenticated user and connected application, never pooled. No charge or paid-upgrade prerequisite may gate eligible plan access. Credits and automatic purchases are separate charge paths. If zero incremental charge cannot be established, deny the candidate. See the [SIWC Terms](https://openai.com/policies/sign-in-with-chatgpt-terms/), [plan usage and credit controls](https://help.openai.com/en/articles/20001542-using-your-chatgpt-plan-in-other-apps-and-sites), and current [provider limitations](https://developers.openai.com/siwc/token-sharing-open-source/preview-limitations). Unsupported provider fields such as `max_output_tokens` cannot be replaced by local truncation claims.

The local SIWC distribution is `BLOCKED_UNVERIFIED` pending exact app/user/workspace/host, program eligibility, credit settings, consent, serializer and terminal usage evidence. Generic PAS-managed multi-app execution is `BLOCKED_PENDING_APPROVAL` pending written authorization for that exact topology. No SIWC credentials belong on PAS centrally managed shared hosts.

## Holds, billing periods and dispatch lifecycle

Future paid calls must fit **both** independent limits:

- Owner budget: UTC calendar-month total across approved apps and payer accounts.
- Provider exposure: the specific payer account's actual provider billing period and its limit.

Both include committed spend, unsettled reservations and unknown sends from prior periods. If either billing calendar, enforced maximum, price, or account mapping is unavailable, paid dispatch denies. A promised hard cap requires evidence that the upstream charge cannot exceed the held maximum; a ledger alone cannot enforce unknown provider behavior. Keep USD micros and exact price revision pinned.

Lifecycle: `prepared → eligible/reserved → durable send claim → terminal` or `unknown`. A timeout, partial stream, disconnect, ambiguous 429, crash after claim, or lost receipt is unknown and remains pending reconciliation. Only authoritative proof of non-execution before send may release a hold and allow re-selection. No hidden SDK retry; unknown never falls back. Plan allowance records are distinct from the monetary ledger. Restore retains old holds, unknown-send fences and revocation epochs until independently reconciled.

## Candidate and accounting boundary

The future selection seam may produce an ordered set of eligible candidates for the existing router to evaluate. It must not itself authorize, reserve, dispatch, or spend. Each candidate is tagged with its immutable route class, exact model/profile, recipient, policy version, payer, evidence expiry and account state. The existing canonical endpoint registry, permission checks, atomic quota reservations, replay/idempotency and dispatch coordinator remain the single authorities. Current router behavior remains unchanged until a separate acceptance decision admits new execution modes.

There is no hidden fallback. On zero eligible candidates, expose only the content-free state and required next action. Never expose private provider/account details through user-facing errors.

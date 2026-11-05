# Proposed reasoning request v1

The [static validator](../../backend/src/personal_ai/reasoning/proposed_request.py)
accepts the object below as the future optional `reasoning` field. The
sketch has no HTTP, SDK or runtime registration.

```json
{
  "schema_version": "reasoning-request-v1",
  "effort": "auto",
  "strategy": "auto",
  "research": "if_authorized",
  "budget": {
    "max_model_calls": 4,
    "max_tool_calls": 2,
    "max_elapsed_seconds": 45,
    "max_input_tokens": 16000,
    "max_output_tokens": 2000,
    "max_concurrency": 1,
    "max_sources": 5,
    "max_provider_cost_usd": "0.00"
  }
}
```

Absence of the entire field preserves legacy direct/chat/research behavior.
Explicit null, unknown fields, unknown versions and enum values, boolean or
fractional counts, negative and out-of-range limits and noncanonical money
strings are invalid. Optional subfields default to `auto` effort and
strategy, `off` research and zero ceilings in this sketch. Zero allows zero
work in that dimension. The values in the example are request ceilings.
Only a versioned compatibility decision may change the meaning of omission.

| Field | Proposed semantics |
| --- | --- |
| `effort` | `auto`, `low`, `medium`, `high`, `max`. Work and quality preference. Vendor-native mapping needs evidence for the exact admitted model and accounting profile. |
| `strategy` | `auto` by default. Explicit catalog pins require a trusted experimental role, enabled profile and normal eligibility. An unauthorized pin yields policy denial. A permitted pin that fails eligibility can use an explicitly recorded safe fallback within the same scope or return unsupported. |
| `research` | `off` or `if_authorized`. A preference to use already allowed evidence when needed. The server resolves current grants. |
| `budget` | Integer caps for physical model attempts, tool calls, monotonic elapsed seconds, separate input/output tokens, simultaneous admitted operations and distinct source revisions. USD is a canonical decimal string with cents. The exact attempt cost estimate and settlement may have higher precision. |

The server binds actor, audience, app, workspace, purpose, original key and
policy from trusted context. Each effective limit is the minimum of the
request ceiling and verified user/app/workspace/operator ceilings, further
constrained by provider, quota, source, disclosure and tool policy.
Strict-free dispatch needs affirmative current account/operation proof.
Unknown pricing, rights or capability narrows or stops before dispatch.
Higher effort changes only feasible work allocation.

A future response extension carries `schema_version`, `requested_effort`,
`effective_effort`, bounded `narrowing_reasons` (capability, budget, policy,
quota, source, unavailable), chosen strategy ID/version, catalog version and
policy version. Effective effort can be absent when work is denied.
`status` is `complete`, `partial` or `unavailable`. `stop_reason` is
`sufficient`, `budget_exhausted`, `evidence_insufficient`, `policy_denied`,
`provider_unavailable`, `cancelled`, `uncertain_effect`, `internal_failure`
or `unsupported`. A partial result identifies missing requirements and
includes only supported, currently disclosable claims. An uncertain effect
uses the original intent to observe or reconcile the attempt.

Per-resource estimate and observed records distinguish attempted and settled
work, confidence (`estimated`, `observed`, `unknown`), and reservation state
(`not_reserved`, `reserved`, `settled`, `uncertain`). Unknown usage is null
and does not release an uncertain reservation. Evidence dependencies carry
opaque source, revision, authorization epoch, observation/freshness class and
citation references with server-bound scope. Recheck them before replay or
disclosure. An opaque continuation references original canonical intent.
Diagnostics exclude source bodies, private identities and hidden reasoning.
An incompatible field change requires a new schema version, explicit capability
negotiation and migration tests against existing clients before exposure.

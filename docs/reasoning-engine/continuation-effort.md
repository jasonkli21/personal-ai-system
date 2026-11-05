# Optional effort on automatic continuation

Send `reasoning` on `POST /v1/conversations/{id}/continue` with
`X-Reasoning-Observation: reasoning-observation-v1`. The backend defaults to
`REASONING_ENABLED=false`. Only local and test environments can opt in.
The [automatic continuation schema](../platform-independence/consumer-v1.openapi.json)
describes the request and negotiated terminal field.

```json
{
  "content": "Explain this argument in one paragraph.",
  "idempotency_key": "9b809a12-f67b-44f6-af81-efcb329ee5b8",
  "reasoning": {
    "schema_version": "reasoning-request-v1",
    "effort": "auto",
    "budget": {
      "max_model_calls": 1,
      "max_concurrency": 1,
      "max_elapsed_seconds": 10,
      "max_input_tokens": 4096,
      "max_output_tokens": 64
    }
  }
}
```

`auto` resolves to fixed `low`. Manual preferences rank `low < medium <
high < max`. The server applies its operator ceiling (default `low`) and
the endpoint's limit after authenticating the app and workspace. The same
direct policy applies to every admitted scope. No per-scope higher grant is
installed. All omitted budget dimensions are zero. The five work limits in
the example must be positive. The admitted envelope permits at most one
generation, one concurrent operation within this turn, separately admitted
counting, zero provider dollars, and zero optional sources or tools. The
existing local tokenizer reserves the full endpoint input ceiling per count,
so an opted-in local request must cover that ceiling even for short input.

The shared assembler receives only the current user message. Source
selectors, research and explicit strategy pins are unsupported. No summary
refresh or memory extraction runs. Direct chat, external-turn preparation,
regenerate and edit/retry retain their existing interfaces.

| Selected profile | Effort support |
| --- | --- |
| `offline_fake` | Synthetic E1 wire fixture, with exact `low` and `high` mappings. A gap or inadequate output bound may narrow to `low`. |
| `offline_fake_alt` | Plain `low`. |
| `local_llama` | Plain `low` through the existing private-socket admission and ledger, subject to the configured profile and its local limits. |
| Hosted, paid, connected and subscription profiles | Opt-in unavailable. Real native capabilities require exact installed proof. |

Successful negotiation echoes the version header. The terminal
`response.completed` or `response.error` can include a `reasoning` object
with the policy and catalog versions, requested and effective effort,
narrowing reasons, native-control disposition and resource observation.
`applied` means the exact synthetic control passed final-wire validation.
Provider acknowledgement and observed reasoning are separate and may be
unknown. Counts describe the current request. Synthetic generation has no
provider reservation or settlement. Reported local usage and estimated
synthetic usage are distinguished. The canonical usage ledger remains the
source of truth for unknown effects and reservations.

A policy denial before SSE uses the normal safe error envelope and a
bounded JSON observation in the response header. Validation, authentication
and original-key conflicts use the ordinary error contract. A completed
same-key replay rechecks disclosure and marks the observation as replayed.
The replay carries no reconstructed historical effective effort. If a
stream is interrupted, inspect the original key's canonical status.
Changed effort or budget conflicts on that key. User-only, failed and
uncertain opted-in continuations cannot issue a second attempt on that key.

The existing SDK continues to consume the ordinary response. Use the
negotiated HTTP contract for effort. Turning the flag off blocks new opt-in
work. Stop or drain active work before changing rollout configuration and
retain original keys and existing usage records for reconciliation.

[Compatibility and capability decision](2026-11-04-effort-contract-decision.md)

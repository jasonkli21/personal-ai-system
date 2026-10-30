# Inference

This package defines the provider-neutral generation, streaming, embedding, counting, attribution,
and preparation contracts used by services. Provider SDK and transport details stay behind adapters.

## Entry points and boundaries

- `__init__.py` and the contracts expose the shared inference interface.
- `litellm/` implements the pinned LiteLLM transport, request shaping, streaming, profiles, and attempt accounting.
- Product workflows depend on the neutral contracts; they should not import LiteLLM types.
- `personal_ai.llm.litellm` exposes the transport clients used by provider adapters.

Gateway and provider contract tests live in `backend/tests/test_litellm_gateway.py`, `backend/tests/test_llm_*.py`, and related usage tests. Offline fakes do not establish live provider compatibility.

## PI-3 explicit execution profiles

Normal API chat/context, research synthesis and the memory worker use
`execution.py`; the API caches one generation/count pair per request. This is a
closed installed factory catalog, not a router, plugin import path or public
provider-selection field. `AI_PROVIDER`/`AI_MODEL` still configure transport
settings; they no longer implicitly authorize the normal inference profile.

| Operator setting | Default / supported behavior |
| --- | --- |
| `INFERENCE_PROFILE` | `offline_fake`; also `offline_fake_alt`, `legacy_gemini`; Groq/Cloudflare selections deny pending approved exact counters |
| `INFERENCE_COST_MODE` | `offline_fake`; remote requires `strict_free`; `mostly_free_opt_in` and `explicit_paid` always deny because USD reservations/caps are absent |
| `INFERENCE_SUMMARY_PROFILE` | `disabled`; explicit same chat profile only |
| `INFERENCE_EXTRACTION_PROFILE` | `disabled`; explicit `legacy_gemini` with structured capability and exact schema approval |
| `INFERENCE_EMBEDDING_PROFILE` | `disabled`; reserved legacy selection remains unavailable pending an approved exact embedding-input counter |

Offline fakes need no credentials, examples or provider ledger/database. They
report distinct fake identities, exact local JSON-byte input units (serializer
`pi3-local-json-bytes-v1`), and estimated synthetic output usage. These units are
not a token bound for any remote model. Fake research retains its existing
literal-excerpt synthesizer and estimated local counter.

For explicit legacy generation/count/summary/extraction, set `AI_PROVIDER=gemini`,
`INFERENCE_PROFILE=legacy_gemini`, `INFERENCE_COST_MODE=strict_free` and the existing
Gemini account/credential scope, free-tier, privacy, quota, counter, context/output
and structured-schema preflight facts. Configure the **existing**
`INFERENCE_ADDITIONAL_ENDPOINT_PROFILES` overlay to supply a complete higher-version
profile with a finite, aware `strict_free_attestation.verified_at` and `valid_until`.
Boolean flags alone do not establish freshness. Privacy must be explicitly approved
even for public input. Schema approvals use `sha256:` plus the hash of canonical
sorted compact JSON (`execution.schema_identity`). The configured profile must
match the actual fixed transport and durable registry exactly. No credentials
belong in profile JSON or evidence references.

Each remote counter/summary/generation/extraction operation uses canonical
EndpointRegistry admission before disclosure and revalidation immediately before
P19 physical-attempt reservation. Count operations reserve the approved input
ceiling; generation reserves its exact prepared count plus bounded output.
The bounded async transport also converts connection/protocol errors to its own
safe fault before LiteLLM can create an unbounded retry client; SDK retry flags
alone did not disable that behavior. Gateway tests detect replacement clients
and the OS/Python fence verifies zero follow-up DNS/connect attempts.
Size request-level token/attempt limits for multiple separately accounted counts;
quota exhaustion denies, without a replacement endpoint or retry. Ledger usage
retains its existing reported/estimated vocabulary. Source changes between
counting and dispatch are rechecked by the owning chat guard; this is not an
atomic deployed source lease or proof that an in-flight request can be recalled.

Normal composition does not dispatch new memory embeddings. The original direct
Gemini embedder and persisted space (`google_genai`, configured model/dimensions,
L2, RETRIEVAL_DOCUMENT/RETRIEVAL_QUERY, v1) remain unchanged; existing compatibility
and mismatch checks still own persisted vectors. No fake vectors or re-embedding
fallback is installed. Legacy vector retrieval/extraction requiring an embedding
will be unavailable through normal composition; schema-3 lexical selection is
independent. Existing memory flags remain default-off.

Direct adapter constructors remain for compatibility tests and explicitly gated
provider evaluation/cascade paths. They are not normal workflow composition and
do not inherit PI-3 admission merely by existing. Manual/connected external turns
retain their separate default-off explicit contracts. No adaptive/shadow promotion.

`make pi3-check` runs an inspected offline suite in a macOS OS network sandbox
(including native TCP/IPv6/Unix probes) plus the Python audit fence. Other operating
systems need an equivalent OS fence; this target fails rather than silently
claiming native isolation. `make pi2-check` separately exercises installed artifacts
and loopback HTTP; that legacy target's Python fence is not a native sandbox.

Rollback: stop/drain new sends; disable the selected profile or select a separately
approved compatible legacy endpoint. Reconcile original continuation/task keys;
retain unknown reservations, messages/branches, receipts, source fences and vector
identities. Never reinterpret an uncertain send as a reason to generate a new key.

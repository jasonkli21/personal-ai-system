# Private local inference and task evaluation

PAS has one optional development-only llama.cpp profile. It uses native
`/tokenize` and `/completion` over a private Unix socket. The integer token
sequence produced during final input preparation is the sequence submitted to
generation, so the request needs neither estimated model tokens nor an
additional chat-template pass. Chat still uses the normal application policy,
context assembler, source rechecks, and canonical usage ledger. [llama.cpp server contract](https://github.com/ggml-org/llama.cpp/blob/master/tools/server/README.md)

| Capability | Contract |
| --- | --- |
| Identity | Exact operator-selected llama.cpp build identity and SHA-256 of one GGUF. The runtime checks the server-reported build, model alias, model filename, and slot/context limits before each count or generation. |
| Serialization and tokenizer | Role/content JSON lines, with special-token parsing disabled during native tokenization. Generation accepts only the final prepared token IDs from that socket. |
| Generation and streaming | Bounded text generation. Chat receives one validated buffered delta followed by its terminal event. Native time-to-first-token is unavailable in this mode. |
| Limits | 4,096 context tokens, at most 512 output tokens, 256 KiB per request or response, at most 120 seconds per model operation and the tighter caller deadline. One in-flight operation per PAS process and one server slot. |
| Accounting | Separate count and generation reservations. Before `/tokenize`, the full serialized request is limited to 4,096 bytes. P19 reserves the 4,096-token ceiling plus the exact `tokenizer_request_bytes` work unit. Tokenizer results above the model context are rejected. Generation reserves exact prepared input and bounded output. The canonical ledger enforces request budgets and a configured 60-call minute bucket. Missing usage stays unknown. |
| Disclosure | Development only. The existing app policy still governs disclosures up to the endpoint's sensitive classification ceiling. The experimental corpus uses synthetic inputs even where policy classifies history as sensitive. |
| Cost | `LOCAL_NO_CHARGE` describes the operator-owned endpoint contract. Hardware and power costs are unmeasured. Hosted billing claims require separate account and operation evidence. |
| Unsupported | Structured generation, upstream SSE, embeddings, hosted fallback, tools, and subscription execution. |

## Operator setup

Use an independently verified build that implements Unix sockets and the native
API above. Pin the build and verify the GGUF bytes yourself before launch.
This checkout has no hardware-verified model profile. Record the model name,
hash, quantization, RAM, disk and observed latency when validating a profile.
Core installation does not need llama.cpp or download a model.

1. Prepare the repository's [local persistence stack](../../stabilization/OPERATIONS.md)
   and apply migrations, including `033_local_inference_accounting.sql`. Use
   disposable local stores and synthetic chat for the experiment.
2. Create a short, canonical, absolute directory owned by the PAS user with
   mode `0700`. On macOS, use the canonical `/private/tmp` spelling for a
   directory there. Use the same UID for the model server. Name the verified
   GGUF `sha256-<hex-digest>.gguf` and give the server the same alias without
   the extension.
3. Start the server under an OS egress fence. The example assumes the
   operator has already set `verified_model`, `verified_digest`, and
   `private_socket` to the reviewed local file, its digest, and socket path.

   ```sh
   llama-server --model "$verified_model" --alias "sha256-$verified_digest" \
     --host "$private_socket" --ctx-size 4096 --parallel 1 \
     --no-context-shift --no-cache-prompt --no-slots --no-webui
   ```

4. In the backend's untracked operator environment use the following values,
   replacing the illustrative path, digest and build. Export the variables
   into the shell for a benchmark launched from the repo root.

   ```dotenv
   APP_ENVIRONMENT=local
   AUTH_MODE=development
   AI_PROVIDER=fake
   AI_MODEL=unused
   INFERENCE_PROFILE=local_llama
   INFERENCE_COST_MODE=local_only
   LOCAL_LLAMA_SOCKET=/private/tmp/pas-private/llama.sock
   LOCAL_LLAMA_MODEL_SHA256=<verified lowercase hex digest>
   LOCAL_LLAMA_BUILD=<build_info reported by the approved server>
   LOCAL_LLAMA_APPROVAL=local:synthetic-task-pilot
   MAX_CONTEXT_TOKENS=4096
   MAX_RESPONSE_TOKENS=128
   SUMMARY_TRIGGER_TOKENS=2048
   ```

   Launch the normal development API and use the normal chat endpoint, or run
   one explicitly selected synthetic development case as described below.

The client uses a Unix-socket-only transport with a fixed HTTP authority,
no environment proxies, no redirects, and no transport retries. It checks
socket ownership and identity before sending and rejects replacement between
preparation and generation. The private directory and operator-approved
process are the trust boundary. Server-reported identity is a consistency
check. A process running as the same user, root, or an untrusted server binary
can defeat those checks. A native fence on the server is required to establish
server egress behavior. Keep tunneling, model routing, request logging,
remote tools and model download disabled. A local recheck and a ledger
reservation leave a small race before physical send. A timeout or disconnect
can leave server computation uncertain.

## Evaluation and trace

```sh
make real-task-eval
make real-task-eval REAL_TASK_FLAGS='--trace synthetic-trace.jsonl'
make real-task-eval REAL_TASK_FLAGS='--local-case research-duration --trace local-trace.jsonl'
```

The first two commands run the pinned 12-case synthetic E1 corpus through normal chat
with an offline fake. E1 reports coverage and safety canary integrity separately;
natural-language task quality is `not_applicable_fake`. The local command explicitly runs one positive development
case against the configured server and durable ledger. It uses three paired
arms with the same prompt, runtime, budget, and no tools. Direct uses no
historical evidence, selected admits the current evidence card, and eligible
also allows the superseded card. The built-in literal rubric checks expected
facts and citations and reports forbidden markers separately. Scope negatives
use canonical active-branch denial. The corpus also includes injection probes
and a tagged holdout per family. The holdout is public. These history fixtures
exercise context selection and are separate from installed external retrieval
or a live research agent.

The CLI reports elapsed time, canonical usage observations where available,
context-selection outcomes, and sanitized per-arm results. Capture cold start,
idle CPU and RAM, disk/model footprint and host configuration separately for
real-model acceptance. The local mode labels results as an E2 attempt. Native
fencing, hardware evidence and independent review are separate evidence.

Trace capture is opt-in and process-local. The recorder drops oldest events
at its fixed limit and reports drops. It pseudonymizes request, task, run,
endpoint and source references with a run-local key, retaining canonical
invocation and attempt UUIDs. It excludes message bodies, token IDs, credentials,
provider headers, and response bodies. The CLI writes a new `0600` JSONL
basename in its working directory with the commit, configuration digest, run ID
and a human-readable summary. Use a clean revision for reproducible receipts.
The trace can be discarded after review under the operator's local retention
policy. Durable usage remains in the canonical ledger.

## Hosted status and rollback

Groq and Cloudflare remain `BLOCKED_UNVERIFIED`. Existing explicit legacy
Gemini strict-free admission still requires its current credential-scoped
attestation, policy, exact counter and quota evidence. This candidate adds
no hosted provider dispatch or verification calls.

To roll back, stop and drain new sends, remove the local selection and approval,
and restart with `offline_fake`. Reconcile existing attempts before retrying any
uncertain original intent. Retain canonical usage records and source grants.
Stop the separate model process and remove disposable local trace files under
the operator's retention policy.

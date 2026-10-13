# Personal AI System

A personal AI platform and research environment focused on the systems around large language models: streaming chat, context management, long-term memory, evidence-grounded research, decision support, domain integrations, evaluation, and application-facing AI capabilities.

The project is intentionally not a model-training or local-model-hosting project. It uses hosted model/provider APIs behind replaceable interfaces and concentrates on the surrounding architecture: memory, retrieval, evidence, routing, constraints, persistence, observability, and cost-aware orchestration.

For concise implementation status and open verification gates, see [docs/current-state.md](docs/current-state.md). Use the [documentation router](docs/README.md) to find task-specific plans, contracts, and evidence.

## What it does

The system provides reusable AI capabilities that can be used directly through its web UI or consumed by domain applications such as travel and shopping.

Core capabilities include:

- streamed conversational chat;
- persistent conversation history;
- token-budgeted context building across conversation, memory, and deterministically planned eligible sources, with provenance and sensitivity manifests;
- an owner-managed AI profile with explicit per-field application sharing;
- a versioned federation grant API and shared broker with gated Travel, Finance, and Health exports; destination-product acceptance remains open;
- attributable long-term memory with retrieval;
- bounded memory retrieval/compaction and lifecycle experiments, with original provenance and source revalidation;
- source-grounded research with persisted evidence;
- iterative research with explicit budgets and recovery;
- canonical research entities and evidence-backed claims;
- deterministic hard constraints and explainable ranking;
- decision snapshots with source attribution;
- travel and shopping comparison modules;
- itinerary-proposal and booking-extraction capability boundaries;
- a typed, confirmed mutation framework with Postgres reservations and domain-owned reconciliation; current domain write adapters remain unavailable;
- owner-scoped application/workspace identity foundations;
- bounded provider-attempt accounting with a default-off owner-scoped developer summary;
- account export/deletion workflow foundations;
- a default-off private artifact tier for compressed traces, evaluation batches and frozen exports;
- synthetic evaluation suites for memory, context, research, decisions, and domain behavior.

## Design principles

- **The model provider is replaceable.**
- **Memory and external evidence are different data classes.**
- **Current evidence can override stale memory.**
- **Hard constraints are enforced by application code, not delegated to a model.**
- **Research is bounded by time, token, source, and cost budgets.**
- **Domain applications keep authority over their own data and business rules.**
- **Experiments require measurable evaluation before promotion.**
- **Cloud resources should scale to zero or stay disabled when not needed.**

## Architecture

```text
                         Browser
                            |
                            v
                +-----------------------+
                | Next.js / React       |
                | public web service    |
                +-----------+-----------+
                            |
                     server-side proxy
                            |
                            v
                +-----------------------+
                | private FastAPI API   |
                |                       |
                | chat + context        |
                | endpoint registry     |
                | usage ledger          |
                | memory + research     |
                | evidence + decisions  |
                | domain capabilities   |
                +----+-------------+----+
                     |             |
                     |             +-------> hosted LLM/search providers
                     +-------> Neon Postgres + pgvector
                     +-------> DynamoDB runtime state
                     +-------> private GCS artifact bodies (opt-in)
                     |
                     +-------> Pub/Sub ---> private Cloud Run worker
```

Domain applications integrate over explicit HTTP contracts rather than importing internal packages.

The internal endpoint registry records provider, model, account, credential-scope,
privacy, capability, count-compatibility, and quota-authority facts, and can
produce strict-free candidates with deterministic rejection reasons. The internal routing
coordinator persists compact decisions and requires atomic usage reservation plus
a current, single-use dispatch claim; see the [Phase 18–21 refactor](docs/personal-ai-chapter-2/phase-18-21-architecture-refactor-implementation-plan.md). Current
application workflows remain Gemini-only behind Phase 15 membership and revocation
acceptance. An internal [bounded task cascade](docs/personal-ai-chapter-2/phase-24-implementation-guide.md)
validates buffered output and accounts for every count/generation attempt; direct
routing remains the default because the synthetic baseline did not justify adoption.

Provider sends have a separate usage ledger for physical attempts, quota
reservations, endpoint health, and bounded owner-attributed summaries. Its
developer inspection route is disabled by default; quota values without
authoritative observations remain unknown.

The optional artifact tier stores compact references in Postgres and immutable
compressed bodies in private GCS, with bounded retention, storage budgets and
account deletion fences. Both backend and browser proxy gates default off;
the worker still reconciles retained bodies while new writes are disabled. Store
rotation waits until old references and recent deletion tombstones are drained;
exports fail explicitly if live artifact bodies exist while storage is disabled.
Cloud/IAM/free-tier acceptance remains unverified. See the [Phase 20 guide](docs/personal-ai-chapter-2/phase-20-implementation-guide.md) for setup and prerequisite gates.

## Repository layout

```text
.
├── backend/
│   ├── src/personal_ai/
│   │   ├── agents/          # research orchestration
│   │   ├── auth/            # identity and owner boundaries
│   │   ├── context/         # token-budgeted context assembly
│   │   ├── decisions/       # evidence-backed decision contracts
│   │   ├── domains/         # thin travel/shopping capabilities
│   │   ├── entities/        # chat and canonical research entities
│   │   ├── evidence/        # attributable observations
│   │   ├── evaluation/      # evaluators, grouped fixtures, and schemas
│   │   ├── llm/             # provider-neutral inference contracts and adapters
│   │   ├── memory/          # durable memory and lifecycle package
│   │   ├── ranking/         # deterministic ranking/constraints
│   │   ├── routing/         # endpoint profiles and strict-free admission
│   │   ├── search/          # search adapters and pipeline
│   │   ├── usage/           # provider invocation and attempt accounting contracts
│   │   ├── services/        # chat/application orchestration
│   │   ├── storage/         # repository contracts and persistence primitives
│   │   └── persistence/     # concrete Postgres and DynamoDB adapter packages
│   └── tests/
├── frontend/
│   ├── src/                 # Next.js application and API proxies
│   │   ├── features/chat/continuation-sidecar/ # sidecar UI, state, and bridge client
│   │   └── lib/api/         # shared client and feature endpoint/DTO groups
│   └── tests/
├── infrastructure/          # local/GCP and semantically grouped cloud assets
├── experiments/             # isolated research experiments
├── docs/                    # architecture, ADRs, runbooks, evaluations
├── docker-compose.persistence.yml
└── Makefile
```

## Tech stack

### Web

- Next.js 15
- React 19
- TypeScript
- pnpm 11.19.0

### API / worker

- Python 3.11+
- FastAPI
- Uvicorn
- Pinned LiteLLM Python SDK beneath Personal AI's neutral inference gateway for Gemini, Groq, and Workers AI
- psycopg and boto3 adapters behind repository contracts

### Cloud

- Google Cloud Run
- Neon Postgres with pgvector for query-rich durable records, embeddings, and the canonical provider usage ledger
- DynamoDB for conversations, messages, summaries, runtime guards, jobs, and scoped provider usage events
- Pub/Sub
- AWS STS web-identity federation from Cloud Run for DynamoDB access
- Secret Manager
- Artifact Registry
- Cloud Build

## Local setup

### Prerequisites

- Python 3.11+; Python 3.12 is used by the containerized runtime
- `uv` 0.11.13
- Node.js 22
- pnpm 11.19.0
- Docker Compose for local Postgres/pgvector and DynamoDB Local

### 1. Clone the repository

```bash
git clone https://github.com/jasonkli21/personal-ai-system.git
cd personal-ai-system
```

### 2. Install backend dependencies

```bash
cd backend

uv sync --locked --only-group build --no-install-project
uv sync --locked --extra dev --group build --no-build-isolation

cd ..
source backend/.venv/bin/activate
```

### 3. Install frontend dependencies

```bash
cd frontend
pnpm install --frozen-lockfile
cd ..
```

### 4. Configure local environment files

```bash
cp backend/.env.example backend/.env
cp frontend/.env.local.example frontend/.env.local
```

The default local configuration keeps optional research, memory-lifecycle, decision, domain, export, deletion, and provider-backed features disabled.

Automated tests use fakes and do not require model credentials or GCP access.

### 5. Start local persistence

The application uses the local Postgres and DynamoDB endpoints from
`backend/.env.example`. Start and initialize them before using persistence-backed
application flows:

```bash
make persistence-up
make persistence-bootstrap
```

Stop the containers with `make persistence-down`. `make persistence-clean`
also deletes their local volumes.

### 6. Start the application

In separate terminals:

```bash
make run-backend
```

```bash
make run-frontend
```

Open:

```text
http://localhost:3000
```

The frontend server-side proxy defaults to:

```env
API_BASE_URL=http://localhost:8000
```

## Model and provider configuration

The default model configuration is Gemini:

```env
AI_PROVIDER=gemini
AI_MODEL=gemini-2.5-flash
AI_API_KEY=
```

Leave `AI_API_KEY` empty for offline/fake-backed testing.

For a real streamed model response, set the key only in the untracked local environment file or Secret Manager in cloud deployments.

Gemini remains the only provider wired into automatic chat, research, and memory workflows. The pinned LiteLLM 1.102.1 Python SDK runs below Personal AI's neutral inference gateway; Personal AI still selects providers and credentials, and LiteLLM Proxy, Router, and cross-provider fallback are not used. Groq and Cloudflare Workers AI support bounded generation and model-gated structured output, but their live gates default off and require account/model-specific free-tier, privacy, and compatibility preflight evidence. They do not provide authoritative endpoint token counting, which current workflows require before dispatch, so enabling their adapter flags alone does not switch application traffic.

The Phase 25.3 continuation sidecar is implemented, but manual external disclosure and connected dispatch are unavailable by default. `EXTERNAL_TURN_ACCEPTANCE_ENABLED` is an explicit, default-off gate; keep it disabled until Phase 15 derived-source/revocation authority and Phase 25.2 DynamoDB transaction/race/restart acceptance pass. The shared planner, local estimated-count preparation runtime, bounded preview, idempotency-key reconciliation, scope propagation, and transient shared-chat streaming seams are implemented and covered locally. Automatic Personal AI continuation remains available. Connected execution additionally requires an approved explicit Phase 18 profile and dispatch signer. A separately started user-local ChatGPT bridge owns reusable credentials, account-specific discovery, and restricted Responses streaming. Live connected execution remains unverified pending distribution approval, enforceable plan-only billing, real OAuth/Responses compatibility, and native browser/loopback acceptance. See the [Phase 25.3 guide](docs/personal-ai-chapter-2/phase-25-3-implementation-guide.md) and [evidence](docs/personal-ai-chapter-2/phase-25-3-implementation-evidence.md). Installation, pairing, and open gates are documented in the [Phase 25.1 guide](docs/personal-ai-chapter-2/phase-25-1-implementation-guide.md).

Phase 26 adds an optional, read-only Travel context integration through the shared planner, context assembler, and sidecar. The Travel API remains authoritative for trips, days, places, bookings, and writes; the integration has independent default-off gates and supports preview, narrowing, Copy, and draft insertion. See the [Phase 26 plan](docs/personal-ai-chapter-2/personal-ai-next-scope-detailed-implementation-plans/plans/phase-26-implementation-plan.md) and [implementation evidence](docs/personal-ai-chapter-2/phase-26-implementation-evidence.md).

Phase 28 adds a separate, read-only Finance context contract through the shared planner, context assembler, and permission-revalidation seams. Both Finance and Personal AI gates default off. Automatic chat routing and the Finance sidecar remain unavailable pending Phase 15/21 prerequisites, an accepted Finance embed contract, and deployed identity/provider privacy checks; see the [Phase 28 evidence](docs/personal-ai-chapter-2/phase-28-implementation-evidence.md).

Phase 29 adds a separate, read-only Health `health-context-read-v1` contract and typed providers through those same shared seams. Its broad context-read gate remains off and unavailable to Personal AI because that contract still requires a Firebase user token. Phase 30 adds a separate, default-off Health federation export using a request-bound, short-lived signed Google-user delegation; both services retain independent consent and owner checks. Shopping still lacks a trusted user-bound destination host, so Phase 30 remains open. See the [Phase 29 evidence](docs/personal-ai-chapter-2/phase-29-implementation-evidence.md) and the [Phase 30/31 follow-up evidence](docs/personal-ai-chapter-2/phase-30-31-follow-up-review-implementation-evidence-2026-10-12.md).

Connected execution requires an operator-provisioned Ed25519 signer that matches the public key pinned in the local bridge's protected compatibility configuration. Set `EXTERNAL_DISPATCH_GRANT_ISSUER`, `EXTERNAL_DISPATCH_GRANT_KEY_ID`, and `EXTERNAL_DISPATCH_GRANT_PRIVATE_KEY` only through a protected local environment file or Secret Manager. The key is never sent to the browser. Manual copy/import does not need this signer or the ChatGPT bridge.

Research, memory, decision, travel, shopping, proposal, and extraction capabilities each have independent gates. Enable only the specific path you are testing and preserve its provider/storage policy controls.

## Quality and evaluation

Common checks from the repository root:

```bash
make backend-test
make backend-lint
make frontend-test
make frontend-lint
make frontend-typecheck
make backend-build
make frontend-build
```

The repository also includes deterministic evaluation suites:

```bash
make context-eval
make context-plan-eval
make planning-eval
make memory-eval
make memory-lifecycle-eval
make research-eval
make retrieval-eval
make iterative-research-eval
make decision-eval
make domain-eval
```

Phase 32 adds a frozen context-planning benchmark, bounded proposal validation,
and compact diagnostics through the shared assembler. Its current decision is
non-promotion: planning remains deterministic, with no planner inference calls.
See the [implementation report](docs/personal-ai-chapter-2/phase-32-implementation-report.md)
for measured limitations and verification.

These evaluations are designed to make changes to memory, retrieval, ranking, context assembly, and research behavior measurable rather than purely subjective.

Phase 33 research retrieval keeps the literal snippet strategy as its default.
The bounded qualifier, two-query expansion, and compact extractive packing probes
require `RESEARCH_RETRIEVAL_EXPERIMENTS_ENABLED=true`; no coverage is promoted.
`RESEARCH_QUERY_STRATEGY` selects `literal-snippet-v1`, `qualifier-v1`, or
`expansion-v1`; `RESEARCH_PACKING_STRATEGY` selects `literal-extractive-v1` or
`compact-extractive-v1`. Source rights, source-domain bounds, mandatory publication
freshness, Phase 19 admission, and context budgets still apply. See the
[Phase 33 report](docs/personal-ai-chapter-2/phase-33-implementation-report.md).

Phase 35 adds a default-off adaptive routing shadow behind the existing strategy
seam. It records preferences over admitted strict-free candidates and preserves
the deterministic visible route. The canonical API dependency is available but no
user workflow consumes it while Phase 15 authorization/revocation and transport
acceptance remain open. The synthetic corpus does not support promotion; learned
ranking and online adaptation are deferred. Run
`make adaptive-routing-eval`; see the [Phase 35 report](docs/personal-ai-chapter-2/phase-35-implementation-report.md)
and [experiment contract](experiments/ranking/README.md).

## Cloud deployment

The deployed topology uses Cloud Run for the web/API/worker, Neon Postgres and
DynamoDB for durable state, and authenticated Pub/Sub delivery for bounded
memory lifecycle jobs.

```text
Browser
  |
  v
Cloud Run: personal-ai-web
  |
  | service identity + end-user identity
  v
Cloud Run: personal-ai-api
  |
  +------> Neon Postgres (TLS transaction pooler)
  |
  +------> DynamoDB (Google identity token exchanged through AWS STS)
  |
  +------> hosted model/search providers
  |
  +------> Pub/Sub ---> Cloud Run: personal-ai-worker
```

### Prerequisites

Provision or prepare:

1. a GCP project with billing enabled;
2. a Google OAuth web client;
3. a Gemini API key stored in Secret Manager;
4. a reviewed staging domain/origin;
5. a provisioned Neon database and runtime DSN stored in Secret Manager;
6. a provisioned DynamoDB table/GSI and an AWS role whose OIDC trust matches the
   Cloud Run service identity and configured audience;
7. appropriate Cloud Run, Pub/Sub, Secret Manager, IAM, and Artifact Registry permissions.

### Store the model key

Example:

```bash
printf '%s' "$GEMINI_API_KEY" | \
  gcloud secrets create personal-ai-gemini-api-key \
  --replication-policy=automatic \
  --data-file=-
```

Do not place the key in repository files or command-line arguments.

### Deploy

Provision Neon and DynamoDB using the reviewed Phase 10 schema and resource
templates before deploying. The deploy script does not create or migrate those
stores. Set `NEON_RUNTIME_DSN_SECRET_NAME`,
`NEON_RUNTIME_DSN_SECRET_VERSION`, `DYNAMODB_ROLE_ARN`, and
`DYNAMODB_IDENTITY_TOKEN_AUDIENCE` in the deployment shell. The Neon DSN secret
must contain the TLS transaction-pooler DSN. Then deploy from a clean reviewed
commit:

```bash
chmod +x infrastructure/gcp/deploy.sh

infrastructure/gcp/deploy.sh \
  staging \
  YOUR_STAGING_PROJECT \
  us-central1 \
  personal-ai-gemini-api-key \
  gemini-2.5-flash \
  YOUR_GOOGLE_OAUTH_WEB_CLIENT_ID.apps.googleusercontent.com \
  owner@example.com \
  https://personal.example \
  2
```

The deployment script:

- enables required GCP APIs;
- builds backend/frontend images;
- resolves immutable image digests;
- deploys separate web, API, and worker services;
- creates scoped service identities;
- configures authenticated Pub/Sub delivery;
- injects the model key and Neon DSN from explicit Secret Manager versions;
- configures the API/worker to use the pre-provisioned Neon and DynamoDB resources.

Production deployment requires the repository's explicit production acknowledgement and should be rehearsed in a synthetic staging project first.

## Cost and free-tier considerations

The architecture is intentionally compatible with low-idle-cost personal use:

- Cloud Run uses request-based billing and can scale to zero;
- Neon and provisioned DynamoDB are durable stores with distinct storage owners;
- Pub/Sub is used only for concrete durable async work;
- optional providers remain disabled until needed;
- provider usage is bounded by application-level request/token/call limits.

This is **free-tier-aware**, not a guarantee of zero cost. Database compute/storage,
DynamoDB capacity and requests, cross-cloud egress, external providers, and model
usage can incur charges. Confirm current account-specific allowances before
deploying; local tests and static configuration checks do not establish strict-$0
eligibility.

## Security notes

- local `AUTH_MODE=development` is a development convenience, not production authentication;
- deployed API and worker services use separate service identities;
- the API validates end-user identity independently of Cloud Run service identity;
- production/staging origins are explicit allowlists;
- provider credentials belong in Secret Manager;
- research/provider outputs are bounded and validated;
- persistent memory retains attribution/provenance;
- external evidence has freshness/retention semantics separate from memory;
- account export/deletion controls remain gated operational capabilities.

Do not put personal data, provider credentials, service-account keys, or production environment files in version control.

## Documentation

Detailed documentation lives in `docs/`.

Useful entry points include:

```text
docs/project-brief.md
docs/architecture.md
docs/api-contract.md
docs/gcp-deployment.md
docs/research-agent.md
docs/dependency-management.md
docs/decisions/
```

## License

No license is currently specified. Add an explicit `LICENSE` file before treating the repository as generally reusable open-source software.

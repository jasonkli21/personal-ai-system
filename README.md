# Personal AI System

A learning and research project for reusable AI capabilities around chat, context, memory, retrieval, evidence, and evaluation. It is experimental software, not a production-ready personal-data service. Provider, cloud, native-storage, and independent security acceptance remain incomplete; see [current state](docs/current-state.md).

## What is here

- A FastAPI core with streaming chat, token-budgeted context assembly, provider-neutral inference contracts, policy and usage boundaries, and persistence adapters.
- Governed memory and local retrieval/research capabilities. These are separately controlled; experimental and privacy-sensitive features default off. Retrieval can enter model context only through its gated, permission-checked path.
- A Next.js web client and optional Travel, Shopping, Finance, and Health reference integrations. Reference applications are a separate distribution and are not part of the standalone core.
- HTTP contracts for independent applications, including the optional HTTP-only [Reading Logbook example](examples/reading-logbook/README.md).

Hosted model adapters require provider credentials. The offline fake profile is for local development and tests; it does not prove real provider behavior or production readiness.

## Quick start: credential-free core

Requirements: Python 3.11+, [uv](https://docs.astral.sh/uv/) 0.11.13, Node.js 22, and pnpm 11.19.0 for the web client. Docker Compose is optional for native persistence.

```sh
cp backend/.env.example backend/.env
cd backend
uv sync --locked --extra dev
set -a; . ./.env; set +a
python -m uvicorn personal_ai.main:app --reload --port 8000
```

The example environment selects `INFERENCE_PROFILE=offline_fake` and `INFERENCE_COST_MODE=offline_fake`, with memory, retrieval and other gated capabilities disabled. No real provider key is needed. The command starts the API; persistent operations need explicitly configured stores. For local Postgres and DynamoDB Local, use `make persistence-up` and the bootstrap commands in the [Makefile](Makefile).

In another terminal, install and start the UI:

```sh
cd frontend
pnpm install --frozen-lockfile
pnpm dev
```

The frontend reads the server-side `API_BASE_URL` from `frontend/.env.local`; copy `frontend/.env.local.example` and keep its default `http://localhost:8000` for local API proxying. See [API and consumer contracts](docs/api-contract.md) before building an independent client.

## Development checks

Run commands from the repository root. The backend environment must be installed as above; install frontend dependencies with the frozen lockfile for frontend commands.

```sh
make backend-lint
make backend-test-offline
make backend-build
make frontend-lint frontend-typecheck frontend-test frontend-build
```

`make backend-test-offline` excludes native persistence and cloud tests. `make pi2-check` builds the core, reference, and Reading Logbook packages and runs offline artifact/contract checks. Native persistence and provider checks are opt-in; see the [current status and gates](docs/current-state.md).

## Architecture and contribution routes

The core owns shared chat, context, inference, memory, retrieval, usage, policy, and storage interfaces. Optional domain applications own their records and rules and contribute through explicit extension points. The API is FastAPI; the browser uses the Next.js API proxy; external consumers use versioned HTTP contracts. See [architecture](docs/architecture.md), [extensions](reference-apps/README.md), and the [documentation router](docs/README.md).

Repository map:

- `backend/src/personal_ai/` — core services, contracts, adapters, and API
- `backend/tests/` — backend unit, contract, and integration tests
- `frontend/` — Next.js UI and tests
- `reference-apps/` — separately installable reference contributions
- `examples/` — independent consumer examples
- `docs/` — architecture, contracts, current implementation state, and evidence

Contributors: read [CONTRIBUTING.md](CONTRIBUTING.md). Security reports: see [SECURITY.md](SECURITY.md). This project is licensed under [Apache License 2.0](LICENSE).

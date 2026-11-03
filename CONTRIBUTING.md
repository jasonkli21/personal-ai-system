# Contributing

Thanks for helping improve this learning and research project. Keep changes focused, preserve existing user work, and avoid adding product scope from future plans alone.

## Setup and checks

Follow the root [README](README.md) for the credential-free setup. Use the relevant Makefile targets for changed code. Backend tests requiring Postgres/DynamoDB, live providers, cloud resources, or deployment are opt-in and must be reported separately; fakes do not establish those behaviors.

Before opening a change, run relevant lint, type, and test checks, then `git diff --check`. Explain any checks that could not run and include focused reproduction steps for fixes. Do not commit credentials, private conversations, generated output, or personal data.

## Project conventions

Routes and UI stay thin; services and domain modules own behavior. Keep provider SDKs behind adapters and route model turns through shared token-budgeted context assembly. Preserve authorization, disclosure, consent/revocation, provenance, idempotency, recovery, and default-off gates. Add tests for behavior changes without weakening existing assertions.

Put user-facing setup and behavior in the root or owning package README; contracts in `docs/`; current implementation status and verification changes in `docs/current-state.md` and dated evidence; design rationale in an accepted ADR. Keep historical plans historical. Do not append implementation notes to the root README.

Use focused pull requests with a clear summary, rationale, relevant tests, and known limitations. No special support or response-time commitment is offered.

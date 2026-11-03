# Read-only MCP source adapter

This optional package is for public synthetic fixtures. Core startup and the
published HTTP consumer API do not load it. The client, server and local loader
each require an explicit `enabled=True` from trusted host code.

- `load_document` takes an absolute operator path, validated retrieval metadata and
  the expected SHA-256. Use the resulting document in a v2 retrieval installation
  with a selected issuer and exact source grants.
- `read_fixture` uses a registered local stdio executable or an in-process
  Streamable HTTP ASGI peer. The fixture registration fixes the peer and
  expected document. A host-owned callback supplies the current registration
  at each authority check. It returns the effective protocol and validated
  issuer/document registration. It never installs results.
- `retrieval_server` builds an SDK server for a verified, current host binding.
  The host supplies the real retrieval service and selected application registry.
  The test suite exercises it in-process and through a separately launched
  synthetic stdio host. That host binds fixed test identity before serving;
  client arguments cannot select or change the identity. This is E1 process
  isolation evidence, not installed authentication or a network listener.

The adapter pins the official Python SDK at 2.3.0 and accepts protocol revisions
`2026-07-28` and `2025-11-25`. Both revisions are exercised through that same
SDK; independent interoperability with a separately implemented legacy peer
has not been established. Unknown revisions remain rejected.

Use a dedicated CPython 3.12 environment with the backend distribution,
pytest and the SDK requirements in
[the macOS ARM64 lock](requirements-macos-arm64-py312.txt). The requirements
lock covers the optional SDK stack. The backend keeps its own dependency
lock. Install trusted build artifacts offline before running the checks.
Use `make mcp-adapter-check` from the repository root. Set `MCP_ADAPTER_PYTHON` to the
dedicated interpreter if it differs from `adapters/mcp_source/.venv/bin/python`.
Set `MCP_ADAPTER_IMPORT_PATH=` to use installed adapter and backend wheels. Missing
dependencies fail collection. The parent check and stdio fixture deny Python
network operations. The HTTP path uses ASGI without sockets.

Rollback is to withdraw the host selections, quiesce any in-flight exchanges
and remove the optional package. Existing retrieval installations, attempt
receipts and model context policies retain their own lifecycle. See
[ADR 0024](../../docs/decisions/0024-hxe1-read-only-mcp.md).

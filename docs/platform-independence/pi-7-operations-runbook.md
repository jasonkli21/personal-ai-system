# PI-7 operations

The installed profiles use synthetic data. The preflight evaluates an operator
proposal. Check the [verification ledger](pi-7-verification.json) for gate and
evidence status.

## Offline core and Reading Logbook

Use Python 3.11+ and uv with a prepared backend virtualenv containing the
versions selected by `backend/uv.lock` for dev and build. Prepare that
environment using the [repository setup](../../README.md#local-setup) in a
separately authorized setup step if it is missing. The smoke commands use
the installed dependency files as their offline input. They check package
names and versions against the lock export and exclude editable distributions,
startup hooks and the source checkout from the installed interpreter. A
version check is not a byte-for-byte reconstruction from downloaded wheel
hashes.

```sh
make pi7-local-smoke PI7_SMOKE_FLAGS=--require-native
make pi7-consumer-smoke PI7_SMOKE_FLAGS=--require-native
make pi7-check
```

The core smoke uses FastAPI's real factory and lifespan, the existing
`offline_fake` inference and shared context composition, explicit in-memory
storage ports and a kernel-assigned numeric loopback HTTP port. Reading Logbook
adds a separately built host and a stdlib-only client in its own environment.
The signed issuer, workspace membership, model and stores are synthetic.
The installed environment runs outside the checkout. The build cache, work
directory, ports, fake records and subprocess groups belong to the invocation.
A repeat starts with fresh state. SIGINT/SIGTERM interrupt the process group
and remove that invocation's temp directory. After an uncatchable termination,
verify ownership and that no child is running before removing its exact temp
directory.

The launcher tests a macOS loopback-only sandbox with native IPv4/IPv6 TCP
probes before reporting native evidence. Some managed shells deny nested
sandbox setup or bind. Without `--require-native` the launcher labels its
Python audit-only path explicitly and still requires working loopback.
The uv build/install commands stay offline in either case. An unsupported
or rejected native fence leaves that claim blocked. Investigate missing
dependency diagnostics using the version in `uv.lock`. The launcher does
not fetch packages or use `.env`, credentials, Docker or personal storage.

## Disposable local persistence

Use a trusted local Docker daemon, Compose v2 and preloaded image tags from
`docker-compose.persistence.yml`. The wrapper uses an explicit Unix socket,
a unique project and only the two existing `integration` services. PostgreSQL
data is on tmpfs and DynamoDB uses in-memory mode. Default ports are
`127.0.0.1:54330` and `127.0.0.1:8001`. Keep these ports free and avoid other
processes publishing them while the drill runs. Use one operator per nonce.
On hosts with a different local Docker socket set `PI7_STORE_SOCKET` to its
absolute path. Do not point the wrapper at a forwarded or shared daemon.

```sh
export PI7_STORE_SESSION=$(backend/.venv/bin/python -I -c 'import secrets; print(secrets.token_hex(16))')
make pi7-store-doctor
make pi7-store-up
make pi7-store-bootstrap
make pi7-store-smoke
make pi7-store-down
```

Doctor checks local tooling, ownership, ports and cached images. Up never
pulls or builds. Bootstrap uses the test DSN and Dynamo endpoint after checking
Compose identity, mount types and published ports. Smoke runs the repository's
synthetic native integration cases, including new repository instances and
scoped state. Down stops and removes only inspected test container IDs and
the owned bridge. There is no volume removal. Save the nonce until cleanup
completes. If a command refuses drift or daemon state changes, inspect the
exact test project before acting. Never use `persistence-clean` for this
profile. To rehearse an ephemeral restart, repeat up, bootstrap and smoke
after down. Verify a clean test store each time. Durable restart and restore
belong to the separately approved [recovery drill](pi-7-data-lifecycle-runbook.md).

## Static cloud plan

```sh
make pi7-cloud-plan
make pi7-cloud-plan PI7_CLOUD_MANIFEST=/path/to/proposal.json PI7_CLOUD_BASELINE=/path/to/reviewed.json
```

Use the [example](../../infrastructure/gcp/pi7-cloud-plan.example.json) as a
schema guide. It contains synthetic image digests, origin, identities and
storage references. Use references only and keep real operator manifests out
of Git. The validator expects a staging plan with pinned images and Neon
secret version, exact Google user audience and origin, distinct service
accounts and service audiences, narrowly named IAM edges, internal API/worker
ingress, exact numeric AWS federation subjects and audiences, restricted
egress, capped services and disabled
optional capabilities. The only PI-7 plan profile is fake inference with a
zero remote model/search budget and the external-provider stop enabled.
An optional baseline yields a redacted list of changed sections. Changes
return a refusal exit code for review. Without a baseline the result covers
policy validation only. Region, endpoints and cloud bindings are checked
statically. DNS, ingress connectivity, current IAM and drift require authorized
live evidence.

The `deploy.sh` command supports `plan` and refuses `apply`. The old positional
Gemini command now refuses before any cloud call. To close apply, a future
reviewed implementation needs a signed or otherwise authenticated plan
identity, an independent read-only live drift check, exact scoped IAM and
network evidence, approvals naming the project and permitted effects, and
tested rollback. Keep any prior revision quarantined until source and receipt
authority are revalidated.

## Cost and incident controls

Use the canonical API request limiter for coarse owner admission. Its route
reservations estimate fan-out. Use P19's attempt and quota ledger for
per-request bounds, endpoint quotas, unresolved acknowledgement and usage
provenance. Preserve the original key across timeout, interrupted stream or
restart. Reconcile an uncertain effect through retained status. Stop new
admission if the ledger or rights cannot be revalidated. UTC daily request
reservation windows and provider quota bucket reset times describe different
authorities. Never clear a counter or prune a receipt to regain capacity.

Local diagnostics contain fixed profile and evidence classes, dependency and
artifact hashes, bounded startup measurements and safe refusal codes. The
standalone planner emits a manifest digest and section names, with no raw
configuration values. Existing application logs have their own correlation
policy and can contain request, app or workspace identifiers. Retain only
necessary diagnostic fields and keep logs out of evidence attachments. For
an incident, stop the affected chat/research/worker route and external retrieval
using the owning runtime controls. A switch cannot recall an already sent
request. Where the adapter or route does not guarantee a physical stop, fence
network egress and stop the worker or service before reopening traffic.

Keep synthetic counts, estimated units, provider-reported usage and billed
currency separate. The current smoke reports zero remote dispatches in its
native fence and unobserved billing. Closed static settings do not cap cloud
infrastructure charges. Provider/account hard caps, allowance resets, pricing,
actual billing and deployed kill-switch behavior require scoped account
evidence. A live strict-free or paid profile stays outside this plan.

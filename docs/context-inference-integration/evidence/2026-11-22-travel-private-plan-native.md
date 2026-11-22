# Travel private plan native preview and joint review · 2026-11-22

**The isolated paired preview passed with migrated PostgreSQL in both applications. G1 remains `BLOCKED_CONTRACT` pending joint approval. Step 4 integrated dispatch and Step 5 acceptance reviews remain pending.** Live execution remains `BLOCKED_EXTERNAL`. [Earlier readiness and source-lock comparison](2026-11-22-travel-g1-native-readiness.md) · [Paired acceptance ledger](2026-11-22-travel-private-plan-paired-verification.md)

## Paired inputs and observed journey

- PAS application source `9ab13a91f2972a1c7edace7f2325d47b9510850e` and Travel `77f3c7a1257b6231ca6cbcffb8a93d121372c861`. The PAS working tree adds the opt-in test, its separate Travel worker and a test fixture repository hook. The Travel checkout was clean. Both Python environments were installed with the project's own `uv sync --locked` and PAS's `dev` extra. [Paired test](../../../backend/tests/test_travel_plan_paired.py) · [Travel worker](../../../backend/tests/app_context_support/travel_plan_worker.py)
- The test imports PAS `create_app` and mounts the private routes only in its isolated composition. It starts a separate Travel Python process and imports the real source route and journal. The worker applies Travel migrations through 0021 in a disposable PostgreSQL schema, runs `alembic check`, and drops the schema. Normal PAS and Travel app entry points each served health and returned 404 on the private path. The worker receives the signed reverse-hop HTTP request over a local pipe and executes it through FastAPI's test transport.
- One fabricated human with the registered Travel client created two PAS conversations through consumer v1. The original-key create replays matched the receipts, and authorized detail confirmed both IDs. Travel's native journal bound each receipt to its reserved trip and create key before either preview. The four interleaved A/B/A/B requests returned the intended revision and exact inventory provenance, with one canonical PAS memory and the correct trip in each prepared package. The HTTP preview excluded raw trip and memory content.
- Removing any source read, runtime handoff or model disclosure grant, substituting an otherwise valid grant from the other conversation, or replacing the memory's model recipient denied preview before Travel's source call. The unregistered authorized party and foreign signed identity returned 403. A forwarded identity header returned 401. A native Travel ACL change denied source read with 404 and blocked preview.
- The Travel journal accepted a preview receipt digest and expiry, retained only the original key for an ambiguous second preview, rejected a changed request with 409, and returned no selector for a different key. The confirmed private continuation returned 422 while G1 is closed. Runtime delivery received zero packages and zero plaintext bytes. The receiving fake provider recorded zero POSTs. Both test processes asserted zero attempted Python outbound socket connections. Native PostgreSQL traffic was local.

## Store and regression results

| Witness | Executed outcome |
| --- | --- |
| Paired preview | `1 passed` with PostgreSQL 17.12 and pgvector 0.8.0. Travel SQL identity, trip ACL/revision, anchor, and preview journal were native. PAS PostgreSQL principal directory, memory record and lifecycle reads were native. The source-write guard for fixture memory seeding, PAS conversation/message stores, exact-consent grants and runtime pairing were fixture inputs. |
| Travel native plan | `6 passed` in `tests/test_private_plan_postgres.py`. Includes distinct-owner isolation, changed revision, shared anchor-key lane isolation, and concurrent journal reservations with separate SQL sessions. |
| Travel full backend and frontend | `355 passed` plus 22 Python subtests with the existing mounted OAuth fixture using a numeric loopback disposable database. `make frontend-check` passed lint, type check and all 17 tests with the frozen pnpm lock. Travel backend mypy and documentation link check passed. Locked Travel backend lint flagged an overlong line and unsorted imports in the candidate. Locked Ruff formatting also flagged seven candidate files, including 0021. |
| PAS native predecessor | `4 passed` in `tests/persistence/test_application_plan_postgres.py` on PostgreSQL/pgvector. That suite uses the existing application-plan fixture and covers PAS's original-key and native routing/owner fence behavior through ambiguity, worker loss, contention and restore. This is a PAS predecessor regression, separate from Travel dispatch. |
| PAS direct consumer contract and lint | The direct consumer contract check passed. The three touched test files pass locked Ruff. Repository-wide `make backend-lint` exits 2 with 10 Ruff findings in pre-existing diagnostics and candidate sources. |
| PAS source identities | Locked source checker exited 1 on planning and offline information handling. The PAS offline plan, context and source suite completed with 178 passes and three failures, all in `test_source_contracts.py`, with zero audited network attempts. The prior read-only comparison records 45 → 49 planning mismatches and 42 → 46 offline core-runtime mismatches from base to candidate. [Source-lock comparison](2026-11-22-travel-g1-native-readiness.md#pas-source-lock-comparison) |

The paired run leaves durable PAS private grants, native DynamoDB conversation/message authority, Travel backup/restore and independent send-process ordering open. The currently tested PAS memory/source grants are typed and request-scoped fixture authorities. The native SQL writes are independent of the R3 fixture's POSIX send lock. A positive synthetic send would supply evidence only for its actual fixture topology.

## Reproduce the paired test

Use separate locked environments, a disposable PostgreSQL database reachable over a Unix socket for Travel, and a disposable local PostgreSQL endpoint with pgvector and a test role that can create databases for PAS. The PAS protected-store fixture needs an absolute temporary path outside every checkout. On managed shells that inject a `.git` placeholder under `/tmp`, use a private fixture directory on `/dev/shm` if available.

```sh
cd "$travel_backend"
UV_PROJECT_ENVIRONMENT="$travel_venv" uv sync --locked
cd "$pas_backend"
UV_PROJECT_ENVIRONMENT="$pas_venv" uv sync --locked --extra dev

env -i PATH="$PATH" LITELLM_LOCAL_MODEL_COST_MAP=True AWS_EC2_METADATA_DISABLED=true \
  TRAVEL_BACKEND="$travel_backend" TRAVEL_TEST_PYTHON="$travel_venv/bin/python" \
  TEST_DATABASE_URL="$travel_disposable_socket_dsn" \
  PERSISTENCE_TEST_POSTGRES_DSN="$pas_disposable_postgres_dsn" \
  "$pas_venv/bin/python" -B -m pytest -q --basetemp="$fixture_directory" \
  tests/test_travel_plan_paired.py
```

## Joint decision requested

The Travel and PAS contract owners should record their joint disposition against Travel ADR 0017 and the paired revisions above. The reviewed preview boundary binds the verified PAS conversation to one Travel-owned trip and preserves the v2 projection and permission provenance through the shared PAS assembler. The next decision is whether to authorize an isolated synthetic dispatch implementation against this boundary. [Proposed ADR 0017](https://github.com/jasonkli21/travel-app/blob/77f3c7a1257b6231ca6cbcffb8a93d121372c861/docs/decisions/0017-private-plan-preview-source.md)

The dispatch proposal must name the release authority, its behavior on revoked or stale rights, and the durable claim and recovery boundary. The required witness reserves the original UUID and exact request before continuation, commits one independently retained send claim, and disables retries through the receiving fake. Ambiguity, restart and an older restore may reconcile only by original-key status and matching detail. Missing fence continuity quarantines recovery. Count physical POSTs at the fake receiver and assert one for the confirmed journey. Record the distributed revocation race as an open live blocker.

The PAS planning and offline benchmark owners also need to disposition the inherited drift and the four new plus six further-changed paths in each core scope. The locked checker's read-only `--propose-planning` and `--propose-offline-benchmark` modes exited 0 and identified planning `v40` and offline generation `14`. The planning proposal awaits the reviewer's freeze date and source-change summary. The offline proposal awaits the reviewer's preregistration. Keep the existing source manifests and historical results intact. An approved successor needs its own evaluations. This evidence supplies an implementer observation and an approval request. No independent or joint sign-off is recorded here.

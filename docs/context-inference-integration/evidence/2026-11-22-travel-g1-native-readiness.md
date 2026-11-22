# Travel G1 native readiness · 2026-11-22

**G1 remains `BLOCKED_CONTRACT`. Step 4 integrated dispatch remains gated, so the formal Step 5 reviews are pending.** Native preview, consent, binding and journal tests did not run. This follow-up records environment checks, read-only PAS source-lock comparisons, and an inspection of the available app entry points. The prior reduced preview and ledger retain their original scope. [Paired verification](2026-11-22-travel-private-plan-paired-verification.md)

Clean checkouts were PAS `9ab13a91f2972a1c7edace7f2325d47b9510850e` and Travel `77f3c7a1257b6231ca6cbcffb8a93d121372c861`. The PAS comparison base was a clean detached checkout at `f5f60fb6f871dad9d59071f2ebf91ecb8e1c69f1`. Travel ADR 0017 is still proposed. [Travel ADR 0017](https://github.com/jasonkli21/travel-app/blob/77f3c7a1257b6231ca6cbcffb8a93d121372c861/docs/decisions/0017-private-plan-preview-source.md)

## Runtime availability

| Check | Result |
| --- | --- |
| Travel backend, `UV_OFFLINE=1 UV_CACHE_DIR=/tmp/r4-travel-cache UV_PROJECT_ENVIRONMENT=/tmp/r4-native-travel uv sync --locked` | Exit 1. The cache lacks the locked Python 3.12 Linux wheel for `psycopg-binary==3.3.6`. |
| PAS backend, `UV_OFFLINE=1 UV_CACHE_DIR=/tmp/r4-pas-cache UV_PROJECT_ENVIRONMENT=/tmp/r4-native-pas uv sync --locked` | Exit 1. The cache lacks `openai==2.54.0`, required by the locked LiteLLM package even for installing the app for a local test. |
| Public PyPI and Debian package index HEAD requests | Both exited 7. The configured proxy refused the connection. |
| Disposable PostgreSQL | No `TEST_DATABASE_URL` or local PostgreSQL executables were present. The local APT cache contained no PostgreSQL package. `docker version` reported permission denied on the daemon socket. |

No database migration or native suite started. No reduced probe was repeated and no provider transport was invoked.

## PAS source-lock comparison

The read-only command `PYTHONPATH=backend/src:reference-apps/src:sdk/python/src python -B backend/scripts/source_contract_check.py --check` exited 1 on both PAS revisions. The two source manifests were identical across revisions. Comparing the full file maps returned by the checker's planning and offline benchmark validators gives:

| Locked source scope | Base mismatched paths | Candidate mismatched paths |
| --- | ---: | ---: |
| Planning | 45 | 49 |
| Offline benchmark core runtime | 42 | 46 |
| Offline benchmark reading logbook client and host | 0 | 0 |

Both core scopes gained four mismatches in `context/builder.py`, `context/providers.py`, `context/runtime.py` and `contracts/context_references.py` under `backend/src/personal_ai`. Six already mismatched paths changed again in both scopes: `context/authority.py`, `context/history.py`, `services/chat/service.py`, `services/conversations.py`, `services/external_turns/application_plan.py` and `services/external_turns/authority.py`. The base planning digest was `6b6f66e1fa24967e6e4618f8761a7f9e39287fad968970b8ae10e0079993d8b3`, compared with `bcc0de894d4cfa861b1a32407e2d3b578ced29781f36a175ff7ca59157361955` at the result. The offline core-runtime digest moved from `7eedba8ca725b07e17fe8eb3085a033bc7607a438fd07fc0ef182ee12747e9e0` to `5284e8b4872e58346d827ebad37434e3ff18aa8c8a78d0fbed2621f3c601dcb4`. A reviewed source-lock disposition must cover both inherited drift and the candidate changes.

## Native verification handoff

1. Make both locked dependency sets available and provision a disposable PostgreSQL database. In the Travel backend, run `TEST_DATABASE_URL=<disposable PostgreSQL URL> uv run --locked pytest -ra -q tests/test_private_plan_postgres.py`. The fixture creates a unique schema, upgrades through 0021, runs `alembic check`, and drops the schema on teardown. The six tests cover default-off, interleaved same-owner trip projection, denied scopes and changed revision, write-once binding and automatic lane separation, competing preview reservations with separate sessions and ambiguous lookup, and distinct-owner isolation. They use an explicitly mounted Travel app, fabricated identities and signed test credentials. [Native suite](https://github.com/jasonkli21/travel-app/blob/77f3c7a1257b6231ca6cbcffb8a93d121372c861/backend/tests/test_private_plan_postgres.py)
2. Exercise the ordinary app entry points for default-off and legacy regression separately from the isolated paired preview. PAS production `create_app` does not call `mount_application_plan`. The pinned mount call is in the PAS test host. Travel's ordinary `main:app` also omits the private source route, and Travel has no product caller for `PrivatePlanJournal.bind_created_conversation`. A paired isolated host needs explicit wiring of the Travel source, SQL sessions, PAS authenticated owner/client and canonical memory/grant stores, and a verified create result before it can prove binding and consent together. Keep the isolated target preview-only while G1 is closed. [PAS isolated test composition](../../../backend/tests/app_context_support/application_plan.py) · [Travel journal](https://github.com/jasonkli21/travel-app/blob/77f3c7a1257b6231ca6cbcffb8a93d121372c861/backend/src/personal_travel/services/private_plan.py)
3. Before Step 5, record the two-trip preview with current owner, identity and exact source/runtime/model consent checks, the release-denial witness, and independently reviewed joint ADR and source-lock dispositions. Native backup/restore and separate-process contention need additional witnesses beyond the six PostgreSQL tests. The existing documented distributed revocation race and live eligibility block remain open.

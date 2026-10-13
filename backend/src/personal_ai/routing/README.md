# Routing

This package owns provider-neutral endpoint eligibility, deterministic route decisions, integrity
hashes, replay, quota-aware strategy evaluation, and dispatch coordination. It does not own the
LiteLLM transport or Postgres SQL implementation.

## Entry points and boundaries

- `service.py` coordinates routing decisions and atomic authorization, reservation, and dispatch lifecycle operations.
- `contracts.py`, `decision_models.py`, `policy.py`, and `integrity.py` define stable records and rules.
- `registry.py`, `strategy.py`, `cascade.py`, and `configured.py` own profile and strategy behavior.
- Persistence implementations live in `personal_ai.persistence.postgres`; orchestration consumes an injected repository contract.
- Routing contracts, decision records, integrity functions, policy rules, and strategy behavior are imported from their owning semantic modules.

Routing tests live in `backend/tests/test_routing_*.py`, `backend/tests/test_provider_matrix.py`, and the usage suites. Decision persistence and replay must retain their current transaction and idempotency boundaries.

Phase 35 adds `features.py` and `adaptive.py` behind `RoutingStrategy`. The normal
persistence factory's `routing_service` composes registry, P19 accounting, explicit
authorization and configured strategy. Its default remains the quota-aware
baseline; optional shadow observes only admitted candidates and cannot dispatch.
The FastAPI `get_routing_decision_service` dependency is the canonical API
composition point and requires an app-installed current authorization authority.
No user workflow consumes it while Phase 15 membership/revocation and
provider-neutral dispatch acceptance remain open. The synchronous strategy
registry accepts only code-reviewed implementations declaring the bounded-pure
execution contract; the measured 5 ms threshold is post-hoc and is not a timeout.
Schema 6 records exact endpoint configuration digests, bounded feature identity
and optional compact shadow metadata inside the existing decision JSON. Historical
schemas remain readable for deterministic replay and are excluded from feature
training when decision-time identity is missing. No SQL schema change is needed.
Malformed/oversized optional diagnostics are omitted without changing the visible
route. See [the experiment contract](../../../../experiments/ranking/README.md).

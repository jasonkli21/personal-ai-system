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

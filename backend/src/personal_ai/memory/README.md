# Memory

This package owns durable user-memory contracts, extraction, retrieval, disclosure policy, and
lifecycle behavior. Memory remains a separate data class from time-sensitive external evidence.

## Entry points and boundaries

- Root modules own memory identity, extraction, retrieval, and general policy.
- `lifecycle/` owns lifecycle contracts, scoring, transitions, jobs, and lifecycle repositories.
- Backend-neutral memory effect coordination contracts live in `effects.py`; database adapters implement them under `personal_ai.persistence`.
- `lifecycle.py` and the `lifecycle_*` modules remain compatibility exports.

Lifecycle and disclosure tests live in `backend/tests/test_memory_lifecycle.py`, `backend/tests/test_memory.py`, and persistence suites. Preserve freshness, source attribution, owner scope, and transactional behavior when changing adapters.

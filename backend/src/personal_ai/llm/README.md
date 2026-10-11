# Inference

This package defines the provider-neutral generation, streaming, embedding, counting, attribution,
and preparation contracts used by services. Provider SDK and transport details stay behind adapters.

## Entry points and boundaries

- `__init__.py` and the contracts expose the shared inference interface.
- `litellm/` implements the pinned LiteLLM transport, request shaping, streaming, profiles, and attempt accounting.
- Product workflows depend on the neutral contracts; they should not import LiteLLM types.
- `personal_ai.llm.litellm_gateway` remains a compatibility import path.

Gateway and provider contract tests live in `backend/tests/test_litellm_gateway.py`, `backend/tests/test_llm_*.py`, and related usage tests. Offline fakes do not establish live provider compatibility.

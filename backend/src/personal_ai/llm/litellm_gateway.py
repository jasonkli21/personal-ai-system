"""Compatibility import for the LiteLLM provider-neutral gateway."""

import sys

from personal_ai.llm.litellm import gateway as _gateway

sys.modules[__name__] = _gateway

"""Compatibility import for external-turn orchestration."""

import sys

from personal_ai.services.external_turns import service as _service

sys.modules[__name__] = _service

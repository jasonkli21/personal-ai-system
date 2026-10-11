"""Compatibility import for the chat-turn service."""

import sys

from personal_ai.services.chat import service as _service

sys.modules[__name__] = _service

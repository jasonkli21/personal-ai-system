"""Compatibility import for lifecycle policy."""

import sys

from personal_ai.memory.lifecycle import policy as _module

sys.modules[__name__] = _module

"""Compatibility import for lifecycle repositories."""

import sys

from personal_ai.memory.lifecycle import repositories as _module

sys.modules[__name__] = _module

"""Compatibility import for lifecycle jobs."""

import sys

from personal_ai.memory.lifecycle import jobs as _module

sys.modules[__name__] = _module

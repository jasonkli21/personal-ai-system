"""Compatibility import for ``personal_ai.agents.research.iterative.repositories``."""

import sys

from personal_ai.agents.research.iterative import repositories as _implementation

sys.modules[__name__] = _implementation

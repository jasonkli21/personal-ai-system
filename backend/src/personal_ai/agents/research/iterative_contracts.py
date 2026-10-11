"""Compatibility import for ``personal_ai.agents.research.iterative.contracts``."""

import sys

from personal_ai.agents.research.iterative import contracts as _implementation

sys.modules[__name__] = _implementation

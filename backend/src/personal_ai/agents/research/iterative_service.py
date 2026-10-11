"""Compatibility import for ``personal_ai.agents.research.iterative.service``."""

import sys

from personal_ai.agents.research.iterative import service as _implementation

sys.modules[__name__] = _implementation

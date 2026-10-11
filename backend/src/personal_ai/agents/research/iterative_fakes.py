"""Compatibility import for ``personal_ai.agents.research.iterative.fakes``."""

import sys

from personal_ai.agents.research.iterative import fakes as _implementation

sys.modules[__name__] = _implementation

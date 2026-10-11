"""Compatibility import for ``personal_ai.persistence.postgres.capabilities``."""

import sys

from personal_ai.persistence.postgres import capabilities as _implementation

sys.modules[__name__] = _implementation

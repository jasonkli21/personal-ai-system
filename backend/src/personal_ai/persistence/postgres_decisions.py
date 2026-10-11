"""Compatibility import for ``personal_ai.persistence.postgres.decisions``."""

import sys

from personal_ai.persistence.postgres import decisions as _implementation

sys.modules[__name__] = _implementation

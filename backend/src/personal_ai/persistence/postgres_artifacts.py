"""Compatibility import for ``personal_ai.persistence.postgres.artifacts``."""

import sys

from personal_ai.persistence.postgres import artifacts as _implementation

sys.modules[__name__] = _implementation

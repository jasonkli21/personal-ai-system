"""Compatibility import for ``personal_ai.persistence.postgres.neon``."""

import sys

from personal_ai.persistence.postgres import neon as _implementation

sys.modules[__name__] = _implementation

"""Compatibility import for ``personal_ai.persistence.postgres.research``."""

import sys

from personal_ai.persistence.postgres import research as _implementation

sys.modules[__name__] = _implementation

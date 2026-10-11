"""Compatibility import for ``personal_ai.persistence.postgres.auth``."""

import sys

from personal_ai.persistence.postgres import auth as _implementation

sys.modules[__name__] = _implementation

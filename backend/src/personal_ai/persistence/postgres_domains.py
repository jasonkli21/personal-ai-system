"""Compatibility import for ``personal_ai.persistence.postgres.domains``."""

import sys

from personal_ai.persistence.postgres import domains as _implementation

sys.modules[__name__] = _implementation

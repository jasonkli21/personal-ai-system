"""Compatibility import for ``personal_ai.persistence.postgres.memory``."""

import sys

from personal_ai.persistence.postgres import memory as _implementation

sys.modules[__name__] = _implementation

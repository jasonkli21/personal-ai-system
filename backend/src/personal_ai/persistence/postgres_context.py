"""Compatibility import for ``personal_ai.persistence.postgres.context``."""

import sys

from personal_ai.persistence.postgres import context as _implementation

sys.modules[__name__] = _implementation

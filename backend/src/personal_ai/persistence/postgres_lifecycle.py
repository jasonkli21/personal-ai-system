"""Compatibility import for ``personal_ai.persistence.postgres.lifecycle``."""

import sys

from personal_ai.persistence.postgres import lifecycle as _implementation

sys.modules[__name__] = _implementation

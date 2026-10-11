"""Compatibility import for ``personal_ai.persistence.postgres.owner_lifecycle``."""

import sys

from personal_ai.persistence.postgres import owner_lifecycle as _implementation

sys.modules[__name__] = _implementation

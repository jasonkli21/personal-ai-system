"""Compatibility import for ``personal_ai.persistence.postgres.routing``."""

import sys

from personal_ai.persistence.postgres import routing as _implementation

sys.modules[__name__] = _implementation

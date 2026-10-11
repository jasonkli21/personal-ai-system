"""Compatibility import for ``personal_ai.persistence.postgres.routing_observations``."""

import sys

from personal_ai.persistence.postgres import routing_observations as _implementation

sys.modules[__name__] = _implementation

"""Compatibility import for ``personal_ai.persistence.postgres.provider_matrix``."""

import sys

from personal_ai.persistence.postgres import provider_matrix as _implementation

sys.modules[__name__] = _implementation

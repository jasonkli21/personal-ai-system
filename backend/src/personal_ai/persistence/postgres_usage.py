"""Compatibility import for Postgres provider usage accounting."""

import sys

from personal_ai.persistence.postgres.usage import accounting as _implementation

sys.modules[__name__] = _implementation

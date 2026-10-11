"""Compatibility import for external-turn principal authority."""

import sys

from personal_ai.services.external_turns import authority as _authority

sys.modules[__name__] = _authority

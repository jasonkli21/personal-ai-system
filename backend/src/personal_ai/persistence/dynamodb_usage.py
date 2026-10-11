"""Compatibility import for DynamoDB provider usage event persistence."""

import sys

from personal_ai.persistence.dynamodb import usage as _implementation

sys.modules[__name__] = _implementation

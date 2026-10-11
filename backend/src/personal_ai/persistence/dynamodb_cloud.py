"""Compatibility import for the federated DynamoDB adapter."""

import sys

from personal_ai.persistence.dynamodb import cloud as _implementation

sys.modules[__name__] = _implementation

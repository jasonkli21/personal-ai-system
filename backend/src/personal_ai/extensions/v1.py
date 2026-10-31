"""Stable v1 host metadata contracts; trusted code, not an HTTP client SDK.

Only the names in __all__ are public. Install and selection confer no identity,
workspace membership, source access or model disclosure authority.
"""

from personal_ai.applications.contracts import (
    ApplicationContextPolicy,
    ApplicationDefinition,
    CapabilityRegistration,
)
from personal_ai.applications.registry import ApplicationContribution
from personal_ai.context.runtime import ContextRuntimeContribution

HOST_CONTRACT_VERSION = "personal-ai-host-v1"
__all__ = [
    "HOST_CONTRACT_VERSION",
    "ApplicationContextPolicy",
    "ApplicationContribution",
    "ApplicationDefinition",
    "CapabilityRegistration",
    "ContextRuntimeContribution",
]

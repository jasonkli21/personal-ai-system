"""Exact installed capability proof. No real native mappings are registered."""

from dataclasses import dataclass
from datetime import UTC, datetime

from personal_ai.reasoning.policy import EFFORTS, Effort
from personal_ai.routing.contracts import EndpointOperation, EndpointProfile


@dataclass(frozen=True, slots=True)
class NativeSetting:
    effort: Effort
    wire_value: str
    minimum_output_tokens: int


@dataclass(frozen=True, slots=True)
class NativeReasoningCapability:
    profile: EndpointProfile
    sdk_id: str
    operation: EndpointOperation
    version: str
    evidence: str
    settings: tuple[NativeSetting, ...]
    valid_until: datetime | None = None

    def resolve(self, profile, sdk_id, operation, ceiling, output_tokens):
        if (
            not profile.enabled
            or profile != self.profile
            or sdk_id != self.sdk_id
            or operation != self.operation
            or operation not in profile.capabilities
            or (self.valid_until is not None and datetime.now(UTC) >= self.valid_until)
        ):
            return None
        eligible = (
            setting for setting in self.settings
            if EFFORTS.index(setting.effort) <= EFFORTS.index(ceiling)
            and setting.minimum_output_tokens <= output_tokens
        )
        return max(eligible, key=lambda setting: EFFORTS.index(setting.effort), default=None)


def resolve_native(profile, sdk_id, operation, ceiling, output_tokens, *, capabilities=()):
    """Exact match only. Ambiguous evidence confers no authority."""
    if profile is None:
        return None
    matches = []
    for capability in capabilities:
        setting = capability.resolve(profile, sdk_id, operation, ceiling, output_tokens)
        if setting is not None:
            matches.append((capability.version, setting))
    return matches[0] if len(matches) == 1 else None

"""Synthetic E1 profile and final-wire validation for the offline adapter."""

import json

from personal_ai.llm.client import ProviderIdentity
from personal_ai.llm.errors import LLMInvalidRequestError
from personal_ai.llm.native_reasoning import (
    NativeReasoningCapability,
    NativeSetting,
    resolve_native,
)
from personal_ai.routing.contracts import EndpointProfile

SDK = "stdlib-json-v1"
CAPABILITY_VERSION = "fake-native-effort-v1"


def offline_profile(identity: ProviderIdentity) -> EndpointProfile:
    return EndpointProfile(
        endpoint_profile_id=f"{identity.provider_id}:generation", profile_version=1,
        provider_id=identity.provider_id, model_id=identity.model_id,
        endpoint_id=identity.provider_id, deployment_id="offline-fixture-v1",
        serializer_id=identity.serializer_id, runtime_id="offline-in-process-v1",
        account_scope_id="offline-fixture", credential_scope_id="offline-no-credential",
        credential_source="none", credential_reference="none:", tier_id="offline",
        execution_mode="LOCAL_ONLY", cost_class="LOCAL_NO_CHARGE",
        enabled=True, capabilities=frozenset({"streaming"}),
    )


_PROVEN_PROFILE = offline_profile(ProviderIdentity(
    "offline_fake", "offline_fake-v1", "pi3-local-json-bytes-v1",
))
_PROOF = NativeReasoningCapability(
    profile=_PROVEN_PROFILE, sdk_id=SDK, operation="streaming",
    version=CAPABILITY_VERSION, evidence="E1_fake",
    settings=(NativeSetting("low", "brief", 1), NativeSetting("high", "extended", 32)),
)


def native_setting(profile, identity, ceiling, output_tokens):
    if (
        identity.provider_id != profile.provider_id
        or identity.model_id != profile.model_id
        or identity.serializer_id != profile.serializer_id
    ):
        return None
    return resolve_native(
        profile, SDK, "streaming", ceiling, output_tokens, capabilities=(_PROOF,),
    )


def serialize(messages, model, value, output_tokens):
    return json.dumps({
        "messages": [(message.role, message.content) for message in messages],
        "model": model, "reasoning": value, "max_output_tokens": output_tokens,
    }, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def verify_wire(wire, messages, model, value, output_tokens):
    """Verify the final payload at the synthetic transport boundary."""
    try:
        body = json.loads(wire)
        expected = {
            "messages": [[message.role, message.content] for message in messages],
            "model": model, "reasoning": value, "max_output_tokens": output_tokens,
        }
        if (
            body == expected
            and wire == json.dumps(
                expected, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
            ).encode()
            and any(
                setting.wire_value == value and setting.minimum_output_tokens <= output_tokens
                for setting in _PROOF.settings
            )
        ):
            return
    except (ValueError, TypeError, UnicodeError):
        pass
    raise LLMInvalidRequestError("synthetic native effort wire mismatch")

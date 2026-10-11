"""Stable configuration and evidence digests for routing decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from personal_ai.routing.contracts import EndpointProfile

if TYPE_CHECKING:
    from .decision_models import RoutingPreferences, RoutingTaskProfile, StrategyRef
import hashlib
import json


def endpoint_configuration_sha256(profile: EndpointProfile) -> str:
    """Digest all registered, secret-free endpoint facts used by quality evidence."""
    payload = json.dumps(profile.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def quality_identity_sha256(
    *,
    endpoint_digest: str,
    task_digest: str,
    policy_version: str,
    quality_profile_id: str,
    quality_profile_version: int,
    scoring_policy_id: str,
    scoring_policy_version: int,
    tested_revision: str,
    evaluation_suite_id: str | None = None,
    evaluation_suite_version: int | None = None,
    fixture_manifest_sha256: str | None = None,
    evaluation_configuration_sha256: str | None = None,
    output_tokens: int | None = None,
    preparation_counter_id: str | None = None,
    preparation_counter_confidence: str | None = None,
    preparation_count_source: str | None = None,
) -> str:
    payload = json.dumps(
        {
            "endpoint_configuration_sha256": endpoint_digest,
            "evaluation_configuration_sha256": evaluation_configuration_sha256,
            "evaluation_suite_id": evaluation_suite_id,
            "evaluation_suite_version": evaluation_suite_version,
            "fixture_manifest_sha256": fixture_manifest_sha256,
            "output_tokens": output_tokens,
            "policy_version": policy_version,
            "preparation_count_source": preparation_count_source,
            "preparation_counter_confidence": preparation_counter_confidence,
            "preparation_counter_id": preparation_counter_id,
            "quality_profile_id": quality_profile_id,
            "quality_profile_version": quality_profile_version,
            "scoring_policy_id": scoring_policy_id,
            "scoring_policy_version": scoring_policy_version,
            "task_configuration_sha256": task_digest,
            "tested_revision": tested_revision,
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def routing_strategy_configuration_sha256(
    preferences: RoutingPreferences, dependencies: tuple[StrategyRef, ...] = ()
) -> str:
    """Digest the effective scorer inputs and composed strategy identities."""
    payload = json.dumps(
        {
            "dependencies": [row.model_dump(mode="json") for row in dependencies],
            "preferences": preferences.model_dump(mode="json"),
        },
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def source_reference_manifest_sha256(references: tuple[str, ...]) -> str:
    """Hash a canonical set of opaque, per-source digests for subset checks."""
    normalized = tuple(sorted(set(references)))
    return hashlib.sha256(json.dumps(normalized, separators=(",", ":")).encode("utf-8")).hexdigest()


def task_configuration_sha256(task: RoutingTaskProfile) -> str:
    """Digest task/output policy while excluding routing-only scarcity preferences.

    Quality evidence predates Phase 23 and remains valid when only the route's
    quota preference changes. Preserve the former serialized shape so existing
    Phase 22 evidence does not become stale merely because new defaulted fields
    were added to ``RoutingPreferences``.
    """
    task_payload = task.model_dump(mode="json")
    if task.cascade_policy is None:
        task_payload.pop("cascade_policy", None)
    for name in (
        "quota_scarcity_weight",
        "quota_unknown_penalty_weight",
        "quota_reset_relief_seconds",
        "degraded_health_penalty",
    ):
        task_payload["preferences"].pop(name, None)
    payload = json.dumps(task_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()

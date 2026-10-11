"""Postgres provider usage health persistence helpers."""

from __future__ import annotations

from datetime import timedelta
from math import ceil


def _health_unavailable(health, now):
    if health is None:
        return False  # Explicit bootstrap: no locally observed failure.
    status, cooldown = health
    if status not in {"healthy", "degraded", "cooldown"}:
        return True
    if cooldown is not None:
        return cooldown > now
    return status != "healthy"


def _lock_endpoint_health(connection, endpoint):
    # Lock even the bootstrap absence of a row against concurrent settlement.
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"provider-health:{endpoint.endpoint_profile_id}:{endpoint.profile_version}",),
    )


def _update_endpoint_health(connection, invocation, result, now, *, default_cooldown_seconds):
    endpoint = invocation.endpoint
    _lock_endpoint_health(connection, endpoint)
    row = connection.execute(
        "SELECT failure_streak,cooldown_until FROM provider_endpoint_health "
        "WHERE endpoint_profile_id=%s AND endpoint_profile_version=%s FOR UPDATE",
        (endpoint.endpoint_profile_id, endpoint.profile_version),
    ).fetchone()
    failures = int(row[0]) if row else 0
    prior_cooldown = row[1] if row else None
    if result.outcome == "success":
        status = "healthy"
        failures = 0
        cooldown = prior_cooldown if prior_cooldown and prior_cooldown > now else None
        connection.execute(
            "INSERT INTO provider_endpoint_health(endpoint_profile_id,endpoint_profile_version,"
            "health_status,failure_streak,cooldown_until,last_status,last_http_status,last_success_at,"
            "updated_at) VALUES (%s,%s,%s,0,%s,%s,%s,%s,%s) "
            "ON CONFLICT(endpoint_profile_id,endpoint_profile_version) DO UPDATE SET "
            "health_status=EXCLUDED.health_status,failure_streak=0,cooldown_until=EXCLUDED.cooldown_until,"
            "last_status=EXCLUDED.last_status,last_http_status=EXCLUDED.last_http_status,"
            "last_success_at=EXCLUDED.last_success_at,updated_at=EXCLUDED.updated_at",
            (
                endpoint.endpoint_profile_id,
                endpoint.profile_version,
                status,
                cooldown,
                result.outcome,
                result.http_status,
                now,
                now,
            ),
        )
        return
    failures += 1
    if result.outcome == "rate_limited":
        duration = result.rate_limits.retry_after_seconds if result.rate_limits else None
        if duration is None and result.rate_limits:
            duration = (
                result.rate_limits.requests_reset_seconds or result.rate_limits.tokens_reset_seconds
            )
        delay = (
            max(1, min(3600, ceil(duration))) if duration is not None else default_cooldown_seconds
        )
        status = "cooldown"
    else:
        delay = min(default_cooldown_seconds, 5 * (2 ** min(failures - 1, 5)))
        status = "degraded"
    cooldown = now + timedelta(seconds=delay)
    if prior_cooldown is not None and prior_cooldown > cooldown:
        cooldown = prior_cooldown
    connection.execute(
        "INSERT INTO provider_endpoint_health(endpoint_profile_id,endpoint_profile_version,"
        "health_status,failure_streak,cooldown_until,last_status,last_http_status,last_failure_at,updated_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT(endpoint_profile_id,endpoint_profile_version) DO UPDATE SET "
        "health_status=EXCLUDED.health_status,failure_streak=EXCLUDED.failure_streak,"
        "cooldown_until=EXCLUDED.cooldown_until,last_status=EXCLUDED.last_status,"
        "last_http_status=EXCLUDED.last_http_status,last_failure_at=EXCLUDED.last_failure_at,"
        "updated_at=EXCLUDED.updated_at",
        (
            endpoint.endpoint_profile_id,
            endpoint.profile_version,
            status,
            failures,
            cooldown,
            result.outcome,
            result.http_status,
            now,
            now,
        ),
    )

"""Bounded provider usage retention and operational-event reconciliation."""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from uuid import UUID

logger = logging.getLogger("personal_ai.persistence.postgres_usage")

from .ledger import _aggregate_attempt, _aggregate_identity, _event_from_row


def _mark_event(accounting, attempt_id: UUID, status: str) -> None:
    with accounting.database.transaction() as connection:
        connection.execute(
            "UPDATE provider_attempts SET operational_event_status=%s WHERE attempt_id=%s",
            (status, attempt_id),
        )


def _publish_event(accounting, attempt_id: UUID, event: dict) -> None:
    if accounting.operational_event_writer is None:
        return
    try:
        accounting.operational_event_writer(event)
    except Exception as error:  # noqa: BLE001 - Postgres remains the authority
        logger.info(
            "provider_usage_event_publish_pending attempt_id=%s error_class=%s",
            attempt_id,
            type(error).__name__,
        )
        return
    accounting._mark_event(attempt_id, "published")


def purge_expired(accounting, *, limit: int) -> int:
    if not 1 <= limit <= 1000:
        raise ValueError("provider_usage_cleanup_limit_invalid")
    now = datetime.now(UTC)
    with accounting.database.transaction() as connection:
        rows = connection.execute(
            "WITH expired AS (SELECT invocation_id FROM provider_invocations "
            "WHERE retention_until<=%s ORDER BY retention_until,invocation_id "
            "LIMIT %s FOR UPDATE SKIP LOCKED) "
            "DELETE FROM provider_invocations i USING expired e "
            "WHERE i.invocation_id=e.invocation_id RETURNING i.invocation_id",
            (now, limit),
        ).fetchall()
        aggregates = connection.execute(
            "WITH expired AS (SELECT owner_id,application_id,workspace_id,usage_day,"
            "endpoint_profile_id,endpoint_profile_version,task_id,operation FROM provider_usage_daily_aggregates "
            "WHERE usage_day < %s::date ORDER BY usage_day LIMIT %s FOR UPDATE SKIP LOCKED) "
            "DELETE FROM provider_usage_daily_aggregates a USING expired e WHERE "
            "a.owner_id=e.owner_id AND a.application_id=e.application_id "
            "AND a.workspace_id IS NOT DISTINCT FROM e.workspace_id AND a.usage_day=e.usage_day "
            "AND a.endpoint_profile_id=e.endpoint_profile_id AND a.task_id=e.task_id "
            "AND a.endpoint_profile_version IS NOT DISTINCT FROM e.endpoint_profile_version "
            "AND a.operation=e.operation RETURNING a.usage_day",
            (now.date() - timedelta(days=accounting.retention_days), limit),
        ).fetchall()
        windows = connection.execute(
            "WITH expired AS (SELECT b.bucket_id,b.window_start "
            "FROM provider_quota_bucket_windows b WHERE b.window_start < %s "
            "AND (b.reset_at IS NULL OR b.reset_at <= %s) "
            "AND NOT EXISTS (SELECT 1 FROM provider_quota_reservations r "
            "WHERE r.bucket_id=b.bucket_id AND r.window_start=b.window_start) "
            "ORDER BY b.window_start,b.bucket_id LIMIT %s FOR UPDATE SKIP LOCKED) "
            "DELETE FROM provider_quota_bucket_windows b USING expired e "
            "WHERE b.bucket_id=e.bucket_id AND b.window_start=e.window_start "
            "RETURNING b.bucket_id",
            (now - timedelta(days=accounting.retention_days), now, limit),
        ).fetchall()
        health = connection.execute(
            "WITH expired AS (SELECT h.endpoint_profile_id,h.endpoint_profile_version "
            "FROM provider_endpoint_health h WHERE h.updated_at < %s "
            "AND NOT EXISTS (SELECT 1 FROM provider_invocations i "
            "WHERE i.endpoint_profile_id=h.endpoint_profile_id "
            "AND i.endpoint_profile_version=h.endpoint_profile_version "
            "AND i.started_at >= %s) ORDER BY h.updated_at LIMIT %s FOR UPDATE SKIP LOCKED) "
            "DELETE FROM provider_endpoint_health h USING expired e "
            "WHERE h.endpoint_profile_id=e.endpoint_profile_id "
            "AND h.endpoint_profile_version=e.endpoint_profile_version "
            "RETURNING h.endpoint_profile_id",
            (
                now - timedelta(days=accounting.retention_days),
                now - timedelta(days=accounting.retention_days),
                limit,
            ),
        ).fetchall()
    removed = len(rows) + len(aggregates) + len(windows) + len(health)
    if accounting.operational_event_purger is not None:
        removed += accounting.operational_event_purger(now, min(limit, 100))
    return removed


def reconcile_operational_events(accounting, *, limit: int) -> int:
    if accounting.operational_event_writer is None:
        return 0
    if not 1 <= limit <= 100:
        raise ValueError("provider_usage_reconcile_limit_invalid")
    with accounting.database.connection() as connection:
        rows = connection.execute(
            "SELECT i.invocation_id,i.owner_id,i.application_id,i.workspace_id,i.task_id,"
            "i.operation,i.request_id,i.run_id,i.endpoint_profile_id,i.endpoint_profile_version,"
            "i.provider_id,i.model_id,i.endpoint_id,i.deployment_id,i.credential_source,"
            "i.credential_scope_id,i.account_scope_id,i.project_scope_id,i.tier_id,"
            "i.execution_mode,i.cost_class,i.billing_owner,i.serializer_id,i.runtime_id,"
            "i.quota_membership,"
            "i.routing_decision_id,i.routing_strategy_id,i.routing_strategy_version,"
            "i.registry_version,i.policy_version,"
            "a.attempt_id,a.parent_attempt_id,a.send_number,a.status,a.error_code,a.http_status,"
            "a.started_at,a.completed_at,a.latency_ms,a.input_tokens,a.output_tokens,a.total_tokens,"
            "a.usage_source,a.usage_confidence,a.unit_usage,a.unit_usage_source,"
            "a.unit_usage_confidence,a.rate_limit_facts "
            "FROM provider_attempts a JOIN provider_invocations i USING(invocation_id) "
            "WHERE a.operational_event_status='pending' AND a.status <> 'pending' "
            "ORDER BY a.started_at,a.attempt_id LIMIT %s",
            (limit,),
        ).fetchall()
    published = 0
    for row in rows:
        event = _event_from_row(row)
        attempt_id = UUID(str(event["attempt_id"]))
        try:
            accounting.operational_event_writer(event)
        except Exception as error:  # noqa: BLE001 - retry on the next bounded maintenance pass
            logger.info(
                "provider_usage_event_replay_failed attempt_id=%s error_class=%s",
                attempt_id,
                type(error).__name__,
            )
            continue
        accounting._mark_event(attempt_id, "published")
        published += 1
    return published


def resolve_stale_attempts(accounting, *, limit: int) -> int:
    """Fence sends orphaned by process death as unknown and retain their reserves."""
    if not 1 <= limit <= 100:
        raise ValueError("provider_usage_stale_attempt_limit_invalid")
    now = datetime.now(UTC)
    cutoff = now - timedelta(seconds=accounting.stale_attempt_seconds)
    with accounting.database.transaction() as connection:
        rows = connection.execute(
            "SELECT i.invocation_id,i.owner_id,i.application_id,i.workspace_id,i.task_id,"
            "i.operation,i.provider_id,i.model_id,i.endpoint_profile_id,a.attempt_id,"
            "i.endpoint_profile_version,"
            "a.parent_attempt_id,a.started_at FROM provider_attempts a "
            "JOIN provider_invocations i USING(invocation_id) WHERE a.status='pending' "
            "AND a.started_at<=%s ORDER BY a.started_at,a.attempt_id LIMIT %s "
            "FOR UPDATE OF a SKIP LOCKED",
            (cutoff, limit),
        ).fetchall()
        for row in rows:
            (
                invocation_id,
                owner_id,
                application_id,
                workspace_id,
                task_id,
                operation,
                provider_id,
                model_id,
                endpoint_profile_id,
                attempt_id,
                endpoint_profile_version,
                parent_attempt_id,
                started_at,
            ) = row
            latency = max(0, int((now - started_at).total_seconds() * 1000))
            connection.execute(
                "UPDATE provider_attempts SET status='unknown',error_code='provider_outcome_unknown',"
                "completed_at=%s,latency_ms=%s,usage_source='unknown',usage_confidence='unknown' "
                "WHERE attempt_id=%s AND status='pending'",
                (now, latency, attempt_id),
            )
            reservations = connection.execute(
                "SELECT bucket_id,window_start,reserved_units,state FROM provider_quota_reservations "
                "WHERE attempt_id=%s FOR UPDATE",
                (attempt_id,),
            ).fetchall()
            for bucket_id, window_start, amount, state in reservations:
                if state in {"reserved", "unknown"}:
                    connection.execute(
                        "UPDATE provider_quota_bucket_windows SET reserved_units=GREATEST(0,"
                        "reserved_units-%s),consumed_units=consumed_units+%s,updated_at=%s "
                        "WHERE bucket_id=%s AND window_start=%s",
                        (amount, amount, now, bucket_id, window_start),
                    )
                connection.execute(
                    "UPDATE provider_quota_reservations SET settled_units=%s,state='uncertain',"
                    "updated_at=%s WHERE attempt_id=%s AND bucket_id=%s",
                    (amount, now, attempt_id, bucket_id),
                )
            connection.execute(
                "UPDATE provider_invocations SET outcome='unknown',completed_at=%s "
                "WHERE invocation_id=%s AND NOT EXISTS (SELECT 1 FROM provider_attempts "
                "WHERE invocation_id=%s AND status='pending')",
                (now, invocation_id, invocation_id),
            )
            invocation = _aggregate_identity(
                owner_id,
                application_id,
                workspace_id,
                task_id,
                operation,
                provider_id,
                model_id,
                endpoint_profile_id,
                endpoint_profile_version,
            )
            _aggregate_attempt(
                connection,
                invocation,
                SimpleNamespace(parent_attempt_id=parent_attempt_id),
                "unknown",
                latency,
                0,
                0,
                "unknown",
                now,
            )
    return len(rows)

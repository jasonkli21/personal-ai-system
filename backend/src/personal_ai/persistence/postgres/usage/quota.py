"""Postgres provider usage quota persistence helpers."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from personal_ai.usage.contracts import AttemptResult
from personal_ai.usage.quota import QuotaObservation as QuotaBucket

_QUOTA_EPOCH = datetime(1970, 1, 1, tzinfo=UTC)


def _actual_unit_usage(unit: str, result: AttemptResult) -> int | None:
    normalized = unit.strip().lower().replace("/", "_").replace("-", "_")
    if "request" in normalized or normalized in {"calls", "call", "provider_calls"}:
        return 1
    if "input" in normalized and "token" in normalized:
        return result.input_tokens if result.usage_confidence == "exact" else None
    if "output" in normalized and "token" in normalized:
        return result.output_tokens if result.usage_confidence == "exact" else None
    if "token" in normalized:
        return result.total_tokens if result.usage_confidence == "exact" else None
    if result.unit_usage_confidence == "exact":
        unit_usage = {
            name.strip().lower().replace("/", "_").replace("-", "_"): value
            for name, value in result.unit_usage
        }
        return unit_usage.get(normalized)
    return None


def _applicable_buckets(buckets: tuple[QuotaBucket, ...], operation: str):
    return tuple(
        sorted(
            (bucket for bucket in buckets if operation in bucket.operations),
            key=lambda bucket: bucket.bucket_id,
        )
    )


def _bucket_confidence(bucket: QuotaBucket) -> str:
    if bucket.confidence == "unknown":
        return "unknown"
    if bucket.source == "provider_headers":
        return "exact"
    return "configured"


def _lock_or_seed_bucket(connection, bucket, window_start, reset_at, confidence, now):
    source = bucket.source
    observed_at = bucket.observed_at
    fresh_until = bucket.fresh_until
    if confidence == "unknown":
        source = "unknown" if bucket.source == "unknown" else bucket.source
    connection.execute(
        "INSERT INTO provider_quota_bucket_windows(bucket_id,authority_scope_id,unit,window_start,"
        "window_seconds,reset_at,source,confidence,evidence_reference,limit_units,reported_remaining,"
        "observed_at,fresh_until,updated_at) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT(bucket_id,window_start) DO NOTHING",
        (
            bucket.bucket_id,
            bucket.authority_scope_id,
            bucket.unit,
            window_start,
            bucket.window_seconds,
            reset_at,
            source,
            confidence,
            bucket.evidence_reference,
            bucket.limit,
            bucket.remaining,
            observed_at,
            fresh_until,
            now,
        ),
    )
    existing = connection.execute(
        "SELECT authority_scope_id,unit,window_seconds,reset_at,observed_at,source,confidence,"
        "limit_units,reported_remaining,consumed_units,reserved_units "
        "FROM provider_quota_bucket_windows "
        "WHERE bucket_id=%s AND window_start=%s FOR UPDATE",
        (bucket.bucket_id, window_start),
    ).fetchone()
    if existing is None:
        raise RuntimeError("provider_quota_bucket_state_missing")
    if existing[0] != bucket.authority_scope_id or existing[1] != bucket.unit:
        raise ValueError("provider_quota_bucket_identity_conflict")
    if (
        bucket.window_seconds is not None
        and existing[2] is not None
        and bucket.window_seconds != existing[2]
    ) or (bucket.reset_at is not None and existing[3] != bucket.reset_at):
        raise ValueError("provider_quota_window_identity_conflict")
    if observed_at is not None and (existing[4] is None or observed_at > existing[4]):
        connection.execute(
            "UPDATE provider_quota_bucket_windows SET source=%s,confidence=%s,evidence_reference=%s,"
            "limit_units=%s,reported_remaining=%s,observed_at=%s,fresh_until=%s,"
            "reset_at=COALESCE(%s,reset_at),updated_at=%s WHERE bucket_id=%s AND window_start=%s",
            (
                source,
                confidence,
                bucket.evidence_reference,
                bucket.limit,
                bucket.remaining,
                observed_at,
                fresh_until,
                reset_at,
                now,
                bucket.bucket_id,
                window_start,
            ),
        )
        return
    if existing[5] == "provider_headers":
        if bucket.limit is not None:
            connection.execute(
                "UPDATE provider_quota_bucket_windows SET limit_units=CASE WHEN limit_units IS NULL "
                "THEN %s ELSE LEAST(limit_units,%s) END,updated_at=%s WHERE bucket_id=%s AND window_start=%s",
                (bucket.limit, bucket.limit, now, bucket.bucket_id, window_start),
            )
        return
    if (
        source in {"operator_attestation", "provider_contract"}
        and confidence != "unknown"
        and (bucket.limit is not None or bucket.remaining is not None)
    ):
        # A live config correction can lower this window immediately. A higher
        # limit never restores capacity already constrained by an older fact
        # or provider remaining observation; it can take effect next window.
        existing_limit = existing[7]
        existing_remaining = existing[8]
        used = int(existing[9]) + int(existing[10])
        conservative_total = existing_limit
        if existing_remaining is not None:
            remaining_total = used + int(existing_remaining)
            conservative_total = (
                remaining_total
                if conservative_total is None
                else min(int(conservative_total), remaining_total)
            )
        if bucket.limit is not None:
            conservative_total = (
                int(bucket.limit)
                if conservative_total is None
                else min(int(conservative_total), int(bucket.limit))
            )
        if bucket.remaining is not None:
            remaining_total = used + int(bucket.remaining)
            conservative_total = (
                remaining_total
                if conservative_total is None
                else min(int(conservative_total), remaining_total)
            )
        connection.execute(
            "UPDATE provider_quota_bucket_windows SET source=%s,confidence=%s,evidence_reference=%s,"
            "limit_units=%s,reported_remaining=NULL,observed_at=NULL,fresh_until=NULL,"
            "window_seconds=COALESCE(%s,window_seconds),reset_at=COALESCE(%s,reset_at),updated_at=%s "
            "WHERE bucket_id=%s AND window_start=%s",
            (
                source,
                confidence,
                bucket.evidence_reference,
                conservative_total,
                bucket.window_seconds,
                reset_at,
                now,
                bucket.bucket_id,
                window_start,
            ),
        )


def _quota_window(bucket: QuotaBucket, now: datetime):
    confidence = _bucket_confidence(bucket)
    reset_at = bucket.reset_at
    window = bucket.window_seconds
    if _unknown_daily_bucket(bucket):
        return _utc_day_start(now), None, "unknown"
    if reset_at is not None and window is not None and reset_at <= now:
        periods = int((now - reset_at).total_seconds() // window) + 1
        reset_at = reset_at + timedelta(seconds=periods * window)
        window_start = reset_at - timedelta(seconds=window)
        if confidence != "unknown":
            confidence = "derived"
    elif reset_at is not None and window is not None:
        window_start = reset_at - timedelta(seconds=window)
    else:
        # A configured duration supplies a derived rolling window. A snapshot
        # without duration keeps its original period and becomes unknown on expiry.
        window_start = bucket.observed_at or now
        if reset_at is None and window is not None:
            reset_at = window_start + timedelta(seconds=window)
            if confidence != "unknown":
                confidence = "derived"
    if bucket.fresh_until is not None and bucket.fresh_until <= now:
        confidence = "unknown"
    if reset_at is not None and reset_at <= now and bucket.reset_at is None:
        confidence = "unknown"
    return window_start.astimezone(UTC), reset_at, confidence


def _record_header_observation(
    connection,
    *,
    bucket_id,
    authority_scope,
    unit,
    window_start,
    result,
    observed_at,
    freshness_seconds,
):
    limits = result.rate_limits
    if limits is None:
        return
    normalized = unit.strip().lower().replace("/", "_").replace("-", "_")
    is_request = "request" in normalized or normalized in {"calls", "call", "provider_calls"}
    is_token = "token" in normalized
    if is_request:
        limit, remaining, reset = (
            limits.requests_limit,
            limits.requests_remaining,
            limits.requests_reset_seconds,
        )
    elif is_token:
        limit, remaining, reset = (
            limits.tokens_limit,
            limits.tokens_remaining,
            limits.tokens_reset_seconds,
        )
    else:
        return
    if limit is None and remaining is None:
        return
    reset_at = observed_at + timedelta(seconds=reset) if reset is not None else None
    fresh_until = observed_at + timedelta(seconds=freshness_seconds)
    connection.execute(
        "UPDATE provider_quota_bucket_windows SET source='provider_headers',confidence='exact',"
        "limit_units=COALESCE(%s,limit_units),reported_remaining=%s,"
        "observed_at=%s,fresh_until=%s,reset_at=COALESCE(%s,reset_at),"
        "consumed_units=CASE WHEN %s IS NOT NULL THEN 0 ELSE consumed_units END,"
        "updated_at=%s WHERE bucket_id=%s AND authority_scope_id=%s AND unit=%s AND window_start=%s "
        "AND (observed_at IS NULL OR observed_at<=%s)",
        (
            limit,
            remaining,
            observed_at,
            fresh_until,
            reset_at,
            remaining,
            observed_at,
            bucket_id,
            authority_scope,
            unit,
            window_start,
            observed_at,
        ),
    )


def _reservation_amount(bucket: QuotaBucket, values: dict[str, int]) -> int | None:
    unit = bucket.unit
    normalized = unit.strip().lower().replace("/", "_").replace("-", "_")
    aliases = {
        "request": "requests",
        "request_count": "requests",
        "calls": "requests",
        "call": "requests",
        "provider_calls": "requests",
        "token": "tokens",
        "input_token": "input_tokens",
        "output_token": "output_tokens",
    }
    normalized = aliases.get(normalized, normalized)
    if normalized in values:
        return values[normalized]
    if "request" in normalized or normalized.endswith("_calls"):
        return values.get("requests")
    if "token" in normalized and "input" in normalized:
        return values.get("input_tokens")
    if "token" in normalized and "output" in normalized:
        return values.get("output_tokens")
    if "token" in normalized:
        return values.get("tokens")
    normalized_values = {
        name.strip().lower().replace("/", "_").replace("-", "_"): amount
        for name, amount in values.items()
    }
    return normalized_values.get(normalized, bucket.reservation_units_per_request)


def _same_shared_bucket_observation(left: QuotaBucket, right: QuotaBucket) -> bool:
    """Require one unambiguous static observation for a shared bucket ID."""
    fields = (
        "authority_scope_id",
        "unit",
        "window_seconds",
        "source",
        "confidence",
        "evidence_reference",
        "limit",
        "remaining",
        "observed_at",
        "fresh_until",
        "reset_at",
    )
    return all(getattr(left, name) == getattr(right, name) for name in fields)


def _select_quota_window(connection, bucket: QuotaBucket, now: datetime):
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"provider-quota:{bucket.bucket_id}",),
    )
    latest = connection.execute(
        "SELECT window_start,reset_at,authority_scope_id,unit,confidence,source,fresh_until "
        "FROM provider_quota_bucket_windows WHERE bucket_id=%s "
        "ORDER BY window_start DESC LIMIT 1 FOR UPDATE",
        (bucket.bucket_id,),
    ).fetchone()
    if latest is None:
        return _quota_window(bucket, now)
    window_start, reset_at, authority, unit, existing_confidence, existing_source, fresh_until = (
        latest
    )
    if authority != bucket.authority_scope_id or unit != bucket.unit:
        raise ValueError("provider_quota_bucket_identity_conflict")
    if _unknown_daily_bucket(bucket):
        if (
            existing_source == "provider_headers"
            and existing_confidence != "unknown"
            and (fresh_until is None or fresh_until > now)
            and (reset_at is None or reset_at > now)
        ):
            return window_start.astimezone(UTC), reset_at, existing_confidence
        return _utc_day_start(now), None, "unknown"
    if (
        bucket.observed_at is not None
        and reset_at is not None
        and bucket.reset_at is not None
        and bucket.observed_at > window_start
        and bucket.reset_at > now
    ):
        return (
            bucket.reset_at - timedelta(seconds=bucket.window_seconds or 0),
            bucket.reset_at,
            _bucket_confidence(bucket),
        )
    if reset_at is None or reset_at > now:
        confidence = (
            "unknown"
            if bucket.fresh_until is not None and bucket.fresh_until <= now
            else existing_confidence
        )
        return window_start.astimezone(UTC), reset_at, confidence
    if bucket.window_seconds is not None:
        periods = int((now - reset_at).total_seconds() // bucket.window_seconds) + 1
        next_reset = reset_at + timedelta(seconds=periods * bucket.window_seconds)
        return (
            next_reset - timedelta(seconds=bucket.window_seconds),
            next_reset,
            "derived" if existing_confidence != "unknown" else "unknown",
        )
    # An expired non-periodic snapshot cannot authorize an invented reset.
    return window_start.astimezone(UTC), reset_at, "unknown"


def _unknown_daily_bucket(bucket: QuotaBucket) -> bool:
    return (
        bucket.confidence == "unknown"
        and bucket.limit is None
        and bucket.remaining is None
        and bucket.window_seconds is None
        and bucket.reset_at is None
        and bucket.observed_at is None
    )


def _utc_day_start(value: datetime) -> datetime:
    value = value.astimezone(UTC)
    return value.replace(hour=0, minute=0, second=0, microsecond=0)

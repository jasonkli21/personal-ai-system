"""Public Postgres provider usage accounting façade."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import replace
from datetime import UTC, datetime, timedelta
from math import ceil
from uuid import UUID, uuid5

from personal_ai.persistence.postgres import PostgresDatabase, _ensure_namespace
from personal_ai.usage.accounting import unit_reservations
from personal_ai.usage.contracts import (
    AttemptMetadata,
    AttemptResult,
    InvocationMetadata,
    UsageAdmissionDenied,
)
from personal_ai.usage.quota import (
    EndpointRuntimeSnapshot,
    QuotaLedgerBucketSnapshot,
    QuotaReservationRequirement,
)

from . import retention
from .health import _health_unavailable, _lock_endpoint_health, _update_endpoint_health
from .ledger import (
    _aggregate_attempt,
    _bounded_text,
    _insert_attempt,
    _insert_invocation,
    _iso,
    _operational_event,
    _rate_limit_payload,
    _request_budget_scope,
    _safe_code,
    _scope,
)
from .quota import (
    _actual_unit_usage,
    _applicable_buckets,
    _lock_or_seed_bucket,
    _record_header_observation,
    _reservation_amount,
    _same_shared_bucket_observation,
    _select_quota_window,
)


class PostgresProviderUsageAccounting:
    """Postgres authority for reservations/settlements and compact daily totals."""

    def __init__(
        self,
        database: PostgresDatabase,
        *,
        retention_days: int = 90,
        request_attempt_limit: int = 64,
        request_token_limit: int = 200_000,
        default_cooldown_seconds: int = 60,
        header_freshness_seconds: int = 60,
        stale_attempt_seconds: int = 300,
        endpoint_profile_resolver=None,
        operational_event_writer: Callable[[dict], None] | None = None,
        operational_event_purger: Callable[[datetime, int], int] | None = None,
    ) -> None:
        self.database = database
        self.retention_days = retention_days
        self.request_attempt_limit = request_attempt_limit
        self.request_token_limit = request_token_limit
        self.default_cooldown_seconds = default_cooldown_seconds
        self.header_freshness_seconds = header_freshness_seconds
        self.stale_attempt_seconds = stale_attempt_seconds
        self.endpoint_profile_resolver = endpoint_profile_resolver
        self.operational_event_writer = operational_event_writer
        self.operational_event_purger = operational_event_purger

    def begin_invocation(self, invocation: InvocationMetadata) -> None:
        """Persist logical work even when setup fails before its first network send."""
        now = datetime.now(UTC)
        retention_until = now + timedelta(days=self.retention_days)
        with self.database.transaction() as connection:
            from personal_ai.persistence.postgres.owner_lifecycle import assert_owner_unfenced

            assert_owner_unfenced(connection, invocation.owner_id)
            scope_id = _ensure_namespace(
                connection,
                invocation.owner_id,
                _scope(invocation.application_id, invocation.workspace_id),
            )
            _insert_invocation(connection, invocation, scope_id, now, retention_until)

    def reserve_attempt(self, invocation, attempt, *, max_attempts):
        # Preserve a denied logical outcome while committing no physical attempt.
        denial = None
        with self.database.transaction() as connection:
            try:
                result = self.reserve_attempt_in_transaction(
                    connection, invocation, attempt, max_attempts=max_attempts
                )
            except UsageAdmissionDenied as error:
                denial = error
        if denial is not None:
            raise denial
        return result

    def assert_invocation_unstarted_in_transaction(self, connection, invocation):
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"provider-usage:{_request_budget_scope(invocation)}",),
        )
        if (
            connection.execute(
                "SELECT 1 FROM provider_attempts WHERE invocation_id=%s LIMIT 1",
                (invocation.invocation_id,),
            ).fetchone()
            is not None
        ):
            raise UsageAdmissionDenied("provider_invocation_already_started")

    def assert_request_budget_in_transaction(
        self, connection, invocation, *, max_reserved_tokens, quota_limits
    ):
        """Read canonical P19 reservations under the existing request lock.

        Count conservative original reservations, including failed/settled sends;
        quota reset never refunds the root operation's cumulative budget.
        """
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"provider-usage:{_request_budget_scope(invocation)}",),
        )
        units = dict(
            unit_reservations(
                input_tokens=invocation.input_tokens_estimate,
                output_tokens=invocation.output_tokens_bound,
            )
        )
        if any(
            _reservation_amount(bucket, units) is None
            for bucket in _applicable_buckets(
                invocation.endpoint.quota_buckets, invocation.operation
            )
        ):
            raise UsageAdmissionDenied("cascade_quota_units_unpriced")
        scope = (
            invocation.owner_id,
            invocation.application_id,
            invocation.workspace_id,
            invocation.request_id,
        )
        tokens = connection.execute(
            "SELECT COALESCE(sum(GREATEST(a.reserved_tokens,COALESCE(a.total_tokens,0),"
            "COALESCE(a.input_tokens,0)+COALESCE(a.output_tokens,0))),0) FROM provider_attempts a "
            "JOIN provider_invocations i USING(invocation_id) WHERE i.owner_id=%s "
            "AND i.application_id=%s AND i.workspace_id IS NOT DISTINCT FROM %s "
            "AND i.request_id=%s",
            scope,
        ).fetchone()[0]
        if tokens > max_reserved_tokens:
            raise UsageAdmissionDenied("cascade_token_budget_exceeded")
        rows = connection.execute(
            "SELECT r.bucket_id,sum(GREATEST(r.reserved_units,COALESCE(r.settled_units,0))) "
            "FROM provider_quota_reservations r "
            "JOIN provider_attempts a USING(attempt_id) "
            "JOIN provider_invocations i USING(invocation_id) WHERE i.owner_id=%s "
            "AND i.application_id=%s AND i.workspace_id IS NOT DISTINCT FROM %s "
            "AND i.request_id=%s GROUP BY r.bucket_id",
            scope,
        ).fetchall()
        if any(
            bucket not in quota_limits or units > quota_limits[bucket] for bucket, units in rows
        ):
            raise UsageAdmissionDenied("cascade_quota_budget_exceeded")

    def reserve_attempt_in_transaction(self, connection, invocation, attempt, *, max_attempts):
        """Small transaction-aware seam; caller owns commit, never provider IO."""
        now = attempt.started_at.astimezone(UTC)
        retention_until = now + timedelta(days=self.retention_days)
        endpoint = invocation.endpoint
        denial = None
        reserved_attempt = None
        selected_buckets = []
        from personal_ai.persistence.postgres.owner_lifecycle import (
            OwnerFenced,
            assert_owner_unfenced,
        )

        try:
            assert_owner_unfenced(connection, invocation.owner_id)
        except OwnerFenced:
            raise UsageAdmissionDenied("provider_owner_deletion_fenced") from None
        if self.endpoint_profile_resolver is not None and endpoint.credential_source != "none":
            try:
                self.endpoint_profile_resolver.assert_current_in_transaction(connection, endpoint)
            except ValueError:
                raise UsageAdmissionDenied("provider_endpoint_profile_stale") from None
        scope_id = _ensure_namespace(
            connection,
            invocation.owner_id,
            _scope(invocation.application_id, invocation.workspace_id),
        )
        request_scope = _request_budget_scope(invocation)
        connection.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
            (f"provider-usage:{request_scope}",),
        )
        _insert_invocation(connection, invocation, scope_id, now, retention_until)

        unresolved = connection.execute(
            "SELECT 1 FROM provider_attempts a JOIN provider_invocations i USING(invocation_id) "
            "WHERE i.owner_id=%s AND i.application_id=%s "
            "AND i.workspace_id IS NOT DISTINCT FROM %s AND i.request_id=%s "
            "AND a.status IN ('pending','unknown','timeout') LIMIT 1",
            (
                invocation.owner_id,
                invocation.application_id,
                invocation.workspace_id,
                invocation.request_id,
            ),
        ).fetchone()
        if unresolved is not None:
            denial = "provider_outcome_unresolved"

        attempt_count, reserved_tokens = connection.execute(
            "SELECT count(*),COALESCE(sum(reserved_tokens),0) "
            "FROM provider_attempts a JOIN provider_invocations i USING (invocation_id) "
            "WHERE i.owner_id=%s AND i.application_id=%s "
            "AND i.workspace_id IS NOT DISTINCT FROM %s AND i.request_id=%s",
            (
                invocation.owner_id,
                invocation.application_id,
                invocation.workspace_id,
                invocation.request_id,
            ),
        ).fetchone()
        call_tokens = max(0, attempt.reserved_tokens)
        if denial is None and attempt_count >= min(max_attempts, self.request_attempt_limit):
            denial = "provider_attempt_budget_exceeded"
        elif denial is None and reserved_tokens + call_tokens > self.request_token_limit:
            denial = "provider_token_budget_exceeded"

        previous_attempt = connection.execute(
            "SELECT attempt_id,send_number FROM provider_attempts "
            "WHERE invocation_id=%s ORDER BY send_number DESC LIMIT 1 FOR UPDATE",
            (invocation.invocation_id,),
        ).fetchone()
        expected_send_number = int(previous_attempt[1]) + 1 if previous_attempt else 1
        expected_parent_id = previous_attempt[0] if previous_attempt else None
        reserved_attempt = (
            attempt
            if (
                attempt.send_number == expected_send_number
                and attempt.parent_attempt_id == expected_parent_id
            )
            else replace(
                attempt,
                attempt_id=uuid5(
                    invocation.invocation_id,
                    f"provider-attempt:{expected_send_number}",
                ),
                parent_attempt_id=expected_parent_id,
                send_number=expected_send_number,
            )
        )

        applicable_buckets = _applicable_buckets(endpoint.quota_buckets, invocation.operation)
        if denial is None:
            if endpoint.quota_membership == "ambiguous":
                denial = "provider_quota_membership_ambiguous"
            elif endpoint.quota_membership != "verified" or not applicable_buckets:
                denial = "provider_quota_membership_unknown"

        if denial is None:
            for bucket in sorted(applicable_buckets, key=lambda b: b.bucket_id):
                amount = _reservation_amount(bucket, dict(attempt.reservation_units))
                window_start, reset_at, confidence = _select_quota_window(connection, bucket, now)
                _lock_or_seed_bucket(connection, bucket, window_start, reset_at, confidence, now)
                state = connection.execute(
                    "SELECT authority_scope_id,unit,window_seconds,reset_at,source,confidence,"
                    "limit_units,reported_remaining,observed_at,fresh_until,consumed_units,reserved_units "
                    "FROM provider_quota_bucket_windows WHERE bucket_id=%s AND window_start=%s "
                    "FOR UPDATE",
                    (bucket.bucket_id, window_start),
                ).fetchone()
                if state is None:
                    raise RuntimeError("provider_quota_bucket_state_missing")
                (
                    authority_scope,
                    unit,
                    _window_seconds,
                    state_reset,
                    _source,
                    state_confidence,
                    limit_units,
                    reported_remaining,
                    _observed_at,
                    fresh_until,
                    consumed,
                    reserved,
                ) = state
                if authority_scope != bucket.authority_scope_id or unit != bucket.unit:
                    raise ValueError("provider_quota_bucket_identity_conflict")
                capacity_known = (
                    state_confidence != "unknown"
                    and (limit_units is not None or reported_remaining is not None)
                    and (fresh_until is None or fresh_until > now)
                    and (state_reset is None or state_reset > now)
                )
                if capacity_known and amount is None:
                    denial = "provider_quota_unit_unpriced"
                elif capacity_known and amount is not None:
                    limits = []
                    if limit_units is not None:
                        limits.append(int(limit_units) - int(consumed) - int(reserved))
                    if reported_remaining is not None:
                        limits.append(int(reported_remaining) - int(consumed) - int(reserved))
                    if limits and min(limits) < amount:
                        denial = "provider_quota_exhausted"
                selected_buckets.append((bucket, window_start, amount, state_confidence))
                if denial is not None:
                    break

        # Settlement locks bucket windows before health. Follow the same order,
        # including across different owners sharing one endpoint/quota scope.
        _lock_endpoint_health(connection, endpoint)
        health = connection.execute(
            "SELECT health_status,cooldown_until FROM provider_endpoint_health "
            "WHERE endpoint_profile_id=%s AND endpoint_profile_version=%s FOR SHARE",
            (endpoint.endpoint_profile_id, endpoint.profile_version),
        ).fetchone()
        if denial is None and _health_unavailable(health, now):
            denial = "provider_endpoint_cooling_down"

        if denial is not None:
            # Denied admission did not dispatch a physical provider send.
            # Keep the logical outcome without inflating attempt/retry counts.
            connection.execute(
                "UPDATE provider_invocations SET outcome='rejected',"
                "completed_at=GREATEST(%s,started_at) "
                "WHERE invocation_id=%s AND outcome='running'",
                (now, invocation.invocation_id),
            )
        else:
            quota_confidences = {item[3] for item in selected_buckets}
            quota_confidence = (
                "unknown"
                if not selected_buckets or "unknown" in quota_confidences
                else "configured"
            )
            connection.execute(
                "UPDATE provider_invocations SET quota_confidence=%s WHERE invocation_id=%s",
                (quota_confidence, invocation.invocation_id),
            )
            connection.execute(
                "UPDATE provider_invocations SET outcome='running',completed_at=NULL "
                "WHERE invocation_id=%s",
                (invocation.invocation_id,),
            )
            _insert_attempt(
                connection,
                invocation,
                reserved_attempt,
                call_tokens,
                retention_until,
                status="pending",
                error_code=None,
            )
            for bucket, window_start, amount, confidence in selected_buckets:
                is_known = confidence != "unknown" and amount is not None
                reserved_amount = amount or 0
                connection.execute(
                    "INSERT INTO provider_quota_reservations(attempt_id,bucket_id,"
                    "authority_scope_id,unit,window_start,reserved_units,settled_units,state,"
                    "confidence,created_at,updated_at) VALUES (%s,%s,%s,%s,%s,%s,NULL,%s,%s,%s,%s)",
                    (
                        reserved_attempt.attempt_id,
                        bucket.bucket_id,
                        bucket.authority_scope_id,
                        bucket.unit,
                        window_start,
                        reserved_amount,
                        "reserved" if is_known else "unknown",
                        confidence,
                        now,
                        now,
                    ),
                )
                if reserved_amount:
                    connection.execute(
                        "UPDATE provider_quota_bucket_windows SET reserved_units=reserved_units+%s,"
                        "updated_at=%s WHERE bucket_id=%s AND window_start=%s",
                        (reserved_amount, now, bucket.bucket_id, window_start),
                    )
        if denial is not None:
            raise UsageAdmissionDenied(denial)
        if reserved_attempt is None:
            raise RuntimeError("provider_usage_attempt_not_reserved")
        return reserved_attempt

    def routing_snapshot(
        self,
        connection,
        profile,
        requirements,
        *,
        operation=None,
        now,
        check_capacity=True,
    ):
        """Single-profile adapter over the batch lock-order authority."""
        if operation is None:
            operations = requirements.required_capabilities
            if len(operations) != 1:
                raise ValueError("provider_usage_operation_required")
            operation = next(iter(operations))
        return self.routing_snapshots(
            connection,
            (profile,),
            requirements,
            operation=operation,
            now=now,
            check_capacity=check_capacity,
        )[profile.endpoint_profile_id]

    def routing_snapshots(
        self,
        connection,
        profiles,
        requirements,
        *,
        operation,
        now,
        check_capacity=True,
    ):
        """Project candidate runtime state after acquiring a global P19 lock order.

        Every canonical quota window is seeded/read once in bucket-ID order.
        Endpoint health locks follow in profile-ID/version order, matching P19
        reservation and settlement ordering. Candidate-specific reservation
        amounts are returned separately from shared mutable bucket state.
        """
        from personal_ai.usage.profiles import from_profile

        profiles = tuple(
            sorted(profiles, key=lambda row: (row.endpoint_profile_id, row.profile_version))
        )
        if operation not in requirements.required_capabilities:
            raise ValueError("provider_usage_operation_not_required")
        reasons_by_profile = {profile.endpoint_profile_id: [] for profile in profiles}
        buckets_by_profile = {}
        requirements_by_profile = {}
        canonical_buckets = {}
        values = dict(
            unit_reservations(
                input_tokens=requirements.input_tokens, output_tokens=requirements.output_tokens
            )
        )
        for profile in profiles:
            endpoint = from_profile(profile)
            applicable = (
                _applicable_buckets(endpoint.quota_buckets, operation) if check_capacity else ()
            )
            buckets_by_profile[profile.endpoint_profile_id] = applicable
            if check_capacity:
                if endpoint.quota_membership == "ambiguous":
                    reasons_by_profile[profile.endpoint_profile_id].append(
                        "provider_quota_membership_ambiguous"
                    )
                elif endpoint.quota_membership != "verified" or not applicable:
                    reasons_by_profile[profile.endpoint_profile_id].append(
                        "provider_quota_membership_unknown"
                    )
            edge_requirements = []
            for bucket in applicable:
                prior = canonical_buckets.get(bucket.bucket_id)
                if prior is not None and not _same_shared_bucket_observation(prior, bucket):
                    raise ValueError("provider_quota_snapshot_conflict")
                canonical_buckets.setdefault(bucket.bucket_id, bucket)
                edge_requirements.append(
                    QuotaReservationRequirement(
                        bucket_id=bucket.bucket_id,
                        reservation_units=_reservation_amount(bucket, values),
                    )
                )
            requirements_by_profile[profile.endpoint_profile_id] = tuple(edge_requirements)

        shared_snapshots = {}
        if check_capacity:
            for bucket_id in sorted(canonical_buckets):
                bucket = canonical_buckets[bucket_id]
                start, reset, window_confidence = _select_quota_window(connection, bucket, now)
                _lock_or_seed_bucket(connection, bucket, start, reset, window_confidence, now)
                row = connection.execute(
                    "SELECT authority_scope_id,unit,window_seconds,reset_at,source,confidence,"
                    "evidence_reference,limit_units,reported_remaining,observed_at,fresh_until,"
                    "consumed_units,reserved_units FROM provider_quota_bucket_windows "
                    "WHERE bucket_id=%s AND window_start=%s FOR UPDATE",
                    (bucket_id, start),
                ).fetchone()
                if row is None:
                    raise RuntimeError("provider_quota_state_missing")
                (
                    authority_scope,
                    unit,
                    window_seconds,
                    reset_at,
                    source,
                    confidence,
                    evidence_reference,
                    limit_units,
                    reported_remaining,
                    observed_at,
                    fresh_until,
                    consumed,
                    reserved,
                ) = row
                if authority_scope != bucket.authority_scope_id or unit != bucket.unit:
                    raise ValueError("provider_quota_bucket_identity_conflict")
                known = (
                    confidence != "unknown"
                    and (limit_units is not None or reported_remaining is not None)
                    and (fresh_until is None or fresh_until > now)
                    and (reset_at is None or reset_at > now)
                )
                limits = []
                if limit_units is not None:
                    limits.append(int(limit_units) - int(consumed) - int(reserved))
                if reported_remaining is not None:
                    limits.append(int(reported_remaining) - int(consumed) - int(reserved))
                remaining_units = max(0, min(limits)) if known and limits else None
                shared_snapshots[bucket_id] = QuotaLedgerBucketSnapshot(
                    bucket_id=bucket_id,
                    unit=unit,
                    window_seconds=window_seconds,
                    window_start=start,
                    reset_at=reset_at,
                    time_to_reset_seconds=(
                        min(31_536_000, max(0, ceil((reset_at - now).total_seconds())))
                        if known and reset_at is not None
                        else None
                    ),
                    source=source,
                    confidence=confidence if known else "unknown",
                    evidence_reference=evidence_reference,
                    limit_units=int(limit_units) if limit_units is not None else None,
                    reported_remaining_units=(
                        int(reported_remaining) if reported_remaining is not None else None
                    ),
                    consumed_units=int(consumed),
                    reserved_units=int(reserved),
                    remaining_units=remaining_units,
                    observed_at=observed_at,
                    fresh_until=fresh_until,
                )
            for profile_id, bucket_requirements in requirements_by_profile.items():
                for requirement in bucket_requirements:
                    snapshot = shared_snapshots[requirement.bucket_id]
                    if snapshot.confidence != "unknown" and requirement.reservation_units is None:
                        reasons_by_profile[profile_id].append("provider_quota_unit_unpriced")
                    elif (
                        snapshot.remaining_units is not None
                        and requirement.reservation_units is not None
                        and snapshot.remaining_units < requirement.reservation_units
                    ):
                        reasons_by_profile[profile_id].append("endpoint_quota_exhausted")

        # Do not interleave endpoint locks with bucket locks. Settlement updates
        # quota rows first, then health, so every participant sees the same order.
        health_by_profile = {}
        for profile in profiles:
            endpoint = from_profile(profile)
            if check_capacity:
                _lock_endpoint_health(connection, endpoint)
                query = (
                    "SELECT health_status,cooldown_until,failure_streak FROM provider_endpoint_health "
                    "WHERE endpoint_profile_id=%s AND endpoint_profile_version=%s FOR SHARE"
                )
            else:
                # The following P19 reservation owns the locked health check;
                # this advisory read must not invert bucket-before-health order.
                query = (
                    "SELECT health_status,cooldown_until,failure_streak FROM provider_endpoint_health "
                    "WHERE endpoint_profile_id=%s AND endpoint_profile_version=%s"
                )
            health = connection.execute(
                query, (profile.endpoint_profile_id, profile.profile_version)
            ).fetchone()
            health_by_profile[profile.endpoint_profile_id] = health
            if health is not None and _health_unavailable(health[:2], now):
                reasons_by_profile[profile.endpoint_profile_id].append(
                    "endpoint_health_unavailable"
                )

        return {
            profile.endpoint_profile_id: EndpointRuntimeSnapshot(
                health_status=(
                    health_by_profile[profile.endpoint_profile_id][0]
                    if health_by_profile[profile.endpoint_profile_id] is not None
                    else "unobserved"
                ),
                cooldown_until=(
                    health_by_profile[profile.endpoint_profile_id][1]
                    if health_by_profile[profile.endpoint_profile_id] is not None
                    else None
                ),
                failure_streak=(
                    int(health_by_profile[profile.endpoint_profile_id][2])
                    if health_by_profile[profile.endpoint_profile_id] is not None
                    else 0
                ),
                quota_buckets=tuple(
                    shared_snapshots[bucket.bucket_id]
                    for bucket in buckets_by_profile[profile.endpoint_profile_id]
                    if bucket.bucket_id in shared_snapshots
                ),
                rejection_reasons=tuple(
                    dict.fromkeys(reasons_by_profile[profile.endpoint_profile_id])
                ),
                quota_requirements=requirements_by_profile[profile.endpoint_profile_id],
            )
            for profile in profiles
        }

    def runtime_rejections(
        self, connection, profile, requirements, *, now, check_capacity=True, operation=None
    ):
        """Current runtime hard-admission reasons, projected from the P19 ledger."""
        return self.routing_snapshot(
            connection,
            profile,
            requirements,
            operation=operation,
            now=now,
            check_capacity=check_capacity,
        ).rejection_reasons

    def reserved_attempt_in_transaction(
        self, connection, invocation, attempt_id, *, expected_units, max_attempts, now
    ):
        """Resolve exact provenance directly, with the attempt locked against settlement."""
        endpoint = invocation.endpoint
        row = connection.execute(
            "SELECT i.owner_id,i.application_id,i.workspace_id,i.request_id,i.run_id,"
            "i.routing_decision_id,i.endpoint_profile_id,i.endpoint_profile_version,i.operation,"
            "i.outcome,a.started_at,a.status,a.send_number,a.parent_attempt_id,a.reserved_tokens,"
            "a.dispatch_claimed_at FROM provider_invocations i JOIN provider_attempts a USING(invocation_id) "
            "WHERE i.invocation_id=%s AND a.attempt_id=%s FOR UPDATE OF a FOR SHARE OF i",
            (invocation.invocation_id, attempt_id),
        ).fetchone()
        expected = (
            invocation.owner_id,
            invocation.application_id,
            invocation.workspace_id,
            invocation.request_id,
            invocation.run_id,
            invocation.routing_decision_id,
            endpoint.endpoint_profile_id,
            endpoint.profile_version,
            invocation.operation,
            "running",
        )
        if (
            row is None
            or row[:10] != expected
            or row[11] != "pending"
            or row[10] > now
            or (now - row[10]).total_seconds() >= self.stale_attempt_seconds
        ):
            raise UsageAdmissionDenied("routing_reservation_not_authoritative")
        if row[12] > max_attempts or row[12] < 1:
            raise UsageAdmissionDenied("routing_attempt_budget_invalid")
        if row[14] != dict(expected_units).get("tokens", 0):
            raise UsageAdmissionDenied("routing_attempt_budget_invalid")
        if row[12] == 1:
            if row[13] is not None:
                raise UsageAdmissionDenied("routing_attempt_lineage_invalid")
        else:
            previous = connection.execute(
                "SELECT attempt_id,status FROM provider_attempts "
                "WHERE invocation_id=%s AND send_number=%s FOR SHARE",
                (invocation.invocation_id, row[12] - 1),
            ).fetchone()
            if (
                previous is None
                or previous[0] != row[13]
                or previous[1] in {"pending", "unknown", "timeout"}
            ):
                raise UsageAdmissionDenied("routing_attempt_lineage_invalid")
        _insert_invocation(
            connection,
            invocation,
            _ensure_namespace(
                connection,
                invocation.owner_id,
                _scope(invocation.application_id, invocation.workspace_id),
            ),
            now,
            now + timedelta(days=self.retention_days),
        )
        buckets = connection.execute(
            "SELECT r.bucket_id,r.reserved_units,r.state,r.authority_scope_id,r.unit,"
            "w.authority_scope_id,w.unit FROM provider_quota_reservations r "
            "JOIN provider_quota_bucket_windows w USING(bucket_id,window_start) "
            "WHERE attempt_id=%s ORDER BY r.bucket_id FOR SHARE OF r,w",
            (attempt_id,),
        ).fetchall()
        bindings = {
            b.bucket_id: b for b in endpoint.quota_buckets if invocation.operation in b.operations
        }
        values = dict(expected_units)
        if not bindings or {b[0] for b in buckets} != set(bindings):
            raise UsageAdmissionDenied("routing_reservation_incomplete")
        for bucket_id, amount, state, authority, unit, window_authority, window_unit in buckets:
            binding = bindings[bucket_id]
            expected_amount = _reservation_amount(binding, values) or 0
            if (
                amount != expected_amount
                or state not in {"reserved", "unknown"}
                or authority != binding.authority_scope_id
                or window_authority != authority
                or unit != binding.unit
                or window_unit != unit
            ):
                raise UsageAdmissionDenied("routing_reservation_incomplete")
        _lock_endpoint_health(connection, endpoint)
        health = connection.execute(
            "SELECT health_status,cooldown_until FROM provider_endpoint_health "
            "WHERE endpoint_profile_id=%s AND endpoint_profile_version=%s FOR SHARE",
            (endpoint.endpoint_profile_id, endpoint.profile_version),
        ).fetchone()
        if _health_unavailable(health, now):
            raise UsageAdmissionDenied("provider_endpoint_cooling_down")
        return AttemptMetadata(
            attempt_id=attempt_id,
            parent_attempt_id=row[13],
            send_number=row[12],
            started_at=row[10],
            reservation_units=(),
            reserved_tokens=row[14],
        )

    def claim_attempt_in_transaction(self, connection, attempt_id, *, now):
        if (
            connection.execute(
                "UPDATE provider_attempts SET dispatch_claimed_at=%s WHERE attempt_id=%s "
                "AND status='pending' AND dispatch_claimed_at IS NULL RETURNING attempt_id",
                (now, attempt_id),
            ).fetchone()
            is None
        ):
            raise UsageAdmissionDenied("routing_dispatch_already_claimed")

    def attempt_outcome_in_transaction(self, connection, invocation_id, attempt_id):
        row = connection.execute(
            "SELECT status FROM provider_attempts WHERE invocation_id=%s AND attempt_id=%s FOR SHARE",
            (invocation_id, attempt_id),
        ).fetchone()
        if row is None or row[0] == "pending":
            raise UsageAdmissionDenied("provider_outcome_unresolved")
        return row[0]

    def settle_attempt(
        self,
        invocation: InvocationMetadata,
        attempt: AttemptMetadata,
        result: AttemptResult,
    ) -> None:
        completed = result.completed_at.astimezone(UTC)
        rate_limits = _rate_limit_payload(result)
        event: dict | None = None
        with self.database.transaction() as connection:
            previous = connection.execute(
                "SELECT status FROM provider_attempts WHERE attempt_id=%s FOR UPDATE",
                (attempt.attempt_id,),
            ).fetchone()
            if previous is None or previous[0] != "pending":
                return
            connection.execute(
                "UPDATE provider_attempts SET status=%s,error_code=%s,http_status=%s,"
                "completed_at=%s,latency_ms=%s,input_tokens=%s,output_tokens=%s,total_tokens=%s,"
                "usage_source=%s,usage_confidence=%s,unit_usage=%s::jsonb,unit_usage_source=%s,"
                "unit_usage_confidence=%s,rate_limit_facts=%s::jsonb "
                "WHERE attempt_id=%s",
                (
                    result.outcome,
                    _safe_code(result.error_code),
                    result.http_status,
                    completed,
                    max(0, result.latency_ms),
                    result.input_tokens,
                    result.output_tokens,
                    result.total_tokens,
                    _bounded_text(result.usage_source, 80),
                    result.usage_confidence,
                    json.dumps(dict(result.unit_usage), separators=(",", ":")),
                    _bounded_text(result.unit_usage_source, 80),
                    result.unit_usage_confidence,
                    json.dumps(rate_limits, separators=(",", ":")),
                    attempt.attempt_id,
                ),
            )
            rows = connection.execute(
                "SELECT bucket_id,authority_scope_id,unit,window_start,reserved_units,state "
                "FROM provider_quota_reservations WHERE attempt_id=%s ORDER BY bucket_id FOR UPDATE",
                (attempt.attempt_id,),
            ).fetchall()
            for bucket_id, authority, unit, window_start, reserved_units, state in rows:
                if state not in {"reserved", "unknown"}:
                    continue
                actual = _actual_unit_usage(unit, result)
                if actual is None:
                    actual = int(reserved_units)
                    reservation_state = "uncertain"
                else:
                    reservation_state = "settled"
                if state in {"reserved", "unknown"}:
                    connection.execute(
                        "UPDATE provider_quota_bucket_windows SET reserved_units=GREATEST(0,"
                        "reserved_units-%s),consumed_units=consumed_units+%s,updated_at=%s "
                        "WHERE bucket_id=%s AND window_start=%s",
                        (reserved_units, actual, completed, bucket_id, window_start),
                    )
                connection.execute(
                    "UPDATE provider_quota_reservations SET settled_units=%s,state=%s,updated_at=%s "
                    "WHERE attempt_id=%s AND bucket_id=%s",
                    (actual, reservation_state, completed, attempt.attempt_id, bucket_id),
                )
                _record_header_observation(
                    connection,
                    bucket_id=bucket_id,
                    authority_scope=authority,
                    unit=unit,
                    window_start=window_start,
                    result=result,
                    observed_at=completed,
                    freshness_seconds=self.header_freshness_seconds,
                )

            _update_endpoint_health(
                connection,
                invocation,
                result,
                completed,
                default_cooldown_seconds=self.default_cooldown_seconds,
            )
            _aggregate_attempt(
                connection,
                invocation,
                attempt,
                result.outcome,
                result.latency_ms,
                result.input_tokens or 0,
                result.output_tokens or 0,
                result.usage_confidence,
                completed,
            )
            event = _operational_event(invocation, attempt, result)

        if event is not None:
            self._publish_event(attempt.attempt_id, event)

    def complete_invocation(
        self,
        invocation: InvocationMetadata,
        *,
        outcome: str,
        completed_at: datetime,
    ) -> None:
        with self.database.transaction() as connection:
            connection.execute(
                "UPDATE provider_invocations SET outcome=%s,completed_at=%s "
                "WHERE invocation_id=%s AND outcome='running'",
                (outcome, completed_at.astimezone(UTC), invocation.invocation_id),
            )

    def summary(
        self, *, owner_id: str, application_id: str, workspace_id: str | None, days: int = 30
    ) -> dict:
        if not 1 <= days <= 90:
            raise ValueError("provider_usage_summary_days_invalid")
        since = datetime.now(UTC) - timedelta(days=days)
        with self.database.connection(snapshot=True) as connection:
            groups = connection.execute(
                "SELECT provider_id,model_id,endpoint_profile_id,endpoint_profile_version,task_id,operation,"
                "sum(attempts),sum(successes),sum(rate_limited),sum(server_errors),sum(failures),"
                "sum(retries),sum(latency_total_ms),sum(input_tokens),sum(output_tokens),"
                "sum(exact_usage_attempts),sum(derived_usage_attempts),sum(unknown_usage_attempts) "
                "FROM provider_usage_daily_aggregates WHERE owner_id=%s AND application_id=%s "
                "AND workspace_id IS NOT DISTINCT FROM %s AND usage_day >= %s::date "
                "GROUP BY provider_id,model_id,endpoint_profile_id,endpoint_profile_version,task_id,operation "
                "ORDER BY sum(attempts) DESC,provider_id,model_id,task_id LIMIT 64",
                (owner_id, application_id, workspace_id, since.date()),
            ).fetchall()
            endpoints = [row[2] for row in groups]
            health_rows = []
            quota_rows = []
            quota_endpoints: set[str] = set()
            if endpoints:
                health_rows = connection.execute(
                    "SELECT endpoint_profile_id,endpoint_profile_version,health_status,"
                    "failure_streak,cooldown_until,last_status,last_http_status,last_success_at,"
                    "last_failure_at,updated_at FROM provider_endpoint_health "
                    "WHERE endpoint_profile_id = ANY(%s) ORDER BY endpoint_profile_id,endpoint_profile_version",
                    (endpoints,),
                ).fetchall()
                quota_rows = connection.execute(
                    "SELECT DISTINCT b.bucket_id,b.authority_scope_id,b.unit,b.window_start,"
                    "b.window_seconds,b.reset_at,b.source,b.confidence,b.limit_units,"
                    "b.reported_remaining,b.observed_at,b.fresh_until "
                    "FROM provider_quota_reservations r "
                    "JOIN provider_attempts a USING(attempt_id) "
                    "JOIN provider_invocations i USING(invocation_id) "
                    "JOIN provider_quota_bucket_windows b USING(bucket_id,window_start) "
                    "WHERE i.owner_id=%s AND i.application_id=%s AND i.workspace_id IS NOT DISTINCT FROM %s "
                    "AND i.started_at >= %s ORDER BY b.bucket_id,b.window_start DESC LIMIT 32",
                    (owner_id, application_id, workspace_id, since),
                ).fetchall()
                quota_endpoints = {
                    row[0]
                    for row in connection.execute(
                        "SELECT DISTINCT i.endpoint_profile_id FROM provider_quota_reservations r "
                        "JOIN provider_attempts a USING(attempt_id) "
                        "JOIN provider_invocations i USING(invocation_id) WHERE i.owner_id=%s "
                        "AND i.application_id=%s AND i.workspace_id IS NOT DISTINCT FROM %s "
                        "AND i.started_at >= %s",
                        (owner_id, application_id, workspace_id, since),
                    ).fetchall()
                }
        return {
            "schema_version": "provider-usage-summary-v1",
            "owner_id": owner_id,
            "application_id": application_id,
            "workspace_id": workspace_id,
            "window_days": days,
            "generated_at": datetime.now(UTC).isoformat(),
            "groups": [
                {
                    "provider_id": row[0],
                    "model_id": row[1],
                    "endpoint_profile_id": row[2],
                    "endpoint_profile_version": row[3],
                    "task_id": row[4],
                    "operation": row[5],
                    "attempts": int(row[6] or 0),
                    "successes": int(row[7] or 0),
                    "rate_limited": int(row[8] or 0),
                    "server_errors": int(row[9] or 0),
                    "failures": int(row[10] or 0),
                    "retries": int(row[11] or 0),
                    "average_latency_ms": (
                        round(int(row[12] or 0) / int(row[6]), 1) if row[6] else None
                    ),
                    "input_tokens": int(row[13] or 0),
                    "output_tokens": int(row[14] or 0),
                    "exact_usage_attempts": int(row[15] or 0),
                    "derived_usage_attempts": int(row[16] or 0),
                    "unknown_usage_attempts": int(row[17] or 0),
                }
                for row in groups
            ],
            "health": [
                {
                    "endpoint_profile_id": row[0],
                    "endpoint_profile_version": row[1],
                    "status": row[2],
                    "failure_streak": row[3],
                    "cooldown_until": _iso(row[4]),
                    "last_status": row[5],
                    "last_http_status": row[6],
                    "last_success_at": _iso(row[7]),
                    "last_failure_at": _iso(row[8]),
                    "updated_at": _iso(row[9]),
                }
                for row in health_rows
            ],
            "quota": [
                {
                    "bucket_id": row[0],
                    "authority_scope_id": row[1],
                    "unit": row[2],
                    "window_start": _iso(row[3]),
                    "window_seconds": row[4],
                    "reset_at": _iso(row[5]),
                    "source": row[6],
                    "snapshot_confidence": row[7],
                    "confidence": (
                        "unknown"
                        if (row[11] is not None and row[11] <= datetime.now(UTC))
                        or (row[5] is not None and row[5] <= datetime.now(UTC))
                        else row[7]
                    ),
                    "limit": row[8],
                    "reported_remaining": row[9],
                    "observed_at": _iso(row[10]),
                    "fresh_until": _iso(row[11]),
                }
                for row in quota_rows
            ]
            + [
                {
                    "endpoint_profile_id": endpoint_id,
                    "bucket_id": None,
                    "authority_scope_id": None,
                    "unit": None,
                    "window_start": None,
                    "window_seconds": None,
                    "reset_at": None,
                    "source": "unknown",
                    "confidence": "unknown",
                    "snapshot_confidence": "unknown",
                    "limit": None,
                    "reported_remaining": None,
                    "observed_at": None,
                    "fresh_until": None,
                }
                for endpoint_id in endpoints
                if endpoint_id not in quota_endpoints
            ],
        }

    def purge_expired(self, *, limit: int) -> int:
        return retention.purge_expired(self, limit=limit)

    def resolve_stale_attempts(self, *, limit: int) -> int:
        return retention.resolve_stale_attempts(self, limit=limit)

    def reconcile_operational_events(self, *, limit: int) -> int:
        return retention.reconcile_operational_events(self, limit=limit)

    def _publish_event(self, attempt_id: UUID, event: dict) -> None:
        return retention._publish_event(self, event)

    def _mark_event(self, attempt_id: UUID, status: str) -> None:
        return retention._mark_event(self, attempt_id)

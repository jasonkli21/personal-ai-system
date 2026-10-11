"""Postgres provider usage ledger persistence helpers."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC
from types import SimpleNamespace

from personal_ai.usage.contracts import InvocationMetadata


def _aggregate_attempt(
    connection,
    invocation,
    attempt,
    outcome,
    latency,
    input_tokens,
    output_tokens,
    usage_confidence,
    at,
):
    endpoint = invocation.endpoint
    success = int(outcome == "success")
    rate_limited = int(outcome == "rate_limited")
    server_error = int(outcome == "server_error")
    failure = int(outcome in {"incomplete", "rejected", "timeout", "failure", "unknown"})
    exact = int(usage_confidence == "exact")
    derived = int(usage_confidence == "derived")
    unknown = int(usage_confidence == "unknown")
    connection.execute(
        "INSERT INTO provider_usage_daily_aggregates(owner_id,application_id,workspace_id,usage_day,"
        "provider_id,model_id,endpoint_profile_id,endpoint_profile_version,task_id,operation,attempts,successes,rate_limited,"
        "server_errors,failures,retries,latency_total_ms,input_tokens,output_tokens,exact_usage_attempts,"
        "derived_usage_attempts,unknown_usage_attempts,updated_at) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) "
        "ON CONFLICT(owner_id,application_id,workspace_id,usage_day,endpoint_profile_id,"
        "endpoint_profile_version,task_id,operation) "
        "DO UPDATE SET attempts=provider_usage_daily_aggregates.attempts+1,"
        "successes=provider_usage_daily_aggregates.successes+EXCLUDED.successes,"
        "rate_limited=provider_usage_daily_aggregates.rate_limited+EXCLUDED.rate_limited,"
        "server_errors=provider_usage_daily_aggregates.server_errors+EXCLUDED.server_errors,"
        "failures=provider_usage_daily_aggregates.failures+EXCLUDED.failures,"
        "retries=provider_usage_daily_aggregates.retries+EXCLUDED.retries,"
        "latency_total_ms=provider_usage_daily_aggregates.latency_total_ms+EXCLUDED.latency_total_ms,"
        "input_tokens=provider_usage_daily_aggregates.input_tokens+EXCLUDED.input_tokens,"
        "output_tokens=provider_usage_daily_aggregates.output_tokens+EXCLUDED.output_tokens,"
        "exact_usage_attempts=provider_usage_daily_aggregates.exact_usage_attempts+EXCLUDED.exact_usage_attempts,"
        "derived_usage_attempts=provider_usage_daily_aggregates.derived_usage_attempts+EXCLUDED.derived_usage_attempts,"
        "unknown_usage_attempts=provider_usage_daily_aggregates.unknown_usage_attempts+EXCLUDED.unknown_usage_attempts,"
        "updated_at=EXCLUDED.updated_at",
        (
            invocation.owner_id,
            invocation.application_id,
            invocation.workspace_id,
            at.date(),
            endpoint.provider_id,
            endpoint.model_id,
            endpoint.endpoint_profile_id,
            endpoint.profile_version,
            invocation.task_id,
            invocation.operation,
            success,
            rate_limited,
            server_error,
            failure,
            int(attempt.parent_attempt_id is not None),
            max(0, int(latency)),
            max(0, int(input_tokens)),
            max(0, int(output_tokens)),
            exact,
            derived,
            unknown,
            at,
        ),
    )


def _aggregate_identity(
    owner_id,
    application_id,
    workspace_id,
    task_id,
    operation,
    provider_id,
    model_id,
    endpoint_profile_id,
    endpoint_profile_version,
):
    return SimpleNamespace(
        owner_id=owner_id,
        application_id=application_id,
        workspace_id=workspace_id,
        task_id=task_id,
        operation=operation,
        endpoint=SimpleNamespace(
            provider_id=provider_id,
            model_id=model_id,
            endpoint_profile_id=endpoint_profile_id,
            profile_version=endpoint_profile_version,
        ),
    )


def _bounded_text(value, limit):
    cleaned = "".join(char for char in str(value) if char.isalnum() or char in "._-:")
    return cleaned[:limit]


def _event_from_row(row):
    keys = (
        "invocation_id",
        "owner_id",
        "application_id",
        "workspace_id",
        "task_id",
        "operation",
        "request_id",
        "run_id",
        "endpoint_profile_id",
        "endpoint_profile_version",
        "provider_id",
        "model_id",
        "endpoint_id",
        "deployment_id",
        "credential_source",
        "credential_scope_id",
        "account_scope_id",
        "project_scope_id",
        "tier_id",
        "execution_mode",
        "cost_class",
        "billing_owner",
        "serializer_id",
        "runtime_id",
        "quota_membership",
        "routing_decision_id",
        "routing_strategy_id",
        "routing_strategy_version",
        "registry_version",
        "policy_version",
        "attempt_id",
        "parent_attempt_id",
        "send_number",
        "status",
        "error_code",
        "http_status",
        "started_at",
        "completed_at",
        "latency_ms",
        "input_tokens",
        "output_tokens",
        "total_tokens",
        "usage_source",
        "usage_confidence",
        "unit_usage",
        "unit_usage_source",
        "unit_usage_confidence",
        "rate_limits",
    )
    values = dict(zip(keys, row, strict=True))
    for name in ("invocation_id", "attempt_id", "parent_attempt_id"):
        if values[name] is not None:
            values[name] = str(values[name])
    for name in ("started_at", "completed_at"):
        if values[name] is not None:
            values[name] = values[name].astimezone(UTC).isoformat()
    return {
        "schema_version": "provider-usage-event-v1",
        "event_id": values["attempt_id"],
        **{
            key: values[key]
            for key in (
                "invocation_id",
                "attempt_id",
                "parent_attempt_id",
                "send_number",
                "owner_id",
                "application_id",
                "workspace_id",
                "task_id",
                "operation",
                "request_id",
                "run_id",
                "endpoint_profile_id",
                "endpoint_profile_version",
                "provider_id",
                "model_id",
                "endpoint_id",
                "deployment_id",
                "credential_source",
                "credential_scope_id",
                "account_scope_id",
                "project_scope_id",
                "tier_id",
                "execution_mode",
                "cost_class",
                "billing_owner",
                "serializer_id",
                "runtime_id",
                "quota_membership",
                "routing_decision_id",
                "routing_strategy_id",
                "routing_strategy_version",
                "registry_version",
                "policy_version",
                "status",
                "error_code",
                "http_status",
                "started_at",
                "completed_at",
                "latency_ms",
                "input_tokens",
                "output_tokens",
                "total_tokens",
                "usage_source",
                "usage_confidence",
                "unit_usage",
                "unit_usage_source",
                "unit_usage_confidence",
            )
        },
        "rate_limits": values["rate_limits"] or {},
    }


def _insert_attempt(
    connection,
    invocation,
    attempt,
    reserved_tokens,
    retention_until,
    *,
    status,
    error_code,
    completed_at=None,
):
    connection.execute(
        "INSERT INTO provider_attempts(attempt_id,invocation_id,parent_attempt_id,send_number,status,"
        "error_code,started_at,completed_at,latency_ms,reserved_tokens,retention_until,"
        "operational_event_status) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
        (
            attempt.attempt_id,
            invocation.invocation_id,
            attempt.parent_attempt_id,
            attempt.send_number,
            status,
            _safe_code(error_code),
            attempt.started_at,
            completed_at,
            0 if completed_at is not None else None,
            reserved_tokens,
            retention_until,
            "published" if status == "rejected" else "pending",
        ),
    )


def _insert_invocation(connection, invocation, scope_id, now, retention_until):
    endpoint = invocation.endpoint
    quota_confidence = (
        "unknown"
        if endpoint.quota_membership != "verified"
        or not endpoint.quota_buckets
        or any(bucket.confidence == "unknown" for bucket in endpoint.quota_buckets)
        else "configured"
    )
    connection.execute(
        "INSERT INTO provider_invocations(invocation_id,scope_id,owner_id,application_id,workspace_id,"
        "task_id,operation,request_id,run_id,endpoint_profile_id,endpoint_profile_version,provider_id,"
        "model_id,endpoint_id,deployment_id,credential_source,credential_scope_id,account_scope_id,"
        "project_scope_id,tier_id,execution_mode,cost_class,billing_owner,serializer_id,runtime_id,"
        "quota_membership,"
        "routing_decision_id,routing_strategy_id,routing_strategy_version,registry_version,policy_version,"
        "input_tokens_estimate,output_tokens_bound,quota_confidence,outcome,started_at,retention_until) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,"
        "%s,%s,%s,%s,%s,%s,%s,%s,%s,'running',%s,%s) ON CONFLICT(invocation_id) DO NOTHING",
        (
            invocation.invocation_id,
            scope_id,
            invocation.owner_id,
            invocation.application_id,
            invocation.workspace_id,
            invocation.task_id,
            invocation.operation,
            invocation.request_id,
            invocation.run_id,
            endpoint.endpoint_profile_id,
            endpoint.profile_version,
            endpoint.provider_id,
            endpoint.model_id,
            endpoint.endpoint_id,
            endpoint.deployment_id,
            endpoint.credential_source,
            endpoint.credential_scope_id,
            endpoint.account_scope_id,
            endpoint.project_scope_id,
            endpoint.tier_id,
            endpoint.execution_mode,
            endpoint.cost_class,
            endpoint.billing_owner,
            endpoint.serializer_id,
            endpoint.runtime_id,
            endpoint.quota_membership,
            invocation.routing_decision_id,
            invocation.routing_strategy_id,
            invocation.routing_strategy_version,
            invocation.registry_version,
            invocation.policy_version,
            invocation.input_tokens_estimate,
            invocation.output_tokens_bound,
            quota_confidence,
            now,
            retention_until,
        ),
    )
    identity = connection.execute(
        "SELECT owner_id,application_id,workspace_id,task_id,operation,request_id,run_id,"
        "endpoint_profile_id,endpoint_profile_version,provider_id,model_id,endpoint_id,deployment_id,"
        "credential_source,credential_scope_id,account_scope_id,project_scope_id,tier_id,execution_mode,"
        "cost_class,billing_owner,serializer_id,runtime_id,quota_membership,routing_decision_id,"
        "routing_strategy_id,routing_strategy_version,registry_version,policy_version "
        "FROM provider_invocations WHERE invocation_id=%s",
        (invocation.invocation_id,),
    ).fetchone()
    expected = (
        invocation.owner_id,
        invocation.application_id,
        invocation.workspace_id,
        invocation.task_id,
        invocation.operation,
        invocation.request_id,
        invocation.run_id,
        endpoint.endpoint_profile_id,
        endpoint.profile_version,
        endpoint.provider_id,
        endpoint.model_id,
        endpoint.endpoint_id,
        endpoint.deployment_id,
        endpoint.credential_source,
        endpoint.credential_scope_id,
        endpoint.account_scope_id,
        endpoint.project_scope_id,
        endpoint.tier_id,
        endpoint.execution_mode,
        endpoint.cost_class,
        endpoint.billing_owner,
        endpoint.serializer_id,
        endpoint.runtime_id,
        endpoint.quota_membership,
        invocation.routing_decision_id,
        invocation.routing_strategy_id,
        invocation.routing_strategy_version,
        invocation.registry_version,
        invocation.policy_version,
    )
    if identity != expected:
        raise ValueError("provider_invocation_identity_conflict")


def _iso(value):
    return value.astimezone(UTC).isoformat() if value is not None else None


def _operational_event(invocation, attempt, result):
    endpoint = invocation.endpoint
    return {
        "schema_version": "provider-usage-event-v1",
        "event_id": str(attempt.attempt_id),
        "invocation_id": str(invocation.invocation_id),
        "attempt_id": str(attempt.attempt_id),
        "parent_attempt_id": str(attempt.parent_attempt_id) if attempt.parent_attempt_id else None,
        "send_number": attempt.send_number,
        "owner_id": invocation.owner_id,
        "application_id": invocation.application_id,
        "workspace_id": invocation.workspace_id,
        "task_id": invocation.task_id,
        "operation": invocation.operation,
        "request_id": invocation.request_id,
        "run_id": invocation.run_id,
        "endpoint_profile_id": endpoint.endpoint_profile_id,
        "endpoint_profile_version": endpoint.profile_version,
        "provider_id": endpoint.provider_id,
        "model_id": endpoint.model_id,
        "endpoint_id": endpoint.endpoint_id,
        "deployment_id": endpoint.deployment_id,
        "credential_source": endpoint.credential_source,
        "credential_scope_id": endpoint.credential_scope_id,
        "account_scope_id": endpoint.account_scope_id,
        "project_scope_id": endpoint.project_scope_id,
        "tier_id": endpoint.tier_id,
        "execution_mode": endpoint.execution_mode,
        "cost_class": endpoint.cost_class,
        "billing_owner": endpoint.billing_owner,
        "serializer_id": endpoint.serializer_id,
        "runtime_id": endpoint.runtime_id,
        "quota_membership": endpoint.quota_membership,
        "routing_decision_id": invocation.routing_decision_id,
        "routing_strategy_id": invocation.routing_strategy_id,
        "routing_strategy_version": invocation.routing_strategy_version,
        "registry_version": invocation.registry_version,
        "policy_version": invocation.policy_version,
        "status": result.outcome,
        "error_code": _safe_code(result.error_code),
        "http_status": result.http_status,
        "started_at": attempt.started_at.astimezone(UTC).isoformat(),
        "completed_at": result.completed_at.astimezone(UTC).isoformat(),
        "latency_ms": max(0, result.latency_ms),
        "input_tokens": result.input_tokens,
        "output_tokens": result.output_tokens,
        "total_tokens": result.total_tokens,
        "usage_source": result.usage_source,
        "usage_confidence": result.usage_confidence,
        "unit_usage": dict(result.unit_usage),
        "unit_usage_source": result.unit_usage_source,
        "unit_usage_confidence": result.unit_usage_confidence,
        "rate_limits": _rate_limit_payload(result),
    }


def _rate_limit_payload(result):
    if result.rate_limits is None:
        return {}
    values = asdict(result.rate_limits)
    return {key: value for key, value in values.items() if value is not None}


def _request_budget_scope(invocation: InvocationMetadata) -> str:
    """Canonical logical-request key; separate apps/workspaces, share across runs."""
    return json.dumps(
        [
            invocation.owner_id,
            invocation.application_id,
            invocation.workspace_id,
            invocation.request_id,
        ],
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _safe_code(value):
    if not value:
        return None
    cleaned = "".join(char for char in str(value) if char.isalnum() or char in "._-:")
    return cleaned[:100] or None


def _scope(application_id, workspace_id):
    from personal_ai.auth.scope import ApplicationScope

    return ApplicationScope(application_id=application_id, workspace_id=workspace_id)

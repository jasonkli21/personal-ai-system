"""Monetary liabilities owned by PostgresProviderUsageAccounting."""

import hashlib
from datetime import UTC

from personal_ai.usage.contracts import UsageAdmissionDenied


def _owner_month(now):
    return now.astimezone(UTC).date().replace(day=1)


def _lock_payer(connection, payer):
    # Force PostgreSQL to error if a future role cannot see all of the shared payer's rows.
    connection.execute("SET LOCAL row_security = off")
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))", (f"provider-money:{payer}",)
    )


def _lock_profile(connection, profile):
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"provider-money-profile:{profile}",),
    )


def _profile_key(exposure):
    return hashlib.sha256(exposure.route.profile.model_dump_json().encode()).hexdigest()


def _facts(invocation, exposure, now):
    maximum = exposure.maximum(
        input_tokens=invocation.input_tokens_estimate,
        output_tokens=invocation.output_tokens_bound,
        now=now,
    )
    return (
        exposure.payer_key,
        _profile_key(exposure),
        exposure.fingerprint,
        _owner_month(now),
        exposure.period.start,
        exposure.period.end,
        maximum,
    )


def _check_balances(connection, owner, exposure, facts, *, other_than=None):
    payer, profile, _, month, start, end, maximum = facts
    used_owner, used_payer, blocked = connection.execute(
        """
        SELECT
          COALESCE(SUM(CASE WHEN owner_id=%(owner)s THEN
              CASE WHEN state IN ('reserved','claimed') THEN maximum_micros
                   WHEN state='settled' AND owner_month=%(month)s THEN actual_micros ELSE 0 END
              ELSE 0 END),0),
          COALESCE(SUM(CASE WHEN payer_key=%(payer)s THEN
              CASE WHEN state IN ('reserved','claimed') THEN maximum_micros
                   WHEN state='settled' AND payer_start=%(start)s AND payer_end=%(end)s
                   THEN actual_micros ELSE 0 END ELSE 0 END),0),
          COALESCE(bool_or(
              (state='claimed' AND (owner_id=%(owner)s OR payer_key=%(payer)s))
              OR (actual_micros > maximum_micros
                  AND (payer_key=%(payer)s OR profile_key=%(profile)s))
              OR (payer_key=%(payer)s AND state IN ('reserved','settled')
                  AND payer_start < %(end)s AND payer_end > %(start)s
                  AND (payer_start<>%(start)s OR payer_end<>%(end)s))
          ),false)
        FROM provider_monetary_holds
        WHERE attempt_id IS DISTINCT FROM %(skip)s::uuid
          AND (owner_id=%(owner)s OR payer_key=%(payer)s OR profile_key=%(profile)s)
        """,
        {
            "owner": owner,
            "payer": payer,
            "profile": profile,
            "month": month,
            "start": start,
            "end": end,
            "skip": other_than,
        },
    ).fetchone()
    if blocked:
        raise UsageAdmissionDenied("inference_financial_reconciliation_required")
    if (
        maximum > exposure.root_cap_micros
        or used_owner + maximum > exposure.owner_cap_micros
        or used_payer + maximum > exposure.payer_cap_micros
    ):
        raise UsageAdmissionDenied("inference_budget_exhausted")


def reserve(connection, invocation, attempt_id, root_id, exposure, now):
    facts = _facts(invocation, exposure, now)
    _lock_payer(connection, exposure.payer_key)
    _lock_profile(connection, facts[1])
    _check_balances(connection, invocation.owner_id, exposure, facts)
    connection.execute(
        "INSERT INTO provider_monetary_holds(attempt_id,root_id,owner_id,payer_key,profile_key,"
        "binding_sha256,owner_month,payer_start,payer_end,maximum_micros,state) "
        "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,'reserved')",
        (attempt_id, root_id, invocation.owner_id, *facts),
    )


def require_reserved(connection, invocation, attempt_id, root_id, exposure, now, *, claim=False):
    facts = _facts(invocation, exposure, now)
    _lock_payer(connection, exposure.payer_key)
    _lock_profile(connection, facts[1])
    row = connection.execute(
        "SELECT owner_id,root_id,payer_key,profile_key,binding_sha256,owner_month,"
        "payer_start,payer_end,maximum_micros,state FROM provider_monetary_holds "
        "WHERE attempt_id=%s FOR UPDATE",
        (attempt_id,),
    ).fetchone()
    if row != (invocation.owner_id, root_id, *facts, "reserved"):
        raise UsageAdmissionDenied("inference_financial_binding_changed")
    _check_balances(connection, invocation.owner_id, exposure, facts, other_than=attempt_id)
    if claim:
        connection.execute(
            "UPDATE provider_monetary_holds SET state='claimed' WHERE attempt_id=%s", (attempt_id,)
        )


def release(connection, attempt_id, root_id):
    row = connection.execute(
        "SELECT payer_key FROM provider_monetary_holds WHERE attempt_id=%s AND root_id=%s",
        (attempt_id, root_id),
    ).fetchone()
    if row is None:
        raise UsageAdmissionDenied("inference_financial_binding_changed")
    _lock_payer(connection, row[0])
    updated = connection.execute(
        "UPDATE provider_monetary_holds SET state='released' "
        "WHERE attempt_id=%s AND root_id=%s AND state='reserved' RETURNING attempt_id",
        (attempt_id, root_id),
    ).fetchone()
    if updated is None:
        raise UsageAdmissionDenied("inference_attempt_already_claimed")


def reconcile(connection, receipt):
    _lock_payer(connection, receipt.payer_key)
    row = connection.execute(
        "SELECT payer_key,binding_sha256,payer_start,payer_end,state,receipt_sha256,actual_micros,"
        "profile_key "
        "FROM provider_monetary_holds WHERE attempt_id=%s FOR UPDATE",
        (receipt.attempt_id,),
    ).fetchone()
    if row is None or row[:4] != (
        receipt.payer_key,
        receipt.binding_sha256,
        receipt.period_start,
        receipt.period_end,
    ):
        raise UsageAdmissionDenied("inference_charge_receipt_invalid")
    # The payer lock serializes the exact attempt. Take the profile lock before publishing excess.
    _lock_profile(connection, row[7])
    if row[4:7] == ("settled", receipt.receipt_id, receipt.actual_micros):
        return
    if row[4] != "claimed":
        raise UsageAdmissionDenied("inference_charge_receipt_conflict")
    # Same lock domain for all receipts, even conflicting receipts naming another payer.
    connection.execute(
        "SELECT pg_advisory_xact_lock(hashtextextended(%s,0))",
        (f"provider-money-receipt:{receipt.receipt_id}",),
    )
    if connection.execute(
        "SELECT 1 FROM provider_monetary_holds WHERE receipt_sha256=%s", (receipt.receipt_id,)
    ).fetchone():
        raise UsageAdmissionDenied("inference_charge_receipt_conflict")
    connection.execute(
        "UPDATE provider_monetary_holds SET state='settled',receipt_sha256=%s,actual_micros=%s "
        "WHERE attempt_id=%s",
        (receipt.receipt_id, receipt.actual_micros, receipt.attempt_id),
    )

"""Fail-closed account export until source-specific export consent is supported."""

from personal_ai.auth.account_data import AccountDataUnavailable


def require_export_safe(value):
    # Account snapshots can contain inactive/failed messages and summaries too.
    # Inspect the entire bounded JSON, not only the active conversation branch.
    if isinstance(value, dict):
        if value.get("provider_id") == "retrieval_context" or str(
            value.get("permission_id", "")
        ).startswith("retrieval_context:"):
            raise AccountDataUnavailable("retrieval_export_authority_unavailable")
        for child in value.values():
            require_export_safe(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            require_export_safe(child)

"""Operator-trusted registration; the HTTP consumer does not import this package."""

import json
import os
import time
from pathlib import Path

from personal_ai.extensions.v1 import (
    HOST_CONTRACT_VERSION,
    ApplicationContextPolicy,
    ApplicationContribution,
    ApplicationDefinition,
    CapabilityRegistration,
    ContextRuntimeContribution,
)


class Membership:
    def __init__(self):
        self.path = Path(os.environ["READING_LOGBOOK_MEMBERSHIP_FILE"])
        if not self.path.is_absolute():
            raise ValueError("absolute_membership_file_required")
        self._read()

    def _read(self):
        with self.path.open("rb") as stream:
            raw = stream.read(32769)
        if len(raw) > 32768:
            raise ValueError("membership_file_too_large")
        value = json.loads(raw)
        if (
            set(value) != {"schema_version", "memberships"}
            or value["schema_version"] != "reading-logbook-membership-v1"
        ):
            raise ValueError("membership_schema_invalid")
        rows = value["memberships"]
        if not isinstance(rows, list) or len(rows) > 128:
            raise ValueError("membership_rows_invalid")
        for row in rows:
            if (
                not isinstance(row, dict)
                or set(row) != {"issuer", "subject", "workspace_id", "expires_at"}
                or row["issuer"] != "https://accounts.google.com"
                or not all(
                    isinstance(row[k], str) and 0 < len(row[k]) <= 200
                    for k in ("subject", "workspace_id")
                )
                or type(row["expires_at"]) is not int
            ):
                raise ValueError("membership_row_invalid")
        return rows

    def is_member(self, principal, application_id, workspace_id):
        return (
            principal.authenticated
            and application_id == "reading_logbook"
            and any(
                row["issuer"] == principal.issuer
                and row["subject"] == principal.subject
                and row["workspace_id"] == workspace_id
                and row["expires_at"] > time.time()
                for row in self._read()
            )
        )


def application():
    if HOST_CONTRACT_VERSION != "personal-ai-host-v1":
        raise ValueError("host_contract_incompatible")
    profile_enabled = os.environ.get("READING_LOGBOOK_PROFILE_ENABLED", "false") == "true"
    retrieval_enabled = os.environ.get("READING_LOGBOOK_RETRIEVAL_ENABLED", "false") == "true"
    history = tuple(
        p
        for p in ApplicationContextPolicy().provider_policies
        if p.provider_id == "conversation_history"
        or (profile_enabled and p.provider_id == "global_profile")
    )
    return ApplicationContribution(
        definitions=(
            ApplicationDefinition(
                application_id="reading_logbook",
                display_name="Reading Logbook",
                memory_namespace="reading_logbook",
                workspace_kind="required",
                tool_ids=("retrieval.query.v1",) if retrieval_enabled else (),
                context_policy=ApplicationContextPolicy(
                    version="reading-logbook-profile-v1" if profile_enabled else "reading-logbook-history-v1",
                    provider_policies=history,
                ),
            ),
        ),
        capabilities=(CapabilityRegistration(
            capability_id="retrieval.query.v1", kind="tool", available=True,
            read_only_context=True, result_fields=("retrieval",), max_result_bytes=32768,
        ),) if retrieval_enabled else (),
        workspace_authorizers={"reading_logbook": Membership()},
    )


def context(settings):
    del settings
    return ContextRuntimeContribution(provider_factories={})

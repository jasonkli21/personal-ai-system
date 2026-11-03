"""Opt-in history-only Project Checklist host contribution."""

import json
import os
import time
from pathlib import Path

from personal_ai.extensions.v1 import (
    HOST_CONTRACT_VERSION,
    ApplicationContextPolicy,
    ApplicationContribution,
    ApplicationDefinition,
    ContextRuntimeContribution,
)

APP = "project_checklist"


class Membership:
    """A single operator-selected issuer, subject and workspace, reread on use."""

    def __init__(self, path: Path):
        if not path.is_absolute():
            raise ValueError("absolute_checklist_membership_file_required")
        self._path = path

    def is_member(self, principal, application_id, workspace_id):
        with self._path.open("rb") as stream:
            raw = stream.read(4097)
        if len(raw) > 4096:
            return False
        row = json.loads(raw)
        return (
            isinstance(row, dict)
            and set(row) == {"issuer", "subject", "workspace_id", "expires_at"}
            and principal.authenticated
            and application_id == APP
            and row["issuer"] == principal.issuer
            and row["subject"] == principal.subject
            and row["workspace_id"] == workspace_id
            and type(row["expires_at"]) is int
            and row["expires_at"] > time.time()
        )


def application():
    if HOST_CONTRACT_VERSION != "personal-ai-host-v1":
        raise ValueError("host_contract_incompatible")
    history = tuple(
        policy
        for policy in ApplicationContextPolicy().provider_policies
        if policy.provider_id == "conversation_history"
    )
    return ApplicationContribution(
        definitions=(
            ApplicationDefinition(
                application_id=APP,
                display_name="Project Checklist",
                memory_namespace=APP,
                workspace_kind="required",
                context_policy=ApplicationContextPolicy(
                    version="project-checklist-history-v1",
                    provider_policies=history,
                ),
            ),
        ),
        workspace_authorizers={
            APP: Membership(Path(os.environ["PROJECT_CHECKLIST_MEMBERSHIP_FILE"])),
        },
    )


def context(settings):
    return ContextRuntimeContribution(provider_factories={})

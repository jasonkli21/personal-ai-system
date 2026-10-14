"""Transactional owner-wide grant heads and immutable revision audit."""

import json
from datetime import UTC, datetime
from hashlib import sha256

from personal_ai.auth.scope import ApplicationScope
from personal_ai.federation.contracts import FederationGrant
from personal_ai.persistence.postgres.database import PersistenceConflict
from personal_ai.persistence.postgres.owner_lifecycle import assert_owner_unfenced


def validate_transition(current, grant, expected_revision):
    if current is None:
        if (
            expected_revision != 0
            or grant.revision != 1
            or grant.epoch != 1
            or grant.state != "active"
        ):
            raise PersistenceConflict("federation_grant_create_conflict")
    elif (
        current.state != "active"
        or current.revision != expected_revision
        or grant.revision != current.revision + 1
        or grant.epoch != current.epoch + 1
        or grant.issuance_id != current.issuance_id
        or grant.created_at != current.created_at
        or grant.updated_at < current.updated_at
    ):
        raise PersistenceConflict("federation_grant_revision_conflict")


class PostgresFederationGrantRepository:
    def __init__(self, database):
        self.database = database

    def record_access(self, selection, scope, result):
        from personal_ai.persistence.postgres.auth import _append_audit

        if selection.federation is None:
            return
        reference = sha256(selection.model_dump_json().encode()).hexdigest()
        event_id = sha256(
            f"federation:{scope.request_id}:{reference}:{result}".encode()
        ).hexdigest()
        with self.database.transaction() as connection:
            _append_audit(
                connection,
                owner_id=scope.owner_id,
                audit_id=event_id,
                action="federation.context.selection",
                target_type="context_selection_digest",
                target_id=reference,
                correlation_id=scope.request_id,
                result=result,
                scope=ApplicationScope(
                    application_id=scope.application_id, workspace_id=scope.workspace_id
                ),
                actor_subject=scope.acting_user_id,
            )

    def get(self, owner_id, grant_id):
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM federation_grants WHERE owner_id=%s AND grant_id=%s "
                "AND NOT EXISTS (SELECT 1 FROM owner_lifecycle_fences WHERE owner_id=%s)",
                (owner_id, grant_id, owner_id),
            ).fetchone()
        if row is None:
            return None
        grant = FederationGrant.model_validate(row[0])
        if grant.owner_id != owner_id or grant.grant_id != grant_id:
            raise RuntimeError("federation_grant_identity_invalid")
        return grant

    def list_destination(self, owner_id, destination):
        """Return only active, unexpired grants for one exact owner/destination scope."""
        now = datetime.now(UTC)
        with self.database.connection() as connection:
            rows = connection.execute(
                "SELECT payload FROM federation_grants "
                "WHERE owner_id=%s AND destination_application_id=%s "
                "AND destination_workspace_id IS NOT DISTINCT FROM %s "
                "AND state='active' AND expires_at>%s "
                "AND NOT EXISTS (SELECT 1 FROM owner_lifecycle_fences WHERE owner_id=%s) "
                "ORDER BY (payload->>'updated_at')::timestamptz DESC, grant_id DESC LIMIT 100",
                (
                    owner_id,
                    destination.application_id,
                    destination.workspace_id,
                    now,
                    owner_id,
                ),
            ).fetchall()
        grants = tuple(FederationGrant.model_validate(row[0]) for row in rows)
        if any(
            grant.owner_id != owner_id or grant.destination != destination for grant in grants
        ):
            raise RuntimeError("federation_grant_identity_invalid")
        return grants

    def save(self, grant, *, expected_revision):
        grant = FederationGrant.model_validate(grant.model_dump())
        payload = json.dumps(grant.model_dump(mode="json"), separators=(",", ":"))
        if len(payload.encode()) > 16384:
            raise ValueError("federation_grant_too_large")
        with self.database.transaction() as connection:
            assert_owner_unfenced(connection, grant.owner_id)
            row = connection.execute(
                "SELECT payload FROM federation_grants WHERE owner_id=%s AND grant_id=%s FOR UPDATE",
                (grant.owner_id, grant.grant_id),
            ).fetchone()
            current = FederationGrant.model_validate(row[0]) if row else None
            validate_transition(current, grant, expected_revision)
            values = (
                grant.issuance_id,
                grant.revision,
                grant.epoch,
                grant.source.application_id,
                grant.source.workspace_id,
                grant.destination.application_id,
                grant.destination.workspace_id,
                grant.category,
                grant.purpose,
                grant.state,
                grant.expires_at,
                grant.revocation_id,
                payload,
                grant.owner_id,
                grant.grant_id,
            )
            if current is None:
                connection.execute(
                    "INSERT INTO federation_grants(issuance_id,revision,epoch,source_application_id,"
                    "source_workspace_id,destination_application_id,destination_workspace_id,"
                    "category,purpose,state,expires_at,revocation_id,payload,owner_id,grant_id) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s)",
                    values,
                )
            else:
                cursor = connection.execute(
                    "UPDATE federation_grants SET issuance_id=%s,revision=%s,epoch=%s,source_application_id=%s,"
                    "source_workspace_id=%s,destination_application_id=%s,destination_workspace_id=%s,"
                    "category=%s,purpose=%s,state=%s,expires_at=%s,revocation_id=%s,payload=%s::jsonb "
                    "WHERE owner_id=%s AND grant_id=%s AND revision=%s",
                    (*values, expected_revision),
                )
                if cursor.rowcount != 1:
                    raise PersistenceConflict("federation_grant_revision_conflict")
            connection.execute(
                "INSERT INTO federation_grant_revisions(owner_id,grant_id,revision,epoch,payload) "
                "VALUES(%s,%s,%s,%s,%s::jsonb)",
                (grant.owner_id, grant.grant_id, grant.revision, grant.epoch, payload),
            )
        return grant

    def purge_owner(self, owner_id):
        """Operator cleanup under the established confirmed-deletion fence.

        Revisions cascade with their head; dangling derived dependencies remain
        denied. This does not claim cleanup of other canonical stores.
        """
        from personal_ai.persistence.postgres.owner_lifecycle import lock_owner

        with self.database.transaction() as connection:
            lock_owner(connection, owner_id)
            if (
                connection.execute(
                    "SELECT 1 FROM owner_lifecycle_fences WHERE owner_id=%s",
                    (owner_id,),
                ).fetchone()
                is None
            ):
                raise ValueError("federation_owner_deletion_fence_required")
            connection.execute("DELETE FROM federation_grants WHERE owner_id=%s", (owner_id,))

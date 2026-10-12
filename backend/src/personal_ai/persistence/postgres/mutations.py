"""Transactional proposal heads, CAS reservations and immutable revision trace."""

from personal_ai.mutations.contracts import MutationProposal
from personal_ai.mutations.transitions import validate_transition
from personal_ai.persistence.postgres.owner_lifecycle import assert_owner_unfenced, lock_owner


class PostgresMutationRepository:
    def __init__(self, database):
        self.database = database

    def get(self, scope, proposal_id):
        with self.database.connection() as connection:
            row = connection.execute(
                "SELECT payload FROM mutation_proposals WHERE owner_id=%s AND proposal_id=%s "
                "AND acting_user_id=%s AND application_id=%s AND workspace_id IS NOT DISTINCT FROM %s "
                "AND NOT EXISTS (SELECT 1 FROM owner_lifecycle_fences WHERE owner_id=%s)",
                (scope.owner_id, proposal_id, scope.acting_user_id, scope.application_id,
                 scope.workspace_id, scope.owner_id),
            ).fetchone()
        if row is None:
            return None
        proposal = MutationProposal.model_validate(row[0])
        if (proposal.owner_id != scope.owner_id or proposal.proposal_id != proposal_id
            or proposal.acting_user_id != scope.acting_user_id
            or proposal.intent.target.application_id != scope.application_id
            or proposal.intent.target.workspace_id != scope.workspace_id):
            raise RuntimeError("mutation_persisted_identity_invalid")
        return proposal

    def save(self, proposal, *, expected_revision):
        proposal = MutationProposal.model_validate_json(proposal.model_dump_json())
        payload = proposal.model_dump_json()
        if len(payload.encode()) > 49152:
            raise ValueError("mutation_metadata_too_large")
        target = proposal.intent.target
        with self.database.transaction() as connection:
            # Existing owner lock also serializes initial inserts and deletion fences.
            assert_owner_unfenced(connection, proposal.owner_id)
            row = connection.execute(
                "SELECT payload FROM mutation_proposals WHERE owner_id=%s AND proposal_id=%s "
                "FOR UPDATE", (proposal.owner_id, proposal.proposal_id),
            ).fetchone()
            current = MutationProposal.model_validate(row[0]) if row else None
            validate_transition(current, proposal, expected_revision)
            if current is None:
                connection.execute(
                    "INSERT INTO mutation_proposals(owner_id,proposal_id,application_id,workspace_id,"
                    "acting_user_id,operation_id,operation_version,domain_operation_key,revision,"
                    "state,expires_at,lease_until,payload) "
                    "VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)",
                    (proposal.owner_id, proposal.proposal_id, target.application_id,
                     target.workspace_id, proposal.acting_user_id,
                     proposal.intent.operation.operation_id, proposal.intent.operation.version,
                     proposal.domain_operation_key, proposal.revision, proposal.state,
                     proposal.intent.expires_at, proposal.lease_until, payload),
                )
            else:
                connection.execute(
                    "UPDATE mutation_proposals SET revision=%s,state=%s,lease_until=%s,payload=%s::jsonb "
                    "WHERE owner_id=%s AND proposal_id=%s AND revision=%s",
                    (proposal.revision, proposal.state, proposal.lease_until, payload,
                     proposal.owner_id, proposal.proposal_id, expected_revision),
                )
            connection.execute(
                "INSERT INTO mutation_proposal_revisions(owner_id,proposal_id,application_id,"
                "workspace_id,revision,payload) VALUES(%s,%s,%s,%s,%s,%s::jsonb)",
                (proposal.owner_id, proposal.proposal_id, target.application_id,
                 target.workspace_id, proposal.revision, payload),
            )
        return proposal

    def purge_owner(self, owner_id):
        """AI metadata only; no rollback/deletion of externally committed domain state."""
        with self.database.transaction() as connection:
            lock_owner(connection, owner_id)
            if connection.execute(
                "SELECT 1 FROM owner_lifecycle_fences WHERE owner_id=%s", (owner_id,),
            ).fetchone() is None:
                raise ValueError("mutation_owner_deletion_fence_required")
            connection.execute("DELETE FROM mutation_proposals WHERE owner_id=%s", (owner_id,))

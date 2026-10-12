-- Query-rich control metadata only; external domains own records and operation receipts.
CREATE TABLE mutation_proposals (
    owner_id text NOT NULL,
    proposal_id uuid NOT NULL,
    application_id text NOT NULL,
    workspace_id text,
    acting_user_id text NOT NULL,
    operation_id text NOT NULL,
    operation_version integer NOT NULL CHECK (operation_version > 0),
    domain_operation_key uuid NOT NULL UNIQUE,
    revision bigint NOT NULL CHECK (revision > 0),
    state text NOT NULL CHECK (state IN ('proposed','validated','confirmed','executing',
        'reconciling','applied','rejected','uncertain','expired')),
    expires_at timestamptz NOT NULL,
    lease_until timestamptz,
    payload jsonb NOT NULL CHECK (octet_length(payload::text) <= 65536),
    PRIMARY KEY (owner_id, proposal_id)
);
CREATE INDEX mutation_scope ON mutation_proposals(owner_id,application_id,workspace_id);
CREATE INDEX mutation_recovery ON mutation_proposals(state,lease_until)
    WHERE state IN ('executing','reconciling','uncertain');
CREATE TABLE mutation_proposal_revisions (
    owner_id text NOT NULL,
    proposal_id uuid NOT NULL,
    application_id text NOT NULL,
    workspace_id text,
    revision bigint NOT NULL CHECK (revision > 0),
    payload jsonb NOT NULL CHECK (octet_length(payload::text) <= 65536),
    PRIMARY KEY (owner_id,proposal_id,revision),
    FOREIGN KEY (owner_id,proposal_id) REFERENCES mutation_proposals(owner_id,proposal_id)
        ON DELETE CASCADE
);

-- Owner-wide permission authority. Domain records are never stored here.
CREATE TABLE federation_grants (
    owner_id text NOT NULL CHECK (length(owner_id) BETWEEN 1 AND 200),
    grant_id uuid NOT NULL,
    issuance_id uuid NOT NULL UNIQUE,
    revision bigint NOT NULL CHECK (revision > 0),
    epoch bigint NOT NULL CHECK (epoch > 0),
    source_application_id text NOT NULL,
    source_workspace_id text,
    destination_application_id text NOT NULL,
    destination_workspace_id text,
    category text NOT NULL,
    purpose text NOT NULL,
    state text NOT NULL CHECK (state IN ('active','revoked')),
    expires_at timestamptz NOT NULL,
    revocation_id uuid,
    payload jsonb NOT NULL CHECK (octet_length(payload::text) <= 16384),
    PRIMARY KEY (owner_id,grant_id),
    CHECK (source_application_id <> destination_application_id),
    CHECK ((state='revoked') = (revocation_id IS NOT NULL)),
    CHECK (payload->>'schema_version' = 'federation-grant-v1'),
    CHECK ((payload->>'issuance_id')::uuid = issuance_id),
    CHECK (payload->>'owner_id' = owner_id AND payload->>'grant_id' = grant_id::text),
    CHECK ((payload->>'revision')::bigint = revision AND (payload->>'epoch')::bigint = epoch),
    CHECK ((payload->>'expires_at')::timestamptz = expires_at),
    CHECK ((payload->>'revocation_id')::uuid IS NOT DISTINCT FROM revocation_id),
    CHECK (payload->>'state' = state AND payload->>'category' = category AND payload->>'purpose' = purpose),
    CHECK (payload->'source'->>'application_id' = source_application_id
        AND (payload->'source'->>'workspace_id') IS NOT DISTINCT FROM source_workspace_id),
    CHECK (payload->'destination'->>'application_id' = destination_application_id
        AND (payload->'destination'->>'workspace_id') IS NOT DISTINCT FROM destination_workspace_id)
);
CREATE INDEX federation_grants_destination_idx ON federation_grants
    (owner_id,destination_application_id,destination_workspace_id,category,state,expires_at);
CREATE TABLE federation_grant_revisions (
    owner_id text NOT NULL,
    grant_id uuid NOT NULL,
    revision bigint NOT NULL,
    epoch bigint NOT NULL,
    payload jsonb NOT NULL CHECK (octet_length(payload::text) <= 16384),
    PRIMARY KEY(owner_id,grant_id,revision),
    FOREIGN KEY(owner_id,grant_id) REFERENCES federation_grants(owner_id,grant_id) ON DELETE CASCADE
);

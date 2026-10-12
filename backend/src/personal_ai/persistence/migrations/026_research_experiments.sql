-- Compact immutable paired evaluation only; no physical dispatch/quota ledger.
CREATE TABLE research_experiments (
    scope_id text NOT NULL REFERENCES scope_namespaces(scope_id),
    record_id text NOT NULL,
    owner_id text NOT NULL CHECK (length(owner_id) BETWEEN 1 AND 200),
    application_id text NOT NULL CHECK (length(application_id) BETWEEN 2 AND 42),
    workspace_id text,
    record_version smallint NOT NULL DEFAULT 1 CHECK (record_version=1),
    revision bigint NOT NULL DEFAULT 1 CHECK (revision=1),
    status text NOT NULL CHECK (status='not_promoted'),
    created_at timestamptz NOT NULL,
    updated_at timestamptz,
    expires_at timestamptz NOT NULL,
    fingerprint char(64) NOT NULL CHECK (fingerprint ~ '^[a-f0-9]{64}$'),
    idempotency_key text NOT NULL,
    payload jsonb NOT NULL CHECK (octet_length(payload::text)<=16384),
    PRIMARY KEY(scope_id,record_id),
    UNIQUE(scope_id,idempotency_key),
    CHECK (expires_at>created_at AND expires_at<=created_at+interval '30 days')
);
CREATE INDEX research_experiments_coverage_idx ON research_experiments
    (scope_id,(payload->>'task_family'),(payload->>'source_profile'),(payload->>'strategy_id'),created_at);
CREATE INDEX research_experiments_owner_expiry_idx ON research_experiments(owner_id,expires_at);

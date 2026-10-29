-- Default-off MEM-2: untrusted pending content and bounded, content-free receipts.
-- No new accepted knowledge state or in-place revision of schema 3.
CREATE TABLE memory_control_proposals (
    scope_id text NOT NULL REFERENCES scope_namespaces(scope_id),
    actor_key text NOT NULL CHECK (actor_key='N' OR actor_key LIKE 'V%'),
    record_id uuid NOT NULL,
    project_id text NOT NULL CHECK (length(project_id) BETWEEN 1 AND 100),
    expires_at timestamptz NOT NULL,
    payload jsonb NOT NULL CHECK (octet_length(payload::text) <= 8192),
    PRIMARY KEY (scope_id, actor_key, record_id)
);
CREATE INDEX memory_control_proposals_expiry ON memory_control_proposals(scope_id, actor_key, expires_at);
CREATE TABLE memory_control_operations (
    scope_id text NOT NULL REFERENCES scope_namespaces(scope_id),
    actor_key text NOT NULL CHECK (actor_key='N' OR actor_key LIKE 'V%'),
    record_id uuid NOT NULL,
    payload jsonb NOT NULL CHECK (octet_length(payload::text) <= 2048),
    PRIMARY KEY (scope_id, actor_key, record_id)
);
-- Expired receipt keys are deliberately retained and count against the quota.

-- Isolated synthetic development only; no runtime composition or memory admission.
-- The authority row is separate from derived checkpoints so restoring derived
-- data alone cannot roll back issuer epochs or original-key/checkpoint heads.
CREATE TABLE offline_consolidation_authorities (
    corpus_digest text PRIMARY KEY CHECK (corpus_digest ~ '^[0-9a-f]{64}$'),
    revision bigint NOT NULL CHECK (revision > 0),
    payload jsonb NOT NULL CHECK (octet_length(payload::text) <= 65536)
);
CREATE TABLE offline_consolidation_checkpoints (
    corpus_digest text NOT NULL REFERENCES offline_consolidation_authorities(corpus_digest),
    owner_id text NOT NULL,
    scope_digest text NOT NULL CHECK (scope_digest ~ '^[0-9a-f]{64}$'),
    generation text NOT NULL CHECK (length(generation) <= 128),
    payload jsonb NOT NULL CHECK (octet_length(payload::text) <= 65536),
    PRIMARY KEY (corpus_digest, scope_digest, generation)
);
CREATE INDEX offline_consolidation_checkpoint_owner
    ON offline_consolidation_checkpoints(owner_id);

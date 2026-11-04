-- Internal synthetic-only episode projection. No runtime host registration.
-- Payload contains closed metadata and canonical lifecycle projection, never tool I/O.
CREATE TABLE memory_episode_scopes (
    owner_id text NOT NULL,
    namespace_digest text NOT NULL CHECK (namespace_digest ~ '^[0-9a-f]{64}$'),
    payload jsonb NOT NULL CHECK (octet_length(payload::text) <= 524288),
    PRIMARY KEY (owner_id, namespace_digest)
);

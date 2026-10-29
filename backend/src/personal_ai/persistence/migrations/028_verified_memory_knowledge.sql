-- MEM-1: immutable bounded knowledge, source fences and complete normalized edges.
-- V1 assertions and V2 support-v1 tables/readers are deliberately unchanged.
CREATE TABLE memory_knowledge (
    scope_id text NOT NULL REFERENCES scope_namespaces(scope_id),
    record_id text NOT NULL,
    owner_id text NOT NULL,
    application_id text NOT NULL,
    workspace_id text,
    project_id text NOT NULL CHECK (length(project_id) BETWEEN 1 AND 100),
    kind text NOT NULL CHECK (kind IN ('procedure', 'project_decision')),
    authority text NOT NULL CHECK (authority IN ('tool_receipt_verified', 'user_asserted')),
    canonical_revision text NOT NULL CHECK (length(canonical_revision) BETWEEN 1 AND 100),
    admission_key char(64) NOT NULL CHECK (admission_key ~ '^[a-f0-9]{64}$'),
    fingerprint char(64) NOT NULL CHECK (fingerprint ~ '^[a-f0-9]{64}$'),
    record_version smallint NOT NULL DEFAULT 3 CHECK (record_version = 3),
    created_at timestamptz NOT NULL,
    expires_at timestamptz NOT NULL,
    payload jsonb NOT NULL CHECK (octet_length(payload::text) <= 16384),
    PRIMARY KEY (scope_id, record_id),
    UNIQUE (scope_id, admission_key),
    CHECK (expires_at > created_at)
);
CREATE INDEX memory_knowledge_select_idx ON memory_knowledge
    (scope_id, project_id, kind, authority, canonical_revision, created_at, record_id);
CREATE INDEX memory_knowledge_expiry_idx ON memory_knowledge (scope_id, expires_at, record_id);

-- Tombstones deliberately outlive erased content and prevent original-epoch replay.
CREATE TABLE memory_knowledge_source_fences (
    scope_id text NOT NULL REFERENCES scope_namespaces(scope_id),
    resolver_id text NOT NULL CHECK (length(resolver_id) BETWEEN 1 AND 100),
    source_id text NOT NULL CHECK (length(source_id) BETWEEN 1 AND 200),
    epoch bigint NOT NULL CHECK (epoch >= 0),
    fingerprint char(64) NOT NULL CHECK (fingerprint ~ '^[a-f0-9]{64}$'),
    active boolean NOT NULL,
    PRIMARY KEY (scope_id, resolver_id, source_id)
);
CREATE TABLE memory_knowledge_sources (
    scope_id text NOT NULL,
    record_id text NOT NULL,
    source_ordinal smallint NOT NULL CHECK (source_ordinal BETWEEN 1 AND 8),
    resolver_id text NOT NULL,
    source_id text NOT NULL,
    source_epoch bigint NOT NULL CHECK (source_epoch >= 0),
    source_fingerprint char(64) NOT NULL CHECK (source_fingerprint ~ '^[a-f0-9]{64}$'),
    relation text NOT NULL CHECK (relation IN ('supports', 'confirmed_by')),
    PRIMARY KEY (scope_id, record_id, source_ordinal),
    UNIQUE (scope_id, record_id, resolver_id, source_id),
    FOREIGN KEY (scope_id, record_id) REFERENCES memory_knowledge(scope_id, record_id) ON DELETE CASCADE,
    FOREIGN KEY (scope_id, resolver_id, source_id)
        REFERENCES memory_knowledge_source_fences(scope_id, resolver_id, source_id)
);
CREATE INDEX memory_knowledge_sources_reverse_idx ON memory_knowledge_sources
    (scope_id, resolver_id, source_id, record_id);

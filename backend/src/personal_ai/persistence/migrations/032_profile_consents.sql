-- PI-4 dormant owner consent aggregate. Old v1 allowlists are archived, never grants.
CREATE TABLE profile_consents (
    scope_id text NOT NULL REFERENCES scope_namespaces(scope_id),
    record_id text NOT NULL CHECK (record_id='owner-profile-consents-v1'),
    owner_id text NOT NULL CHECK (length(owner_id) BETWEEN 1 AND 200),
    application_id text NOT NULL CHECK (application_id='personal_ai'),
    workspace_id text CHECK (workspace_id IS NULL),
    record_version smallint NOT NULL DEFAULT 1 CHECK (record_version=1),
    status text, revision bigint NOT NULL CHECK (revision>=0),
    created_at timestamptz NOT NULL, updated_at timestamptz NOT NULL,
    expires_at timestamptz, fingerprint char(64), idempotency_key text,
    payload jsonb NOT NULL CHECK (octet_length(payload::text)<=131072),
    PRIMARY KEY (scope_id,record_id)
);
CREATE INDEX profile_consents_owner_idx ON profile_consents(owner_id);
INSERT INTO profile_consents(scope_id,record_id,owner_id,application_id,revision,created_at,updated_at,payload)
SELECT scope_id,'owner-profile-consents-v1',owner_id,'personal_ai',0,now(),now(),
    jsonb_build_object('schema_version','profile-consents-v1','owner_id',owner_id,
        'revision',0,'grants','[]'::jsonb,'receipts','[]'::jsonb,
        'legacy_sharing',COALESCE((SELECT jsonb_object_agg(f->>'field',f->'shared_with_applications')
            FROM jsonb_array_elements(payload->'fields') f
            WHERE jsonb_array_length(COALESCE(f->'shared_with_applications','[]'::jsonb))>0),'{}'::jsonb))
FROM global_profiles;
UPDATE global_profiles SET payload=jsonb_set(payload,'{fields}',
    COALESCE((SELECT jsonb_agg(jsonb_set(f,'{shared_with_applications}','[]'::jsonb))
        FROM jsonb_array_elements(payload->'fields') f),'[]'::jsonb));
-- Old writers fail explicitly instead of resurrecting broad, perpetual shares.
ALTER TABLE global_profiles ADD CONSTRAINT global_profiles_legacy_sharing_disabled
    CHECK (NOT jsonb_path_exists(payload,'$.fields[*].shared_with_applications[*]'));

CREATE TABLE workflow_runs (
    run_id uuid PRIMARY KEY,
    scope_digest text NOT NULL,
    original_key uuid NOT NULL,
    intent_digest text NOT NULL,
    source_digest text NOT NULL,
    spec jsonb,
    deadline timestamptz NOT NULL,
    record jsonb NOT NULL,
    UNIQUE (scope_digest, original_key)
);

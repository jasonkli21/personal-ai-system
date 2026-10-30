-- Support globally bounded cleanup of expired proposal bodies during maintenance.
CREATE INDEX memory_control_proposals_expiry_gc
    ON memory_control_proposals(expires_at, scope_id, actor_key, record_id);

-- Preserve stable project identity when reconciling migration-030 receipts after
-- project revision drift. Receipts whose target row is already gone retain their
-- legacy fingerprint behavior.
WITH legacy AS (
    SELECT
        o.scope_id,
        o.actor_key,
        o.record_id,
        COALESCE(k.project_id, p.project_id) AS project_id
    FROM memory_control_operations o
    LEFT JOIN memory_knowledge k
        ON o.payload->>'action' = 'forget'
        AND k.scope_id = o.scope_id
        AND k.record_id::text = o.payload->>'target_id'
    LEFT JOIN memory_control_proposals p
        ON o.payload->>'action' IN ('propose', 'reviewed', 'rejected')
        AND p.scope_id = o.scope_id
        AND p.actor_key = o.actor_key
        AND p.record_id::text = o.payload->>'target_id'
    WHERE NOT (o.payload ? 'project_id')
)
UPDATE memory_control_operations o
SET payload = jsonb_set(o.payload, '{project_id}', to_jsonb(legacy.project_id), true)
FROM legacy
WHERE o.scope_id = legacy.scope_id
  AND o.actor_key = legacy.actor_key
  AND o.record_id = legacy.record_id
  AND legacy.project_id IS NOT NULL;

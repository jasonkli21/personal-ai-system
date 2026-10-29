-- Bind schema-3 source epochs and reverse edges to the exact acting user.
-- Existing fences with retained records are cloned per record actor. Orphaned
-- fences have no recoverable actor identity, so they remain a global legacy
-- replay deny ('L') and cannot authorize mutation by any actor.

ALTER TABLE memory_knowledge_source_fences
    ADD COLUMN actor_key text NOT NULL DEFAULT 'L';
ALTER TABLE memory_knowledge_sources
    ADD COLUMN actor_key text NOT NULL DEFAULT 'L';

ALTER TABLE memory_knowledge_sources
    DROP CONSTRAINT memory_knowledge_sources_scope_id_resolver_id_source_id_fkey;
ALTER TABLE memory_knowledge_source_fences
    DROP CONSTRAINT memory_knowledge_source_fences_pkey,
    ADD PRIMARY KEY (scope_id, resolver_id, source_id, actor_key);

UPDATE memory_knowledge_sources AS edge
SET actor_key = CASE
    WHEN knowledge.payload->>'acting_user_id' IS NULL THEN 'N'
    ELSE 'V' || (knowledge.payload->>'acting_user_id')
END
FROM memory_knowledge AS knowledge
WHERE knowledge.scope_id = edge.scope_id
  AND knowledge.record_id = edge.record_id;

ALTER TABLE memory_knowledge_sources
    ALTER COLUMN actor_key DROP DEFAULT;

INSERT INTO memory_knowledge_source_fences
    (scope_id, resolver_id, source_id, actor_key, epoch, fingerprint, active)
SELECT DISTINCT
    fence.scope_id,
    fence.resolver_id,
    fence.source_id,
    edge.actor_key,
    fence.epoch,
    fence.fingerprint,
    fence.active
FROM memory_knowledge_source_fences AS fence
JOIN memory_knowledge_sources AS edge
  ON edge.scope_id = fence.scope_id
 AND edge.resolver_id = fence.resolver_id
 AND edge.source_id = fence.source_id
ON CONFLICT (scope_id, resolver_id, source_id, actor_key) DO NOTHING;

-- Every old fence still referenced by an edge now has actor-specific copies.
-- Keep only unreferenced old identities as conservative global tombstones.
DELETE FROM memory_knowledge_source_fences AS fence
WHERE fence.actor_key = 'L'
  AND EXISTS (
      SELECT 1
      FROM memory_knowledge_sources AS edge
      WHERE edge.scope_id = fence.scope_id
        AND edge.resolver_id = fence.resolver_id
        AND edge.source_id = fence.source_id
  );

ALTER TABLE memory_knowledge_source_fences
    ALTER COLUMN actor_key DROP DEFAULT,
    ALTER COLUMN actor_key SET NOT NULL;
ALTER TABLE memory_knowledge_sources
    ADD CONSTRAINT memory_knowledge_sources_actor_fence_fkey
    FOREIGN KEY (scope_id, resolver_id, source_id, actor_key)
    REFERENCES memory_knowledge_source_fences(scope_id, resolver_id, source_id, actor_key);

DROP INDEX memory_knowledge_sources_reverse_idx;
CREATE INDEX memory_knowledge_sources_reverse_idx ON memory_knowledge_sources
    (scope_id, resolver_id, source_id, actor_key, record_id);

ALTER TABLE memory_knowledge_source_fences
    ADD CONSTRAINT memory_knowledge_source_actor_key_check
    CHECK (actor_key = 'N' OR actor_key = 'L' OR actor_key LIKE 'V%');
ALTER TABLE memory_knowledge_sources
    ADD CONSTRAINT memory_knowledge_edge_actor_key_check
    CHECK (actor_key = 'N' OR actor_key LIKE 'V%');

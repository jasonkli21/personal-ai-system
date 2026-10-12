-- Phase 34: reconstruct narrow lifecycle validity epochs for historical projections.
-- Hermetic SQL: no runtime imports or mutable policy definitions.
UPDATE memory_lifecycle_states AS state
SET payload = state.payload || jsonb_build_object(
    'validity_epoch', GREATEST(
        CASE WHEN state.payload->>'retrieval_status' IN ('forgotten','superseded') THEN 1 ELSE 0 END,
        (SELECT count(*) FROM memory_lifecycle_events AS event
         WHERE event.scope_id = state.scope_id AND event.aggregate_id = state.record_id
           AND event.payload->>'event_type' IN ('forgotten','superseded','reactivated','review_required'))
    ),
    'unresolved_conflict', EXISTS(
        SELECT 1 FROM memory_lifecycle_events AS event
        WHERE event.scope_id = state.scope_id AND event.aggregate_id = state.record_id
          AND event.payload->>'event_type' = 'review_required'
    )
), revision = state.revision + 1
WHERE NOT (state.payload ? 'validity_epoch');

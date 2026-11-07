# ADR 0003: Model local development as a single unauthenticated owner

- Status: accepted
- Date: 2026-08-19

## Context

The initial vertical slice is for one logical personal user, but local development does not implement authentication or authorization. Storage needs an identity seam so that a future real identity system does not require a data-model redesign.

## Decision

Assign each persisted local-development record `owner_id = "local"`. Every repository method accepts an `owner_id` parameter. The application must not claim that this is authenticated identity.

## Consequences

- Conversation and message APIs/services can consistently scope reads and writes by owner.
- A later authentication implementation can replace the caller-supplied owner with verified identity while retaining repository shapes.
- This is not a security boundary and is unsuitable for exposing real personal data on the current public deployment.

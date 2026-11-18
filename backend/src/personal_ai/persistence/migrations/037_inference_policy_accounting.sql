CREATE TABLE inference_owner_policies (
    owner_id text PRIMARY KEY CHECK (length(owner_id) BETWEEN 1 AND 200),
    revision bigint NOT NULL CHECK (revision > 0),
    payload jsonb NOT NULL CHECK (octet_length(payload::text) <= 32768)
);

CREATE TABLE inference_route_roots (
    root_id uuid PRIMARY KEY,
    owner_id text NOT NULL,
    payload_sha256 char(64) NOT NULL,
    plan_sha256 char(64) NOT NULL,
    deadline timestamptz NOT NULL,
    candidate smallint NOT NULL DEFAULT 0 CHECK (candidate BETWEEN 0 AND 16),
    state text NOT NULL DEFAULT 'open' CHECK (state IN ('open', 'fenced', 'stopped')),
    attempt_id uuid
);

-- Financial and logical replay identities survive ordinary usage retention and owner deletion.
-- No prompt, authorization document, receipt body, credential or provider token is stored.
CREATE TABLE provider_monetary_holds (
    attempt_id uuid PRIMARY KEY,
    root_id uuid NOT NULL REFERENCES inference_route_roots(root_id),
    owner_id text NOT NULL,
    payer_key char(64) NOT NULL,
    profile_key char(64) NOT NULL,
    binding_sha256 char(64) NOT NULL,
    owner_month date NOT NULL,
    payer_start timestamptz NOT NULL,
    payer_end timestamptz NOT NULL CHECK (payer_end > payer_start),
    maximum_micros bigint NOT NULL CHECK (maximum_micros > 0),
    state text NOT NULL CHECK (state IN ('reserved', 'claimed', 'released', 'settled')),
    actual_micros bigint CHECK (actual_micros >= 0),
    receipt_sha256 char(64) UNIQUE,
    CHECK ((state = 'settled') = (actual_micros IS NOT NULL AND receipt_sha256 IS NOT NULL))
);
CREATE INDEX provider_monetary_owner_idx ON provider_monetary_holds(owner_id, owner_month);
CREATE INDEX provider_monetary_payer_idx ON provider_monetary_holds(payer_key, payer_start, payer_end);
CREATE INDEX provider_monetary_profile_idx ON provider_monetary_holds(profile_key)
    WHERE actual_micros > maximum_micros;
CREATE UNIQUE INDEX provider_monetary_root_active_idx ON provider_monetary_holds(root_id)
    WHERE state <> 'released';

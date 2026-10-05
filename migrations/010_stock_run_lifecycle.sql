-- P0 stock run lifecycle: DATA -> RESEARCH -> RECONCILE -> COMPUTE -> PERSIST -> PRESENT
-- Additive governance schema. Frozen EDGE scoring/forecast/recommendation methodology is unchanged.

CREATE TABLE IF NOT EXISTS edge_run_lifecycles (
    lifecycle_id text PRIMARY KEY,
    ticker text NOT NULL,
    trigger_type text NOT NULL CHECK (trigger_type IN ('USER','SCHEDULED')),
    target_session date,
    canonical_requested_at timestamptz,
    stage text NOT NULL CHECK (stage IN (
        'RUN_CREATED','DATA_PENDING','DATA_READY','DATA_BLOCKED',
        'RESEARCH_PENDING','RESEARCH_READY','RESEARCH_BLOCKED',
        'AUCTION_PENDING','AUCTION_READY','AUCTION_BLOCKED',
        'RECONCILED','COMPUTE_DISPATCHED','COMPUTE_PENDING','COMPUTED','COMPUTE_BLOCKED',
        'PERSISTED','PRESENTED'
    )),
    market_snapshot_id text,
    research_bundle_id text,
    recommendation_id text,
    stage_detail text,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_edge_run_lifecycles_target
ON edge_run_lifecycles(target_session,ticker,created_at DESC);

CREATE TABLE IF NOT EXISTS edge_market_snapshots (
    snapshot_id text PRIMARY KEY,
    lifecycle_id text NOT NULL UNIQUE REFERENCES edge_run_lifecycles(lifecycle_id),
    ticker text NOT NULL,
    captured_at timestamptz NOT NULL,
    provider text NOT NULL CHECK (provider='UPSTOX'),
    payload jsonb NOT NULL,
    payload_hash text NOT NULL CHECK (length(payload_hash)=64),
    status text NOT NULL CHECK (status='DATA_READY'),
    inserted_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_edge_market_snapshots_ticker_time
ON edge_market_snapshots(ticker,captured_at DESC);

CREATE OR REPLACE FUNCTION prevent_edge_market_snapshot_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'edge_market_snapshots are immutable';
END $$;

DROP TRIGGER IF EXISTS trg_edge_market_snapshots_immutable ON edge_market_snapshots;
CREATE TRIGGER trg_edge_market_snapshots_immutable
BEFORE UPDATE OR DELETE ON edge_market_snapshots
FOR EACH ROW EXECUTE FUNCTION prevent_edge_market_snapshot_mutation();

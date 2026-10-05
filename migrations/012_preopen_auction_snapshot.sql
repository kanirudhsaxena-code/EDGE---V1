-- P0 pre-open Stage-2 immutable auction snapshot.
-- PREP DATA remains immutable and research-bound; AUCTION DATA is frozen in
-- 09:10:00-09:14:59 IST and is the only permitted pre-open reference-price source.

CREATE TABLE IF NOT EXISTS edge_auction_snapshots (
    auction_snapshot_id text PRIMARY KEY,
    lifecycle_id text NOT NULL UNIQUE REFERENCES edge_run_lifecycles(lifecycle_id),
    ticker text NOT NULL,
    captured_at timestamptz NOT NULL,
    provider text NOT NULL CHECK (provider='UPSTOX'),
    source_ref text NOT NULL,
    indicative_equilibrium_price double precision NOT NULL CHECK (indicative_equilibrium_price > 0),
    payload jsonb NOT NULL,
    payload_hash text NOT NULL CHECK (length(payload_hash)=64),
    status text NOT NULL CHECK (status='AUCTION_READY'),
    inserted_at timestamptz NOT NULL DEFAULT now()
);

ALTER TABLE edge_run_lifecycles
ADD COLUMN IF NOT EXISTS auction_snapshot_id text;

CREATE OR REPLACE FUNCTION prevent_edge_auction_snapshot_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'edge_auction_snapshots are immutable';
END $$;

DROP TRIGGER IF EXISTS trg_edge_auction_snapshots_immutable ON edge_auction_snapshots;
CREATE TRIGGER trg_edge_auction_snapshots_immutable
BEFORE UPDATE OR DELETE ON edge_auction_snapshots
FOR EACH ROW EXECUTE FUNCTION prevent_edge_auction_snapshot_mutation();

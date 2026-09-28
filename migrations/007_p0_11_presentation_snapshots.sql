-- P0-11 immutable EDGE Stocks presentation snapshot storage.
--
-- Repository definition only. Validate on a temporary Neon branch before any
-- production application. This migration is additive and does not alter EDGE V1
-- analytical methodology, efficacy rules, canonical selection or trading logic.

CREATE TABLE IF NOT EXISTS presentation_snapshots (
  presentation_snapshot_id bigserial PRIMARY KEY,
  presentation_contract_version text NOT NULL
    CHECK (presentation_contract_version='P0_11_PRESENTATION_V1'),
  engine text NOT NULL CHECK (engine='EDGE_STOCKS'),
  run_id bigint NOT NULL REFERENCES edge_runs(run_id) ON DELETE RESTRICT,
  result_id text NOT NULL REFERENCES recommendations(recommendation_id) ON DELETE RESTRICT,
  checkpoint_id bigint REFERENCES outcome_checkpoints(checkpoint_id) ON DELETE RESTRICT,
  governance_state text NOT NULL CHECK (btrim(governance_state) <> ''),
  sections jsonb NOT NULL
    CHECK (jsonb_typeof(sections)='array' AND jsonb_array_length(sections)=4),
  source_payload_hash text NOT NULL CHECK (btrim(source_payload_hash) <> ''),
  presentation_hash text NOT NULL CHECK (presentation_hash ~ '^[0-9a-f]{64}$'),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_edge_presentation_exact_identity
ON presentation_snapshots(run_id,result_id,COALESCE(checkpoint_id,0));

CREATE INDEX IF NOT EXISTS idx_edge_presentation_result
ON presentation_snapshots(result_id,created_at DESC);

CREATE RULE presentation_snapshots_no_update AS
ON UPDATE TO presentation_snapshots DO INSTEAD NOTHING;

CREATE RULE presentation_snapshots_no_delete AS
ON DELETE TO presentation_snapshots DO INSTEAD NOTHING;

-- No INSERT/backfill is performed. Historical recommendations stay immutable and
-- remain presentation-unavailable unless a contemporaneous governed snapshot exists.

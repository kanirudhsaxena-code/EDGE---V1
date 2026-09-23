-- EDGE Stocks VNext Learning Lab engine-owned immutable observations and daily snapshots.
-- Additive only. Frozen EDGE_V1 methodology and official canonical efficacy are unchanged.

CREATE TABLE IF NOT EXISTS edge_learning_observations_vnext (
  observation_id text PRIMARY KEY,
  recommendation_id text NOT NULL REFERENCES recommendations(recommendation_id),
  ticker text NOT NULL,
  target_trading_date date NOT NULL,
  run_role text NOT NULL CHECK (run_role IN ('CANONICAL','DIAGNOSTIC','MANUAL','SHADOW')),
  official_efficacy_eligible boolean NOT NULL DEFAULT false,
  dimension text NOT NULL,
  observation_type text NOT NULL,
  outcome_classification text,
  metrics jsonb NOT NULL DEFAULT '{}'::jsonb,
  exclusion_reason text,
  source_ref text NOT NULL,
  observed_at timestamptz NOT NULL,
  content_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (official_efficacy_eligible OR exclusion_reason IS NOT NULL)
);

CREATE INDEX IF NOT EXISTS idx_edge_learning_observations_vnext_target
ON edge_learning_observations_vnext(target_trading_date DESC,ticker,observed_at DESC);

CREATE TABLE IF NOT EXISTS edge_learning_daily_snapshots_vnext (
  snapshot_id text PRIMARY KEY,
  cycle_id text NOT NULL UNIQUE,
  as_of timestamptz NOT NULL,
  snapshot_status text NOT NULL CHECK (snapshot_status IN ('COMPLETE','PARTIAL')),
  runs_analyzed integer NOT NULL CHECK (runs_analyzed >= 0),
  canonical_runs integer NOT NULL CHECK (canonical_runs >= 0),
  diagnostic_runs integer NOT NULL CHECK (diagnostic_runs >= 0),
  manual_runs integer NOT NULL CHECK (manual_runs >= 0),
  shadow_runs integer NOT NULL CHECK (shadow_runs >= 0),
  matured_outcomes integer NOT NULL CHECK (matured_outcomes >= 0),
  scorable_outcomes integer NOT NULL CHECK (scorable_outcomes >= 0),
  data_gap_outcomes integer NOT NULL CHECK (data_gap_outcomes >= 0),
  new_observations integer NOT NULL CHECK (new_observations >= 0),
  active_hypotheses integer NOT NULL DEFAULT 0 CHECK (active_hypotheses >= 0),
  active_challengers integer NOT NULL DEFAULT 0 CHECK (active_challengers >= 0),
  approval_required integer NOT NULL DEFAULT 0 CHECK (approval_required >= 0),
  data_quality_state text NOT NULL,
  snapshot jsonb NOT NULL,
  methodology_versions jsonb NOT NULL DEFAULT '{"EDGE":"EDGE_V1"}'::jsonb,
  source_lineage jsonb NOT NULL DEFAULT '{}'::jsonb,
  content_hash text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  CHECK (canonical_runs + diagnostic_runs + manual_runs + shadow_runs <= runs_analyzed),
  CHECK (scorable_outcomes + data_gap_outcomes <= matured_outcomes)
);

CREATE INDEX IF NOT EXISTS idx_edge_learning_daily_snapshots_vnext_asof
ON edge_learning_daily_snapshots_vnext(as_of DESC);

INSERT INTO schema_meta(schema_version, applied_at)
VALUES (6, now())
ON CONFLICT (schema_version) DO NOTHING;

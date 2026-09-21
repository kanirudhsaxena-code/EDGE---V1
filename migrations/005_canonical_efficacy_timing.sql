-- EDGE Stocks canonical efficacy/timing governance
-- Frozen 21 Sep 2026. Additive governance only; frozen EDGE scoring is unchanged.

CREATE TABLE IF NOT EXISTS edge_recommendation_governance (
    recommendation_id text PRIMARY KEY REFERENCES recommendations(recommendation_id),
    canonical_key text NOT NULL,
    ticker text NOT NULL,
    target_trading_date date NOT NULL,
    forecast_horizon text NOT NULL,
    candidate_type text NOT NULL CHECK (
      candidate_type IN (
        'LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
        'EXCEPTION_CANONICAL','DIAGNOSTIC_SNAPSHOT'
      )
    ),
    requested_at timestamptz NOT NULL,
    completed_at timestamptz NOT NULL,
    ordinary_cutoff_at timestamptz,
    hard_boundary_at timestamptz,
    research_fresh_at timestamptz,
    fallback_reason text,
    created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_edge_recommendation_governance_key
ON edge_recommendation_governance(canonical_key, completed_at DESC);

CREATE TABLE IF NOT EXISTS edge_canonical_selections (
    canonical_key text PRIMARY KEY,
    ticker text NOT NULL,
    target_trading_date date NOT NULL,
    forecast_horizon text NOT NULL,
    selection_status text NOT NULL CHECK(selection_status IN ('SELECTED','CANONICAL_MISSED')),
    canonical_type text NOT NULL CHECK(
      canonical_type IN (
        'LEGACY_CANONICAL','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
        'EXCEPTION_CANONICAL','CANONICAL_MISSED'
      )
    ),
    selected_recommendation_id text REFERENCES recommendations(recommendation_id),
    selected_at timestamptz NOT NULL DEFAULT now(),
    selection_reason text,
    CHECK(
      (selection_status='SELECTED' AND selected_recommendation_id IS NOT NULL)
      OR
      (selection_status='CANONICAL_MISSED' AND selected_recommendation_id IS NULL)
    ),
    UNIQUE(ticker,target_trading_date,forecast_horizon)
);

CREATE INDEX IF NOT EXISTS idx_edge_canonical_selections_target
ON edge_canonical_selections(target_trading_date,ticker);

-- Historical migration rule: one final verdict per ticker + original run date + horizon.
-- The latest immutable production recommendation of that historical day wins.
INSERT INTO edge_recommendation_governance(
  recommendation_id,canonical_key,ticker,target_trading_date,forecast_horizon,
  candidate_type,requested_at,completed_at,ordinary_cutoff_at,hard_boundary_at,
  research_fresh_at,fallback_reason
)
SELECT r.recommendation_id,
       upper(r.ticker)||'|'||to_char((r.run_timestamp AT TIME ZONE 'Asia/Kolkata')::date,'YYYY-MM-DD')||'|'||r.forecast_horizon,
       upper(r.ticker),
       (r.run_timestamp AT TIME ZONE 'Asia/Kolkata')::date,
       r.forecast_horizon,
       'LEGACY_CANDIDATE',
       r.run_timestamp,
       r.run_timestamp,
       NULL,NULL,
       erb.research_fresh_at,
       'Pre-activation historical run retained under LEGACY_CANONICAL migration rule.'
FROM recommendations r
LEFT JOIN recommendation_research_bundle rrb USING(recommendation_id)
LEFT JOIN edge_research_bundles erb USING(bundle_id)
WHERE (r.run_timestamp AT TIME ZONE 'Asia/Kolkata')::date < DATE '2026-09-22'
ON CONFLICT (recommendation_id) DO NOTHING;

INSERT INTO edge_canonical_selections(
  canonical_key,ticker,target_trading_date,forecast_horizon,
  selection_status,canonical_type,selected_recommendation_id,selected_at,selection_reason
)
SELECT DISTINCT ON (g.canonical_key)
       g.canonical_key,g.ticker,g.target_trading_date,g.forecast_horizon,
       'SELECTED','LEGACY_CANONICAL',g.recommendation_id,now(),
       'Latest valid immutable recommendation for the historical ticker/day/horizon; migrated without hindsight.'
FROM edge_recommendation_governance g
JOIN recommendations r USING(recommendation_id)
WHERE g.candidate_type='LEGACY_CANDIDATE'
ORDER BY g.canonical_key,r.run_timestamp DESC
ON CONFLICT (canonical_key) DO NOTHING;

-- Master efficacy membership is now canonical-selection driven.
UPDATE recommendation_lifecycle l
SET include_in_master_metrics = EXISTS (
  SELECT 1
  FROM edge_canonical_selections s
  WHERE s.selection_status='SELECTED'
    AND s.selected_recommendation_id=l.recommendation_id
),
updated_at=now();

ALTER TABLE recommendation_lifecycle
ALTER COLUMN include_in_master_metrics SET DEFAULT false;

CREATE OR REPLACE VIEW v_edge_canonical_history AS
SELECT s.canonical_key,s.ticker,s.target_trading_date,s.forecast_horizon,
       s.selection_status,s.canonical_type,s.selected_recommendation_id,s.selected_at,
       r.run_timestamp,r.definitive_forecast,r.definitive_recommendation,
       l.status AS lifecycle_status,p.outcome_verdict,p.model_return_pct
FROM edge_canonical_selections s
LEFT JOIN recommendations r ON r.recommendation_id=s.selected_recommendation_id
LEFT JOIN recommendation_lifecycle l ON l.recommendation_id=s.selected_recommendation_id
LEFT JOIN recommendation_performance p ON p.recommendation_id=s.selected_recommendation_id;


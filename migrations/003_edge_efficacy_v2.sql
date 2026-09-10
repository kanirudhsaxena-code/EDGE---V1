-- EDGE Efficacy Engine V2
-- Approved design: mandatory all-stock assessment on every run; each new recommendation
-- has a maximum five-trading-day lifecycle. Existing pre-V2 recommendations remain immutable.

ALTER TABLE outcome_checkpoints DROP CONSTRAINT IF EXISTS outcome_checkpoints_checkpoint_type_check;
ALTER TABLE outcome_checkpoints ADD CONSTRAINT outcome_checkpoints_checkpoint_type_check
CHECK (checkpoint_type = ANY (ARRAY['D+1'::text,'D+2'::text,'D+3'::text,'D+4'::text,'D+5'::text,'D+10'::text,'D+15'::text,'HORIZON'::text]));

CREATE TABLE IF NOT EXISTS recommendation_lifecycle (
    recommendation_id text PRIMARY KEY REFERENCES recommendations(recommendation_id),
    tracking_policy text NOT NULL CHECK (tracking_policy IN ('EDGE_D5_V2','LEGACY_PRE_V2')),
    include_in_master_metrics boolean NOT NULL DEFAULT true,
    horizon_days integer CHECK (horizon_days BETWEEN 1 AND 5),
    expiry_trading_date date,
    status text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED')),
    closure_reason text CHECK (closure_reason IN ('TARGET','STOP','D+5','MANUAL_EXIT','NOT_SCORABLE','LEGACY')),
    closed_at timestamptz,
    standard_model_capital numeric NOT NULL DEFAULT 100 CHECK (standard_model_capital > 0),
    actual_user_executed boolean NOT NULL DEFAULT false,
    actual_user_return_pct numeric,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now(),
    CHECK ((tracking_policy = 'LEGACY_PRE_V2') OR horizon_days IS NOT NULL),
    CHECK ((status = 'OPEN' AND closed_at IS NULL) OR status = 'CLOSED')
);

CREATE TABLE IF NOT EXISTS recommendation_performance (
    recommendation_id text PRIMARY KEY REFERENCES recommendations(recommendation_id),
    reference_price numeric,
    current_price numeric,
    current_return_pct numeric,
    mfe_pct numeric,
    mae_pct numeric,
    potential_gain_pct numeric,
    potential_loss_pct numeric,
    model_return_pct numeric,
    model_pnl_units numeric,
    direction_hit boolean,
    target_hit boolean,
    stop_hit boolean,
    zone_result text CHECK (zone_result IN ('FULL_HIT','PARTIAL_HIT','MISS','NOT_SCORABLE')),
    outcome_verdict text NOT NULL DEFAULT 'OPEN' CHECK (outcome_verdict IN ('OPEN','WIN','LOSS','FLAT','NOT_SCORABLE')),
    last_assessed_at timestamptz,
    notes text
);

CREATE TABLE IF NOT EXISTS model_portfolio_positions (
    position_id bigserial PRIMARY KEY,
    ticker text NOT NULL,
    opened_by_recommendation_id text NOT NULL REFERENCES recommendations(recommendation_id),
    opened_at timestamptz NOT NULL,
    entry_price numeric NOT NULL,
    standard_capital numeric NOT NULL DEFAULT 100 CHECK (standard_capital > 0),
    direction text NOT NULL CHECK (direction IN ('LONG','SHORT_AVOID')),
    status text NOT NULL DEFAULT 'OPEN' CHECK (status IN ('OPEN','CLOSED')),
    closed_by_recommendation_id text REFERENCES recommendations(recommendation_id),
    closed_at timestamptz,
    exit_price numeric,
    return_pct numeric,
    pnl_units numeric,
    closure_reason text,
    notes text
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_model_portfolio_one_open_per_ticker
ON model_portfolio_positions(ticker) WHERE status='OPEN';
CREATE INDEX IF NOT EXISTS idx_recommendation_lifecycle_status ON recommendation_lifecycle(status);
CREATE INDEX IF NOT EXISTS idx_recommendation_lifecycle_expiry ON recommendation_lifecycle(expiry_trading_date);
CREATE INDEX IF NOT EXISTS idx_recommendation_performance_verdict ON recommendation_performance(outcome_verdict);
CREATE INDEX IF NOT EXISTS idx_model_portfolio_status ON model_portfolio_positions(status);

CREATE OR REPLACE VIEW v_edge_stock_assessment AS
SELECT r.ticker,
       count(*) FILTER (WHERE l.include_in_master_metrics) AS recommendations,
       count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='OPEN') AS open_recommendations,
       count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED') AS closed_recommendations,
       round(100.0 * count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED' AND p.outcome_verdict='WIN') /
             NULLIF(count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED' AND p.outcome_verdict IN ('WIN','LOSS','FLAT')),0), 1) AS recommendation_hit_rate_pct,
       round(100.0 * count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED' AND p.direction_hit IS TRUE) /
             NULLIF(count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED' AND p.direction_hit IS NOT NULL),0), 1) AS direction_hit_rate_pct,
       round(100.0 * count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED' AND p.target_hit IS TRUE) /
             NULLIF(count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED' AND p.target_hit IS NOT NULL),0), 1) AS target_hit_rate_pct,
       round(avg(p.model_return_pct) FILTER (WHERE l.include_in_master_metrics AND p.outcome_verdict='WIN'),2) AS avg_gain_pct,
       round(avg(p.model_return_pct) FILTER (WHERE l.include_in_master_metrics AND p.outcome_verdict='LOSS'),2) AS avg_loss_pct,
       round(avg(p.mfe_pct) FILTER (WHERE l.include_in_master_metrics),2) AS avg_mfe_pct,
       round(avg(p.mae_pct) FILTER (WHERE l.include_in_master_metrics),2) AS avg_mae_pct,
       round(sum(p.model_pnl_units) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED'),2) AS cumulative_model_pnl_units
FROM recommendations r
JOIN recommendation_lifecycle l USING (recommendation_id)
LEFT JOIN recommendation_performance p USING (recommendation_id)
GROUP BY r.ticker;

CREATE OR REPLACE VIEW v_edge_master_assessment AS
SELECT count(*) FILTER (WHERE l.include_in_master_metrics) AS recommendations,
       count(DISTINCT r.ticker) FILTER (WHERE l.include_in_master_metrics) AS unique_stocks,
       count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='OPEN') AS open_recommendations,
       count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED') AS closed_recommendations,
       round(100.0 * count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED' AND p.outcome_verdict='WIN') /
             NULLIF(count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED' AND p.outcome_verdict IN ('WIN','LOSS','FLAT')),0), 1) AS recommendation_hit_rate_pct,
       round(100.0 * count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED' AND p.direction_hit IS TRUE) /
             NULLIF(count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED' AND p.direction_hit IS NOT NULL),0), 1) AS direction_hit_rate_pct,
       round(100.0 * count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED' AND p.target_hit IS TRUE) /
             NULLIF(count(*) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED' AND p.target_hit IS NOT NULL),0), 1) AS target_hit_rate_pct,
       round(avg(p.model_return_pct) FILTER (WHERE l.include_in_master_metrics AND p.outcome_verdict='WIN'),2) AS avg_gain_pct,
       round(avg(p.model_return_pct) FILTER (WHERE l.include_in_master_metrics AND p.outcome_verdict='LOSS'),2) AS avg_loss_pct,
       round(avg(p.mfe_pct) FILTER (WHERE l.include_in_master_metrics),2) AS avg_mfe_pct,
       round(avg(p.mae_pct) FILTER (WHERE l.include_in_master_metrics),2) AS avg_mae_pct,
       round(sum(p.model_pnl_units) FILTER (WHERE l.include_in_master_metrics AND l.status='CLOSED'),2) AS cumulative_model_pnl_units
FROM recommendations r
JOIN recommendation_lifecycle l USING (recommendation_id)
LEFT JOIN recommendation_performance p USING (recommendation_id);

CREATE OR REPLACE VIEW v_edge_active_calls AS
WITH open_counts AS (
  SELECT r.ticker, count(*) AS open_recommendations
  FROM recommendations r JOIN recommendation_lifecycle l USING (recommendation_id)
  WHERE l.include_in_master_metrics AND l.status='OPEN'
  GROUP BY r.ticker
), latest AS (
  SELECT DISTINCT ON (r.ticker)
         r.ticker, r.recommendation_id, r.run_timestamp, r.definitive_forecast,
         r.definitive_recommendation, r.expected_price_zone_low, r.expected_price_zone_high,
         l.expiry_trading_date, p.current_price, p.current_return_pct, p.mfe_pct, p.mae_pct,
         p.target_hit, p.stop_hit, p.outcome_verdict
  FROM recommendations r
  JOIN recommendation_lifecycle l USING (recommendation_id)
  LEFT JOIN recommendation_performance p USING (recommendation_id)
  WHERE l.include_in_master_metrics AND l.status='OPEN'
  ORDER BY r.ticker, r.run_timestamp DESC
)
SELECT latest.*, open_counts.open_recommendations
FROM latest JOIN open_counts USING (ticker)
ORDER BY ticker;

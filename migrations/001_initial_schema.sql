CREATE TABLE IF NOT EXISTS schema_meta (
  schema_version integer PRIMARY KEY,
  applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS model_versions (
  model_version text PRIMARY KEY,
  status text NOT NULL CHECK(status IN ('DRAFT','FROZEN','PRODUCTION_LOCKED','RETIRED')),
  freeze_date date,
  specification_ref text,
  specification_hash text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS edge_runs (
  run_id bigserial PRIMARY KEY,
  command_type text NOT NULL CHECK(command_type IN ('EDGE','EDGE_UPDATE','EDGE_OUTCOME','EDGE_STATUS','EDGE_EFFICACY','TEST')),
  ticker text NOT NULL,
  run_timestamp timestamptz NOT NULL,
  model_version text NOT NULL REFERENCES model_versions(model_version),
  status text NOT NULL CHECK(status IN ('STARTED','COMMITTED','FAILED','CANCELLED')),
  parent_run_id bigint REFERENCES edge_runs(run_id),
  notes text
);

CREATE TABLE IF NOT EXISTS recommendations (
  recommendation_pk bigserial PRIMARY KEY,
  recommendation_id text NOT NULL UNIQUE,
  parent_recommendation_id text REFERENCES recommendations(recommendation_id),
  run_id bigint NOT NULL UNIQUE REFERENCES edge_runs(run_id),
  model_version text NOT NULL REFERENCES model_versions(model_version),
  ticker text NOT NULL,
  company_name text,
  run_timestamp timestamptz NOT NULL,
  forecast_horizon text NOT NULL,
  bull_probability numeric(6,3) NOT NULL CHECK(bull_probability BETWEEN 0 AND 100),
  base_probability numeric(6,3) NOT NULL CHECK(base_probability BETWEEN 0 AND 100),
  bear_probability numeric(6,3) NOT NULL CHECK(bear_probability BETWEEN 0 AND 100),
  definitive_forecast text NOT NULL CHECK(definitive_forecast IN ('BULLISH','BASE_RANGE','BEARISH')),
  expected_price_zone_low numeric,
  expected_price_zone_high numeric,
  des numeric(7,3) NOT NULL CHECK(des BETWEEN -100 AND 100),
  market_trust_score numeric(6,3) NOT NULL CHECK(market_trust_score BETWEEN 0 AND 100),
  market_trust_band text NOT NULL,
  bot_score numeric(6,3) NOT NULL CHECK(bot_score BETWEEN 0 AND 100),
  bot_grade text NOT NULL CHECK(bot_grade IN ('C','B','A','A+','A++')),
  decision_ladder text NOT NULL CHECK(decision_ladder IN ('OBSERVE','WATCHLIST','INVESTIGATION','PILOT','PARTIAL','FULL')),
  definitive_recommendation text NOT NULL,
  holding_status_known boolean NOT NULL DEFAULT false,
  event_shock_level text NOT NULL CHECK(event_shock_level IN ('LOW','MODERATE','HIGH','EXTREME')),
  active_override text CHECK(active_override IN ('O1','O2','O3') OR active_override IS NULL),
  evidence_gate_status text NOT NULL CHECK(evidence_gate_status IN ('PASS','GATED','NOT_VERIFIED')),
  rationale text,
  created_at timestamptz NOT NULL DEFAULT now(),
  committed_at timestamptz NOT NULL,
  record_hash text,
  CHECK(abs((bull_probability + base_probability + bear_probability) - 100.0) <= 0.01),
  CHECK(expected_price_zone_high IS NULL OR expected_price_zone_low IS NULL OR expected_price_zone_high >= expected_price_zone_low)
);

CREATE TABLE IF NOT EXISTS evidence_items (
  evidence_id bigserial PRIMARY KEY,
  ticker text NOT NULL,
  evidence_type text NOT NULL,
  source_kind text NOT NULL CHECK(source_kind IN ('SCREENSHOT','WEB_RESEARCH','CORPORATE_SOURCE','EXCHANGE_SOURCE','OTHER_PERMITTED')),
  capture_timestamp timestamptz,
  publication_timestamp timestamptz,
  event_timestamp timestamptz,
  ingestion_timestamp timestamptz NOT NULL DEFAULT now(),
  freshness text NOT NULL CHECK(freshness IN ('FRESH','AGING','STALE','UNKNOWN','N/A')),
  quality text NOT NULL CHECK(quality IN ('HIGH','MEDIUM','LOW','NOT_VERIFIED')),
  verification_status text NOT NULL CHECK(verification_status IN ('VERIFIED','NOT_VERIFIED','NOT_AVAILABLE')),
  file_ref text,
  source_ref text,
  observation text,
  content_hash text
);

CREATE TABLE IF NOT EXISTS recommendation_evidence (
  recommendation_id text NOT NULL REFERENCES recommendations(recommendation_id),
  evidence_id bigint NOT NULL REFERENCES evidence_items(evidence_id),
  use_role text NOT NULL,
  PRIMARY KEY(recommendation_id, evidence_id)
);

CREATE TABLE IF NOT EXISTS component_scores (
  component_score_id bigserial PRIMARY KEY,
  recommendation_id text NOT NULL REFERENCES recommendations(recommendation_id),
  component text NOT NULL,
  original_weight numeric(6,3) NOT NULL CHECK(original_weight BETWEEN 0 AND 100),
  raw_score integer CHECK(raw_score BETWEEN -2 AND 2),
  normalized_direction numeric(6,4) CHECK(normalized_direction BETWEEN -1 AND 1),
  evidence_quality text NOT NULL CHECK(evidence_quality IN ('HIGH','MEDIUM','LOW','NOT_VERIFIED')),
  availability_status text NOT NULL CHECK(availability_status IN ('AVAILABLE','NOT_VERIFIED','NOT_AVAILABLE','N/A')),
  normalized_weight numeric(7,4),
  weighted_contribution numeric(9,4),
  conflict_flag boolean NOT NULL DEFAULT false,
  gate_override_flag text,
  notes text,
  UNIQUE(recommendation_id, component)
);

CREATE TABLE IF NOT EXISTS market_trust (
  recommendation_id text PRIMARY KEY REFERENCES recommendations(recommendation_id),
  evidence_quality_score numeric(6,3) NOT NULL CHECK(evidence_quality_score BETWEEN 0 AND 100),
  freshness_score numeric(6,3) NOT NULL CHECK(freshness_score BETWEEN 0 AND 100),
  completeness_score numeric(6,3) NOT NULL CHECK(completeness_score BETWEEN 0 AND 100),
  directional_agreement_score numeric(6,3) NOT NULL CHECK(directional_agreement_score BETWEEN 0 AND 100),
  market_confirmation_score numeric(6,3) NOT NULL CHECK(market_confirmation_score BETWEEN 0 AND 100),
  market_trust_score numeric(6,3) NOT NULL CHECK(market_trust_score BETWEEN 0 AND 100),
  market_trust_band text NOT NULL
);

CREATE TABLE IF NOT EXISTS bot_scores (
  recommendation_id text PRIMARY KEY REFERENCES recommendations(recommendation_id),
  forecast_edge numeric(6,3) NOT NULL CHECK(forecast_edge BETWEEN 0 AND 100),
  market_trust numeric(6,3) NOT NULL CHECK(market_trust BETWEEN 0 AND 100),
  structure_pattern_quality numeric(6,3) NOT NULL CHECK(structure_pattern_quality BETWEEN 0 AND 100),
  pv_pvpo_confirmation numeric(6,3) NOT NULL CHECK(pv_pvpo_confirmation BETWEEN 0 AND 100),
  catalyst_asymmetry numeric(6,3) NOT NULL CHECK(catalyst_asymmetry BETWEEN 0 AND 100),
  execution_quality numeric(6,3) NOT NULL CHECK(execution_quality BETWEEN 0 AND 100),
  bot_score numeric(6,3) NOT NULL CHECK(bot_score BETWEEN 0 AND 100),
  bot_grade text NOT NULL CHECK(bot_grade IN ('C','B','A','A+','A++')),
  decision_ladder text NOT NULL CHECK(decision_ladder IN ('OBSERVE','WATCHLIST','INVESTIGATION','PILOT','PARTIAL','FULL'))
);

CREATE TABLE IF NOT EXISTS execution_plans (
  recommendation_id text PRIMARY KEY REFERENCES recommendations(recommendation_id),
  instrument text NOT NULL CHECK(instrument IN ('EQUITY','CALL','PUT','NONE')),
  entry_low numeric,
  entry_high numeric,
  stop_price numeric,
  invalidation_text text,
  target1 numeric,
  target2 numeric,
  risk_per_unit numeric,
  reward_to_t1 numeric,
  reward_to_t2 numeric,
  rr_t1 numeric,
  rr_t2 numeric,
  risk_unit_category text CHECK(risk_unit_category IN ('0','0.25R','0.50R','1.00R')),
  time_exit text,
  option_strike numeric,
  option_expiry date,
  observed_premium numeric,
  execution_quality_score numeric(6,3) CHECK(execution_quality_score BETWEEN 0 AND 100),
  execution_quality_level text,
  option_suitability_status text,
  notes text,
  CHECK(entry_high IS NULL OR entry_low IS NULL OR entry_high >= entry_low)
);

CREATE TABLE IF NOT EXISTS outcome_checkpoints (
  checkpoint_id bigserial PRIMARY KEY,
  recommendation_id text NOT NULL REFERENCES recommendations(recommendation_id),
  checkpoint_type text NOT NULL CHECK(checkpoint_type IN ('D+1','D+3','D+5','D+10','D+15','HORIZON')),
  due_date date,
  status text NOT NULL CHECK(status IN ('DUE','CAPTURED','NOT_SCORABLE','CLOSED')),
  observed_at timestamptz,
  actual_price numeric,
  period_high numeric,
  period_low numeric,
  option_premium numeric,
  source_ref text,
  notes text,
  UNIQUE(recommendation_id, checkpoint_type)
);

CREATE TABLE IF NOT EXISTS efficacy_results (
  efficacy_id bigserial PRIMARY KEY,
  recommendation_id text NOT NULL REFERENCES recommendations(recommendation_id),
  checkpoint_id bigint REFERENCES outcome_checkpoints(checkpoint_id),
  direction_result text CHECK(direction_result IN ('HIT','MISS','NEUTRAL_AMBIGUOUS','NOT_SCORABLE')),
  zone_result text CHECK(zone_result IN ('FULL_HIT','PARTIAL_HIT','MISS','NOT_SCORABLE')),
  execution_result text CHECK(execution_result IN ('T2_HIT','T1_HIT','TIME_FLAT','STOP_HIT','SEVERE_FAILURE','NOT_SCORABLE')),
  execution_score integer CHECK(execution_score BETWEEN -2 AND 2),
  realized_r numeric,
  pnl numeric,
  mfe numeric,
  mae numeric,
  brier_score numeric,
  calibration_bucket text,
  primary_failure_code text,
  secondary_failure_codes text[],
  overall_verdict text,
  computed_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(recommendation_id, checkpoint_id)
);

CREATE TABLE IF NOT EXISTS failure_codes (
  failure_code text PRIMARY KEY,
  description text NOT NULL
);

CREATE TABLE IF NOT EXISTS change_log (
  change_id bigserial PRIMARY KEY,
  change_timestamp timestamptz NOT NULL DEFAULT now(),
  model_version text,
  schema_version integer,
  change_type text NOT NULL,
  description text NOT NULL,
  rationale text,
  approved_by text
);

CREATE INDEX IF NOT EXISTS idx_edge_runs_ticker_time ON edge_runs(ticker, run_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_recommendations_ticker_time ON recommendations(ticker, run_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_evidence_ticker_time ON evidence_items(ticker, ingestion_timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_checkpoints_due ON outcome_checkpoints(status, due_date);
CREATE INDEX IF NOT EXISTS idx_efficacy_recommendation ON efficacy_results(recommendation_id);

INSERT INTO schema_meta(schema_version, applied_at)
VALUES (1, now())
ON CONFLICT (schema_version) DO NOTHING;

INSERT INTO model_versions(model_version,status,freeze_date,specification_ref,created_at)
VALUES ('EDGE_V1','FROZEN',DATE '2026-09-09','EDGE_V1_Master_Specification',now())
ON CONFLICT (model_version) DO NOTHING;

INSERT INTO failure_codes(failure_code,description) VALUES
('F1','Direction/structure misread'),
('F2','PV/PVPO misread'),
('F3','Pattern failure'),
('F4','Catalyst/news error or missed event'),
('F5','Fundamental/valuation thesis error'),
('F6','Institutional/relative-strength misread'),
('F7','Event shock / gap'),
('F8','Entry/stop/target execution design'),
('F9','Options strike/expiry/premium selection'),
('F10','Evidence stale/incomplete/ambiguous'),
('F11','Probability overconfidence/underconfidence'),
('F12','Other documented cause')
ON CONFLICT (failure_code) DO NOTHING;
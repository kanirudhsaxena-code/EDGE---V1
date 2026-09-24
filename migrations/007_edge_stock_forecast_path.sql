-- Phase 2.0 G5: additive immutable D through D+4 forecast-path persistence.
-- This migration does not alter frozen EDGE scoring, probabilities, Market Trust,
-- recommendation logic, canonical selection, efficacy populations, or execution.

create table if not exists edge_stock_forecast_paths (
  recommendation_id text primary key references recommendations(recommendation_id),
  path_version text not null check (path_version = 'EDGE_STOCK_FORECAST_PATH_V1'),
  source_run_id text not null,
  issued_at timestamptz not null,
  payload_hash text not null,
  created_at timestamptz not null default now()
);

create table if not exists edge_stock_forecast_path_rows (
  recommendation_id text not null references edge_stock_forecast_paths(recommendation_id),
  horizon_index smallint not null check (horizon_index between 0 and 4),
  horizon_label text not null check (horizon_label in ('D','D+1','D+2','D+3','D+4')),
  target_trading_date date not null,
  direction text not null check (direction in ('BULL','BASE','BEAR')),
  bull_probability numeric(7,4) not null check (bull_probability between 0 and 100),
  base_probability numeric(7,4) not null check (base_probability between 0 and 100),
  bear_probability numeric(7,4) not null check (bear_probability between 0 and 100),
  expected_centre numeric,
  outer_expected_zone_low numeric not null,
  outer_expected_zone_high numeric not null,
  evidence_basis text not null,
  regime_context text not null,
  verification_state text not null,
  lineage jsonb not null,
  created_at timestamptz not null default now(),
  primary key (recommendation_id, horizon_index),
  unique (recommendation_id, horizon_label),
  unique (recommendation_id, target_trading_date),
  check (abs((bull_probability + base_probability + bear_probability) - 100.0) <= 0.01),
  check (outer_expected_zone_low <= outer_expected_zone_high),
  check (
    direction = case
      when bull_probability >= base_probability and bull_probability >= bear_probability then 'BULL'
      when base_probability >= bull_probability and base_probability >= bear_probability then 'BASE'
      else 'BEAR'
    end
  )
);

-- Issuance rows are immutable. Outcomes, when introduced by governed lifecycle
-- work, must be appended separately rather than rewriting the issued forecast.
create or replace function block_edge_stock_forecast_path_mutation()
returns trigger language plpgsql as $$
begin
  raise exception 'EDGE stock forecast path issuance rows are immutable';
end;
$$;

drop trigger if exists trg_edge_stock_forecast_paths_immutable on edge_stock_forecast_paths;
create trigger trg_edge_stock_forecast_paths_immutable
before update or delete on edge_stock_forecast_paths
for each row execute function block_edge_stock_forecast_path_mutation();

drop trigger if exists trg_edge_stock_forecast_path_rows_immutable on edge_stock_forecast_path_rows;
create trigger trg_edge_stock_forecast_path_rows_immutable
before update or delete on edge_stock_forecast_path_rows
for each row execute function block_edge_stock_forecast_path_mutation();

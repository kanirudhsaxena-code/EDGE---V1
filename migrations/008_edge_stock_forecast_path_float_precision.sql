-- Phase 2.0 G5: preserve exact producer float values for immutable hash readback.
--
-- Migration 007 used NUMERIC(7,4) for probabilities. That scale can quantize
-- full-precision producer values before they are read back, causing a false
-- immutable payload-hash mismatch even when the governed row set is otherwise
-- intact. G5 hashes Python IEEE-754 float values, so persisted numeric forecast
-- fields must preserve those values without scale truncation.
--
-- This migration is additive to governance behavior: it does not change EDGE
-- scoring, probabilities, recommendation logic, canonical selection, efficacy,
-- Market Trust, execution, or trading. Existing issuance rows remain immutable.

alter table edge_stock_forecast_path_rows
  alter column bull_probability type double precision using bull_probability::double precision,
  alter column base_probability type double precision using base_probability::double precision,
  alter column bear_probability type double precision using bear_probability::double precision,
  alter column expected_centre type double precision using expected_centre::double precision,
  alter column outer_expected_zone_low type double precision using outer_expected_zone_low::double precision,
  alter column outer_expected_zone_high type double precision using outer_expected_zone_high::double precision;

-- Governed self-maintaining NSE calendar cache and exact session proofs.
-- Append-only; provider refreshes create new snapshots and the latest verified
-- rows are selected through read-only views.

CREATE TABLE IF NOT EXISTS nse_calendar_year_snapshots (
  id bigserial PRIMARY KEY,
  calendar_year integer NOT NULL CHECK (calendar_year BETWEEN 2000 AND 2200),
  provider text NOT NULL CHECK (provider='UPSTOX'),
  status text NOT NULL CHECK (status='VERIFIED'),
  trading_holidays jsonb NOT NULL,
  special_timing_dates jsonb NOT NULL,
  source_ref text NOT NULL,
  acquired_at timestamptz NOT NULL,
  payload_hash text NOT NULL CHECK (length(payload_hash)=64),
  inserted_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(calendar_year,payload_hash)
);

CREATE INDEX IF NOT EXISTS nse_calendar_year_snapshots_year_time_idx
  ON nse_calendar_year_snapshots(calendar_year, acquired_at DESC);

CREATE TABLE IF NOT EXISTS nse_session_proofs (
  id bigserial PRIMARY KEY,
  session_date date NOT NULL,
  session_state text NOT NULL CHECK (session_state IN (
    'TRADING_DAY','TRADING_HOLIDAY','WEEKEND','SPECIAL_TIMING'
  )),
  preopen_eligible boolean NOT NULL,
  market_open_at timestamptz,
  market_close_at timestamptz,
  provider text NOT NULL CHECK (provider='UPSTOX'),
  timing_source_ref text,
  calendar_source_ref text NOT NULL,
  acquired_at timestamptz NOT NULL,
  payload jsonb NOT NULL,
  payload_hash text NOT NULL CHECK (length(payload_hash)=64),
  status text NOT NULL CHECK (status='VERIFIED'),
  inserted_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(session_date,payload_hash)
);

CREATE INDEX IF NOT EXISTS nse_session_proofs_date_time_idx
  ON nse_session_proofs(session_date, acquired_at DESC);

CREATE OR REPLACE VIEW v_nse_calendar_year_latest AS
SELECT DISTINCT ON (calendar_year)
  calendar_year,provider,status,trading_holidays,special_timing_dates,
  source_ref,acquired_at,payload_hash,inserted_at
FROM nse_calendar_year_snapshots
WHERE status='VERIFIED'
ORDER BY calendar_year, acquired_at DESC, id DESC;

CREATE OR REPLACE VIEW v_nse_session_latest AS
SELECT DISTINCT ON (session_date)
  session_date,session_state,preopen_eligible,market_open_at,market_close_at,
  provider,timing_source_ref,calendar_source_ref,acquired_at,payload,payload_hash,
  status,inserted_at
FROM nse_session_proofs
WHERE status='VERIFIED'
ORDER BY session_date, acquired_at DESC, id DESC;

CREATE OR REPLACE FUNCTION prevent_nse_calendar_snapshot_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'governed NSE calendar snapshots are append-only';
END $$;

DROP TRIGGER IF EXISTS trg_nse_calendar_year_immutable ON nse_calendar_year_snapshots;
CREATE TRIGGER trg_nse_calendar_year_immutable
BEFORE UPDATE OR DELETE ON nse_calendar_year_snapshots
FOR EACH ROW EXECUTE FUNCTION prevent_nse_calendar_snapshot_mutation();

DROP TRIGGER IF EXISTS trg_nse_session_proofs_immutable ON nse_session_proofs;
CREATE TRIGGER trg_nse_session_proofs_immutable
BEFORE UPDATE OR DELETE ON nse_session_proofs
FOR EACH ROW EXECUTE FUNCTION prevent_nse_calendar_snapshot_mutation();

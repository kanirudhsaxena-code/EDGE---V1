-- EDGE Stocks execution-layer historical cache.
-- Mirrors the MDOS market-cache-document-v1 integrity contract used by 5DR.
-- No methodology/scoring/recommendation/learning changes.
CREATE SCHEMA IF NOT EXISTS market_data_cache;

CREATE TABLE IF NOT EXISTS market_data_cache.market_cache_documents (
  series_id text PRIMARY KEY,
  provider_id text NOT NULL,
  source_semantic text NOT NULL,
  document_sha256 char(64) NOT NULL,
  dataset_sha256 char(64) NOT NULL,
  latest_timestamp timestamptz NULL,
  record_count integer NOT NULL CHECK (record_count >= 0),
  document jsonb NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now(),
  CHECK (document->>'schema' = 'market-cache-document-v1'),
  CHECK (document->>'series_id' = series_id),
  CHECK (document->>'document_sha256' = document_sha256::text),
  CHECK (document->>'dataset_sha256' = dataset_sha256::text)
);

CREATE INDEX IF NOT EXISTS market_cache_documents_updated_at_idx
  ON market_data_cache.market_cache_documents(updated_at);

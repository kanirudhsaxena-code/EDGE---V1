-- EDGE Research Bundle V1
-- Clarification amendment: ChatGPT fresh web research is mandatory for every governed
-- EDGE run; Upstox may supply structured supporting evidence but cannot independently
-- validate material research claims. Exa is optional retrieval infrastructure.

CREATE TABLE IF NOT EXISTS edge_research_bundles (
    bundle_id text PRIMARY KEY,
    ticker text NOT NULL,
    contract_version text NOT NULL CHECK (contract_version='EDGE_RESEARCH_BUNDLE_V1'),
    research_authority text NOT NULL CHECK (research_authority='CHATGPT'),
    research_fresh_at timestamptz NOT NULL,
    created_at timestamptz NOT NULL,
    payload jsonb NOT NULL,
    payload_hash text NOT NULL CHECK (length(payload_hash)=64),
    status text NOT NULL CHECK (status IN ('READY','CONSUMED','BLOCKED')),
    inserted_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_edge_research_bundles_ticker_fresh
ON edge_research_bundles(ticker,research_fresh_at DESC);

CREATE TABLE IF NOT EXISTS recommendation_research_bundle (
    recommendation_id text PRIMARY KEY REFERENCES recommendations(recommendation_id),
    bundle_id text NOT NULL REFERENCES edge_research_bundles(bundle_id),
    linked_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION prevent_edge_research_bundle_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'edge_research_bundles are immutable';
END $$;

DROP TRIGGER IF EXISTS trg_edge_research_bundles_immutable ON edge_research_bundles;
CREATE TRIGGER trg_edge_research_bundles_immutable
BEFORE UPDATE OR DELETE ON edge_research_bundles
FOR EACH ROW EXECUTE FUNCTION prevent_edge_research_bundle_mutation();

CREATE OR REPLACE FUNCTION prevent_recommendation_research_bundle_mutation()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION 'recommendation research-bundle links are immutable';
END $$;

DROP TRIGGER IF EXISTS trg_recommendation_research_bundle_immutable ON recommendation_research_bundle;
CREATE TRIGGER trg_recommendation_research_bundle_immutable
BEFORE UPDATE OR DELETE ON recommendation_research_bundle
FOR EACH ROW EXECUTE FUNCTION prevent_recommendation_research_bundle_mutation();

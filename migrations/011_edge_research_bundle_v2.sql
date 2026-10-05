-- EDGE Research Bundle V2: production-owned web research bound to immutable DATA lifecycle.
-- V1 ChatGPT bundles remain readable for historical/compatibility runs.

ALTER TABLE edge_research_bundles
ADD COLUMN IF NOT EXISTS lifecycle_id text,
ADD COLUMN IF NOT EXISTS market_snapshot_id text;

ALTER TABLE edge_research_bundles
DROP CONSTRAINT IF EXISTS edge_research_bundles_contract_version_check;
ALTER TABLE edge_research_bundles
DROP CONSTRAINT IF EXISTS edge_research_bundles_research_authority_check;

ALTER TABLE edge_research_bundles
ADD CONSTRAINT edge_research_bundles_contract_version_check
CHECK (contract_version IN ('EDGE_RESEARCH_BUNDLE_V1','EDGE_RESEARCH_BUNDLE_V2'));

ALTER TABLE edge_research_bundles
ADD CONSTRAINT edge_research_bundles_research_authority_check
CHECK (
  (contract_version='EDGE_RESEARCH_BUNDLE_V1' AND research_authority='CHATGPT')
  OR
  (contract_version='EDGE_RESEARCH_BUNDLE_V2' AND research_authority='EDGE_SYSTEM')
);

ALTER TABLE edge_research_bundles
DROP CONSTRAINT IF EXISTS edge_research_bundles_lifecycle_fk;
ALTER TABLE edge_research_bundles
ADD CONSTRAINT edge_research_bundles_lifecycle_fk
FOREIGN KEY (lifecycle_id) REFERENCES edge_run_lifecycles(lifecycle_id);

ALTER TABLE edge_research_bundles
DROP CONSTRAINT IF EXISTS edge_research_bundles_market_snapshot_fk;
ALTER TABLE edge_research_bundles
ADD CONSTRAINT edge_research_bundles_market_snapshot_fk
FOREIGN KEY (market_snapshot_id) REFERENCES edge_market_snapshots(snapshot_id);

CREATE UNIQUE INDEX IF NOT EXISTS idx_edge_research_bundle_lifecycle_v2
ON edge_research_bundles(lifecycle_id)
WHERE lifecycle_id IS NOT NULL;

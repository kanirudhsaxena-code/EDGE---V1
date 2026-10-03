-- G5.1 Anytime Invocation & Canonical Governance
-- Additive only: frozen EDGE V1 scoring, G5 D:D+4 methodology and benchmark
-- selection rules remain unchanged. Valid user snapshots are separately retained
-- for all-run efficacy and never compete with the standardized pre-open benchmark.

ALTER TABLE edge_recommendation_governance
ADD COLUMN IF NOT EXISTS trigger_type text,
ADD COLUMN IF NOT EXISTS evidence_mode text,
ADD COLUMN IF NOT EXISTS market_session_as_of date,
ADD COLUMN IF NOT EXISTS benchmark_role text;

ALTER TABLE edge_recommendation_governance
DROP CONSTRAINT IF EXISTS edge_recommendation_governance_trigger_type_check;
ALTER TABLE edge_recommendation_governance
ADD CONSTRAINT edge_recommendation_governance_trigger_type_check
CHECK (trigger_type IS NULL OR trigger_type IN ('USER','SCHEDULED'));

ALTER TABLE edge_recommendation_governance
DROP CONSTRAINT IF EXISTS edge_recommendation_governance_evidence_mode_check;
ALTER TABLE edge_recommendation_governance
ADD CONSTRAINT edge_recommendation_governance_evidence_mode_check
CHECK (evidence_mode IS NULL OR evidence_mode IN ('CLOSED_SESSION','PREOPEN','LIVE_INTRADAY','SESSION_FINAL'));

ALTER TABLE edge_recommendation_governance
DROP CONSTRAINT IF EXISTS edge_recommendation_governance_benchmark_role_check;
ALTER TABLE edge_recommendation_governance
ADD CONSTRAINT edge_recommendation_governance_benchmark_role_check
CHECK (benchmark_role IS NULL OR benchmark_role IN ('NONE','SESSION_PREOPEN'));

ALTER TABLE edge_recommendation_governance
DROP CONSTRAINT IF EXISTS edge_recommendation_governance_candidate_type_check;

ALTER TABLE edge_recommendation_governance
ADD CONSTRAINT edge_recommendation_governance_candidate_type_check
CHECK (
  candidate_type IN (
    'LEGACY_CANDIDATE',
    'PREOPEN_CANONICAL',
    'OVERNIGHT_FALLBACK_CANONICAL',
    'EXCEPTION_CANONICAL',
    'USER_CANONICAL_SNAPSHOT',
    'DIAGNOSTIC_SNAPSHOT'
  )
);

-- All-run efficacy deliberately does not reuse include_in_master_metrics.
-- That flag remains benchmark-selection membership only.
CREATE OR REPLACE VIEW v_edge_all_run_assessment AS
SELECT
  count(*) FILTER (
    WHERE g.candidate_type IN (
      'LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
      'EXCEPTION_CANONICAL','USER_CANONICAL_SNAPSHOT'
    )
  ) AS recommendations,
  count(DISTINCT r.ticker) FILTER (
    WHERE g.candidate_type IN (
      'LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
      'EXCEPTION_CANONICAL','USER_CANONICAL_SNAPSHOT'
    )
  ) AS unique_stocks,
  count(*) FILTER (
    WHERE g.candidate_type IN (
      'LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
      'EXCEPTION_CANONICAL','USER_CANONICAL_SNAPSHOT'
    ) AND l.status='OPEN'
  ) AS open_recommendations,
  count(*) FILTER (
    WHERE g.candidate_type IN (
      'LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
      'EXCEPTION_CANONICAL','USER_CANONICAL_SNAPSHOT'
    ) AND l.status='CLOSED'
  ) AS closed_recommendations,
  count(*) FILTER (
    WHERE g.candidate_type IN (
      'LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
      'EXCEPTION_CANONICAL','USER_CANONICAL_SNAPSHOT'
    ) AND l.status='CLOSED' AND p.outcome_verdict IN ('WIN','LOSS','FLAT')
  ) AS scorable_recommendations,
  round(
    100.0 * count(*) FILTER (
      WHERE g.candidate_type IN (
        'LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
        'EXCEPTION_CANONICAL','USER_CANONICAL_SNAPSHOT'
      ) AND l.status='CLOSED' AND p.outcome_verdict='WIN'
    )
    / NULLIF(count(*) FILTER (
      WHERE g.candidate_type IN (
        'LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
        'EXCEPTION_CANONICAL','USER_CANONICAL_SNAPSHOT'
      ) AND l.status='CLOSED' AND p.outcome_verdict IN ('WIN','LOSS','FLAT')
    ),0),
    1
  ) AS recommendation_hit_rate_pct,
  round(
    100.0 * count(*) FILTER (
      WHERE g.candidate_type IN (
        'LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
        'EXCEPTION_CANONICAL','USER_CANONICAL_SNAPSHOT'
      ) AND l.status='CLOSED' AND p.direction_hit IS TRUE
    )
    / NULLIF(count(*) FILTER (
      WHERE g.candidate_type IN (
        'LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
        'EXCEPTION_CANONICAL','USER_CANONICAL_SNAPSHOT'
      ) AND l.status='CLOSED' AND p.direction_hit IS NOT NULL
    ),0),
    1
  ) AS direction_hit_rate_pct,
  round(
    100.0 * count(*) FILTER (
      WHERE g.candidate_type IN (
        'LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
        'EXCEPTION_CANONICAL','USER_CANONICAL_SNAPSHOT'
      ) AND l.status='CLOSED' AND p.target_hit IS TRUE
    )
    / NULLIF(count(*) FILTER (
      WHERE g.candidate_type IN (
        'LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
        'EXCEPTION_CANONICAL','USER_CANONICAL_SNAPSHOT'
      ) AND l.status='CLOSED' AND p.target_hit IS NOT NULL
    ),0),
    1
  ) AS target_hit_rate_pct
FROM recommendations r
JOIN recommendation_lifecycle l USING(recommendation_id)
JOIN edge_recommendation_governance g USING(recommendation_id)
LEFT JOIN recommendation_performance p USING(recommendation_id);

CREATE OR REPLACE VIEW v_edge_stock_all_run_assessment AS
SELECT
  r.ticker,
  count(*) AS recommendations,
  count(*) FILTER (WHERE l.status='OPEN') AS open_recommendations,
  count(*) FILTER (WHERE l.status='CLOSED') AS closed_recommendations,
  count(*) FILTER (
    WHERE l.status='CLOSED' AND p.outcome_verdict IN ('WIN','LOSS','FLAT')
  ) AS scorable_recommendations,
  round(
    100.0 * count(*) FILTER (WHERE l.status='CLOSED' AND p.outcome_verdict='WIN')
    / NULLIF(count(*) FILTER (
      WHERE l.status='CLOSED' AND p.outcome_verdict IN ('WIN','LOSS','FLAT')
    ),0),
    1
  ) AS recommendation_hit_rate_pct,
  round(
    100.0 * count(*) FILTER (WHERE l.status='CLOSED' AND p.direction_hit IS TRUE)
    / NULLIF(count(*) FILTER (
      WHERE l.status='CLOSED' AND p.direction_hit IS NOT NULL
    ),0),
    1
  ) AS direction_hit_rate_pct,
  round(
    100.0 * count(*) FILTER (WHERE l.status='CLOSED' AND p.target_hit IS TRUE)
    / NULLIF(count(*) FILTER (
      WHERE l.status='CLOSED' AND p.target_hit IS NOT NULL
    ),0),
    1
  ) AS target_hit_rate_pct
FROM recommendations r
JOIN recommendation_lifecycle l USING(recommendation_id)
JOIN edge_recommendation_governance g USING(recommendation_id)
LEFT JOIN recommendation_performance p USING(recommendation_id)
WHERE g.candidate_type IN (
  'LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL',
  'EXCEPTION_CANONICAL','USER_CANONICAL_SNAPSHOT'
)
GROUP BY r.ticker;

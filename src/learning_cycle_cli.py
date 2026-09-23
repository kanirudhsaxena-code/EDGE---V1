"""Governed autonomous EDGE Learning Lab daily cycle.

The cycle preserves the legacy learning_runs audit record and additionally emits
one immutable VNext daily snapshot plus immutable outcome observations. It does
not change EDGE scoring, thresholds, probabilities, Market Trust, BOT,
recommendations, execution rules, or production versions.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from .learning_snapshot import build_daily_snapshot, build_outcome_observation, content_hash


@dataclass(frozen=True)
class LearningCycleState:
    recommendation_sample_size: int
    independent_sample_size: int
    status: str
    note: str


def classify_learning_cycle(recommendation_sample_size: int, independent_sample_size: int) -> LearningCycleState:
    if recommendation_sample_size < 0 or independent_sample_size < 0:
        raise ValueError("sample sizes must be non-negative")
    if independent_sample_size == 0:
        return LearningCycleState(
            recommendation_sample_size,
            independent_sample_size,
            "DEFERRED",
            "No mature closed recommendation outcomes yet; learning inference is prohibited.",
        )
    return LearningCycleState(
        recommendation_sample_size,
        independent_sample_size,
        "COMPLETED",
        "Mature outcome sample detected; governance cycle opened for downstream candidate evaluation.",
    )


def _dict_rows(cur) -> list[dict]:
    columns=[item.name for item in cur.description]
    return [dict(zip(columns,row)) for row in cur.fetchall()]


def main() -> int:
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        print(json.dumps({"status": "BLOCKED_CONFIGURATION", "diagnostic_code": "DATABASE_URL_MISSING"}))
        return 2

    import psycopg

    now=datetime.now(ZoneInfo("Asia/Kolkata"))
    cycle_id=f"EDGE-LL-{now:%Y%m%d}"
    as_of=now.isoformat()

    conn = psycopg.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM recommendations")
            recommendation_sample = int(cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM recommendation_performance WHERE outcome_verdict <> 'OPEN'")
            independent_sample = int(cur.fetchone()[0])
            state = classify_learning_cycle(recommendation_sample, independent_sample)

            # Backward-compatible governance audit record.
            cur.execute(
                """
                INSERT INTO learning_runs
                (production_model_version, scope, status, recommendation_sample_size,
                 independent_sample_size, completed_at, notes)
                SELECT 'EDGE_V1','EDGE',%s,%s,%s,now(),%s
                WHERE NOT EXISTS (
                  SELECT 1
                  FROM learning_runs
                  WHERE (started_at AT TIME ZONE 'Asia/Kolkata')::date =
                        (now() AT TIME ZONE 'Asia/Kolkata')::date
                    AND notes LIKE 'Autonomous Learning Lab cycle:%%'
                )
                RETURNING learning_run_id
                """,
                (
                    state.status,
                    state.recommendation_sample_size,
                    state.independent_sample_size,
                    "Autonomous Learning Lab cycle: " + state.note,
                ),
            )
            inserted = cur.fetchone()

            # All current-day governed runs are learning evidence. Only the selected
            # canonical is official-efficacy eligible.
            cur.execute(
                """
                SELECT r.recommendation_id,r.run_id,r.ticker,g.target_trading_date,
                       CASE WHEN s.selected_recommendation_id=r.recommendation_id
                            THEN 'CANONICAL' ELSE 'DIAGNOSTIC' END AS run_role,
                       (s.selected_recommendation_id=r.recommendation_id) AS official_efficacy_eligible
                  FROM edge_recommendation_governance g
                  JOIN recommendations r USING(recommendation_id)
                  LEFT JOIN edge_canonical_selections s
                    ON s.canonical_key=g.canonical_key AND s.selection_status='SELECTED'
                 WHERE (g.completed_at AT TIME ZONE 'Asia/Kolkata')::date =
                       (now() AT TIME ZONE 'Asia/Kolkata')::date
                 ORDER BY g.completed_at,r.recommendation_id
                """
            )
            runs=_dict_rows(cur)

            # Only outcomes reconciled today are "new matured outcomes" for this
            # snapshot; lifetime efficacy remains in the canonical efficacy views.
            cur.execute(
                """
                SELECT r.recommendation_id,r.run_id,r.ticker,g.target_trading_date,
                       CASE WHEN s.selected_recommendation_id=r.recommendation_id
                            THEN 'CANONICAL' ELSE 'DIAGNOSTIC' END AS run_role,
                       (s.selected_recommendation_id=r.recommendation_id) AS official_efficacy_eligible,
                       p.outcome_verdict,p.model_return_pct,p.direction_hit,p.zone_result,
                       p.mfe_pct,p.mae_pct,p.last_assessed_at AS observed_at,
                       cp.source_ref
                  FROM recommendation_performance p
                  JOIN recommendations r USING(recommendation_id)
                  LEFT JOIN edge_recommendation_governance g USING(recommendation_id)
                  LEFT JOIN edge_canonical_selections s
                    ON s.selected_recommendation_id=r.recommendation_id
                  LEFT JOIN LATERAL (
                    SELECT source_ref
                      FROM outcome_checkpoints oc
                     WHERE oc.recommendation_id=r.recommendation_id
                       AND oc.observed_at IS NOT NULL
                     ORDER BY oc.observed_at DESC,oc.checkpoint_id DESC
                     LIMIT 1
                  ) cp ON true
                 WHERE p.outcome_verdict <> 'OPEN'
                   AND p.last_assessed_at IS NOT NULL
                   AND (p.last_assessed_at AT TIME ZONE 'Asia/Kolkata')::date =
                       (now() AT TIME ZONE 'Asia/Kolkata')::date
                 ORDER BY p.last_assessed_at,r.recommendation_id
                """
            )
            outcome_rows=_dict_rows(cur)

            observations=[]
            matured=[]
            for row in outcome_rows:
                if row.get("target_trading_date") is None:
                    # Preserve evidence integrity: an outcome without governed target
                    # lineage is a data gap, not a fabricated learning observation.
                    matured.append({"scorable":False,"data_gap":True})
                    continue
                row["target_trading_date"]=str(row["target_trading_date"])
                row["observed_at"]=row["observed_at"].isoformat() if row.get("observed_at") else as_of
                if not row.get("official_efficacy_eligible"):
                    row["exclusion_reason"]="NON_CANONICAL"
                observation=build_outcome_observation(row)
                if observation is not None:
                    observations.append(observation)
                verdict=str(row.get("outcome_verdict") or "")
                matured.append({
                    "scorable":bool(row.get("official_efficacy_eligible")) and verdict in {"WIN","LOSS","FLAT"},
                    "data_gap":verdict=="NOT_SCORABLE",
                })

            for observation in observations:
                digest=content_hash(observation)
                metrics=observation.get("metrics") or {}
                cur.execute(
                    """
                    INSERT INTO edge_learning_observations_vnext
                    (observation_id,recommendation_id,ticker,target_trading_date,run_role,
                     official_efficacy_eligible,dimension,observation_type,outcome_classification,
                     metrics,exclusion_reason,source_ref,observed_at,content_hash)
                    VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb,%s,%s,%s,%s)
                    ON CONFLICT (observation_id) DO NOTHING
                    """,
                    (
                        observation["observation_id"],observation["recommendation_id"],observation["ticker"],
                        observation["target_trading_date"],observation["run_role"],
                        observation["official_efficacy_eligible"],observation["dimension"],
                        observation["observation_type"],observation["outcome_classification"],
                        json.dumps(metrics,sort_keys=True,default=str),observation["exclusion_reason"],
                        observation["source_ref"],observation["observed_at"],digest,
                    ),
                )

            normalized_runs=[
                {
                    **row,
                    "target_trading_date":str(row["target_trading_date"]) if row.get("target_trading_date") else None,
                }
                for row in runs
            ]
            snapshot=build_daily_snapshot(
                cycle_id=cycle_id,
                as_of=as_of,
                runs=normalized_runs,
                observations=observations,
                matured_outcomes=matured,
                data_quality_state="PASS" if all(row.get("target_trading_date") for row in runs) else "PARTIAL_LINEAGE",
                source_lineage={
                    "engine_database":"EDGE",
                    "canonical_selection":"edge_canonical_selections",
                    "outcome_source":"recommendation_performance",
                },
            )
            counts=snapshot["counts"]
            cur.execute(
                """
                INSERT INTO edge_learning_daily_snapshots_vnext
                (snapshot_id,cycle_id,as_of,snapshot_status,runs_analyzed,canonical_runs,
                 diagnostic_runs,manual_runs,shadow_runs,matured_outcomes,scorable_outcomes,
                 data_gap_outcomes,new_observations,active_hypotheses,active_challengers,
                 approval_required,data_quality_state,snapshot,methodology_versions,
                 source_lineage,content_hash)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                        %s::jsonb,%s::jsonb,%s::jsonb,%s)
                ON CONFLICT (cycle_id) DO NOTHING
                """,
                (
                    snapshot["snapshot_id"],snapshot["cycle_id"],snapshot["as_of"],snapshot["snapshot_status"],
                    counts["runs_analyzed"],counts["canonical_runs"],counts["diagnostic_runs"],
                    counts["manual_runs"],counts["shadow_runs"],counts["matured_outcomes"],
                    counts["scorable_outcomes"],counts["data_gap_outcomes"],counts["new_observations"],
                    counts["active_hypotheses"],counts["active_challengers"],counts["approval_required"],
                    snapshot["data_quality_state"],json.dumps(snapshot["snapshot"],sort_keys=True,default=str),
                    json.dumps(snapshot["methodology_versions"],sort_keys=True,default=str),
                    json.dumps(snapshot["source_lineage"],sort_keys=True,default=str),snapshot["content_hash"],
                ),
            )

        conn.commit()
        handoff={
            "schema_version":"MDOS_LEARNING_LAB_HANDOFF_V1",
            "generated_at":now.astimezone(ZoneInfo("UTC")).isoformat().replace("+00:00","Z"),
            "engine":"EDGE_STOCKS",
            "snapshot":snapshot,
            "observations":observations,
            "candidates":[],
            "methodology_changed":False,
            "automatic_adoption_enabled":False,
            "production_change_allowed":False,
        }
        handoff_path=Path(os.environ.get("LEARNING_HANDOFF_PATH","edge-learning-lab-handoff.json"))
        handoff_path.write_text(
            json.dumps(handoff,sort_keys=True,separators=(",",":"),default=str)+"\n",
            encoding="utf-8",
        )
        print(
            json.dumps(
                {
                    "status": state.status,
                    "recommendation_sample_size": state.recommendation_sample_size,
                    "independent_sample_size": state.independent_sample_size,
                    "learning_run_id": None if inserted is None else inserted[0],
                    "snapshot_id": snapshot["snapshot_id"],
                    "observations_emitted": len(observations),
                    "handoff_path":str(handoff_path),
                    "methodology_changed": False,
                    "automatic_adoption_enabled": False,
                    "production_change_allowed": False,
                },
                sort_keys=True,
                default=str,
            )
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

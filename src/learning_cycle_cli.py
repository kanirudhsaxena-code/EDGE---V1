"""Governed autonomous EDGE Learning Lab cycle logger.

This module does not change EDGE scoring, weights, thresholds, DES, Market Trust,
probability calibration, recommendation semantics, or model versions. It only
assesses whether enough matured outcomes exist to open a learning cycle and
records that governance state in the existing learning_runs table.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass


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


def main() -> int:
    db_url = os.getenv("DATABASE_URL", "").strip()
    if not db_url:
        print(json.dumps({"status": "BLOCKED_CONFIGURATION", "diagnostic_code": "DATABASE_URL_MISSING"}))
        return 2

    import psycopg

    conn = psycopg.connect(db_url)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT count(*) FROM recommendations")
            recommendation_sample = int(cur.fetchone()[0])
            cur.execute("SELECT count(*) FROM recommendation_performance WHERE outcome_verdict <> 'OPEN'")
            independent_sample = int(cur.fetchone()[0])
            state = classify_learning_cycle(recommendation_sample, independent_sample)

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
                    AND notes LIKE 'Autonomous Learning Lab cycle:%'
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
        conn.commit()
        print(
            json.dumps(
                {
                    "status": state.status,
                    "recommendation_sample_size": state.recommendation_sample_size,
                    "independent_sample_size": state.independent_sample_size,
                    "learning_run_id": None if inserted is None else inserted[0],
                    "methodology_changed": False,
                    "automatic_adoption_enabled": False,
                },
                sort_keys=True,
            )
        )
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())

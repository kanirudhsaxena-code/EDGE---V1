"""EDGE Stocks canonical timing/efficacy governance.

This module is intentionally outside the frozen EDGE scoring engine. It classifies
immutable recommendations for efficacy membership and finalizes one canonical
recommendation per ticker + target trading date + governed horizon.
"""
from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

IST=ZoneInfo("Asia/Kolkata")
NY=ZoneInfo("America/New_York")
ACTIVATION_TARGET_DATE=date(2026,9,22)
PREOPEN_START=time(8,40)
PREOPEN_REQUEST_CUTOFF=time(8,55)
HARD_BOUNDARY=time(9,0)

NSE_HOLIDAYS_2026={
    date(2026,1,15),date(2026,1,26),date(2026,2,19),date(2026,3,3),
    date(2026,3,19),date(2026,3,26),date(2026,3,31),date(2026,4,1),
    date(2026,4,3),date(2026,4,14),date(2026,5,1),date(2026,5,28),
    date(2026,6,26),date(2026,8,26),date(2026,9,14),date(2026,10,2),
    date(2026,10,20),date(2026,11,10),date(2026,11,24),date(2026,12,25),
}
NYSE_HOLIDAYS_2026={
    date(2026,1,1),date(2026,1,19),date(2026,2,16),date(2026,4,3),
    date(2026,5,25),date(2026,6,19),date(2026,7,3),date(2026,9,7),
    date(2026,11,26),date(2026,12,25),
}
NYSE_EARLY_CLOSES_2026={date(2026,11,27),date(2026,12,24)}


def is_nse_day(day:date)->bool:
    return day.weekday()<5 and day not in NSE_HOLIDAYS_2026


def next_nse_day(day:date)->date:
    cursor=day
    for _ in range(370):
        cursor+=timedelta(days=1)
        if is_nse_day(cursor):
            return cursor
    raise ValueError("next NSE trading day not found")


def _is_nyse_day(day:date)->bool:
    return day.weekday()<5 and day not in NYSE_HOLIDAYS_2026


def last_nyse_close_before(target_open_ist:datetime)->datetime:
    candidate=target_open_ist.astimezone(NY).date()
    for _ in range(10):
        if _is_nyse_day(candidate):
            close_at=time(13,0) if candidate in NYSE_EARLY_CLOSES_2026 else time(16,0)
            close_ny=datetime.combine(candidate,close_at,tzinfo=NY)
            if close_ny < target_open_ist.astimezone(NY):
                return close_ny.astimezone(IST)
        candidate-=timedelta(days=1)
    raise ValueError("NYSE close could not be resolved")


def classify_stock_run(run_at:datetime)->dict:
    if run_at.tzinfo is None:
        raise ValueError("run_at must be timezone-aware")
    local=run_at.astimezone(IST)
    clock=local.time().replace(tzinfo=None)
    day=local.date()
    target=day if is_nse_day(day) and clock < time(15,30) else next_nse_day(day)
    key_date=target
    target_open=datetime.combine(target,HARD_BOUNDARY,tzinfo=IST)

    if target < ACTIVATION_TARGET_DATE:
        candidate_type="LEGACY_CANDIDATE"
    else:
        preopen_start=datetime.combine(target,PREOPEN_START,tzinfo=IST)
        request_cutoff=datetime.combine(target,PREOPEN_REQUEST_CUTOFF,tzinfo=IST)
        overnight_start=last_nyse_close_before(target_open)
        if preopen_start <= local <= request_cutoff:
            candidate_type="PREOPEN_CANONICAL"
        elif overnight_start <= local < preopen_start:
            candidate_type="OVERNIGHT_FALLBACK_CANONICAL"
        else:
            candidate_type="DIAGNOSTIC_SNAPSHOT"

    return {
        "target_trading_date":key_date,
        "candidate_type":candidate_type,
        "ordinary_cutoff_at":datetime.combine(target,PREOPEN_REQUEST_CUTOFF,tzinfo=IST),
        "hard_boundary_at":target_open,
    }


def canonical_key(ticker:str,target:date,horizon:str)->str:
    return f"{ticker.strip().upper()}|{target.isoformat()}|{horizon.strip().upper()}"


def register_recommendation_governance_values(
    conn,*,recommendation_id:str,ticker:str,run_at:datetime,completed_at:datetime,
    horizon:str,research_fresh_at:datetime|None=None,requested_at:datetime|None=None,
    canonical_attempt_slot:str|None=None,
)->dict:
    requested_at=requested_at or run_at
    classification=classify_stock_run(requested_at)
    candidate_type=classification["candidate_type"]
    if completed_at and completed_at.astimezone(IST) >= classification["hard_boundary_at"]:
        candidate_type="DIAGNOSTIC_SNAPSHOT"
    fallback_reason=(f"canonical_attempt_slot={canonical_attempt_slot}" if canonical_attempt_slot else None)
    if candidate_type in {"PREOPEN_CANONICAL","OVERNIGHT_FALLBACK_CANONICAL"}:
        if research_fresh_at is None or (requested_at-research_fresh_at).total_seconds() > 90*60:
            candidate_type="DIAGNOSTIC_SNAPSHOT"
            fallback_reason="Canonical eligibility blocked: governed stock research was not refreshed within 90 minutes of issuance."
    key=canonical_key(ticker,classification["target_trading_date"],horizon)
    cur=conn.cursor()
    cur.execute(
        """
        INSERT INTO edge_recommendation_governance(
          recommendation_id,canonical_key,ticker,target_trading_date,forecast_horizon,
          candidate_type,requested_at,completed_at,ordinary_cutoff_at,hard_boundary_at,
          research_fresh_at,fallback_reason
        ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (recommendation_id) DO NOTHING
        """,
        (
            recommendation_id,key,str(ticker).upper(),classification["target_trading_date"],
            horizon,candidate_type,requested_at,completed_at or run_at,
            classification["ordinary_cutoff_at"],classification["hard_boundary_at"],
            research_fresh_at,
            (
                ((fallback_reason + "; ") if fallback_reason else "")
                + ("Overnight fallback requires no newer material governed research before selection."
                   if candidate_type=="OVERNIGHT_FALLBACK_CANONICAL" else "")
            ) or None,
        ),
    )
    return {**classification,"candidate_type":candidate_type,"canonical_key":key}


def register_recommendation_governance(
    conn,recommendation_id:str,*,requested_at:datetime|None=None,
    canonical_attempt_slot:str|None=None,
)->dict:
    """Compatibility loader for callers that only hold recommendation_id."""
    cur=conn.cursor()
    cur.execute(
        """
        SELECT r.ticker,r.run_timestamp,r.created_at,r.forecast_horizon,
               erb.research_fresh_at
          FROM recommendations r
          LEFT JOIN recommendation_research_bundle rrb USING(recommendation_id)
          LEFT JOIN edge_research_bundles erb USING(bundle_id)
         WHERE r.recommendation_id=%s
         LIMIT 1
        """,
        (recommendation_id,),
    )
    row=cur.fetchone()
    if not row:
        raise ValueError("recommendation not found")
    ticker,run_at,completed_at,horizon,research_fresh_at=row
    return register_recommendation_governance_values(
        conn,recommendation_id=recommendation_id,ticker=ticker,run_at=run_at,
        completed_at=completed_at or run_at,horizon=horizon,
        research_fresh_at=research_fresh_at,requested_at=requested_at,
        canonical_attempt_slot=canonical_attempt_slot,
    )

def _fallback_research_still_current(cur,ticker:str,recommendation_id:str,run_at:datetime,cutoff:datetime)->bool:
    cur.execute(
        """
        SELECT erb.research_fresh_at
          FROM recommendation_research_bundle rrb
          JOIN edge_research_bundles erb USING(bundle_id)
         WHERE rrb.recommendation_id=%s
         LIMIT 1
        """,
        (recommendation_id,),
    )
    row=cur.fetchone()
    if not row or row[0] is None:
        return False
    linked_fresh=row[0]
    cur.execute(
        """
        SELECT 1
          FROM edge_research_bundles
         WHERE ticker=%s
           AND status='READY'
           AND research_fresh_at > %s
           AND research_fresh_at <= %s
         LIMIT 1
        """,
        (ticker,linked_fresh,cutoff),
    )
    return cur.fetchone() is None


def finalize_stock_canonicals(conn,now_ist:datetime|None=None)->int:
    now_ist=(now_ist or datetime.now(IST)).astimezone(IST)
    if now_ist.tzinfo is None:
        raise ValueError("now_ist must be timezone-aware")
    today=now_ist.date()
    if not is_nse_day(today) or now_ist.time().replace(tzinfo=None) < HARD_BOUNDARY:
        return 0

    with conn.cursor() as cur:
        cur.execute(
            """
            SELECT DISTINCT g.canonical_key,g.ticker,g.target_trading_date,g.forecast_horizon
              FROM edge_recommendation_governance g
             WHERE g.target_trading_date=%s
               AND NOT EXISTS (
                 SELECT 1 FROM edge_canonical_selections s WHERE s.canonical_key=g.canonical_key
               )
            """,
            (today,),
        )
        keys=cur.fetchall()

        # Active governed stock lineages also require an explicit missed state if
        # no recommendation was generated for today's target.
        cur.execute(
            """
            SELECT DISTINCT r.ticker,r.forecast_horizon
              FROM recommendations r
              JOIN recommendation_lifecycle l USING(recommendation_id)
             WHERE l.status='OPEN'
            """
        )
        active=cur.fetchall()

    existing_keys={row[0] for row in keys}
    for ticker,horizon in active:
        key=canonical_key(ticker,today,horizon)
        if key not in existing_keys:
            keys.append((key,str(ticker).upper(),today,horizon))
            existing_keys.add(key)

    finalized=0
    for key,ticker,target,horizon in keys:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT g.recommendation_id,g.candidate_type,g.requested_at,g.completed_at,
                       g.ordinary_cutoff_at,g.hard_boundary_at,r.run_timestamp
                  FROM edge_recommendation_governance g
                  JOIN recommendations r USING(recommendation_id)
                 WHERE g.canonical_key=%s
                   AND g.candidate_type IN ('PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL')
                   AND g.requested_at <= g.ordinary_cutoff_at
                   AND g.completed_at < g.hard_boundary_at
                 ORDER BY
                   CASE g.candidate_type WHEN 'PREOPEN_CANONICAL' THEN 2 ELSE 1 END DESC,
                   g.requested_at DESC
                """,
                (key,),
            )
            candidates=cur.fetchall()
            selected=None
            for candidate in candidates:
                rec_id,ctype,requested,completed,cutoff,boundary,run_ts=candidate
                if ctype=="OVERNIGHT_FALLBACK_CANONICAL" and not _fallback_research_still_current(
                    cur,ticker,rec_id,run_ts,cutoff
                ):
                    continue
                selected=candidate
                break

            if selected:
                rec_id,ctype,_,_,_,_,_=selected
                cur.execute(
                    """
                    INSERT INTO edge_canonical_selections(
                      canonical_key,ticker,target_trading_date,forecast_horizon,
                      selection_status,canonical_type,selected_recommendation_id,selected_at,selection_reason
                    ) VALUES (%s,%s,%s,%s,'SELECTED',%s,%s,%s,%s)
                    ON CONFLICT (canonical_key) DO NOTHING
                    """,
                    (
                        key,ticker,target,horizon,ctype,rec_id,now_ist,
                        f"{ctype}: latest valid complete governed recommendation selected under frozen timing policy.",
                    ),
                )
                if cur.rowcount:
                    cur.execute(
                        "UPDATE recommendation_lifecycle SET include_in_master_metrics=false,updated_at=now() WHERE recommendation_id IN (SELECT recommendation_id FROM edge_recommendation_governance WHERE canonical_key=%s)",
                        (key,),
                    )
                    cur.execute(
                        "UPDATE recommendation_lifecycle SET include_in_master_metrics=true,updated_at=now() WHERE recommendation_id=%s",
                        (rec_id,),
                    )
                    finalized+=1
            else:
                cur.execute(
                    """
                    INSERT INTO edge_canonical_selections(
                      canonical_key,ticker,target_trading_date,forecast_horizon,
                      selection_status,canonical_type,selected_recommendation_id,selected_at,selection_reason
                    ) VALUES (%s,%s,%s,%s,'CANONICAL_MISSED','CANONICAL_MISSED',NULL,%s,%s)
                    ON CONFLICT (canonical_key) DO NOTHING
                    """,
                    (
                        key,ticker,target,horizon,now_ist,
                        "No complete pre-open canonical or research-current overnight fallback existed by 09:00 IST.",
                    ),
                )
                finalized+=max(cur.rowcount,0)
        conn.commit()
    return finalized

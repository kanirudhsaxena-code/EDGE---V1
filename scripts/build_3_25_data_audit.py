#!/usr/bin/env python3
import json, os
from collections import Counter, defaultdict
from datetime import datetime, timezone
import psycopg2

now=datetime.now(timezone.utc)
conn=psycopg2.connect(os.environ["DATABASE_URL"])
conn.set_session(readonly=True, autocommit=False)
try:
    with conn.cursor() as cur:
        cur.execute("select current_database(), current_schema()")
        database_name,schema_name=cur.fetchone()

        cur.execute("""
          select r.recommendation_id,r.ticker,r.run_timestamp,er.command_type,
                 g.canonical_key,g.candidate_type,g.trigger_type,g.benchmark_role,
                 s.selection_status,s.selected_recommendation_id,
                 l.tracking_policy,l.include_in_master_metrics,l.status,l.closure_reason,
                 p.outcome_verdict,p.direction_hit,p.target_hit,p.stop_hit,
                 coalesce(fp.path_count,0) as path_count,
                 coalesce(fp.path_labels,'') as path_labels
            from recommendations r
            join edge_runs er on er.run_id=r.run_id
            left join edge_recommendation_governance g using(recommendation_id)
            left join edge_canonical_selections s
              on s.canonical_key=g.canonical_key
            left join recommendation_lifecycle l using(recommendation_id)
            left join recommendation_performance p using(recommendation_id)
            left join (
              select recommendation_id,count(*) as path_count,
                     string_agg(horizon_label,',' order by horizon_index) as path_labels
                from edge_stock_forecast_path_rows
               group by recommendation_id
            ) fp using(recommendation_id)
           order by r.run_timestamp,r.recommendation_id
        """)
        rows=cur.fetchall()

        cur.execute("""
          select
            (select count(*) from recommendations),
            (select count(*) from recommendation_lifecycle),
            (select count(*) from recommendation_performance),
            (select count(*) from edge_recommendation_governance),
            (select count(*) from edge_canonical_selections),
            (select count(*) from edge_stock_forecast_paths),
            (select count(*) from edge_stock_forecast_path_rows),
            (select count(*) from outcome_checkpoints),
            (select count(*) from efficacy_results)
        """)
        counts=cur.fetchone()
finally:
    conn.rollback()
    conn.close()

records=[]
classes=Counter()
by_ticker=defaultdict(Counter)
for row in rows:
    (recommendation_id,ticker,run_timestamp,command_type,canonical_key,candidate_type,trigger_type,benchmark_role,
     selection_status,selected_recommendation_id,tracking_policy,include_master,lifecycle_status,closure_reason,
     outcome_verdict,direction_hit,target_hit,stop_hit,path_count,path_labels)=row

    selected=(selection_status=="SELECTED" and selected_recommendation_id==recommendation_id)
    complete_path=(int(path_count or 0)==5 and path_labels=="D,D+1,D+2,D+3,D+4")

    if command_type=="TEST":
        classification="TEST_UAT"
    elif candidate_type=="DIAGNOSTIC_SNAPSHOT":
        classification="DIAGNOSTIC"
    elif selected:
        if not complete_path:
            classification="AUDIT_ONLY_INCOMPLETE"
        elif lifecycle_status=="OPEN":
            classification="PROVISIONAL_OPEN_CALL"
        elif lifecycle_status=="CLOSED" and outcome_verdict in ("WIN","LOSS","FLAT"):
            classification="OFFICIAL_SCORABLE"
        elif lifecycle_status=="CLOSED" and outcome_verdict=="NOT_SCORABLE":
            classification="AUDIT_ONLY_INCOMPLETE"
        else:
            classification="REPAIR_PENDING"
    elif candidate_type=="USER_CANONICAL_SNAPSHOT":
        classification="ALL_RUN_DIAGNOSTIC"
    elif candidate_type in ("LEGACY_CANDIDATE","PREOPEN_CANONICAL","OVERNIGHT_FALLBACK_CANONICAL","EXCEPTION_CANONICAL"):
        classification="NONCANONICAL"
    elif candidate_type is None:
        classification="AUDIT_ONLY_INCOMPLETE"
    else:
        classification="DIAGNOSTIC"

    classes[classification]+=1
    by_ticker[str(ticker).upper()][classification]+=1
    records.append({
        "recommendation_id":recommendation_id,
        "ticker":str(ticker).upper(),
        "run_timestamp":run_timestamp.isoformat() if run_timestamp else None,
        "command_type":command_type,
        "canonical_key":canonical_key,
        "candidate_type":candidate_type,
        "trigger_type":trigger_type,
        "benchmark_role":benchmark_role,
        "selection_status":selection_status,
        "selected_recommendation_id":selected_recommendation_id,
        "tracking_policy":tracking_policy,
        "include_in_master_metrics":include_master,
        "lifecycle_status":lifecycle_status,
        "closure_reason":closure_reason,
        "outcome_verdict":outcome_verdict,
        "direction_hit":direction_hit,
        "target_hit":target_hit,
        "stop_hit":stop_hit,
        "path_count":int(path_count or 0),
        "path_labels":path_labels,
        "classification":classification,
    })

resolved=sum(1 for r in records if r["classification"]=="OFFICIAL_SCORABLE")
selected_matured=sum(1 for r in records if r["selection_status"]=="SELECTED" and r["lifecycle_status"]=="CLOSED")
report={
    "version":"MDOS_BUILD_3_25_EDGE_STOCK_DATA_AUDIT_V1",
    "generated_at":now.isoformat().replace("+00:00","Z"),
    "read_only":True,
    "database":{"name":database_name,"schema":schema_name},
    "table_counts":{
        "recommendations":int(counts[0] or 0),
        "recommendation_lifecycle":int(counts[1] or 0),
        "recommendation_performance":int(counts[2] or 0),
        "governance":int(counts[3] or 0),
        "canonical_selections":int(counts[4] or 0),
        "forecast_paths":int(counts[5] or 0),
        "forecast_path_rows":int(counts[6] or 0),
        "outcome_checkpoints":int(counts[7] or 0),
        "efficacy_results":int(counts[8] or 0),
    },
    "summary":{
        "classification_counts":dict(classes),
        "by_ticker":{k:dict(v) for k,v in sorted(by_ticker.items())},
        "selected_matured":selected_matured,
        "official_scorable":resolved,
        "selected_matured_scoreable_pct":round(100.0*resolved/selected_matured,2) if selected_matured else None,
    },
    "records":records,
}
print(json.dumps(report,indent=2,sort_keys=True))

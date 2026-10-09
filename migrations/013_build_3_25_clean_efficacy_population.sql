-- MDOS Build 3.25 — Clean EDGE Stocks efficacy populations.
-- Additive only. Historical recommendations, canonical selections and forecast paths are not mutated.

create or replace view public.v_build_3_25_edge_stock_population as
with path as (
  select r.recommendation_id,
         count(p.horizon_index) as path_count,
         string_agg(p.horizon_label,',' order by p.horizon_index) as path_labels
    from public.recommendations r
    left join public.edge_stock_forecast_path_rows p using(recommendation_id)
   group by r.recommendation_id
),
base as (
  select r.recommendation_id,r.ticker,r.run_timestamp,er.command_type,
         g.canonical_key,g.candidate_type,g.trigger_type,g.benchmark_role,
         l.tracking_policy,l.include_in_master_metrics,l.status as lifecycle_status,l.closure_reason,
         p.outcome_verdict,p.direction_hit,p.target_hit,p.stop_hit,p.model_return_pct,p.mfe_pct,p.mae_pct,
         coalesce(path.path_count,0) as path_count,
         coalesce(path.path_labels,'') as path_labels,
         exists(
           select 1 from public.edge_canonical_selections s
            where s.selection_status='SELECTED'
              and s.selected_recommendation_id=r.recommendation_id
         ) as selected_benchmark
    from public.recommendations r
    join public.edge_runs er on er.run_id=r.run_id
    left join public.edge_recommendation_governance g using(recommendation_id)
    left join public.recommendation_lifecycle l using(recommendation_id)
    left join public.recommendation_performance p using(recommendation_id)
    left join path using(recommendation_id)
)
select *,
       case
         when command_type='TEST' then 'TEST_UAT'
         when selected_benchmark and (path_count<>5 or path_labels<>'D,D+1,D+2,D+3,D+4') then 'AUDIT_ONLY_INCOMPLETE'
         when selected_benchmark and lifecycle_status='OPEN' then 'PROVISIONAL_OPEN_CALL'
         when selected_benchmark and lifecycle_status='CLOSED' and outcome_verdict in ('WIN','LOSS','FLAT') then 'OFFICIAL_SCORABLE'
         when selected_benchmark and lifecycle_status='CLOSED' and outcome_verdict='NOT_SCORABLE' then 'AUDIT_ONLY_INCOMPLETE'
         when selected_benchmark then 'REPAIR_PENDING'
         when candidate_type='DIAGNOSTIC_SNAPSHOT' then 'DIAGNOSTIC'
         when candidate_type='USER_CANONICAL_SNAPSHOT' then 'ALL_RUN_DIAGNOSTIC'
         when candidate_type in ('LEGACY_CANDIDATE','PREOPEN_CANONICAL','OVERNIGHT_FALLBACK_CANONICAL','EXCEPTION_CANONICAL') then 'NONCANONICAL'
         when candidate_type is null then 'AUDIT_ONLY_INCOMPLETE'
         else 'DIAGNOSTIC'
       end as population_state,
       case
         when selected_benchmark and (path_count<>5 or path_labels<>'D,D+1,D+2,D+3,D+4')
           then 'FROZEN_FIVE_SESSION_PATH_INCOMPLETE'
         when selected_benchmark and lifecycle_status='CLOSED' and outcome_verdict='NOT_SCORABLE'
           then 'RESOLVED_NOT_SCORABLE'
         when selected_benchmark and lifecycle_status not in ('OPEN','CLOSED')
           then 'LIFECYCLE_STATE_INCOMPLETE'
         when candidate_type is null then 'GOVERNANCE_CLASSIFICATION_MISSING'
         else null
       end as population_reason
  from base;

create or replace view public.v_official_edge_stock_efficacy_population as
select *
  from public.v_build_3_25_edge_stock_population
 where population_state='OFFICIAL_SCORABLE';

create or replace view public.v_edge_stock_efficacy_audit_exclusions as
select *
  from public.v_build_3_25_edge_stock_population
 where population_state in ('AUDIT_ONLY_INCOMPLETE','REPAIR_PENDING','TEST_UAT','DIAGNOSTIC','NONCANONICAL');

create or replace view public.v_edge_stock_all_run_diagnostics_clean as
select *
  from public.v_build_3_25_edge_stock_population
 where population_state in ('ALL_RUN_DIAGNOSTIC','OFFICIAL_SCORABLE','PROVISIONAL_OPEN_CALL');

create or replace view public.v_build_3_25_edge_stock_population_summary as
select
  count(*) as total_recommendations,
  count(*) filter (where selected_benchmark) as selected_benchmark_count,
  count(*) filter (where population_state='OFFICIAL_SCORABLE') as official_scorable_count,
  count(*) filter (where population_state='PROVISIONAL_OPEN_CALL') as provisional_open_count,
  count(*) filter (where population_state='REPAIR_PENDING') as repair_pending_count,
  count(*) filter (where population_state='AUDIT_ONLY_INCOMPLETE') as audit_incomplete_count,
  count(*) filter (where population_state='ALL_RUN_DIAGNOSTIC') as all_run_diagnostic_count,
  count(*) filter (where population_state in ('TEST_UAT','DIAGNOSTIC','NONCANONICAL')) as nonofficial_other_count,
  round(
    100.0*count(*) filter (where population_state='OFFICIAL_SCORABLE')
    / nullif(count(*) filter (where population_state in ('OFFICIAL_SCORABLE','REPAIR_PENDING')),0),2
  ) as official_resolved_coverage_pct,
  count(*) filter (where selected_benchmark
    and path_count=5 and path_labels='D,D+1,D+2,D+3,D+4') as selected_complete_path_count,
  count(*) filter (where selected_benchmark and population_state='AUDIT_ONLY_INCOMPLETE')
    as selected_audit_exclusion_count,
  round(
    100.0*count(*) filter (where selected_benchmark
      and path_count=5 and path_labels='D,D+1,D+2,D+3,D+4')
    / nullif(count(*) filter (where selected_benchmark),0),2
  ) as selected_path_completeness_pct
from public.v_build_3_25_edge_stock_population;

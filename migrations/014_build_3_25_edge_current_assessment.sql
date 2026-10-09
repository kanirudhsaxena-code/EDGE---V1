-- Build 3.25: additive current assessment derived from governed efficacy populations.
-- Historical recommendations and their outcomes are unchanged.
-- Do not misrepresent model returns as net % return on invested capital.
create or replace view public.v_build_3_25_edge_current_assessment as
with eligible as (
    select *
      from public.v_build_3_25_edge_stock_population
     where population_state='OFFICIAL_SCORABLE'
),
scored as (
    select count(*) as scored_recommendations,
           count(*) filter (where outcome_verdict='WIN') as wins,
           count(*) filter (where outcome_verdict='LOSS') as losses,
           count(*) filter (where outcome_verdict='FLAT') as flats,
           count(*) filter (where direction_hit is true) as direction_hits,
           count(*) filter (where direction_hit is not null) as direction_evaluated,
           count(*) filter (where target_hit is true) as target_hits,
           count(*) filter (where target_hit is not null) as target_evaluated,
           round(avg(mfe_pct)::numeric,2) as avg_mfe_pct,
           round(avg(mae_pct)::numeric,2) as avg_mae_pct
      from eligible
)
select 'MDOS_BUILD_3_25_EDGE_CLEAN_ASSESSMENT_V1'::text as assessment_version,
       summary.total_recommendations,
       summary.selected_benchmark_count,
       summary.selected_complete_path_count,
       summary.selected_audit_exclusion_count,
       summary.selected_path_completeness_pct,
       summary.provisional_open_count,
       summary.repair_pending_count,
       summary.all_run_diagnostic_count,
       s.scored_recommendations,
       s.wins,s.losses,s.flats,
       round(100.0*s.wins/nullif(s.scored_recommendations,0),2) as recommendation_hit_rate_pct,
       s.direction_hits,s.direction_evaluated,
       round(100.0*s.direction_hits/nullif(s.direction_evaluated,0),2) as direction_hit_rate_pct,
       s.target_hits,s.target_evaluated,
       round(100.0*s.target_hits/nullif(s.target_evaluated,0),2) as target_hit_rate_pct,
       s.avg_mfe_pct,s.avg_mae_pct,
       null::numeric as net_return_on_invested_capital_pct,
       'NOT_COMPUTABLE_FROM_MODEL_ONLY_HISTORY'::text as net_return_status,
       case
         when summary.selected_benchmark_count=0 then 'NO_SELECTED_BENCHMARKS'
         when summary.selected_complete_path_count=0 then 'BLOCKED_NO_COMPLETE_CANONICAL_PATH'
         when summary.repair_pending_count>0 then 'BLOCKED_EVALUATION_PENDING'
         when s.scored_recommendations=0 then 'PENDING_QUALIFIED_OUTCOMES'
         else 'REPORTABLE'
       end::text as reporting_status
  from public.v_build_3_25_edge_stock_population_summary summary
 cross join scored;

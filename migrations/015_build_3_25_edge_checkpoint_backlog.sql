-- Build 3.25: due-checkpoint audit, additive and read-only.
-- Keeps selected canonical overdue observations distinct from nonofficial/all-run backlog.
create or replace view public.v_build_3_25_edge_checkpoint_backlog as
select oc.recommendation_id,
       p.ticker,
       oc.checkpoint_type,
       oc.due_date,
       oc.status as checkpoint_status,
       p.selected_benchmark,
       p.population_state as recommendation_population,
       (oc.due_date < (now() at time zone 'Asia/Kolkata')::date
         or (oc.due_date=(now() at time zone 'Asia/Kolkata')::date
             and (now() at time zone 'Asia/Kolkata')::time>=time '15:40')) as matured,
       case
         when oc.status='CAPTURED' then 'CAPTURED_AUDIT_OBSERVATION'
         when oc.status='DUE' and
           (oc.due_date < (now() at time zone 'Asia/Kolkata')::date
            or (oc.due_date=(now() at time zone 'Asia/Kolkata')::date
                and (now() at time zone 'Asia/Kolkata')::time>=time '15:40'))
           and p.selected_benchmark then 'SELECTED_OVERDUE_UNRECONCILED'
         when oc.status='DUE' and
           (oc.due_date < (now() at time zone 'Asia/Kolkata')::date
            or (oc.due_date=(now() at time zone 'Asia/Kolkata')::date
                and (now() at time zone 'Asia/Kolkata')::time>=time '15:40'))
           then 'NONCANONICAL_OVERDUE_DIAGNOSTIC'
         when oc.status='DUE' then 'NOT_YET_DUE'
         else 'OTHER_REVIEW'
       end as backlog_state,
       p.tracking_policy
from public.outcome_checkpoints oc
join public.v_build_3_25_edge_stock_population p using(recommendation_id)
where oc.checkpoint_type in ('D+1','D+2','D+3','D+4','D+5');

create or replace view public.v_build_3_25_edge_checkpoint_backlog_summary as
select count(*) as five_session_checkpoints,
       count(*) filter(where selected_benchmark) as selected_five_session_checkpoints,
       count(*) filter(where selected_benchmark and checkpoint_status='CAPTURED') as selected_captured_checkpoints,
       count(*) filter(where backlog_state='SELECTED_OVERDUE_UNRECONCILED') as selected_overdue_checkpoints,
       count(distinct recommendation_id) filter(where backlog_state='SELECTED_OVERDUE_UNRECONCILED')
         as selected_recommendations_with_overdue_checkpoints,
       count(*) filter(where backlog_state='NONCANONICAL_OVERDUE_DIAGNOSTIC')
         as noncanonical_overdue_checkpoints,
       count(*) filter(where backlog_state='NOT_YET_DUE') as future_checkpoints,
       count(*) filter(where backlog_state='OTHER_REVIEW') as other_review_checkpoints,
       (select count(*) from public.v_build_3_25_edge_stock_population
         where selected_benchmark and tracking_policy='LEGACY_PRE_V2')
         as selected_legacy_nonfive_horizon_recommendations,
       (select count(*) from public.v_build_3_25_edge_stock_population
         where selected_benchmark and tracking_policy='EDGE_D5_V2')
         as selected_v2_five_horizon_recommendations
from public.v_build_3_25_edge_checkpoint_backlog;

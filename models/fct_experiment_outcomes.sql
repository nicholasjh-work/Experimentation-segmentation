{{
  config(
    materialized='table',
    schema='ANALYTICS'
  )
}}

-- fct_experiment_outcomes
--
-- Summarises experiment results by variant.  For each experiment and
-- variant combination it reports the number of participants, number of
-- converters (members who complete a success event) and average health
-- metrics during the experiment window.  Conversion rate is computed as
-- converters / participants.

with assignments as (
    select
        ea.member_id,
        ea.experiment_id,
        ea.variant,
        exp.experiment_name,
        exp.start_date,
        exp.end_date
    from {{ source('raw', 'experiment_assignments') }} ea
    join {{ source('raw', 'experiments') }} exp
      on exp.experiment_id = ea.experiment_id
),
event_success as (
    -- identify members who triggered a success event during the experiment
    select
        fe.member_id,
        fe.event_date,
        fe.event_name,
        fe.feature
    from {{ source('raw', 'feature_events') }} fe
    where fe.event_name in ('onboarding_completed', 'health_goal_set')
),
daily_filtered as (
    -- restrict daily metrics to the experiment window
    select
        dm.member_id,
        dm.metric_date,
        dm.hrv,
        dm.resting_heart_rate,
        dm.sleep_hours,
        dm.sleep_quality,
        dm.strain,
        dm.recovery
    from {{ source('raw', 'daily_metrics') }} dm
),
aggregated as (
    select
        a.experiment_id,
        a.variant,
        count(distinct a.member_id) as participants,
        count(distinct case when es.member_id is not null and es.event_date between a.start_date and a.end_date then a.member_id end) as converters,
        avg(case when dm.metric_date between a.start_date and a.end_date then dm.hrv end) as avg_hrv,
        avg(case when dm.metric_date between a.start_date and a.end_date then dm.resting_heart_rate end) as avg_resting_hr,
        avg(case when dm.metric_date between a.start_date and a.end_date then dm.sleep_hours end) as avg_sleep_hours,
        avg(case when dm.metric_date between a.start_date and a.end_date then dm.sleep_quality end) as avg_sleep_quality,
        avg(case when dm.metric_date between a.start_date and a.end_date then dm.strain end) as avg_strain,
        avg(case when dm.metric_date between a.start_date and a.end_date then dm.recovery end) as avg_recovery
    from assignments a
    left join event_success es on es.member_id = a.member_id
    left join daily_filtered dm on dm.member_id = a.member_id
    group by 1,2
)
select
    experiment_id,
    variant,
    participants,
    converters,
    converters / nullif(participants, 0) as conversion_rate,
    avg_hrv,
    avg_resting_hr,
    avg_sleep_hours,
    avg_sleep_quality,
    avg_strain,
    avg_recovery
from aggregated;
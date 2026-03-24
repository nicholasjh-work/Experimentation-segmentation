{{
  config(
    materialized='table',
    schema='ANALYTICS'
  )
}}

-- fct_health_kpis
--
-- Aggregates daily health metrics by member and week.  These weekly
-- aggregates are used for behavioural segmentation and trend reporting.

with weekly as (
    select
        member_id,
        date_trunc('week', metric_date) as week_start,
        avg(hrv) as avg_hrv,
        avg(resting_heart_rate) as avg_resting_hr,
        avg(sleep_hours) as avg_sleep_hours,
        avg(sleep_quality) as avg_sleep_quality,
        avg(strain) as avg_strain,
        avg(recovery) as avg_recovery,
        avg(calories) as avg_calories
    from {{ source('raw', 'daily_metrics') }}
    group by 1,2
)
select * from weekly;
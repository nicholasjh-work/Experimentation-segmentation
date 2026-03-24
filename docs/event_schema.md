# Event Schema – Experimentation & Segmentation

Although this repository does not generate new events, it depends on the event schema defined in the infrastructure project.  Here we recap the relevant events and how they feed into experimentation and segmentation.

| Event Name | Purpose | Consumed by |
|-----------|---------|-------------|
| `experiment_assignment` | Records which experiment and variant a member is assigned to.  Contains `member_id`, `experiment_id`, `variant` and `assignment_date`. | `fct_experiment_outcomes` joins assignments to outcome metrics. |
| `feature_event` | Captures user interactions such as `onboarding_completed` or `health_goal_set`.  Fields include `member_id`, `event_date`, `event_name` and `feature`. | Used to define success events (conversions) in experiments. |
| `daily_metrics` | Provides physiological and behavioural metrics at a daily cadence (HRV, heart rate, sleep, strain, recovery, calories). | Aggregated into weekly KPIs in `fct_health_kpis` and used for segmentation. |

When sending events to Amplitude or other tools, respect the API’s batch size and rate limits to ensure reliable ingestion.
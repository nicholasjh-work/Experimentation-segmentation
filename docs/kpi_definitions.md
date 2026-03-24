# KPI Definitions – Experimentation & Segmentation

This document details the metrics used in the experimentation and segmentation repository.

## Experiment metrics

- **Participants** – the number of unique members assigned to a given variant of an experiment.
- **Converters** – the number of participants who complete a predefined success event during the experiment window (e.g. completing onboarding or setting a health goal).  Counting conversions allows calculation of the conversion rate.
- **Conversion rate** – converters divided by participants.  This fraction is compared between variants using statistical tests to assess significance.
- **Effect size (Cohen’s d)** – a standardised measure of the difference between the treatment and control group means.  Values of approximately 0.2, 0.5 and 0.8 indicate small, medium and large effects, respectively.  Effect sizes complement p‑values by quantifying practical significance.
- **Confidence interval** – a range of values that is likely to contain the true difference in means with a specified probability (95 % in this project).  If the interval excludes zero, the difference is statistically significant.

## Health KPIs

- **Average HRV** – mean heart rate variability across a week, reflecting cardiovascular variability.
- **Average resting heart rate** – mean resting heart rate across a week.  Lower values generally correspond to better fitness.
- **Average sleep hours / quality** – average duration and quality of sleep.  These metrics indicate recovery and readiness.
- **Average strain & recovery** – mean values of exertion and recovery metrics that help classify users into power and casual segments.

## Segmentation metrics

The K‑means clustering algorithm partitions members based on the health KPIs into groups that minimise within‑cluster variance.  In this project two clusters are used: one representing power users (higher strain and recovery) and the other representing casual users (lower strain and recovery).  Cluster assignments can be appended to fact tables for further analysis.

## Data quality checks

The dbt models enforce uniqueness of the `fct_experiment_outcomes` table on the combination of experiment_id and variant and of the `fct_health_kpis` table on the combination of member_id and week_start.  Not‑null tests ensure that key fields are populated.
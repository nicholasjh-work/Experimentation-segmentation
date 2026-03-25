"""Experimentation & Segmentation demo using PostgreSQL.

Usage:
    python demo.py
    python demo.py --db-url postgresql://user:pass@host/dbname
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mticker
import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler
from sqlalchemy import create_engine, text

sys.path.insert(0, str(Path(__file__).parent))
from analysis.experiment_analyzer import ExperimentAnalyzer

DEFAULT_DB_URL = "postgresql://demo_user:demo_pass@localhost:5432/analytics_demo"


def build_experiment_outcomes(engine):
    sql = """
    WITH assignments AS (
        SELECT ea.member_id, ea.experiment_id, ea.variant, exp.experiment_name, exp.start_date, exp.end_date
        FROM raw.experiment_assignments ea JOIN raw.experiments exp ON exp.experiment_id = ea.experiment_id
    ),
    event_success AS (
        SELECT fe.member_id, fe.event_date, fe.event_name FROM raw.feature_events fe
        WHERE fe.event_name IN ('onboarding_completed', 'health_goal_set')
    ),
    aggregated AS (
        SELECT a.experiment_id, a.experiment_name, a.variant,
            COUNT(DISTINCT a.member_id) AS participants,
            COUNT(DISTINCT CASE WHEN es.member_id IS NOT NULL AND es.event_date BETWEEN a.start_date AND a.end_date
                THEN a.member_id END) AS converters,
            AVG(CASE WHEN dm.metric_date BETWEEN a.start_date AND a.end_date THEN dm.hrv END) AS avg_hrv,
            AVG(CASE WHEN dm.metric_date BETWEEN a.start_date AND a.end_date THEN dm.strain END) AS avg_strain,
            AVG(CASE WHEN dm.metric_date BETWEEN a.start_date AND a.end_date THEN dm.recovery END) AS avg_recovery
        FROM assignments a
        LEFT JOIN event_success es ON es.member_id = a.member_id
        LEFT JOIN raw.daily_metrics dm ON dm.member_id = a.member_id
        GROUP BY 1,2,3
    )
    SELECT *, converters * 1.0 / NULLIF(participants, 0) AS conversion_rate
    FROM aggregated ORDER BY experiment_id, variant
    """
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def build_health_kpis(engine):
    sql = """
    SELECT member_id, AVG(hrv) as avg_hrv, AVG(strain) as avg_strain,
           AVG(recovery) as avg_recovery, AVG(sleep_hours) as avg_sleep_hours,
           AVG(sleep_quality) as avg_sleep_quality
    FROM raw.daily_metrics GROUP BY member_id
    """
    with engine.connect() as conn:
        return pd.read_sql(text(sql), conn)


def run_ab_analysis(df, out_dir):
    analyzer = ExperimentAnalyzer(alpha=0.05)
    experiments = df["experiment_id"].unique()
    for exp_id in sorted(experiments):
        ed = df[df["experiment_id"] == exp_id]
        name = ed["experiment_name"].iloc[0]
        ctrl = ed[ed["variant"] == "control"].iloc[0]
        treat = ed[ed["variant"] == "treatment"].iloc[0]
        print(f"\n  Experiment {exp_id}: {name}")
        print(
            f"  {'':4s}{'Variant':12s} {'Participants':>12s} {'Converters':>10s} {'Conv Rate':>10s}"
        )
        for _, row in ed.iterrows():
            print(
                f"  {'':4s}{row['variant']:12s} {int(row['participants']):>12,} {int(row['converters']):>10,} {row['conversion_rate']:>10.3f}"
            )
        np.random.seed(int(exp_id))
        co = np.random.binomial(
            1, ctrl["conversion_rate"], int(ctrl["participants"])
        ).astype(float)
        tr = np.random.binomial(
            1, treat["conversion_rate"], int(treat["participants"])
        ).astype(float)
        result = analyzer.analyze(co, tr)
        print(
            f"\n  {'':4s}Decision:  {result.decision}  (p={result.p_value:.4f}, d={result.cohen_d:.4f})"
        )

    colors = {"control": "#3b82f6", "treatment": "#06d6a0"}
    fig, axes = plt.subplots(1, len(experiments), figsize=(7 * len(experiments), 6))
    if len(experiments) == 1:
        axes = [axes]
    for i, eid in enumerate(sorted(experiments)):
        ed = df[df["experiment_id"] == eid]
        ax = axes[i]
        bars = ax.bar(
            ed["variant"],
            ed["conversion_rate"],
            color=[colors.get(v, "#999") for v in ed["variant"]],
            alpha=0.8,
            width=0.5,
        )
        ax.set_title(f"Experiment {eid}: {ed['experiment_name'].iloc[0]}")
        ax.set_ylabel("Conversion Rate")
        ax.yaxis.set_major_formatter(mticker.PercentFormatter(1.0))
        ax.set_ylim(0, max(ed["conversion_rate"]) * 1.3)
        for bar, rate in zip(bars, ed["conversion_rate"]):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.003,
                f"{rate:.1%}",
                ha="center",
                fontsize=11,
            )
        ax.grid(True, alpha=0.3, axis="y")
    plt.tight_layout()
    plt.savefig(out_dir / "ab_test_results.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"\n  Saved {out_dir}/ab_test_results.png")


def run_segmentation(kdf, out_dir):
    features = [
        "avg_hrv",
        "avg_strain",
        "avg_recovery",
        "avg_sleep_hours",
        "avg_sleep_quality",
    ]
    X = kdf[features].dropna()
    X_scaled = StandardScaler().fit_transform(X)

    inertias = [
        KMeans(n_clusters=k, random_state=42, n_init=10).fit(X_scaled).inertia_
        for k in range(2, 8)
    ]
    km = KMeans(n_clusters=3, random_state=42, n_init=10)
    kdf = kdf.loc[X.index].copy()
    kdf["cluster"] = km.fit_predict(X_scaled)

    cm = kdf.groupby("cluster")["avg_strain"].mean()
    sr = cm.rank(ascending=False).astype(int)
    nm = {c: {1: "Power", 2: "Active", 3: "Casual"}[r] for c, r in sr.items()}
    kdf["segment"] = kdf["cluster"].map(nm)

    print(f"\n  Segment Profiles:")
    for seg in ["Power", "Active", "Casual"]:
        sub = kdf[kdf["segment"] == seg]
        print(
            f"    {seg:8s} (n={len(sub):,}):  HRV={sub['avg_hrv'].mean():.1f}  Strain={sub['avg_strain'].mean():.1f}  Recovery={sub['avg_recovery'].mean():.1f}  Sleep={sub['avg_sleep_hours'].mean():.1f}h"
        )

    # Elbow
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(list(range(2, 8)), inertias, "bo-", linewidth=2)
    ax.axvline(x=3, color="red", linestyle="--", alpha=0.5, label="k=3")
    ax.legend()
    ax.set_xlabel("k")
    ax.set_ylabel("Inertia")
    ax.set_title("Elbow Method")
    ax.grid(True, alpha=0.3)
    plt.savefig(out_dir / "elbow_plot.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {out_dir}/elbow_plot.png")

    # Scatter + Radar
    colors = {"Power": "#2ecc71", "Active": "#3498db", "Casual": "#e74c3c"}
    fig, axes = plt.subplots(1, 2, figsize=(16, 7))
    for seg in ["Power", "Active", "Casual"]:
        sub = kdf[kdf["segment"] == seg]
        axes[0].scatter(
            sub["avg_hrv"],
            sub["avg_strain"],
            alpha=0.3,
            label=f"{seg} (n={len(sub):,})",
            color=colors[seg],
            s=15,
        )
    axes[0].set_xlabel("Average HRV")
    axes[0].set_ylabel("Average Strain")
    axes[0].set_title("Member Segments: HRV vs Strain")
    axes[0].legend()
    axes[0].grid(True, alpha=0.3)

    seg_means = kdf.groupby("segment")[features].mean()
    seg_norm = (seg_means - seg_means.min()) / (
        seg_means.max() - seg_means.min() + 1e-8
    )
    angles = np.linspace(0, 2 * np.pi, len(features), endpoint=False).tolist() + [0]
    fl = ["HRV", "Strain", "Recovery", "Sleep Hrs", "Sleep Qual"]
    ax_r = fig.add_subplot(122, polar=True)
    axes[1].set_visible(False)
    for seg in ["Power", "Active", "Casual"]:
        vals = seg_norm.loc[seg].tolist() + [seg_norm.loc[seg].tolist()[0]]
        ax_r.plot(angles, vals, "o-", label=seg, color=colors[seg], linewidth=2)
        ax_r.fill(angles, vals, alpha=0.1, color=colors[seg])
    ax_r.set_xticks(angles[:-1])
    ax_r.set_xticklabels(fl, size=9)
    ax_r.set_title("Segment Profiles", y=1.08)
    ax_r.legend(loc="upper right", bbox_to_anchor=(1.35, 1.1))
    plt.tight_layout()
    plt.savefig(out_dir / "segmentation_results.png", dpi=150, bbox_inches="tight")
    plt.close()
    print(f"  Saved {out_dir}/segmentation_results.png")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--db-url", default=os.getenv("DATABASE_URL", DEFAULT_DB_URL))
    args = parser.parse_args()
    engine = create_engine(args.db_url)
    out_dir = Path(__file__).parent / "screenshots"
    out_dir.mkdir(exist_ok=True)

    print("=" * 60)
    print("  STEP 1: Running pytest")
    print("=" * 60)
    tr = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).parent),
    )
    print(tr.stdout)
    if tr.returncode != 0:
        print(tr.stderr)
        return

    print("=" * 60)
    print("  STEP 2: A/B Test Analysis")
    print("=" * 60)
    print("\nBuilding fct_experiment_outcomes...")
    odf = build_experiment_outcomes(engine)
    print(f"  {len(odf)} rows")
    run_ab_analysis(odf, out_dir)

    print("\n" + "=" * 60)
    print("  STEP 3: K-Means Segmentation")
    print("=" * 60)
    print("\nBuilding member-level health KPIs...")
    kdf = build_health_kpis(engine)
    print(f"  {len(kdf):,} members")
    run_segmentation(kdf, out_dir)

    engine.dispose()
    print(f"\n{'='*60}\n  DEMO COMPLETE\n{'='*60}")


if __name__ == "__main__":
    main()

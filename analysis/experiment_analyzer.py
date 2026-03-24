"""Statistical tools for analyzing A/B experiments.

Provides the ExperimentAnalyzer class implementing Welch's t-test for
comparing two independent samples. Computes Cohen's d effect size and
a 95% confidence interval for the difference in means. Returns a
recommendation to Ship or Iterate based on a significance threshold.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Tuple

import numpy as np
from scipy import stats


def _cohen_d(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Cohen's d effect size between two samples.

    Uses pooled standard deviation with unbiased sample variances.
    """
    nx, ny = len(x), len(y)
    vx, vy = x.var(ddof=1), y.var(ddof=1)
    pooled_std = np.sqrt(((nx - 1) * vx + (ny - 1) * vy) / (nx + ny - 2) + 1e-12)
    return float((x.mean() - y.mean()) / pooled_std)


def _confidence_interval(
    x: np.ndarray, y: np.ndarray, alpha: float = 0.05
) -> Tuple[float, float]:
    """Compute a two-sided CI for the difference in means (x - y).

    Uses Welch-Satterthwaite degrees of freedom approximation.
    """
    mx, my = x.mean(), y.mean()
    sx2, sy2 = x.var(ddof=1), y.var(ddof=1)
    nx, ny = len(x), len(y)
    se = np.sqrt(sx2 / nx + sy2 / ny + 1e-12)
    df_num = (sx2 / nx + sy2 / ny) ** 2
    df_den = ((sx2 / nx) ** 2) / (nx - 1) + ((sy2 / ny) ** 2) / (ny - 1)
    df = df_num / df_den if df_den > 0 else min(nx, ny) - 1
    t_crit = stats.t.ppf(1 - alpha / 2, df)
    diff = mx - my
    return float(diff - t_crit * se), float(diff + t_crit * se)


@dataclass
class ExperimentResult:
    """Results from an A/B test analysis."""

    t_stat: float
    p_value: float
    cohen_d: float
    ci_low: float
    ci_high: float
    decision: str
    control_mean: float
    treatment_mean: float
    control_n: int
    treatment_n: int


class ExperimentAnalyzer:
    """Analyze A/B test results using Welch's t-test.

    Example::

        analyzer = ExperimentAnalyzer(alpha=0.05)
        result = analyzer.analyze(control_values, treatment_values)
        print(result.decision)  # "Ship" or "Iterate"
    """

    def __init__(self, alpha: float = 0.05) -> None:
        self.alpha = alpha

    def analyze(
        self, control: Iterable[float], treatment: Iterable[float]
    ) -> ExperimentResult:
        """Run Welch's t-test and return an ExperimentResult.

        Parameters
        ----------
        control : Iterable[float]
            Metric values for the control group.
        treatment : Iterable[float]
            Metric values for the treatment group.

        Returns
        -------
        ExperimentResult
            Dataclass with t-stat, p-value, Cohen's d, CI, and decision.
        """
        x = np.array(list(control), dtype=float)
        y = np.array(list(treatment), dtype=float)

        if len(x) < 2 or len(y) < 2:
            raise ValueError(
                f"Both groups need at least 2 observations. "
                f"Got control={len(x)}, treatment={len(y)}."
            )

        t_stat, p_value = stats.ttest_ind(x, y, equal_var=False)
        effect_size = _cohen_d(y, x)
        ci_low, ci_high = _confidence_interval(y, x, alpha=self.alpha)
        decision = "Ship" if p_value < self.alpha else "Iterate"

        return ExperimentResult(
            t_stat=float(t_stat),
            p_value=float(p_value),
            cohen_d=float(effect_size),
            ci_low=ci_low,
            ci_high=ci_high,
            decision=decision,
            control_mean=float(x.mean()),
            treatment_mean=float(y.mean()),
            control_n=len(x),
            treatment_n=len(y),
        )

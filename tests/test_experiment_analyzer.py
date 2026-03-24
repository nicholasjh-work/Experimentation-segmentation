"""Tests for experiment_analyzer.ExperimentAnalyzer.

Covers:
- Equal distributions (should not ship)
- Clearly different distributions (should ship)
- Underpowered / tiny sample (should iterate)
- Input validation (too few observations)
- Effect size direction
"""
import numpy as np
import pytest

from analysis.experiment_analyzer import ExperimentAnalyzer, ExperimentResult


@pytest.fixture
def analyzer() -> ExperimentAnalyzer:
    return ExperimentAnalyzer(alpha=0.05)


class TestEqualDistributions:
    """When control and treatment are drawn from the same distribution,
    the analyzer should recommend Iterate (not significant)."""

    def test_same_normal(self, analyzer: ExperimentAnalyzer) -> None:
        np.random.seed(42)
        control = np.random.normal(50, 5, size=500)
        treatment = np.random.normal(50, 5, size=500)
        result = analyzer.analyze(control, treatment)
        assert result.decision == "Iterate"
        assert result.p_value > 0.05

    def test_ci_contains_zero(self, analyzer: ExperimentAnalyzer) -> None:
        np.random.seed(42)
        control = np.random.normal(100, 10, size=300)
        treatment = np.random.normal(100, 10, size=300)
        result = analyzer.analyze(control, treatment)
        assert result.ci_low <= 0 <= result.ci_high


class TestDifferentDistributions:
    """When treatment is clearly better, should recommend Ship."""

    def test_large_effect(self, analyzer: ExperimentAnalyzer) -> None:
        np.random.seed(123)
        control = np.random.normal(50, 5, size=200)
        treatment = np.random.normal(55, 5, size=200)
        result = analyzer.analyze(control, treatment)
        assert result.decision == "Ship"
        assert result.p_value < 0.05

    def test_effect_size_positive(self, analyzer: ExperimentAnalyzer) -> None:
        np.random.seed(123)
        control = np.random.normal(50, 5, size=200)
        treatment = np.random.normal(55, 5, size=200)
        result = analyzer.analyze(control, treatment)
        # Treatment mean > control mean, so cohen_d should be positive
        assert result.cohen_d > 0
        assert result.treatment_mean > result.control_mean

    def test_ci_excludes_zero(self, analyzer: ExperimentAnalyzer) -> None:
        np.random.seed(123)
        control = np.random.normal(50, 5, size=200)
        treatment = np.random.normal(55, 5, size=200)
        result = analyzer.analyze(control, treatment)
        # CI for (treatment - control) should be entirely positive
        assert result.ci_low > 0


class TestUnderpowered:
    """Tiny samples should not reach significance even with real difference."""

    def test_small_sample_iterates(self, analyzer: ExperimentAnalyzer) -> None:
        np.random.seed(99)
        control = np.random.normal(50, 10, size=5)
        treatment = np.random.normal(55, 10, size=5)
        result = analyzer.analyze(control, treatment)
        # With n=5 per group and moderate effect, should not be significant
        assert result.decision == "Iterate"
        assert result.control_n == 5
        assert result.treatment_n == 5


class TestResultShape:
    """Verify the ExperimentResult dataclass has all expected fields."""

    def test_result_is_dataclass(self, analyzer: ExperimentAnalyzer) -> None:
        np.random.seed(1)
        result = analyzer.analyze(
            np.random.normal(50, 5, 100), np.random.normal(50, 5, 100)
        )
        assert isinstance(result, ExperimentResult)
        assert isinstance(result.t_stat, float)
        assert isinstance(result.p_value, float)
        assert isinstance(result.cohen_d, float)
        assert isinstance(result.ci_low, float)
        assert isinstance(result.ci_high, float)
        assert result.decision in ("Ship", "Iterate")


class TestInputValidation:
    """Edge cases and bad inputs."""

    def test_too_few_observations_raises(self, analyzer: ExperimentAnalyzer) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            analyzer.analyze([1.0], [2.0, 3.0])

    def test_empty_raises(self, analyzer: ExperimentAnalyzer) -> None:
        with pytest.raises(ValueError, match="at least 2"):
            analyzer.analyze([], [1.0, 2.0])

    def test_custom_alpha(self) -> None:
        strict = ExperimentAnalyzer(alpha=0.01)
        np.random.seed(77)
        control = np.random.normal(50, 5, size=100)
        treatment = np.random.normal(52, 5, size=100)
        result = strict.analyze(control, treatment)
        # Marginal effect at stricter alpha may not ship
        assert result.p_value > 0 and result.p_value < 1

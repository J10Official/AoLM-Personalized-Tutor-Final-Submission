"""
Tests for the Evaluation Metrics module (evaluation/metrics.py).

Covers requirements:
  R21.1–R21.3 — System evaluation metrics (faithfulness, constraint, relevance)
  R14.5       — Mastery formula verification
  R22.4–R22.5 — Cognitive depth / Bloom's level progression
"""

import math
import pytest
from backend.evaluation.metrics import (
    EvaluationMetrics, TestResult, TestSession, run_evaluation_report,
)


class TestNormalisedGain:

    def test_basic_gain(self):
        """Normalised gain with improvement."""
        g = EvaluationMetrics.normalised_gain(pre_score=0.3, post_score=0.7)
        expected = (0.7 - 0.3) / (1.0 - 0.3)
        assert abs(g - expected) < 1e-6

    def test_zero_gain(self):
        """No improvement → gain = 0."""
        g = EvaluationMetrics.normalised_gain(0.5, 0.5)
        assert g == 0.0

    def test_ceiling_pre_score(self):
        """Pre-score at max → denominator is 0 → return 0 or 1."""
        g = EvaluationMetrics.normalised_gain(1.0, 1.0)
        assert g == 0.0

    def test_perfect_gain(self):
        """Full improvement to max → gain = 1."""
        g = EvaluationMetrics.normalised_gain(0.0, 1.0)
        assert g == 1.0


class TestCohensD:

    def test_large_effect(self):
        """Cohen's d > 0.8 is a large effect."""
        pre = [0.2, 0.3, 0.25, 0.2, 0.3]
        post = [0.8, 0.9, 0.85, 0.8, 0.9]
        d = EvaluationMetrics.cohens_d(pre, post)
        assert d > 0.8

    def test_no_effect(self):
        """Identical pre/post → d = 0."""
        scores = [0.5, 0.5, 0.5]
        d = EvaluationMetrics.cohens_d(scores, scores)
        assert d == 0.0

    def test_empty_input(self):
        """Empty lists → d = 0."""
        assert EvaluationMetrics.cohens_d([], []) == 0.0


class TestRetentionRatio:

    def test_perfect_retention(self):
        """Delayed score == post score → 100% retention."""
        r = EvaluationMetrics.retention_ratio(0.8, 0.8)
        assert r == 1.0

    def test_partial_retention(self):
        """Delayed score < post score → retention < 1."""
        r = EvaluationMetrics.retention_ratio(0.8, 0.6)
        assert r == pytest.approx(0.75)

    def test_zero_post_score(self):
        """Post score 0 → return 0 (avoid div by zero)."""
        r = EvaluationMetrics.retention_ratio(0.0, 0.5)
        assert r == 0.0


class TestBloomProgression:

    def test_one_level_up(self):
        """R22.4 / R22.5: Progression from remember to understand = +1."""
        prog = EvaluationMetrics.bloom_level_progression("remember", "understand")
        assert prog == 1

    def test_two_levels_up(self):
        """Progression from understand to apply = +1."""
        prog = EvaluationMetrics.bloom_level_progression("understand", "apply")
        assert prog == 1

    def test_no_progression(self):
        """Same level → 0."""
        prog = EvaluationMetrics.bloom_level_progression("apply", "apply")
        assert prog == 0


class TestMasteryPredictionAccuracy:

    def test_perfect_correlation(self):
        """Predicted mastery perfectly matches actual scores → r = 1."""
        predicted = [0.1, 0.3, 0.5, 0.7, 0.9]
        actual = [0.1, 0.3, 0.5, 0.7, 0.9]
        r = EvaluationMetrics.mastery_prediction_accuracy(predicted, actual)
        assert abs(r - 1.0) < 1e-6

    def test_insufficient_data(self):
        """Fewer than 3 data points → return 0."""
        assert EvaluationMetrics.mastery_prediction_accuracy([0.5], [0.5]) == 0.0


class TestZPDTargetingAccuracy:

    def test_perfect_zpd_targeting(self):
        """All recommended concepts are in ZPD → 100%."""
        recommended = ["a", "b", "c"]
        actual_zpd = ["a", "b", "c", "d"]
        acc = EvaluationMetrics.zpd_targeting_accuracy(recommended, actual_zpd)
        assert acc == 1.0

    def test_partial_zpd_targeting(self):
        """Only some recommendations are in ZPD."""
        recommended = ["a", "b", "c"]
        actual_zpd = ["a", "d"]
        acc = EvaluationMetrics.zpd_targeting_accuracy(recommended, actual_zpd)
        assert abs(acc - 1 / 3) < 1e-6

    def test_empty_recommendations(self):
        """No recommendations → 0."""
        assert EvaluationMetrics.zpd_targeting_accuracy([], ["a"]) == 0.0


class TestEvaluationReport:

    def test_report_structure(self):
        """Evaluation report has expected top-level keys."""
        pre = [TestSession(
            session_type="pre_test", learner_id="u1",
            timestamp="2026-01-01",
            results=[TestResult("c1", "q1", True, 0.4, "remember", 10.0)]
        )]
        post = [TestSession(
            session_type="post_test", learner_id="u1",
            timestamp="2026-01-02",
            results=[TestResult("c1", "q1", True, 0.8, "apply", 8.0)]
        )]
        report = run_evaluation_report(pre, post)
        assert "learning_effectiveness" in report
        assert "normalised_gain" in report["learning_effectiveness"]
        assert "cohens_d" in report["learning_effectiveness"]

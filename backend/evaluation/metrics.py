"""
Evaluation Framework for the Personalised Learning System.

Implements metrics from the plan: normalised learning gain, Cohen's d,
retention measurement, and comparative benchmarks. Designed to work
with synthetic learners first and real participants later.
"""

import math
import json
import os
from dataclasses import dataclass, field
from typing import Optional
from datetime import datetime


@dataclass
class TestResult:
    """Result of a single test item."""
    concept_id: str
    question_id: str
    correct: bool
    score: float          # normalised 0-1
    bloom_level: str
    response_time: float  # seconds


@dataclass
class TestSession:
    """A pre-test or post-test session."""
    session_type: str     # 'pre_test', 'post_test', 'delayed_post_test'
    learner_id: str
    timestamp: str
    results: list[TestResult] = field(default_factory=list)

    @property
    def total_score(self) -> float:
        if not self.results:
            return 0.0
        return sum(r.score for r in self.results) / len(self.results)

    @property
    def accuracy(self) -> float:
        if not self.results:
            return 0.0
        return sum(1 for r in self.results if r.correct) / len(self.results)


class EvaluationMetrics:
    """Computes all evaluation metrics from the plan."""

    @staticmethod
    def normalised_gain(pre_score: float, post_score: float, max_score: float = 1.0) -> float:
        """
        Hake's normalised learning gain.
        
        g = (post - pre) / (max - pre)
        
        Accounts for ceiling effect: learners who start high have less room to grow.
        Target: > 0.5 (medium-high)
        """
        denominator = max_score - pre_score
        if denominator <= 0:
            return 0.0 if post_score <= pre_score else 1.0
        return (post_score - pre_score) / denominator

    @staticmethod
    def cohens_d(pre_scores: list[float], post_scores: list[float]) -> float:
        """
        Cohen's d effect size for pre-post comparison.
        
        d = (mean_post - mean_pre) / pooled_SD
        
        Interpretation: 0.2 = small, 0.5 = medium, 0.8 = large
        Target: > 0.8
        """
        n = len(pre_scores)
        if n == 0:
            return 0.0

        mean_pre = sum(pre_scores) / n
        mean_post = sum(post_scores) / n

        var_pre = sum((x - mean_pre) ** 2 for x in pre_scores) / max(n - 1, 1)
        var_post = sum((x - mean_post) ** 2 for x in post_scores) / max(n - 1, 1)

        pooled_sd = math.sqrt((var_pre + var_post) / 2)
        if pooled_sd == 0:
            return 0.0

        return (mean_post - mean_pre) / pooled_sd

    @staticmethod
    def retention_ratio(post_score: float, delayed_score: float) -> float:
        """
        Retention at delayed post-test.
        
        retention = delayed_score / post_score
        
        Target: > 0.75 (at 2 weeks)
        """
        if post_score == 0:
            return 0.0
        return delayed_score / post_score

    @staticmethod
    def bloom_level_progression(pre_bloom: str, post_bloom: str) -> int:
        """
        Change in highest Bloom's level consistently answered correctly.
        
        Target: increase >= 1 level
        """
        levels = ["remember", "understand", "apply", "analyse", "evaluate", "create"]
        pre_idx = levels.index(pre_bloom) if pre_bloom in levels else 0
        post_idx = levels.index(post_bloom) if post_bloom in levels else 0
        return post_idx - pre_idx

    @staticmethod
    def mastery_prediction_accuracy(
        predicted_mastery: list[float],
        actual_scores: list[float]
    ) -> float:
        """
        Pearson correlation between predicted mastery and actual test performance.
        
        Target: r > 0.7
        """
        n = len(predicted_mastery)
        if n < 3:
            return 0.0

        mean_p = sum(predicted_mastery) / n
        mean_a = sum(actual_scores) / n

        cov = sum((p - mean_p) * (a - mean_a) for p, a in zip(predicted_mastery, actual_scores))
        std_p = math.sqrt(sum((p - mean_p) ** 2 for p in predicted_mastery))
        std_a = math.sqrt(sum((a - mean_a) ** 2 for a in actual_scores))

        if std_p == 0 or std_a == 0:
            return 0.0

        return cov / (std_p * std_a)

    @staticmethod
    def zpd_targeting_accuracy(
        recommended_concepts: list[str],
        actual_zpd_concepts: list[str]
    ) -> float:
        """
        % of recommended concepts that fall in the learner's actual ZPD.
        
        Target: > 80%
        """
        if not recommended_concepts:
            return 0.0
        hits = sum(1 for c in recommended_concepts if c in actual_zpd_concepts)
        return hits / len(recommended_concepts)

    @staticmethod
    def confidence_calibration(
        confidences: list[float],
        accuracies: list[bool]
    ) -> float:
        """
        Correlation between response-time-derived confidence and actual correctness.
        
        Target: r > 0.6
        """
        n = len(confidences)
        if n < 3:
            return 0.0

        acc_float = [1.0 if a else 0.0 for a in accuracies]
        return EvaluationMetrics.mastery_prediction_accuracy(confidences, acc_float)


def run_evaluation_report(pre_tests: list[TestSession], post_tests: list[TestSession],
                          delayed_tests: list[TestSession] = None) -> dict:
    """
    Generate a complete evaluation report from test data.
    """
    metrics = EvaluationMetrics()

    # Aggregate scores
    pre_scores = [t.total_score for t in pre_tests]
    post_scores = [t.total_score for t in post_tests]

    avg_pre = sum(pre_scores) / max(len(pre_scores), 1)
    avg_post = sum(post_scores) / max(len(post_scores), 1)

    # Normalised gains per learner
    gains = [
        metrics.normalised_gain(pre, post)
        for pre, post in zip(pre_scores, post_scores)
    ]
    avg_gain = sum(gains) / max(len(gains), 1)

    # Effect size
    d = metrics.cohens_d(pre_scores, post_scores)

    report = {
        "timestamp": datetime.now().isoformat(),
        "n_learners": len(pre_tests),
        "learning_effectiveness": {
            "avg_pre_score": round(avg_pre, 4),
            "avg_post_score": round(avg_post, 4),
            "normalised_gain": round(avg_gain, 4),
            "cohens_d": round(d, 4),
            "gains_per_learner": [round(g, 4) for g in gains],
            "interpretation": {
                "gain": "high" if avg_gain > 0.5 else "medium" if avg_gain > 0.3 else "low",
                "effect_size": "large" if d > 0.8 else "medium" if d > 0.5 else "small"
            }
        }
    }

    # Retention (if delayed tests available)
    if delayed_tests:
        delayed_scores = [t.total_score for t in delayed_tests]
        retention_ratios = [
            metrics.retention_ratio(post, delayed)
            for post, delayed in zip(post_scores, delayed_scores)
        ]
        avg_retention = sum(retention_ratios) / max(len(retention_ratios), 1)
        report["retention"] = {
            "avg_delayed_score": round(sum(delayed_scores) / max(len(delayed_scores), 1), 4),
            "avg_retention_ratio": round(avg_retention, 4),
            "meets_target": avg_retention >= 0.75
        }

    return report

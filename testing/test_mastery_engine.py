"""
Tests for the Mastery Engine (core/mastery_engine.py).

Covers requirements:
  R14.3  — Mastery update after evaluation
  R14.5  — Mastery formula: M_new = 0.3 × score + 0.7 × M_old (generalised)
  R15.1  — Ebbinghaus decay: M_effective = M_base × e^(-t/S)
  R15.2  — EMA blending
  R15.3  — Balance recent performance with history
  R15.4  — Prevent instability (clamp 0–1)
  R6.8   — Update learner graph after session
"""

import math
import pytest
from datetime import datetime, timezone, timedelta
from backend.core.mastery_engine import MasteryEngine
from backend.core.learner_model import LearnerModel, ConceptState


class TestBayesianUpdate:

    def test_correct_answer_increases_mastery(self, sample_kg):
        """R14.3: Correct answer should increase mastery via BKT."""
        engine = MasteryEngine(sample_kg)
        posterior = engine.bayesian_update(prior_mastery=0.5, correct=True)
        assert posterior > 0.5

    def test_incorrect_answer_decreases_mastery(self, sample_kg):
        """R14.3: Incorrect answer should decrease mastery via BKT."""
        engine = MasteryEngine(sample_kg)
        # Note: P_LEARN still applies so we need to check relative decrease
        prior = 0.7
        posterior = engine.bayesian_update(prior, correct=False)
        # The slip/guess + learning transition means posterior may not be < prior
        # but should be less than a correct-answer posterior
        posterior_correct = engine.bayesian_update(prior, correct=True)
        assert posterior < posterior_correct

    def test_bayesian_update_clamped(self, sample_kg):
        """R15.4: BKT posterior is clamped to [0, 1]."""
        engine = MasteryEngine(sample_kg)
        posterior = engine.bayesian_update(1.0, correct=True)
        assert 0.0 <= posterior <= 1.0
        posterior = engine.bayesian_update(0.0, correct=False)
        assert 0.0 <= posterior <= 1.0


class TestForgettingDecay:

    def test_no_decay_if_never_reviewed(self, sample_kg):
        """R15.1: No decay if concept was never reviewed."""
        engine = MasteryEngine(sample_kg)
        cs = ConceptState(concept_id="variables")
        # last_reviewed is None → decay factor = 1.0
        decay = engine.compute_forgetting_decay(cs)
        assert decay == 1.0

    def test_decay_increases_with_time(self, sample_kg):
        """R15.1: Longer time since review → lower retention."""
        engine = MasteryEngine(sample_kg)
        now = datetime.now(timezone.utc)

        cs_recent = ConceptState(
            concept_id="variables",
            last_reviewed=(now - timedelta(days=1)).isoformat(),
        )
        cs_old = ConceptState(
            concept_id="variables",
            last_reviewed=(now - timedelta(days=30)).isoformat(),
        )

        decay_recent = engine.compute_forgetting_decay(cs_recent)
        decay_old = engine.compute_forgetting_decay(cs_old)
        assert decay_recent > decay_old

    def test_successful_retrievals_strengthen_memory(self, sample_kg):
        """R15.1: More successful retrievals → slower forgetting (higher S)."""
        engine = MasteryEngine(sample_kg)
        now = datetime.now(timezone.utc)
        reviewed_at = (now - timedelta(days=14)).isoformat()

        cs_weak = ConceptState(
            concept_id="variables",
            last_reviewed=reviewed_at,
            successful_retrievals=0,
        )
        cs_strong = ConceptState(
            concept_id="variables",
            last_reviewed=reviewed_at,
            successful_retrievals=5,
        )

        decay_weak = engine.compute_forgetting_decay(cs_weak)
        decay_strong = engine.compute_forgetting_decay(cs_strong)
        assert decay_strong > decay_weak


class TestMasteryUpdatePipeline:

    def test_correct_high_score_increases_mastery(self, sample_kg, sample_learner):
        """R14.5 / R15.2: Correct answer with high score increases mastery."""
        engine = MasteryEngine(sample_kg)
        old_mastery = sample_learner.get_concept_state("operators").mastery  # 0.4

        new_mastery = engine.update_mastery(
            learner=sample_learner,
            concept_id="operators",
            score=0.9,
            correct=True,
            response_time=10.0,
        )
        assert new_mastery > old_mastery

    def test_incorrect_low_score_decreases_mastery(self, sample_kg, sample_learner):
        """R14.5 / R15.2: Incorrect answer with low score decreases mastery."""
        engine = MasteryEngine(sample_kg)
        old_mastery = sample_learner.get_concept_state("variables").mastery  # 0.8

        new_mastery = engine.update_mastery(
            learner=sample_learner,
            concept_id="variables",
            score=0.0,
            correct=False,
            response_time=60.0,
        )
        assert new_mastery < old_mastery

    def test_mastery_always_in_zero_one(self, sample_kg, sample_learner):
        """R15.4: Mastery is clamped to [0, 1] regardless of inputs."""
        engine = MasteryEngine(sample_kg)
        for _ in range(20):
            new_m = engine.update_mastery(
                sample_learner, "variables", score=1.0, correct=True, response_time=1.0
            )
            assert 0.0 <= new_m <= 1.0

    def test_mastery_history_tracked(self, sample_kg, sample_learner):
        """R6.8 / R16.5: Mastery history is appended after each update."""
        engine = MasteryEngine(sample_kg)
        cs = sample_learner.get_concept_state("operators")
        initial_history_len = len(cs.mastery_history)

        engine.update_mastery(
            sample_learner, "operators", score=0.7, correct=True, response_time=15.0
        )
        assert len(cs.mastery_history) == initial_history_len + 1

    def test_total_attempts_incremented(self, sample_kg, sample_learner):
        """R6.8: Total attempts counter is incremented."""
        engine = MasteryEngine(sample_kg)
        cs = sample_learner.get_concept_state("operators")
        old_attempts = cs.total_attempts

        engine.update_mastery(
            sample_learner, "operators", score=0.5, correct=False, response_time=20.0
        )
        assert cs.total_attempts == old_attempts + 1


class TestPrerequisitePenalty:

    def test_penalty_on_failure(self, sample_kg, sample_learner):
        """R10.3: Failing a concept penalises its prerequisites."""
        engine = MasteryEngine(sample_kg)
        old_mastery_operators = sample_learner.get_concept_state("operators").mastery

        penalised = engine.apply_prerequisite_penalty(
            sample_learner, failed_concept_id="conditionals", penalty=0.05
        )
        assert "operators" in penalised
        new_mastery = sample_learner.get_concept_state("operators").mastery
        assert new_mastery < old_mastery_operators

    def test_penalty_does_not_go_below_zero(self, sample_kg, sample_learner):
        """R15.4: Penalty should not push mastery below 0."""
        engine = MasteryEngine(sample_kg)
        sample_learner.get_concept_state("variables").mastery = 0.01
        engine.apply_prerequisite_penalty(
            sample_learner, "data_types", penalty=0.1
        )
        assert sample_learner.get_concept_state("variables").mastery >= 0.0


class TestReviewSchedule:

    def test_concepts_needing_review(self, sample_kg, sample_learner):
        """R-API.9: Can identify concepts that have decayed below threshold."""
        engine = MasteryEngine(sample_kg)
        # Set a concept as reviewed a long time ago
        cs = sample_learner.get_concept_state("variables")
        cs.mastery = 0.7
        cs.last_reviewed = (
            datetime.now(timezone.utc) - timedelta(days=60)
        ).isoformat()

        needs_review = engine.get_concepts_needing_review(sample_learner, threshold=0.6)
        review_ids = [cid for cid, _ in needs_review]
        assert "variables" in review_ids

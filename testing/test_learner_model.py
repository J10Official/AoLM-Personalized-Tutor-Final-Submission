"""
Tests for the Learner Model (core/learner_model.py).

Covers requirements:
  R6.9   — Personalised Learner Graph (JSON)
  R16.1  — learner_id
  R16.2  — Per-concept mastery scores
  R16.3  — Per-concept doubts
  R16.4  — Persisted per learner (JSON file)
  R16.5  — Updated after each session
  R5.4   — Build dataset of misconceptions
"""

import os
import json
import pytest
from backend.core.learner_model import LearnerModel, ConceptState, SessionLog


class TestLearnerModelCreation:

    def test_create_learner_with_id(self):
        """R16.1: Learner graph stores learner_id."""
        learner = LearnerModel(learner_id="arjun", name="Arjun")
        assert learner.learner_id == "arjun"
        assert learner.name == "Arjun"

    def test_default_empty_state(self):
        """R16.2: New learner starts with no concepts."""
        learner = LearnerModel(learner_id="new_user")
        assert len(learner.concepts) == 0
        assert learner.avg_mastery == 0.0


class TestConceptState:

    def test_get_concept_state_auto_creates(self):
        """R16.2: Accessing a concept state auto-creates it at mastery 0."""
        learner = LearnerModel(learner_id="test")
        cs = learner.get_concept_state("variables")
        assert cs.concept_id == "variables"
        assert cs.mastery == 0.0

    def test_mastery_map(self, sample_learner):
        """R16.2: Mastery map returns all concept mastery levels."""
        mastery_map = sample_learner.get_mastery_map()
        assert "variables" in mastery_map
        assert mastery_map["variables"] == 0.8
        assert mastery_map["loops"] == 0.0

    def test_known_concepts_threshold(self, sample_learner):
        """R16.2: Can filter concepts by mastery threshold."""
        known = sample_learner.get_known_concepts(threshold=0.3)
        assert "variables" in known
        assert "data_types" in known
        assert "operators" in known
        assert "conditionals" not in known  # 0.15 < 0.3

    def test_mastered_concepts(self, sample_learner):
        """R16.2: Can identify mastered concepts (≥ 0.7)."""
        mastered = sample_learner.get_mastered_concepts(threshold=0.7)
        assert "variables" in mastered
        assert "operators" not in mastered


class TestDoubts:

    def test_store_doubt(self):
        """R16.3 / R5.4: Doubts are stored per concept."""
        learner = LearnerModel(learner_id="test")
        cs = learner.get_concept_state("gradient_descent")
        cs.doubts.append({
            "text": "Why does learning rate matter so much?",
            "type": "causal",
            "resolved": True,
            "resolution": "Because it controls step size..."
        })
        assert len(cs.doubts) == 1
        assert cs.doubts[0]["text"] == "Why does learning rate matter so much?"

    def test_get_all_doubts(self):
        """R16.3: Can retrieve all doubts across concepts."""
        learner = LearnerModel(learner_id="test")
        cs1 = learner.get_concept_state("concept_a")
        cs1.doubts.append({"text": "Doubt 1", "resolved": True})
        cs2 = learner.get_concept_state("concept_b")
        cs2.doubts.append({"text": "Doubt 2", "resolved": False})

        all_doubts = learner.get_all_doubts()
        assert len(all_doubts) == 2

    def test_get_unresolved_doubts_only(self):
        """R16.3: Can filter to only unresolved doubts."""
        learner = LearnerModel(learner_id="test")
        cs = learner.get_concept_state("concept_a")
        cs.doubts.append({"text": "Resolved doubt", "resolved": True})
        cs.doubts.append({"text": "Unresolved doubt", "resolved": False})

        unresolved = learner.get_all_doubts(unresolved_only=True)
        assert len(unresolved) == 1
        assert unresolved[0]["text"] == "Unresolved doubt"

    def test_misconceptions_stored(self):
        """R5.4: Misconceptions detected by doubt resolver are stored."""
        learner = LearnerModel(learner_id="test")
        cs = learner.get_concept_state("concept_a")
        cs.misconceptions_detected.append("Confuses X with Y")
        assert len(cs.misconceptions_detected) == 1


class TestCourseEnrollment:

    def test_enroll_in_course(self, sample_kg):
        """R6.9: Learner can enroll in a course, adding all concepts."""
        learner = LearnerModel(learner_id="new")
        concept_ids = list(sample_kg.concepts.keys())
        newly_enrolled = learner.enroll_in_course("Intro to Python", concept_ids)

        assert len(newly_enrolled) == 5
        assert "Intro to Python" in learner.enrolled_courses
        assert learner.is_enrolled_in("Intro to Python")

    def test_double_enrollment_no_duplicates(self, sample_kg):
        """R6.9: Re-enrolling doesn't duplicate concepts."""
        learner = LearnerModel(learner_id="new")
        concept_ids = list(sample_kg.concepts.keys())
        learner.enroll_in_course("Intro to Python", concept_ids)
        newly = learner.enroll_in_course("Intro to Python", concept_ids)
        assert len(newly) == 0  # All already enrolled


class TestLearnerPersistence:

    def test_save_and_load(self, sample_learner, tmp_dir):
        """R16.4: Learner profile is persisted to and loaded from JSON."""
        path = os.path.join(tmp_dir, "learners", "test_user.json")
        sample_learner.save(path)
        assert os.path.exists(path)

        loaded = LearnerModel.load(path)
        assert loaded.learner_id == sample_learner.learner_id
        assert loaded.get_concept_state("variables").mastery == 0.8

    def test_json_structure(self, sample_learner, tmp_dir):
        """R16.4: JSON file has expected structure."""
        path = os.path.join(tmp_dir, "learners", "test_user.json")
        sample_learner.save(path)
        with open(path) as f:
            data = json.load(f)
        assert "learner_id" in data
        assert "concepts" in data
        assert "global_stats" in data
        assert "enrolled_courses" in data


class TestSessionLogging:

    def test_add_session(self):
        """R16.5: Sessions are logged in the learner profile."""
        learner = LearnerModel(learner_id="test")
        session = SessionLog(
            session_id="sess_1",
            concept_id="variables",
            started_at="2026-05-01T10:00:00Z",
            ended_at="2026-05-01T10:10:00Z",
            questions_attempted=5,
            questions_correct=4,
            mastery_before=0.3,
            mastery_after=0.5,
        )
        learner.add_session(session)
        assert learner.total_sessions == 1


class TestConceptStateProperties:

    def test_calibration_accuracy_no_attempts(self):
        """Calibration accuracy defaults to 0.5 with no data."""
        cs = ConceptState(concept_id="test")
        assert cs.calibration_accuracy == 0.5

    def test_calibration_accuracy_with_data(self):
        """Calibration accuracy = correct / total."""
        cs = ConceptState(concept_id="test", total_attempts=10, correct_attempts=7)
        assert cs.calibration_accuracy == 0.7

    def test_confidence_from_response_time(self):
        """Response time maps to a confidence value in [0.1, 1.0]."""
        cs = ConceptState(concept_id="test", avg_response_time=5.0)
        conf = cs.confidence_from_response_time
        assert 0.1 <= conf <= 1.0

    def test_confidence_decreases_with_slow_response(self):
        """Slower response → lower confidence."""
        fast = ConceptState(concept_id="t1", avg_response_time=5.0)
        slow = ConceptState(concept_id="t2", avg_response_time=60.0)
        assert fast.confidence_from_response_time > slow.confidence_from_response_time

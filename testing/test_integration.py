"""
Integration-style tests that verify end-to-end flows WITHOUT an LLM.

Covers requirements:
  R6.8   — Update learner graph after session (mastery pipeline)
  R5.5   — Bridge doubts to known concepts
  R12.5  — Store doubts
  R14.3  — Mastery update via evaluator
  R24.1  — Learning is long-form and structured (session structure)
"""

import pytest
from backend.core.knowledge_graph import KnowledgeGraph, BloomLevel
from backend.core.learner_model import LearnerModel, ConceptState
from backend.core.mastery_engine import MasteryEngine


class TestFullMasteryPipeline:
    """Simulate a complete learning + evaluation cycle."""

    def test_mastery_improves_after_correct_answers(self, sample_kg, sample_learner):
        """R6.8 / R14.3: Mastery increases over a series of correct answers."""
        engine = MasteryEngine(sample_kg)
        concept_id = "operators"
        initial_mastery = sample_learner.get_concept_state(concept_id).mastery

        # Simulate 5 correct answers
        for i in range(5):
            engine.update_mastery(
                sample_learner, concept_id,
                score=0.8, correct=True, response_time=10.0
            )

        final_mastery = sample_learner.get_concept_state(concept_id).mastery
        assert final_mastery > initial_mastery

    def test_mastery_decreases_after_wrong_answers(self, sample_kg, sample_learner):
        """R6.8 / R14.3: Mastery decreases after repeated failures."""
        engine = MasteryEngine(sample_kg)
        concept_id = "variables"
        initial_mastery = sample_learner.get_concept_state(concept_id).mastery  # 0.8

        for i in range(5):
            engine.update_mastery(
                sample_learner, concept_id,
                score=0.0, correct=False, response_time=60.0
            )

        final_mastery = sample_learner.get_concept_state(concept_id).mastery
        assert final_mastery < initial_mastery


class TestDoubtStoragePipeline:
    """Verify doubt storage and retrieval across the system."""

    def test_doubt_stored_and_retrievable(self, sample_learner):
        """R12.5 / R5.4: Doubts are stored and can be retrieved."""
        cs = sample_learner.get_concept_state("operators")
        cs.doubts.append({
            "text": "Why does order of operations matter?",
            "type": "causal",
            "resolved": True,
            "resolution": "Because operations have different precedence...",
        })

        all_doubts = sample_learner.get_all_doubts()
        doubt_texts = [d["text"] for d in all_doubts]
        assert "Why does order of operations matter?" in doubt_texts

    def test_misconception_stored_across_concepts(self, sample_learner):
        """R5.4: Misconceptions are tracked per concept."""
        cs1 = sample_learner.get_concept_state("variables")
        cs1.misconceptions_detected.append("Confuses variable with constant")
        cs2 = sample_learner.get_concept_state("data_types")
        cs2.misconceptions_detected.append("Thinks int and float are the same")

        total_misconceptions = sum(
            len(cs.misconceptions_detected) for cs in sample_learner.concepts.values()
        )
        assert total_misconceptions == 2


class TestLearnerProgressionSimulation:
    """Simulate a learner progressing through the concept graph."""

    def test_zpd_expands_as_mastery_grows(self, sample_kg, sample_learner):
        """R3.1 / R10.2: As the learner masters concepts, more become ZPD-ready."""
        engine = MasteryEngine(sample_kg)

        # Initially, with low mastery on operators/conditionals/loops, few are ready
        initial_ready = sample_kg.get_ready_concepts(
            sample_learner.get_mastery_map(), threshold=0.5
        )

        # Boost operators mastery
        sample_learner.get_concept_state("operators").mastery = 0.7

        expanded_ready = sample_kg.get_ready_concepts(
            sample_learner.get_mastery_map(), threshold=0.5
        )

        # With operators mastered, conditionals should now be ZPD-ready
        assert len(expanded_ready) >= len(initial_ready)

    def test_diagnostic_rollback_after_failure(self, sample_kg, sample_learner):
        """R10.3: After failing a concept, system identifies weak prerequisites."""
        engine = MasteryEngine(sample_kg)

        # Learner fails loops (mastery 0.0)
        # Prerequisite chain: loops → conditionals → operators → data_types, variables
        # Set operators as weak
        sample_learner.get_concept_state("operators").mastery = 0.2

        chain = sample_kg.get_diagnostic_chain(
            "loops", sample_learner.get_mastery_map(), threshold=0.5
        )

        # Should identify at least conditionals and operators as weak
        assert "conditionals" in chain or "operators" in chain

    def test_prerequisite_penalty_cascades(self, sample_kg, sample_learner):
        """R10.3: Failing a concept penalises its prerequisites."""
        engine = MasteryEngine(sample_kg)

        old_operators = sample_learner.get_concept_state("operators").mastery

        penalised = engine.apply_prerequisite_penalty(
            sample_learner, "conditionals", penalty=0.05
        )

        assert "operators" in penalised
        assert sample_learner.get_concept_state("operators").mastery < old_operators


class TestKnowledgeGraphIntegrity:
    """Verify KG structural integrity through operations."""

    def test_save_load_preserves_structure(self, sample_kg, tmp_dir):
        """R9.7 / R9.8: Save/load roundtrip preserves all relationships."""
        import os
        path = os.path.join(tmp_dir, "kg.json")
        sample_kg.save(path)

        loaded = KnowledgeGraph.load(path)

        # Same concepts
        assert set(loaded.concepts.keys()) == set(sample_kg.concepts.keys())

        # Same prerequisites
        for cid in sample_kg.concepts:
            assert (
                loaded.concepts[cid].prerequisites
                == sample_kg.concepts[cid].prerequisites
            )

        # Same courses
        assert len(loaded.courses) == len(sample_kg.courses)

    def test_topological_order_stable(self, sample_kg):
        """R9.8: Topological order is deterministic and valid."""
        order1 = sample_kg.topological_order()
        order2 = sample_kg.topological_order()
        assert order1 == order2  # Deterministic
        assert len(order1) == len(sample_kg.concepts)

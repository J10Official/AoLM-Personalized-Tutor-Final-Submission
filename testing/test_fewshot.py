"""
Tests for the Few-Shot Examples system.

Validates:
- All example sets exist and are non-empty
- Examples match DSPy Signature field names
- Examples cover the expected mastery levels
- Flywheel-approved examples are merged correctly
- get_all_examples returns the correct structure
"""

import json
import os
import pytest
import dspy


class TestExamplesExist:
    """All agents have at least one few-shot example."""

    def test_source_curator_examples(self):
        from backend.agents.fewshot_examples import SOURCE_CURATOR_EXAMPLES
        assert len(SOURCE_CURATOR_EXAMPLES) >= 2

    def test_learning_curator_examples(self):
        from backend.agents.fewshot_examples import LEARNING_CURATOR_EXAMPLES
        assert len(LEARNING_CURATOR_EXAMPLES) >= 1

    def test_retrieval_question_examples(self):
        from backend.agents.fewshot_examples import RETRIEVAL_QUESTION_EXAMPLES
        assert len(RETRIEVAL_QUESTION_EXAMPLES) >= 1

    def test_doubt_resolver_examples(self):
        from backend.agents.fewshot_examples import DOUBT_RESOLVER_EXAMPLES
        assert len(DOUBT_RESOLVER_EXAMPLES) >= 2

    def test_question_generator_examples(self):
        from backend.agents.fewshot_examples import QUESTION_GENERATOR_EXAMPLES
        assert len(QUESTION_GENERATOR_EXAMPLES) >= 1

    def test_evaluator_written_examples(self):
        from backend.agents.fewshot_examples import EVALUATOR_WRITTEN_EXAMPLES
        assert len(EVALUATOR_WRITTEN_EXAMPLES) >= 2

    def test_evaluator_mcq_examples(self):
        from backend.agents.fewshot_examples import EVALUATOR_MCQ_EXAMPLES
        assert len(EVALUATOR_MCQ_EXAMPLES) >= 2


class TestExampleFieldNames:
    """Examples match their corresponding DSPy Signature fields."""

    def test_source_curator_has_required_fields(self):
        from backend.agents.fewshot_examples import SOURCE_CURATOR_EXAMPLES
        ex = SOURCE_CURATOR_EXAMPLES[0]
        # Input fields
        assert hasattr(ex, 'concept_name')
        assert hasattr(ex, 'mastery_level')
        assert hasattr(ex, 'depth_instructions')
        # Output fields
        assert hasattr(ex, 'curated_document')
        assert hasattr(ex, 'quality_notes')

    def test_doubt_resolver_has_required_fields(self):
        from backend.agents.fewshot_examples import DOUBT_RESOLVER_EXAMPLES
        ex = DOUBT_RESOLVER_EXAMPLES[0]
        assert hasattr(ex, 'doubt')
        assert hasattr(ex, 'answer')
        assert hasattr(ex, 'misconception_type')
        assert hasattr(ex, 'follow_up_question')

    def test_question_generator_has_required_fields(self):
        from backend.agents.fewshot_examples import QUESTION_GENERATOR_EXAMPLES
        ex = QUESTION_GENERATOR_EXAMPLES[0]
        assert hasattr(ex, 'concept_name')
        assert hasattr(ex, 'bloom_levels_allowed')
        assert hasattr(ex, 'questions')

    def test_evaluator_written_has_required_fields(self):
        from backend.agents.fewshot_examples import EVALUATOR_WRITTEN_EXAMPLES
        ex = EVALUATOR_WRITTEN_EXAMPLES[0]
        assert hasattr(ex, 'concept_accuracy_score')
        assert hasattr(ex, 'feedback')

    def test_evaluator_mcq_has_required_fields(self):
        from backend.agents.fewshot_examples import EVALUATOR_MCQ_EXAMPLES
        ex = EVALUATOR_MCQ_EXAMPLES[0]
        assert hasattr(ex, 'is_correct')
        assert hasattr(ex, 'feedback')


class TestExampleMasteryLevels:
    """Examples cover the range of mastery levels."""

    def test_source_curator_covers_beginner_and_advanced(self):
        from backend.agents.fewshot_examples import SOURCE_CURATOR_EXAMPLES
        levels = {ex.mastery_level for ex in SOURCE_CURATOR_EXAMPLES}
        assert "beginner" in levels
        assert "advanced" in levels

    def test_doubt_resolver_covers_misconception_types(self):
        from backend.agents.fewshot_examples import DOUBT_RESOLVER_EXAMPLES
        types = {ex.misconception_type for ex in DOUBT_RESOLVER_EXAMPLES}
        assert "relational" in types
        assert "none" in types

    def test_evaluator_covers_strong_and_weak(self):
        from backend.agents.fewshot_examples import EVALUATOR_WRITTEN_EXAMPLES
        scores = [ex.concept_accuracy_score for ex in EVALUATOR_WRITTEN_EXAMPLES]
        assert max(scores) >= 3  # Strong answer
        assert min(scores) <= 1  # Weak answer


class TestGetAllExamples:
    """get_all_examples returns a complete, correctly-structured dict."""

    def test_returns_all_keys(self):
        from backend.agents.fewshot_examples import get_all_examples
        examples = get_all_examples()
        expected_keys = {
            "source_curator", "learning_curator", "retrieval_questions",
            "doubt_resolver", "question_generator",
            "evaluator_written", "evaluator_mcq",
        }
        assert set(examples.keys()) == expected_keys

    def test_all_values_are_lists(self):
        from backend.agents.fewshot_examples import get_all_examples
        examples = get_all_examples()
        for key, value in examples.items():
            assert isinstance(value, list), f"{key} should be a list"

    def test_all_examples_are_dspy_examples(self):
        from backend.agents.fewshot_examples import get_all_examples
        examples = get_all_examples()
        for key, value in examples.items():
            for ex in value:
                assert isinstance(ex, dspy.Example), f"{key} should contain dspy.Example instances"


class TestFlywheelMerge:
    """Flywheel-approved examples are merged into the doubt resolver set."""

    def test_merge_with_no_flywheel_file(self):
        """Without flywheel data, hand-crafted examples are still returned."""
        from backend.agents.fewshot_examples import get_all_examples
        examples = get_all_examples()
        assert len(examples["doubt_resolver"]) >= 2  # At least the hand-crafted ones

    def test_merge_with_flywheel_file(self, tmp_path):
        """When flywheel data exists, it's merged into doubt_resolver."""
        # Create a fake approved_examples.json
        flywheel_data = {
            "doubt_resolution": [
                {
                    "concept_name": "Sorting",
                    "doubt": "Why is quicksort faster?",
                    "answer": "Average case O(n log n).",
                    "misconception_type": "none",
                    "misconception_explanation": "",
                    "follow_up_question": "What is the worst case?",
                }
            ],
            "evaluation": [],
            "total_approved": 1,
        }
        flywheel_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "backend", "data", "flywheel"
        )
        os.makedirs(flywheel_dir, exist_ok=True)
        path = os.path.join(flywheel_dir, "approved_examples.json")
        already_existed = os.path.exists(path)

        try:
            with open(path, "w") as f:
                json.dump(flywheel_data, f)

            from backend.agents.fewshot_examples import get_all_examples
            examples = get_all_examples()
            # Should include hand-crafted (2) + flywheel (1) = 3
            assert len(examples["doubt_resolver"]) >= 3
        finally:
            # Clean up — don't leave test data in the real flywheel dir
            if not already_existed and os.path.exists(path):
                os.remove(path)


class TestAgentDemosLoaded:
    """Verify that agents actually set demos on their predictors."""

    def test_source_curator_has_demos(self):
        from backend.agents.source_curator import SourceCuratorAgent
        from backend.core.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        agent = SourceCuratorAgent(kg)
        assert hasattr(agent.curator, 'demos')
        assert len(agent.curator.demos) >= 1

    def test_doubt_resolver_has_demos(self):
        from backend.agents.doubt_resolver import DoubtResolverAgent
        from backend.core.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        agent = DoubtResolverAgent(kg)
        assert hasattr(agent.resolver, 'demos')
        assert len(agent.resolver.demos) >= 1

    def test_evaluator_has_demos(self):
        from backend.agents.evaluator import EvaluatorAgent
        from backend.core.knowledge_graph import KnowledgeGraph
        kg = KnowledgeGraph()
        agent = EvaluatorAgent(kg)
        assert hasattr(agent.mcq_evaluator, 'demos')
        assert hasattr(agent.written_evaluator, 'demos')
        assert len(agent.mcq_evaluator.demos) >= 1
        assert len(agent.written_evaluator.demos) >= 1

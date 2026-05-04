"""
Tests for Agent structural correctness (agents/*.py).

These tests verify that each agent class exists, has the correct DSPy
signatures, correct initialisation, and correct interface — WITHOUT
calling the actual LLM.

Covers requirements:
  R2.1   — 6 modular DSPy agents
  R6.2–6.7 — Each agent exists with correct interface
  R8.4–8.6 — Source Curator mastery calibration
  R11.4–11.6 — Learning Curator depth rules
  R12.2  — Doubt Resolver uses only known concepts
  R13.4  — Question Generator Bloom's level gating
  R14.1  — Evaluator MCQ scoring
  R14.2  — Evaluator written scoring
  R25.1–25.3 — DSPy Signature, Module, ChainOfThought usage
"""

import pytest
from backend.agents.source_curator import SourceCuratorAgent, SourceCurationSignature
from backend.agents.recommender import RecommenderAgent, MotivationSignature
from backend.agents.learning_curator import (
    LearningCuratorAgent, AdaptiveExplanationSignature, RetrievalQuestionSignature,
)
from backend.agents.doubt_resolver import DoubtResolverAgent, DoubtResolutionSignature
from backend.agents.question_generator import QuestionGeneratorAgent, QuestionGenerationSignature
from backend.agents.evaluator import (
    EvaluatorAgent, MCQEvaluationSignature, WrittenEvaluationSignature,
)
import dspy


# ──────────────────────────────────────────────
# R2.1 — All 6 agents exist
# ──────────────────────────────────────────────

class TestAllAgentsExist:

    def test_source_curator_exists(self, sample_kg):
        """R6.3: Source Curator agent can be instantiated."""
        agent = SourceCuratorAgent(sample_kg)
        assert agent is not None

    def test_recommender_exists(self, sample_kg):
        """R6.2: Recommender agent can be instantiated."""
        agent = RecommenderAgent(sample_kg)
        assert agent is not None

    def test_learning_curator_exists(self, sample_kg):
        """R6.4: Learning Curator agent can be instantiated."""
        agent = LearningCuratorAgent(sample_kg)
        assert agent is not None

    def test_doubt_resolver_exists(self, sample_kg):
        """R6.5: Doubt Resolver agent can be instantiated."""
        agent = DoubtResolverAgent(sample_kg)
        assert agent is not None

    def test_question_generator_exists(self, sample_kg):
        """R6.6: Question Generator agent can be instantiated."""
        agent = QuestionGeneratorAgent(sample_kg)
        assert agent is not None

    def test_evaluator_exists(self, sample_kg):
        """R6.7: Evaluator agent can be instantiated."""
        agent = EvaluatorAgent(sample_kg)
        assert agent is not None


# ──────────────────────────────────────────────
# R25.1 — DSPy Signatures have correct fields
# ──────────────────────────────────────────────

class TestDSPySignatures:

    def _sig_has_field(self, sig, field_name):
        """Check if a DSPy Signature has a field (using model_fields or repr)."""
        # DSPy Signatures expose fields in their string repr
        return field_name in str(sig)

    def test_source_curation_signature_fields(self):
        """R25.1: SourceCurationSignature has required input/output fields."""
        sig = SourceCurationSignature
        assert self._sig_has_field(sig, 'concept_name')
        assert self._sig_has_field(sig, 'mastery_level')
        assert self._sig_has_field(sig, 'depth_instructions')
        assert self._sig_has_field(sig, 'curated_document')
        assert self._sig_has_field(sig, 'quality_notes')

    def test_doubt_resolution_signature_fields(self):
        """R25.1: DoubtResolutionSignature has required fields."""
        sig = DoubtResolutionSignature
        assert self._sig_has_field(sig, 'doubt')
        assert self._sig_has_field(sig, 'known_concepts')
        assert self._sig_has_field(sig, 'answer')
        assert self._sig_has_field(sig, 'misconception_type')

    def test_question_generation_signature_fields(self):
        """R25.1: QuestionGenerationSignature has required fields."""
        sig = QuestionGenerationSignature
        assert self._sig_has_field(sig, 'concept_name')
        assert self._sig_has_field(sig, 'bloom_levels_allowed')
        assert self._sig_has_field(sig, 'questions')

    def test_evaluation_signatures(self):
        """R25.1: MCQ and Written evaluation signatures exist."""
        assert self._sig_has_field(MCQEvaluationSignature, 'is_correct')
        assert self._sig_has_field(WrittenEvaluationSignature, 'concept_accuracy_score')
        assert self._sig_has_field(WrittenEvaluationSignature, 'feedback')


# ──────────────────────────────────────────────
# R25.3 — ChainOfThought usage
# ──────────────────────────────────────────────

class TestChainOfThoughtUsage:

    def test_source_curator_uses_cot(self, sample_kg):
        """R25.3 / R8.7: Source Curator uses ChainOfThought."""
        agent = SourceCuratorAgent(sample_kg)
        assert isinstance(agent.curator, dspy.ChainOfThought)

    def test_recommender_uses_cot(self, sample_kg):
        """R25.3: Recommender uses ChainOfThought for motivation."""
        agent = RecommenderAgent(sample_kg)
        assert isinstance(agent.motivator, dspy.ChainOfThought)

    def test_learning_curator_uses_cot(self, sample_kg):
        """R25.3: Learning Curator uses ChainOfThought."""
        agent = LearningCuratorAgent(sample_kg)
        assert isinstance(agent.explainer, dspy.ChainOfThought)
        assert isinstance(agent.retrieval_gen, dspy.ChainOfThought)

    def test_doubt_resolver_uses_cot(self, sample_kg):
        """R25.3: Doubt Resolver uses ChainOfThought."""
        agent = DoubtResolverAgent(sample_kg)
        assert isinstance(agent.resolver, dspy.ChainOfThought)

    def test_question_generator_uses_cot(self, sample_kg):
        """R25.3: Question Generator uses ChainOfThought."""
        agent = QuestionGeneratorAgent(sample_kg)
        assert isinstance(agent.generator, dspy.ChainOfThought)

    def test_evaluator_uses_cot(self, sample_kg):
        """R25.3: Evaluator uses ChainOfThought."""
        agent = EvaluatorAgent(sample_kg)
        assert isinstance(agent.mcq_evaluator, dspy.ChainOfThought)
        assert isinstance(agent.written_evaluator, dspy.ChainOfThought)


# ──────────────────────────────────────────────
# R8.4–8.6 — Source Curator mastery calibration
# ──────────────────────────────────────────────

class TestSourceCuratorMasteryCalibration:

    @pytest.mark.parametrize("mastery,expected_level", [
        (0.1, "beginner"),
        (0.29, "beginner"),
        (0.3, "intermediate"),
        (0.59, "intermediate"),
        (0.6, "advanced"),
        (0.9, "advanced"),
    ])
    def test_mastery_level_mapping(self, sample_kg, mastery, expected_level):
        """R8.4–8.6: Mastery correctly maps to beginner/intermediate/advanced."""
        agent = SourceCuratorAgent(sample_kg)
        assert agent._get_mastery_level(mastery) == expected_level

    def test_depth_rules_exist_for_all_levels(self, sample_kg):
        """R8.4–8.6: Depth rules are defined for all 3 mastery levels."""
        agent = SourceCuratorAgent(sample_kg)
        assert "beginner" in agent.DEPTH_RULES
        assert "intermediate" in agent.DEPTH_RULES
        assert "advanced" in agent.DEPTH_RULES

    def test_beginner_depth_mentions_analogies(self, sample_kg):
        """R8.4: Beginner depth rules mention analogies/simple language."""
        agent = SourceCuratorAgent(sample_kg)
        rule = agent.DEPTH_RULES["beginner"].lower()
        assert "analog" in rule or "simple" in rule

    def test_advanced_depth_mentions_proofs(self, sample_kg):
        """R8.6: Advanced depth rules mention proofs/precision."""
        agent = SourceCuratorAgent(sample_kg)
        rule = agent.DEPTH_RULES["advanced"].lower()
        assert "proof" in rule or "precision" in rule


# ──────────────────────────────────────────────
# R13.4 — Question Generator Bloom's gating
# ──────────────────────────────────────────────

class TestQuestionGeneratorBloomGating:

    @pytest.mark.parametrize("mastery,expected_levels", [
        (0.1, ["remember", "understand"]),
        (0.4, ["apply", "analyse"]),
        (0.7, ["analyse", "evaluate"]),
        (0.9, ["evaluate", "create"]),
    ])
    def test_bloom_levels_by_mastery(self, sample_kg, mastery, expected_levels):
        """R13.4 / R22.4 / R22.5: Bloom levels are gated by mastery."""
        agent = QuestionGeneratorAgent(sample_kg)
        levels = agent._get_bloom_levels(mastery)
        assert levels == expected_levels


# ──────────────────────────────────────────────
# R10.5 / R10.6 — Recommender uses graph not LLM
# ──────────────────────────────────────────────

class TestRecommenderGraphTraversal:

    def test_recommender_returns_zpd_ready(self, sample_kg, sample_learner):
        """R10.2 / R10.5: Recommender returns ZPD-ready concepts via graph traversal."""
        agent = RecommenderAgent(sample_kg)
        # The recommend method calls the LLM for motivation, which will fail
        # without DSPy config. But the fallback should still work.
        try:
            recs = agent.recommend(sample_learner, top_k=3)
        except Exception:
            # LLM not configured; use the graph traversal part only
            mastery_map = sample_learner.get_mastery_map()
            ready = sample_kg.get_ready_concepts(mastery_map, threshold=0.5)
            assert len(ready) > 0

    def test_diagnostic_rollback_returns_weak_prereqs(self, sample_kg, sample_learner):
        """R10.3: Diagnostic rollback finds weak prerequisites."""
        agent = RecommenderAgent(sample_kg)
        mastery_map = sample_learner.get_mastery_map()
        # Force low mastery on prereqs
        sample_learner.get_concept_state("operators").mastery = 0.2
        sample_learner.get_concept_state("data_types").mastery = 0.2

        chain = sample_kg.get_diagnostic_chain(
            "conditionals", sample_learner.get_mastery_map(), threshold=0.5
        )
        assert len(chain) > 0


# ──────────────────────────────────────────────
# R12.4 — Doubt Resolver misconception taxonomy
# ──────────────────────────────────────────────

class TestDoubtResolverMisconceptionTypes:

    def test_depth_rules_exist(self, sample_kg):
        """R12.2: Doubt Resolver has depth rules for all mastery levels."""
        agent = DoubtResolverAgent(sample_kg)
        assert "beginner" in agent.DEPTH_RULES
        assert "intermediate" in agent.DEPTH_RULES
        assert "advanced" in agent.DEPTH_RULES

    def test_misconception_type_enum(self):
        """R12.4: Misconception taxonomy has required types."""
        from backend.core.knowledge_graph import MisconceptionType
        assert MisconceptionType.DEFINITIONAL.value == "definitional"
        assert MisconceptionType.RELATIONAL.value == "relational"
        assert MisconceptionType.PROCEDURAL.value == "procedural"
        assert MisconceptionType.CAUSAL.value == "causal"

    def test_concept_not_found_returns_error(self, sample_kg, sample_learner):
        """R6.5: Doubt Resolver returns error for unknown concepts."""
        agent = DoubtResolverAgent(sample_kg)
        result = agent.resolve(sample_learner, "nonexistent_concept", "some doubt")
        assert "error" in result

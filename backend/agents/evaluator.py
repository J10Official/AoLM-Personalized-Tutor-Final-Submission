"""
Evaluator Agent — Agent 6 in the architecture.

Scores learner answers using an expanded rubric (10 points),
provides qualitative feedback, and measures response time as confidence proxy.
"""

import json
import dspy
from backend.core.knowledge_graph import KnowledgeGraph
from backend.core.learner_model import LearnerModel


class MCQEvaluationSignature(dspy.Signature):
    """Evaluate an MCQ answer."""
    question: str = dspy.InputField()
    correct_answer: str = dspy.InputField()
    student_answer: str = dspy.InputField()

    is_correct: bool = dspy.OutputField(desc="Whether the student's answer matches the correct answer")
    feedback: str = dspy.OutputField(desc="Brief feedback explaining why the answer is correct or incorrect")


class WrittenEvaluationSignature(dspy.Signature):
    """Evaluate a written answer using an expanded rubric."""
    question: str = dspy.InputField()
    correct_answer: str = dspy.InputField()
    rubric: str = dspy.InputField()
    student_answer: str = dspy.InputField()
    concept_name: str = dspy.InputField()

    concept_accuracy_score: int = dspy.OutputField(desc="Score 0-3: Does the answer demonstrate understanding of the core concept?")
    reasoning_score: int = dspy.OutputField(desc="Score 0-2: Is the reasoning chain valid and complete?")
    example_score: int = dspy.OutputField(desc="Score 0-2: Are examples relevant and correctly applied?")
    precision_score: int = dspy.OutputField(desc="Score 0-1: Are technical terms used correctly?")
    connection_score: int = dspy.OutputField(desc="Score 0-2: Does the answer link to related concepts?")
    feedback: str = dspy.OutputField(desc="Detailed qualitative feedback in Markdown. Structure with: **Strengths**, **Areas to Improve**, and **Specific Misconceptions** (if any). Use bullet points for clarity.")


class EvaluatorAgent:
    """Evaluates learner answers with expanded rubric and response-time tracking."""

    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.mcq_evaluator = dspy.ChainOfThought(MCQEvaluationSignature)
        self.written_evaluator = dspy.ChainOfThought(WrittenEvaluationSignature)
        # Load few-shot examples for better output quality
        try:
            from backend.agents.fewshot_examples import get_all_examples
            examples = get_all_examples()
            self.mcq_evaluator.demos = examples.get("evaluator_mcq", [])
            self.written_evaluator.demos = examples.get("evaluator_written", [])
        except Exception:
            pass

    def evaluate(
        self,
        learner: LearnerModel,
        concept_id: str,
        question: dict,
        student_answer: str,
        response_time: float
    ) -> dict:
        """
        Evaluate a student answer and return scores + feedback.

        Args:
            learner: Learner model
            concept_id: Concept being tested
            question: Question dict with 'question', 'type', 'correct_answer', etc.
            student_answer: The learner's answer
            response_time: Time taken in seconds (confidence proxy)
        """
        q_type = question.get("type", "written")
        q_text = question.get("question", "")
        correct = question.get("correct_answer", "")
        rubric = question.get("rubric", "")
        concept = self.kg.get_concept(concept_id)
        concept_name = concept.name if concept else concept_id

        if q_type == "mcq":
            return self._evaluate_mcq(
                learner, concept_id, q_text, correct, student_answer, response_time
            )
        else:
            return self._evaluate_written(
                learner, concept_id, concept_name, q_text, correct,
                rubric, student_answer, response_time
            )

    def _evaluate_mcq(self, learner, concept_id, question, correct, answer, response_time):
        try:
            result = self.mcq_evaluator(
                question=question,
                correct_answer=correct,
                student_answer=answer
            )
            is_correct = result.is_correct
            feedback = result.feedback
        except Exception:
            is_correct = answer.strip().lower() == correct.strip().lower()
            feedback = "Correct!" if is_correct else f"The correct answer was: {correct}"

        score = 1.0 if is_correct else 0.0

        return {
            "concept_id": concept_id,
            "question_type": "mcq",
            "is_correct": is_correct,
            "score": score,
            "max_score": 1.0,
            "normalised_score": score,
            "feedback": feedback,
            "response_time": response_time,
            "score_breakdown": {"correct": is_correct}
        }

    def _evaluate_written(self, learner, concept_id, concept_name, question, correct, rubric, answer, response_time):
        try:
            result = self.written_evaluator(
                question=question,
                correct_answer=correct,
                rubric=rubric or "Evaluate for accuracy, reasoning, examples, precision, and connections.",
                student_answer=answer,
                concept_name=concept_name
            )
            breakdown = {
                "concept_accuracy": int(result.concept_accuracy_score),
                "reasoning": int(result.reasoning_score),
                "examples": int(result.example_score),
                "precision": int(result.precision_score),
                "connections": int(result.connection_score),
            }
            total = sum(breakdown.values())
            feedback = result.feedback
        except Exception as e:
            breakdown = {"concept_accuracy": 1, "reasoning": 1, "examples": 0, "precision": 0, "connections": 0}
            total = 2
            feedback = f"Auto-evaluation: partial credit given. ({e})"

        normalised = total / 10.0
        is_correct = normalised >= 0.5

        return {
            "concept_id": concept_id,
            "question_type": "written",
            "is_correct": is_correct,
            "score": total,
            "max_score": 10,
            "normalised_score": normalised,
            "feedback": feedback,
            "response_time": response_time,
            "score_breakdown": breakdown
        }

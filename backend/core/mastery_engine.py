"""
Mastery Engine — Agent 7 in the architecture.

Implements the hybrid BKT + Forgetting Curve + Response-Time Calibration
mastery computation. Separated from the Evaluator for modularity.
"""

import math
from datetime import datetime, timezone
from backend.core.learner_model import LearnerModel, ConceptState
from backend.core.knowledge_graph import KnowledgeGraph


class MasteryEngine:
    """
    Computes and updates learner mastery using a psychologically-grounded
    composite formula combining:
    1. Bayesian Knowledge Tracing (guess/slip accounting)
    2. Ebbinghaus forgetting curve (time decay)
    3. Response-time confidence proxy
    4. Concept difficulty weighting

    Slides formula reference:
        M_effective = M_base × e^(-t/S)          → compute_forgetting_decay()
        M_new = 0.3 × eval_score + 0.7 × M_old   → simplified version

    Our implementation is a SUPERSET of the slides formula:
        Step 1: BKT Bayesian update (accounts for guess/slip probabilities)
        Step 2: Blend BKT with score-based EMA: 0.7 × m_bkt + 0.3 × (0.4 × score + 0.6 × M_old)
                This generalises the slides formula while adding BKT signal
        Step 3: Apply Ebbinghaus decay: M_blended × e^(-t/S)
        Step 4: Response-time confidence calibration
    """

    # BKT parameters (can be tuned from real data later)
    P_SLIP = 0.1        # P(incorrect | mastered)
    P_GUESS = 0.2       # P(correct | not mastered)
    P_LEARN = 0.15      # P(transition to mastered per interaction)

    # Forgetting curve base strength in days
    S_BASE = 7.0

    def __init__(self, knowledge_graph: KnowledgeGraph, ablation_no_kg: bool = False):
        self.kg = knowledge_graph
        self.ablation_no_kg = ablation_no_kg

    def bayesian_update(self, prior_mastery: float, correct: bool) -> float:
        """
        BKT-inspired Bayesian update of mastery given an observation.
        
        P(mastered | correct) = P(correct | mastered) * P(mastered) / P(correct)
        P(mastered | incorrect) = P(incorrect | mastered) * P(mastered) / P(incorrect)
        """
        p_m = prior_mastery
        
        if correct:
            p_correct_given_m = 1.0 - self.P_SLIP
            p_correct_given_not_m = self.P_GUESS
            p_correct = p_correct_given_m * p_m + p_correct_given_not_m * (1 - p_m)
            if p_correct == 0:
                return p_m
            posterior = (p_correct_given_m * p_m) / p_correct
        else:
            p_incorrect_given_m = self.P_SLIP
            p_incorrect_given_not_m = 1.0 - self.P_GUESS
            p_incorrect = p_incorrect_given_m * p_m + p_incorrect_given_not_m * (1 - p_m)
            if p_incorrect == 0:
                return p_m
            posterior = (p_incorrect_given_m * p_m) / p_incorrect

        # Apply learning transition
        posterior = posterior + (1 - posterior) * self.P_LEARN
        return max(0.0, min(1.0, posterior))

    def compute_forgetting_decay(self, concept_state: ConceptState) -> float:
        """
        Apply Ebbinghaus-style exponential decay based on time since last review.
        
        M_effective = M_base * e^(-t/S)
        
        S (strength) grows with successful retrievals and connections.
        """
        if concept_state.last_reviewed is None:
            return 1.0  # No decay if never reviewed

        last_review = datetime.fromisoformat(concept_state.last_reviewed)
        now = datetime.now(timezone.utc)
        days_elapsed = (now - last_review).total_seconds() / 86400.0

        # Adaptive strength: grows with successful practice and connections
        S = self.S_BASE
        S *= (1.0 + 0.5 * concept_state.successful_retrievals)

        # Add connection bonus if concept is in knowledge graph (skip in ablation)
        if not self.ablation_no_kg:
            concept = self.kg.get_concept(concept_state.concept_id)
            if concept:
                connection_count = self.kg.get_connection_count(concept_state.concept_id)
                S *= (1.0 + 0.3 * connection_count)

        decay_factor = math.exp(-days_elapsed / S)
        return max(0.0, min(1.0, decay_factor))

    def compute_confidence_factor(self, concept_state: ConceptState) -> float:
        """
        Derive confidence factor from response time (proxy for self-confidence).
        
        confidence_factor = response_time_confidence * calibration_accuracy
        """
        rt_confidence = concept_state.confidence_from_response_time
        calibration = concept_state.calibration_accuracy
        return rt_confidence * calibration

    def update_mastery(
        self,
        learner: LearnerModel,
        concept_id: str,
        score: float,
        correct: bool,
        response_time: float,
    ) -> float:
        """
        Full mastery update pipeline with streak acceleration and difficulty weighting.

        Args:
            learner: The learner model to update
            concept_id: Which concept was tested
            score: Normalised score (0.0 to 1.0)
            correct: Whether the answer was correct (for BKT)
            response_time: Time taken in seconds (confidence proxy)

        Returns:
            New mastery value
        """
        cs = learner.get_concept_state(concept_id)
        old_mastery = cs.mastery

        # Step 1: BKT update (accounts for guess/slip)
        m_bkt = self.bayesian_update(cs.mastery, correct)

        # Step 2: Blend BKT with score-based EMA for richer signal
        # BKT is binary (correct/incorrect); score gives gradation
        m_blended = 0.7 * m_bkt + 0.3 * (0.4 * score + 0.6 * cs.mastery)

        # Step 3: Streak-based momentum
        # Consecutive correct answers accelerate mastery gain
        if correct:
            streak = getattr(cs, '_correct_streak', 0) + 1
            cs._correct_streak = streak
            # Streak bonus: diminishing returns, max ~15% boost at 5+ streak
            streak_bonus = min(0.15, 0.03 * streak)
            m_blended = min(1.0, m_blended + streak_bonus)
        else:
            cs._correct_streak = 0

        # Step 4: Difficulty-weighted scoring
        # Harder concepts yield slightly more mastery per correct answer
        concept = self.kg.get_concept(concept_id)
        if concept and correct:
            diff_bonus = concept.difficulty * 0.05  # max 5% bonus for hardest concepts
            m_blended = min(1.0, m_blended + diff_bonus)

        # Step 5: Apply forgetting curve decay
        decay = self.compute_forgetting_decay(cs)
        m_decayed = m_blended * decay

        # Step 6: Response-time confidence calibration
        # Update running average response time
        cs.total_attempts += 1
        if correct:
            cs.correct_attempts += 1
            cs.successful_retrievals += 1
        cs.avg_response_time = (
            (cs.avg_response_time * (cs.total_attempts - 1) + response_time)
            / cs.total_attempts
        )

        conf_factor = self.compute_confidence_factor(cs)
        # Confidence modulates mastery but floor at 0.85 to avoid excessive suppression
        m_calibrated = m_decayed * (0.85 + 0.15 * conf_factor)

        # Clamp to [0, 1]
        new_mastery = max(0.0, min(1.0, m_calibrated))

        # Update concept state
        cs.mastery = new_mastery
        cs.mastery_history.append(round(new_mastery, 4))
        cs.last_reviewed = datetime.now(timezone.utc).isoformat()

        return new_mastery

    def apply_prerequisite_penalty(
        self,
        learner: LearnerModel,
        failed_concept_id: str,
        penalty: float = 0.05,
        score: float = 0.0,
    ) -> list[str]:
        """
        When a learner fails a concept, apply a proportional mastery penalty
        to its prerequisites — they may not be as solid as we thought.

        Penalty is proportional to how badly the student scored:
        - score = 0.0 → full penalty
        - score = 0.4 → 60% of penalty
        - score >= 0.5 → no penalty (they partially know it)

        Returns list of concept IDs that were penalised.
        """
        concept = self.kg.get_concept(failed_concept_id)
        if not concept:
            return []

        # Scale penalty by how far below passing threshold (0.5)
        deficit = max(0.0, 0.5 - score)
        scaled_penalty = penalty * (deficit / 0.5)  # 0 at score=0.5, full at score=0

        if scaled_penalty < 0.005:
            return []  # Negligible, skip

        penalised = []
        for prereq_id in concept.prerequisites:
            cs = learner.get_concept_state(prereq_id)
            cs.mastery = max(0.0, cs.mastery - scaled_penalty)
            cs.mastery_history.append(round(cs.mastery, 4))
            penalised.append(prereq_id)

        return penalised

    def get_concepts_needing_review(
        self, learner: LearnerModel, threshold: float = 0.6
    ) -> list[tuple[str, float]]:
        """
        Find concepts whose effective mastery has decayed below threshold.
        Returns list of (concept_id, effective_mastery) sorted by urgency.
        """
        needs_review = []
        for cid, cs in learner.concepts.items():
            if cs.mastery > 0.3:  # Only review concepts we've actually learned
                decay = self.compute_forgetting_decay(cs)
                effective = cs.mastery * decay
                if effective < threshold:
                    needs_review.append((cid, effective))

        needs_review.sort(key=lambda x: x[1])  # Most urgent first
        return needs_review

"""
Recommender Agent — Agent 1 in the architecture.

Traverses the knowledge graph to recommend the next concept for the learner
based on ZPD targeting. Uses pure graph traversal (no LLM) for reliability,
with LLM only for generating motivational context.

Key features (per slides):
- Selects concepts where prerequisites are mastered (>= 0.5 threshold)
- Diagnostic rollback: if learner fails, recursively traverse prerequisites
  to find the deepest weak concept and trigger quizzes
- Fallback: if no ZPD-ready concepts, recommend from global concept graph
"""

import random
import dspy
from backend.core.knowledge_graph import KnowledgeGraph
from backend.core.learner_model import LearnerModel


class MotivationSignature(dspy.Signature):
    """Generate a short motivational message explaining why a learner should study a concept next."""
    concept_name: str = dspy.InputField(desc="Name of the recommended concept")
    concept_description: str = dspy.InputField(desc="Description of the concept")
    prerequisites_mastered: str = dspy.InputField(desc="Comma-separated list of mastered prerequisite names")
    learner_level: str = dspy.InputField(desc="beginner, intermediate, or advanced")
    motivation: str = dspy.OutputField(desc="A 2-3 sentence motivational explanation of why to learn this concept now and how it connects to what the learner already knows")


class RecommenderAgent:
    """
    Recommends the next concept(s) for a learner using ZPD-based graph traversal.
    
    Logic:
    1. Find concepts where ALL prerequisites are mastered (>= 0.5 threshold per slides)
    2. Filter out already-mastered concepts
    3. Sort by readiness_score = min(prereq_masteries) × concept_centrality
    4. If learner recently failed, do diagnostic rollback via recursive prerequisite traversal
    5. If no ZPD-ready enrolled concepts, fallback to random available concepts from global graph
    """

    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.motivator = dspy.ChainOfThought(MotivationSignature)

    def recommend(
        self,
        learner: LearnerModel,
        top_k: int = 3,
        mastery_threshold: float = 0.5,
        failed_concept_id: str = None
    ) -> list[dict]:
        """
        Get top-K recommended concepts for the learner.

        Args:
            learner: The learner model
            top_k: Number of recommendations to return
            mastery_threshold: Min mastery for prerequisites to be considered 'met'
                               (0.5 per slides: "mastered prereqs greater than 0.5")
            failed_concept_id: If set, triggers diagnostic rollback

        Returns:
            List of dicts with concept info, readiness score, and motivation
        """
        mastery_map = learner.get_mastery_map()

        # Diagnostic rollback: if learner failed, recursively find weak prerequisites
        if failed_concept_id:
            return self._diagnostic_rollback(learner, failed_concept_id, mastery_map, mastery_threshold)

        # Find ZPD-ready concepts from enrolled courses
        enrolled_ids = set(learner.concepts.keys())
        ready_ids = self.kg.get_ready_concepts(mastery_map, mastery_threshold)
        ready_ids = [cid for cid in ready_ids if cid in enrolled_ids]

        if not ready_ids:
            # Fallback 1: lowest-difficulty unmastered enrolled concepts
            all_concepts = self.kg.topological_order()
            ready_ids = [
                cid for cid in all_concepts
                if cid in enrolled_ids and mastery_map.get(cid, 0.0) < 0.85
            ][:top_k]

        if not ready_ids:
            # Fallback 2: recommend random available concepts from GLOBAL graph
            # (concepts the user is NOT enrolled in — encourage exploration)
            return self._recommend_from_global(learner, top_k, mastery_map)

        # Score and sort
        scored = []
        for cid in ready_ids:
            concept = self.kg.get_concept(cid)
            prereq_masteries = [
                mastery_map.get(pid, 0.0) for pid in concept.prerequisites
            ]
            min_prereq = min(prereq_masteries) if prereq_masteries else 1.0
            centrality = self.kg.concept_centrality(cid)
            current_mastery = mastery_map.get(cid, 0.0)

            # Higher score = more ready + more central + more room to grow
            readiness = min_prereq * (1 + centrality) * (1 - current_mastery)
            scored.append((cid, readiness))

        scored.sort(key=lambda x: x[1], reverse=True)
        top_concepts = scored[:top_k]

        # Build recommendations
        recommendations = []
        for cid, readiness in top_concepts:
            concept = self.kg.get_concept(cid)
            mastered_prereqs = [
                self.kg.get_concept(pid).name
                for pid in concept.prerequisites
                if mastery_map.get(pid, 0.0) >= mastery_threshold
                and self.kg.get_concept(pid)
            ]

            level = "beginner"
            m = mastery_map.get(cid, 0.0)
            if m >= 0.6:
                level = "advanced"
            elif m >= 0.3:
                level = "intermediate"

            # Generate motivation via LLM
            try:
                result = self.motivator(
                    concept_name=concept.name,
                    concept_description=concept.description,
                    prerequisites_mastered=", ".join(mastered_prereqs) if mastered_prereqs else "none yet",
                    learner_level=level
                )
                motivation = result.motivation
            except Exception:
                motivation = f"You're ready to learn {concept.name}! Your prerequisites are solid."

            recommendations.append({
                "concept_id": cid,
                "concept_name": concept.name,
                "description": concept.description,
                "readiness_score": round(readiness, 3),
                "difficulty": concept.difficulty,
                "current_mastery": mastery_map.get(cid, 0.0),
                "reason": "zpd_ready",
                "motivation": motivation,
                "prerequisites": concept.prerequisites,
                "bloom_ceiling": concept.bloom_ceiling.value
            })

        return recommendations

    def _diagnostic_rollback(
        self, learner: LearnerModel, failed_concept_id: str,
        mastery_map: dict, mastery_threshold: float
    ) -> list[dict]:
        """
        Diagnostic rollback: recursively traverse prerequisites to find the
        deepest weak concepts that need review before the learner can retry.
        Triggers quiz recommendations for those prerequisites.
        """
        # Get the full diagnostic chain (ordered deepest-first)
        chain = self.kg.get_diagnostic_chain(
            failed_concept_id, mastery_map, threshold=mastery_threshold
        )

        if not chain:
            # No weak prerequisites found — recommend the weakest single one
            weakest = self.kg.get_weakest_prerequisite(failed_concept_id, mastery_map)
            if weakest and mastery_map.get(weakest, 0.0) < mastery_threshold:
                chain = [weakest]
            else:
                # Nothing to rollback to — just re-recommend the failed concept
                concept = self.kg.get_concept(failed_concept_id)
                if concept:
                    return [{
                        "concept_id": failed_concept_id,
                        "concept_name": concept.name,
                        "readiness_score": 0.0,
                        "reason": "retry",
                        "motivation": f"Try studying '{concept.name}' again — practice makes progress!",
                        "difficulty": concept.difficulty,
                        "diagnostic_chain": [],
                    }]
                return []

        # Build recommendations from the diagnostic chain
        recommendations = []
        for cid in chain:
            concept = self.kg.get_concept(cid)
            if not concept:
                continue
            recommendations.append({
                "concept_id": cid,
                "concept_name": concept.name,
                "readiness_score": 0.0,
                "reason": "diagnostic_rollback",
                "motivation": f"Before mastering what you struggled with, let's strengthen your understanding of '{concept.name}' — it's a key prerequisite.",
                "difficulty": concept.difficulty,
                "current_mastery": mastery_map.get(cid, 0.0),
                "diagnostic_chain": chain,
            })

        return recommendations

    def _recommend_from_global(
        self, learner: LearnerModel, top_k: int, mastery_map: dict
    ) -> list[dict]:
        """
        Fallback: when no enrolled ZPD-ready concepts exist, recommend random
        available concepts from the global concept graph that the learner
        hasn't encountered yet. Per slides: "if there are no such course
        just show any random available course from global concept."
        """
        enrolled_ids = set(learner.concepts.keys())
        global_candidates = [
            cid for cid in self.kg.concepts.keys()
            if cid not in enrolled_ids
        ]

        if not global_candidates:
            return []

        # Pick random concepts, preferring ones with fewer prerequisites
        random.shuffle(global_candidates)
        selected = global_candidates[:top_k]

        recommendations = []
        for cid in selected:
            concept = self.kg.get_concept(cid)
            if not concept:
                continue

            # Find which course this concept belongs to
            course_name = None
            for course in self.kg.courses:
                if cid in course.concept_ids:
                    course_name = course.course_name
                    break

            recommendations.append({
                "concept_id": cid,
                "concept_name": concept.name,
                "description": concept.description,
                "readiness_score": 0.0,
                "difficulty": concept.difficulty,
                "current_mastery": 0.0,
                "reason": "global_explore",
                "motivation": f"Explore something new! '{concept.name}' from {course_name or 'the knowledge base'} could broaden your understanding.",
                "course_name": course_name,
                "bloom_ceiling": concept.bloom_ceiling.value
            })

        return recommendations

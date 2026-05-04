"""
Learning Curator Agent — Agent 3 in the architecture.

Produces adaptive explanations calibrated to the learner's mastery level,
anticipates doubts, and generates retrieval questions on prerequisites
(Bjork's testing effect — retrieval-first learning).

Contexts used (per slides):
1. Lecture Transcript (via source_material from Source Curator)
2. Doubts by any user (global doubts from knowledge graph)
3. User Personal Graph (mastery map + known concept descriptions)

Adaptive Depth Rules (per slides):
- Beginner (M < 0.3): analogies, first principles
- Intermediate (0.3 ≤ M < 0.6): intuition + precision
- Advanced (M ≥ 0.6): math, proofs
"""

import json
import os
import dspy
from backend.core.knowledge_graph import KnowledgeGraph, BloomLevel
from backend.core.learner_model import LearnerModel
from backend.agents.utils import parse_json_response


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load_transcript_context(concept_id: str) -> str:
    """Load transcript excerpt for a concept from concept_sources.json."""
    sources_path = os.path.join(DATA_DIR, "raw", "concept_sources.json")
    if os.path.exists(sources_path):
        with open(sources_path, "r") as f:
            sources = json.load(f)
        source = sources.get(concept_id, {})
        return source.get("transcript_excerpt", "")
    return ""


class AdaptiveExplanationSignature(dspy.Signature):
    """Generate an adaptive explanation of a concept tailored to the learner's level, grounded in the source material and personal context."""
    concept_name: str = dspy.InputField()
    concept_description: str = dspy.InputField()
    mastery_level: str = dspy.InputField(desc="beginner, intermediate, or advanced")
    depth_instructions: str = dspy.InputField(desc="Specific depth/style rules for this mastery level")
    known_concepts: str = dspy.InputField(desc="Concepts the learner already knows, comma-separated")
    source_material: str = dspy.InputField(desc="Curated source content (lecture transcript + merged sources) to base the explanation on")
    global_doubts: str = dspy.InputField(desc="Common doubts other learners have had about this concept (JSON array)")
    user_personal_graph: str = dspy.InputField(desc="Learner's personal knowledge state: their mastery levels and known concepts (JSON)")
    
    explanation: str = dspy.OutputField(desc="Adaptive explanation of the concept, calibrated to the learner's level. Format in clean Markdown with **bold** for key terms, `code` for technical notation, and bullet/numbered lists for steps. For beginners: use analogies, first principles, simple language. For intermediate: mix intuition + technical precision. For advanced: full precision, proofs, math (use LaTeX $...$ for inline math, $$...$$ for display equations). Ground your explanation in the source material. DO NOT include unnecessary introductory fluff. Start directly with the core technical explanation.")
    anticipated_doubts: str = dspy.OutputField(desc="3 doubts the learner is likely to have, as a JSON array of strings. No markdown fences around the JSON. Consider the global doubts from other learners when generating these.")
    key_takeaways: str = dspy.OutputField(desc="3-5 key takeaways from the explanation, as a JSON array of strings. No markdown fences around the JSON.")


class RetrievalQuestionSignature(dspy.Signature):
    """Generate retrieval practice questions on prerequisite concepts to activate prior knowledge."""
    prerequisite_concepts: str = dspy.InputField(desc="Names and descriptions of prerequisite concepts, as JSON")
    target_concept: str = dspy.InputField(desc="The concept the learner is about to learn")
    
    retrieval_questions: str = dspy.OutputField(desc="3 retrieval questions on prerequisites that activate prior knowledge needed for the target concept. Format as JSON array of objects with 'question', 'concept', and 'expected_answer' fields.")


class LearningCuratorAgent:
    """
    Creates adaptive learning sessions with retrieval-first design.
    
    Flow:
    1. Generate retrieval questions on prerequisites (Bjork's testing effect)
    2. Produce adaptive explanation calibrated to mastery level
    3. Anticipate doubts the learner might have
    
    Uses three contexts per slides:
    1. Lecture Transcript (source_material)
    2. Global Doubts (from other users via knowledge graph)
    3. User Personal Graph (mastery map + concept descriptions)
    """

    DEPTH_RULES = {
        "beginner": (
            "Beginner level (mastery < 0.3): Use analogies and first principles. "
            "Explain concepts using everyday language and real-world metaphors. "
            "Start from the 'why' before the 'what'. Define every technical term. "
            "Focus on building intuition, not precision."
        ),
        "intermediate": (
            "Intermediate level (mastery 0.3-0.6): Mix intuition with technical precision. "
            "You can use technical terms with brief clarifications. "
            "Include concrete examples and connect to prerequisites the learner knows. "
            "Balance accessibility with accuracy."
        ),
        "advanced": (
            "Advanced level (mastery >= 0.6): Full technical precision. "
            "Use formal definitions, mathematical notation, and proofs where applicable. "
            "Include edge cases, subtle distinctions, and advanced implications. "
            "Assume solid prerequisite knowledge."
        ),
    }

    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.explainer = dspy.ChainOfThought(AdaptiveExplanationSignature)
        self.retrieval_gen = dspy.ChainOfThought(RetrievalQuestionSignature)
        # Load few-shot examples for better output quality
        try:
            from backend.agents.fewshot_examples import get_all_examples
            examples = get_all_examples()
            self.explainer.demos = examples.get("learning_curator", [])
            self.retrieval_gen.demos = examples.get("retrieval_questions", [])
        except Exception:
            pass

    def _get_mastery_level(self, mastery: float) -> str:
        if mastery < 0.3:
            return "beginner"
        elif mastery < 0.6:
            return "intermediate"
        else:
            return "advanced"

    def create_session(
        self,
        learner: LearnerModel,
        concept_id: str,
        source_material: str = ""
    ) -> dict:
        """
        Create a complete learning session for a concept.

        Returns dict with:
        - retrieval_questions: Questions on prerequisites (asked BEFORE explanation)
        - explanation: Adaptive explanation
        - anticipated_doubts: Likely learner doubts
        - key_takeaways: Summary points
        - bloom_level: Target Bloom's level for this session
        """
        concept = self.kg.get_concept(concept_id)
        if not concept:
            return {"error": f"Concept '{concept_id}' not found"}

        cs = learner.get_concept_state(concept_id)
        mastery = cs.mastery
        level = self._get_mastery_level(mastery)
        depth_instructions = self.DEPTH_RULES[level]

        known = learner.get_known_concepts()
        known_names = [
            self.kg.get_concept(cid).name
            for cid in known if self.kg.get_concept(cid)
        ]

        # --- Context 1: Lecture Transcript ---
        # If no source material provided by Source Curator, load transcript directly
        if not source_material:
            transcript = _load_transcript_context(concept_id)
            source_material = transcript if transcript else concept.description

        # --- Context 2: Global Doubts from other users ---
        global_doubts = getattr(concept, "global_doubts", [])

        # --- Context 3: User Personal Graph ---
        personal_graph = {}
        for cid in learner.concepts:
            c = self.kg.get_concept(cid)
            if c:
                c_state = learner.get_concept_state(cid)
                personal_graph[cid] = {
                    "name": c.name,
                    "mastery": round(c_state.mastery, 2),
                    "doubts_count": len(c_state.doubts),
                }

        # Step 1: Generate retrieval questions on prerequisites
        prereqs = self.kg.get_prerequisites(concept_id)
        retrieval_questions = []
        if prereqs:
            prereq_info = json.dumps([
                {"name": p.name, "description": p.description}
                for p in prereqs
            ])
            try:
                rq_result = self.retrieval_gen(
                    prerequisite_concepts=prereq_info,
                    target_concept=concept.name
                )
                retrieval_questions = json.loads(rq_result.retrieval_questions)
            except Exception:
                retrieval_questions = []

        # Step 2: Generate adaptive explanation with all 3 contexts
        try:
            result = self.explainer(
                concept_name=concept.name,
                concept_description=concept.description,
                mastery_level=level,
                depth_instructions=depth_instructions,
                known_concepts=", ".join(known_names) if known_names else "none",
                source_material=source_material[:15000],
                global_doubts=json.dumps(global_doubts[:5]) if global_doubts else "[]",
                user_personal_graph=json.dumps(personal_graph),
            )
            explanation = result.explanation
            anticipated_doubts = parse_json_response(result.anticipated_doubts, fallback=[])
            key_takeaways = parse_json_response(result.key_takeaways, fallback=[])
        except Exception as e:
            explanation = f"Error generating explanation: {e}"
            anticipated_doubts = []
            key_takeaways = []

        bloom_level = BloomLevel.from_mastery(mastery)

        return {
            "concept_id": concept_id,
            "concept_name": concept.name,
            "mastery_level": level,
            "bloom_level": bloom_level.value,
            "retrieval_questions": retrieval_questions,
            "explanation": explanation,
            "anticipated_doubts": anticipated_doubts,
            "key_takeaways": key_takeaways,
            "difficulty": concept.difficulty,
            "prerequisites": [p.name for p in prereqs]
        }

"""
Question Generator Agent — Agent 5 in the architecture.

Generates Bloom's-level-tagged, interleaved questions that connect
current and past concepts. Includes misconception probes from doubt history.

Contexts used (per slides):
1. Lecture Transcript (from concept_sources.json)
2. Doubts by any user (personal + global doubts)
3. User Personal Graph (mastery map + known concepts)

Adaptive Depth Rules (per slides):
- Low mastery: recall + application
- High mastery: synthesis + analysis
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


class QuestionGenerationSignature(dspy.Signature):
    """Generate assessment questions for a concept, tagged by Bloom's level, using lecture transcript, doubts, and the learner's personal knowledge graph."""
    concept_name: str = dspy.InputField()
    concept_description: str = dspy.InputField()
    transcript_context: str = dspy.InputField(desc="Relevant excerpt from the lecture transcript covering this concept. Use this to create questions grounded in the actual course material.")
    mastery_level: str = dspy.InputField(desc="beginner, intermediate, or advanced")
    depth_instructions: str = dspy.InputField(desc="Specific depth rules for question difficulty at this mastery level")
    bloom_levels_allowed: str = dspy.InputField(desc="Allowed Bloom's levels for questions (comma-separated)")
    known_concepts_for_interleaving: str = dspy.InputField(desc="Previously mastered concepts to interleave with (JSON list)")
    past_doubts: str = dspy.InputField(desc="Learner's past doubts on this concept (JSON list)")
    user_personal_graph: str = dspy.InputField(desc="Learner's personal knowledge state with mastery levels (JSON). Use this to calibrate question difficulty and make connections to concepts the learner knows well.")
    
    questions: str = dspy.OutputField(desc="""Generate exactly 5 questions as a JSON array. Each question object must have:
    - 'question': the question text (DO NOT include transcript text in the question itself, just formulate a clean question)
    - 'type': 'mcq' or 'written'
    - 'bloom_level': one of remember/understand/apply/analyse/evaluate/create
    - 'interleaved_concept': name of the other concept involved (or null)
    - 'pattern': one of 'property_transfer', 'mechanism_contrast', 'failure_mode', 'multi_step', 'analogy_construction', 'misconception_probe'
    - 'options': for MCQ, array of 4 options; for written, null
    - 'correct_answer': the correct answer
    - 'rubric': for written, what a good answer should include
    At least 2 questions must interleave with a previously mastered concept.
    At least 1 question should probe a past misconception if available.""")


class QuestionGeneratorAgent:
    """Generates Bloom's-tagged, interleaved assessment questions with full context."""

    DEPTH_RULES = {
        "beginner": (
            "Beginner (mastery < 0.3): Focus on recall and basic understanding. "
            "Questions should test whether the learner can define terms, identify key ideas, "
            "and explain concepts in simple language. Use remember + understand Bloom's levels."
        ),
        "intermediate": (
            "Intermediate (mastery 0.3-0.6): Focus on application and analysis. "
            "Questions should require applying concepts to new situations, comparing/contrasting, "
            "and explaining mechanisms. Use apply + analyse Bloom's levels."
        ),
        "advanced": (
            "Advanced (mastery >= 0.6): Focus on evaluation and creation. "
            "Questions should require critiquing, designing solutions, synthesising across concepts, "
            "and handling edge cases. Use evaluate + create Bloom's levels."
        ),
    }

    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.generator = dspy.ChainOfThought(QuestionGenerationSignature)
        # Load few-shot examples for better output quality
        try:
            from backend.agents.fewshot_examples import get_all_examples
            examples = get_all_examples()
            self.generator.demos = examples.get("question_generator", [])
        except Exception:
            pass

    def _get_bloom_levels(self, mastery: float) -> list[str]:
        if mastery < 0.3:
            return ["remember", "understand"]
        elif mastery < 0.6:
            return ["apply", "analyse"]
        elif mastery < 0.85:
            return ["analyse", "evaluate"]
        else:
            return ["evaluate", "create"]

    def _get_mastery_level(self, mastery: float) -> str:
        if mastery < 0.3:
            return "beginner"
        elif mastery < 0.6:
            return "intermediate"
        else:
            return "advanced"

    def generate(self, learner: LearnerModel, concept_id: str) -> dict:
        """Generate 5 assessment questions for a concept with full context."""
        concept = self.kg.get_concept(concept_id)
        if not concept:
            return {"error": f"Concept '{concept_id}' not found"}

        cs = learner.get_concept_state(concept_id)
        mastery = cs.mastery

        level = self._get_mastery_level(mastery)
        depth_instructions = self.DEPTH_RULES[level]
        bloom_levels = self._get_bloom_levels(mastery)

        # --- Context 1: Lecture Transcript ---
        transcript_ctx = _load_transcript_context(concept_id)

        # --- Context 2: Doubts (personal + global) ---
        personal_doubts = [d.get("text", "") for d in cs.doubts]
        global_doubts = getattr(concept, "global_doubts", [])
        all_doubts = personal_doubts.copy()
        for gd in global_doubts:
            if gd not in all_doubts:
                all_doubts.append(gd)

        # --- Context 3: User Personal Graph ---
        personal_graph = {}
        mastered = learner.get_mastered_concepts(threshold=0.3)
        interleave_concepts = []
        for mid in mastered:
            if mid != concept_id:
                mc = self.kg.get_concept(mid)
                if mc:
                    interleave_concepts.append({"name": mc.name, "description": mc.description})
                    personal_graph[mid] = {
                        "name": mc.name,
                        "mastery": round(learner.get_concept_state(mid).mastery, 2),
                    }

        try:
            result = self.generator(
                concept_name=concept.name,
                concept_description=concept.description,
                transcript_context=transcript_ctx[:15000] if transcript_ctx else "No transcript available.",
                mastery_level=level,
                depth_instructions=depth_instructions,
                bloom_levels_allowed=", ".join(bloom_levels),
                known_concepts_for_interleaving=json.dumps(interleave_concepts[:5]),
                past_doubts=json.dumps(all_doubts[:5]),
                user_personal_graph=json.dumps(personal_graph),
            )
            
            questions = parse_json_response(result.questions, fallback=None)
            if not questions:
                raise ValueError("Could not parse questions from LLM response")
        except Exception as e:
            questions = [{
                "question": f"Explain the core idea of {concept.name} in your own words.",
                "type": "written",
                "bloom_level": "understand",
                "interleaved_concept": None,
                "pattern": "property_transfer",
                "options": None,
                "correct_answer": concept.description,
                "rubric": "Should demonstrate understanding of the key concept."
            }]

        return {
            "concept_id": concept_id,
            "concept_name": concept.name,
            "mastery_level": level,
            "bloom_levels": bloom_levels,
            "questions": questions
        }

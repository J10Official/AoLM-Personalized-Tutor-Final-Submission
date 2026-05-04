"""
Doubt Resolver Agent — Agent 4 in the architecture.

Answers learner doubts using ONLY their known concepts (constructivist constraint).
Classifies misconceptions into a taxonomy and stores them for future remediation.

Contexts used (per slides):
1. Lecture Transcript (from concept_sources.json)
2. User Personal Graph (known concepts with mastery levels)

Adaptive Depth Rules (per slides):
- Beginner: analogies, first principles
- Intermediate: intuition + precision
- Advanced: math, proofs
"""

import json
import os
import dspy
from backend.core.knowledge_graph import KnowledgeGraph
from backend.core.learner_model import LearnerModel


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


class DoubtResolutionSignature(dspy.Signature):
    """Resolve a learner's doubt using only their known concepts, grounded in the lecture transcript and their personal knowledge graph."""
    doubt: str = dspy.InputField(desc="The learner's doubt or question")
    concept_name: str = dspy.InputField(desc="The concept the doubt is about")
    concept_description: str = dspy.InputField(desc="Description of the concept")
    transcript_context: str = dspy.InputField(desc="Relevant excerpt from the lecture transcript covering this concept. Use this to ground your answer in the actual course material.")
    known_concepts: str = dspy.InputField(desc="Concepts the learner already knows with their mastery levels (JSON list of {name, description, mastery})")
    mastery_level: str = dspy.InputField(desc="Learner's current mastery: beginner, intermediate, or advanced")
    depth_instructions: str = dspy.InputField(desc="Specific depth rules for the answer based on the learner's mastery level")

    answer: str = dspy.OutputField(desc="Clear answer to the doubt using ONLY the learner's known concepts. Format in Markdown: use **bold** for key terms, bullet lists for steps, and LaTeX ($...$) for math where relevant. Do NOT introduce new concepts the learner hasn't seen. Use analogies from their existing knowledge. Ground your answer in the lecture transcript context but DO NOT copy-paste the transcript verbatim.")
    misconception_type: str = dspy.OutputField(desc="Type of misconception: 'definitional', 'relational', 'procedural', 'causal', or 'none'")
    misconception_explanation: str = dspy.OutputField(desc="If a misconception was detected, explain what the learner likely misunderstands. If none, say 'No misconception detected.'")
    follow_up_question: str = dspy.OutputField(desc="A probing follow-up question to check if the learner understood the resolution")


class DoubtResolverAgent:
    """
    Resolves learner doubts with constructivist constraints.
    
    Hard rules:
    - ONLY use concepts the learner has already encountered
    - Classify each doubt by misconception type
    - Store doubts for the Question Generator to create targeted remediation
    - Adapt answer depth to mastery level
    """

    DEPTH_RULES = {
        "beginner": (
            "Beginner level: Answer using simple analogies and first principles. "
            "Avoid jargon. Relate to everyday experiences. "
            "Be patient and build from the most basic understanding."
        ),
        "intermediate": (
            "Intermediate level: Answer with a mix of intuition and technical precision. "
            "You can use some technical terms but clarify them. "
            "Provide concrete examples to illustrate the point."
        ),
        "advanced": (
            "Advanced level: Answer with full technical precision. "
            "Use formal definitions and mathematical reasoning where applicable. "
            "Address subtle edge cases and nuances."
        ),
    }

    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.resolver = dspy.ChainOfThought(DoubtResolutionSignature)
        # Load few-shot examples for better output quality
        try:
            from backend.agents.fewshot_examples import get_all_examples
            examples = get_all_examples()
            self.resolver.demos = examples.get("doubt_resolver", [])
        except Exception:
            pass

    def _get_mastery_level(self, mastery: float) -> str:
        if mastery < 0.3:
            return "beginner"
        elif mastery < 0.6:
            return "intermediate"
        else:
            return "advanced"

    def resolve(self, learner: LearnerModel, concept_id: str, doubt_text: str) -> dict:
        """
        Resolve a doubt and classify any misconceptions.
        """
        concept = self.kg.get_concept(concept_id)
        if not concept:
            return {"error": f"Concept '{concept_id}' not found"}

        # --- Context 1: Lecture Transcript ---
        transcript_ctx = _load_transcript_context(concept_id)

        # --- Context 2: User Personal Graph (known concepts with mastery) ---
        known_ids = learner.get_known_concepts(threshold=0.2)
        known_info = []
        for kid in known_ids:
            kc = self.kg.get_concept(kid)
            if kc:
                k_mastery = learner.get_concept_state(kid).mastery
                known_info.append({
                    "name": kc.name,
                    "description": kc.description,
                    "mastery": round(k_mastery, 2),
                })

        cs = learner.get_concept_state(concept_id)
        mastery = cs.mastery
        level = self._get_mastery_level(mastery)
        depth_instructions = self.DEPTH_RULES[level]

        try:
            result = self.resolver(
                doubt=doubt_text,
                concept_name=concept.name,
                concept_description=concept.description,
                transcript_context=transcript_ctx[:15000] if transcript_ctx else "No transcript available.",
                known_concepts=json.dumps(known_info),
                mastery_level=level,
                depth_instructions=depth_instructions,
            )

            # Store the doubt in the learner model
            cs = learner.get_concept_state(concept_id)
            doubt_record = {
                "text": doubt_text,
                "type": result.misconception_type,
                "resolved": True,
                "resolution": result.answer,
            }
            cs.doubts.append(doubt_record)

            if result.misconception_type != "none":
                cs.misconceptions_detected.append(result.misconception_explanation)

            return {
                "concept_id": concept_id,
                "doubt": doubt_text,
                "answer": result.answer,
                "misconception_type": result.misconception_type,
                "misconception_explanation": result.misconception_explanation,
                "follow_up_question": result.follow_up_question,
                "used_known_concepts": [ki["name"] for ki in known_info[:5]]
            }
        except Exception as e:
            return {
                "concept_id": concept_id,
                "doubt": doubt_text,
                "answer": f"Error resolving doubt: {e}",
                "misconception_type": "none",
                "misconception_explanation": "",
                "follow_up_question": "",
                "used_known_concepts": []
            }

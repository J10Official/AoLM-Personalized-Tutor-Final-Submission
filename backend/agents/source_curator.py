"""
Source Curator Agent — Agent 2 in the architecture (per slides).

Retrieves multiple sources (YouTube transcript, concept descriptions, related
concept information), ranks by quality & mastery fit, and merges the best
ideas into ONE coherent document calibrated to the learner's mastery level.

Mastery-calibrated depth (from slides):
- M < 0.3: Analogies, simple language
- 0.3 ≤ M < 0.6: Mixed intuition + technical
- M ≥ 0.6: Full precision, proofs
"""

import json
import os
import dspy
from backend.core.knowledge_graph import KnowledgeGraph
from backend.core.learner_model import LearnerModel


DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")


def _load_transcript(concept_id: str) -> str:
    """Load transcript for a concept from concept_sources.json."""
    sources_path = os.path.join(DATA_DIR, "raw", "concept_sources.json")
    if os.path.exists(sources_path):
        with open(sources_path, "r") as f:
            sources = json.load(f)
        source = sources.get(concept_id, {})
        return source.get("transcript_excerpt", "")
    return ""


class SourceCurationSignature(dspy.Signature):
    """Curate and merge multiple sources into ONE coherent learning document calibrated to the learner's mastery level."""
    concept_name: str = dspy.InputField(desc="Name of the concept to curate sources for")
    concept_description: str = dspy.InputField(desc="Description of the concept from the knowledge graph")
    lecture_transcript: str = dspy.InputField(desc="Raw transcript excerpt from the lecture covering this concept")
    related_concepts_info: str = dspy.InputField(desc="JSON list of related and prerequisite concept descriptions for context")
    mastery_level: str = dspy.InputField(desc="beginner (<0.3), intermediate (0.3-0.6), or advanced (>=0.6)")
    depth_instructions: str = dspy.InputField(desc="Specific instructions for how deep/technical the curated document should be")

    curated_document: str = dspy.OutputField(desc="A single coherent learning document that merges the best content from all sources. Calibrated to the learner's mastery level. Should be comprehensive but focused. Do NOT include meta-commentary about the curation process.")
    quality_notes: str = dspy.OutputField(desc="Brief notes on source quality and what was prioritised in the curation")


class SourceCuratorAgent:
    """
    Curates and merges learning sources into a mastery-calibrated document.

    Flow:
    1. Gather sources: lecture transcript, concept description, related concepts
    2. Rank by quality and mastery fit
    3. Merge into ONE coherent narrative
    4. Calibrate depth to learner's mastery level
    """

    DEPTH_RULES = {
        "beginner": (
            "The learner is a beginner (mastery < 0.3). "
            "Use analogies, simple language, and first principles. "
            "Avoid jargon unless you immediately define it. "
            "Start with the 'why' before the 'what'. "
            "Use everyday analogies to build intuition."
        ),
        "intermediate": (
            "The learner is intermediate (mastery 0.3-0.6). "
            "Use a mix of intuition and technical precision. "
            "You can use technical terms but provide brief clarifications. "
            "Include concrete examples and connect to prerequisites the learner knows."
        ),
        "advanced": (
            "The learner is advanced (mastery >= 0.6). "
            "Use full technical precision, formal definitions, and mathematical notation where applicable. "
            "Include proofs, edge cases, and subtle distinctions. "
            "Assume the learner is comfortable with all prerequisites."
        ),
    }

    def __init__(self, knowledge_graph: KnowledgeGraph):
        self.kg = knowledge_graph
        self.curator = dspy.ChainOfThought(SourceCurationSignature)
        # Load few-shot examples for better output quality
        try:
            from backend.agents.fewshot_examples import get_all_examples
            examples = get_all_examples()
            self.curator.demos = examples.get("source_curator", [])
        except Exception:
            pass

    def _get_mastery_level(self, mastery: float) -> str:
        if mastery < 0.3:
            return "beginner"
        elif mastery < 0.6:
            return "intermediate"
        else:
            return "advanced"

    def curate(self, learner: LearnerModel, concept_id: str) -> dict:
        """
        Curate sources for a concept, merging into a single mastery-calibrated document.

        Returns:
            dict with 'curated_document', 'quality_notes', 'sources_used', 'mastery_level'
        """
        concept = self.kg.get_concept(concept_id)
        if not concept:
            return {"error": f"Concept '{concept_id}' not found"}

        cs = learner.get_concept_state(concept_id)
        mastery = cs.mastery
        level = self._get_mastery_level(mastery)
        depth_instructions = self.DEPTH_RULES[level]

        # Source 1: Lecture transcript
        transcript = _load_transcript(concept_id)

        # Source 2: Related and prerequisite concept info
        related_info = []
        for pid in concept.prerequisites:
            pc = self.kg.get_concept(pid)
            if pc:
                p_mastery = learner.get_concept_state(pid).mastery
                related_info.append({
                    "name": pc.name,
                    "description": pc.description,
                    "relationship": "prerequisite",
                    "learner_mastery": round(p_mastery, 2),
                })
        for rid in concept.related_concepts:
            rc = self.kg.get_concept(rid)
            if rc:
                r_mastery = learner.get_concept_state(rid).mastery
                related_info.append({
                    "name": rc.name,
                    "description": rc.description,
                    "relationship": "related",
                    "learner_mastery": round(r_mastery, 2),
                })

        try:
            result = self.curator(
                concept_name=concept.name,
                concept_description=concept.description,
                lecture_transcript=transcript[:15000] if transcript else "No transcript available — use the concept description and related concepts to build the document.",
                related_concepts_info=json.dumps(related_info) if related_info else "[]",
                mastery_level=level,
                depth_instructions=depth_instructions,
            )

            return {
                "curated_document": result.curated_document,
                "quality_notes": result.quality_notes,
                "mastery_level": level,
                "sources_used": {
                    "has_transcript": bool(transcript),
                    "related_concepts": len(related_info),
                },
            }
        except Exception as e:
            # Fallback: return transcript + description concatenated
            fallback = concept.description
            if transcript:
                fallback = f"{concept.description}\n\n---\n\nFrom the lecture:\n{transcript[:5000]}"
            return {
                "curated_document": fallback,
                "quality_notes": f"LLM curation failed ({e}); using raw sources.",
                "mastery_level": level,
                "sources_used": {"has_transcript": bool(transcript), "related_concepts": 0},
            }

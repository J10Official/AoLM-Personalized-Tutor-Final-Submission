"""
Human-in-the-Loop Data Flywheel.

Collects real learner interactions (doubts, evaluations, misconceptions),
allows a data engineer to curate and approve high-quality examples, and
exports them as DSPy few-shot examples that agents load automatically.

Storage: JSON files in backend/data/flywheel/
  - interactions.json: all raw collected interactions
  - approved_examples.json: curated, approved examples for few-shot use
"""

import json
import os
import uuid
from datetime import datetime, timezone
from dataclasses import dataclass, field, asdict
from typing import Optional


FLYWHEEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "flywheel")


@dataclass
class Interaction:
    """A single learner interaction captured by the system."""
    id: str
    type: str                     # 'doubt_resolution' | 'evaluation' | 'misconception'
    learner_id: str
    concept_id: str
    concept_name: str
    timestamp: str
    status: str = "pending"       # 'pending' | 'approved' | 'rejected'

    # Doubt-specific fields
    doubt_text: str = ""
    answer_text: str = ""
    misconception_type: str = ""
    misconception_explanation: str = ""
    follow_up_question: str = ""

    # Evaluation-specific fields
    question_text: str = ""
    student_answer: str = ""
    correct_answer: str = ""
    score: float = 0.0
    feedback: str = ""
    bloom_level: str = ""
    question_type: str = ""       # 'mcq' | 'written'

    # Curator notes (added by data engineer)
    curator_notes: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @staticmethod
    def from_dict(d: dict) -> "Interaction":
        return Interaction(**{k: v for k, v in d.items() if k in Interaction.__dataclass_fields__})


class FlywheelStore:
    """
    Manages the Human-in-the-Loop data flywheel.

    Provides:
    - Automatic collection of learner interactions
    - Curation workflow (approve/reject)
    - Export to DSPy few-shot format
    - Aggregate statistics
    """

    def __init__(self, flywheel_dir: str = FLYWHEEL_DIR):
        self.flywheel_dir = flywheel_dir
        os.makedirs(flywheel_dir, exist_ok=True)
        self._interactions_path = os.path.join(flywheel_dir, "interactions.json")
        self._approved_path = os.path.join(flywheel_dir, "approved_examples.json")
        self._interactions: list[Interaction] = []
        self._load()

    def _load(self):
        """Load interactions from disk."""
        if os.path.exists(self._interactions_path):
            with open(self._interactions_path, "r") as f:
                data = json.load(f)
            self._interactions = [Interaction.from_dict(d) for d in data]
        else:
            self._interactions = []

    def _save(self):
        """Persist interactions to disk."""
        with open(self._interactions_path, "w") as f:
            json.dump([i.to_dict() for i in self._interactions], f, indent=2)

    # ──────────────────────────────────────────────
    # Collection — called automatically by agents
    # ──────────────────────────────────────────────

    def collect_doubt(
        self,
        learner_id: str,
        concept_id: str,
        concept_name: str,
        doubt_text: str,
        answer_text: str,
        misconception_type: str = "none",
        misconception_explanation: str = "",
        follow_up_question: str = "",
    ) -> str:
        """
        Record a doubt resolution interaction.
        Returns the interaction ID.
        """
        interaction = Interaction(
            id=str(uuid.uuid4())[:8],
            type="doubt_resolution",
            learner_id=learner_id,
            concept_id=concept_id,
            concept_name=concept_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            doubt_text=doubt_text,
            answer_text=answer_text,
            misconception_type=misconception_type,
            misconception_explanation=misconception_explanation,
            follow_up_question=follow_up_question,
        )
        self._interactions.append(interaction)
        self._save()
        return interaction.id

    def collect_evaluation(
        self,
        learner_id: str,
        concept_id: str,
        concept_name: str,
        question_text: str,
        student_answer: str,
        correct_answer: str,
        score: float,
        feedback: str,
        bloom_level: str = "",
        question_type: str = "written",
    ) -> str:
        """
        Record an evaluation interaction.
        Returns the interaction ID.
        """
        interaction = Interaction(
            id=str(uuid.uuid4())[:8],
            type="evaluation",
            learner_id=learner_id,
            concept_id=concept_id,
            concept_name=concept_name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            question_text=question_text,
            student_answer=student_answer,
            correct_answer=correct_answer,
            score=score,
            feedback=feedback,
            bloom_level=bloom_level,
            question_type=question_type,
        )
        self._interactions.append(interaction)
        self._save()
        return interaction.id

    # ──────────────────────────────────────────────
    # Curation — used by data engineer
    # ──────────────────────────────────────────────

    def get_interactions(
        self,
        filter_type: Optional[str] = None,
        filter_status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> tuple[list[dict], int]:
        """
        Get interactions with optional filtering.
        Returns (list of interaction dicts, total count).
        """
        filtered = self._interactions
        if filter_type:
            filtered = [i for i in filtered if i.type == filter_type]
        if filter_status:
            filtered = [i for i in filtered if i.status == filter_status]

        total = len(filtered)
        # Sort by timestamp descending (newest first)
        filtered = sorted(filtered, key=lambda i: i.timestamp, reverse=True)
        page = filtered[offset:offset + limit]
        return [i.to_dict() for i in page], total

    def approve(self, interaction_id: str, curator_notes: str = "") -> bool:
        """Approve an interaction for use as a few-shot example."""
        for i in self._interactions:
            if i.id == interaction_id:
                i.status = "approved"
                i.curator_notes = curator_notes
                self._save()
                self._export_approved()
                return True
        return False

    def reject(self, interaction_id: str, curator_notes: str = "") -> bool:
        """Reject an interaction."""
        for i in self._interactions:
            if i.id == interaction_id:
                i.status = "rejected"
                i.curator_notes = curator_notes
                self._save()
                self._export_approved()
                return True
        return False

    # ──────────────────────────────────────────────
    # Export — DSPy few-shot examples
    # ──────────────────────────────────────────────

    def _export_approved(self):
        """Export all approved interactions as few-shot examples."""
        approved = [i for i in self._interactions if i.status == "approved"]
        examples = {
            "doubt_resolution": [],
            "evaluation": [],
            "exported_at": datetime.now(timezone.utc).isoformat(),
            "total_approved": len(approved),
        }

        for interaction in approved:
            if interaction.type == "doubt_resolution":
                examples["doubt_resolution"].append({
                    "concept_name": interaction.concept_name,
                    "doubt": interaction.doubt_text,
                    "answer": interaction.answer_text,
                    "misconception_type": interaction.misconception_type,
                    "misconception_explanation": interaction.misconception_explanation,
                    "follow_up_question": interaction.follow_up_question,
                })
            elif interaction.type == "evaluation":
                examples["evaluation"].append({
                    "concept_name": interaction.concept_name,
                    "question": interaction.question_text,
                    "student_answer": interaction.student_answer,
                    "correct_answer": interaction.correct_answer,
                    "score": interaction.score,
                    "feedback": interaction.feedback,
                    "bloom_level": interaction.bloom_level,
                    "question_type": interaction.question_type,
                })

        with open(self._approved_path, "w") as f:
            json.dump(examples, f, indent=2)

    def export_fewshot_examples(self) -> dict:
        """
        Export approved examples and return them.
        Also saves to approved_examples.json.
        """
        self._export_approved()
        if os.path.exists(self._approved_path):
            with open(self._approved_path, "r") as f:
                return json.load(f)
        return {"doubt_resolution": [], "evaluation": [], "total_approved": 0}

    @staticmethod
    def load_approved_examples(flywheel_dir: str = FLYWHEEL_DIR) -> dict:
        """
        Load approved examples from disk (used by agents at startup).
        Returns empty dict if no approved examples exist.
        """
        path = os.path.join(flywheel_dir, "approved_examples.json")
        if os.path.exists(path):
            with open(path, "r") as f:
                return json.load(f)
        return {"doubt_resolution": [], "evaluation": []}

    # ──────────────────────────────────────────────
    # Statistics
    # ──────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Aggregate statistics for the data engineer dashboard."""
        total = len(self._interactions)
        by_type = {}
        by_status = {}
        by_misconception = {}
        top_concepts = {}

        for i in self._interactions:
            by_type[i.type] = by_type.get(i.type, 0) + 1
            by_status[i.status] = by_status.get(i.status, 0) + 1

            if i.misconception_type and i.misconception_type != "none":
                by_misconception[i.misconception_type] = by_misconception.get(i.misconception_type, 0) + 1

            key = f"{i.concept_id}:{i.concept_name}"
            top_concepts[key] = top_concepts.get(key, 0) + 1

        # Sort concepts by count
        sorted_concepts = sorted(top_concepts.items(), key=lambda x: x[1], reverse=True)

        return {
            "total_interactions": total,
            "by_type": by_type,
            "by_status": by_status,
            "misconceptions_by_type": by_misconception,
            "top_concepts": [
                {"concept": k.split(":", 1)[1] if ":" in k else k, "concept_id": k.split(":")[0], "count": v}
                for k, v in sorted_concepts[:10]
            ],
            "approval_rate": round(
                by_status.get("approved", 0) / total * 100, 1
            ) if total > 0 else 0.0,
        }

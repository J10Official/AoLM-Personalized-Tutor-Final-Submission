"""
Learner Model for the Personalised Learning System.

Represents an individual learner's knowledge state: per-concept mastery,
doubt history, session logs, and metacognitive calibration.
"""

import json
import os
import math
from dataclasses import dataclass, field, asdict
from typing import Optional
from datetime import datetime, timezone


@dataclass
class ConceptState:
    """Learner's state for a single concept."""
    concept_id: str
    mastery: float = 0.0
    mastery_history: list[float] = field(default_factory=list)
    last_reviewed: Optional[str] = None
    successful_retrievals: int = 0
    forgetting_strength: float = 7.0
    doubts: list[dict] = field(default_factory=list)
    misconceptions_detected: list[str] = field(default_factory=list)
    bloom_level_achieved: str = "remember"
    total_attempts: int = 0
    correct_attempts: int = 0
    avg_response_time: float = 0.0
    session_count: int = 0

    @property
    def calibration_accuracy(self) -> float:
        if self.total_attempts == 0:
            return 0.5
        return self.correct_attempts / self.total_attempts

    @property
    def confidence_from_response_time(self) -> float:
        if self.avg_response_time <= 0:
            return 0.5
        t = self.avg_response_time
        confidence = 1.0 / (1.0 + math.exp((t - 20) / 8))
        return max(0.1, min(1.0, confidence))


@dataclass
class SessionLog:
    """Log of a single learning session."""
    session_id: str
    concept_id: str
    started_at: str
    ended_at: Optional[str] = None
    doubts_raised: int = 0
    questions_attempted: int = 0
    questions_correct: int = 0
    mastery_before: float = 0.0
    mastery_after: float = 0.0
    bloom_level_tested: str = "remember"
    response_times: list[float] = field(default_factory=list)


class LearnerModel:
    """Complete learner profile — the personalisation backbone."""

    def __init__(self, learner_id: str, name: str = ""):
        self.learner_id = learner_id
        self.name = name
        self.concepts: dict[str, ConceptState] = {}
        self.sessions: list[dict] = []
        self.enrolled_courses: list[str] = []  # course names this user is enrolled in
        self.created_at = datetime.now(timezone.utc).isoformat()
        self.updated_at = self.created_at

    def get_concept_state(self, concept_id: str) -> ConceptState:
        if concept_id not in self.concepts:
            self.concepts[concept_id] = ConceptState(concept_id=concept_id)
        return self.concepts[concept_id]

    def get_mastery_map(self) -> dict[str, float]:
        return {cid: cs.mastery for cid, cs in self.concepts.items()}

    def get_known_concepts(self, threshold: float = 0.3) -> list[str]:
        return [cid for cid, cs in self.concepts.items() if cs.mastery >= threshold]

    def get_mastered_concepts(self, threshold: float = 0.7) -> list[str]:
        return [cid for cid, cs in self.concepts.items() if cs.mastery >= threshold]

    def get_all_doubts(self, unresolved_only: bool = False) -> list[dict]:
        all_doubts = []
        for cs in self.concepts.values():
            for doubt in cs.doubts:
                if unresolved_only and doubt.get("resolved", False):
                    continue
                all_doubts.append({**doubt, "concept_id": cs.concept_id})
        return all_doubts

    def add_session(self, session: SessionLog) -> None:
        self.sessions.append(asdict(session))
        self.updated_at = datetime.now(timezone.utc).isoformat()

    def enroll_in_course(self, course_name: str, concept_ids: list[str]) -> list[str]:
        """
        Enroll this learner in a course, adding all concepts at mastery 0.

        Returns: list of newly enrolled concept IDs (skips already-known concepts).
        """
        if course_name not in self.enrolled_courses:
            self.enrolled_courses.append(course_name)

        newly_enrolled = []
        for cid in concept_ids:
            if cid not in self.concepts:
                self.concepts[cid] = ConceptState(concept_id=cid)
                newly_enrolled.append(cid)

        self.updated_at = datetime.now(timezone.utc).isoformat()
        return newly_enrolled

    def is_enrolled_in(self, course_name: str) -> bool:
        """Check if learner is enrolled in a specific course."""
        return course_name in self.enrolled_courses

    @property
    def total_sessions(self) -> int:
        return len(self.sessions)

    @property
    def total_doubts(self) -> int:
        return sum(len(cs.doubts) for cs in self.concepts.values())

    @property
    def doubts_resolved(self) -> int:
        return sum(
            1 for cs in self.concepts.values()
            for d in cs.doubts if d.get("resolved", False)
        )

    @property
    def avg_mastery(self) -> float:
        if not self.concepts:
            return 0.0
        return sum(cs.mastery for cs in self.concepts.values()) / len(self.concepts)

    def to_dict(self) -> dict:
        return {
            "learner_id": self.learner_id,
            "name": self.name,
            "concepts": {cid: asdict(cs) for cid, cs in self.concepts.items()},
            "sessions": self.sessions,
            "enrolled_courses": self.enrolled_courses,
            "global_stats": {
                "avg_mastery": round(self.avg_mastery, 3),
                "total_sessions": self.total_sessions,
                "total_doubts": self.total_doubts,
                "doubts_resolved": self.doubts_resolved,
                "concepts_encountered": len(self.concepts),
                "concepts_mastered": len(self.get_mastered_concepts())
            },
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }

    def save(self, filepath: str) -> None:
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "LearnerModel":
        with open(filepath, "r") as f:
            data = json.load(f)
        model = cls(learner_id=data["learner_id"], name=data.get("name", ""))
        model.created_at = data.get("created_at", "")
        model.updated_at = data.get("updated_at", "")
        model.sessions = data.get("sessions", [])
        model.enrolled_courses = data.get("enrolled_courses", [])
        for cid, cdata in data.get("concepts", {}).items():
            model.concepts[cid] = ConceptState(**cdata)
        return model

    def summary(self) -> str:
        lines = [
            f"Learner: {self.name} ({self.learner_id})",
            f"  Concepts encountered: {len(self.concepts)}",
            f"  Concepts mastered: {len(self.get_mastered_concepts())}",
            f"  Average mastery: {self.avg_mastery:.2f}",
            f"  Total sessions: {self.total_sessions}",
            f"  Total doubts: {self.total_doubts} (resolved: {self.doubts_resolved})"
        ]
        return "\n".join(lines)

"""
Knowledge Graph for the Personalised Learning System.

Represents the global concept graph — a DAG of concepts with prerequisite
relationships, difficulty ratings, Bloom's ceiling levels, and metadata
sourced from NPTEL course structures.

Uses NetworkX for in-memory graph operations and JSON for persistence.
"""

import json
import os
from dataclasses import dataclass, field, asdict
from typing import Optional
from enum import Enum
from datetime import datetime, timezone

import networkx as nx


class BloomLevel(str, Enum):
    """Revised Bloom's Taxonomy levels, ordered from lowest to highest."""
    REMEMBER = "remember"
    UNDERSTAND = "understand"
    APPLY = "apply"
    ANALYSE = "analyse"
    EVALUATE = "evaluate"
    CREATE = "create"

    @classmethod
    def level_index(cls, level: "BloomLevel") -> int:
        order = list(cls)
        return order.index(level)

    @classmethod
    def from_mastery(cls, mastery: float) -> "BloomLevel":
        """Map a mastery score to the appropriate Bloom's level ceiling."""
        if mastery < 0.3:
            return cls.UNDERSTAND
        elif mastery < 0.6:
            return cls.APPLY
        elif mastery < 0.85:
            return cls.EVALUATE
        else:
            return cls.CREATE


class MisconceptionType(str, Enum):
    """Taxonomy of misconception types for doubt classification."""
    DEFINITIONAL = "definitional"   # Misunderstanding what a term means
    RELATIONAL = "relational"       # Misunderstanding how concepts connect
    PROCEDURAL = "procedural"       # Misunderstanding a process/algorithm
    CAUSAL = "causal"               # Misunderstanding why something works


@dataclass
class ConceptNode:
    """A single concept in the knowledge graph."""
    id: str
    name: str
    description: str
    difficulty: float                           # 0.0 to 1.0
    bloom_ceiling: BloomLevel                   # Highest Bloom's level applicable
    prerequisites: list[str] = field(default_factory=list)
    related_concepts: list[str] = field(default_factory=list)
    common_misconceptions: list[str] = field(default_factory=list)
    lecture_source: Optional[str] = None        # NPTEL lecture reference
    key_terms: list[str] = field(default_factory=list)
    example_questions: list[str] = field(default_factory=list)
    global_doubts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["bloom_ceiling"] = self.bloom_ceiling.value
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "ConceptNode":
        d["bloom_ceiling"] = BloomLevel(d["bloom_ceiling"])
        return cls(**d)


@dataclass
class CourseMetadata:
    """Metadata for a single ingested course."""
    course_name: str
    channel: str = ""
    playlist_id: str = ""
    lectures: list[dict] = field(default_factory=list)
    concept_ids: list[str] = field(default_factory=list)
    ingested_at: str = ""

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "CourseMetadata":
        return cls(**d)


class KnowledgeGraph:
    """
    Global knowledge graph representing concept relationships.

    This is a Directed Acyclic Graph (DAG) where edges represent
    prerequisite relationships (edge A→B means A is a prerequisite of B).

    Supports multiple courses — concepts are atomic and shared across courses.
    """

    def __init__(self):
        self.graph = nx.DiGraph()
        self.concepts: dict[str, ConceptNode] = {}
        # Multi-course metadata
        self.courses: list[CourseMetadata] = []
        # Legacy single-course fields (kept for backward compat)
        self.course_name: Optional[str] = None
        self.channel: Optional[str] = None
        self.lectures: list[dict] = []

    def add_concept(self, concept: ConceptNode) -> None:
        """Add a concept node to the graph."""
        self.concepts[concept.id] = concept
        self.graph.add_node(concept.id)

        # Add prerequisite edges
        for prereq_id in concept.prerequisites:
            if prereq_id in self.concepts:
                self.graph.add_edge(prereq_id, concept.id, relation="PREREQUISITE_OF")

        # Add related edges (undirected, stored as bidirectional)
        for related_id in concept.related_concepts:
            if related_id in self.concepts:
                self.graph.add_edge(concept.id, related_id, relation="RELATED_TO")
                self.graph.add_edge(related_id, concept.id, relation="RELATED_TO")

    def get_concept(self, concept_id: str) -> Optional[ConceptNode]:
        """Retrieve a concept by ID."""
        return self.concepts.get(concept_id)

    def get_prerequisites(self, concept_id: str) -> list[ConceptNode]:
        """Get all direct prerequisites of a concept."""
        prereq_ids = self.concepts[concept_id].prerequisites
        return [self.concepts[pid] for pid in prereq_ids if pid in self.concepts]

    def get_all_prerequisites(self, concept_id: str) -> list[str]:
        """Get ALL prerequisites (transitive closure) of a concept."""
        all_prereqs = set()
        queue = list(self.concepts[concept_id].prerequisites)
        while queue:
            pid = queue.pop(0)
            if pid not in all_prereqs and pid in self.concepts:
                all_prereqs.add(pid)
                queue.extend(self.concepts[pid].prerequisites)
        return list(all_prereqs)

    def get_dependents(self, concept_id: str) -> list[str]:
        """Get concepts that depend on this concept (successors in DAG)."""
        return [
            succ for succ in self.graph.successors(concept_id)
            if self.graph[concept_id][succ].get("relation") == "PREREQUISITE_OF"
        ]

    def get_related(self, concept_id: str) -> list[str]:
        """Get concepts related to this concept (non-prerequisite links)."""
        related = []
        for neighbor in self.graph.neighbors(concept_id):
            if self.graph[concept_id][neighbor].get("relation") == "RELATED_TO":
                related.append(neighbor)
        return related

    def get_ready_concepts(self, mastery_map: dict[str, float], threshold: float = 0.7) -> list[str]:
        """
        Find concepts the learner is ready to learn (ZPD targeting).

        A concept is 'ready' if:
        1. All its prerequisites have mastery >= threshold
        2. The concept itself has mastery < 0.85 (not yet mastered)
        """
        ready = []
        for concept_id, concept in self.concepts.items():
            current_mastery = mastery_map.get(concept_id, 0.0)
            if current_mastery >= 0.85:
                continue  # Already mastered

            # Check all prerequisites
            all_prereqs_met = True
            min_prereq_mastery = 1.0
            for prereq_id in concept.prerequisites:
                prereq_mastery = mastery_map.get(prereq_id, 0.0)
                min_prereq_mastery = min(min_prereq_mastery, prereq_mastery)
                if prereq_mastery < threshold:
                    all_prereqs_met = False
                    break

            if all_prereqs_met:
                ready.append(concept_id)

        return ready

    def get_weakest_prerequisite(self, concept_id: str, mastery_map: dict[str, float]) -> Optional[str]:
        """
        Diagnostic rollback: find the weakest prerequisite of a concept.
        Used when a learner fails — trace back to what they need to review.
        """
        prereqs = self.concepts[concept_id].prerequisites
        if not prereqs:
            return None

        weakest = min(prereqs, key=lambda pid: mastery_map.get(pid, 0.0))
        return weakest

    def get_diagnostic_chain(
        self,
        concept_id: str,
        mastery_map: dict[str, float],
        threshold: float = 0.5,
        max_depth: int = 5,
    ) -> list[str]:
        """
        Recursive diagnostic rollback: walk the prerequisite chain to find
        ALL weak prerequisites that should be reviewed before retrying the
        failed concept.

        Returns a list of concept IDs ordered from deepest prerequisite
        to the failed concept's direct prerequisite (i.e., learning order).
        """
        chain = []
        visited = set()

        def _walk(cid: str, depth: int):
            if depth > max_depth or cid in visited:
                return
            visited.add(cid)
            concept = self.get_concept(cid)
            if not concept:
                return

            for prereq_id in concept.prerequisites:
                if prereq_id in self.concepts:
                    prereq_mastery = mastery_map.get(prereq_id, 0.0)
                    if prereq_mastery < threshold:
                        # Recurse deeper first
                        _walk(prereq_id, depth + 1)
                        if prereq_id not in chain:
                            chain.append(prereq_id)

        _walk(concept_id, 0)
        return chain

    def topological_order(self) -> list[str]:
        """Return concepts in valid learning order (topological sort)."""
        # Filter to only prerequisite edges for topological sort
        prereq_graph = nx.DiGraph()
        for concept_id in self.concepts:
            prereq_graph.add_node(concept_id)
            for prereq_id in self.concepts[concept_id].prerequisites:
                if prereq_id in self.concepts:
                    prereq_graph.add_edge(prereq_id, concept_id)
        return list(nx.topological_sort(prereq_graph))

    def concept_centrality(self, concept_id: str) -> float:
        """
        Compute how 'central' a concept is in the graph.
        More dependents + more connections = higher centrality.
        Used for prioritising concept recommendations.
        """
        dependents = len(self.get_dependents(concept_id))
        related = len(self.get_related(concept_id))
        total_concepts = max(len(self.concepts), 1)
        return (dependents * 2 + related) / total_concepts

    def get_connection_count(self, concept_id: str) -> int:
        """Count how many edges connect to this concept."""
        return self.graph.degree(concept_id)

    # ========================
    # Multi-course support
    # ========================

    def has_course(self, identifier: str) -> bool:
        """
        Check if a course has already been ingested.
        Matches by playlist_id or course_name (case-insensitive).
        """
        identifier_lower = identifier.lower().strip()
        for course in self.courses:
            if course.playlist_id and course.playlist_id.lower() == identifier_lower:
                return True
            if course.course_name.lower().strip() == identifier_lower:
                return True
        return False

    def get_course(self, identifier: str) -> Optional[CourseMetadata]:
        """Get a course by playlist_id or course_name."""
        identifier_lower = identifier.lower().strip()
        for course in self.courses:
            if course.playlist_id and course.playlist_id.lower() == identifier_lower:
                return course
            if course.course_name.lower().strip() == identifier_lower:
                return course
        return None

    def get_course_concepts(self, course_name: str) -> list[str]:
        """Get all concept IDs belonging to a specific course."""
        course = self.get_course(course_name)
        if course:
            return [cid for cid in course.concept_ids if cid in self.concepts]
        return []

    def add_course_metadata(self, metadata: CourseMetadata) -> None:
        """Register a course's metadata."""
        # Check if already exists
        if not self.has_course(metadata.playlist_id or metadata.course_name):
            self.courses.append(metadata)
        # Update legacy fields for backward compat
        self.course_name = metadata.course_name
        self.channel = metadata.channel
        self.lectures = metadata.lectures

    def merge(self, other_kg: "KnowledgeGraph") -> list[str]:
        """
        Merge concepts from another KnowledgeGraph into this one.
        Deduplicates by concept ID — existing concepts are NOT overwritten.

        Returns: list of newly added concept IDs.
        """
        new_concept_ids = []

        for cid, concept in other_kg.concepts.items():
            if cid not in self.concepts:
                self.add_concept(concept)
                new_concept_ids.append(cid)

        # Rebuild edges for new concepts (prerequisites may reference existing)
        for cid in new_concept_ids:
            concept = self.concepts[cid]
            for prereq_id in concept.prerequisites:
                if prereq_id in self.concepts:
                    if not self.graph.has_edge(prereq_id, cid):
                        self.graph.add_edge(prereq_id, cid, relation="PREREQUISITE_OF")
            for related_id in concept.related_concepts:
                if related_id in self.concepts:
                    if not self.graph.has_edge(cid, related_id):
                        self.graph.add_edge(cid, related_id, relation="RELATED_TO")
                    if not self.graph.has_edge(related_id, cid):
                        self.graph.add_edge(related_id, cid, relation="RELATED_TO")

        # Merge course metadata
        for course in other_kg.courses:
            self.add_course_metadata(course)

        return new_concept_ids

    # ========================
    # Validation
    # ========================

    def validate(self) -> list[str]:
        """Validate the knowledge graph for common issues."""
        issues = []

        # Check for cycles (should be a DAG)
        prereq_graph = nx.DiGraph()
        for cid, concept in self.concepts.items():
            for pid in concept.prerequisites:
                if pid in self.concepts:
                    prereq_graph.add_edge(pid, cid)

        if not nx.is_directed_acyclic_graph(prereq_graph):
            cycles = list(nx.simple_cycles(prereq_graph))
            issues.append(f"Prerequisite graph has cycles: {cycles}")

        # Check for dangling prerequisites
        for cid, concept in self.concepts.items():
            for pid in concept.prerequisites:
                if pid not in self.concepts:
                    issues.append(f"Concept '{cid}' has unknown prerequisite '{pid}'")

        # Check for isolated nodes (no prerequisites and no dependents)
        for cid in self.concepts:
            if prereq_graph.degree(cid) == 0 and len(self.concepts[cid].prerequisites) == 0:
                if not self.get_dependents(cid):
                    issues.append(f"Concept '{cid}' is isolated (no connections)")

        return issues

    # ========================
    # Persistence
    # ========================

    def save(self, filepath: str) -> None:
        """Persist the knowledge graph to a JSON file."""
        data = {
            "concepts": {cid: c.to_dict() for cid, c in self.concepts.items()},
            "courses": [c.to_dict() for c in self.courses],
            "hierarchy": {
                "course_name": self.course_name,
                "channel": self.channel,
                "lectures": self.lectures,
            },
            "metadata": {
                "total_concepts": len(self.concepts),
                "total_edges": self.graph.number_of_edges(),
                "total_courses": len(self.courses),
            }
        }
        dir_name = os.path.dirname(filepath)
        if dir_name:
            os.makedirs(dir_name, exist_ok=True)
        with open(filepath, "w") as f:
            json.dump(data, f, indent=2)

    @classmethod
    def load(cls, filepath: str) -> "KnowledgeGraph":
        """Load a knowledge graph from a JSON file."""
        kg = cls()
        with open(filepath, "r") as f:
            data = json.load(f)

        # Load hierarchy metadata (legacy single-course format)
        hierarchy = data.get("hierarchy", {})
        kg.course_name = hierarchy.get("course_name")
        kg.channel = hierarchy.get("channel")
        kg.lectures = hierarchy.get("lectures", [])

        # Load multi-course metadata
        for cdata in data.get("courses", []):
            kg.courses.append(CourseMetadata.from_dict(cdata))

        # If no courses list but hierarchy exists, create one from legacy format
        if not kg.courses and kg.course_name:
            kg.courses.append(CourseMetadata(
                course_name=kg.course_name,
                channel=kg.channel or "",
                lectures=kg.lectures,
                concept_ids=list(data.get("concepts", {}).keys()),
                ingested_at="",
            ))

        # Two-pass: first add all concepts, then rebuild edges
        for cid, cdata in data["concepts"].items():
            concept = ConceptNode.from_dict(cdata)
            kg.concepts[concept.id] = concept
            kg.graph.add_node(concept.id)

        # Second pass: add edges
        for cid, concept in kg.concepts.items():
            for prereq_id in concept.prerequisites:
                if prereq_id in kg.concepts:
                    kg.graph.add_edge(prereq_id, cid, relation="PREREQUISITE_OF")
            for related_id in concept.related_concepts:
                if related_id in kg.concepts:
                    kg.graph.add_edge(cid, related_id, relation="RELATED_TO")

        return kg

    def summary(self) -> str:
        """Return a human-readable summary of the knowledge graph."""
        lines = ["Knowledge Graph Summary"]
        if self.course_name:
            lines.append(f"  Course: {self.course_name}")
        if self.channel:
            lines.append(f"  Channel: {self.channel}")
        if self.courses:
            lines.append(f"  Total courses: {len(self.courses)}")
            for c in self.courses:
                lines.append(f"    - {c.course_name} ({len(c.concept_ids)} concepts)")
        if self.lectures:
            lines.append(f"  Lectures: {len(self.lectures)}")
        lines.extend([
            f"  Concepts: {len(self.concepts)}",
            f"  Edges: {self.graph.number_of_edges()}",
        ])
        topo = self.topological_order()
        if topo:
            lines.append(f"  Topological order: {' → '.join(topo[:10])}...")
        lines.append(f"  Validation issues: {len(self.validate())}")
        return "\n".join(lines)

"""
Tests for the Knowledge Graph (core/knowledge_graph.py).

Covers requirements:
  R6.10  — Global Knowledge Graph
  R9.4   — Node taxonomy (Course, Lecture, Concept)
  R9.6   — Atomic concepts
  R9.7   — JSON persistence
  R9.8   — DAG structure
  R10.1  — Graph traversal
  R10.2  — ZPD-ready concepts (prerequisites mastered ≥ threshold)
  R10.3  — Diagnostic rollback
  R21.5  — Graph traversal accuracy
"""

import os
import json
import pytest
from backend.core.knowledge_graph import (
    KnowledgeGraph, ConceptNode, BloomLevel, MisconceptionType, CourseMetadata,
)


# ──────────────────────────────────────────────
# R9.8 — DAG validation
# ──────────────────────────────────────────────

class TestKnowledgeGraphDAG:

    def test_graph_is_dag(self, sample_kg):
        """R9.8: Knowledge graph prerequisite structure must be a DAG (no cycles)."""
        issues = sample_kg.validate()
        cycle_issues = [i for i in issues if "cycle" in i.lower()]
        assert len(cycle_issues) == 0, f"Graph has cycles: {cycle_issues}"

    def test_topological_sort_exists(self, sample_kg):
        """R9.8: Topological ordering must be computable (only for DAGs)."""
        order = sample_kg.topological_order()
        assert len(order) == len(sample_kg.concepts)

    def test_topological_order_respects_prerequisites(self, sample_kg):
        """R9.8 / R21.5: Every concept appears after all its prerequisites."""
        order = sample_kg.topological_order()
        idx = {cid: i for i, cid in enumerate(order)}
        for cid, concept in sample_kg.concepts.items():
            for prereq in concept.prerequisites:
                assert idx[prereq] < idx[cid], (
                    f"Prereq {prereq} must appear before {cid} in topological order"
                )


# ──────────────────────────────────────────────
# R9.6 — Atomic concepts
# ──────────────────────────────────────────────

class TestConceptAtomicity:

    def test_concept_has_required_fields(self, sample_kg):
        """R9.6: Each concept must have id, name, description, difficulty, bloom_ceiling."""
        for cid, concept in sample_kg.concepts.items():
            assert concept.id, "Concept must have an id"
            assert concept.name, "Concept must have a name"
            assert concept.description, "Concept must have a description"
            assert 0.0 <= concept.difficulty <= 1.0, "Difficulty must be in [0, 1]"
            assert isinstance(concept.bloom_ceiling, BloomLevel)

    def test_concept_ids_are_snake_case(self, sample_kg):
        """R9.6: Concept IDs should be generic snake_case identifiers."""
        import re
        for cid in sample_kg.concepts:
            assert re.match(r"^[a-z][a-z0-9_]*$", cid), f"ID '{cid}' is not snake_case"


# ──────────────────────────────────────────────
# R9.7 — JSON persistence
# ──────────────────────────────────────────────

class TestKnowledgeGraphPersistence:

    def test_save_and_load_roundtrip(self, sample_kg, tmp_dir):
        """R9.7: Knowledge graph must be saveable and loadable from JSON."""
        path = os.path.join(tmp_dir, "kg.json")
        sample_kg.save(path)
        assert os.path.exists(path)

        loaded = KnowledgeGraph.load(path)
        assert len(loaded.concepts) == len(sample_kg.concepts)
        for cid in sample_kg.concepts:
            assert cid in loaded.concepts

    def test_saved_json_is_valid(self, sample_kg, tmp_dir):
        """R9.7: Saved file must be valid JSON with expected keys."""
        path = os.path.join(tmp_dir, "kg.json")
        sample_kg.save(path)
        with open(path) as f:
            data = json.load(f)
        assert "concepts" in data
        assert "metadata" in data
        assert data["metadata"]["total_concepts"] == len(sample_kg.concepts)


# ──────────────────────────────────────────────
# R10.1 / R10.2 — Graph traversal & ZPD
# ──────────────────────────────────────────────

class TestGraphTraversal:

    def test_get_prerequisites(self, sample_kg):
        """R10.1: Can retrieve direct prerequisites of a concept."""
        prereqs = sample_kg.get_prerequisites("conditionals")
        prereq_ids = [p.id for p in prereqs]
        assert "operators" in prereq_ids

    def test_get_all_prerequisites_transitive(self, sample_kg):
        """R10.1: Can retrieve transitive closure of prerequisites."""
        all_prereqs = sample_kg.get_all_prerequisites("loops")
        assert "conditionals" in all_prereqs
        assert "operators" in all_prereqs
        assert "variables" in all_prereqs

    def test_get_ready_concepts_zpd(self, sample_kg):
        """R10.2: ZPD targeting — only concepts with ALL prereqs mastered are ready."""
        mastery_map = {
            "variables": 0.8,
            "data_types": 0.6,
            "operators": 0.4,
            "conditionals": 0.15,
            "loops": 0.0,
        }
        ready = sample_kg.get_ready_concepts(mastery_map, threshold=0.5)
        # variables: mastery 0.8 < 0.85, no prereqs → ready (not yet fully mastered)
        assert "variables" in ready
        # data_types has prereq variables=0.8 ≥ 0.5 → ready
        assert "data_types" in ready
        # operators has prereq data_types=0.6 ≥ 0.5 AND variables=0.8 ≥ 0.5 → ready
        assert "operators" in ready

    def test_concept_centrality(self, sample_kg):
        """R10.4: Concepts with more dependents are more central."""
        c_variables = sample_kg.concept_centrality("variables")
        c_loops = sample_kg.concept_centrality("loops")
        # variables has 2 dependents, loops has 0
        assert c_variables > c_loops


# ──────────────────────────────────────────────
# R10.3 — Diagnostic rollback
# ──────────────────────────────────────────────

class TestDiagnosticRollback:

    def test_diagnostic_chain_finds_weak_prereqs(self, sample_kg):
        """R10.3: Diagnostic rollback finds weak prerequisites recursively."""
        mastery_map = {
            "variables": 0.8,
            "data_types": 0.3,  # weak
            "operators": 0.2,   # weak
            "conditionals": 0.1,
            "loops": 0.0,
        }
        chain = sample_kg.get_diagnostic_chain("loops", mastery_map, threshold=0.5)
        # Should find weak prereqs of loops (conditionals → operators → data_types)
        assert len(chain) > 0
        assert "conditionals" in chain

    def test_weakest_prerequisite(self, sample_kg):
        """R10.3: Can find the single weakest prerequisite."""
        mastery_map = {"variables": 0.9, "data_types": 0.3}
        weakest = sample_kg.get_weakest_prerequisite("operators", mastery_map)
        assert weakest == "data_types"


# ──────────────────────────────────────────────
# R9.4 — Multi-course support
# ──────────────────────────────────────────────

class TestMultiCourse:

    def test_course_metadata_stored(self, sample_kg):
        """R9.4: Course metadata is stored and retrievable."""
        assert len(sample_kg.courses) > 0
        assert sample_kg.courses[0].course_name == "Intro to Python"

    def test_has_course_by_name(self, sample_kg):
        """R9.4: Can check if a course is already ingested."""
        assert sample_kg.has_course("Intro to Python")
        assert not sample_kg.has_course("Advanced ML")

    def test_get_course_concepts(self, sample_kg):
        """R9.4: Can retrieve all concept IDs belonging to a course."""
        concepts = sample_kg.get_course_concepts("Intro to Python")
        assert len(concepts) == 5

    def test_merge_graphs(self, sample_kg):
        """R9.4: Can merge two knowledge graphs without duplicates."""
        other_kg = KnowledgeGraph()
        new_concept = ConceptNode(
            id="functions", name="Functions",
            description="Reusable blocks of code.",
            difficulty=0.5, bloom_ceiling=BloomLevel.APPLY,
            prerequisites=["loops"],
        )
        other_kg.add_concept(new_concept)
        other_kg.add_course_metadata(CourseMetadata(
            course_name="Advanced Python", concept_ids=["functions"],
        ))

        new_ids = sample_kg.merge(other_kg)
        assert "functions" in new_ids
        assert len(sample_kg.concepts) == 6


# ──────────────────────────────────────────────
# BloomLevel mapping
# ──────────────────────────────────────────────

class TestBloomLevel:

    @pytest.mark.parametrize("mastery,expected", [
        (0.1, BloomLevel.UNDERSTAND),
        (0.29, BloomLevel.UNDERSTAND),
        (0.3, BloomLevel.APPLY),
        (0.59, BloomLevel.APPLY),
        (0.6, BloomLevel.EVALUATE),
        (0.84, BloomLevel.EVALUATE),
        (0.85, BloomLevel.CREATE),
        (1.0, BloomLevel.CREATE),
    ])
    def test_bloom_from_mastery(self, mastery, expected):
        """R13.4 / R22.4 / R22.5: Bloom level maps correctly from mastery."""
        assert BloomLevel.from_mastery(mastery) == expected

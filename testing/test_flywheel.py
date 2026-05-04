"""
Tests for the Human-in-the-Loop Data Flywheel.

Covers:
- Interaction collection (doubts & evaluations)
- Curation workflow (approve/reject)
- Export to DSPy few-shot format
- Statistics aggregation
"""

import json
import os
import pytest
from backend.data.flywheel import FlywheelStore, Interaction


@pytest.fixture
def flywheel(tmp_path):
    """Create a FlywheelStore with a temporary directory."""
    return FlywheelStore(flywheel_dir=str(tmp_path / "flywheel"))


class TestCollectInteractions:
    """R2.2/R17.3: System collects learner interactions automatically."""

    def test_collect_doubt(self, flywheel):
        """A doubt resolution is recorded and persisted."""
        iid = flywheel.collect_doubt(
            learner_id="alice",
            concept_id="recursion",
            concept_name="Recursion",
            doubt_text="Why doesn't recursion run forever?",
            answer_text="Because of the base case.",
            misconception_type="relational",
            misconception_explanation="Conflates loops and recursion.",
        )
        assert iid  # Returns non-empty ID
        interactions, total = flywheel.get_interactions()
        assert total == 1
        assert interactions[0]["type"] == "doubt_resolution"
        assert interactions[0]["doubt_text"] == "Why doesn't recursion run forever?"
        assert interactions[0]["status"] == "pending"

    def test_collect_evaluation(self, flywheel):
        """An evaluation interaction is recorded and persisted."""
        iid = flywheel.collect_evaluation(
            learner_id="bob",
            concept_id="binary_search",
            concept_name="Binary Search",
            question_text="Explain binary search.",
            student_answer="It searches by halving.",
            correct_answer="It divides the sorted array in half...",
            score=0.7,
            feedback="Good but could be more specific.",
            bloom_level="understand",
            question_type="written",
        )
        assert iid
        interactions, total = flywheel.get_interactions()
        assert total == 1
        assert interactions[0]["type"] == "evaluation"
        assert interactions[0]["score"] == 0.7

    def test_multiple_interactions(self, flywheel):
        """Multiple interactions are stored correctly."""
        flywheel.collect_doubt("alice", "x", "X", "q1", "a1")
        flywheel.collect_doubt("bob", "y", "Y", "q2", "a2")
        flywheel.collect_evaluation("alice", "x", "X", "q", "a", "c", 0.5, "f")
        _, total = flywheel.get_interactions()
        assert total == 3

    def test_persistence(self, tmp_path):
        """Interactions survive reload from disk."""
        fw_dir = str(tmp_path / "flywheel")
        fw1 = FlywheelStore(flywheel_dir=fw_dir)
        fw1.collect_doubt("alice", "x", "X", "q", "a")
        
        fw2 = FlywheelStore(flywheel_dir=fw_dir)
        _, total = fw2.get_interactions()
        assert total == 1


class TestCurationWorkflow:
    """R24.6: Data engineer can approve/reject interactions."""

    def test_approve(self, flywheel):
        iid = flywheel.collect_doubt("alice", "x", "X", "q", "a")
        ok = flywheel.approve(iid, "Good example")
        assert ok
        interactions, _ = flywheel.get_interactions(filter_status="approved")
        assert len(interactions) == 1
        assert interactions[0]["curator_notes"] == "Good example"

    def test_reject(self, flywheel):
        iid = flywheel.collect_doubt("alice", "x", "X", "q", "a")
        ok = flywheel.reject(iid, "Too vague")
        assert ok
        interactions, _ = flywheel.get_interactions(filter_status="rejected")
        assert len(interactions) == 1

    def test_approve_nonexistent(self, flywheel):
        ok = flywheel.approve("nonexistent_id")
        assert not ok

    def test_filter_by_type(self, flywheel):
        flywheel.collect_doubt("a", "x", "X", "q", "a")
        flywheel.collect_evaluation("b", "y", "Y", "q", "a", "c", 0.5, "f")
        doubts, _ = flywheel.get_interactions(filter_type="doubt_resolution")
        evals, _ = flywheel.get_interactions(filter_type="evaluation")
        assert len(doubts) == 1
        assert len(evals) == 1

    def test_filter_by_status(self, flywheel):
        id1 = flywheel.collect_doubt("a", "x", "X", "q1", "a1")
        flywheel.collect_doubt("b", "y", "Y", "q2", "a2")
        flywheel.approve(id1)
        approved, _ = flywheel.get_interactions(filter_status="approved")
        pending, _ = flywheel.get_interactions(filter_status="pending")
        assert len(approved) == 1
        assert len(pending) == 1

    def test_pagination(self, flywheel):
        for i in range(10):
            flywheel.collect_doubt(f"user{i}", "x", "X", f"q{i}", f"a{i}")
        page1, total = flywheel.get_interactions(limit=3, offset=0)
        assert len(page1) == 3
        assert total == 10
        page2, _ = flywheel.get_interactions(limit=3, offset=3)
        assert len(page2) == 3


class TestExport:
    """R24.6: Export approved examples as DSPy few-shot data."""

    def test_export_approved(self, flywheel):
        id1 = flywheel.collect_doubt("a", "x", "X", "q", "a", "relational", "exp")
        id2 = flywheel.collect_evaluation("b", "y", "Y", "q", "sa", "ca", 0.8, "fb")
        flywheel.approve(id1)
        flywheel.approve(id2)

        examples = flywheel.export_fewshot_examples()
        assert examples["total_approved"] == 2
        assert len(examples["doubt_resolution"]) == 1
        assert len(examples["evaluation"]) == 1
        assert examples["doubt_resolution"][0]["doubt"] == "q"

    def test_export_excludes_rejected(self, flywheel):
        id1 = flywheel.collect_doubt("a", "x", "X", "q1", "a1")
        id2 = flywheel.collect_doubt("b", "y", "Y", "q2", "a2")
        flywheel.approve(id1)
        flywheel.reject(id2)

        examples = flywheel.export_fewshot_examples()
        assert examples["total_approved"] == 1

    def test_export_file_created(self, flywheel):
        iid = flywheel.collect_doubt("a", "x", "X", "q", "a")
        flywheel.approve(iid)
        flywheel.export_fewshot_examples()

        path = os.path.join(flywheel.flywheel_dir, "approved_examples.json")
        assert os.path.exists(path)
        with open(path) as f:
            data = json.load(f)
        assert data["total_approved"] == 1

    def test_load_approved_static(self, tmp_path):
        """Static loader returns empty dict when no file exists."""
        result = FlywheelStore.load_approved_examples(str(tmp_path))
        assert result == {"doubt_resolution": [], "evaluation": []}


class TestStatistics:
    """Admin dashboard statistics."""

    def test_empty_stats(self, flywheel):
        stats = flywheel.get_stats()
        assert stats["total_interactions"] == 0
        assert stats["approval_rate"] == 0.0

    def test_stats_with_data(self, flywheel):
        id1 = flywheel.collect_doubt("a", "x", "Concept X", "q", "a", "relational")
        flywheel.collect_doubt("b", "x", "Concept X", "q2", "a2", "definitional")
        flywheel.collect_evaluation("c", "y", "Concept Y", "q", "sa", "ca", 0.5, "f")
        flywheel.approve(id1)

        stats = flywheel.get_stats()
        assert stats["total_interactions"] == 3
        assert stats["by_type"]["doubt_resolution"] == 2
        assert stats["by_type"]["evaluation"] == 1
        assert stats["by_status"]["approved"] == 1
        assert stats["by_status"]["pending"] == 2
        assert stats["misconceptions_by_type"]["relational"] == 1
        assert stats["misconceptions_by_type"]["definitional"] == 1
        assert len(stats["top_concepts"]) == 2


class TestInteractionModel:
    """Interaction dataclass serialisation."""

    def test_to_dict_roundtrip(self):
        i = Interaction(
            id="abc", type="doubt_resolution",
            learner_id="alice", concept_id="x", concept_name="X",
            timestamp="2025-01-01T00:00:00Z",
            doubt_text="question",
        )
        d = i.to_dict()
        i2 = Interaction.from_dict(d)
        assert i2.id == "abc"
        assert i2.doubt_text == "question"
        assert i2.status == "pending"

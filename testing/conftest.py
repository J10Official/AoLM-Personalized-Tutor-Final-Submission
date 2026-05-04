"""
Shared fixtures for the Personalised Learning System test suite.

These fixtures create test knowledge graphs, learner models, and agent
instances WITHOUT requiring a live LLM connection, so that structural /
deterministic behaviour can be verified offline.
"""

import os
import sys
import json
import pytest
import tempfile

# Add the project root to the path so we can import backend modules
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from backend.core.knowledge_graph import KnowledgeGraph, ConceptNode, BloomLevel, CourseMetadata
from backend.core.learner_model import LearnerModel, ConceptState


# ---------------------------------------------------------------------------
# Knowledge Graph Fixtures
# ---------------------------------------------------------------------------

def _make_concept(cid, name, desc, difficulty, bloom, prereqs=None, related=None):
    return ConceptNode(
        id=cid,
        name=name,
        description=desc,
        difficulty=difficulty,
        bloom_ceiling=bloom,
        prerequisites=prereqs or [],
        related_concepts=related or [],
        common_misconceptions=[f"Common misconception about {name}"],
        key_terms=[name.lower()],
        example_questions=[f"Explain {name} in your own words."],
        global_doubts=[f"Why does {name} matter?"],
    )


@pytest.fixture
def sample_kg():
    """A small knowledge graph with 5 concepts forming a DAG."""
    kg = KnowledgeGraph()

    concepts = [
        _make_concept("variables", "Variables", "Containers for storing data values.",
                       0.1, BloomLevel.REMEMBER),
        _make_concept("data_types", "Data Types", "Classification of data (int, float, str).",
                       0.2, BloomLevel.UNDERSTAND, prereqs=["variables"]),
        _make_concept("operators", "Operators", "Symbols that perform operations on variables.",
                       0.3, BloomLevel.APPLY, prereqs=["variables", "data_types"]),
        _make_concept("conditionals", "Conditionals", "if/else statements for branching logic.",
                       0.4, BloomLevel.APPLY, prereqs=["operators"],
                       related=["data_types"]),
        _make_concept("loops", "Loops", "Repeating a block of code (for, while).",
                       0.5, BloomLevel.ANALYSE, prereqs=["conditionals"]),
    ]

    for c in concepts:
        kg.add_concept(c)

    course_meta = CourseMetadata(
        course_name="Intro to Python",
        channel="TestChannel",
        playlist_id="PL_TEST_123",
        lectures=[{"index": 0, "title": "Lecture 1", "video_id": "vid1"}],
        concept_ids=[c.id for c in concepts],
    )
    kg.add_course_metadata(course_meta)

    return kg


@pytest.fixture
def sample_learner(sample_kg):
    """A learner enrolled in the sample course with varied mastery."""
    learner = LearnerModel(learner_id="test_user", name="Test User")
    concept_ids = list(sample_kg.concepts.keys())
    learner.enroll_in_course("Intro to Python", concept_ids)

    # Set varied mastery levels
    learner.get_concept_state("variables").mastery = 0.8
    learner.get_concept_state("data_types").mastery = 0.6
    learner.get_concept_state("operators").mastery = 0.4
    learner.get_concept_state("conditionals").mastery = 0.15
    learner.get_concept_state("loops").mastery = 0.0

    return learner


@pytest.fixture
def tmp_dir():
    """Provide a temporary directory for file persistence tests."""
    with tempfile.TemporaryDirectory() as d:
        yield d

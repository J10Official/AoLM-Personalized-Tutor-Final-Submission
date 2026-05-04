"""
Populate TestUser — Creates a realistic test user enrolled in 2 courses
with varied mastery levels, doubts, review data, and session history.

Run: python -m backend.data.populate_testuser
"""

import json
import os
import sys
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.learner_model import LearnerModel, ConceptState


DATA_DIR = os.path.dirname(os.path.abspath(__file__))
LEARNERS_DIR = os.path.join(DATA_DIR, "learners")


def populate():
    """Create/update TestUser with realistic learning data across 2 courses."""

    learner = LearnerModel(learner_id="testuser", name="TestUser")

    # ========================================================================
    # Course 1: Crash Course Geology
    # Simulating: user has studied ~60% of the course, strong on basics,
    # intermediate on middle topics, hasn't touched advanced concepts.
    # ========================================================================
    geology_course = "Crash Course Geology"
    learner.enrolled_courses.append(geology_course)

    now = datetime.now(timezone.utc)

    # Mastered concepts (mastery > 0.7) — foundational
    mastered_geo = {
        "geology_definition": {
            "mastery": 0.88,
            "last_reviewed": (now - timedelta(days=5)).isoformat(),
            "successful_retrievals": 4,
            "total_attempts": 5,
            "correct_attempts": 4,
            "avg_response_time": 8.3,
            "session_count": 2,
            "bloom_level_achieved": "apply",
            "doubts": [
                {
                    "text": "Is geology only about rocks?",
                    "type": "definitional",
                    "resolved": True,
                    "resolution": "No, geology is the study of the entire Earth system — its formation, composition, structure, and processes. Rocks are just one part of a much larger interconnected system."
                }
            ],
        },
        "geological_history_indigenous": {
            "mastery": 0.75,
            "last_reviewed": (now - timedelta(days=6)).isoformat(),
            "successful_retrievals": 3,
            "total_attempts": 4,
            "correct_attempts": 3,
            "avg_response_time": 12.1,
            "session_count": 1,
            "bloom_level_achieved": "understand",
            "doubts": [],
        },
        "earth_interconnected_system": {
            "mastery": 0.82,
            "last_reviewed": (now - timedelta(days=4)).isoformat(),
            "successful_retrievals": 3,
            "total_attempts": 4,
            "correct_attempts": 3,
            "avg_response_time": 10.5,
            "session_count": 2,
            "bloom_level_achieved": "apply",
            "doubts": [
                {
                    "text": "How does the atmosphere connect to geology?",
                    "type": "relational",
                    "resolved": True,
                    "resolution": "The atmosphere interacts with the lithosphere through weathering and erosion, and volcanic eruptions release gases that affect atmospheric composition."
                }
            ],
        },
    }

    # Intermediate concepts (mastery 0.3-0.6) — in progress
    intermediate_geo = {
        "geological_history_early_scientists": {
            "mastery": 0.55,
            "last_reviewed": (now - timedelta(days=3)).isoformat(),
            "successful_retrievals": 2,
            "total_attempts": 4,
            "correct_attempts": 2,
            "avg_response_time": 18.2,
            "session_count": 1,
            "bloom_level_achieved": "understand",
            "doubts": [
                {
                    "text": "What's the difference between uniformitarianism and catastrophism?",
                    "type": "relational",
                    "resolved": True,
                    "resolution": "Uniformitarianism (Hutton) says geological change is gradual; catastrophism (Cuvier) says change comes from sudden events. Modern geology accepts both."
                }
            ],
        },
        "fields_of_geology": {
            "mastery": 0.48,
            "last_reviewed": (now - timedelta(days=8)).isoformat(),  # Old — should trigger review
            "successful_retrievals": 1,
            "total_attempts": 3,
            "correct_attempts": 1,
            "avg_response_time": 22.0,
            "session_count": 1,
            "bloom_level_achieved": "remember",
            "doubts": [],
        },
        "earth_internal_structure_overview": {
            "mastery": 0.42,
            "last_reviewed": (now - timedelta(days=2)).isoformat(),
            "successful_retrievals": 1,
            "total_attempts": 3,
            "correct_attempts": 1,
            "avg_response_time": 20.5,
            "session_count": 1,
            "bloom_level_achieved": "remember",
            "doubts": [
                {
                    "text": "Why is the inner core solid if it's hotter than the outer core?",
                    "type": "causal",
                    "resolved": True,
                    "resolution": "The extreme pressure at the inner core compresses atoms so tightly that they can't move freely, making it solid despite the temperature."
                }
            ],
        },
        "earth_crust_properties": {
            "mastery": 0.38,
            "last_reviewed": (now - timedelta(days=10)).isoformat(),  # Old — should trigger review
            "successful_retrievals": 1,
            "total_attempts": 2,
            "correct_attempts": 1,
            "avg_response_time": 25.0,
            "session_count": 1,
            "bloom_level_achieved": "remember",
            "doubts": [],
        },
    }

    # Beginner concepts (mastery < 0.3) — just started
    beginner_geo = {
        "geology_human_impact": {
            "mastery": 0.15,
            "last_reviewed": (now - timedelta(days=1)).isoformat(),
            "successful_retrievals": 0,
            "total_attempts": 1,
            "correct_attempts": 0,
            "avg_response_time": 30.0,
            "session_count": 1,
            "bloom_level_achieved": "remember",
            "doubts": [
                {
                    "text": "Why does geology matter for city planning?",
                    "type": "causal",
                    "resolved": False,
                }
            ],
        },
        "solar_system_formation": {
            "mastery": 0.22,
            "last_reviewed": (now - timedelta(days=12)).isoformat(),  # Old — should trigger review
            "successful_retrievals": 0,
            "total_attempts": 2,
            "correct_attempts": 0,
            "avg_response_time": 28.0,
            "session_count": 1,
            "bloom_level_achieved": "remember",
            "doubts": [],
        },
    }

    # Not started (mastery 0) — advanced topics
    not_started_geo = [
        "lithosphere_definition",
        "asthenosphere_definition",
        "continental_vs_oceanic_crust",
        "mantle_convection",
        "plate_tectonics_introduction",
        "sinestia_theory",
        "isotopic_signatures",
        "moon_giant_impact_theory",
        "earth_water_origin",
    ]

    # Add all geology concepts
    for cid, data in {**mastered_geo, **intermediate_geo, **beginner_geo}.items():
        cs = ConceptState(
            concept_id=cid,
            mastery=data["mastery"],
            mastery_history=[data["mastery"]],
            last_reviewed=data.get("last_reviewed"),
            successful_retrievals=data.get("successful_retrievals", 0),
            doubts=data.get("doubts", []),
            bloom_level_achieved=data.get("bloom_level_achieved", "remember"),
            total_attempts=data.get("total_attempts", 0),
            correct_attempts=data.get("correct_attempts", 0),
            avg_response_time=data.get("avg_response_time", 0.0),
            session_count=data.get("session_count", 0),
        )
        learner.concepts[cid] = cs

    for cid in not_started_geo:
        learner.concepts[cid] = ConceptState(concept_id=cid)

    # ========================================================================
    # Course 2: Mamba and S4 (ML/DL course)
    # Simulating: user is more advanced here, strong on fundamentals,
    # working through advanced topics.
    # ========================================================================
    mamba_course = "Mamba and S4 Explained: Architecture, Parallel Scan, Kernel Fusion, Recurrent, Convolution, Math"
    learner.enrolled_courses.append(mamba_course)

    mastered_mamba = {
        "sequence_modeling": {
            "mastery": 0.92,
            "last_reviewed": (now - timedelta(days=2)).isoformat(),
            "successful_retrievals": 5,
            "total_attempts": 6,
            "correct_attempts": 5,
            "avg_response_time": 7.0,
            "session_count": 3,
            "bloom_level_achieved": "analyse",
            "doubts": [],
        },
        "recurrent_neural_network": {
            "mastery": 0.85,
            "last_reviewed": (now - timedelta(days=3)).isoformat(),
            "successful_retrievals": 4,
            "total_attempts": 5,
            "correct_attempts": 4,
            "avg_response_time": 9.0,
            "session_count": 2,
            "bloom_level_achieved": "apply",
            "doubts": [
                {
                    "text": "Why can't RNNs process sequences in parallel?",
                    "type": "procedural",
                    "resolved": True,
                    "resolution": "Each time step depends on the hidden state from the previous step (h_t = f(h_{t-1}, x_t)), creating a sequential dependency chain."
                }
            ],
        },
        "convolutional_neural_network": {
            "mastery": 0.78,
            "last_reviewed": (now - timedelta(days=4)).isoformat(),
            "successful_retrievals": 3,
            "total_attempts": 4,
            "correct_attempts": 3,
            "avg_response_time": 11.0,
            "session_count": 2,
            "bloom_level_achieved": "apply",
            "doubts": [],
        },
        "continuous_signals": {
            "mastery": 0.73,
            "last_reviewed": (now - timedelta(days=5)).isoformat(),
            "successful_retrievals": 3,
            "total_attempts": 3,
            "correct_attempts": 3,
            "avg_response_time": 10.0,
            "session_count": 1,
            "bloom_level_achieved": "understand",
            "doubts": [],
        },
        "discrete_signals": {
            "mastery": 0.71,
            "last_reviewed": (now - timedelta(days=5)).isoformat(),
            "successful_retrievals": 3,
            "total_attempts": 4,
            "correct_attempts": 3,
            "avg_response_time": 10.5,
            "session_count": 1,
            "bloom_level_achieved": "understand",
            "doubts": [],
        },
    }

    intermediate_mamba = {
        "rnn_hidden_state": {
            "mastery": 0.58,
            "last_reviewed": (now - timedelta(days=2)).isoformat(),
            "successful_retrievals": 2,
            "total_attempts": 4,
            "correct_attempts": 2,
            "avg_response_time": 15.0,
            "session_count": 1,
            "bloom_level_achieved": "understand",
            "doubts": [
                {
                    "text": "What information does the hidden state encode?",
                    "type": "definitional",
                    "resolved": True,
                    "resolution": "The hidden state is a compressed representation of all previous inputs in the sequence — it's the network's 'memory' of what it has seen so far."
                }
            ],
        },
        "transformer_model": {
            "mastery": 0.52,
            "last_reviewed": (now - timedelta(days=7)).isoformat(),  # Old — triggers review
            "successful_retrievals": 2,
            "total_attempts": 3,
            "correct_attempts": 2,
            "avg_response_time": 18.0,
            "session_count": 1,
            "bloom_level_achieved": "understand",
            "doubts": [
                {
                    "text": "Why do transformers use self-attention instead of convolution?",
                    "type": "causal",
                    "resolved": True,
                    "resolution": "Self-attention allows every token to attend to every other token directly, capturing long-range dependencies without the limited receptive field of convolutions."
                }
            ],
        },
        "state_space_models": {
            "mastery": 0.45,
            "last_reviewed": (now - timedelta(days=1)).isoformat(),
            "successful_retrievals": 1,
            "total_attempts": 3,
            "correct_attempts": 1,
            "avg_response_time": 22.0,
            "session_count": 1,
            "bloom_level_achieved": "remember",
            "doubts": [],
        },
        "vanishing_exploding_gradients": {
            "mastery": 0.40,
            "last_reviewed": (now - timedelta(days=9)).isoformat(),  # Old — triggers review
            "successful_retrievals": 1,
            "total_attempts": 3,
            "correct_attempts": 1,
            "avg_response_time": 20.0,
            "session_count": 1,
            "bloom_level_achieved": "remember",
            "doubts": [
                {
                    "text": "Why does the gradient vanish specifically in deep networks?",
                    "type": "causal",
                    "resolved": False,
                }
            ],
        },
    }

    beginner_mamba = {
        "self_attention_mechanism": {
            "mastery": 0.25,
            "last_reviewed": (now - timedelta(days=1)).isoformat(),
            "successful_retrievals": 0,
            "total_attempts": 2,
            "correct_attempts": 0,
            "avg_response_time": 25.0,
            "session_count": 1,
            "bloom_level_achieved": "remember",
            "doubts": [],
        },
        "differential_equations_introduction": {
            "mastery": 0.18,
            "last_reviewed": (now - timedelta(days=14)).isoformat(),  # Very old — high urgency review
            "successful_retrievals": 0,
            "total_attempts": 1,
            "correct_attempts": 0,
            "avg_response_time": 35.0,
            "session_count": 1,
            "bloom_level_achieved": "remember",
            "doubts": [],
        },
    }

    not_started_mamba = [
        "rnn_non_parallel_training",
        "rnn_constant_inference_cost",
        "transformer_parallel_training",
        "transformer_non_constant_inference_cost",
        "quadratic_scaling_transformer",
        "convolutional_kernel",
        "cnn_parallelizable_computation",
        "proportional_growth_model",
        "rate_of_change",
        "ideal_sequence_model_properties",
        "mamba_model",
    ]

    # Add all Mamba concepts
    for cid, data in {**mastered_mamba, **intermediate_mamba, **beginner_mamba}.items():
        cs = ConceptState(
            concept_id=cid,
            mastery=data["mastery"],
            mastery_history=[data["mastery"]],
            last_reviewed=data.get("last_reviewed"),
            successful_retrievals=data.get("successful_retrievals", 0),
            doubts=data.get("doubts", []),
            bloom_level_achieved=data.get("bloom_level_achieved", "remember"),
            total_attempts=data.get("total_attempts", 0),
            correct_attempts=data.get("correct_attempts", 0),
            avg_response_time=data.get("avg_response_time", 0.0),
            session_count=data.get("session_count", 0),
        )
        learner.concepts[cid] = cs

    for cid in not_started_mamba:
        learner.concepts[cid] = ConceptState(concept_id=cid)

    # ========================================================================
    # Add session history
    # ========================================================================
    learner.sessions = [
        {
            "session_id": "session_001",
            "concept_id": "geology_definition",
            "started_at": (now - timedelta(days=10)).isoformat(),
            "ended_at": (now - timedelta(days=10, hours=-1)).isoformat(),
            "doubts_raised": 1,
            "questions_attempted": 4,
            "questions_correct": 3,
            "mastery_before": 0.0,
            "mastery_after": 0.65,
            "bloom_level_tested": "understand",
        },
        {
            "session_id": "session_002",
            "concept_id": "geology_definition",
            "started_at": (now - timedelta(days=5)).isoformat(),
            "ended_at": (now - timedelta(days=5, hours=-1)).isoformat(),
            "doubts_raised": 0,
            "questions_attempted": 3,
            "questions_correct": 3,
            "mastery_before": 0.65,
            "mastery_after": 0.88,
            "bloom_level_tested": "apply",
        },
        {
            "session_id": "session_003",
            "concept_id": "sequence_modeling",
            "started_at": (now - timedelta(days=7)).isoformat(),
            "ended_at": (now - timedelta(days=7, hours=-1)).isoformat(),
            "doubts_raised": 0,
            "questions_attempted": 5,
            "questions_correct": 5,
            "mastery_before": 0.0,
            "mastery_after": 0.78,
            "bloom_level_tested": "understand",
        },
        {
            "session_id": "session_004",
            "concept_id": "recurrent_neural_network",
            "started_at": (now - timedelta(days=4)).isoformat(),
            "ended_at": (now - timedelta(days=4, hours=-1)).isoformat(),
            "doubts_raised": 1,
            "questions_attempted": 5,
            "questions_correct": 4,
            "mastery_before": 0.0,
            "mastery_after": 0.72,
            "bloom_level_tested": "apply",
        },
        {
            "session_id": "session_005",
            "concept_id": "transformer_model",
            "started_at": (now - timedelta(days=7)).isoformat(),
            "ended_at": (now - timedelta(days=7, hours=-1)).isoformat(),
            "doubts_raised": 1,
            "questions_attempted": 3,
            "questions_correct": 2,
            "mastery_before": 0.0,
            "mastery_after": 0.52,
            "bloom_level_tested": "understand",
        },
    ]

    # Save
    os.makedirs(LEARNERS_DIR, exist_ok=True)
    filepath = os.path.join(LEARNERS_DIR, "testuser.json")
    learner.save(filepath)

    # Print summary
    print("=" * 60)
    print("TestUser Population Complete")
    print("=" * 60)
    print(f"\n{learner.summary()}")

    # Count by mastery level
    mastered = [cid for cid, cs in learner.concepts.items() if cs.mastery >= 0.7]
    intermediate = [cid for cid, cs in learner.concepts.items() if 0.3 <= cs.mastery < 0.7]
    beginner = [cid for cid, cs in learner.concepts.items() if 0.0 < cs.mastery < 0.3]
    not_started = [cid for cid, cs in learner.concepts.items() if cs.mastery == 0.0]

    print(f"\n  Enrolled courses: {learner.enrolled_courses}")
    print(f"\n  Mastery distribution:")
    print(f"    Mastered (≥0.7):    {len(mastered)} concepts")
    print(f"    Intermediate:       {len(intermediate)} concepts")
    print(f"    Beginner (<0.3):    {len(beginner)} concepts")
    print(f"    Not started (0.0):  {len(not_started)} concepts")
    print(f"\n  Doubts: {learner.total_doubts} total ({learner.doubts_resolved} resolved)")
    print(f"  Sessions: {learner.total_sessions}")

    # Check which concepts should need review
    review_candidates = [(cid, cs) for cid, cs in learner.concepts.items()
                         if cs.mastery > 0.3 and cs.last_reviewed
                         and (now - datetime.fromisoformat(cs.last_reviewed)).days > 6]
    print(f"\n  Concepts likely needing review (>6 days old, mastery>0.3): {len(review_candidates)}")
    for cid, cs in review_candidates:
        days = (now - datetime.fromisoformat(cs.last_reviewed)).days
        print(f"    {cid}: mastery={cs.mastery}, last_reviewed={days}d ago")

    print(f"\n  Saved to: {filepath}")


if __name__ == "__main__":
    populate()

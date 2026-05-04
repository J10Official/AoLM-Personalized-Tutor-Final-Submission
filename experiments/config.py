"""
Experiment Configuration — shared constants for all experiment scripts.

Uses the existing TestUser data and the system's preprocessed courses.
The "student" LLM (gemma-3-27b) answers questions to simulate learners.
The "teacher" LLM (gemma-4-31b) runs the system agents.
"""

import os
import sys
import logging
import time

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

# LLM config
STUDENT_MODEL = "gemini/gemma-3-27b-it"     # Simulates student answers
TEACHER_MODEL = "gemini/gemma-4-31b-it"     # System agents (already configured)

# Data paths
DATA_DIR = os.path.join(PROJECT_ROOT, "backend", "data")
KG_PATH = os.path.join(DATA_DIR, "knowledge_graph.json")
LEARNER_PATH = os.path.join(DATA_DIR, "learners", "testuser.json")
RESULTS_DIR = os.path.join(PROJECT_ROOT, "experiments", "results")

# Experiment scale — set for comprehensive evaluation
NUM_CONCEPTS_PER_EXPERIMENT = 100  # Comprehensive evaluation across the KG
NUM_LEARNING_ITERATIONS = 5        # 5 learning iterations per concept
NUM_QUESTIONS_PER_CONCEPT = 5      # 5 questions per concept (full session)

# Ensure results directory
os.makedirs(RESULTS_DIR, exist_ok=True)


def setup_logging(name: str) -> logging.Logger:
    """Set up structured logging for an experiment."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)
    # Console handler with timestamps
    if not logger.handlers:
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        fmt = logging.Formatter("[%(asctime)s] %(levelname)s  %(message)s", datefmt="%H:%M:%S")
        ch.setFormatter(fmt)
        logger.addHandler(ch)
        # File handler
        fh = logging.FileHandler(os.path.join(RESULTS_DIR, f"{name}.log"), mode="w")
        fh.setLevel(logging.DEBUG)
        fh.setFormatter(logging.Formatter("[%(asctime)s] %(levelname)-8s %(message)s"))
        logger.addHandler(fh)
    return logger


def get_api_key():
    from dotenv import load_dotenv
    load_dotenv(os.path.join(DATA_DIR, "..", ".env"))
    return os.getenv("GOOGLE_API_KEY", "")


def load_knowledge_graph():
    from backend.core.knowledge_graph import KnowledgeGraph
    return KnowledgeGraph.load(KG_PATH)


def load_learner():
    from backend.core.learner_model import LearnerModel
    return LearnerModel.load(LEARNER_PATH)


def create_fresh_learner(learner_id="exp_learner"):
    """Create a fresh learner with no mastery for controlled experiments."""
    from backend.core.learner_model import LearnerModel
    lm = LearnerModel(learner_id=learner_id, name="Experiment Learner")
    return lm


def configure_student_lm():
    """Configure a DSPy LM for the student model (gemma-3-27b)."""
    import dspy
    api_key = get_api_key()
    lm = dspy.LM(STUDENT_MODEL, api_key=api_key, max_tokens=1024, temperature=0.7)
    return lm


def configure_teacher_lm():
    """Configure a DSPy LM for the teacher/system model."""
    import dspy
    api_key = get_api_key()
    lm = dspy.LM(TEACHER_MODEL, api_key=api_key, max_tokens=4096, temperature=0.3)
    dspy.configure(lm=lm)
    return lm


def timed(logger, msg):
    """Context manager that logs start/end with timing."""
    class Timer:
        def __init__(self):
            self.start = None
        def __enter__(self):
            logger.info(f"⏳ {msg}...")
            self.start = time.time()
            return self
        def __exit__(self, *args):
            elapsed = time.time() - self.start
            logger.info(f"✅ {msg} — {elapsed:.1f}s")
    return Timer()


def sample_concepts(kg, n=NUM_CONCEPTS_PER_EXPERIMENT, strategy="diverse"):
    """
    Sample n concepts from the KG with diversity:
    - Mix of difficulties (easy, medium, hard)
    - Must have descriptions
    """
    import random
    concepts = [(cid, c) for cid, c in kg.concepts.items() if c.description and len(c.description) > 20]

    if strategy == "diverse":
        easy = [(cid, c) for cid, c in concepts if c.difficulty < 0.4]
        medium = [(cid, c) for cid, c in concepts if 0.4 <= c.difficulty < 0.7]
        hard = [(cid, c) for cid, c in concepts if c.difficulty >= 0.7]

        sampled = []
        for bucket in [easy, medium, hard]:
            if bucket:
                random.shuffle(bucket)
                sampled.extend(bucket[:max(1, n // 3 + 1)])

        random.shuffle(sampled)
        return sampled[:n]
    else:
        random.shuffle(concepts)
        return concepts[:n]

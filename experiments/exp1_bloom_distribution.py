"""
Experiment 1: Bloom's Level Distribution vs Mastery

Measures whether the system correctly targets Bloom's taxonomy levels
based on the learner's mastery. At low mastery, questions should be
remember/understand; at high mastery, evaluate/create.

Metric: Alignment score between expected and actual Bloom distributions.
"""

import json
import os
import sys
import dspy
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments.config import (
    configure_teacher_lm, load_knowledge_graph, create_fresh_learner,
    sample_concepts, RESULTS_DIR, setup_logging, timed
)

log = setup_logging("exp1")

EXPECTED_BLOOM = {
    "beginner":     {"remember": 0.4, "understand": 0.4, "apply": 0.15, "analyse": 0.05, "evaluate": 0, "create": 0},
    "intermediate": {"remember": 0.05, "understand": 0.15, "apply": 0.35, "analyse": 0.35, "evaluate": 0.1, "create": 0},
    "advanced":     {"remember": 0, "understand": 0.05, "apply": 0.1, "analyse": 0.2, "evaluate": 0.35, "create": 0.3},
}


def run_bloom_experiment():
    log.info("=" * 60)
    log.info("EXPERIMENT 1: Bloom Distribution vs Mastery")
    log.info("=" * 60)

    with timed(log, "Configuring LM"):
        lm = configure_teacher_lm()
    kg = load_knowledge_graph()

    from backend.agents.question_generator import QuestionGeneratorAgent
    qgen = QuestionGeneratorAgent(kg)

    results = {"beginner": [], "intermediate": [], "advanced": []}
    concepts = sample_concepts(kg, n=2, strategy="diverse")
    log.info(f"Sampled {len(concepts)} concepts")

    levels = [("beginner", 0.15), ("intermediate", 0.45), ("advanced", 0.75)]
    tasks = [(level, mastery, cid, c) for level, mastery in levels for cid, c in concepts[:1]]

    for level, mastery_val, cid, concept in tqdm(tasks, desc="Bloom tests"):
        learner = create_fresh_learner(f"bloom_{level}")
        learner.get_concept_state(cid).mastery = mastery_val
        learner.enroll_in_course("experiment", [cid])

        with timed(log, f"[{level}] {concept.name}"):
            try:
                result = qgen.generate(learner, cid)
                questions = result.get("questions", [])
                bloom_levels = [q.get("bloom_level", "understand") for q in questions]
                results[level].extend(bloom_levels)
                log.info(f"  {len(questions)} questions: {bloom_levels}")
            except Exception as e:
                log.error(f"  Error: {e}")

    # Compute distribution & alignment
    bloom_dists = {}
    alignment_scores = {}
    for level, blooms in results.items():
        total = len(blooms) if blooms else 1
        dist = {b: round(blooms.count(b) / total, 3) for b in ["remember", "understand", "apply", "analyse", "evaluate", "create"]}
        bloom_dists[level] = dist
        expected = EXPECTED_BLOOM[level]
        l1 = sum(abs(expected.get(b, 0) - dist.get(b, 0)) for b in expected)
        alignment_scores[level] = round(1.0 - l1 / 2.0, 3)

    report = {
        "experiment": "bloom_distribution_vs_mastery",
        "actual_distributions": bloom_dists,
        "expected_distributions": EXPECTED_BLOOM,
        "alignment_scores": alignment_scores,
        "mean_alignment": round(sum(alignment_scores.values()) / 3, 3),
        "raw_counts": {k: len(v) for k, v in results.items()},
    }

    out_path = os.path.join(RESULTS_DIR, "exp1_bloom_distribution.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    log.info("")
    log.info("Bloom Alignment Scores:")
    for level, score in alignment_scores.items():
        log.info(f"  {level:15s}: {score:.3f}")
    log.info(f"  {'Mean':15s}: {report['mean_alignment']:.3f}")
    log.info(f"Results → {out_path}")
    return report


if __name__ == "__main__":
    run_bloom_experiment()

"""
Experiment 5: Pedagogical Faithfulness — LLM-Based Evaluation

Tests whether the system adheres to its core pedagogical principles:
1. Constructivist Constraint: Do doubt resolutions only use known concepts?
2. Misconception Detection: Does the system correctly flag wrong answers?
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

log = setup_logging("exp5")


class ConstructivistJudgeSignature(dspy.Signature):
    """Judge whether a doubt resolution follows the constructivist constraint."""
    doubt: str = dspy.InputField()
    answer: str = dspy.InputField()
    known_concepts: str = dspy.InputField(desc="Concepts the learner already knows")
    concept_being_learned: str = dspy.InputField()

    uses_only_known: bool = dspy.OutputField(desc="True if answer only uses known concepts + the current concept")
    introduced_unknown: str = dspy.OutputField(desc="Unknown concepts introduced, or 'none'")
    scaffolding_score: int = dspy.OutputField(desc="1-5: builds from simple to complex")
    clarity_score: int = dspy.OutputField(desc="1-5: how clear and understandable")
    reasoning: str = dspy.OutputField(desc="Brief justification")


class MisconceptionJudgeSignature(dspy.Signature):
    """Judge whether the system correctly detected a misconception."""
    question: str = dspy.InputField()
    correct_answer: str = dspy.InputField()
    wrong_answer: str = dspy.InputField()
    system_feedback: str = dspy.InputField()

    detection_correct: bool = dspy.OutputField(desc="True if system correctly identified the answer was wrong")
    feedback_helpful: int = dspy.OutputField(desc="1-5: how helpful for learning from the mistake")
    misconception_analysis_quality: int = dspy.OutputField(desc="1-5: quality of misunderstanding diagnosis")


def run_pedagogical_faithfulness():
    log.info("=" * 60)
    log.info("EXPERIMENT 5: Pedagogical Faithfulness Audit")
    log.info("=" * 60)

    with timed(log, "Configuring LM"):
        lm = configure_teacher_lm()
    kg = load_knowledge_graph()

    from backend.agents.doubt_resolver import DoubtResolverAgent
    from backend.agents.question_generator import QuestionGeneratorAgent
    from backend.agents.evaluator import EvaluatorAgent

    doubt_resolver = DoubtResolverAgent(kg)
    qgen = QuestionGeneratorAgent(kg)
    evaluator = EvaluatorAgent(kg)
    constructivist_judge = dspy.ChainOfThought(ConstructivistJudgeSignature)
    misconception_judge = dspy.ChainOfThought(MisconceptionJudgeSignature)

    # Select 1 concept with prerequisites
    import random
    concepts_with_prereqs = [(cid, c) for cid, c in kg.concepts.items()
                              if c.prerequisites and c.description and len(c.description) > 20]
    random.shuffle(concepts_with_prereqs)
    concepts = concepts_with_prereqs[:1]
    log.info(f"Selected {len(concepts)} concept(s) with prerequisites")

    # ===== Test A: Constructivist Constraint =====
    log.info("\n--- Test A: Constructivist Constraint ---")
    constructivist_results = []

    for cid, concept in tqdm(concepts, desc="Constructivist"):
        learner = create_fresh_learner(f"faith_A_{cid}")
        known_names = []
        for pid in concept.prerequisites:
            pc = kg.get_concept(pid)
            if pc:
                learner.get_concept_state(pid).mastery = 0.6
                known_names.append(pc.name)
        learner.get_concept_state(cid).mastery = 0.2
        learner.enroll_in_course("experiment", [cid] + concept.prerequisites)

        doubt_text = f"I don't understand how {concept.name} works. Can you explain the key idea?"

        with timed(log, f"Doubt resolution: {concept.name}"):
            try:
                result = doubt_resolver.resolve(learner, cid, doubt_text)
                answer = result.get("answer", "")
            except Exception as e:
                log.error(f"  Doubt error: {e}")
                constructivist_results.append({"concept": concept.name, "error": str(e)})
                continue

        with timed(log, f"Judging constructivism"):
            try:
                judgement = constructivist_judge(
                    doubt=doubt_text, answer=answer[:2000],
                    known_concepts=", ".join(known_names) if known_names else "none",
                    concept_being_learned=concept.name,
                )
                entry = {
                    "concept": concept.name, "known_concepts": known_names,
                    "uses_only_known": bool(judgement.uses_only_known),
                    "introduced_unknown": judgement.introduced_unknown,
                    "scaffolding_score": int(judgement.scaffolding_score),
                    "clarity_score": int(judgement.clarity_score),
                    "reasoning": judgement.reasoning,
                }
                constructivist_results.append(entry)
                log.info(f"  Only known: {entry['uses_only_known']}, Scaffold: {entry['scaffolding_score']}/5")
            except Exception as e:
                log.error(f"  Judge error: {e}")
                constructivist_results.append({"concept": concept.name, "error": str(e)})

    # ===== Test B: Misconception Detection =====
    log.info("\n--- Test B: Misconception Detection ---")
    misconception_results = []

    for cid, concept in tqdm(concepts, desc="Misconception"):
        learner = create_fresh_learner(f"faith_B_{cid}")
        learner.get_concept_state(cid).mastery = 0.4
        learner.enroll_in_course("experiment", [cid])

        with timed(log, f"QGen for misconception: {concept.name}"):
            try:
                q_result = qgen.generate(learner, cid)
                questions = q_result.get("questions", [])
                written_q = next((q for q in questions if q.get("type") == "written"), questions[0] if questions else None)
            except Exception as e:
                log.error(f"  QGen error: {e}")
                continue

        if not written_q:
            continue

        wrong_answer = f"I think {concept.name} is basically the same as sorting numbers."

        with timed(log, f"Evaluating wrong answer"):
            try:
                eval_result = evaluator.evaluate(learner=learner, concept_id=cid, question=written_q,
                                                  student_answer=wrong_answer, response_time=10.0)
            except Exception as e:
                log.error(f"  Eval error: {e}")
                continue

        with timed(log, f"Judging misconception detection"):
            try:
                judgement = misconception_judge(
                    question=written_q.get("question", ""), correct_answer=written_q.get("correct_answer", ""),
                    wrong_answer=wrong_answer, system_feedback=eval_result.get("feedback", ""),
                )
                entry = {
                    "concept": concept.name, "detection_correct": bool(judgement.detection_correct),
                    "feedback_helpful": int(judgement.feedback_helpful),
                    "misconception_analysis": int(judgement.misconception_analysis_quality),
                    "system_score": eval_result.get("normalised_score", 0),
                }
                misconception_results.append(entry)
                log.info(f"  Detected: {entry['detection_correct']}, Feedback: {entry['feedback_helpful']}/5")
            except Exception as e:
                log.error(f"  Judge error: {e}")

    # Aggregate
    safe_avg = lambda lst, key: round(sum(x[key] for x in lst if key in x and isinstance(x[key], (int, float))) / max(1, len([x for x in lst if key in x])), 2)

    summary = {
        "constructivist": {
            "adherence_rate": round(sum(1 for r in constructivist_results if r.get("uses_only_known", False)) / max(1, len(constructivist_results)), 2),
            "avg_scaffolding": safe_avg(constructivist_results, "scaffolding_score"),
            "avg_clarity": safe_avg(constructivist_results, "clarity_score"),
        },
        "misconception": {
            "detection_rate": round(sum(1 for r in misconception_results if r.get("detection_correct", False)) / max(1, len(misconception_results)), 2),
            "avg_feedback_helpfulness": safe_avg(misconception_results, "feedback_helpful"),
            "avg_analysis_quality": safe_avg(misconception_results, "misconception_analysis"),
        },
    }

    report = {"experiment": "pedagogical_faithfulness",
              "constructivist_results": constructivist_results,
              "misconception_results": misconception_results, "summary": summary}

    out_path = os.path.join(RESULTS_DIR, "exp5_pedagogical_faithfulness.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    log.info("")
    log.info(f"Constructivist Adherence: {summary['constructivist']['adherence_rate']:.0%}")
    log.info(f"Avg Scaffolding: {summary['constructivist']['avg_scaffolding']}/5")
    log.info(f"Misconception Detection: {summary['misconception']['detection_rate']:.0%}")
    log.info(f"Results → {out_path}")
    return report


if __name__ == "__main__":
    run_pedagogical_faithfulness()

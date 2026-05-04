"""
Experiment 4: Mastery Evolution Over Learning Iterations (KG vs No-KG)

Simulates a student (gemma-3-27b) going through learning iterations.
Tracks mastery evolution with and without KG.
"""

import json
import os
import sys
import dspy
from tqdm import tqdm

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from experiments.config import (
    configure_teacher_lm, configure_student_lm, load_knowledge_graph,
    create_fresh_learner, sample_concepts, RESULTS_DIR,
    NUM_LEARNING_ITERATIONS, setup_logging, timed
)

log = setup_logging("exp4")


class StudentAnswerSignature(dspy.Signature):
    """You are a student who just read an explanation. Answer the question based ONLY on what you learned."""
    explanation: str = dspy.InputField(desc="The explanation you just read")
    question: str = dspy.InputField(desc="The question to answer")
    question_type: str = dspy.InputField(desc="'mcq' or 'written'")
    options: str = dspy.InputField(desc="For MCQ: the options. For written: 'N/A'")

    answer: str = dspy.OutputField(desc="Your answer. For MCQ: the letter+text. For written: 2-3 sentences.")


def run_mastery_evolution():
    log.info("=" * 60)
    log.info("EXPERIMENT 4: Mastery Evolution (KG vs No-KG)")
    log.info("=" * 60)

    with timed(log, "Configuring LMs"):
        teacher_lm = configure_teacher_lm()
        student_lm = configure_student_lm()

    kg = load_knowledge_graph()

    from backend.agents.source_curator import SourceCuratorAgent
    from backend.agents.learning_curator import LearningCuratorAgent
    from backend.agents.question_generator import QuestionGeneratorAgent
    from backend.agents.evaluator import EvaluatorAgent
    from backend.core.mastery_engine import MasteryEngine
    from backend.core.knowledge_graph import KnowledgeGraph, ConceptNode

    concepts = sample_concepts(kg, n=1, strategy="diverse")
    log.info(f"Sampled {len(concepts)} concept(s), {NUM_LEARNING_ITERATIONS} iterations")

    all_results = []

    for mode in tqdm(["with_kg", "without_kg"], desc="Modes"):
        ablation = (mode == "without_kg")
        log.info(f"\n--- Mode: {mode} ---")

        if ablation:
            minimal_kg = KnowledgeGraph()
            for cid, c in concepts:
                minimal_kg.concepts[cid] = ConceptNode(
                    id=cid, name=c.name, description=c.description,
                    difficulty=c.difficulty, bloom_ceiling=c.bloom_ceiling,
                    prerequisites=[], related_concepts=[], lecture_source=c.lecture_source,
                )
            active_kg = minimal_kg
        else:
            active_kg = kg

        source_curator = SourceCuratorAgent(active_kg)
        learning_curator = LearningCuratorAgent(active_kg)
        qgen = QuestionGeneratorAgent(active_kg)
        evaluator = EvaluatorAgent(active_kg)
        mastery_engine = MasteryEngine(active_kg, ablation_no_kg=ablation)
        student_answerer = dspy.ChainOfThought(StudentAnswerSignature)

        for cid, concept in concepts:
            learner = create_fresh_learner(f"evo_{mode}_{cid}")
            learner.enroll_in_course("experiment", [cid])
            mastery_trajectory = [0.0]
            score_trajectory = []

            for iteration in tqdm(range(NUM_LEARNING_ITERATIONS), desc=f"{concept.name[:15]} ({mode})", leave=False):
                log.info(f"  [{mode}] {concept.name} — iter {iteration+1}")

                # 1. Generate explanation
                with timed(log, f"  Explain iter {iteration+1}"):
                    try:
                        with dspy.context(lm=teacher_lm):
                            src = source_curator.curate(learner, cid)
                            session = learning_curator.create_session(learner, cid, source_material=src.get("curated_document", concept.description))
                            explanation = session.get("explanation", concept.description)
                    except Exception as e:
                        log.error(f"  Explain error: {e}")
                        explanation = concept.description

                # 2. Generate 1 question
                with timed(log, f"  Question iter {iteration+1}"):
                    try:
                        with dspy.context(lm=teacher_lm):
                            q_result = qgen.generate(learner, cid)
                            questions = q_result.get("questions", [])[:1]
                    except Exception as e:
                        log.error(f"  QGen error: {e}")
                        questions = []

                if not questions:
                    continue

                q = questions[0]
                q_type = q.get("type", "written")
                options_str = "N/A"
                if q_type == "mcq" and q.get("options"):
                    options_str = "\n".join(f"{chr(65+i)}. {opt}" for i, opt in enumerate(q["options"]))

                # 3. Student answers
                with timed(log, f"  Student answer iter {iteration+1}"):
                    try:
                        with dspy.context(lm=student_lm):
                            resp = student_answerer(
                                explanation=explanation[:3000], question=q.get("question", ""),
                                question_type=q_type, options=options_str,
                            )
                        student_answer = resp.answer
                    except Exception as e:
                        student_answer = "I don't know"
                        log.error(f"  Student error: {e}")

                # 4. Evaluate
                with timed(log, f"  Evaluate iter {iteration+1}"):
                    try:
                        with dspy.context(lm=teacher_lm):
                            ev = evaluator.evaluate(learner=learner, concept_id=cid, question=q,
                                                    student_answer=student_answer, response_time=15.0)
                        score = ev.get("normalised_score", 0.0)
                        correct = ev.get("is_correct", False)
                    except Exception as e:
                        score, correct = 0.0, False

                # 5. Update mastery
                new_mastery = mastery_engine.update_mastery(learner=learner, concept_id=cid,
                                                            score=score, correct=correct, response_time=15.0)
                mastery_trajectory.append(round(new_mastery, 4))
                score_trajectory.append(round(score, 4))
                log.info(f"    Score={score:.2f}, Mastery={new_mastery:.4f}")

            all_results.append({
                "mode": mode, "concept_id": cid, "concept_name": concept.name,
                "mastery_trajectory": mastery_trajectory, "score_trajectory": score_trajectory,
                "final_mastery": mastery_trajectory[-1],
                "mastery_gain": round(mastery_trajectory[-1] - mastery_trajectory[0], 4),
            })

    avg = lambda lst: round(sum(lst) / len(lst), 4) if lst else 0
    wk_gains = [r["mastery_gain"] for r in all_results if r["mode"] == "with_kg"]
    nk_gains = [r["mastery_gain"] for r in all_results if r["mode"] == "without_kg"]

    summary = {
        "with_kg_avg_gain": avg(wk_gains),
        "without_kg_avg_gain": avg(nk_gains),
        "kg_advantage": round(avg(wk_gains) - avg(nk_gains), 4),
    }

    report = {"experiment": "mastery_evolution", "iterations": NUM_LEARNING_ITERATIONS,
              "per_concept_results": all_results, "summary": summary}

    out_path = os.path.join(RESULTS_DIR, "exp4_mastery_evolution.json")
    with open(out_path, "w") as f:
        json.dump(report, f, indent=2)

    log.info("")
    log.info(f"With KG gain:    {summary['with_kg_avg_gain']:.4f}")
    log.info(f"Without KG gain: {summary['without_kg_avg_gain']:.4f}")
    log.info(f"KG advantage:    {summary['kg_advantage']:+.4f}")
    log.info(f"Results → {out_path}")
    return report


if __name__ == "__main__":
    run_mastery_evolution()

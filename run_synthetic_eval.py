import os
import time
import json
import textstat
from backend.core.learner_model import LearnerModel, ConceptState
from backend.core.knowledge_graph import KnowledgeGraph
from backend.agents.learning_curator import LearningCuratorAgent
from backend.agents.doubt_resolver import DoubtResolverAgent
from backend.agents.question_generator import QuestionGeneratorAgent
import dspy
from dotenv import load_dotenv

load_dotenv(os.path.join("backend", ".env"))

DATA_DIR = "backend/data"
EXP_DIR = "experiments"
os.makedirs(EXP_DIR, exist_ok=True)

llm_model = os.getenv("LLM_MODEL", "gemini/gemini-3-flash-preview")
api_key = os.getenv("GOOGLE_API_KEY", "")
lm = dspy.LM(llm_model, api_key=api_key)
dspy.configure(lm=lm)

kg = KnowledgeGraph.load(os.path.join(DATA_DIR, "knowledge_graph.json"))

learning_curator = LearningCuratorAgent(kg)
doubt_resolver = DoubtResolverAgent(kg)
q_generator = QuestionGeneratorAgent(kg)

beginner = LearnerModel(learner_id="eval_beginner")
advanced = LearnerModel(learner_id="eval_advanced")

concept_id = "geology_definition"  
concept = kg.get_concept(concept_id)

if not concept:
    print(f"Concept {concept_id} not found in KG. Exiting.")
    exit(1)

course = next((c for c in kg.courses if c.course_name == "Crash Course Geology"), None)
concept_ids = course.concept_ids if course else []

beginner.enroll_in_course("Crash Course Geology", concept_ids)
advanced.enroll_in_course("Crash Course Geology", concept_ids)

# Set Mastery
beginner.get_concept_state(concept_id).mastery = 0.1
advanced.get_concept_state(concept_id).mastery = 0.8

results = {
    "model": llm_model,
    "timestamp": time.time(),
    "metrics": {
        "readability": {},
        "doubt_resolver": {},
        "efficiency": {}
    }
}

print("Running Learning Curator for Beginner...")
t0 = time.time()
beg_session = learning_curator.create_session(beginner, concept_id)
beg_time = time.time() - t0
beg_readability = textstat.flesch_kincaid_grade(beg_session["explanation"])

time.sleep(3)

print("Running Learning Curator for Advanced...")
t0 = time.time()
adv_session = learning_curator.create_session(advanced, concept_id)
adv_time = time.time() - t0
adv_readability = textstat.flesch_kincaid_grade(adv_session["explanation"])

results["metrics"]["readability"] = {
    "beginner_grade_level": beg_readability,
    "advanced_grade_level": adv_readability,
    "beginner_explanation_sample": beg_session["explanation"][:200],
    "advanced_explanation_sample": adv_session["explanation"][:200]
}
results["metrics"]["efficiency"]["learning_curator_avg_time"] = (beg_time + adv_time) / 2

time.sleep(3)

print("Running Doubt Resolver...")
doubt_text = "Wait, isn't geology just looking at rocks? What else is there?"
t0 = time.time()
doubt_res = doubt_resolver.resolve(beginner, concept_id, doubt_text)
doubt_time = time.time() - t0

results["metrics"]["doubt_resolver"] = {
    "doubt": doubt_text,
    "misconception_type": doubt_res["misconception_type"],
    "answer_sample": doubt_res["answer"],
    "time_taken": doubt_time
}

time.sleep(3)

print("Running Question Generator for Beginner...")
t0 = time.time()
q_res = q_generator.generate(beginner, concept_id)
q_time = time.time() - t0

bloom_levels = [q.get("bloom_level") for q in q_res["questions"]]
results["metrics"]["question_generator"] = {
    "beginner_bloom_distribution": bloom_levels,
    "time_taken": q_time
}

out_path = os.path.join(EXP_DIR, f"eval_results_{int(time.time())}.json")
with open(out_path, "w") as f:
    json.dump(results, f, indent=2)

print(f"\nEvaluation complete! Results saved to {out_path}")
print(json.dumps(results, indent=2))

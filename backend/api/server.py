"""
FastAPI Server for the Personalised Learning System.

Provides REST API endpoints for the frontend to interact with all agents,
the knowledge graph, learner profiles, and mastery engine.

Agents wired (per slides architecture):
1. Recommender          → /api/learner/{id}/recommendations
2. Source Curator       → used internally by /api/session/start
3. Learning Curator     → /api/session/start
4. Doubt Resolver       → /api/doubt/resolve
5. Question Generator   → /api/learner/{id}/questions/{concept_id}
6. Evaluator            → /api/evaluate

Plus: Mastery Engine (Agent 7) updates on every evaluation.
"""

import os
import json
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from backend.core.knowledge_graph import KnowledgeGraph
from backend.core.learner_model import LearnerModel, ConceptState, SessionLog
from backend.core.mastery_engine import MasteryEngine

# Globals
kg: KnowledgeGraph = None
learners: dict[str, LearnerModel] = {}
mastery_engine: MasteryEngine = None
DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data")

# Flywheel for Human-in-the-Loop data collection
from backend.data.flywheel import FlywheelStore
flywheel_store: FlywheelStore = None

# --- DSPy setup (lazy, so server starts even without API key) ---
dspy_configured = False
recommender_agent = None
source_curator_agent = None
learning_curator_agent = None
doubt_resolver_agent = None
question_generator_agent = None
evaluator_agent = None

# --- Ablation Mode ---
# When ABLATION_NO_KG=true, the system bypasses KG-dependent personalisation:
#   - No prerequisite-aware recommendations
#   - No ZPD targeting (random concept selection)
#   - No forgetting curve KG connection bonuses
#   - No prerequisite penalty propagation
# This enables controlled A/B ablation studies.
ABLATION_NO_KG = os.getenv("ABLATION_NO_KG", "false").lower() in ("true", "1", "yes")
if ABLATION_NO_KG:
    print("⚠️  ABLATION MODE: Knowledge graph personalisation DISABLED")


def configure_dspy():
    """Configure DSPy with cloud API. Call once when first needed."""
    global dspy_configured, recommender_agent, source_curator_agent
    global learning_curator_agent, doubt_resolver_agent
    global question_generator_agent, evaluator_agent

    if dspy_configured:
        return

    try:
        from backend.core.llm_config import configure_dspy_lm
        lm = configure_dspy_lm()

        if lm:
            dspy_configured = True

            from backend.agents.recommender import RecommenderAgent
            from backend.agents.source_curator import SourceCuratorAgent
            from backend.agents.learning_curator import LearningCuratorAgent
            from backend.agents.doubt_resolver import DoubtResolverAgent
            from backend.agents.question_generator import QuestionGeneratorAgent
            from backend.agents.evaluator import EvaluatorAgent

            recommender_agent = RecommenderAgent(kg)
            source_curator_agent = SourceCuratorAgent(kg)
            learning_curator_agent = LearningCuratorAgent(kg)
            doubt_resolver_agent = DoubtResolverAgent(kg)
            question_generator_agent = QuestionGeneratorAgent(kg)
            evaluator_agent = EvaluatorAgent(kg)
            print("All 6 agents initialised successfully")
        else:
            print("WARNING: No API key found. LLM features disabled.")
    except Exception as e:
        print(f"WARNING: DSPy configuration failed: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: load knowledge graph and any saved learner profiles."""
    global kg, mastery_engine, flywheel_store

    # Load knowledge graph if it exists; otherwise start empty
    kg_path = os.path.join(DATA_DIR, "knowledge_graph.json")
    if os.path.exists(kg_path):
        kg = KnowledgeGraph.load(kg_path)
        print(f"Loaded existing knowledge graph. {kg.summary()}")
    else:
        kg = KnowledgeGraph()
        print("No knowledge graph found. Ingest a course via POST /api/course/ingest")

    mastery_engine = MasteryEngine(kg, ablation_no_kg=ABLATION_NO_KG)

    # Initialise flywheel store
    flywheel_store = FlywheelStore()
    print(f"Flywheel initialised. {flywheel_store.get_stats()['total_interactions']} interactions loaded.")

    # Load saved learner profiles
    learners_dir = os.path.join(DATA_DIR, "learners")
    if os.path.exists(learners_dir):
        for fname in os.listdir(learners_dir):
            if fname.endswith(".json"):
                lm = LearnerModel.load(os.path.join(learners_dir, fname))
                learners[lm.learner_id] = lm

    print(f"Loaded {len(learners)} learner profiles.")
    yield
    # Shutdown: save all profiles
    for lid, lm in learners.items():
        save_learner(lm)


app = FastAPI(
    title="Personalised Learning System",
    description="AI-powered adaptive learning with deep conceptual focus",
    version="0.4.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== Structured Logging ==========
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

API_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "logs")
os.makedirs(API_LOG_DIR, exist_ok=True)

# File handler — structured API logs
_log_file = os.path.join(API_LOG_DIR, f"backend_api.log")
_file_handler = logging.FileHandler(_log_file, mode="a")
_file_handler.setFormatter(logging.Formatter("%(asctime)s | %(levelname)s | %(message)s"))

# Console handler
_console_handler = logging.StreamHandler()
_console_handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s", datefmt="%H:%M:%S"))

api_logger = logging.getLogger("deeplearn.api")
api_logger.setLevel(logging.INFO)
api_logger.addHandler(_file_handler)
api_logger.addHandler(_console_handler)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every API request and response status."""
    async def dispatch(self, request: Request, call_next):
        start = time.time()
        method = request.method
        path = request.url.path
        try:
            response = await call_next(request)
            elapsed = (time.time() - start) * 1000
            api_logger.info(f"{method} {path} → {response.status_code} ({elapsed:.0f}ms)")
            return response
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            api_logger.error(f"{method} {path} → ERROR ({elapsed:.0f}ms): {e}")
            raise

app.add_middleware(RequestLoggingMiddleware)


def save_learner(learner: LearnerModel):
    learners_dir = os.path.join(DATA_DIR, "learners")
    os.makedirs(learners_dir, exist_ok=True)
    learner.save(os.path.join(learners_dir, f"{learner.learner_id}.json"))


def get_learner(learner_id: str) -> LearnerModel:
    if learner_id not in learners:
        raise HTTPException(status_code=404, detail=f"Learner '{learner_id}' not found")
    return learners[learner_id]


def _load_concept_sources() -> dict:
    """Load concept-to-transcript mapping from raw/concept_sources.json."""
    sources_path = os.path.join(DATA_DIR, "raw", "concept_sources.json")
    if os.path.exists(sources_path):
        with open(sources_path, "r") as f:
            return json.load(f)
    return {}


# ========== Pydantic Models ==========

class CreateLearnerRequest(BaseModel):
    learner_id: str
    name: str = ""

class DoubtRequest(BaseModel):
    learner_id: str
    concept_id: str
    doubt: str

class AnswerRequest(BaseModel):
    learner_id: str
    concept_id: str
    question: dict
    answer: str
    response_time: float  # seconds

class SessionStartRequest(BaseModel):
    learner_id: str
    concept_id: str

class CourseIngestRequest(BaseModel):
    youtube_url: str = ""
    topic: str = ""       # Alternative: search by topic instead of URL
    learner_id: str       # Which user is adding this course


# ========== Endpoints ==========

@app.get("/api/health")
async def health():
    return {
        "status": "ok",
        "dspy_configured": dspy_configured,
        "concepts": len(kg.concepts) if kg else 0,
        "course_name": kg.course_name if kg else None,
        "has_graph": kg is not None and len(kg.concepts) > 0,
        "total_courses": len(kg.courses) if kg else 0,
        "ablation_mode": ABLATION_NO_KG,
    }


# --- Course Ingestion ---

@app.post("/api/course/ingest")
async def ingest_course(req: CourseIngestRequest):
    """
    Ingest a YouTube video/playlist OR search by topic to build/update the knowledge graph.

    - If youtube_url is provided: uses existing URL-based flow
    - If topic is provided: searches YouTube for best lectures, then ingests
    - If the course was already ingested, skips re-processing and just enrolls the user.
    - Auto-enrolls the requesting user in all course concepts at mastery 0.
    """
    global kg, mastery_engine

    # Validate: must provide either youtube_url or topic
    if not req.youtube_url and not req.topic:
        raise HTTPException(status_code=400, detail="Must provide either 'youtube_url' or 'topic'.")

    # Verify learner exists
    if req.learner_id not in learners:
        raise HTTPException(status_code=404, detail=f"Learner '{req.learner_id}' not found. Create profile first.")

    learner = learners[req.learner_id]

    from backend.data.rag_pipeline import run_rag_pipeline, run_rag_pipeline_from_topic

    try:
        if req.topic and not req.youtube_url:
            # Topic-based search: find videos, then extract concepts
            updated_kg, concept_ids, already_ingested = run_rag_pipeline_from_topic(
                req.topic,
                existing_kg=kg,
            )
        else:
            # URL-based flow (existing)
            updated_kg, concept_ids, already_ingested = run_rag_pipeline(
                req.youtube_url,
                existing_kg=kg,
            )
    except Exception as e:
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    # Update the global knowledge graph
    kg = updated_kg
    mastery_engine = MasteryEngine(kg, ablation_no_kg=ABLATION_NO_KG)

    # Enroll the user in all course concepts (mastery 0 for new ones)
    course_name = kg.course_name or "Unknown"
    newly_enrolled = learner.enroll_in_course(course_name, concept_ids)
    save_learner(learner)

    # Re-initialise DSPy agents with updated graph (if configured)
    global dspy_configured
    if dspy_configured:
        dspy_configured = False  # Force re-init with new KG
        configure_dspy()

    return {
        "status": "success",
        "course_name": course_name,
        "channel": kg.channel or "",
        "already_ingested": already_ingested,
        "lectures_found": len(kg.lectures),
        "concepts_extracted": len(concept_ids),
        "concepts_enrolled": len(newly_enrolled),
        "graph_summary": kg.summary(),
    }


# --- Knowledge Graph ---

@app.get("/api/graph")
async def get_graph():
    """Return the full knowledge graph for visualisation."""
    nodes = []
    edges = []
    for cid, concept in kg.concepts.items():
        nodes.append({
            "id": cid,
            "name": concept.name,
            "difficulty": concept.difficulty,
            "bloom_ceiling": concept.bloom_ceiling.value,
            "lecture": concept.lecture_source,
            "description": concept.description
        })
        for pid in concept.prerequisites:
            edges.append({"source": pid, "target": cid, "type": "prerequisite"})
        for rid in concept.related_concepts:
            if rid in kg.concepts:
                edges.append({"source": cid, "target": rid, "type": "related"})

    return {
        "nodes": nodes,
        "edges": edges,
        "course_name": kg.course_name,
        "channel": kg.channel,
        "lectures": kg.lectures,
        "courses": [c.to_dict() for c in kg.courses],
    }

@app.get("/api/learner/{learner_id}/graph")
async def get_learner_graph(learner_id: str):
    """Return the personalized knowledge graph subset for the learner's enrolled courses."""
    lm = get_learner(learner_id)
    enrolled_ids = set(lm.concepts.keys())
    
    nodes = []
    edges = []
    for cid in enrolled_ids:
        concept = kg.get_concept(cid)
        if not concept:
            continue
        nodes.append({
            "id": cid,
            "name": concept.name,
            "difficulty": concept.difficulty,
            "bloom_ceiling": concept.bloom_ceiling.value,
            "lecture": concept.lecture_source,
            "description": concept.description
        })
        # Only add edges if BOTH nodes are in the enrolled_ids set
        for pid in concept.prerequisites:
            if pid in enrolled_ids:
                edges.append({"source": pid, "target": cid, "type": "prerequisite"})
        for rid in concept.related_concepts:
            if rid in enrolled_ids:
                edges.append({"source": cid, "target": rid, "type": "related"})

    return {
        "nodes": nodes,
        "edges": edges,
        "courses": [c.to_dict() for c in kg.courses if lm.is_enrolled_in(c.course_name)],
    }


@app.get("/api/graph/concept/{concept_id}")
async def get_concept(concept_id: str):
    concept = kg.get_concept(concept_id)
    if not concept:
        raise HTTPException(404, f"Concept '{concept_id}' not found")
    return concept.to_dict()


# --- Concept Video Info ---

@app.get("/api/concept/{concept_id}/video")
async def get_concept_video(concept_id: str):
    """
    Get video embedding info for a concept.
    Returns video_id and title for YouTube iframe embed.
    """
    concept = kg.get_concept(concept_id)
    if not concept:
        raise HTTPException(404, f"Concept '{concept_id}' not found")

    # Look up in concept_sources mapping
    sources = _load_concept_sources()
    source = sources.get(concept_id, {})

    if source.get("video_id"):
        return {
            "video_id": source["video_id"],
            "title": source.get("title", ""),
            "embed_url": f"https://www.youtube-nocookie.com/embed/{source['video_id']}",
            "has_video": True,
        }

    # Fallback: try to find video from lectures metadata
    if concept.lecture_source and kg.lectures:
        for lecture in kg.lectures:
            if concept.lecture_source in lecture.get("title", "") or lecture.get("title", "") in concept.lecture_source:
                vid = lecture.get("video_id", "")
                if vid:
                    return {
                        "video_id": vid,
                        "title": lecture.get("title", ""),
                        "embed_url": f"https://www.youtube-nocookie.com/embed/{vid}",
                        "has_video": True,
                    }

    return {"video_id": None, "title": "", "embed_url": "", "has_video": False}


# --- Learner Management ---

@app.post("/api/learner")
async def create_learner(req: CreateLearnerRequest):
    if req.learner_id in learners:
        return learners[req.learner_id].to_dict()
    lm = LearnerModel(learner_id=req.learner_id, name=req.name)
    learners[req.learner_id] = lm
    save_learner(lm)
    return lm.to_dict()


@app.get("/api/learner/{learner_id}")
async def get_learner_profile(learner_id: str):
    return get_learner(learner_id).to_dict()


@app.get("/api/learner/{learner_id}/mastery")
async def get_mastery_map(learner_id: str):
    lm = get_learner(learner_id)
    mastery_map = lm.get_mastery_map()
    # Only return concepts the user is enrolled in
    full_map = {}
    for cid in lm.concepts:
        concept = kg.get_concept(cid)
        if concept:
            full_map[cid] = {
                "mastery": mastery_map.get(cid, 0.0),
                "name": concept.name,
                "difficulty": concept.difficulty,
            }
    return full_map


@app.get("/api/learner/{learner_id}/courses")
async def get_learner_courses(learner_id: str):
    """Get courses the learner is enrolled in, with per-course mastery summary."""
    lm = get_learner(learner_id)
    mastery_map = lm.get_mastery_map()

    courses = []
    for course in kg.courses:
        if lm.is_enrolled_in(course.course_name):
            # Calculate per-course mastery
            course_masteries = [mastery_map.get(cid, 0.0) for cid in course.concept_ids if cid in lm.concepts]
            avg = sum(course_masteries) / len(course_masteries) if course_masteries else 0.0
            mastered = sum(1 for m in course_masteries if m >= 0.7)

            # Map concepts to lectures
            enriched_lectures = []
            for lec in course.lectures:
                lec_title = lec.get("title", "")
                lec_concepts = []
                for cid in course.concept_ids:
                    if cid in lm.concepts:
                        concept = kg.get_concept(cid)
                        if concept and concept.lecture_source:
                            # Fuzzy match since lecture_source might be partial
                            if concept.lecture_source in lec_title or lec_title in concept.lecture_source:
                                lec_concepts.append({
                                    "id": cid,
                                    "name": concept.name,
                                    "mastery": mastery_map.get(cid, 0.0)
                                })
                enriched_lectures.append({
                    **lec,
                    "concepts": lec_concepts
                })

            courses.append({
                "course_name": course.course_name,
                "channel": course.channel,
                "lectures": enriched_lectures,
                "lectures_count": len(course.lectures),
                "concepts_count": len(course.concept_ids),
                "avg_mastery": round(avg, 3),
                "concepts_mastered": mastered,
            })

    return {"courses": courses}


class EnrollCourseRequest(BaseModel):
    course_name: str

@app.post("/api/learner/{learner_id}/enroll")
async def enroll_learner_in_course(learner_id: str, req: EnrollCourseRequest):
    """Enroll a learner in an existing course by course_name."""
    lm = get_learner(learner_id)
    
    # Find the course
    course_to_enroll = None
    for course in kg.courses:
        if course.course_name == req.course_name:
            course_to_enroll = course
            break
            
    if not course_to_enroll:
        raise HTTPException(404, f"Course '{req.course_name}' not found")
        
    if lm.is_enrolled_in(req.course_name):
        return {"status": "already_enrolled", "course_name": req.course_name}
        
    # Enroll
    newly_enrolled = lm.enroll_in_course(req.course_name, course_to_enroll.concept_ids)
    save_learner(lm)
    
    return {
        "status": "success", 
        "course_name": req.course_name,
        "concepts_enrolled": len(newly_enrolled)
    }


# --- Recommender ---

@app.get("/api/learner/{learner_id}/recommendations")
async def get_recommendations(learner_id: str, top_k: int = 3, failed_concept: Optional[str] = None):
    configure_dspy()
    lm = get_learner(learner_id)

    # Handle empty state — no concepts enrolled
    if not lm.concepts:
        return {
            "recommendations": [],
            "message": "No courses enrolled yet. Upload a YouTube course to get started!",
        }

    if ABLATION_NO_KG:
        # Ablation: no graph-based ZPD. Just recommend lowest-mastery enrolled concepts.
        mastery_map = lm.get_mastery_map()
        enrolled = [(cid, mastery_map.get(cid, 0.0)) for cid in lm.concepts]
        enrolled.sort(key=lambda x: x[1])  # lowest mastery first
        recs = []
        for cid, m in enrolled[:top_k]:
            c = kg.get_concept(cid)
            if not c:
                continue
            recs.append({
                "concept_id": cid,
                "concept_name": c.name,
                "description": c.description,
                "difficulty": c.difficulty,
                "current_mastery": m,
                "reason": "ablation_lowest_mastery",
                "motivation": f"Continue learning {c.name} (mastery: {m:.0%})",
                "bloom_ceiling": c.bloom_ceiling.value,
            })
    elif recommender_agent:
        recs = recommender_agent.recommend(lm, top_k=top_k, failed_concept_id=failed_concept)
    else:
        # Fallback: simple graph-based recommendation without LLM
        mastery_map = lm.get_mastery_map()
        # Only recommend from user's enrolled concepts
        enrolled_ids = set(lm.concepts.keys())
        ready = [c for c in kg.get_ready_concepts(mastery_map, threshold=0.5) if c in enrolled_ids]
        if not ready:
            topo = [c for c in kg.topological_order() if c in enrolled_ids]
            ready = topo[:top_k]
        recs = []
        for cid in ready[:top_k]:
            c = kg.get_concept(cid)
            if not c:
                continue
            recs.append({
                "concept_id": cid,
                "concept_name": c.name,
                "description": c.description,
                "difficulty": c.difficulty,
                "current_mastery": mastery_map.get(cid, 0.0),
                "reason": "zpd_ready",
                "motivation": f"You're ready to learn {c.name}!",
                "bloom_ceiling": c.bloom_ceiling.value
            })

    # Find course recommendations (courses the user is NOT enrolled in)
    course_recs = []
    for course in kg.courses:
        if not lm.is_enrolled_in(course.course_name):
            course_recs.append({
                "course_name": course.course_name,
                "channel": course.channel,
                "lectures_count": len(course.lectures),
                "concepts_count": len(course.concept_ids),
                "description": f"Learn {len(course.concept_ids)} new concepts from {course.channel}."
            })

    return {
        "recommendations": recs,
        "course_recommendations": course_recs[:3],
        "ablation_mode": ABLATION_NO_KG,
    }


# --- Learning Session ---

@app.post("/api/session/start")
async def start_session(req: SessionStartRequest):
    configure_dspy()
    lm = get_learner(req.learner_id)
    concept = kg.get_concept(req.concept_id)
    if not concept:
        raise HTTPException(404, f"Concept '{req.concept_id}' not found")

    # Ensure user is enrolled in this concept
    if req.concept_id not in lm.concepts:
        lm.concepts[req.concept_id] = ConceptState(concept_id=req.concept_id)
        save_learner(lm)

    # Get video info for embedding
    sources = _load_concept_sources()
    source = sources.get(req.concept_id, {})
    video_id = source.get("video_id", "")

    if learning_curator_agent:
        # Step 1: Use Source Curator to create curated source material
        source_material = ""
        if source_curator_agent:
            try:
                curation = source_curator_agent.curate(lm, req.concept_id)
                source_material = curation.get("curated_document", "")
            except Exception as e:
                print(f"Source Curator failed, using transcript fallback: {e}")
                source_material = source.get("transcript_excerpt", "")

        # Step 2: Pass curated material to Learning Curator
        session_data = learning_curator_agent.create_session(
            lm, req.concept_id, source_material=source_material
        )
    else:
        # Fallback without LLM
        cs = lm.get_concept_state(req.concept_id)
        prereqs = kg.get_prerequisites(req.concept_id)
        session_data = {
            "concept_id": req.concept_id,
            "concept_name": concept.name,
            "mastery_level": "beginner" if cs.mastery < 0.3 else ("intermediate" if cs.mastery < 0.6 else "advanced"),
            "bloom_level": "understand",
            "retrieval_questions": [],
            "explanation": concept.description,
            "anticipated_doubts": concept.common_misconceptions,
            "key_takeaways": [concept.description],
            "difficulty": concept.difficulty,
            "prerequisites": [p.name for p in prereqs]
        }

    # Inject video embed info
    session_data["video_id"] = video_id
    session_data["embed_url"] = f"https://www.youtube-nocookie.com/embed/{video_id}" if video_id else ""
    session_data["video_title"] = source.get("title", "")

    return session_data


# --- Doubt Resolution ---

@app.post("/api/doubt/resolve")
async def resolve_doubt(req: DoubtRequest):
    configure_dspy()
    lm = get_learner(req.learner_id)

    if doubt_resolver_agent:
        result = doubt_resolver_agent.resolve(lm, req.concept_id, req.doubt)
    else:
        cs = lm.get_concept_state(req.concept_id)
        cs.doubts.append({"text": req.doubt, "type": "unknown", "resolved": False})
        result = {
            "concept_id": req.concept_id,
            "doubt": req.doubt,
            "answer": "LLM not configured. Please set up your API key.",
            "misconception_type": "none",
            "follow_up_question": ""
        }

    # Store doubt globally to benefit other users
    concept = kg.get_concept(req.concept_id)
    if concept:
        concept.global_doubts.append(req.doubt)
        kg.save(os.path.join(DATA_DIR, "knowledge_graph.json"))

    # Collect for flywheel (Human-in-the-Loop)
    if flywheel_store:
        try:
            flywheel_store.collect_doubt(
                learner_id=req.learner_id,
                concept_id=req.concept_id,
                concept_name=concept.name if concept else req.concept_id,
                doubt_text=req.doubt,
                answer_text=result.get("answer", ""),
                misconception_type=result.get("misconception_type", "none"),
                misconception_explanation=result.get("misconception_explanation", ""),
                follow_up_question=result.get("follow_up_question", ""),
            )
        except Exception as e:
            print(f"Flywheel collect_doubt failed: {e}")

    save_learner(lm)
    return result


# --- Question Generation ---

@app.get("/api/learner/{learner_id}/questions/{concept_id}")
async def generate_questions(learner_id: str, concept_id: str):
    configure_dspy()
    lm = get_learner(learner_id)

    if question_generator_agent:
        result = question_generator_agent.generate(lm, concept_id)
    else:
        concept = kg.get_concept(concept_id)
        if not concept:
            raise HTTPException(404, f"Concept '{concept_id}' not found")
        result = {
            "concept_id": concept_id,
            "concept_name": concept.name,
            "mastery_level": "beginner",
            "bloom_levels": ["remember", "understand"],
            "questions": [{
                "question": f"Explain {concept.name} in your own words.",
                "type": "written",
                "bloom_level": "understand",
                "interleaved_concept": None,
                "pattern": "property_transfer",
                "options": None,
                "correct_answer": concept.description,
                "rubric": "Demonstrate understanding."
            }]
        }

    return result


# --- Answer Evaluation ---

@app.post("/api/evaluate")
async def evaluate_answer(req: AnswerRequest):
    configure_dspy()
    lm = get_learner(req.learner_id)

    if evaluator_agent:
        eval_result = evaluator_agent.evaluate(
            lm, req.concept_id, req.question, req.answer, req.response_time
        )
    else:
        correct = req.answer.strip().lower() == req.question.get("correct_answer", "").strip().lower()
        eval_result = {
            "concept_id": req.concept_id,
            "question_type": req.question.get("type", "written"),
            "is_correct": correct,
            "score": 1.0 if correct else 0.3,
            "normalised_score": 1.0 if correct else 0.3,
            "feedback": "Correct!" if correct else "Review the concept.",
            "response_time": req.response_time,
            "score_breakdown": {}
        }

    # Update mastery via Mastery Engine
    new_mastery = mastery_engine.update_mastery(
        learner=lm,
        concept_id=req.concept_id,
        score=eval_result["normalised_score"],
        correct=eval_result["is_correct"],
        response_time=req.response_time
    )
    eval_result["new_mastery"] = round(new_mastery, 4)

    # Prerequisite penalty on failure (skip in ablation mode — no KG)
    if not eval_result["is_correct"] and not ABLATION_NO_KG:
        penalised = mastery_engine.apply_prerequisite_penalty(
            lm, req.concept_id, score=eval_result["normalised_score"]
        )
        eval_result["prerequisites_penalised"] = penalised

    # Check for concepts needing review (Ebbinghaus decay)
    if not ABLATION_NO_KG:
        needs_review = mastery_engine.get_concepts_needing_review(lm)
        eval_result["concepts_needing_review"] = [
            {"concept_id": cid, "effective_mastery": round(em, 3)}
            for cid, em in needs_review[:3]
        ]
    else:
        eval_result["concepts_needing_review"] = []

    eval_result["ablation_mode"] = ABLATION_NO_KG

    # Collect for flywheel (Human-in-the-Loop)
    if flywheel_store:
        try:
            concept = kg.get_concept(req.concept_id)
            flywheel_store.collect_evaluation(
                learner_id=req.learner_id,
                concept_id=req.concept_id,
                concept_name=concept.name if concept else req.concept_id,
                question_text=req.question.get("question", ""),
                student_answer=req.answer,
                correct_answer=req.question.get("correct_answer", ""),
                score=eval_result["normalised_score"],
                feedback=eval_result.get("feedback", ""),
                bloom_level=req.question.get("bloom_level", ""),
                question_type=req.question.get("type", "written"),
            )
        except Exception as e:
            print(f"Flywheel collect_evaluation failed: {e}")

    save_learner(lm)
    return eval_result


# --- Review Schedule (Ebbinghaus Decay) ---

@app.get("/api/learner/{learner_id}/review-schedule")
async def get_review_schedule(learner_id: str):
    lm = get_learner(learner_id)
    needs_review = mastery_engine.get_concepts_needing_review(lm)
    schedule = []
    for cid, effective_mastery in needs_review:
        concept = kg.get_concept(cid)
        schedule.append({
            "concept_id": cid,
            "concept_name": concept.name if concept else cid,
            "effective_mastery": round(effective_mastery, 3),
            "stored_mastery": round(lm.get_concept_state(cid).mastery, 3),
            "urgency": "high" if effective_mastery < 0.3 else ("medium" if effective_mastery < 0.5 else "low")
        })
    return {"review_schedule": schedule}


# ========================================
# Admin / Data Engineer — Flywheel API
# ========================================

class FlywheelApprovalRequest(BaseModel):
    curator_notes: str = ""

@app.get("/api/admin/flywheel/interactions")
async def get_flywheel_interactions(
    type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
):
    """List collected learner interactions with optional filtering."""
    if not flywheel_store:
        return {"interactions": [], "total": 0}
    interactions, total = flywheel_store.get_interactions(
        filter_type=type, filter_status=status, limit=limit, offset=offset
    )
    return {"interactions": interactions, "total": total}


@app.post("/api/admin/flywheel/approve/{interaction_id}")
async def approve_interaction(interaction_id: str, req: FlywheelApprovalRequest):
    """Approve an interaction for use as a few-shot training example."""
    if not flywheel_store:
        raise HTTPException(500, "Flywheel not initialised")
    ok = flywheel_store.approve(interaction_id, req.curator_notes)
    if not ok:
        raise HTTPException(404, f"Interaction '{interaction_id}' not found")
    return {"status": "approved", "interaction_id": interaction_id}


@app.post("/api/admin/flywheel/reject/{interaction_id}")
async def reject_interaction(interaction_id: str, req: FlywheelApprovalRequest):
    """Reject an interaction (mark as not suitable for training)."""
    if not flywheel_store:
        raise HTTPException(500, "Flywheel not initialised")
    ok = flywheel_store.reject(interaction_id, req.curator_notes)
    if not ok:
        raise HTTPException(404, f"Interaction '{interaction_id}' not found")
    return {"status": "rejected", "interaction_id": interaction_id}


@app.get("/api/admin/flywheel/stats")
async def get_flywheel_stats():
    """Get aggregate flywheel statistics."""
    if not flywheel_store:
        return {"total_interactions": 0}
    return flywheel_store.get_stats()


@app.post("/api/admin/flywheel/export")
async def export_flywheel_examples():
    """Export approved interactions as DSPy few-shot examples."""
    if not flywheel_store:
        raise HTTPException(500, "Flywheel not initialised")
    examples = flywheel_store.export_fewshot_examples()
    return {
        "status": "exported",
        "total_approved": examples.get("total_approved", 0),
        "doubt_examples": len(examples.get("doubt_resolution", [])),
        "evaluation_examples": len(examples.get("evaluation", [])),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

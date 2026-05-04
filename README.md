# Personalised Learning System via Multi-Agent AI

**Deep Concepts, Personal Doubts, Adaptive Questions**

A knowledge graph-augmented personalised learning system that combines six DSPy-compiled LLM agents with a psychologically-grounded Bayesian mastery engine to deliver adaptive, constructivist instruction from YouTube lecture content.

### 📄 [Research Paper (PDF)](paper.pdf) &nbsp;&nbsp;&nbsp; 🎬 [Demo Video (MP4)](video.mp4)

---

## Table of Contents

- [Quick Start](#quick-start)
- [System Overview](#system-overview)
- [Architecture](#architecture)
- [Components](#components)
- [Run Scripts](#run-scripts)
- [Project Structure](#project-structure)
- [Configuration](#configuration)
- [Experiments](#experiments)
- [Testing](#testing)
- [Data](#data)

---

## Quick Start

```bash
# 1. Clone and enter the project
cd PersonalisedLearningSystem

# 2. Create and activate virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API key
echo "GOOGLE_API_KEY=your-key-here" > backend/.env
echo "LLM_MODEL=gemini/gemma-4-31b-it" >> backend/.env

# 5. Run the system
./run.sh
```

The system will be available at:
- **Learner Interface**: http://localhost:5173
- **Admin Dashboard**: http://localhost:5173/admin.html
- **API**: http://localhost:8000

---

## Run Scripts

| Script | Purpose | Command |
|--------|---------|---------|
| `run.sh` | Start the full learning system (backend + frontend) | `./run.sh` |
| `run_tests.sh` | Run the unit and integration test suite | `./run_tests.sh` |
| `run_evals.sh` | Run synthetic evaluations and ablation studies | `./run_evals.sh all` |
| `run_admin.sh` | Start the flywheel admin dashboard only | `./run_admin.sh` |

### `run.sh` — Learning System
Starts both the FastAPI backend (port 8000) and the Vite frontend dev server (port 5173). Logs are written to `logs/` with timestamps. Press Ctrl+C to stop both.

### `run_tests.sh` — Test Suite
Runs all tests in `testing/` using pytest. Pass pytest arguments after the script:
```bash
./run_tests.sh                    # All tests, short output
./run_tests.sh -v -k "mastery"   # Verbose, only mastery tests
./run_tests.sh --tb=long          # Full tracebacks
```

### `run_evals.sh` — Experiments
Runs the automated experiment framework. Requires a valid API key in `backend/.env`.
```bash
./run_evals.sh all        # All 5 experiments
./run_evals.sh 1          # Experiment 1: Bloom Distribution
./run_evals.sh 2          # Experiment 2: UID Calibration
./run_evals.sh 3          # Experiment 3: KG vs No-KG
./run_evals.sh 4          # Experiment 4: Mastery Evolution
./run_evals.sh 5          # Experiment 5: Faithfulness
./run_evals.sh summary    # Regenerate summary report
./run_evals.sh synthetic  # Legacy synthetic eval
```
Results are saved to `experiments/results/`.

### `run_admin.sh` — Flywheel Admin
Starts the backend API and serves the admin dashboard for the Human-in-the-Loop data flywheel. Access at http://localhost:5174/admin.html.

---
## Compute details
- API based will run from a laptop, but the API responses are slow so there would be a lot of latency. 
- In a real world scenario, the API responses would be faster and parallel calls would be made to reduce latency.

## System Overview

### Pedagogical Foundation
Current AI tutoring systems suffer from two fundamental problems:
1. **Gamification systems** (e.g., Duolingo) violate the Zone of Proximal Development (ZPD) by isolating learning into bite-sized, unconnected trivia.
2. **Reactive LLM tutors** (e.g., ChatGPT) bypass constructivist mental modelling by providing immediate, exhaustive answers.

### Our Approach
- **Doubt-centric learning**: Doubts are treated as the foundation of deep understanding
- **Constructivist constraints**: Doubt resolution uses ONLY concepts the learner already knows
- **Adaptive depth calibration**: Content difficulty is calibrated via Bloom's taxonomy
- **Structured knowledge graph**: A DAG of concepts with prerequisites ensures valid learning paths
- **Retrieval-first design**: Prerequisite retrieval questions precede new content (Bjork's desirable difficulties)

---

## Architecture

```
YouTube Playlist / Topic Query
         │
         ▼
┌──────────────────────┐
│   RAG Pipeline       │  yt-dlp + parallel transcript fetching
│   Concept Extraction │  LLM: 15-35 atomic concepts per course
└──────────────────────┘
         │
         ▼
┌──────────────────────┐
│   Knowledge Graph    │  NetworkX DAG
│   171 concepts       │  348 edges, 7 courses
└──────────────────────┘
         │
         ▼
┌──────────────────────────────────────────────────┐
│              6 DSPy Agent Pipeline                │
│  Recommender → Source Curator → Learning Curator  │
│  Doubt Resolver → Question Generator → Evaluator │
└──────────────────────────────────────────────────┘
         │
         ▼
┌──────────────────────┐
│   Mastery Engine     │  BKT + Ebbinghaus + Streak + Difficulty
│   + Learner Model    │  Response-time confidence calibration
└──────────────────────┘
```

---

## Components

### Knowledge Graph (`backend/core/knowledge_graph.py`)
- **ConceptNode** with difficulty, Bloom's ceiling, prerequisites, misconceptions, global doubts
- DAG operations: topological sort, ZPD-ready detection, centrality scoring, diagnostic chain traversal
- Multi-course support with automatic deduplication and acyclicity validation

### Mastery Engine (`backend/core/mastery_engine.py`)
Six-step update pipeline:
1. **BKT** — Bayesian posterior with P_slip=0.1, P_guess=0.2, P_learn=0.15
2. **BKT-Score Blending** — 0.7 × BKT + 0.3 × EMA(score)
3. **Streak Momentum** — min(0.15, 0.03 × streak_count)
4. **Difficulty Bonus** — 0.05 × concept difficulty
5. **Ebbinghaus Decay** — M × exp(-Δt/S), S depends on retrievals + KG connections
6. **Response-Time Confidence** — Tempered sigmoid (inflection=20s, temp=8)

Plus prerequisite penalty propagation and ablation mode (`ablation_no_kg`).

### Agent Pipeline (6 agents in `backend/agents/`)
| Agent | Key Feature |
|-------|-------------|
| **Recommender** | Pure graph traversal (no LLM), ZPD targeting, diagnostic rollback |
| **Source Curator** | Merges transcript + prereq info into mastery-calibrated document |
| **Learning Curator** | Retrieval-first design, 3 contexts, depth calibration |
| **Doubt Resolver** | Constructivist constraint (only known concepts), misconception taxonomy |
| **Question Generator** | Bloom's level gating, interleaving, 6 question patterns |
| **Evaluator** | 5-dimension rubric (10 pts), MCQ + written, response time tracking |

### Learner Model (`backend/core/learner_model.py`)
Per-concept state: mastery, history, doubts, misconceptions, Bloom level achieved, response times. Multi-course enrollment, session logging, JSON persistence.

### Human-in-the-Loop Flywheel (`backend/data/flywheel.py`)
Automatic capture of doubt resolutions and evaluations → data engineer curation → DSPy few-shot export.

### RAG Pipeline (`backend/data/rag_pipeline.py`)
YouTube URL → yt-dlp transcripts → LLM concept extraction → KG merge. Supports chunking for long transcripts and topic search fallback.

---

## Project Structure

```
PersonalisedLearningSystem/
├── run.sh                    # Start full system
├── run_tests.sh              # Run test suite
├── run_evals.sh              # Run evaluations/ablations
├── run_admin.sh              # Start flywheel admin
├── requirements.txt          # Python dependencies
│
├── backend/
│   ├── api/
│   │   └── server.py         # FastAPI endpoints
│   ├── agents/
│   │   ├── learning_curator.py
│   │   ├── source_curator.py
│   │   ├── doubt_resolver.py
│   │   ├── question_generator.py
│   │   ├── evaluator.py
│   │   ├── recommender.py
│   │   └── fewshot_examples.py
│   ├── core/
│   │   ├── knowledge_graph.py
│   │   ├── mastery_engine.py
│   │   ├── learner_model.py
│   │   └── llm_config.py
│   ├── data/
│   │   ├── rag_pipeline.py
│   │   ├── youtube_service.py
│   │   ├── flywheel.py
│   │   ├── knowledge_graph.json
│   │   ├── raw/               # Transcripts, extracted concepts
│   │   ├── learners/          # Per-learner profiles
│   │   └── flywheel/          # Interaction logs
│   ├── .env                   # API keys (not committed)
│   └── requirements.txt       # Backend-specific deps
│
├── frontend/
│   ├── index.html             # Learner interface
│   ├── main.js, style.css
│   ├── admin.html             # Flywheel admin dashboard
│   ├── admin.js, admin.css
│   └── package.json
│
├── experiments/
│   ├── run_all.py             # Experiment runner
│   ├── config.py              # Shared configuration
│   ├── exp1_bloom_distribution.py
│   ├── exp2_uid_calibration.py
│   ├── exp3_kg_ablation.py
│   ├── exp4_mastery_evolution.py
│   ├── exp5_pedagogical_faithfulness.py
│   └── results/               # JSON telemetry + summary
│
├── testing/
│   ├── conftest.py            # Shared fixtures
│   ├── test_knowledge_graph.py
│   ├── test_mastery_engine.py
│   ├── test_learner_model.py
│   ├── test_agents.py
│   ├── test_flywheel.py
│   ├── test_integration.py
│   └── ...
│
└── logs/                      # Runtime logs (auto-created)
```

---

## Configuration

### Environment Variables (`backend/.env`)
```env
GOOGLE_API_KEY=your-gemini-api-key
LLM_MODEL=gemini/gemini-2.0-flash    # DSPy model identifier
```

### LLM Configuration (`backend/core/llm_config.py`)
Handles model selection, transcript chunking limits, and context window sizes. The system is model-agnostic via DSPy — change `LLM_MODEL` to switch models without modifying agent logic.

### Key Thresholds
| Parameter | Value | Description |
|-----------|-------|-------------|
| Prerequisite readiness | 0.5 | Min prereq mastery for ZPD |
| Mastery ceiling | 0.85 | Concept considered "mastered" |
| Known concept threshold | 0.2 | Min mastery for doubt resolver vocabulary |
| Forgetting S₀ | 7 days | Base forgetting strength |
| Streak cap | 0.15 | Maximum streak momentum bonus |
| Sigmoid inflection/temp | 20s / 8 | Response-time confidence curve |

---

## Experiments

Five automated experiments evaluate pedagogical quality:

| # | Experiment | Metric |
|---|-----------|--------|
| 1 | Bloom Distribution Alignment | Bloom level distribution vs mastery tier |
| 2 | Surprisal-Based UID Calibration | GPT-2 surprisal + Flesch-Kincaid grade |
| 3 | KG vs No-KG Quality | LLM-as-judge (coherence, prereq awareness, depth, quality) |
| 4 | Mastery Evolution | Mastery trajectory over N iterations with simulated student |
| 5 | Pedagogical Faithfulness | Constructivist adherence + misconception detection |

Run with `./run_evals.sh`. See `experiments/README.md` for detailed documentation.

---

## Testing

The test suite in `testing/` covers:
- **Knowledge Graph**: DAG validation, topological sort, concept operations
- **Mastery Engine**: BKT updates, forgetting decay, streak momentum, ablation mode
- **Learner Model**: State management, persistence, multi-course enrollment
- **Agents**: Signature validation, depth calibration, constructivist constraints
- **Flywheel**: Interaction capture, curation workflow, DSPy export
- **Integration**: End-to-end pipeline, API model validation

Run with `./run_tests.sh`.

---

## Data

| Resource | Location | Description |
|----------|----------|-------------|
| Knowledge Graph | `backend/data/knowledge_graph.json` | 171 concepts, 348 edges, 7 courses |
| Transcripts | `backend/data/raw/transcripts.json` | Raw YouTube transcripts |
| Concept Sources | `backend/data/raw/concept_sources.json` | Concept → transcript excerpt |
| Learner Profiles | `backend/data/learners/*.json` | Per-learner state |
| Flywheel Data | `backend/data/flywheel/` | Interaction logs + approved examples |
| Experiment Results | `experiments/results/` | JSON telemetry + summary report |

**Courses**: Crash Course Geology (24), S4/Mamba (22), Scientific Thinking (29), StatQuest Transformers (21), Integration (17), Linear Algebra (44), Medical History (15)
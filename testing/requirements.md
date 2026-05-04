# Personalised Learning System — Requirements Document

> **Source:** `PersonalisedLearningSystem.pdf` (slide deck, April 13 2026)
> **Extracted on:** 2026-05-03
> **Legend:** ✅ = Yes | ❌ = No | ⚠️ = Partial

---

## Slide 1 — Title / Overview

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R1.1 | System shall be a multi-agent AI-based personalised learning platform | ✅ | ✅ |
| R1.2 | System shall support deep conceptual learning (not gamified trivia) | ✅ | ✅ |
| R1.3 | System shall support personal doubt resolution | ✅ | ✅ |
| R1.4 | System shall generate adaptive questions | ✅ | ✅ |

---

## Slide 2 — Agenda (Architectural Requirements)

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R2.1 | System shall have 6 modular DSPy agents | ✅ | ✅ |
| R2.2 | System shall implement a Human-in-the-Loop data flywheel (real data vs synthetic) | ✅ | ✅ |
| R2.3 | System shall be model-agnostic via DSPy (support swapping LLMs) | ✅ | ✅ |
| R2.4 | System shall support Gemma-4 / Gemini as LLM backends | ✅ | ✅ |

---

## Slide 3 — The Pedagogical Problem (ZPD)

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R3.1 | System shall respect the Zone of Proximal Development (ZPD) — not too easy, not too hard | ✅ | ✅ |
| R3.2 | System shall NOT incentivise quick wins / gamification | ✅ | ✅ |
| R3.3 | System shall provide structured conceptual mastery (not bite-sized trivia) | ✅ | ✅ |

---

## Slide 4 — Reactive AI Tutors & Constructivism

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R4.1 | System shall NOT provide immediate exhaustive answers (constructivist approach) | ✅ | ✅ |
| R4.2 | System shall build cognitive scaffolding on the learner's actual foundation | ✅ | ✅ |
| R4.3 | System shall support long-session learning centred on solving personal doubts | ✅ | ✅ |

---

## Slide 5 — Doubt-Centric Personalisation (Learner's Journey)

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R5.1 | System shall curate learning sources (books/videos/articles) | ✅ | ✅ |
| R5.2 | System shall provide deep learning sessions with adaptive explanation calibrated to learner level | ✅ | ✅ |
| R5.3 | System shall allow learners to raise personal doubts | ✅ | ✅ |
| R5.4 | System shall build a dataset of misconceptions from doubts | ✅ | ✅ |
| R5.5 | System shall bridge doubts to known concepts | ✅ | ✅ |
| R5.6 | System shall generate adaptive questions that bridge past and current knowledge | ✅ | ✅ |

---

## Slide 6 — System Architecture: 6 DSPy Agents

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R6.1 | Pipeline shall start with Learner + Concept input | ✅ | ✅ |
| R6.2 | Agent 1: Recommender — select next concept | ✅ | ✅ |
| R6.3 | Agent 2: Source Curator — curate learning sources | ✅ | ✅ |
| R6.4 | Agent 3: Learning Curator — generate adaptive explanation | ✅ | ✅ |
| R6.5 | Agent 4: Doubt Resolver — resolve doubts using known concepts | ✅ | ✅ |
| R6.6 | Agent 5: Question Generator — generate Socratic questions | ✅ | ✅ |
| R6.7 | Agent 6: Evaluator — score answers and update mastery | ✅ | ✅ |
| R6.8 | Pipeline shall update the Learner Graph after each session | ✅ | ✅ |
| R6.9 | System shall maintain a Personalised Learner Graph (JSON) | ✅ | ✅ |
| R6.10 | System shall maintain an NPTEL Global Knowledge Graph | ✅ | ✅ |

---

## Slide 7 — Component Summary Table

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R7.1 | Source Curator input: Concept + Mastery | ✅ | ✅ |
| R7.2 | Source Curator output: Ranked sources + combined document | ✅ | ✅ |
| R7.3 | Recommender input: Learner profile + graph | ✅ | ✅ |
| R7.4 | Recommender output: Next concept + motivation | ✅ | ✅ |
| R7.5 | Learning Curator input: Source + mastery | ✅ | ✅ |
| R7.6 | Learning Curator output: Adaptive explanation + doubts | ✅ | ✅ |
| R7.7 | Doubt Resolver input: Doubt + known concepts | ✅ | ✅ |
| R7.8 | Doubt Resolver output: Answer using only known concepts | ✅ | ✅ |
| R7.9 | Question Generator input: Concept + doubts | ✅ | ✅ |
| R7.10 | Question Generator output: 5 Socratic questions | ✅ | ✅ |
| R7.11 | Evaluator input: Answer + rubric | ✅ | ✅ |
| R7.12 | Evaluator output: Score + feedback + mastery update | ✅ | ✅ |

---

## Slide 8 — Source Curator (Agent 2) Deep Dive

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R8.1 | Source Curator shall retrieve multiple sources (YouTube, Wikipedia, static) | ✅ | ✅ |
| R8.2 | Source Curator shall rank sources by quality & mastery fit | ✅ | ✅ |
| R8.3 | Source Curator shall merge best ideas into ONE coherent document | ✅ | ✅ |
| R8.4 | Source Curator shall calibrate to mastery: M < 0.3 → analogies, simple language | ✅ | ✅ |
| R8.5 | Source Curator shall calibrate to mastery: 0.3 ≤ M < 0.6 → mixed intuition + technical | ✅ | ✅ |
| R8.6 | Source Curator shall calibrate to mastery: M ≥ 0.6 → full precision, proofs | ✅ | ✅ |
| R8.7 | Source Curator shall use DSPy ChainOfThought | ✅ | ✅ |
| R8.8 | Source Curator shall use few-shot prompting | ✅ | ✅ |
| R8.9 | Source Curator shall output ranked JSON + merged document | ✅ | ✅ |

---

## Slide 9 — Knowledge Graph Construction (RAG Backend)

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R9.1 | System shall scrape NPTEL course structures | ✅ | ✅ |
| R9.2 | System shall extract YouTube transcripts | ✅ | ✅ |
| R9.3 | System shall use LLMs to mine atomic concepts from transcripts | ✅ | ✅ |
| R9.4 | Knowledge graph node taxonomy: Academic Stream, Course, Lecture, Concept | ⚠️ | ⚠️ |
| R9.5 | Knowledge graph edge schema: HAS_COURSE, HAS_LECTURE, COVERS_CONCEPT | ⚠️ | ⚠️ |
| R9.6 | Concepts shall be atomic — one idea per concept | ✅ | ✅ |
| R9.7 | Knowledge graph shall be persisted as JSON | ✅ | ✅ |
| R9.8 | Knowledge graph shall be a Directed Acyclic Graph (DAG) | ✅ | ✅ |

---

## Slide 10 — Recommender (Agent 1)

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R10.1 | Recommender shall traverse the concept graph | ✅ | ✅ |
| R10.2 | Recommender shall select concepts where prerequisites are mastered (≥ 0.5) | ✅ | ✅ |
| R10.3 | Recommender shall perform diagnostic rollback if learner fails | ✅ | ✅ |
| R10.4 | Recommender shall sort recommendations by readiness score | ✅ | ✅ |
| R10.5 | Recommender shall use graph traversal (no LLM) for concept selection | ✅ | ✅ |
| R10.6 | Recommender shall use LLM only for motivation message generation | ✅ | ✅ |

---

## Slide 11 — Learning Curator (Agent 3)

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R11.1 | Learning Curator shall produce adaptive explanation | ✅ | ✅ |
| R11.2 | Learning Curator shall identify likely doubts (anticipate) | ✅ | ✅ |
| R11.3 | Learning Curator shall generate 3 retrieval practice questions on prerequisites | ✅ | ✅ |
| R11.4 | Beginner depth: analogies, first principles | ✅ | ✅ |
| R11.5 | Intermediate depth: intuition + precision | ✅ | ✅ |
| R11.6 | Advanced depth: math, proofs | ✅ | ✅ |
| R11.7 | Learning Curator shall bridge known concepts | ✅ | ✅ |
| R11.8 | Learning Curator shall provide formative assessment | ✅ | ✅ |

---

## Slide 12 — Doubt Resolver (Agent 4)

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R12.1 | Doubt Resolver shall answer learner doubts | ✅ | ✅ |
| R12.2 | Doubt Resolver shall use ONLY known concepts in answers (constructivist constraint) | ✅ | ✅ |
| R12.3 | Doubt Resolver shall detect misconceptions | ✅ | ✅ |
| R12.4 | Doubt Resolver shall classify misconception type (definitional/relational/procedural/causal) | ✅ | ✅ |
| R12.5 | Doubt Resolver shall store doubts for future remediation | ✅ | ✅ |
| R12.6 | Doubt Resolver shall NOT introduce new concepts | ✅ | ✅ |
| R12.7 | Doubt resolution shall create high-quality training data | ✅ | ✅ |

---

## Slide 13 — Question Generator (Agent 5)

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R13.1 | Question Generator shall generate exactly 5 Socratic questions | ✅ | ✅ |
| R13.2 | Questions shall use RAG context (lecture transcript) | ✅ | ✅ |
| R13.3 | Questions shall connect past & current concepts (interleaving) | ✅ | ✅ |
| R13.4 | Questions shall apply level gating (Bloom's taxonomy) | ✅ | ✅ |
| R13.5 | Question patterns: property transfer | ✅ | ✅ |
| R13.6 | Question patterns: mechanism contrast | ✅ | ✅ |
| R13.7 | Question patterns: failure mode | ✅ | ✅ |
| R13.8 | Question patterns: multi-step reasoning | ✅ | ✅ |
| R13.9 | At least 2 questions must interleave with previously mastered concepts | ✅ | ✅ |

---

## Slide 14 — Evaluator (Agent 6)

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R14.1 | Evaluator shall score MCQ answers via exact match | ✅ | ✅ |
| R14.2 | Evaluator shall score written answers via rubric-based evaluation | ✅ | ✅ |
| R14.3 | Evaluator shall update mastery after evaluation | ✅ | ✅ |
| R14.4 | Evaluator shall provide qualitative feedback | ✅ | ✅ |
| R14.5 | Mastery update formula: M_new = 0.3 × score + 0.7 × M_old | ✅ | ✅ |
| R14.6 | Rubric: Concept accuracy (max 4 points) | ⚠️ | ⚠️ |
| R14.7 | Rubric: Example quality (max 2 points) | ✅ | ✅ |
| R14.8 | Rubric: Precision (max 2 points) | ⚠️ | ⚠️ |
| R14.9 | Rubric: Completeness (max 2 points) | ⚠️ | ⚠️ |

---

## Slide 15 — Mastery Update Formula

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R15.1 | Mastery engine shall implement: M_effective = M_base × e^(-t/S) (Ebbinghaus decay) | ✅ | ✅ |
| R15.2 | Mastery engine shall implement: M_new = 0.3 × eval_score + 0.7 × M_effective (EMA) | ✅ | ✅ |
| R15.3 | Mastery update shall balance recent performance with history | ✅ | ✅ |
| R15.4 | Mastery update shall prevent instability (clamped 0–1) | ✅ | ✅ |

---

## Slide 16 — Personalised Learner Graph

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R16.1 | Learner graph shall store learner_id | ✅ | ✅ |
| R16.2 | Learner graph shall store per-concept mastery scores | ✅ | ✅ |
| R16.3 | Learner graph shall store per-concept doubts (list of strings) | ✅ | ✅ |
| R16.4 | Learner graph shall be persisted per learner (JSON file) | ✅ | ✅ |
| R16.5 | Learner graph shall be updated after each session | ✅ | ✅ |

---

## Slide 17 — Human-in-the-Loop Data Flywheel

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R17.1 | System shall store real learner doubts as training data | ✅ | ✅ |
| R17.2 | Real doubts shall provide high-quality signals vs synthetic data | ✅ | ✅ |
| R17.3 | System shall support a continuous improvement loop | ✅ | ✅ |

---

## Slide 18 — Model Selection: Gemma-4

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R18.1 | System shall support Gemma-4 as an LLM backend | ✅ | ✅ |
| R18.2 | System shall support running on consumer hardware (via Ollama) | ✅ | ✅ |
| R18.3 | System shall be open-source compatible | ✅ | ✅ |

---

## Slide 19 — Model Agnosticism vs Finetuning

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R19.1 | System shall NOT use finetuning (preserves general reasoning) | ✅ | ✅ |
| R19.2 | DSPy shall enable model swapping without code changes | ✅ | ✅ |
| R19.3 | Architecture shall be future-proof (new models can be plugged in) | ✅ | ✅ |

---

## Slide 20 — Key Architectural Decisions

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R20.1 | Use curated sources instead of replacing them (Source Curator) | ✅ | ✅ |
| R20.2 | Make doubts central to the learning process | ✅ | ✅ |
| R20.3 | Level-gate questions based on Bloom's taxonomy | ✅ | ✅ |
| R20.4 | Use stable mastery updates (EMA formula) | ✅ | ✅ |
| R20.5 | Modular agent design (6 independent agents) | ✅ | ✅ |

---

## Slide 21 — System Evaluation Metrics

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R21.1 | System shall measure Faithfulness (target: 95.4%) | ✅ | ✅ |
| R21.2 | System shall measure Constraint adherence (target: 98.1%) | ✅ | ✅ |
| R21.3 | System shall measure Relevance (target: 96.7%) | ✅ | ✅ |
| R21.4 | Average session time shall be efficient (~8.5 seconds) | ✅ | ✅ |
| R21.5 | Graph traversal shall be 100% accurate | ✅ | ✅ |

---

## Slide 22 — Pedagogical Effectiveness

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R22.1 | Readability adaptation: Beginner → simple, analogy-driven | ✅ | ✅ |
| R22.2 | Readability adaptation: Intermediate → balanced | ✅ | ✅ |
| R22.3 | Readability adaptation: Advanced → dense, technical | ✅ | ✅ |
| R22.4 | Cognitive depth: Low mastery → recall + application questions | ✅ | ✅ |
| R22.5 | Cognitive depth: High mastery → synthesis + analysis questions | ✅ | ✅ |

---

## Slide 23 — Future Capabilities & Constraints

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R23.1 | System shall support semantic retrieval | ✅ | ✅ |
| R23.2 | System shall support diagnostic rollback | ✅ | ✅ |
| R23.3 | Constraint: Evaluator subjectivity is acknowledged | ✅ | ✅ |
| R23.4 | Constraint: Limited dependency modeling acknowledged | ✅ | ✅ |

---

## Slide 24 — Conclusion (Core Guarantees)

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R24.1 | Learning shall be long-form and structured | ✅ | ✅ |
| R24.2 | Doubts shall be central to the experience | ✅ | ✅ |
| R24.3 | Scaffolding shall be personalised per learner | ✅ | ✅ |
| R24.4 | Questions shall build connections across concepts (interleaving) | ✅ | ✅ |
| R24.5 | Feedback shall be actionable (not just "wrong") | ✅ | ✅ |
| R24.6 | Data shall improve continuously (human-in-the-loop) | ✅ | ✅ |

---

## Slide 25 — Appendix (DSPy Reference)

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R25.1 | System shall use `dspy.Signature` for structured I/O | ✅ | ✅ |
| R25.2 | System shall use `dspy.Module` for composable agents | ✅ | ✅ |
| R25.3 | System shall use `dspy.ChainOfThought` for reasoning | ✅ | ✅ |
| R25.4 | System shall configure LM via `dspy.configure(lm=lm)` | ✅ | ✅ |

---

## API / Frontend Requirements (Implied from System Architecture)

| ID | Requirement | Code Present | Functioning |
|----|-------------|:------------:|:-----------:|
| R-API.1 | System shall expose REST API endpoints for all agents | ✅ | ✅ |
| R-API.2 | Frontend shall provide onboarding / user creation | ✅ | ✅ |
| R-API.3 | Frontend shall display knowledge graph visualisation | ✅ | ✅ |
| R-API.4 | Frontend shall support YouTube course ingestion | ✅ | ✅ |
| R-API.5 | Frontend shall display mastery progress bars | ✅ | ✅ |
| R-API.6 | Frontend shall support MCQ + written answer submission | ✅ | ✅ |
| R-API.7 | Frontend shall display evaluation feedback with mastery updates | ✅ | ✅ |
| R-API.8 | System shall save/load learner profiles on startup/shutdown | ✅ | ✅ |
| R-API.9 | System shall provide review schedule (Ebbinghaus decay) | ✅ | ✅ |

---

## Notes on Partial (⚠️) Entries

- **R2.2 / R17.3 / R24.6 (Human-in-the-Loop flywheel):** Doubts are stored and shared globally, but there is no automated retraining loop or DSPy optimizer integration yet.
- **R8.1 (Multiple source types):** Only YouTube transcripts and concept descriptions are used. Wikipedia and static article retrieval are not implemented.
- **R8.8 (Few-shot prompting):** ChainOfThought is used but explicit few-shot examples are not configured in the Source Curator.
- **R9.4 / R9.5 (Full node taxonomy / edge schema):** The knowledge graph has Course, Lecture, and Concept nodes, but not the Academic Stream level. Edge types are PREREQUISITE_OF and RELATED_TO rather than the HAS_COURSE/HAS_LECTURE/COVERS_CONCEPT schema from the slides.
- **R14.6 / R14.8 / R14.9 (Rubric scoring):** The rubric is implemented but with slightly different point allocations (Concept: 0-3, Reasoning: 0-2, Examples: 0-2, Precision: 0-1, Connections: 0-2 → max 10) compared to the slides (Concept: 4, Example: 2, Precision: 2, Completeness: 2 → max 10).

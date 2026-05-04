# Personalised Learning System - Backend Architecture

This document describes the implementation of the backend modules for the Personalised Learning System, mapping each module to the architecture presented in the project slides.

## Architecture Alignment Summary

The backend is built around a multi-agent architecture orchestrated by DSPy, leveraging a dynamic knowledge graph and a Bayesian-Ebbinghaus mastery engine. 

Overall, the implementation **strictly follows** the provided architectural slides. It includes all 7 core agents and engines, uses the specified contexts for grounding, and adheres to the constructivist pedagogical constraints. 

Where deviations occur, they are **extensions** designed to make the system more robust, generalizable, or mathematically sound (e.g., recursive diagnostic rollback instead of 1-step rollback).

---

## 1. Knowledge Graph (`core/knowledge_graph.py`)

*   **Slide Alignment:** The slides mandate a fine-grained concept graph with prerequisites, difficulty, and Bloom's taxonomy ceilings.
*   **Implementation:** Implemented as a Directed Acyclic Graph (DAG) containing `ConceptNode` objects.
*   **Extensions/Deviations:** 
    *   **Global vs. Personal:** We implemented a *Global Knowledge Graph* containing all concepts from all courses, and a *Personal Learner Graph* (stored in the `LearnerModel`) which tracks which concepts the user is enrolled in and their individual mastery. This was necessary to allow a single user to learn from multiple courses without their graphs bleeding together unnecessarily.
    *   **Recursive Diagnostic Chain:** Added `get_diagnostic_chain()`. When a student fails a concept, instead of just checking the immediate prerequisite, the graph recursively traces back down the prerequisite tree to find the *root cause* of the failure (the deepest weak prerequisite).

## 2. Mastery Engine (`core/mastery_engine.py`)

*   **Slide Alignment:** The slides present a composite mastery formula: `M_new = 0.3 * eval_score + 0.7 * M_old` combined with an Ebbinghaus forgetting curve `M_effective = M_base * e^(-t/S)`.
*   **Implementation:** We implemented a **superset** of this formula. 
*   **Extensions/Deviations:** 
    *   The simple slide formula does not account for guessing or slipping. We incorporated **Bayesian Knowledge Tracing (BKT)** to calculate a preliminary probability, which is then blended with the slide's Exponential Moving Average (EMA) formula. 
    *   This provides a much more mathematically rigorous assessment of true mastery while still honoring the exact slide formula structure and the required Ebbinghaus time-decay mechanism.

## 3. Recommender Agent (Agent 1) (`agents/recommender.py`)

*   **Slide Alignment:** Must recommend concepts in the Zone of Proximal Development (ZPD) where prerequisite mastery > 0.5. Must handle diagnostic rollback on failure.
*   **Implementation:** Uses DSPy to recommend concepts by analyzing the topological order of the graph and the user's current mastery state.
*   **Extensions/Deviations:**
    *   **Global Fallback:** If the learner has mastered all concepts in their enrolled courses, the recommender will automatically search the *Global Knowledge Graph* and recommend new courses/concepts to enroll in.
    *   **Deep Diagnostic Rollback:** As mentioned above, it uses the recursive chain to recommend a structured review path rather than a single node.

## 4. Source Curator Agent (Agent 2) (`agents/source_curator.py`)

*   **Slide Alignment:** Gathers lecture transcripts, concept descriptions, and prerequisite context to create a unified source document.
*   **Implementation:** Fully implemented. Extracts the specific chunk of the transcript relevant to the concept, gathers definitions of prerequisites, and outputs a clean Markdown document.
*   **Extensions/Deviations:** None. Matches slides exactly.

## 5. Learning Curator Agent (Agent 3) (`agents/learning_curator.py`)

*   **Slide Alignment:** Generates the learning session using 3 contexts: Lecture Transcript, Global Doubts (crowdsourced), and User Personal Graph. Must adapt depth to mastery (Beginner: analogies, Advanced: math/proofs).
*   **Implementation:** Fully implemented using DSPy. The agent's prompt signature strictly enforces the inclusion of the 3 contexts and branches its output style based on the learner's incoming mastery level.
*   **Extensions/Deviations:** None. Matches slides exactly.

## 6. Doubt Resolver Agent (Agent 4) (`agents/doubt_resolver.py`)

*   **Slide Alignment:** Must resolve doubts using *only* concepts the learner already knows (Constructivist constraint). Must classify misconception types and store them.
*   **Implementation:** The agent receives a serialized list of the user's known concepts (`mastery > 0.2`) and is strictly prompted to use only those concepts for analogies. It classifies doubts into a taxonomy (definitional, relational, causal, procedural) and stores them in the `ConceptState`.
*   **Extensions/Deviations:** Added the same mastery-based depth rules (Beginner/Intermediate/Advanced) as the Learning Curator to ensure tonal consistency across the platform.

## 7. Question Generator Agent (Agent 5) (`agents/question_generator.py`)

*   **Slide Alignment:** Generates questions targeting the concept's Bloom's taxonomy ceiling, interleaving previous concepts to prevent isolated memorization.
*   **Implementation:** Uses DSPy to generate varied question types. It explicitly receives the learner's personal graph to select valid concepts for interleaving.
*   **Extensions/Deviations:** None. Matches slides exactly.

## 8. Evaluator Agent (Agent 6) (`agents/evaluator.py`)

*   **Slide Alignment:** Evaluates written answers against a rubric, generating a score and constructive feedback.
*   **Implementation:** Uses a DSPy Chain-of-Thought pipeline to assess semantic correctness, completeness, and reasoning, returning a normalized score (0.0 - 1.0) which is fed directly into the Mastery Engine.
*   **Extensions/Deviations:** None. Matches slides exactly.

## 9. RAG Pipeline (`data/rag_pipeline.py`)

*   **Slide Alignment:** Ingest YouTube courses and dynamically build the knowledge graph.
*   **Implementation:** Uses `yt-dlp` to fetch transcripts and Gemini to extract atomic concepts, build the prerequisite DAG, and assign difficulty.
*   **Extensions/Deviations:** 
    *   **Transcript Chunking:** Added a chunking mechanism because full course transcripts frequently exceed the LLM context window (or API token limits). The pipeline splits the transcript, extracts concepts from each chunk, and merges/deduplicates them into a unified graph.

## 10. LLM Configuration (`core/llm_config.py` & `.env`)

*   **Implementation:** Centralized configuration that allows seamless swapping between Cloud APIs (like Gemini 2.0 Flash or Gemma 4 31B via Google API) and local models (like Ollama). Currently configured to use `gemini/gemma-4-31b-it` via the Google Generative AI API.

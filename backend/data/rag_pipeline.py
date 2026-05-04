"""
RAG Pipeline: YouTube URL → Knowledge Graph

Takes a YouTube video or playlist URL, fetches transcripts, uses LLM to extract
fine-grained atomic concepts, and builds a hierarchical knowledge graph.

Hierarchy: Course → Lectures → Concepts

Concepts are atomic and generic (not namespaced to a course) so they can be
shared across courses in a personal knowledge graph.

Supports merging new courses into an existing global knowledge graph and
skipping re-processing for already-ingested courses.
"""

import os
import json
from datetime import datetime, timezone

from backend.data.youtube_service import CourseInfo, fetch_course_from_url
from backend.core.knowledge_graph import KnowledgeGraph, ConceptNode, BloomLevel, CourseMetadata


DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)))
RAW_DIR = os.path.join(DATA_DIR, "raw")


def extract_concepts_with_llm(course: CourseInfo, api_key: str) -> dict | None:
    """
    Use Gemini to extract fine-grained atomic concepts from lecture transcripts.

    If the combined transcript exceeds MAX_INPUT_CHARS, it is chunked into
    segments, concepts are extracted from each chunk, and results are
    merged/deduplicated.

    Returns structured concept data with course hierarchy, or None on failure.
    """
    from google import genai
    from backend.core.llm_config import get_llm_config, needs_chunking, chunk_text

    client = genai.Client(api_key=api_key)
    config = get_llm_config()
    max_chars = config["max_input_chars"]

    # Use model from env if set, otherwise default to gemini-2.0-flash
    model_name = os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash")
    # Strip DSPy prefix (e.g. "gemini/gemini-2.0-flash" → "gemini-2.0-flash")
    if "/" in model_name:
        model_name = model_name.split("/", 1)[1]
    print(f"  Using model: {model_name}")

    # Build context from transcripts
    combined = ""
    lecture_list = []
    for video in course.videos:
        if video.transcript:
            combined += f"\n\n=== LECTURE {video.index + 1}: {video.title} ===\n{video.transcript}"
            lecture_list.append(f"Lecture {video.index + 1}: {video.title}")

    if not combined:
        print("ERROR: No transcripts available for concept extraction.")
        return None

    lectures_str = "\n".join(lecture_list)

    # Check if we need chunking
    if needs_chunking(combined, max_chars):
        print(f"  📦 Transcript ({len(combined)} chars) exceeds limit ({max_chars}). Chunking...")
        return _extract_concepts_chunked(client, model_name, course, combined, lectures_str, max_chars)

    # Single-pass extraction (transcript fits in context)
    return _extract_concepts_single(client, model_name, course, combined, lectures_str)


def _build_extraction_prompt(course: CourseInfo, transcript_text: str, lectures_str: str) -> str:
    """Build the concept extraction prompt."""
    return f"""You are an expert in computer science pedagogy and knowledge graph construction.

COURSE: {course.course_name}
INSTRUCTOR/CHANNEL: {course.channel}
LECTURES:
{lectures_str}

TRANSCRIPTS:
{transcript_text}

TASK: Extract ALL atomic concepts taught across these lectures. Build a fine-grained concept graph suitable for a personalised learning system.

CRITICAL RULES:
1. Concepts must be ATOMIC — each concept teaches exactly ONE idea/skill
2. Concept IDs must be GENERIC (e.g., "gradient_descent", "binary_search", "recursion") — NOT course-specific. These concepts will be shared across courses in a personal knowledge graph.
3. Extract 15-35 concepts depending on lecture content density
4. Prerequisites must form a DAG (no cycles)
5. Difficulty should reflect actual cognitive load (0.1 = trivial, 0.9 = very hard)
6. Every concept ID used in prerequisites MUST be defined in the concepts list
7. Include concepts from ALL lectures that have transcripts
8. Common misconceptions should be REAL student mistakes

Return a JSON object with this EXACT structure:
{{
  "course_name": "{course.course_name}",
  "channel": "{course.channel}",
  "lectures": [
    {{"index": 0, "title": "Lecture title", "video_id": "abc123"}}
  ],
  "concepts": [
    {{
      "id": "snake_case_generic_id",
      "name": "Human Readable Name",
      "description": "A clear 2-3 sentence description of this concept as taught in the lectures. Reference specific examples or explanations from the transcript.",
      "difficulty": 0.0,
      "bloom_ceiling": "remember|understand|apply|analyse|evaluate|create",
      "prerequisites": ["id_of_prereq1"],
      "related_concepts": ["id_of_related"],
      "common_misconceptions": ["misconception text"],
      "lecture_source": "Exact lecture title from the list above",
      "key_terms": ["term1", "term2"],
      "example_questions": ["A sample question to test understanding"]
    }}
  ]
}}

Return ONLY valid JSON, no markdown formatting or code fences."""


def _parse_llm_response(text: str) -> dict | None:
    """Parse and clean LLM JSON response."""
    text = text.strip()
    # Clean potential markdown wrapping
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        if text.endswith("```"):
            text = text.rsplit("```", 1)[0]
        elif "```" in text:
            text = text.rsplit("```", 1)[0]

    try:
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"  ⚠ JSON parse error: {e}")
        print(f"  Raw response (first 500 chars): {text[:500]}")
        return None


def _extract_concepts_single(client, model_name: str, course: CourseInfo,
                              combined: str, lectures_str: str) -> dict | None:
    """Extract concepts from transcript in a single pass."""
    prompt = _build_extraction_prompt(course, combined, lectures_str)

    print("  Calling Gemini for concept extraction...")
    try:
        response = client.models.generate_content(model=model_name, contents=prompt)
        result = _parse_llm_response(response.text)
        if result:
            print(f"  ✓ Extracted {len(result.get('concepts', []))} concepts")
        return result
    except Exception as e:
        error_msg = str(e).lower()
        if "quota" in error_msg or "resource_exhausted" in error_msg or "429" in error_msg:
            print(f"  ⚠ API quota exhausted: {e}")
            raise RuntimeError(
                "Gemini API quota exhausted. Your free tier daily limit has been reached. "
                "Either wait for the quota to reset (usually next day), upgrade to a paid plan "
                "at https://ai.google.dev, or use a different API key."
            ) from e
        print(f"  ⚠ LLM error: {e}")
        return None


def _extract_concepts_chunked(client, model_name: str, course: CourseInfo,
                                combined: str, lectures_str: str,
                                max_chars: int) -> dict | None:
    """
    Extract concepts from chunked transcript segments and merge results.
    Used when the combined transcript exceeds model context.
    """
    from backend.core.llm_config import chunk_text
    
    chunks = chunk_text(combined, max_chars=max_chars - 3000)  # Reserve space for prompt
    print(f"  Split into {len(chunks)} chunks")

    all_concepts = {}
    for i, chunk in enumerate(chunks):
        print(f"  Processing chunk {i + 1}/{len(chunks)} ({len(chunk)} chars)...")
        prompt = _build_extraction_prompt(course, chunk, lectures_str)

        try:
            response = client.models.generate_content(model=model_name, contents=prompt)
            result = _parse_llm_response(response.text)

            if result and "concepts" in result:
                for concept in result["concepts"]:
                    cid = concept["id"]
                    if cid not in all_concepts:
                        all_concepts[cid] = concept
                    else:
                        # Merge: combine misconceptions, key_terms, example_questions
                        existing = all_concepts[cid]
                        for field in ["common_misconceptions", "key_terms", "example_questions"]:
                            for item in concept.get(field, []):
                                if item not in existing.get(field, []):
                                    existing.setdefault(field, []).append(item)

                print(f"    ✓ Got {len(result.get('concepts', []))} concepts from chunk {i + 1}")
        except Exception as e:
            print(f"    ⚠ Chunk {i + 1} failed: {e}")
            continue

    if not all_concepts:
        print("  ⚠ No concepts extracted from any chunk")
        return None

    # Validate prerequisites — only keep ones that reference defined concepts
    defined_ids = set(all_concepts.keys())
    for cid, concept in all_concepts.items():
        concept["prerequisites"] = [p for p in concept.get("prerequisites", []) if p in defined_ids]
        concept["related_concepts"] = [r for r in concept.get("related_concepts", []) if r in defined_ids]

    merged_result = {
        "course_name": course.course_name,
        "channel": course.channel,
        "concepts": list(all_concepts.values()),
    }
    print(f"  ✓ Merged: {len(all_concepts)} unique concepts from {len(chunks)} chunks")
    return merged_result



def build_knowledge_graph_from_concepts(concept_data: dict) -> KnowledgeGraph:
    """Convert extracted concept data into a KnowledgeGraph with hierarchy metadata."""
    kg = KnowledgeGraph()

    concepts = concept_data.get("concepts", [])
    defined_ids = {c["id"] for c in concepts}

    for c in concepts:
        # Validate prerequisites — only include ones that are defined
        valid_prereqs = [p for p in c.get("prerequisites", []) if p in defined_ids]
        valid_related = [r for r in c.get("related_concepts", []) if r in defined_ids]

        try:
            bloom = BloomLevel(c.get("bloom_ceiling", "understand"))
        except ValueError:
            bloom = BloomLevel.UNDERSTAND

        node = ConceptNode(
            id=c["id"],
            name=c["name"],
            description=c.get("description", ""),
            difficulty=float(c.get("difficulty", 0.5)),
            bloom_ceiling=bloom,
            prerequisites=valid_prereqs,
            related_concepts=valid_related,
            common_misconceptions=c.get("common_misconceptions", []),
            lecture_source=c.get("lecture_source", ""),
            key_terms=c.get("key_terms", []),
            example_questions=c.get("example_questions", []),
        )
        kg.add_concept(node)

    # Build course metadata
    course_name = concept_data.get("course_name", "Unknown Course")
    channel = concept_data.get("channel", "")
    lectures = concept_data.get("lectures", [])
    playlist_id = concept_data.get("playlist_id", "")

    course_meta = CourseMetadata(
        course_name=course_name,
        channel=channel,
        playlist_id=playlist_id,
        lectures=lectures,
        concept_ids=list(defined_ids),
        ingested_at=datetime.now(timezone.utc).isoformat(),
    )
    kg.add_course_metadata(course_meta)

    # Set legacy fields
    kg.course_name = course_name
    kg.channel = channel
    kg.lectures = lectures

    return kg


def run_rag_pipeline(
    youtube_url: str,
    existing_kg: KnowledgeGraph = None,
) -> tuple[KnowledgeGraph | None, list[str], bool]:
    """
    Main RAG pipeline: YouTube URL → transcripts → concepts → knowledge graph.

    Args:
        youtube_url: A YouTube video or playlist URL.
        existing_kg: Optional existing KG to merge into (instead of replacing).

    Returns:
        Tuple of:
        - KnowledgeGraph (updated or new), or None on failure
        - list of concept IDs in this course (for enrollment)
        - bool: True if course was already ingested (skipped re-processing)
    """
    from dotenv import load_dotenv
    load_dotenv(os.path.join(DATA_DIR, "..", ".env"))

    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        raise ValueError("GOOGLE_API_KEY not set in backend/.env. Please add your Gemini API key.")

    print("=" * 60)
    print("RAG Pipeline: YouTube → Knowledge Graph")
    print("=" * 60)

    # Step 0: Parse URL to check for duplicates
    from backend.data.youtube_service import parse_youtube_url
    parsed = parse_youtube_url(youtube_url)
    identifier = parsed.get("playlist_id") or parsed.get("video_id") or ""

    # Check if course was already ingested
    if existing_kg and identifier and existing_kg.has_course(identifier):
        course_meta = existing_kg.get_course(identifier)
        print(f"\n✅ Course already ingested: {course_meta.course_name}")
        print(f"   Returning existing concept IDs for enrollment.")
        return existing_kg, course_meta.concept_ids, True

    # Step 1: Fetch course info and transcripts
    print(f"\n📥 Step 1: Fetching from YouTube...")
    try:
        course = fetch_course_from_url(youtube_url)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch from YouTube: {e}") from e

    if course.transcripts_fetched == 0:
        raise RuntimeError(
            f"No transcripts could be fetched for any of the {course.lecture_count} video(s). "
            f"This may be because the video has no captions/subtitles, or YouTube is blocking transcript access. "
            f"Try a different video or playlist with available captions."
        )

    # Save raw data
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(os.path.join(RAW_DIR, "course_info.json"), "w") as f:
        json.dump(course.to_dict(), f, indent=2)
    print(f"  Saved course info to raw/course_info.json")

    # Step 2: Extract concepts with LLM
    print(f"\n🧠 Step 2: Extracting concepts with Gemini...")
    concept_data = extract_concepts_with_llm(course, api_key)

    if not concept_data:
        raise RuntimeError(
            "LLM concept extraction failed. The Gemini API may have returned an invalid response, "
            "or the API key may be invalid/rate-limited. Check the server logs for details."
        )

    # Always use real video metadata from YouTube (LLM often hallucinates video IDs)
    concept_data["lectures"] = [
        {"index": v.index, "title": v.title, "video_id": v.video_id}
        for v in course.videos
    ]

    # Store playlist_id for dedup
    concept_data["playlist_id"] = identifier

    # Save extracted concepts
    with open(os.path.join(RAW_DIR, "extracted_concepts.json"), "w") as f:
        json.dump(concept_data, f, indent=2)
    print(f"  Saved extracted concepts to raw/extracted_concepts.json")

    # Step 3: Build knowledge graph
    print(f"\n🔗 Step 3: Building knowledge graph...")
    new_kg = build_knowledge_graph_from_concepts(concept_data)

    # Collect concept IDs from this course
    course_concept_ids = list(new_kg.concepts.keys())

    # Merge into existing KG if provided
    if existing_kg:
        print(f"  Merging into existing graph ({len(existing_kg.concepts)} concepts)...")
        new_ids = existing_kg.merge(new_kg)
        print(f"  ✓ Added {len(new_ids)} new concepts (skipped {len(course_concept_ids) - len(new_ids)} duplicates)")
        result_kg = existing_kg
    else:
        result_kg = new_kg

    # Validate
    issues = result_kg.validate()
    if issues:
        print(f"  ⚠ Validation issues: {issues}")
    else:
        print("  ✓ Graph is valid (DAG, no dangling references)")

    # Save
    kg_path = os.path.join(DATA_DIR, "knowledge_graph.json")
    result_kg.save(kg_path)

    # Save concept-to-transcript mapping for RAG retrieval
    concept_sources = {}
    # Load existing sources if merging
    sources_path = os.path.join(RAW_DIR, "concept_sources.json")
    if existing_kg and os.path.exists(sources_path):
        with open(sources_path, "r") as f:
            concept_sources = json.load(f)

    for c in concept_data.get("concepts", []):
        lecture = c.get("lecture_source", "")
        for v in course.videos:
            if lecture and (lecture in v.title or v.title in lecture):
                concept_sources[c["id"]] = {
                    "video_id": v.video_id,
                    "title": v.title,
                    "transcript_excerpt": v.transcript if v.transcript else "",
                }
                break

    with open(sources_path, "w") as f:
        json.dump(concept_sources, f, indent=2)
    print(f"  Mapped {len(concept_sources)} concepts to source transcripts")

    print(f"\n{result_kg.summary()}")
    print(f"\n✅ RAG Pipeline complete!")
    print(f"  Course: {new_kg.course_name}")
    print(f"  Lectures: {len(new_kg.lectures)}")
    print(f"  Concepts in this course: {len(course_concept_ids)}")
    print(f"  Total concepts in graph: {len(result_kg.concepts)}")

    return result_kg, course_concept_ids, False


def run_rag_pipeline_from_topic(
    topic: str,
    existing_kg: KnowledgeGraph = None,
) -> tuple[KnowledgeGraph | None, list[str], bool]:
    """
    RAG pipeline variant: Topic string → YouTube search → transcripts → concepts → KG.

    Instead of a YouTube URL, this accepts a topic string, searches YouTube for
    the best lectures, and runs the same extraction pipeline.

    Args:
        topic: The topic to search for (e.g. "binary search algorithm")
        existing_kg: Optional existing KG to merge into.

    Returns:
        Same tuple as run_rag_pipeline: (KnowledgeGraph, concept_ids, already_ingested)
    """
    from dotenv import load_dotenv
    load_dotenv(os.path.join(DATA_DIR, "..", ".env"))

    api_key = os.getenv("GOOGLE_API_KEY", "")
    if not api_key or api_key.startswith("your_"):
        raise ValueError("GOOGLE_API_KEY not set in backend/.env. Please add your Gemini API key.")

    # Check if this topic was already ingested
    topic_id = f"topic_{topic.lower().replace(' ', '_')}"
    if existing_kg and existing_kg.has_course(topic_id):
        course_meta = existing_kg.get_course(topic_id)
        print(f"\n✅ Topic already ingested: {course_meta.course_name}")
        return existing_kg, course_meta.concept_ids, True

    print("=" * 60)
    print(f"RAG Pipeline: Topic Search → Knowledge Graph")
    print(f"  Topic: {topic}")
    print("=" * 60)

    # Step 1: Search YouTube and fetch transcripts
    from backend.data.youtube_service import build_course_from_search
    try:
        course = build_course_from_search(topic, max_results=5)
    except Exception as e:
        raise RuntimeError(f"Topic search failed: {e}") from e

    if course.transcripts_fetched == 0:
        raise RuntimeError(
            f"No transcripts could be fetched for any videos found for '{topic}'. "
            f"Try a more specific topic or use a direct YouTube URL."
        )

    # Save raw data
    os.makedirs(RAW_DIR, exist_ok=True)
    with open(os.path.join(RAW_DIR, "course_info.json"), "w") as f:
        json.dump(course.to_dict(), f, indent=2)

    # Step 2: Extract concepts with LLM
    print(f"\n🧠 Step 2: Extracting concepts with Gemini...")
    concept_data = extract_concepts_with_llm(course, api_key)

    if not concept_data:
        raise RuntimeError("LLM concept extraction failed after topic search.")

    concept_data["lectures"] = [
        {"index": v.index, "title": v.title, "video_id": v.video_id}
        for v in course.videos
    ]
    concept_data["playlist_id"] = topic_id

    with open(os.path.join(RAW_DIR, "extracted_concepts.json"), "w") as f:
        json.dump(concept_data, f, indent=2)

    # Step 3: Build knowledge graph
    print(f"\n🔗 Step 3: Building knowledge graph...")
    new_kg = build_knowledge_graph_from_concepts(concept_data)
    course_concept_ids = list(new_kg.concepts.keys())

    if existing_kg:
        new_ids = existing_kg.merge(new_kg)
        result_kg = existing_kg
    else:
        result_kg = new_kg

    kg_path = os.path.join(DATA_DIR, "knowledge_graph.json")
    result_kg.save(kg_path)

    # Save concept-to-transcript mapping
    concept_sources = {}
    sources_path = os.path.join(RAW_DIR, "concept_sources.json")
    if existing_kg and os.path.exists(sources_path):
        with open(sources_path, "r") as f:
            concept_sources = json.load(f)

    for c in concept_data.get("concepts", []):
        lecture = c.get("lecture_source", "")
        for v in course.videos:
            if lecture and (lecture in v.title or v.title in lecture):
                concept_sources[c["id"]] = {
                    "video_id": v.video_id,
                    "title": v.title,
                    "transcript_excerpt": v.transcript if v.transcript else "",
                }
                break

    with open(sources_path, "w") as f:
        json.dump(concept_sources, f, indent=2)

    print(f"\n✅ Topic Pipeline complete! ({len(course_concept_ids)} concepts)")
    return result_kg, course_concept_ids, False


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python -m backend.data.rag_pipeline <youtube_url>")
        print("  Example: python -m backend.data.rag_pipeline 'https://www.youtube.com/playlist?list=PLBlnK6fEyqRj9lld8sWIUNwlKfdUoPd1Y'")
        sys.exit(1)

    url = sys.argv[1]
    run_rag_pipeline(url)

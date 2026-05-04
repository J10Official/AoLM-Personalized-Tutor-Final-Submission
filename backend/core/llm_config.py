"""
Centralised LLM Configuration for the Personalised Learning System.

Handles:
1. Model selection (Gemini cloud API or Ollama local)
2. Input chunking for large transcripts that exceed model context
3. DSPy configuration
"""

import os
import math
from dotenv import load_dotenv

# Load .env from backend directory
_env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
load_dotenv(_env_path)


def get_llm_config() -> dict:
    """Get current LLM configuration from environment."""
    return {
        "model": os.getenv("LLM_MODEL", "gemini/gemini-2.0-flash"),
        "api_key": os.getenv("GOOGLE_API_KEY", ""),
        "max_input_chars": int(os.getenv("MAX_INPUT_CHARS", "200000")),
    }


def configure_dspy_lm():
    """
    Configure DSPy with the LLM specified in .env.
    Returns the configured LM object or None on failure.
    """
    import dspy
    config = get_llm_config()
    model_name = config["model"]
    api_key = config["api_key"]

    try:
        if model_name.startswith("ollama/"):
            # Local Ollama — no API key needed
            base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
            lm = dspy.LM(model_name, api_base=base_url)
        else:
            # Cloud API (Gemini, OpenAI, etc.)
            if not api_key:
                print("WARNING: No API key found. LLM features disabled.")
                return None
            lm = dspy.LM(model_name, api_key=api_key)

        dspy.configure(lm=lm)
        print(f"DSPy configured: {model_name}")
        return lm
    except Exception as e:
        print(f"WARNING: DSPy configuration failed: {e}")
        return None


# ========================================
# Input Chunking Utilities
# ========================================

def chunk_text(text: str, max_chars: int = None, overlap: int = 500) -> list[str]:
    """
    Split text into overlapping chunks that fit within the model context.

    Args:
        text: The input text to chunk.
        max_chars: Maximum characters per chunk. Defaults to MAX_INPUT_CHARS from env.
        overlap: Characters of overlap between consecutive chunks.

    Returns:
        List of text chunks. Returns [text] if no chunking needed.
    """
    if max_chars is None:
        max_chars = int(os.getenv("MAX_INPUT_CHARS", "200000"))

    if len(text) <= max_chars:
        return [text]

    chunks = []
    start = 0
    while start < len(text):
        end = start + max_chars

        # Try to break at a paragraph or sentence boundary
        if end < len(text):
            # Look for paragraph break
            para_break = text.rfind("\n\n", start + max_chars // 2, end)
            if para_break > start:
                end = para_break + 2
            else:
                # Look for sentence break
                sent_break = text.rfind(". ", start + max_chars // 2, end)
                if sent_break > start:
                    end = sent_break + 2

        chunks.append(text[start:end])
        start = end - overlap  # Overlap for context continuity

        # Avoid infinite loop on very small overlap
        if start >= len(text) - overlap:
            break

    return chunks


def needs_chunking(text: str, max_chars: int = None) -> bool:
    """Check if text exceeds the model's input limit and needs chunking."""
    if max_chars is None:
        max_chars = int(os.getenv("MAX_INPUT_CHARS", "200000"))
    return len(text) > max_chars

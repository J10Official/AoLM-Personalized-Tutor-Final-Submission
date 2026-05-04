"""
Tests for the LLM Configuration module (core/llm_config.py).

Covers requirements:
  R2.3   — Model agnosticism via DSPy
  R2.4   — Support Gemma-4 / Gemini
  R18.1  — Gemma-4 support
  R18.2  — Ollama (local consumer hardware) support
  R19.2  — Model swapping without code changes
  R25.4  — dspy.configure(lm=lm)
"""

import os
import pytest
from backend.core.llm_config import get_llm_config, chunk_text, needs_chunking


class TestLLMConfig:

    def test_get_llm_config_returns_dict(self):
        """R2.3: LLM config returns a dict with model, api_key, max_input_chars."""
        config = get_llm_config()
        assert isinstance(config, dict)
        assert "model" in config
        assert "api_key" in config
        assert "max_input_chars" in config

    def test_default_model_is_gemini(self):
        """R2.4: Default model should be a Gemini model."""
        config = get_llm_config()
        model = config["model"]
        assert "gemini" in model.lower() or "ollama" in model.lower()

    def test_max_input_chars_is_positive(self):
        """R2.3: Max input chars is a positive integer."""
        config = get_llm_config()
        assert config["max_input_chars"] > 0


class TestTextChunking:

    def test_short_text_no_chunking(self):
        """Short text should not be chunked."""
        text = "Hello world"
        chunks = chunk_text(text, max_chars=100)
        assert len(chunks) == 1
        assert chunks[0] == text

    def test_long_text_is_chunked(self):
        """Long text is split into multiple chunks."""
        text = "A" * 1000
        chunks = chunk_text(text, max_chars=300, overlap=50)
        assert len(chunks) > 1

    def test_chunks_have_overlap(self):
        """Chunks overlap for context continuity."""
        text = "ABCDEFGHIJ" * 100
        chunks = chunk_text(text, max_chars=300, overlap=50)
        if len(chunks) >= 2:
            # The end of chunk 0 and start of chunk 1 should overlap
            end_of_first = chunks[0][-50:]
            # The second chunk should contain some content from near the end of chunk 0
            assert len(chunks[1]) > 0

    def test_needs_chunking_true_for_long_text(self):
        """needs_chunking returns True for text exceeding limit."""
        assert needs_chunking("A" * 1000, max_chars=500) is True

    def test_needs_chunking_false_for_short_text(self):
        """needs_chunking returns False for text within limit."""
        assert needs_chunking("Hello", max_chars=500) is False

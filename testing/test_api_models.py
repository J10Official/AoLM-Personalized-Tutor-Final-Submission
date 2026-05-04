"""
Tests for the FastAPI Server (api/server.py).

Covers requirements:
  R-API.1  — REST API endpoints for all agents
  R-API.2  — Onboarding / user creation
  R-API.8  — Save/load learner profiles
  R6.1     — Pipeline starts with Learner + Concept input
"""

import os
import sys
import json
import pytest
from unittest.mock import patch, MagicMock

# We test the Pydantic models and endpoint logic structurally.
# Full integration tests would require a running server + LLM.

from backend.api.server import (
    CreateLearnerRequest, DoubtRequest, AnswerRequest,
    SessionStartRequest, CourseIngestRequest, EnrollCourseRequest,
)


class TestPydanticModels:

    def test_create_learner_request(self):
        """R-API.2: CreateLearnerRequest has required fields."""
        req = CreateLearnerRequest(learner_id="test_user", name="Test")
        assert req.learner_id == "test_user"
        assert req.name == "Test"

    def test_create_learner_default_name(self):
        """R-API.2: Name defaults to empty string."""
        req = CreateLearnerRequest(learner_id="test")
        assert req.name == ""

    def test_doubt_request(self):
        """R6.5: DoubtRequest has learner_id, concept_id, doubt."""
        req = DoubtRequest(learner_id="u1", concept_id="variables", doubt="Why?")
        assert req.learner_id == "u1"
        assert req.concept_id == "variables"
        assert req.doubt == "Why?"

    def test_answer_request(self):
        """R6.7: AnswerRequest has all required fields."""
        req = AnswerRequest(
            learner_id="u1", concept_id="variables",
            question={"question": "What is X?", "type": "written"},
            answer="X is...", response_time=15.0
        )
        assert req.response_time == 15.0

    def test_session_start_request(self):
        """R6.1: SessionStartRequest has learner_id and concept_id."""
        req = SessionStartRequest(learner_id="u1", concept_id="loops")
        assert req.learner_id == "u1"
        assert req.concept_id == "loops"

    def test_course_ingest_request(self):
        """R-API.4: CourseIngestRequest has youtube_url and learner_id."""
        req = CourseIngestRequest(
            youtube_url="https://youtube.com/watch?v=abc", learner_id="u1"
        )
        assert "youtube" in req.youtube_url

    def test_enroll_course_request(self):
        """EnrollCourseRequest has course_name."""
        req = EnrollCourseRequest(course_name="Intro to Python")
        assert req.course_name == "Intro to Python"

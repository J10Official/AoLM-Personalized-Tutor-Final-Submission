"""
Tests for the YouTube Service (data/youtube_service.py).

Covers requirements:
  R9.1   — Scrape NPTEL / YouTube course structures
  R9.2   — Extract YouTube transcripts
  R-API.4 — YouTube course ingestion
"""

import pytest
from backend.data.youtube_service import parse_youtube_url, VideoInfo, CourseInfo


class TestParseYouTubeURL:

    def test_standard_video_url(self):
        """Parse standard youtube.com/watch?v=... URL."""
        result = parse_youtube_url("https://www.youtube.com/watch?v=dQw4w9WgXcQ")
        assert result["type"] == "video"
        assert result["video_id"] == "dQw4w9WgXcQ"
        assert result["playlist_id"] is None

    def test_short_url(self):
        """Parse youtu.be/... short URL."""
        result = parse_youtube_url("https://youtu.be/dQw4w9WgXcQ")
        assert result["type"] == "video"
        assert result["video_id"] == "dQw4w9WgXcQ"

    def test_playlist_url(self):
        """Parse youtube.com/playlist?list=... URL."""
        result = parse_youtube_url(
            "https://www.youtube.com/playlist?list=PLBlnK6fEyqRj9lld8sWIUNwlKfdUoPd1Y"
        )
        assert result["type"] == "playlist"
        assert result["playlist_id"] == "PLBlnK6fEyqRj9lld8sWIUNwlKfdUoPd1Y"

    def test_video_with_playlist(self):
        """Parse video URL that includes a playlist parameter."""
        result = parse_youtube_url(
            "https://www.youtube.com/watch?v=abc123&list=PLxyz"
        )
        assert result["type"] == "playlist"  # playlist takes priority
        assert result["video_id"] == "abc123"
        assert result["playlist_id"] == "PLxyz"

    def test_mobile_url(self):
        """Parse m.youtube.com URL."""
        result = parse_youtube_url("https://m.youtube.com/watch?v=testid12345")
        assert result["video_id"] == "testid12345"

    def test_invalid_url(self):
        """Invalid URL returns None types."""
        result = parse_youtube_url("https://example.com/notavideopage")
        assert result["type"] is None
        assert result["video_id"] is None

    def test_url_with_whitespace(self):
        """URL with leading/trailing whitespace is handled."""
        result = parse_youtube_url("  https://www.youtube.com/watch?v=abc123  ")
        assert result["video_id"] == "abc123"


class TestVideoInfo:

    def test_video_info_to_dict(self):
        """VideoInfo serialises to dict correctly."""
        v = VideoInfo(video_id="vid1", title="Lecture 1", index=0, transcript="hello")
        d = v.to_dict()
        assert d["video_id"] == "vid1"
        assert d["title"] == "Lecture 1"
        assert d["transcript"] == "hello"


class TestCourseInfo:

    def test_course_info_properties(self):
        """CourseInfo computes lecture_count and transcripts_fetched."""
        course = CourseInfo(
            course_name="Test Course",
            videos=[
                VideoInfo("v1", "Lec 1", 0, transcript="text"),
                VideoInfo("v2", "Lec 2", 1, transcript=""),
                VideoInfo("v3", "Lec 3", 2, transcript="text"),
            ],
        )
        assert course.lecture_count == 3
        assert course.transcripts_fetched == 2

    def test_course_info_to_dict(self):
        """CourseInfo serialises to dict."""
        course = CourseInfo(course_name="Test", channel="Channel")
        d = course.to_dict()
        assert d["course_name"] == "Test"
        assert d["channel"] == "Channel"

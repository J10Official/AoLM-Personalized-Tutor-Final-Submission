"""
YouTube Service: URL parsing, playlist metadata, and transcript fetching.

Handles both single video URLs and playlist URLs. Uses yt-dlp for playlist
metadata extraction and youtube-transcript-api for transcript retrieval.
"""

import re
import time
from dataclasses import dataclass, field
from urllib.parse import urlparse, parse_qs

from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.formatters import TextFormatter


@dataclass
class VideoInfo:
    """Metadata for a single YouTube video."""
    video_id: str
    title: str
    index: int = 0  # Position in playlist (0-based)
    transcript: str = ""
    transcript_length: int = 0

    def to_dict(self) -> dict:
        return {
            "video_id": self.video_id,
            "title": self.title,
            "index": self.index,
            "transcript": self.transcript,
            "transcript_length": self.transcript_length,
        }


@dataclass
class CourseInfo:
    """Metadata for a YouTube course (playlist or single video)."""
    course_name: str
    channel: str = ""
    is_playlist: bool = False
    playlist_id: str = ""
    videos: list[VideoInfo] = field(default_factory=list)

    @property
    def lecture_count(self) -> int:
        return len(self.videos)

    @property
    def transcripts_fetched(self) -> int:
        return sum(1 for v in self.videos if v.transcript)

    def to_dict(self) -> dict:
        return {
            "course_name": self.course_name,
            "channel": self.channel,
            "is_playlist": self.is_playlist,
            "playlist_id": self.playlist_id,
            "lecture_count": self.lecture_count,
            "transcripts_fetched": self.transcripts_fetched,
            "videos": [v.to_dict() for v in self.videos],
        }


# ============================================================
# URL Parsing
# ============================================================

def parse_youtube_url(url: str) -> dict:
    """
    Parse a YouTube URL and determine its type.

    Returns:
        {
            "type": "video" | "playlist",
            "video_id": str | None,
            "playlist_id": str | None,
        }
    """
    url = url.strip()
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    result = {"type": None, "video_id": None, "playlist_id": None}

    # Check for playlist
    if "list" in params:
        result["playlist_id"] = params["list"][0]
        result["type"] = "playlist"

    # Check for video ID
    if parsed.hostname in ("www.youtube.com", "youtube.com", "m.youtube.com"):
        if "v" in params:
            result["video_id"] = params["v"][0]
            if not result["type"]:
                result["type"] = "video"
    elif parsed.hostname in ("youtu.be",):
        # youtu.be/VIDEO_ID
        video_id = parsed.path.lstrip("/")
        if video_id:
            result["video_id"] = video_id
            if not result["type"]:
                result["type"] = "video"

    # Fallback: try to extract video ID from path
    if not result["video_id"] and not result["playlist_id"]:
        # Try regex for video ID
        match = re.search(r"(?:v=|youtu\.be/)([\w-]{11})", url)
        if match:
            result["video_id"] = match.group(1)
            result["type"] = "video"

    return result


# ============================================================
# Playlist Metadata (via yt-dlp)
# ============================================================

def get_playlist_metadata(playlist_url: str) -> CourseInfo:
    """
    Extract playlist metadata using yt-dlp (flat extraction, no download).
    Returns CourseInfo with video IDs and titles.
    """
    import yt_dlp

    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(playlist_url, download=False)

    course_name = info.get("title", "Unknown Course")
    channel = info.get("channel", info.get("uploader", ""))

    videos = []
    for i, entry in enumerate(info.get("entries", [])):
        if entry is None:
            continue
        videos.append(VideoInfo(
            video_id=entry.get("id", entry.get("url", "")),
            title=entry.get("title", f"Lecture {i + 1}"),
            index=i,
        ))

    return CourseInfo(
        course_name=course_name,
        channel=channel,
        is_playlist=True,
        playlist_id=info.get("id", ""),
        videos=videos,
    )


def get_video_metadata(video_id: str) -> CourseInfo:
    """
    Get metadata for a single video using yt-dlp.
    Returns CourseInfo with one video entry.
    """
    import yt_dlp

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
    }

    url = f"https://www.youtube.com/watch?v={video_id}"

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)

    title = info.get("title", "Unknown Video")
    channel = info.get("channel", info.get("uploader", ""))

    video = VideoInfo(
        video_id=video_id,
        title=title,
        index=0,
    )

    return CourseInfo(
        course_name=title,  # For single videos, course name = video title
        channel=channel,
        is_playlist=False,
        videos=[video],
    )


# ============================================================
# Transcript Fetching
# ============================================================

def _fetch_transcript_ytdlp(video_id: str) -> str:
    """Fallback: fetch transcript via yt-dlp when youtube-transcript-api is IP-blocked."""
    try:
        import subprocess, json as _json, tempfile, glob
        url = f"https://www.youtube.com/watch?v={video_id}"
        with tempfile.TemporaryDirectory() as tmpdir:
            # Try auto-subtitles first (most videos), then manual subs
            cmd = [
                "yt-dlp",
                "--skip-download",
                "--write-auto-sub",
                "--write-sub",
                "--sub-lang", "en",
                "--sub-format", "json3",
                "-o", f"{tmpdir}/%(id)s.%(ext)s",
                url,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            # Find the subtitle file
            sub_files = glob.glob(f"{tmpdir}/*.json3")
            if not sub_files:
                # Try vtt format as fallback
                cmd[cmd.index("json3")] = "vtt"
                subprocess.run(cmd, capture_output=True, text=True, timeout=30)
                sub_files = glob.glob(f"{tmpdir}/*.vtt")
                if sub_files:
                    with open(sub_files[0], "r") as f:
                        lines = f.readlines()
                    # Parse VTT: skip header lines and timestamps, keep only text
                    text_lines = []
                    for line in lines:
                        line = line.strip()
                        if not line or line.startswith("WEBVTT") or "-->" in line or line.isdigit():
                            continue
                        # Strip HTML tags
                        import re
                        clean = re.sub(r"<[^>]+>", "", line)
                        if clean and clean not in text_lines[-1:]:
                            text_lines.append(clean)
                    return " ".join(text_lines)
                return ""

            # Parse json3 subtitle format
            with open(sub_files[0], "r") as f:
                data = _json.load(f)
            segments = data.get("events", [])
            text_parts = []
            for seg in segments:
                segs = seg.get("segs", [])
                for s in segs:
                    t = s.get("utf8", "").strip()
                    if t and t != "\n":
                        text_parts.append(t)
            return " ".join(text_parts)
    except Exception as e:
        print(f"  ⚠ yt-dlp subtitle fallback also failed for {video_id}: {e}")
        return ""


def fetch_transcript(video_id: str) -> str:
    """
    Fetch and format transcript for a single YouTube video.
    
    Strategy:
    1. Try youtube-transcript-api (fast, clean output)
    2. If IP-blocked, fall back to yt-dlp subtitle extraction
    """
    # Attempt 1: youtube-transcript-api
    try:
        ytt_api = YouTubeTranscriptApi()
        transcript = ytt_api.fetch(video_id)
        formatter = TextFormatter()
        text = formatter.format_transcript(transcript)
        return text
    except Exception as e:
        print(f"  ⚠ youtube-transcript-api failed for {video_id}: {e}")
        print(f"  ↳ Trying yt-dlp subtitle fallback...")

    # Attempt 2: yt-dlp fallback
    text = _fetch_transcript_ytdlp(video_id)
    if text:
        print(f"  ✓ yt-dlp fallback succeeded ({len(text)} chars)")
    return text


def fetch_all_transcripts(
    course: CourseInfo,
    max_chars_per_transcript: int = 200000,
    delay: float = 0.3,
    max_workers: int = 4,
) -> CourseInfo:
    """
    Fetch transcripts for all videos in a CourseInfo using parallel workers.
    Modifies the CourseInfo in place and returns it.

    Args:
        course: CourseInfo with video entries
        max_chars_per_transcript: Max chars to keep per transcript
        delay: Seconds to wait between requests (rate limiting per worker)
        max_workers: Number of parallel transcript fetch workers
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    def _fetch_one(video: VideoInfo) -> tuple[VideoInfo, str]:
        time.sleep(delay)  # light rate limiting
        transcript = fetch_transcript(video.video_id)
        return video, transcript

    total = len(course.videos)
    completed = 0

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(_fetch_one, video): video
            for video in course.videos
        }
        for future in as_completed(futures):
            video, transcript = future.result()
            completed += 1
            if transcript:
                video.transcript = transcript[:max_chars_per_transcript]
                video.transcript_length = len(transcript)
                print(f"  [{completed}/{total}] ✓ {video.title} ({len(transcript)} chars)")
            else:
                print(f"  [{completed}/{total}] ✗ {video.title} — no transcript")

    fetched = course.transcripts_fetched
    print(f"  Fetched {fetched}/{total} transcripts")
    return course


# ============================================================
# High-level helpers
# ============================================================

def fetch_course_from_url(url: str) -> CourseInfo:
    """
    Main entry point: parse a YouTube URL, get metadata, fetch transcripts.

    Supports:
    - Single video URLs (youtube.com/watch?v=... or youtu.be/...)
    - Playlist URLs (youtube.com/playlist?list=...)
    - Video URLs with playlist context (youtube.com/watch?v=...&list=...)
    """
    parsed = parse_youtube_url(url)

    if parsed["type"] == "playlist" and parsed["playlist_id"]:
        print(f"📋 Detected playlist: {parsed['playlist_id']}")
        playlist_url = f"https://www.youtube.com/playlist?list={parsed['playlist_id']}"
        course = get_playlist_metadata(playlist_url)
        print(f"  Course: {course.course_name} ({len(course.videos)} lectures)")
    elif parsed["type"] == "video" and parsed["video_id"]:
        print(f"🎬 Detected single video: {parsed['video_id']}")
        course = get_video_metadata(parsed["video_id"])
        print(f"  Video: {course.course_name}")
    else:
        raise ValueError(f"Could not parse YouTube URL: {url}")

    print(f"\n📥 Fetching transcripts...")
    fetch_all_transcripts(course)
    print(f"  Fetched {course.transcripts_fetched}/{course.lecture_count} transcripts")

    return course


# ============================================================
# Topic-Based YouTube Search
# ============================================================

def search_youtube_videos(topic: str, max_results: int = 5) -> list[VideoInfo]:
    """
    Search YouTube for lectures on a topic using yt-dlp.

    Uses yt-dlp's built-in ytsearch to find relevant videos,
    avoiding the need for a YouTube Data API key.

    Args:
        topic: Topic to search for (e.g. "binary search algorithm")
        max_results: Maximum number of videos to return (1-10)

    Returns:
        List of VideoInfo with video_id and title populated.
    """
    import yt_dlp

    max_results = min(max(max_results, 1), 10)
    search_query = f"ytsearch{max_results}:{topic} lecture tutorial"

    ydl_opts = {
        "extract_flat": True,
        "quiet": True,
        "no_warnings": True,
    }

    print(f"🔍 Searching YouTube for: '{topic}'")

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(search_query, download=False)

    videos = []
    for i, entry in enumerate(info.get("entries", [])):
        if entry is None:
            continue
        vid_id = entry.get("id", entry.get("url", ""))
        title = entry.get("title", f"Video {i + 1}")
        channel = entry.get("channel", entry.get("uploader", ""))
        print(f"  [{i + 1}] {title} ({vid_id}) — {channel}")
        videos.append(VideoInfo(
            video_id=vid_id,
            title=title,
            index=i,
        ))

    return videos


def build_course_from_search(topic: str, max_results: int = 5) -> CourseInfo:
    """
    Build a CourseInfo from YouTube search results for a given topic.

    Searches YouTube for lectures, creates a virtual "course" from the
    top results, and fetches transcripts.

    Args:
        topic: Topic to search for
        max_results: Maximum videos to include

    Returns:
        CourseInfo with transcripts fetched.
    """
    videos = search_youtube_videos(topic, max_results=max_results)

    if not videos:
        raise ValueError(f"No YouTube results found for topic: '{topic}'")

    # Determine channel from first video (for metadata)
    channel = ""
    try:
        import yt_dlp
        ydl_opts = {"quiet": True, "no_warnings": True, "skip_download": True}
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            first_info = ydl.extract_info(
                f"https://www.youtube.com/watch?v={videos[0].video_id}",
                download=False
            )
            channel = first_info.get("channel", first_info.get("uploader", ""))
    except Exception:
        pass

    # Build course name from topic
    course_name = f"{topic.title()} (Auto-curated)"

    course = CourseInfo(
        course_name=course_name,
        channel=channel or "Multiple Sources",
        is_playlist=False,
        playlist_id=f"topic_{topic.lower().replace(' ', '_')}",
        videos=videos,
    )

    print(f"\n📥 Fetching transcripts for {len(videos)} videos...")
    fetch_all_transcripts(course)
    print(f"  Fetched {course.transcripts_fetched}/{course.lecture_count} transcripts")

    # Filter out videos with no transcript
    original_count = len(course.videos)
    course.videos = [v for v in course.videos if v.transcript]
    if len(course.videos) < original_count:
        print(f"  Removed {original_count - len(course.videos)} videos with no transcript")

    # Re-index
    for i, v in enumerate(course.videos):
        v.index = i

    return course


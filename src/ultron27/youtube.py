from __future__ import annotations

import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any, Callable


YOUTUBE_SEARCH_ENDPOINT = "https://www.youtube.com/results"
YOUTUBE_WATCH_ENDPOINT = "https://www.youtube.com/watch"
DEFAULT_LOOKUP_TIMEOUT_SECONDS = 8.0
MAX_QUERY_LENGTH = 240
MAX_RESPONSE_BYTES = 4 * 1024 * 1024
MAX_CANDIDATE_VIDEOS = 6

_VIDEO_ID = re.compile(r"^[A-Za-z0-9_-]{11}$")
_VIDEO_RENDERER = re.compile(
    r'"videoRenderer"\s*:\s*\{\s*"videoId"\s*:\s*"(?P<video_id>[A-Za-z0-9_-]{11})"'
)
_YOUTUBE_HOSTS = {"youtube.com", "www.youtube.com", "m.youtube.com", "music.youtube.com"}


class YouTubeLookupError(RuntimeError):
    """Raised when a safe YouTube video target cannot be resolved."""


@dataclass(frozen=True)
class YouTubeVideo:
    query: str
    video_id: str
    search_url: str
    candidate_ids: tuple[str, ...] = ()

    @property
    def watch_url(self) -> str:
        return youtube_watch_url(self.video_id)


def normalize_youtube_query(query: str) -> str:
    normalized = " ".join(query.strip().split())
    if not normalized:
        raise ValueError("YouTube playback needs a video title, topic, or channel name.")
    if len(normalized) > MAX_QUERY_LENGTH:
        raise ValueError(f"YouTube queries are limited to {MAX_QUERY_LENGTH} characters.")
    if any(ord(char) < 32 for char in normalized):
        raise ValueError("YouTube query contains invalid control characters.")
    return normalized


def youtube_search_url(query: str) -> str:
    normalized = normalize_youtube_query(query)
    return f"{YOUTUBE_SEARCH_ENDPOINT}?{urllib.parse.urlencode({'search_query': normalized})}"


def youtube_watch_url(video_id: str) -> str:
    if not is_youtube_video_id(video_id):
        raise ValueError("YouTube returned an invalid video identifier.")
    return f"{YOUTUBE_WATCH_ENDPOINT}?{urllib.parse.urlencode({'v': video_id, 'autoplay': '1'})}"


def is_youtube_video_id(value: object) -> bool:
    return isinstance(value, str) and bool(_VIDEO_ID.fullmatch(value))


def youtube_video_id_from_url(value: str) -> str | None:
    candidate = value.strip()
    if not re.match(r"^https?://", candidate, flags=re.IGNORECASE):
        return None
    try:
        parsed = urllib.parse.urlparse(candidate)
    except ValueError:
        return None
    host = (parsed.hostname or "").lower().rstrip(".")
    video_id = ""
    if host == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif host in _YOUTUBE_HOSTS:
        if parsed.path.rstrip("/") == "/watch":
            video_id = urllib.parse.parse_qs(parsed.query).get("v", [""])[0]
        else:
            parts = [part for part in parsed.path.split("/") if part]
            if len(parts) >= 2 and parts[0].lower() in {"embed", "live", "shorts"}:
                video_id = parts[1]
    return video_id if is_youtube_video_id(video_id) else None


def is_safe_youtube_watch_url(value: str) -> bool:
    try:
        parsed = urllib.parse.urlparse(value)
    except ValueError:
        return False
    if parsed.scheme != "https" or parsed.username or parsed.password:
        return False
    if (parsed.hostname or "").lower().rstrip(".") not in _YOUTUBE_HOSTS:
        return False
    if parsed.path.rstrip("/") != "/watch":
        return False
    query = urllib.parse.parse_qs(parsed.query)
    return bool(query.get("v") and _VIDEO_ID.fullmatch(query["v"][0]))


def resolve_first_youtube_video(
    query: str,
    *,
    timeout: float = DEFAULT_LOOKUP_TIMEOUT_SECONDS,
    opener: Callable[..., Any] | None = None,
) -> YouTubeVideo:
    normalized = normalize_youtube_query(query)
    search_url = youtube_search_url(normalized)
    referenced_id = youtube_video_id_from_url(normalized)
    if referenced_id is not None:
        return YouTubeVideo(normalized, referenced_id, search_url, (referenced_id,))

    request = urllib.request.Request(
        search_url,
        headers={
            "Accept-Language": "en-US,en;q=0.9",
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0 Safari/537.36"
            ),
        },
    )
    open_request = opener or urllib.request.urlopen
    try:
        with open_request(request, timeout=timeout) as response:
            payload = response.read(MAX_RESPONSE_BYTES)
    except (OSError, TimeoutError, urllib.error.URLError) as exc:
        raise YouTubeLookupError("YouTube search could not be reached.") from exc

    text = payload.decode("utf-8", errors="replace")
    candidate_ids: list[str] = []
    for match in _VIDEO_RENDERER.finditer(text):
        video_id = match.group("video_id")
        if video_id not in candidate_ids:
            candidate_ids.append(video_id)
        if len(candidate_ids) >= MAX_CANDIDATE_VIDEOS:
            break
    if not candidate_ids:
        raise YouTubeLookupError("YouTube did not return a playable video result.")
    return YouTubeVideo(normalized, candidate_ids[0], search_url, tuple(candidate_ids))

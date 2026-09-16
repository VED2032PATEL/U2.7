from __future__ import annotations

import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from ultron27.brain import UltronBrain
from ultron27.executor import Executor
from ultron27.models import ToolCall
from ultron27.planner import DatasetPlanner, regex_plan
from ultron27.policy import decide
from ultron27.runtime import RuntimeSettings, UltronAssistant
from ultron27.tools import validate_tool_call
from ultron27.web_server import WebState, _youtube_player_directive
from ultron27.youtube import (
    MAX_RESPONSE_BYTES,
    YouTubeLookupError,
    YouTubeVideo,
    is_safe_youtube_watch_url,
    is_youtube_video_id,
    resolve_first_youtube_video,
    youtube_search_url,
    youtube_video_id_from_url,
    youtube_watch_url,
)


VIDEO_ID = "dQw4w9WgXcQ"


class _Response:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.read_limit: int | None = None

    def __enter__(self) -> "_Response":
        return self

    def __exit__(self, *_args: object) -> None:
        return None

    def read(self, limit: int) -> bytes:
        self.read_limit = limit
        return self.payload[:limit]


class YouTubeFeatureTest(unittest.TestCase):
    def test_play_and_search_youtube_use_distinct_typed_tools(self) -> None:
        cases = {
            "play Interstellar trailer on YouTube": ToolCall("play_youtube_video", {"query": "Interstellar trailer"}),
            "watch C++ pointers & references on YouTube.": ToolCall("play_youtube_video", {"query": "C++ pointers & references"}),
            "play Interstellar trailer on YouTube, please.": ToolCall("play_youtube_video", {"query": "Interstellar trailer"}),
            "open YouTube and play lofi hip hop radio": ToolCall("play_youtube_video", {"query": "lofi hip hop radio"}),
            "search YouTube for Python tutorials": ToolCall("open_website", {"site": "youtube", "query": "Python tutorials"}),
            "open YouTube": ToolCall("open_website", {"site": "youtube"}),
            "play blinding lights on Spotify": ToolCall("play_music", {"query": "blinding lights"}),
        }
        planner = DatasetPlanner.from_jsonl()
        for utterance, expected in cases.items():
            with self.subTest(utterance=utterance):
                self.assertEqual(planner.plan(utterance).tool_call, expected)

    def test_youtube_playback_tool_is_low_risk_and_rejects_extra_arguments(self) -> None:
        plan = regex_plan("play Python tutorial on YouTube")
        validation = validate_tool_call(plan.tool_call)

        self.assertTrue(validation.valid)
        self.assertEqual(decide(plan, validation).action, "allow")
        invalid = validate_tool_call(ToolCall("play_youtube_video", {"query": "Python", "url": "https://example.test"}))
        self.assertFalse(invalid.valid)

    def test_resolver_encodes_query_uses_bounded_timeout_and_first_video_renderer(self) -> None:
        response = _Response(
            b'ignored "videoId":"AAAAAAAAAAA" '
            b'"videoRenderer":{"videoId":"dQw4w9WgXcQ","title":{"runs":[{"text":"result"}]}} '
            b'"videoRenderer":{"videoId":"M7lc1UVf-VE","title":{"runs":[{"text":"fallback"}]}}'
        )
        observed: dict[str, object] = {}

        def opener(request: object, *, timeout: float) -> _Response:
            observed["url"] = getattr(request, "full_url")
            observed["timeout"] = timeout
            return response

        video = resolve_first_youtube_video("AC/DC live & loud + remaster", timeout=3.5, opener=opener)

        self.assertEqual(video.video_id, VIDEO_ID)
        self.assertEqual(observed["url"], "https://www.youtube.com/results?search_query=AC%2FDC+live+%26+loud+%2B+remaster")
        self.assertEqual(observed["timeout"], 3.5)
        self.assertEqual(response.read_limit, MAX_RESPONSE_BYTES)
        self.assertEqual(video.watch_url, f"https://www.youtube.com/watch?v={VIDEO_ID}&autoplay=1")
        self.assertEqual(video.candidate_ids, (VIDEO_ID, "M7lc1UVf-VE"))

    def test_resolver_accepts_direct_youtube_links_but_rejects_lookalikes(self) -> None:
        direct = resolve_first_youtube_video(f"https://youtu.be/{VIDEO_ID}")

        self.assertEqual(direct.video_id, VIDEO_ID)
        self.assertEqual(youtube_video_id_from_url(f"https://www.youtube.com/shorts/{VIDEO_ID}"), VIDEO_ID)
        self.assertIsNone(youtube_video_id_from_url(f"https://www.youtube.com.evil.test/watch?v={VIDEO_ID}"))
        self.assertFalse(is_safe_youtube_watch_url(f"https://example.test/watch?v={VIDEO_ID}"))
        self.assertTrue(is_safe_youtube_watch_url(youtube_watch_url(VIDEO_ID)))
        self.assertTrue(is_youtube_video_id(VIDEO_ID))
        self.assertFalse(is_youtube_video_id("../../not-safe"))

    def test_resolver_fails_closed_for_network_and_unrecognized_results(self) -> None:
        def offline(_request: object, *, timeout: float) -> _Response:
            raise urllib.error.URLError(f"offline after {timeout}")

        with self.assertRaises(YouTubeLookupError):
            resolve_first_youtube_video("offline video", opener=offline)
        with self.assertRaises(YouTubeLookupError):
            resolve_first_youtube_video("missing video", opener=lambda *_args, **_kwargs: _Response(b"no renderers"))

    def test_executor_dry_run_skips_network_and_external_launch(self) -> None:
        executor = Executor(dry_run=True)
        with (
            patch("ultron27.executor.resolve_first_youtube_video") as resolver,
            patch("ultron27.executor.subprocess.Popen") as process,
            patch("ultron27.executor.webbrowser.open") as browser,
        ):
            result = executor.execute(ToolCall("play_youtube_video", {"query": "  Python   tutorial  "}))

        self.assertEqual(result.status, "dry_run")
        self.assertEqual(result.data["query"], "Python tutorial")
        self.assertEqual(result.data["playback_target"], "ultron_mini_player")
        self.assertFalse(result.data["playback_requested"])
        self.assertEqual(result.data["search_url"], youtube_search_url("Python tutorial"))
        resolver.assert_not_called()
        process.assert_not_called()
        browser.assert_not_called()

    def test_executor_returns_internal_player_payload_without_os_launch(self) -> None:
        executor = Executor(dry_run=False)
        video = YouTubeVideo("Python tutorial", VIDEO_ID, youtube_search_url("Python tutorial"))
        with (
            patch("ultron27.executor.resolve_first_youtube_video", return_value=video) as resolver,
            patch("ultron27.executor.subprocess.Popen") as process,
            patch("ultron27.executor.webbrowser.open") as browser,
        ):
            result = executor.execute(ToolCall("play_youtube_video", {"query": "Python tutorial"}))

        self.assertEqual(result.status, "success")
        self.assertEqual(result.data["query"], "Python tutorial")
        self.assertEqual(result.data["video_id"], VIDEO_ID)
        self.assertEqual(result.data["candidate_video_ids"], [VIDEO_ID])
        self.assertEqual(result.data["playback_target"], "ultron_mini_player")
        self.assertTrue(result.data["playback_requested"])
        self.assertFalse(result.data["playback_verified"])
        self.assertNotIn("browser", result.data)
        self.assertNotIn("window_mode", result.data)
        resolver.assert_called_once_with("Python tutorial")
        process.assert_not_called()
        browser.assert_not_called()

    def test_executor_fails_closed_when_resolution_fails_or_query_is_not_text(self) -> None:
        executor = Executor(dry_run=False)
        with (
            patch("ultron27.executor.resolve_first_youtube_video", side_effect=YouTubeLookupError("no result")),
            patch("ultron27.executor.subprocess.Popen") as process,
            patch("ultron27.executor.webbrowser.open") as browser,
        ):
            missing = executor.execute(ToolCall("play_youtube_video", {"query": "missing"}))
            invalid = executor.execute(ToolCall("play_youtube_video", {"query": None}))

        self.assertEqual(missing.status, "error")
        self.assertEqual(invalid.status, "blocked")
        process.assert_not_called()
        browser.assert_not_called()

    def test_youtube_directive_accepts_only_successful_internal_player_results(self) -> None:
        valid = {
            "steps": [
                {
                    "tool_call": {"name": "play_youtube_video", "arguments": {"query": "Python"}},
                    "result": {
                        "status": "success",
                        "data": {
                            "query": "Python tutorial",
                            "video_id": VIDEO_ID,
                            "playback_target": "ultron_mini_player",
                        },
                    },
                }
            ]
        }
        self.assertEqual(
            _youtube_player_directive(valid),
            {
                "kind": "youtube_player",
                "action": "cue",
                "query": "Python tutorial",
                "video_id": VIDEO_ID,
                "video_ids": [VIDEO_ID],
                "autoplay": False,
            },
        )

        distinct_candidates = [f"videoid{i:04d}" for i in range(7)]
        candidate_task = {
            "steps": [
                {
                    "tool_call": valid["steps"][0]["tool_call"],
                    "result": {
                        "status": "success",
                        "data": {
                            **valid["steps"][0]["result"]["data"],
                            "candidate_video_ids": distinct_candidates,
                        },
                    },
                }
            ]
        }
        directive = _youtube_player_directive(candidate_task)
        self.assertIsNotNone(directive)
        self.assertEqual(directive["video_ids"][0], VIDEO_ID)
        self.assertEqual(len(directive["video_ids"]), 6)

        for mutation in (
            {"tool_call": {"name": "open_website"}, "result": valid["steps"][0]["result"]},
            {"tool_call": valid["steps"][0]["tool_call"], "result": {"status": "error", "data": valid["steps"][0]["result"]["data"]}},
            {
                "tool_call": valid["steps"][0]["tool_call"],
                "result": {"status": "success", "data": {**valid["steps"][0]["result"]["data"], "video_id": "../../unsafe"}},
            },
            {
                "tool_call": valid["steps"][0]["tool_call"],
                "result": {"status": "success", "data": {**valid["steps"][0]["result"]["data"], "playback_target": "external"}},
            },
        ):
            with self.subTest(mutation=mutation):
                self.assertIsNone(_youtube_player_directive({"steps": [mutation]}))

    @staticmethod
    def _state(*, dry_run: bool) -> WebState:
        settings = RuntimeSettings(
            dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
            audit_log=Path(".ultron/test-youtube-audit.jsonl"),
            workspace=Path("."),
            dry_run=dry_run,
            safe_roots=(Path("."),),
            app_aliases=None,
            screenshot_dir=Path(".ultron/screenshots"),
            planner_mode="rules",
            llm_model="unused",
            llm_endpoint="http://localhost:11434",
            llm_timeout_seconds=1.0,
            write_audit=False,
        )
        return WebState(UltronBrain(UltronAssistant(settings)))

    def test_webstate_success_emits_internal_player_directive_but_dry_run_does_not(self) -> None:
        video = YouTubeVideo("Interstellar trailer", VIDEO_ID, youtube_search_url("Interstellar trailer"))
        state = self._state(dry_run=False)
        with patch("ultron27.executor.resolve_first_youtube_video", return_value=video):
            payload = state.command("play Interstellar trailer on YouTube")

        self.assertEqual(
            payload["ui_directive"],
            {
                "kind": "youtube_player",
                "action": "cue",
                "query": "Interstellar trailer",
                "video_id": VIDEO_ID,
                "video_ids": [VIDEO_ID],
                "autoplay": False,
            },
        )
        self.assertEqual(payload["task"]["steps"][0]["result"]["data"]["playback_target"], "ultron_mini_player")

        dry_state = self._state(dry_run=True)
        dry_payload = dry_state.command("play Interstellar trailer on YouTube")
        self.assertNotIn("ui_directive", dry_payload)

    def test_voice_transcript_routes_youtube_playback_without_llm(self) -> None:
        state = self._state(dry_run=False)
        video = YouTubeVideo("Interstellar trailer", VIDEO_ID, youtube_search_url("Interstellar trailer"))
        with patch("ultron27.executor.resolve_first_youtube_video", return_value=video):
            payload = state.voice_transcribe({"transcript": "ULTRON play Interstellar trailer on you tube please", "confidence": 0.99})

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["transcript"]["text"], "play Interstellar trailer on YouTube please")
        self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "play_youtube_video")
        self.assertEqual(payload["task"]["steps"][0]["result"]["status"], "success")
        self.assertEqual(payload["ui_directive"]["kind"], "youtube_player")
        self.assertEqual(payload["ui_directive"]["video_id"], VIDEO_ID)
        self.assertEqual(payload["history"][0]["tool_selected"], "play_youtube_video")

    def test_frontend_contract_uses_internal_player_and_only_requested_controls(self) -> None:
        html = Path("web/index.html").read_text(encoding="utf-8")
        app = Path("web/app.js").read_text(encoding="utf-8")
        styles = Path("web/styles.css").read_text(encoding="utf-8")

        self.assertIn('id="youtubeWindow"', html)
        self.assertIn('id="youtubePlayerHost"', html)
        self.assertIn('id="youtubeBackButton"', html)
        self.assertIn('id="youtubePlayButton"', html)
        self.assertIn('id="youtubeForwardButton"', html)
        self.assertIn('content="strict-origin-when-cross-origin"', html)
        self.assertIn('directive.kind === "youtube_player"', app)
        self.assertIn("YOUTUBE_VIDEO_ID_PATTERN", app)
        self.assertIn('script.src = "https://www.youtube.com/iframe_api"', app)
        self.assertIn("origin: window.location.origin", app)
        self.assertIn('controls: "1"', app)
        self.assertNotIn('disablekb: "1"', app)
        self.assertIn("iframe.referrerPolicy = \"strict-origin-when-cross-origin\"", app)
        self.assertIn("youtubePlayerHost.replaceChildren(iframe)", app)
        self.assertIn("youtubePlayer.seekTo(target, true)", app)
        self.assertIn("tryNextYouTubeCandidate", app)
        self.assertIn('iframe.setAttribute("referrerpolicy", "strict-origin-when-cross-origin")', app)
        self.assertIn('iframe.setAttribute("allow", "autoplay; encrypted-media; picture-in-picture")', app)
        self.assertIn("pauseYouTubePlayer(\"Playback paused while the mini-player is minimized.\")", app)
        self.assertIn("destroyYouTubePlayer()", app)
        self.assertIn(".youtube-window", styles)
        self.assertIn("min-height: 200px", styles)


if __name__ == "__main__":
    unittest.main()

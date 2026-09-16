from __future__ import annotations

import io
import json
import os
import socket
import subprocess
import threading
import tempfile
import unittest
import urllib.parse
from contextlib import redirect_stdout
from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from ultron27.audit import append_audit_record, read_recent_audit_records
from ultron27.brain import MemoryStore, TaskState, UltronBrain
from ultron27.cli import main
from ultron27.console import format_assistant_response, run_console
from ultron27.config import UltronConfig, load_config
from ultron27.conversation import ConversationManager
from ultron27.diagnostics import build_diagnostics
from ultron27.dataset_quality import DatasetRow, analyze_dataset, build_safety_cases, is_underspecified
from ultron27.executor import Executor
from ultron27.internet import WebSearchResponse, WebSearchResult, filter_relevant_results
from ultron27.knowledge import KnowledgeBase
from ultron27.llm import GroqProvider, LLMPlanner, LLMPlannerError, parse_llm_tool_call
from ultron27.modeling import generate_model_scene, validate_scene_spec
from ultron27.models import RiskLevel, ToolCall, ToolResult
from ultron27.planner import DatasetPlanner, regex_plan
from ultron27.policy import decide
from ultron27.runtime import RuntimeSettings, UltronAssistant
from ultron27.spotify import SpotifyAuthConfig, SpotifyWebPlayer
from ultron27.skills import SkillRegistry, SkillSpec, validate_skill_input
from ultron27.tools import validate_tool_call
from ultron27.voice import (
    DeepgramSTT,
    DeepgramTTS,
    MockMicrophoneCapture,
    MockSTT,
    MockTTS,
    SoundDeviceMicrophoneCapture,
    TextPayloadSTT,
    VoiceProviderConfig,
    VoiceSession,
    analyze_audio_payload,
    build_voice_session,
    clean_transcript,
    strip_wake_greeting,
    strip_wake_word,
)
from ultron27.wake import DoubleClapWakeProvider, EnergyVADProvider, MockVADProvider, MockWakeWordProvider, WakeGateConfig
from ultron27.web_server import WebState, make_handler
from ultron27.weather import WeatherSnapshot, weather_code_description
from ultron27.windows_executor import (
    _ensure_spotify_window_foreground,
    _spotify_button_icon_state,
    _wait_for_whatsapp_ui,
    merge_windows_app_aliases,
    resolve_app_alias,
    resolve_app_target,
    resolve_whatsapp_recipient,
)
from scripts.config_wizard import generate_config
from scripts.launch_ultron import find_open_port


class PipelineTest(unittest.TestCase):
    def test_regex_volume_command_is_valid_and_allowed(self) -> None:
        plan = regex_plan("set volume to 40 percent")
        validation = validate_tool_call(plan.tool_call)
        decision = decide(plan, validation)

        self.assertEqual(plan.tool_call, ToolCall("set_system_volume", {"level": 40}))
        self.assertTrue(validation.valid)
        self.assertEqual(decision.action, "allow")

    def test_high_risk_delete_requires_confirmation(self) -> None:
        plan = regex_plan("delete project_report.txt")
        validation = validate_tool_call(plan.tool_call)
        decision = decide(plan, validation)

        self.assertTrue(validation.valid)
        self.assertEqual(decision.action, "confirm")

    def test_dataset_exact_match_uses_expected_tool(self) -> None:
        planner = DatasetPlanner.from_jsonl()
        plan = planner.plan("play lofi beats")

        self.assertEqual(plan.tool_call.name, "play_music")
        self.assertEqual(plan.tool_call.arguments, {"query": "lofi beats"})
        self.assertEqual(plan.source, "dataset_exact")

    def test_regex_web_and_spotify_commands_use_typed_tools(self) -> None:
        web = regex_plan("search the web for weather in Delhi")
        spotify = regex_plan("play blinding lights on spotify")
        generic_spotify = regex_plan("play songs through spotify")
        notepad_write = regex_plan("open notepad and write alien in it")

        self.assertEqual(web.tool_call, ToolCall("search_web", {"query": "weather in delhi"}))
        self.assertEqual(spotify.tool_call, ToolCall("play_music", {"query": "blinding lights"}))
        self.assertEqual(generic_spotify.tool_call, ToolCall("play_music", {"query": "songs"}))
        self.assertEqual(notepad_write.tool_call, ToolCall("write_text_in_application", {"app": "notepad", "text": "alien"}))

    def test_information_request_uses_web_search_instead_of_local_files(self) -> None:
        plan = regex_plan("find information about quantum computing")

        self.assertEqual(plan.tool_call, ToolCall("search_web", {"query": "quantum computing"}))

    def test_regex_whatsapp_command_preserves_message_and_requires_confirmation(self) -> None:
        plan = regex_plan("Open WhatsApp and text Mom saying I'll be home at 7, and send it")
        validation = validate_tool_call(plan.tool_call)
        decision = decide(plan, validation)

        self.assertEqual(
            plan.tool_call,
            ToolCall("send_whatsapp_message", {"recipient": "Mom", "message": "I'll be home at 7,"}),
        )
        self.assertTrue(validation.valid)
        self.assertEqual(decision.action, "confirm")

    def test_file_and_session_changes_remain_confirmation_gated(self) -> None:
        commands = (
            "close Notepad",
            "rename report.txt to final_report.txt",
            "move report.txt to Documents",
            "draft an email to alex@example.com about the report",
            "lock my computer",
        )
        for command in commands:
            with self.subTest(command=command):
                plan = regex_plan(command)
                self.assertEqual(decide(plan, validate_tool_call(plan.tool_call)).action, "confirm")

    def test_brain_preserves_periods_inside_file_names(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        renamed = state.command("rename report.txt to final_report.txt")
        moved = state.command("move report.txt to Documents")
        website = state.command("open github.com")

        self.assertEqual(renamed["task"]["status"], "waiting_for_confirmation")
        self.assertEqual(renamed["task"]["steps"][0]["tool_call"]["name"], "rename_file")
        self.assertEqual(moved["task"]["status"], "waiting_for_confirmation")
        self.assertEqual(moved["task"]["steps"][0]["tool_call"]["name"], "move_file")
        self.assertEqual(website["task"]["steps"][0]["tool_call"]["name"], "open_website")

    def test_regex_whatsapp_supports_message_first_phrasing(self) -> None:
        plan = regex_plan('send "The build is ready." to Project Lead on WhatsApp')

        self.assertEqual(
            plan.tool_call,
            ToolCall("send_whatsapp_message", {"recipient": "Project Lead", "message": "The build is ready."}),
        )

    def test_regex_whatsapp_supports_spoken_comma_phrasing(self) -> None:
        plan = regex_plan("WhatsApp, Em Hitansh, hi")

        self.assertEqual(
            plan.tool_call,
            ToolCall("send_whatsapp_message", {"recipient": "Em Hitansh", "message": "hi"}),
        )

    def test_incomplete_whatsapp_message_asks_for_clarification(self) -> None:
        plan = regex_plan("send a WhatsApp message")

        self.assertEqual(plan.tool_call.name, "ask_clarification")

    def test_jarvis_style_command_matrix_routes_to_typed_tools(self) -> None:
        cases = {
            "unmute the sound": ToolCall("mute_system_volume", {"mute": False}),
            "turn the volume up by 10 percent": ToolCall("adjust_system_volume", {"direction": "up", "delta": 10}),
            "lower the volume by 15 percent": ToolCall("adjust_system_volume", {"direction": "down", "delta": 15}),
            "make the sound 30 percent": ToolCall("set_system_volume", {"level": 30}),
            "increase brightness by 20 percent": ToolCall("adjust_screen_brightness", {"direction": "up", "delta": 20}),
            "dim the screen by 10 percent": ToolCall("adjust_screen_brightness", {"direction": "down", "delta": 10}),
            "pause the music": ToolCall("pause_media", {"action": "pause"}),
            "resume playback": ToolCall("pause_media", {"action": "play"}),
            "play the next song": ToolCall("next_media_track", {}),
            "go back to the previous track": ToolCall("previous_media_track", {}),
            "switch to Spotify": ToolCall("switch_application", {"app": "spotify"}),
            "close Notepad": ToolCall("close_application", {"app": "notepad"}),
            "open YouTube": ToolCall("open_website", {"site": "youtube"}),
            "open github.com": ToolCall("open_website", {"site": "github.com"}),
            "search YouTube for Python tutorials": ToolCall("open_website", {"site": "youtube", "query": "Python tutorials"}),
            "open YouTube and search for Python tutorials": ToolCall("open_website", {"site": "youtube", "query": "Python tutorials"}),
            "play a Python tutorial on YouTube": ToolCall("play_youtube_video", {"query": "a Python tutorial"}),
            "open Google and search for weather in Ahmedabad": ToolCall("open_website", {"site": "google", "query": "weather in Ahmedabad"}),
            "what time is it": ToolCall("get_system_status", {"category": "time"}),
            "what is today's date": ToolCall("get_system_status", {"category": "date"}),
            "how much battery is left": ToolCall("get_system_status", {"category": "battery"}),
            "show my system information": ToolCall("get_system_status", {"category": "system"}),
            "calculate 27 times 14": ToolCall("calculate", {"expression": "27 times 14"}),
            "what is 15 percent of 200": ToolCall("calculate", {"expression": "15 percent of 200"}),
            "find PDF files in Downloads": ToolCall("search_files", {"query": "*", "file_type": "pdf", "folder": "Downloads"}),
            "look for all PDF files inside Downloads": ToolCall("search_files", {"query": "*", "file_type": "pdf", "folder": "Downloads"}),
            "create a note called groceries with milk and eggs": ToolCall("create_note", {"title": "groceries", "content": "milk and eggs"}),
            "create a folder called invoices in Documents": ToolCall("create_folder", {"folder": "invoices", "parent": "Documents"}),
            "make a directory called receipts in Documents": ToolCall("create_folder", {"folder": "receipts", "parent": "Documents"}),
            "rename report.txt to final_report.txt": ToolCall("rename_file", {"old_name": "report.txt", "new_name": "final_report.txt"}),
            "move report.txt to Documents": ToolCall("move_file", {"file_name": "report.txt", "destination": "Documents"}),
            "lock my computer": ToolCall("lock_screen", {}),
            "draft an email to alex@example.com about the report": ToolCall("draft_email", {"recipient": "alex@example.com", "subject": "the report"}),
        }
        planner = DatasetPlanner.from_jsonl()

        for utterance, expected in cases.items():
            with self.subTest(utterance=utterance):
                self.assertEqual(planner.plan(utterance).tool_call, expected)

    def test_local_time_date_and_calculation_use_command_route(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        time_payload = state.command("what time is it")
        date_payload = state.command("what is today's date")
        calculation_payload = state.command("what is 15 percent of 200")
        file_payload = state.command("find file named project_report.txt")
        youtube_payload = state.command("search YouTube for Python tutorials")

        self.assertEqual(time_payload["route"], "command")
        self.assertEqual(time_payload["task"]["steps"][0]["tool_call"]["name"], "get_system_status")
        self.assertEqual(date_payload["route"], "command")
        self.assertEqual(calculation_payload["route"], "command")
        self.assertEqual(calculation_payload["task"]["steps"][0]["result"]["data"]["value"], 30)
        self.assertEqual(file_payload["route"], "command")
        self.assertEqual(file_payload["task"]["steps"][0]["tool_call"]["name"], "search_files")
        self.assertEqual(youtube_payload["route"], "command")
        self.assertEqual(youtube_payload["task"]["steps"][0]["tool_call"]["name"], "open_website")

    def test_assistant_reply_handles_conversation_without_blocking(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = state.command("hello ultron")

        self.assertEqual(payload["route"], "chat")
        self.assertEqual(payload["task"]["status"], "completed")
        self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "assistant_reply")
        self.assertIn("At your service", payload["subtitle"])

    def test_groq_chat_powers_casual_conversation_when_configured(self) -> None:
        settings = replace(
            _test_settings(),
            llm_provider="groq",
            llm_model="openai/gpt-oss-20b",
            llm_endpoint="https://api.groq.com/openai/v1",
        )
        state = WebState(UltronBrain(UltronAssistant(settings)))

        with patch("ultron27.conversation.GroqChatProvider.complete_chat", return_value="Hello, Ved. I am here and ready.") as chat_mock:
            payload = state.command("hi")

        self.assertEqual(payload["route"], "chat")
        self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "assistant_reply")
        self.assertEqual(payload["response"], "Hello, Ved. I am here and ready.")
        chat_mock.assert_called_once()

    def test_audibility_check_is_chat_not_unsupported_command(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = state.command("Am I audible or wrong?")

        self.assertEqual(payload["route"], "chat")
        self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "assistant_reply")
        self.assertIn("read your messages", payload["response"])

    def test_cortana_greeting_is_chat_not_unsupported_command(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = state.command("Hey, Cortana. Hello.")

        self.assertEqual(payload["route"], "chat")
        self.assertNotIn("No safe supported tool", payload["response"])

    def test_factual_question_uses_web_search_response(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))
        web = WebSearchResponse(
            "success",
            "who is ada lovelace",
            "I found this on the web for who is ada lovelace:\n1. Ada Lovelace - Mathematician",
            (WebSearchResult("Ada Lovelace", "https://example.test/ada", "Mathematician and early programmer."),),
        )

        with patch("ultron27.conversation.search_web", return_value=web) as search_mock:
            payload = state.command("Who is Ada Lovelace?")

        self.assertEqual(payload["route"], "web_search")
        self.assertIn("Ada Lovelace", payload["response"])
        self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "assistant_reply")
        self.assertEqual(payload["task"]["steps"][0]["result"]["data"]["web"]["results"][0]["url"], "https://example.test/ada")
        search_mock.assert_called_once_with("Ada Lovelace")

    def test_gather_information_routes_to_web_not_file_search(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))
        web = WebSearchResponse(
            "success",
            "quantum computing",
            "Quantum computing uses quantum-mechanical effects for computation.",
            (WebSearchResult("Quantum computing", "https://example.test/quantum", "A computing paradigm."),),
        )

        with patch("ultron27.conversation.search_web", return_value=web) as search_mock:
            payload = state.command("gather info on quantum computing")

        self.assertEqual(payload["route"], "web_search")
        self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "assistant_reply")
        self.assertNotEqual(payload["task"]["steps"][0]["tool_call"]["name"], "search_files")
        search_mock.assert_called_once_with("quantum computing")

    def test_gather_information_on_that_reuses_previous_web_topic(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        def fake_search(query: str) -> WebSearchResponse:
            return WebSearchResponse(
                "success",
                query,
                f"Information about {query}",
                (WebSearchResult(query, "https://example.test/topic", "Useful context."),),
            )

        with patch("ultron27.conversation.search_web", side_effect=fake_search) as search_mock:
            state.command("Who is Ada Lovelace?")
            follow_up = state.command("gather info on that")

        self.assertEqual(follow_up["route"], "web_search")
        self.assertEqual(search_mock.call_args_list[0].args[0], "Ada Lovelace")
        self.assertEqual(search_mock.call_args_list[1].args[0], "Ada Lovelace")

    def test_groq_research_synthesizes_sources_and_opens_research_window(self) -> None:
        settings = replace(
            _test_settings(),
            llm_provider="groq",
            llm_model="openai/gpt-oss-20b",
            llm_endpoint="https://api.groq.com/openai/v1",
        )
        state = WebState(UltronBrain(UltronAssistant(settings)))
        web = WebSearchResponse(
            "success",
            "dogs",
            "RAW SEARCH SNIPPET",
            (WebSearchResult("Dog", "https://example.test/dog", "Dogs have lived with humans for a long time."),),
        )

        with (
            patch("ultron27.conversation.search_web", return_value=web),
            patch(
                "ultron27.conversation.GroqChatProvider.complete_chat",
                return_value="Dogs are highly social domesticated mammals, sir. Their long relationship with people shaped many working and companion roles.",
            ) as chat_mock,
        ):
            payload = state.command("gather information about dogs")

        self.assertEqual(payload["route"], "web_search")
        self.assertNotIn("RAW SEARCH SNIPPET", payload["response"])
        self.assertEqual(payload["ui_directive"]["kind"], "research")
        self.assertTrue(payload["ui_directive"]["synthesized"])
        self.assertEqual(payload["ui_directive"]["results"][0]["url"], "https://example.test/dog")
        self.assertEqual(chat_mock.call_args.kwargs["max_tokens"], 720)

    def test_camera_command_opens_internal_camera_instead_of_windows_app(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = state.command("open camera and take a picture")

        self.assertEqual(payload["route"], "interface")
        self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "assistant_reply")
        self.assertEqual(payload["ui_directive"]["kind"], "camera")
        self.assertTrue(payload["ui_directive"]["auto_capture"])

    def test_hand_control_commands_return_interface_directives(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        enabled = state.command("enable hand gesture controls")
        desktop = state.command("control the laptop cursor using my hand")
        guide = state.command("show me the hand gesture guide")
        paused = state.command("pause hand mouse control")
        resumed = state.command("resume hand mouse control")
        disabled = state.command("turn off hand tracking")

        self.assertEqual(enabled["route"], "interface")
        self.assertEqual(enabled["ui_directive"], {"kind": "gestures", "action": "start"})
        self.assertEqual(desktop["ui_directive"], {"kind": "gestures", "action": "start", "mode": "desktop"})
        self.assertEqual(guide["ui_directive"], {"kind": "gestures", "action": "guide"})
        self.assertEqual(paused["ui_directive"], {"kind": "gestures", "action": "pause"})
        self.assertEqual(resumed["ui_directive"], {"kind": "gestures", "action": "resume"})
        self.assertEqual(disabled["ui_directive"], {"kind": "gestures", "action": "stop"})

    def test_camera_to_3d_command_routes_to_object_isolation(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = state.command("make a 3d model of what I am showing in the camera")

        self.assertEqual(payload["route"], "interface")
        self.assertEqual(payload["ui_directive"]["kind"], "modeler")
        self.assertEqual(payload["ui_directive"]["action"], "scan_object")
        self.assertTrue(payload["ui_directive"]["fallback_360"])
        self.assertIn("isolate", payload["response"].lower())

    def test_3d_prompt_scan_and_model_controls_return_distinct_directives(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        generated = state.command("make a 3d model of a cube")
        scanned = state.command("scan this bottle 360 degrees")
        enlarged = state.command("enlarge it")
        hidden = state.command("vanish it")

        self.assertEqual(generated["ui_directive"], {"kind": "modeler", "action": "generate", "description": "cube"})
        self.assertEqual(scanned["ui_directive"]["action"], "scan_360")
        self.assertEqual(scanned["ui_directive"]["target"], "bottle")
        self.assertEqual(scanned["ui_directive"]["required_views"], 12)
        self.assertEqual(enlarged["ui_directive"]["action"], "scale_up")
        self.assertEqual(hidden["ui_directive"]["action"], "hide")

    def test_local_3d_generator_builds_valid_procedural_scenes(self) -> None:
        cube = generate_model_scene("cube", _test_settings())
        bottle = generate_model_scene("water bottle", _test_settings())

        self.assertEqual(cube["status"], "success")
        self.assertEqual(cube["source"], "procedural")
        self.assertEqual(cube["scene"]["objects"][0]["shape"], "box")
        self.assertEqual(bottle["scene"]["name"], "bottle")
        self.assertEqual(len(bottle["scene"]["objects"]), 3)

    def test_3d_scene_validation_drops_unknown_parts_and_clamps_vectors(self) -> None:
        scene = validate_scene_spec(
            {
                "name": "Test / Model",
                "objects": [
                    {"shape": "script", "position": [0, 0, 0]},
                    {
                        "shape": "box",
                        "position": [12, -9, 0],
                        "rotation": [0, 0, 0],
                        "scale": [8, 0.001, 1],
                        "color": "not-a-color",
                    },
                ],
            }
        )

        self.assertEqual(scene["name"], "test  model")
        self.assertEqual(len(scene["objects"]), 1)
        self.assertEqual(scene["objects"][0]["position"], [6.0, -6.0, 0.0])
        self.assertEqual(scene["objects"][0]["scale"], [6.0, 0.05, 1.0])
        self.assertRegex(scene["objects"][0]["color"], r"^#[0-9a-f]{6}$")

    def test_unknown_3d_prompt_uses_validated_groq_primitive_json(self) -> None:
        settings = replace(_test_settings(), llm_provider="groq")
        generated = json.dumps(
            {
                "name": "desk lamp",
                "objects": [
                    {"shape": "cylinder", "position": [0, 0, 0], "rotation": [0, 0, 0], "scale": [1, 0.2, 1], "color": "#55e6a2"},
                    {"shape": "cone", "position": [0, 1, 0], "rotation": [0, 0, 0], "scale": [1, 1, 1], "color": "#67cce6"},
                ],
            }
        )
        with patch("ultron27.modeling.GroqChatProvider.complete_chat", return_value=generated) as chat:
            result = generate_model_scene("desk lamp", settings)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["source"], "groq")
        self.assertEqual(len(result["scene"]["objects"]), 2)
        self.assertEqual(chat.call_args.kwargs["max_tokens"], 900)

    def test_model_generation_http_endpoint_returns_scene(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            request = Request(
                f"http://127.0.0.1:{server.server_address[1]}/api/model/generate",
                data=json.dumps({"description": "cube"}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            payload = json.loads(urlopen(request, timeout=5).read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(payload["status"], "success")
        self.assertEqual(payload["scene"]["name"], "cube")

    def test_voice_path_preserves_gesture_and_modeler_directives(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        gesture = state.voice_transcribe({"transcript": "enable hand controls"})
        model = state.voice_transcribe({"transcript": "make a 3d model of this"})

        self.assertEqual(gesture["ui_directive"], {"kind": "gestures", "action": "start"})
        self.assertEqual(model["ui_directive"]["kind"], "modeler")
        self.assertTrue(model["continue_listening"])

    def test_open_browser_and_search_uses_internal_research_console(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))
        web = WebSearchResponse(
            "success",
            "solar flares",
            "Solar flares release energy from the Sun.",
            (WebSearchResult("Solar flare", "https://example.test/solar", "Solar activity."),),
        )

        with patch("ultron27.conversation.search_web", return_value=web) as search_mock:
            payload = state.command("open browser and search for solar flares")

        self.assertEqual(payload["route"], "web_search")
        self.assertEqual(payload["ui_directive"]["kind"], "research")
        search_mock.assert_called_once_with("solar flares")

    def test_web_research_topic_with_action_word_is_not_stolen_by_command_router(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))
        web = WebSearchResponse(
            "success",
            "why dogs became close companions to humans",
            "Dogs and humans developed a close relationship over time.",
            (WebSearchResult("Dog domestication", "https://example.test/dogs", "Long-term domestication."),),
        )

        with patch("ultron27.conversation.search_web", return_value=web) as search_mock:
            payload = state.research("why dogs became close companions to humans")

        self.assertEqual(payload["route"], "web_search")
        self.assertEqual(payload["ui_directive"]["kind"], "research")
        search_mock.assert_called_once_with("why dogs became close companions to humans")

    def test_camera_capture_saves_valid_png_to_screenshot_directory(self) -> None:
        tiny_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII="
        with tempfile.TemporaryDirectory() as tmp:
            state = WebState(UltronBrain(UltronAssistant(_workspace_settings(Path(tmp)))))

            payload = state.camera_capture({"image": tiny_png})

            self.assertEqual(payload["status"], "saved")
            self.assertTrue(Path(payload["path"]).is_file())
            self.assertEqual(Path(payload["path"]).parent, (Path(tmp) / ".ultron" / "screenshots").resolve())

    def test_startup_briefing_uses_time_and_current_location_weather(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())), assistant_location="Jabalpur")
        weather = WeatherSnapshot(
            location="Jabalpur",
            region="Madhya Pradesh",
            country="India",
            latitude=23.17,
            longitude=79.95,
            temperature_c=28.4,
            apparent_temperature_c=30.1,
            humidity_percent=64,
            wind_speed_kmh=9.2,
            weather_code=2,
            condition="partly cloudy",
            observed_at="2026-07-12T12:00",
        )

        with patch("ultron27.web_server.get_current_weather", return_value=weather) as weather_mock:
            payload = state.startup_briefing(force=True)

        self.assertEqual(payload["status"], "ok")
        self.assertIn("Jabalpur", payload["message"])
        self.assertIn("28 degrees Celsius", payload["message"])
        self.assertEqual(payload["weather"]["condition"], "partly cloudy")
        weather_mock.assert_called_once_with("Jabalpur")

    def test_weather_codes_have_human_descriptions(self) -> None:
        self.assertEqual(weather_code_description(0), "clear")
        self.assertEqual(weather_code_description(63), "rainy")
        self.assertEqual(weather_code_description(95), "stormy")

    def test_web_result_filter_removes_unrelated_name_collisions(self) -> None:
        results = [
            WebSearchResult("Dog", "https://example.test/dog", "The domesticated descendant of the wolf."),
            WebSearchResult("Dogs in warfare", "https://example.test/war", "Dogs have served alongside humans."),
            WebSearchResult("Dogstar (band)", "https://example.test/band", "An American alternative rock band."),
        ]

        filtered = filter_relevant_results("dogs", results)

        self.assertEqual([item.title for item in filtered], ["Dog", "Dogs in warfare"])

    def test_conversation_manager_learns_and_forgets_safe_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _workspace_settings(Path(tmp), dry_run=True, write_audit=False)
            state = WebState(UltronBrain(UltronAssistant(settings)))

            remembered = state.command("remember that I prefer concise responses")
            memory = state.memory_status()
            forgotten = state.memory_forget("concise")

            self.assertEqual(remembered["route"], "memory_remember")
            self.assertTrue(any("concise responses" in item["value"] for item in memory["memory"]))
            self.assertEqual(forgotten["removed"], 1)
            self.assertFalse(any("concise responses" in item.get("value", "") for item in forgotten["memory"]))

    def test_personal_favorite_statement_is_learned_without_tool_denial(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = WebState(UltronBrain(UltronAssistant(_workspace_settings(Path(tmp)))))

            remembered = state.command("my favorite song is Blinding Lights")
            recalled = state.command("what is my favorite song?")

            self.assertEqual(remembered["route"], "memory_remember")
            self.assertIn("favorite song is Blinding Lights", remembered["response"])
            self.assertNotIn("safe tool", remembered["response"].lower())
            self.assertEqual(recalled["route"], "memory_lookup")
            self.assertIn("Blinding Lights", recalled["response"])

    def test_favorite_song_reference_resolves_before_spotify_planning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = WebState(UltronBrain(UltronAssistant(_workspace_settings(Path(tmp)))))
            state.command("Blinding Lights is my favourite song")

            payload = state.command("play my favorite song")

            call = payload["task"]["steps"][0]["tool_call"]
            self.assertEqual(call["name"], "play_music")
            self.assertEqual(call["arguments"]["query"], "blinding lights")
            self.assertIn("memory_reference_resolved", payload["conversation"]["memory_events"])

    def test_unknown_personal_reference_admits_missing_memory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = WebState(UltronBrain(UltronAssistant(_workspace_settings(Path(tmp)))))

            payload = state.command("play my favorite song")

            self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "assistant_reply")
            self.assertIn("do not know your favorite song", payload["response"])
            self.assertNotIn("safe tool", payload["response"].lower())

    def test_hinglish_favorite_statement_and_family_alias_are_learned(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = WebState(UltronBrain(UltronAssistant(_workspace_settings(Path(tmp)))))

            song = state.command("mera favourite song Taki Taki hai")
            relation = state.command("Em Hitansh is my brother")

            memory = state.memory_status()["memory"]
            self.assertEqual(song["route"], "memory_remember")
            self.assertEqual(relation["route"], "memory_remember")
            self.assertTrue(any(item["key"] == "preference:favorite_song" and item["value"] == "Taki Taki" for item in memory))
            self.assertTrue(any(item["key"] == "relation:brother" and item["value"] == "Em Hitansh" for item in memory))

    def test_personal_statement_routes_to_conversation_instead_of_planner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            state = WebState(UltronBrain(UltronAssistant(_workspace_settings(Path(tmp)))))

            payload = state.command("I had a difficult day at college")

            self.assertEqual(payload["route"], "chat")
            self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "assistant_reply")

    def test_conversation_memory_off_stops_new_personalization(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            settings = _workspace_settings(Path(tmp), dry_run=True, write_audit=False)
            state = WebState(UltronBrain(UltronAssistant(settings)))

            off = state.command("turn memory off")
            remembered = state.command("remember that I prefer long reports")

            self.assertEqual(off["route"], "memory_toggle")
            self.assertFalse(remembered["memory_enabled"])
            self.assertIn("did not store", remembered["response"])
            self.assertFalse(any("long reports" in item.get("value", "") for item in state.memory_status()["memory"]))

    def test_conversation_high_risk_still_requires_confirmation(self) -> None:
        manager = ConversationManager(UltronBrain(UltronAssistant(_test_settings())))

        payload = manager.handle("delete project_report.txt")

        self.assertEqual(payload["route"], "command")
        self.assertTrue(payload["needs_confirmation"])
        self.assertEqual(payload["task"]["status"], "waiting_for_confirmation")

    def test_short_whatsapp_command_reaches_planner_and_confirmation_gate(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = state.command("WhatsApp Em Hitansh: Hi")

        self.assertEqual(payload["route"], "command")
        self.assertEqual(payload["task"]["status"], "waiting_for_confirmation")
        self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "send_whatsapp_message")

    def test_whatsapp_can_be_locally_configured_to_send_without_confirmation(self) -> None:
        settings = replace(_test_settings(), whatsapp_require_confirmation=False)

        payload = UltronAssistant(settings).handle("WhatsApp, Em Hitansh, hi")
        web_payload = WebState(UltronBrain(UltronAssistant(settings))).command("WhatsApp, Em Hitansh, hi")

        self.assertEqual(payload["policy"]["action"], "allow")
        self.assertEqual(payload["result"]["status"], "dry_run")
        self.assertFalse(payload["runtime"]["confirmed"])
        self.assertTrue(payload["runtime"]["auto_confirmed"])
        self.assertEqual(web_payload["route"], "command")
        self.assertEqual(web_payload["task"]["status"], "completed")
        self.assertNotIn("needs_confirmation", web_payload)

    def test_web_and_spotify_executor_use_safe_targets(self) -> None:
        executor = Executor(dry_run=False)

        with (
            patch("ultron27.executor.SpotifyWebPlayer.from_workspace", return_value=None),
            patch("webbrowser.open", return_value=True) as open_mock,
            patch("os.startfile") as startfile_mock,
            patch("ultron27.windows_executor._focus_spotify_window", return_value=123),
            patch("ultron27.windows_executor._force_spotify_search", return_value=True),
            patch("ultron27.windows_executor._click_spotify_result_play_button", return_value=True),
        ):
            web = executor.execute(ToolCall("search_web", {"query": "ultron project"}))
            spotify = executor.execute(ToolCall("play_music", {"query": "lofi beats"}))

        self.assertEqual(web.status, "success")
        self.assertEqual(spotify.status, "success")
        opened_urls = [call.args[0] for call in open_mock.call_args_list]
        self.assertTrue(any(url.startswith("https://www.google.com/search?") for url in opened_urls))
        startfile_mock.assert_called_once_with("spotify:search:lofi%20beats")

    def test_calculator_and_website_tools_execute_without_llm(self) -> None:
        executor = Executor(dry_run=False)

        calculation = executor.execute(ToolCall("calculate", {"expression": "15 percent of 200"}))
        unsafe = executor.execute(ToolCall("calculate", {"expression": "2 ** 100"}))
        with patch("webbrowser.open", return_value=True) as open_mock:
            website = executor.execute(ToolCall("open_website", {"site": "youtube", "query": "Python tutorials"}))

        self.assertEqual(calculation.status, "success")
        self.assertEqual(calculation.data["value"], 30)
        self.assertEqual(unsafe.status, "blocked")
        self.assertEqual(website.status, "success")
        self.assertTrue(open_mock.call_args.args[0].startswith("https://www.youtube.com/results?search_query=Python+tutorials"))

    def test_file_organization_tools_stay_inside_safe_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            documents = workspace / "Documents"
            second_root = workspace / "Second"
            documents.mkdir()
            second_root.mkdir()
            source = workspace / "report.txt"
            source.write_text("report", encoding="utf-8")
            (second_root / "other-report.txt").write_text("report", encoding="utf-8")
            executor = Executor(dry_run=False, workspace=workspace, safe_roots=(workspace, second_root))

            created = executor.execute(ToolCall("create_folder", {"folder": "invoices", "parent": "Documents"}))
            renamed = executor.execute(ToolCall("rename_file", {"old_name": "report.txt", "new_name": "final_report.txt"}))
            moved = executor.execute(ToolCall("move_file", {"file_name": "final_report.txt", "destination": "Documents"}))
            searched = executor.execute(ToolCall("search_files", {"query": "report", "file_type": "txt"}))

            self.assertEqual(created.status, "success")
            self.assertTrue((documents / "invoices").is_dir())
            self.assertEqual(renamed.status, "success")
            self.assertEqual(moved.status, "success")
            self.assertTrue((documents / "final_report.txt").is_file())
            self.assertEqual(searched.status, "success")
            self.assertEqual(len(searched.data["matches"]), 2)

    def test_windows_relative_controls_and_media_use_typed_adapters(self) -> None:
        executor = Executor(dry_run=False)

        class FakeVolume:
            scalar = 0.67
            mute = None

            def GetMasterVolumeLevelScalar(self) -> float:
                return self.scalar

            def SetMasterVolumeLevelScalar(self, value: float, _context: object) -> None:
                self.scalar = value

            def SetMute(self, value: int, _context: object) -> None:
                self.mute = value

        volume = FakeVolume()
        with (
            patch("ultron27.windows_executor._windows_endpoint_volume", return_value=volume),
            patch("screen_brightness_control.get_brightness", return_value=[37]),
            patch("screen_brightness_control.set_brightness") as set_brightness,
            patch("ultron27.windows_executor._tap_key") as tap_key,
        ):
            volume_result = executor.execute(ToolCall("adjust_system_volume", {"direction": "down", "delta": 15}))
            unmute_result = executor.execute(ToolCall("mute_system_volume", {"mute": False}))
            brightness_result = executor.execute(ToolCall("adjust_screen_brightness", {"direction": "up", "delta": 20}))
            media_result = executor.execute(ToolCall("next_media_track", {}))

        self.assertEqual(volume_result.changed["level"], 52)
        self.assertEqual(unmute_result.status, "success")
        self.assertEqual(volume.mute, 0)
        self.assertEqual(brightness_result.changed["level"], 57)
        set_brightness.assert_called_once_with(57, display=0)
        self.assertEqual(media_result.status, "success")
        tap_key.assert_called_once()

    def test_windows_uri_apps_and_window_controls_are_supported(self) -> None:
        executor = Executor(dry_run=False)

        class FakeUser32:
            @staticmethod
            def PostMessageW(hwnd: int, message: int, wparam: int, lparam: int) -> bool:
                return hwnd == 456 and message != 0 and wparam == 0 and lparam == 0

        with (
            patch("os.startfile") as startfile_mock,
            patch("ultron27.windows_executor._find_application_window", return_value=456),
            patch("ultron27.windows_executor._activate_window", return_value=True),
            patch("ultron27.windows_executor._user32", return_value=FakeUser32()),
            patch("ultron27.windows_executor.time.sleep"),
        ):
            opened = executor.execute(ToolCall("open_application", {"app": "settings"}))
            switched = executor.execute(ToolCall("switch_application", {"app": "notepad"}))
            closed = executor.execute(ToolCall("close_application", {"app": "notepad"}))

        self.assertEqual(opened.status, "success")
        startfile_mock.assert_called_once_with("ms-settings:")
        self.assertEqual(switched.status, "success")
        self.assertEqual(closed.status, "success")

    def test_spotify_executor_reports_error_when_play_button_is_not_verified(self) -> None:
        executor = Executor(dry_run=False)

        with (
            patch("ultron27.executor.SpotifyWebPlayer.from_workspace", return_value=None),
            patch("os.startfile"),
            patch("ultron27.windows_executor._focus_spotify_window", return_value=123),
            patch("ultron27.windows_executor._force_spotify_search", return_value=True),
            patch("ultron27.windows_executor._click_spotify_result_play_button", return_value=False),
        ):
            result = executor.execute(ToolCall("play_music", {"query": "blinding lights"}))

        self.assertEqual(result.status, "error")
        self.assertFalse(result.data["playback_started"])

    def test_spotify_executor_clicks_visible_result_play_button(self) -> None:
        executor = Executor(dry_run=False)

        with (
            patch("ultron27.executor.SpotifyWebPlayer.from_workspace", return_value=None),
            patch("os.startfile") as startfile_mock,
            patch("ultron27.windows_executor._focus_spotify_window", return_value=123),
            patch("ultron27.windows_executor._force_spotify_search", return_value=True) as search_mock,
            patch("ultron27.windows_executor._click_spotify_result_play_button", return_value=True) as click_play,
        ):
            result = executor.execute(ToolCall("play_music", {"query": "taki taki"}))

        self.assertEqual(result.status, "success")
        self.assertTrue(result.data["playback_started"])
        self.assertEqual(result.data["provider"], "spotify_desktop")
        startfile_mock.assert_called_once_with("spotify:search:taki%20taki")
        search_mock.assert_called_once_with("taki taki")
        click_play.assert_called_once_with(123)

    def test_spotify_executor_never_appends_play_to_search_query(self) -> None:
        executor = Executor(dry_run=False)

        with (
            patch("ultron27.executor.SpotifyWebPlayer.from_workspace", return_value=None),
            patch("os.startfile") as startfile_mock,
            patch("ultron27.windows_executor._focus_spotify_window", return_value=123),
            patch("ultron27.windows_executor._force_spotify_search", return_value=True),
            patch("ultron27.windows_executor._click_spotify_result_play_button", return_value=True),
        ):
            result = executor.execute(ToolCall("play_music", {"query": "blinding lights"}))

        self.assertEqual(result.status, "success")
        startfile_mock.assert_called_once_with("spotify:search:blinding%20lights")

    def test_spotify_button_state_distinguishes_play_and_pause_icons(self) -> None:
        class FakeImage:
            size = (41, 41)

            def __init__(self, dark: set[tuple[int, int]]) -> None:
                self.dark = dark

            def load(self) -> "FakeImage":
                return self

            def __getitem__(self, point: tuple[int, int]) -> tuple[int, int, int]:
                return (20, 20, 20) if point in self.dark else (30, 215, 96)

        play = {(x, y) for x in range(13, 28) for y in range(10 + abs(x - 13), 31 - abs(x - 13))}
        pause = {(x, y) for x in (*range(12, 17), *range(25, 30)) for y in range(9, 32)}

        self.assertEqual(_spotify_button_icon_state(FakeImage(play)), "play")
        self.assertEqual(_spotify_button_icon_state(FakeImage(pause)), "pause")

    def test_spotify_foreground_fallback_activates_window_before_play_click(self) -> None:
        class FakeUser32:
            def __init__(self) -> None:
                self.foreground = iter((111, 111, 222))

            def GetForegroundWindow(self) -> int:
                return next(self.foreground)

            def ShowWindow(self, hwnd: int, state: int) -> None:
                return None

            def SetForegroundWindow(self, hwnd: int) -> None:
                return None

        with (
            patch("ultron27.windows_executor._user32", return_value=FakeUser32()),
            patch("ultron27.windows_executor._window_rect", return_value=(100, 10, 900, 700)),
            patch("ultron27.windows_executor._click_screen_point") as click_mock,
            patch("ultron27.windows_executor.time.sleep"),
        ):
            activated = _ensure_spotify_window_foreground(222)

        self.assertTrue(activated)
        click_mock.assert_called_once_with(500, 16)

    def test_spotify_web_player_searches_track_and_starts_playback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            token_path = Path(tmp) / "spotify_token.json"
            token_path.write_text(json.dumps({"access_token": "token", "expires_at": 9999999999}), encoding="utf-8")
            player = SpotifyWebPlayer(SpotifyAuthConfig(client_id="client", token_path=token_path))

            search = {"tracks": {"items": [{"name": "Taki Taki", "uri": "spotify:track:abc", "artists": [{"name": "DJ Snake"}]}]}}
            devices = {"devices": [{"id": "device-1", "is_active": True}]}
            statuses: list[tuple[str, str]] = []

            def fake_json(url: str, token: str) -> dict[str, object]:
                if "/search?" in url:
                    return search
                if url.endswith("/me/player/devices"):
                    return devices
                return {}

            def fake_status(url: str, token: str, *, method: str, body: bytes) -> int:
                statuses.append((url, body.decode("utf-8")))
                return 204

            with patch.object(player, "_api_json", side_effect=fake_json), patch.object(player, "_api_status", side_effect=fake_status):
                result = player.play("taki taki")

        self.assertEqual(result.status, "success")
        self.assertEqual(result.data["provider"], "spotify_web_api")
        self.assertTrue(any(url.endswith("/me/player/play?device_id=device-1") for url, _body in statuses))
        self.assertTrue(any('"spotify:track:abc"' in body for _url, body in statuses))

    def test_spotify_web_player_reports_missing_connect_device(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            token_path = Path(tmp) / "spotify_token.json"
            token_path.write_text(json.dumps({"access_token": "token", "expires_at": 9999999999}), encoding="utf-8")
            player = SpotifyWebPlayer(SpotifyAuthConfig(client_id="client", token_path=token_path))
            search = {"tracks": {"items": [{"name": "Taki Taki", "uri": "spotify:track:abc", "artists": []}]}}

            def fake_json(url: str, token: str) -> dict[str, object]:
                return search if "/search?" in url else {"devices": []}

            with patch.object(player, "_api_json", side_effect=fake_json):
                result = player.play("taki taki")

        self.assertEqual(result.status, "device_unavailable")
        self.assertIn("no controllable Spotify Connect device", result.message)

    def test_spotify_player_reuses_client_id_saved_with_local_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            token_path = workspace / ".ultron" / "spotify_token.json"
            token_path.parent.mkdir(parents=True)
            token_path.write_text(
                json.dumps({"client_id": "saved-client", "redirect_uri": "http://127.0.0.1:8766/callback"}),
                encoding="utf-8",
            )

            with patch("ultron27.spotify.get_secret", return_value=""):
                player = SpotifyWebPlayer.from_workspace(workspace)

        self.assertIsNotNone(player)
        self.assertEqual(player.config.client_id, "saved-client")

    def test_whatsapp_contact_resolution_requires_exact_international_number(self) -> None:
        mapped = resolve_whatsapp_recipient("Mom", {"mom": "+91 98765 43210"})
        direct = resolve_whatsapp_recipient("+1 (555) 123-4567", {})
        local_only = resolve_whatsapp_recipient("9876543210", {})

        self.assertEqual(mapped, ("919876543210", "configured_contact"))
        self.assertEqual(direct, ("15551234567", "direct_number"))
        self.assertEqual(local_only, ("", ""))

    def test_whatsapp_executor_opens_exact_chat_and_presses_send_once(self) -> None:
        executor = Executor(dry_run=False, whatsapp_contacts={"mom": "+919876543210"})

        class FakeUser32:
            @staticmethod
            def GetForegroundWindow() -> int:
                return 456

        with (
            patch("os.startfile") as startfile_mock,
            patch("ultron27.windows_executor._focus_whatsapp_window", return_value=456),
            patch("ultron27.windows_executor._user32", return_value=FakeUser32()),
            patch("ultron27.windows_executor._send_key_sequence") as send_keys,
            patch("ultron27.windows_executor.time.sleep"),
        ):
            result = executor.execute(
                ToolCall("send_whatsapp_message", {"recipient": "Mom", "message": "I'll be home at 7."})
            )

        self.assertEqual(result.status, "success")
        self.assertTrue(result.data["send_submitted"])
        self.assertFalse(result.data["delivery_verified"])
        uri = startfile_mock.call_args.args[0]
        self.assertTrue(uri.startswith("whatsapp://send?"))
        self.assertIn("phone=919876543210", uri)
        self.assertIn("text=I%27ll%20be%20home%20at%207.", uri)
        send_keys.assert_called_once_with(("enter",))

    def test_whatsapp_executor_routes_unmapped_name_to_exact_desktop_search(self) -> None:
        executor = Executor(dry_run=False, whatsapp_contacts={})
        expected = ToolResult(
            "success",
            "Sent WhatsApp message to Em Hitansh.",
            data={"contact_verified": True, "send_submitted": True},
        )

        with patch.object(executor.windows, "_send_whatsapp_named_contact", return_value=expected) as named_contact:
            result = executor.execute(ToolCall("send_whatsapp_message", {"recipient": "Em Hitansh", "message": "Hi"}))

        self.assertEqual(result, expected)
        named_contact.assert_called_once_with("Em Hitansh", "Hi")

    def test_whatsapp_ui_wait_retries_until_search_is_ready(self) -> None:
        window = object()
        search = object()

        class FakeDesktop:
            def __init__(self, *, backend: str):
                self.backend = backend

            def window(self, *, handle: int) -> object:
                self.handle = handle
                return window

        with (
            patch("ultron27.windows_executor._focus_whatsapp_window", return_value=777),
            patch("ultron27.windows_executor._find_whatsapp_search_control", side_effect=[None, search]),
            patch("ultron27.windows_executor.time.sleep"),
        ):
            ready_window, ready_search = _wait_for_whatsapp_ui(FakeDesktop, 456, timeout=1.0)

        self.assertIs(ready_window, window)
        self.assertIs(ready_search, search)

    def test_whatsapp_executor_rejects_local_number_without_country_code(self) -> None:
        executor = Executor(dry_run=False, whatsapp_contacts={})

        with patch.object(executor.windows, "_send_whatsapp_named_contact") as named_contact:
            result = executor.execute(ToolCall("send_whatsapp_message", {"recipient": "9876543210", "message": "Hi"}))

        self.assertEqual(result.status, "blocked")
        self.assertIn("country code", result.message)
        named_contact.assert_not_called()

    def test_write_text_in_application_uses_approved_app_and_paste(self) -> None:
        executor = Executor(dry_run=False, app_aliases={"notepad": "notepad.exe"})

        with (
            patch("subprocess.Popen") as popen,
            patch("ultron27.windows_executor._write_clipboard_windows") as write_clipboard,
            patch("ultron27.windows_executor._focus_window_for_automation", return_value=456),
            patch("ultron27.windows_executor._send_key_sequence") as send_keys,
        ):
            popen.return_value.pid = 1234
            result = executor.execute(ToolCall("write_text_in_application", {"app": "notepad", "text": "alien"}))

        self.assertEqual(result.status, "success")
        self.assertEqual(result.changed["text_length"], 5)
        write_clipboard.assert_called_once_with("alien")
        send_keys.assert_called_once_with(("ctrl+v",))

    def test_write_text_in_application_falls_back_to_title_focus(self) -> None:
        executor = Executor(dry_run=False, app_aliases={"notepad": "notepad.exe"})

        with (
            patch("subprocess.Popen") as popen,
            patch("ultron27.windows_executor._write_clipboard_windows"),
            patch("ultron27.windows_executor._focus_window_for_automation", side_effect=[None, 789]) as focus,
            patch("ultron27.windows_executor._send_key_sequence"),
        ):
            popen.return_value.pid = 1234
            result = executor.execute(ToolCall("write_text_in_application", {"app": "notepad", "text": "alien"}))

        self.assertEqual(result.status, "success")
        self.assertEqual(focus.call_args_list[0].kwargs["process_pid"], 1234)
        self.assertNotIn("process_pid", focus.call_args_list[1].kwargs)

    def test_planner_prefers_numeric_slot_extraction_over_fuzzy_match(self) -> None:
        planner = DatasetPlanner.from_jsonl()
        plan = planner.plan("set volume to 40 percent")

        self.assertEqual(plan.tool_call, ToolCall("set_system_volume", {"level": 40}))
        self.assertEqual(plan.source, "regex")

    def test_validation_rejects_bad_volume(self) -> None:
        validation = validate_tool_call(ToolCall("set_system_volume", {"level": 120}))

        self.assertFalse(validation.valid)
        self.assertTrue(any("between 0 and 100" in error for error in validation.errors))

    def test_dry_run_executor_does_not_mutate(self) -> None:
        result = Executor(dry_run=True).execute(ToolCall("set_system_volume", {"level": 25}))

        self.assertEqual(result.status, "dry_run")
        self.assertIn("25%", result.message)

    def test_config_file_and_environment_override_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "ultron.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "dataset_path": "custom_dataset.jsonl",
                        "audit_log": "logs/audit.jsonl",
                        "dry_run": False,
                        "workspace": "workspace",
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(
                config_path,
                environ={"ULTRON_DRY_RUN": "true", "ULTRON_AUDIT_LOG": "override.jsonl"},
                base_dir=root,
            )

            self.assertEqual(config.dataset_path, root / "custom_dataset.jsonl")
            self.assertEqual(config.audit_log, root / "override.jsonl")
            self.assertTrue(config.dry_run)
            self.assertEqual(config.workspace, root / "workspace")

    def test_whatsapp_settings_load_from_config_and_environment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "ultron.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "whatsapp_contacts": {"mom": "+919000000000"},
                        "whatsapp_require_confirmation": False,
                    }
                ),
                encoding="utf-8",
            )

            from_file = load_config(config_path, environ={}, base_dir=root)
            from_env = load_config(
                config_path,
                environ={
                    "ULTRON_WHATSAPP_CONTACTS": '{"project lead":"+15551234567"}',
                    "ULTRON_WHATSAPP_REQUIRE_CONFIRMATION": "true",
                },
                base_dir=root,
            )

        self.assertEqual(from_file.whatsapp_contacts, {"mom": "+919000000000"})
        self.assertFalse(from_file.whatsapp_require_confirmation)
        self.assertEqual(from_env.whatsapp_contacts, {"project lead": "+15551234567"})
        self.assertTrue(from_env.whatsapp_require_confirmation)

    def test_audit_record_includes_stable_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            append_audit_record({"utterance": "open notepad"}, audit_path)

            record = json.loads(audit_path.read_text(encoding="utf-8"))

            self.assertEqual(record["schema_version"], 1)
            self.assertIn("record_id", record)
            self.assertIn("timestamp_utc", record)
            self.assertEqual(record["utterance"], "open notepad")

    def test_cli_returns_structured_dry_run_response(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            main(["set volume to 40 percent", "--dry-run", "--no-audit"])

        payload = json.loads(output.getvalue())

        self.assertEqual(payload["tool_call"], {"name": "set_system_volume", "arguments": {"level": 40}})
        self.assertEqual(payload["policy"]["action"], "allow")
        self.assertEqual(payload["result"]["status"], "dry_run")
        self.assertTrue(payload["runtime"]["dry_run"])

    def test_cli_confirmed_delete_stays_non_destructive(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            main(["delete project_report.txt", "--yes", "--dry-run", "--no-audit"])

        payload = json.loads(output.getvalue())

        self.assertEqual(payload["policy"]["action"], "allow")
        self.assertEqual(payload["tool_call"]["name"], "delete_file")
        self.assertEqual(payload["result"]["status"], "dry_run")
        self.assertIn("Would delete file", payload["result"]["message"])

    def test_execute_confirmed_delete_is_not_implemented(self) -> None:
        result = Executor(dry_run=False).execute(ToolCall("delete_file", {"file_name": "project_report.txt"}))

        self.assertEqual(result.status, "not_implemented")
        self.assertIn("intentionally not implemented", result.message)

    def test_phase2_create_note_writes_inside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            result = Executor(dry_run=False, workspace=workspace).execute(
                ToolCall("create_note", {"title": "phase two", "content": "real low-risk write"})
            )

            note_path = workspace / "notes" / "phase_two.md"

            self.assertEqual(result.status, "success")
            self.assertTrue(note_path.exists())
            self.assertEqual(note_path.read_text(encoding="utf-8").strip(), "real low-risk write")

    def test_phase2_search_files_respects_safe_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            allowed = workspace / "allowed"
            blocked = workspace / "blocked"
            allowed.mkdir()
            blocked.mkdir()
            (allowed / "resume.txt").write_text("ok", encoding="utf-8")
            (blocked / "resume.txt").write_text("no", encoding="utf-8")

            result = Executor(dry_run=False, workspace=workspace, safe_roots=(allowed,)).execute(
                ToolCall("search_files", {"query": "resume", "file_type": "txt"})
            )

            self.assertEqual(result.status, "success")
            self.assertEqual(result.data["matches"], [str((allowed / "resume.txt").resolve())])

    def test_phase2_reminder_and_timer_are_saved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            executor = Executor(dry_run=False, workspace=workspace)

            with patch("ultron27.executor._start_windows_timer_notification", return_value=4321):
                reminder = executor.execute(ToolCall("set_reminder", {"task": "check email", "time": "7 pm"}))
                timer = executor.execute(ToolCall("start_timer", {"duration": "15 minutes"}))

            self.assertEqual(reminder.status, "success")
            self.assertEqual(timer.status, "success")
            self.assertTrue((workspace / ".ultron" / "reminders.jsonl").exists())
            self.assertTrue((workspace / ".ultron" / "timers.jsonl").exists())

    def test_phase2_planner_handles_timer_and_screenshot(self) -> None:
        timer = regex_plan("start timer for 15 minutes")
        screenshot = regex_plan("take a screenshot")

        self.assertEqual(timer.tool_call, ToolCall("start_timer", {"duration": "15 minutes"}))
        self.assertEqual(screenshot.tool_call, ToolCall("take_screenshot", {}))

    def test_phase3_dataset_quality_finds_conflicts_and_safety_cases(self) -> None:
        rows = [
            DatasetRow(
                id="1",
                utterance="find resume documents",
                intent="search_files",
                tool_name="search_files",
                tool_arguments={"query": "resume", "file_type": "pdf", "folder": "Downloads"},
                risk_level="low",
                requires_confirmation=False,
                expected_result="Search results",
                source="test",
                language="en",
                domain="laptop_assistant",
            ),
            DatasetRow(
                id="2",
                utterance="find resume documents",
                intent="search_files",
                tool_name="search_files",
                tool_arguments={"query": "resume", "file_type": "docx", "folder": "Documents"},
                risk_level="low",
                requires_confirmation=False,
                expected_result="Search results",
                source="test",
                language="en",
                domain="laptop_assistant",
            ),
            DatasetRow(
                id="3",
                utterance="delete resume.pdf",
                intent="delete_file",
                tool_name="delete_file",
                tool_arguments={"file_name": "resume.pdf"},
                risk_level="high",
                requires_confirmation=True,
                expected_result="Confirmation required",
                source="test",
                language="en",
                domain="laptop_assistant",
            ),
        ]

        report = analyze_dataset(rows)
        safety_cases = build_safety_cases(rows)

        self.assertEqual(report["conflicting_duplicate_groups"], 1)
        self.assertEqual(report["safety_examples"], 1)
        self.assertEqual(safety_cases[0]["expected_policy_action"], "confirm")

    def test_phase3_underspecified_search_detection(self) -> None:
        row = DatasetRow(
            id="1",
            utterance="look for assignment documents",
            intent="search_files",
            tool_name="search_files",
            tool_arguments={"query": "assignment", "file_type": "png", "folder": "Videos"},
            risk_level="low",
            requires_confirmation=False,
            expected_result="Search results",
            source="test",
            language="en",
            domain="laptop_assistant",
        )

        self.assertTrue(is_underspecified(row))

    def test_phase4_llm_json_tool_call_parser(self) -> None:
        call, intent, confidence = parse_llm_tool_call(
            '{"intent":"set_volume","tool_name":"set_system_volume","tool_arguments":{"level":35},"confidence":0.91}'
        )

        self.assertEqual(call, ToolCall("set_system_volume", {"level": 35}))
        self.assertEqual(intent, "set_volume")
        self.assertEqual(confidence, 0.91)

    def test_phase4_llm_planner_validates_tool_schema(self) -> None:
        class FakeProvider:
            def complete(self, prompt: str, timeout: float) -> str:
                return '{"intent":"set_volume","tool_name":"set_system_volume","tool_arguments":{"level":150},"confidence":1}'

        planner = LLMPlanner(FakeProvider())

        with self.assertRaises(LLMPlannerError):
            planner.plan("set volume very high")

    def test_phase4_llm_planner_produces_safe_plan(self) -> None:
        class FakeProvider:
            def complete(self, prompt: str, timeout: float) -> str:
                return '{"intent":"open_app","tool_name":"open_application","tool_arguments":{"app":"notepad"},"confidence":0.8}'

        plan = LLMPlanner(FakeProvider()).plan("launch the basic text editor")

        self.assertEqual(plan.tool_call, ToolCall("open_application", {"app": "notepad"}))
        self.assertEqual(plan.source, "llm")
        self.assertEqual(plan.risk_level.value, "low")

    def test_phase15_regex_handles_flexible_open_app_phrasing(self) -> None:
        phrases = ["launch notepad", "bring up notepad", "start the notes app", "launch the basic text editor"]

        plans = [regex_plan(phrase) for phrase in phrases]

        self.assertTrue(all(plan.tool_call == ToolCall("open_application", {"app": "notepad"}) for plan in plans))
        self.assertTrue(all(plan.source == "regex" for plan in plans))

    def test_phase15_llm_low_confidence_asks_clarification(self) -> None:
        class FakeProvider:
            def complete(self, prompt: str, timeout: float) -> str:
                return '{"intent":"open_app","tool_name":"open_application","tool_arguments":{"app":"notepad"},"confidence":0.2}'

        plan = LLMPlanner(FakeProvider()).plan("maybe notes maybe not")

        self.assertEqual(plan.tool_call.name, "ask_clarification")
        self.assertEqual(plan.intent, "clarify_intent")
        self.assertEqual(plan.risk_level.value, "none")
        self.assertNotIn("I heard", plan.tool_call.arguments["question"])

    def test_phase15_llm_explicit_clarification_payload_is_supported(self) -> None:
        call, intent, confidence = parse_llm_tool_call(
            '{"intent":"clarify_intent","tool_name":"ask_clarification","tool_arguments":{"question":"What text should I write in Notepad?"},"confidence":0.72,"needs_clarification":true,"clarification_question":"What text should I write in Notepad?"}'
        )

        self.assertEqual(call, ToolCall("ask_clarification", {"question": "What text should I write in Notepad?"}))
        self.assertEqual(intent, "clarify_intent")
        self.assertEqual(confidence, 0.72)

    def test_phase15_llm_parser_strips_thinking_blocks(self) -> None:
        call, intent, confidence = parse_llm_tool_call(
            '<think>I should not be visible.</think>{"intent":"open_app","tool_name":"open_application","tool_arguments":{"app":"notepad"},"confidence":0.87}'
        )

        self.assertEqual(call, ToolCall("open_application", {"app": "notepad"}))
        self.assertEqual(intent, "open_app")
        self.assertEqual(confidence, 0.87)

    def test_phase15_mock_llm_maps_flexible_music_phrase(self) -> None:
        class FakeProvider:
            def complete(self, prompt: str, timeout: float) -> str:
                self.prompt = prompt
                return '{"intent":"play_music","tool_name":"play_music","tool_arguments":{"query":"lofi music"},"confidence":0.78}'

        provider = FakeProvider()
        plan = LLMPlanner(provider).plan("put on some lofi music")

        self.assertEqual(plan.tool_call, ToolCall("play_music", {"query": "lofi music"}))
        self.assertIn("put on some lofi music", provider.prompt)

    def test_phase15_hybrid_llm_unavailable_falls_back_safely(self) -> None:
        settings = RuntimeSettings(
            dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
            audit_log=Path(".ultron/test-audit.jsonl"),
            workspace=Path("."),
            dry_run=True,
            safe_roots=(Path("."),),
            app_aliases=None,
            screenshot_dir=Path(".ultron/screenshots"),
            planner_mode="hybrid",
            llm_model="unused",
            llm_endpoint="http://localhost:11434",
            llm_timeout_seconds=1.0,
            write_audit=False,
        )
        assistant = UltronAssistant(settings)

        with patch("ultron27.runtime.make_ollama_router", side_effect=LLMPlannerError("Ollama unavailable")):
            payload = assistant.handle("do a completely unknown assistant task")

        self.assertEqual(payload["tool_call"]["name"], "unsupported_request")
        self.assertTrue(payload["runtime"]["llm"]["attempted"])
        self.assertIn("Ollama unavailable", payload["runtime"]["llm"]["error"])

    def test_hybrid_groq_retries_unknown_open_app_alias(self) -> None:
        class FakeRouter:
            def route(self, utterance: str):
                self.utterance = utterance
                return regex_plan("open notepad")

        settings = RuntimeSettings(
            dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
            audit_log=Path(".ultron/test-audit.jsonl"),
            workspace=Path("."),
            dry_run=True,
            safe_roots=(Path("."),),
            app_aliases=None,
            screenshot_dir=Path(".ultron/screenshots"),
            planner_mode="hybrid",
            llm_model="unused",
            llm_endpoint="https://api.groq.com/openai/v1",
            llm_timeout_seconds=1.0,
            llm_provider="groq",
            write_audit=False,
        )
        router = FakeRouter()

        with patch("ultron27.runtime.make_groq_router", return_value=router) as mocked:
            payload = UltronAssistant(settings).handle("launch the simple writing program")

        self.assertTrue(mocked.called)
        self.assertEqual(router.utterance, "launch the simple writing program")
        self.assertEqual(payload["tool_call"], {"name": "open_application", "arguments": {"app": "notepad"}})
        self.assertTrue(payload["runtime"]["llm"]["attempted"])

    def test_phase4_config_accepts_llm_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "ultron.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "planner_mode": "hybrid",
                        "llm_provider": "ollama",
                        "llm_model": "qwen-test",
                        "llm_endpoint": "http://localhost:11434",
                        "llm_timeout_seconds": 3,
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(config_path, environ={}, base_dir=root)

            self.assertEqual(config.planner_mode, "hybrid")
            self.assertEqual(config.llm_model, "qwen-test")
            self.assertEqual(config.llm_endpoint, "http://localhost:11434")
            self.assertEqual(config.llm_timeout_seconds, 3.0)

    def test_groq_provider_parses_openai_compatible_response(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "choices": [
                            {
                                "message": {
                                    "content": '{"intent":"open_app","tool_name":"open_application","tool_arguments":{"app":"notepad"},"confidence":0.92}'
                                }
                            }
                        ]
                    }
                ).encode("utf-8")

        with patch.dict(os.environ, {"GROQ_API_KEY": "test-key"}), patch("urllib.request.urlopen", return_value=FakeResponse()) as mocked:
            content = GroqProvider(endpoint="https://api.groq.com/openai/v1", model="test-model").complete("open notepad", 2)

        self.assertIn('"tool_name":"open_application"', content)
        request = mocked.call_args.args[0]
        self.assertEqual(request.full_url, "https://api.groq.com/openai/v1/chat/completions")
        self.assertEqual(request.get_header("Authorization"), "Bearer test-key")

    def test_config_accepts_groq_and_deepgram_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "ultron.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "planner_mode": "hybrid",
                        "llm_provider": "groq",
                        "llm_model": "openai/gpt-oss-20b",
                        "llm_endpoint": "https://api.groq.com/openai/v1",
                        "voice_stt_provider": "deepgram",
                        "voice_stt_model": "nova-3",
                        "voice_stt_language": "multi",
                        "voice_stt_keyterms": ["ULTRON", "Em Hitansh"],
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(config_path, environ={}, base_dir=root)

            self.assertEqual(config.llm_provider, "groq")
            self.assertEqual(config.llm_endpoint, "https://api.groq.com/openai/v1")
            self.assertEqual(config.voice_stt_provider, "deepgram")
            self.assertEqual(config.voice_stt_model, "nova-3")
            self.assertEqual(config.voice_stt_language, "multi")
            self.assertEqual(config.voice_stt_keyterms, ("ULTRON", "Em Hitansh"))

    def test_phase5_runtime_reuses_pipeline(self) -> None:
        settings = RuntimeSettings(
            dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
            audit_log=Path(".ultron/test-audit.jsonl"),
            workspace=Path("."),
            dry_run=True,
            safe_roots=(Path("."),),
            app_aliases=None,
            screenshot_dir=Path(".ultron/screenshots"),
            planner_mode="rules",
            llm_model="unused",
            llm_endpoint="http://localhost:11434",
            llm_timeout_seconds=1.0,
            write_audit=False,
        )

        payload = UltronAssistant(settings).handle("set volume to 40 percent")

        self.assertEqual(payload["tool_call"], {"name": "set_system_volume", "arguments": {"level": 40}})
        self.assertEqual(payload["policy"]["action"], "allow")
        self.assertEqual(payload["result"]["status"], "dry_run")

    def test_phase5_text_response_is_human_readable(self) -> None:
        payload = {
            "utterance": "set volume to 40 percent",
            "source": "regex",
            "confidence": 0.76,
            "tool_call": {"name": "set_system_volume", "arguments": {"level": 40}},
            "policy": {"action": "allow", "risk_level": "low"},
            "result": {"status": "dry_run", "message": "Would set volume to 40%"},
        }

        response = format_assistant_response(payload)

        self.assertIn("Tool: set_system_volume", response)
        self.assertIn("Policy: allow", response)
        self.assertIn("Result: dry_run", response)

    def test_phase5_console_accepts_help_json_and_exit(self) -> None:
        class FakeAssistant:
            def handle(self, utterance: str, *, confirmed: bool = False) -> dict:
                return {
                    "utterance": utterance,
                    "source": "regex",
                    "confidence": 0.76,
                    "tool_call": {"name": "set_system_volume", "arguments": {"level": 40}},
                    "policy": {"action": "allow", "risk_level": "low"},
                    "result": {"status": "dry_run", "message": "Would set volume to 40%"},
                    "runtime": {"confirmed": confirmed},
                }

        output = io.StringIO()
        run_console(FakeAssistant(), input_stream=io.StringIO("/help\n/json set volume to 40 percent\n/exit\n"), output_stream=output)

        text = output.getvalue()

        self.assertIn("Commands:", text)
        self.assertIn('"tool_call"', text)
        self.assertIn("Session ended.", text)

    def test_phase6_brain_decomposes_note_goal(self) -> None:
        settings = RuntimeSettings(
            dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
            audit_log=Path(".ultron/test-audit.jsonl"),
            workspace=Path("."),
            dry_run=True,
            safe_roots=(Path("."),),
            app_aliases=None,
            screenshot_dir=Path(".ultron/screenshots"),
            planner_mode="rules",
            llm_model="unused",
            llm_endpoint="http://localhost:11434",
            llm_timeout_seconds=1.0,
            write_audit=False,
        )

        task = UltronBrain(UltronAssistant(settings)).plan(
            "Create a note called project ideas and add that I should test voice mode next."
        )

        self.assertEqual(task.classification, "multi_step")
        self.assertEqual(len(task.steps), 2)
        self.assertEqual(task.steps[0].tool_call["name"], "create_note")
        self.assertEqual(task.steps[1].tool_call["name"], "append_to_note")

    def test_phase6_brain_executes_safe_multistep_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            settings = RuntimeSettings(
                dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
                audit_log=workspace / ".ultron" / "audit.jsonl",
                workspace=workspace,
                dry_run=False,
                safe_roots=(workspace,),
                app_aliases=None,
                screenshot_dir=workspace / ".ultron" / "screenshots",
                planner_mode="rules",
                llm_model="unused",
                llm_endpoint="http://localhost:11434",
                llm_timeout_seconds=1.0,
                write_audit=False,
            )

            task = UltronBrain(UltronAssistant(settings), memory_path=workspace / ".ultron" / "memory.json").execute(
                "Create a note called project ideas and add that I should test voice mode next."
            )

            self.assertEqual(task.status, TaskState.COMPLETED)
            note = workspace / "notes" / "project_ideas.md"
            self.assertTrue(note.exists())
            self.assertEqual(note.read_text(encoding="utf-8").strip(), "I should test voice mode next")

    def test_phase6_brain_high_risk_waits_for_confirmation(self) -> None:
        settings = RuntimeSettings(
            dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
            audit_log=Path(".ultron/test-audit.jsonl"),
            workspace=Path("."),
            dry_run=True,
            safe_roots=(Path("."),),
            app_aliases=None,
            screenshot_dir=Path(".ultron/screenshots"),
            planner_mode="rules",
            llm_model="unused",
            llm_endpoint="http://localhost:11434",
            llm_timeout_seconds=1.0,
            write_audit=False,
        )

        task = UltronBrain(UltronAssistant(settings)).execute("delete project_report.txt")

        self.assertEqual(task.status, TaskState.WAITING_FOR_CONFIRMATION)
        self.assertEqual(task.steps[0].result["status"], "confirmation_required")

    def test_phase6_memory_write_read_and_forget(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            memory = MemoryStore(Path(tmp) / "memory.json")

            stored = memory.remember("preferred_editor", "notepad", kind="preference")
            rejected = memory.remember("api_key", "secret value", kind="secret")

            self.assertTrue(stored)
            self.assertFalse(rejected)
            self.assertEqual(memory.list()[0]["value"], "notepad")
            self.assertEqual(memory.forget("editor"), 1)
            self.assertEqual(memory.list(), [])

    def test_phase6_brain_marks_failed_tool_result(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            settings = RuntimeSettings(
                dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
                audit_log=workspace / ".ultron" / "audit.jsonl",
                workspace=workspace,
                dry_run=False,
                safe_roots=(workspace,),
                app_aliases=None,
                screenshot_dir=workspace / ".ultron" / "screenshots",
                planner_mode="rules",
                llm_model="unused",
                llm_endpoint="http://localhost:11434",
                llm_timeout_seconds=1.0,
                write_audit=False,
            )

            with patch(
                "ultron27.windows_executor.WindowsAutomationAdapter.set_system_volume",
                return_value=ToolResult("error", "Simulated audio device failure."),
            ):
                task = UltronBrain(UltronAssistant(settings), memory_path=workspace / ".ultron" / "memory.json").execute(
                    "set volume to 40 percent"
                )

            self.assertEqual(task.status, TaskState.FAILED)
            self.assertEqual(task.steps[0].result["status"], "error")

    def test_phase6_brain_writes_task_audit_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            audit_path = workspace / ".ultron" / "audit.jsonl"
            settings = RuntimeSettings(
                dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
                audit_log=audit_path,
                workspace=workspace,
                dry_run=True,
                safe_roots=(workspace,),
                app_aliases=None,
                screenshot_dir=workspace / ".ultron" / "screenshots",
                planner_mode="rules",
                llm_model="unused",
                llm_endpoint="http://localhost:11434",
                llm_timeout_seconds=1.0,
                write_audit=True,
            )

            UltronBrain(UltronAssistant(settings), memory_path=workspace / ".ultron" / "memory.json").execute(
                "create note project ideas"
            )

            records = [json.loads(line) for line in audit_path.read_text(encoding="utf-8").splitlines()]

            self.assertTrue(any(record.get("record_type") == "brain_task" for record in records))

    def test_phase6_cli_plan_command_outputs_task_plan(self) -> None:
        output = io.StringIO()
        with redirect_stdout(output):
            main(["/plan create a note called ideas and add that voice mode is next", "--text", "--no-audit"])

        text = output.getvalue()

        self.assertIn("Status: pending", text)
        self.assertIn("Tool: create_note", text)
        self.assertIn("Tool: append_to_note", text)

    def test_phase7_web_state_processes_command(self) -> None:
        settings = RuntimeSettings(
            dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
            audit_log=Path(".ultron/test-audit.jsonl"),
            workspace=Path("."),
            dry_run=True,
            safe_roots=(Path("."),),
            app_aliases=None,
            screenshot_dir=Path(".ultron/screenshots"),
            planner_mode="rules",
            llm_model="unused",
            llm_endpoint="http://localhost:11434",
            llm_timeout_seconds=1.0,
            write_audit=False,
        )

        state = WebState(UltronBrain(UltronAssistant(settings)))
        payload = state.command("create note visual interface")

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["visual_state"], "speaking")
        self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "create_note")

    def test_phase7_subtitle_toggle_updates_state(self) -> None:
        settings = RuntimeSettings(
            dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
            audit_log=Path(".ultron/test-audit.jsonl"),
            workspace=Path("."),
            dry_run=True,
            safe_roots=(Path("."),),
            app_aliases=None,
            screenshot_dir=Path(".ultron/screenshots"),
            planner_mode="rules",
            llm_model="unused",
            llm_endpoint="http://localhost:11434",
            llm_timeout_seconds=1.0,
            write_audit=False,
        )

        state = WebState(UltronBrain(UltronAssistant(settings)))
        payload = state.toggle_subtitles(False)

        self.assertFalse(payload["subtitles_enabled"])
        self.assertFalse(state.subtitles_enabled)

    def test_phase7_static_ui_uses_local_three_module(self) -> None:
        app = Path("web/app.js").read_text(encoding="utf-8")
        html = Path("web/index.html").read_text(encoding="utf-8")

        self.assertIn("./vendor/three.module.min.js", app)
        self.assertIn("ultron-scene", html)
        self.assertIn("subtitleToggle", html)

    def test_command_center_ui_keeps_local_assets_and_control_hooks(self) -> None:
        app = Path("web/app.js").read_text(encoding="utf-8")
        html = Path("web/index.html").read_text(encoding="utf-8")
        styles = Path("web/styles.css").read_text(encoding="utf-8")
        core = Path("web/ultron-core.js").read_text(encoding="utf-8")

        self.assertTrue(Path("web/vendor/lucide.min.js").is_file())
        self.assertIn('id="operationsDrawer"', html)
        self.assertIn('data-drawer-tab="activity"', html)
        self.assertIn('data-drawer-tab="voice"', html)
        self.assertIn('data-drawer-tab="system"', html)
        self.assertIn('id="coreMicButton"', html)
        self.assertIn('id="commandInput"', html)
        self.assertIn('id="cameraWindow"', html)
        self.assertIn('id="researchWindow"', html)
        self.assertIn('id="modelWindow"', html)
        self.assertIn('id="gestureToggle"', html)
        self.assertIn('id="handGuideModal"', html)
        self.assertIn('data-gesture-mode="desktop"', html)
        self.assertIn('id="gestureSensitivitySlider"', html)
        self.assertIn('id="gestureOverlay"', html)
        self.assertIn('id="objectOverlay"', html)
        self.assertIn('id="objectScanMeter"', html)
        self.assertIn('id="modelScaleSlider"', html)
        self.assertIn("selectDrawerTab", app)
        self.assertIn("updateCoreLayout", app)
        self.assertIn("startBargeInMonitor", app)
        self.assertIn("echoCancellation: true", app)
        self.assertIn("navigator.mediaDevices.getUserMedia", app)
        self.assertIn("createHandGestureController", app)
        self.assertIn("createDesktopGestureInterpreter", app)
        self.assertIn("window.pywebview.api.hand_input", app)
        self.assertIn("setNativeHandControl", app)
        self.assertIn("createPhotoReliefModeler", app)
        self.assertIn("createObjectScanner", app)
        self.assertIn("start360ObjectScan", app)
        self.assertIn("beginGestureGrab", app)
        self.assertIn(".operations-drawer", styles)
        self.assertIn(".app-window", styles)
        self.assertIn(".gesture-cursor", styles)
        self.assertIn(".model-stage", styles)
        self.assertIn("HandLandmarker", Path("web/hand-gestures.js").read_text(encoding="utf-8"))
        hand_mouse = Path("web/hand-mouse.js").read_text(encoding="utf-8")
        self.assertIn('"three_finger:down": "minimize_all"', hand_mouse)
        self.assertIn('"four_finger:right": "desktop_right"', hand_mouse)
        self.assertIn("release_all", hand_mouse)
        self.assertIn(".hand-guide-modal", styles)
        self.assertIn("PlaneGeometry", Path("web/photo-modeler.js").read_text(encoding="utf-8"))
        self.assertIn("multiViewScanGeometry", Path("web/photo-modeler.js").read_text(encoding="utf-8"))
        self.assertIn("exportOBJ", Path("web/photo-modeler.js").read_text(encoding="utf-8"))
        self.assertIn("ObjectDetector", Path("web/object-scanner.js").read_text(encoding="utf-8"))
        self.assertIn("body.details-collapsed .detail-panel", styles)
        self.assertIn("makeNeuralLattice", core)
        self.assertIn("makeOrbitSystem", core)
        self.assertIn("THREE.InstancedMesh", core)
        self.assertIn("STATE_COLORS", core)

    def test_opening_sequence_stages_core_and_interface_reveal(self) -> None:
        app = Path("web/app.js").read_text(encoding="utf-8")
        html = Path("web/index.html").read_text(encoding="utf-8")
        styles = Path("web/styles.css").read_text(encoding="utf-8")
        core = Path("web/ultron-core.js").read_text(encoding="utf-8")

        self.assertIn('id="startupSequence"', html)
        self.assertIn("data-startup-module", html)
        self.assertIn("runOpeningSequence", app)
        self.assertIn("await openingSequencePromise", app)
        self.assertIn("startBoot()", core)
        self.assertIn("setBootProgress(progress)", core)
        self.assertIn("body.app-booting", styles)
        self.assertIn("@keyframes boot-drawer-in", styles)
        self.assertIn("@media (prefers-reduced-motion: reduce)", styles)

    def test_phase7_api_status_and_subtitle_toggle(self) -> None:
        settings = RuntimeSettings(
            dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
            audit_log=Path(".ultron/test-audit.jsonl"),
            workspace=Path("."),
            dry_run=True,
            safe_roots=(Path("."),),
            app_aliases=None,
            screenshot_dir=Path(".ultron/screenshots"),
            planner_mode="rules",
            llm_model="unused",
            llm_endpoint="http://localhost:11434",
            llm_timeout_seconds=1.0,
            write_audit=False,
        )
        state = WebState(UltronBrain(UltronAssistant(settings)))
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            status = json.loads(urlopen(base + "/api/status", timeout=5).read().decode("utf-8"))
            request = Request(
                base + "/api/subtitles/toggle",
                data=json.dumps({"enabled": False}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            toggled = json.loads(urlopen(request, timeout=5).read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(status["status"], "ok")
        self.assertFalse(toggled["subtitles_enabled"])

    def test_phase8_voice_transcript_executes_command(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = state.voice_transcribe({"transcript": "ULTRON, create note voice demo"})

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["transcript"]["text"], "create note voice demo")
        self.assertEqual(payload["visual_state"], "speaking")
        self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "create_note")
        self.assertEqual(payload["history"][0]["tool_selected"], "create_note")

    def test_phase8_high_risk_voice_command_requires_confirmation(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = state.voice_transcribe({"transcript": "ULTRON, delete project_report.txt"})

        self.assertTrue(payload["needs_confirmation"])
        self.assertEqual(payload["task"]["status"], "waiting_for_confirmation")
        self.assertEqual(payload["voice"]["pending_confirmation_goal"], "delete project_report.txt")
        self.assertIn("yes confirm", payload["spoken_response"])

        confirmed = state.voice_transcribe({"transcript": "yes confirm"})

        self.assertTrue(confirmed["confirmed"])
        self.assertNotEqual(confirmed["task"]["status"], "waiting_for_confirmation")

    def test_phase8_tts_response_generated(self) -> None:
        tts = MockTTS()
        state = WebState(UltronBrain(UltronAssistant(_test_settings())), voice=VoiceSession(tts=tts))

        payload = state.speak({"text": "Done. I created the note demo."})

        self.assertEqual(tts.spoken, ["Done. I created the note demo."])
        self.assertEqual(payload["speech"]["status"], "spoken")
        self.assertTrue(payload["voice"]["speaking"])

    def test_phase8_mute_disables_speaking(self) -> None:
        tts = MockTTS()
        state = WebState(UltronBrain(UltronAssistant(_test_settings())), voice=VoiceSession(tts=tts))
        state.voice.set_muted(True)

        payload = state.speak({"text": "This should not be spoken."})

        self.assertEqual(tts.spoken, [])
        self.assertEqual(payload["status"], "muted")
        self.assertFalse(payload["voice"]["speaking"])

    def test_phase8_voice_subtitles_update_and_toggle_still_works(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = state.voice_transcribe({"transcript": "create note subtitles"})
        toggled = state.toggle_subtitles(False)

        self.assertNotIn("You said:", payload["last_subtitle"])
        self.assertNotIn("Understood:", payload["last_subtitle"])
        self.assertNotIn("ULTRON:", payload["last_subtitle"])
        self.assertIn("note", payload["last_subtitle"].lower())
        self.assertFalse(toggled["subtitles_enabled"])

    def test_phase8_empty_voice_input_does_not_execute(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = state.voice_transcribe({"transcript": "   "})

        self.assertEqual(payload["status"], "empty")
        self.assertEqual(payload["visual_state"], "listening")
        self.assertEqual(payload["last_task"], None)
        self.assertEqual(payload["history"], [])

    def test_voice_low_confidence_transcript_asks_for_clarification(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = state.voice_transcribe({"transcript": "delete project report", "confidence": 0.2})

        self.assertEqual(payload["status"], "clarification_required")
        self.assertEqual(payload["last_task"], None)
        self.assertNotIn("I heard", payload["spoken_response"])
        self.assertIn("not fully sure", payload["spoken_response"])
        self.assertEqual(payload["history"][0]["action_result"], "clarification_required")

    def test_phase8_voice_api_endpoints(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            started = json.loads(
                urlopen(
                    Request(
                        base + "/api/voice/start",
                        data=json.dumps({"push_to_talk": True}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    ),
                    timeout=5,
                )
                .read()
                .decode("utf-8")
            )
            transcribed = json.loads(
                urlopen(
                    Request(
                        base + "/api/voice/transcribe",
                        data=json.dumps({"transcript": "ULTRON, create note api voice"}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    ),
                    timeout=5,
                )
                .read()
                .decode("utf-8")
            )
            status = json.loads(urlopen(base + "/api/voice/status", timeout=5).read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(started["visual_state"], "listening")
        self.assertEqual(transcribed["task"]["steps"][0]["tool_call"]["name"], "create_note")
        self.assertEqual(status["status"], "ok")

    def test_voice_session_defaults_to_continuous_listening(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = state.voice_status()

        self.assertFalse(payload["voice"]["push_to_talk"])

    def test_blocked_command_summary_is_actionable(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = state.command("do something impossible and unsafe")

        self.assertEqual(payload["task"]["status"], "blocked")
        self.assertIn("I do not have a safe tool", payload["subtitle"])
        self.assertIn("create a note", payload["subtitle"])

    def test_phase9_config_accepts_voice_provider_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "ultron.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "voice_stt_provider": "faster_whisper",
                        "voice_tts_provider": "piper",
                        "voice_tts_model": "aura-2-orion-en",
                        "voice_stt_model_path": "models/whisper",
                        "voice_tts_model_path": "models/piper.onnx",
                        "voice_tts_voice_path": "models/piper.json",
                        "voice_device": "cpu",
                        "voice_identity": "ULTRON-local",
                        "voice_preference": "Microsoft David",
                        "voice_rate": 0.86,
                        "voice_pitch": 0.7,
                        "voice_volume": 0.8,
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(
                config_path,
                environ={
                    "ULTRON_TTS_PROVIDER": "pyttsx3",
                    "ULTRON_VOICE_PREFERENCE": "Microsoft George",
                    "ULTRON_VOICE_RATE": "1.05",
                },
                base_dir=root,
            )

            self.assertEqual(config.voice_stt_provider, "faster_whisper")
            self.assertEqual(config.voice_tts_provider, "pyttsx3")
            self.assertEqual(config.voice_tts_model, "aura-2-orion-en")
            self.assertEqual(config.voice_stt_model_path, root / "models" / "whisper")
            self.assertEqual(config.voice_tts_model_path, root / "models" / "piper.onnx")
            self.assertEqual(config.voice_tts_voice_path, root / "models" / "piper.json")
            self.assertEqual(config.voice_identity, "ULTRON-local")
            self.assertEqual(config.voice_preference, "Microsoft George")
            self.assertEqual(config.voice_rate, 1.05)

    def test_deepgram_stt_parses_prerecorded_audio_response(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "results": {
                            "channels": [
                                {
                                    "alternatives": [
                                        {"transcript": "open notepad", "confidence": 0.91}
                                    ]
                                }
                            ]
                        }
                    }
                ).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "sample.wav"
            audio_path.write_bytes(b"RIFF....WAVEfmt ")

            with patch.dict(os.environ, {"DEEPGRAM_API_KEY": "test-key"}), patch("urllib.request.urlopen", return_value=FakeResponse()) as mocked:
                result = DeepgramSTT(model_name="nova-3").transcribe({"audio_path": str(audio_path)})

        self.assertEqual(result.text, "open notepad")
        self.assertEqual(result.provider, "deepgram")
        self.assertAlmostEqual(result.confidence, 0.91)
        request = mocked.call_args.args[0]
        self.assertIn("https://api.deepgram.com/v1/listen?model=nova-3", request.full_url)
        self.assertIn("language=multi", request.full_url)
        self.assertIn("smart_format=true", request.full_url)
        self.assertEqual(request.get_header("Authorization"), "Token test-key")

    def test_deepgram_tts_returns_one_time_progressive_audio_stream(self) -> None:
        class FakeResponse:
            headers = {"Content-Type": "audio/mpeg"}

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return b"ID3-neural-audio"

        provider = DeepgramTTS(model_name="aura-2-orion-en", rate=1.03, api_key="test-key")
        with patch("ultron27.voice.urllib.request.urlopen") as unopened:
            payload = provider.speak("At your service, sir.")
        unopened.assert_not_called()

        with patch("ultron27.voice.urllib.request.urlopen", return_value=FakeResponse()) as mocked:
            with provider.open_audio_stream(payload["stream_id"]) as response:
                audio = response.read()

        request = mocked.call_args.args[0]
        query = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
        self.assertEqual(payload["status"], "audio_stream")
        self.assertEqual(payload["provider"], "deepgram")
        self.assertEqual(payload["model"], "aura-2-orion-en")
        self.assertEqual(audio, b"ID3-neural-audio")
        self.assertNotIn("audio_base64", payload)
        self.assertEqual(query["model"], ["aura-2-orion-en"])
        self.assertEqual(query["speed"], ["1.03"])
        self.assertEqual(request.get_header("Authorization"), "Token test-key")
        with self.assertRaises(KeyError):
            provider.open_audio_stream(payload["stream_id"])

    def test_deepgram_tts_http_route_streams_audio_without_exposing_key(self) -> None:
        class FakeResponse:
            headers = {"Content-Type": "audio/mpeg"}

            def __init__(self) -> None:
                self.chunks = [b"ID3-", b"progressive-audio", b""]

            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self, _size: int = -1) -> bytes:
                return self.chunks.pop(0)

            def read1(self, size: int = -1) -> bytes:
                return self.read(size)

        tts = DeepgramTTS(model_name="aura-2-orion-en", rate=1.03, api_key="private-test-key")
        state = WebState(
            UltronBrain(UltronAssistant(_test_settings())),
            voice=VoiceSession(
                tts=tts,
                configured_tts=tts,
                provider_config=VoiceProviderConfig(tts_provider="deepgram", tts_model="aura-2-orion-en"),
            ),
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            speak_request = Request(
                base + "/api/speak",
                data=json.dumps({"text": "Streaming voice test."}).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            payload = json.loads(urlopen(speak_request, timeout=5).read().decode("utf-8"))
            with patch("ultron27.voice.urllib.request.urlopen", return_value=FakeResponse()) as upstream:
                audio = urlopen(base + payload["speech"]["stream_url"], timeout=5).read()
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(payload["speech"]["status"], "audio_stream")
        self.assertNotIn("private-test-key", json.dumps(payload))
        self.assertEqual(audio, b"ID3-progressive-audio")
        self.assertEqual(upstream.call_args.args[0].get_header("Authorization"), "Token private-test-key")

    def test_web_client_plays_progressive_neural_audio_stream(self) -> None:
        app = Path("web/app.js").read_text(encoding="utf-8")

        self.assertIn('payload.speech.status === "audio_stream"', app)
        self.assertIn('let source = String(speech.stream_url || "")', app)
        self.assertIn('const audio = new Audio(source)', app)

    def test_deepgram_multilingual_keyterms_restore_contact_name(self) -> None:
        class FakeResponse:
            def __enter__(self) -> "FakeResponse":
                return self

            def __exit__(self, *_args: object) -> None:
                return None

            def read(self) -> bytes:
                return json.dumps(
                    {
                        "results": {
                            "channels": [
                                {
                                    "alternatives": [
                                        {"transcript": "Whats app M Hitansh saying hi", "confidence": 0.88}
                                    ]
                                }
                            ]
                        }
                    }
                ).encode("utf-8")

        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "sample.wav"
            audio_path.write_bytes(b"RIFF....WAVEfmt ")
            provider = DeepgramSTT(
                model_name="nova-3",
                language="multi",
                keyterms=("WhatsApp", "Em Hitansh"),
                api_key="test-key",
            )

            with patch("urllib.request.urlopen", return_value=FakeResponse()) as mocked:
                result = provider.transcribe({"audio_path": str(audio_path)})

        self.assertEqual(result.text, "WhatsApp Em Hitansh saying hi")
        request = mocked.call_args.args[0]
        parsed = urllib.parse.parse_qs(urllib.parse.urlparse(request.full_url).query)
        self.assertEqual(parsed["language"], ["multi"])
        self.assertEqual(parsed["keyterm"], ["WhatsApp", "Em Hitansh"])

    def test_deepgram_stt_reports_missing_key_as_unavailable(self) -> None:
        with patch("ultron27.voice.get_secret", return_value=""):
            health = DeepgramSTT(model_name="nova-3").health()

        self.assertFalse(health.available)
        self.assertEqual(health.fallback_to, "browser")

    def test_phase9_missing_local_voice_models_fall_back_gracefully(self) -> None:
        class Config:
            voice_stt_provider = "faster_whisper"
            voice_tts_provider = "piper"
            voice_stt_model_path = None
            voice_tts_model_path = None
            voice_tts_voice_path = None
            voice_device = "cpu"
            voice_identity = "ULTRON"
            voice_rate = 0.92
            voice_pitch = 0.72
            voice_volume = 0.95

        session = build_voice_session(Config())
        providers = session.providers_status()

        self.assertEqual(providers["configured"]["stt"], "faster_whisper")
        self.assertEqual(providers["configured"]["tts"], "piper")
        self.assertEqual(providers["active"]["stt"], "browser")
        self.assertEqual(providers["active"]["tts"], "browser_speech_synthesis")
        self.assertEqual(providers["speech_settings"]["voice_preference"], "Microsoft George")
        self.assertFalse(providers["providers"]["stt"]["available"])
        self.assertFalse(providers["providers"]["tts"]["available"])

    def test_phase9_mocked_stt_tts_provider_selection(self) -> None:
        tts = MockTTS()
        session = VoiceSession(
            stt=MockSTT("ULTRON, create note provider test"),
            tts=tts,
            configured_stt=MockSTT(),
            configured_tts=tts,
            provider_config=VoiceProviderConfig(stt_provider="mock", tts_provider="mock", voice_identity="ULTRON-test"),
        )

        stt_payload = session.test_stt({})
        tts_payload = session.test_tts("Done.")

        self.assertEqual(stt_payload["transcript"]["text"], "create note provider test")
        self.assertEqual(stt_payload["transcript"]["provider"], "mock_stt")
        self.assertEqual(tts_payload["speech"]["provider"], "mock_tts")
        self.assertEqual(tts.spoken, ["Done."])
        self.assertEqual(tts_payload["speech"]["voice"], "ULTRON-test")

    def test_backend_capture_is_one_shot_and_turns_microphone_off(self) -> None:
        session = VoiceSession(
            stt=MockSTT("ULTRON, create note backend once"),
            tts=MockTTS(),
            capture=MockMicrophoneCapture("ULTRON, create note backend once"),
            configured_capture=MockMicrophoneCapture(),
        )
        state = WebState(UltronBrain(UltronAssistant(_test_settings())), voice=session)

        payload = state.voice_capture({})

        self.assertEqual(payload["status"], "ok")
        self.assertFalse(payload["voice"]["microphone_enabled"])
        self.assertEqual(payload["voice_diagnostics"]["capture_provider"], "mock_capture")

    def test_clap_standby_capture_is_energy_only_and_creates_no_temp_file(self) -> None:
        class FakeAudio:
            @staticmethod
            def tobytes() -> bytes:
                return b"\x00\x00" * 8000

        capture = SoundDeviceMicrophoneCapture(sample_rate=16000, default_seconds=0.55)
        with (
            patch("sounddevice.rec", return_value=FakeAudio()),
            patch("sounddevice.wait"),
            patch("ultron27.voice.tempfile.NamedTemporaryFile") as temporary_file,
        ):
            payload = capture.capture({"seconds": 0.55, "energy_only": True})

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["energy_only"])
        self.assertNotIn("audio_path", payload)
        temporary_file.assert_not_called()

    def test_temporary_command_audio_is_removed_after_transcription(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "command.wav"
            audio_path.write_bytes(b"RIFF-test")
            state = WebState(
                UltronBrain(UltronAssistant(_test_settings())),
                voice=VoiceSession(stt=MockSTT("what time is it"), tts=MockTTS()),
            )

            payload = state.voice_transcribe(
                {
                    "audio_path": str(audio_path),
                    "temporary_audio": True,
                    "audio_duration_ms": 1800,
                    "speech_ms": 1400,
                    "audio_energy": 0.2,
                }
            )

            self.assertEqual(payload["status"], "ok")
            self.assertFalse(audio_path.exists())

    def test_wake_poll_removes_legacy_temporary_audio_without_stt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "standby.wav"
            audio_path.write_bytes(b"RIFF-test")
            state = WebState(UltronBrain(UltronAssistant(_test_settings())))
            state.wake_start()

            payload = state.wake_process(
                {
                    "audio_path": str(audio_path),
                    "temporary_audio": True,
                    "audio_duration_ms": 550,
                    "speech_ms": 0,
                    "audio_energy": 0.001,
                }
            )

            self.assertEqual(payload["status"], "ignored")
            self.assertFalse(audio_path.exists())

    def test_voice_calibration_updates_energy_vad_threshold(self) -> None:
        vad = EnergyVADProvider(0.015)
        session = VoiceSession(
            capture=MockMicrophoneCapture(),
            configured_capture=MockMicrophoneCapture(),
            vad=vad,
            configured_vad=vad,
        )
        state = WebState(UltronBrain(UltronAssistant(_test_settings())), voice=session)

        payload = state.voice_calibrate({"audio_energy": 0.04, "seconds": 1})

        self.assertEqual(payload["status"], "ok")
        self.assertAlmostEqual(vad.threshold, 0.018, places=3)
        self.assertEqual(payload["voice_diagnostics"]["status"], "calibrated")

    def test_phase9_voice_provider_api_endpoints(self) -> None:
        tts = MockTTS()
        state = WebState(
            UltronBrain(UltronAssistant(_test_settings())),
            voice=VoiceSession(
                stt=MockSTT("ULTRON, create note api provider"),
                tts=tts,
                configured_stt=MockSTT(),
                configured_tts=tts,
                provider_config=VoiceProviderConfig(stt_provider="mock", tts_provider="mock"),
            ),
        )
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            providers = json.loads(urlopen(base + "/api/voice/providers", timeout=5).read().decode("utf-8"))
            stt = json.loads(
                urlopen(
                    Request(
                        base + "/api/voice/test-stt",
                        data=json.dumps({}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    ),
                    timeout=5,
                )
                .read()
                .decode("utf-8")
            )
            tts_payload = json.loads(
                urlopen(
                    Request(
                        base + "/api/voice/test-tts",
                        data=json.dumps({"text": "Provider API test."}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    ),
                    timeout=5,
                )
                .read()
                .decode("utf-8")
            )
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(providers["active"]["stt"], "mock_stt")
        self.assertEqual(providers["active"]["tts"], "mock_tts")
        self.assertEqual(stt["transcript"]["text"], "create note api provider")
        self.assertEqual(tts_payload["speech"]["provider"], "mock_tts")

    def test_phase10_wake_word_detected_enters_listening(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        state.wake_start()
        payload = state.wake_process({"transcript": "ULTRON", "audio_energy": 0.8})

        self.assertEqual(payload["status"], "wake_detected")
        self.assertEqual(payload["wake"]["mode"], "listening")
        self.assertEqual(payload["spoken_response"], "At your service, sir.")
        self.assertEqual(payload["visual_state"], "listening")
        self.assertIsNone(payload["last_task"])

    def test_phase10_config_accepts_wake_and_vad_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "ultron.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "wake_word_provider": "openwakeword",
                        "wake_phrases": ["ULTRON", "Hey ULTRON"],
                        "wake_model_path": "models/wake.onnx",
                        "vad_provider": "silero",
                        "vad_energy_threshold": 0.025,
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(
                config_path,
                environ={"ULTRON_WAKE_WORD_PROVIDER": "text", "ULTRON_VAD_PROVIDER": "energy"},
                base_dir=root,
            )

            self.assertEqual(config.wake_word_provider, "text")
            self.assertEqual(config.wake_phrases, ("ULTRON", "Hey ULTRON"))
            self.assertEqual(config.wake_model_path, root / "models" / "wake.onnx")
            self.assertEqual(config.vad_provider, "energy")
            self.assertEqual(config.vad_energy_threshold, 0.025)

    def test_phase10_config_accepts_double_clap_settings(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            config_path = root / "ultron.config.json"
            config_path.write_text(
                json.dumps(
                    {
                        "wake_word_provider": "double_clap",
                        "wake_auto_start": True,
                        "clap_spike_ratio": 5.5,
                        "clap_min_gap_s": 0.08,
                        "clap_max_gap_s": 0.42,
                        "clap_cooldown_s": 0.6,
                    }
                ),
                encoding="utf-8",
            )

            config = load_config(config_path, environ={}, base_dir=root)

            self.assertEqual(config.wake_word_provider, "double_clap")
            self.assertTrue(config.wake_auto_start)
            self.assertEqual(config.clap_spike_ratio, 5.5)
            self.assertEqual(config.clap_min_gap_s, 0.08)
            self.assertEqual(config.clap_max_gap_s, 0.42)
            self.assertEqual(config.clap_cooldown_s, 0.6)

    def test_double_clap_standby_can_start_automatically(self) -> None:
        config = UltronConfig(
            wake_word_provider="double_clap",
            wake_auto_start=True,
            voice_stt_provider="mock",
            voice_tts_provider="mock",
            voice_capture_provider="mock",
        )

        voice = build_voice_session(config)
        state = WebState(UltronBrain(UltronAssistant(_test_settings())), voice=voice)

        self.assertTrue(voice.wake_status.always_listening)
        self.assertEqual(voice.wake_status.mode, "waiting_for_wake_word")
        self.assertTrue(voice.status.microphone_enabled)
        self.assertFalse(voice.status.listening)
        self.assertEqual(state.visual_state, "waiting_for_wake_word")
        self.assertIn("Double clap", state.last_subtitle)

    def test_web_clap_loop_uses_energy_standby_then_full_command_capture(self) -> None:
        app = Path("web/app.js").read_text(encoding="utf-8")

        self.assertIn("energy_only: true", app)
        self.assertIn("command_capture: true", app)
        self.assertIn("const commandCapture = captureBackendWakeCommand();", app)
        self.assertIn("Promise.all([commandCapture, speakText(greeting)])", app)
        self.assertIn("captureBackendWakeCommand", app)

    def test_phase10_double_clap_provider_detects_second_spike(self) -> None:
        config = WakeGateConfig(wake_word_provider="double_clap")
        provider = DoubleClapWakeProvider(config)

        first = provider.detect({"audio_energy": 0.05, "timestamp_s": 1.0})
        provider.detect({"audio_energy": 0.001, "timestamp_s": 1.10})
        second = provider.detect({"audio_energy": 0.05, "timestamp_s": 1.20})

        self.assertFalse(first.detected)
        self.assertTrue(second.detected)
        self.assertEqual(second.phrase, "double_clap")
        self.assertEqual(second.provider, "double_clap")

    def test_phase10_double_clap_wake_gate_enters_listening_without_command(self) -> None:
        config = WakeGateConfig(wake_word_provider="double_clap")
        wake = DoubleClapWakeProvider(config)
        vad = EnergyVADProvider(0.015)
        state = WebState(
            UltronBrain(UltronAssistant(_test_settings())),
            voice=VoiceSession(
                wake=wake,
                vad=vad,
                configured_wake=wake,
                configured_vad=vad,
                wake_config=config,
            ),
        )

        state.wake_start()
        first = state.wake_process({"audio_energy": 0.05, "timestamp_s": 1.0})
        quiet = state.wake_process({"audio_energy": 0.001, "timestamp_s": 1.10})
        second = state.wake_process({"audio_energy": 0.05, "timestamp_s": 1.20})

        self.assertEqual(first["status"], "ignored")
        self.assertEqual(quiet["status"], "ignored")
        self.assertEqual(second["status"], "wake_detected")
        self.assertEqual(second["wake"]["mode"], "listening")
        self.assertEqual(second["spoken_response"], "At your service, sir.")
        self.assertFalse(second["command_executed"])

    def test_double_clap_peak_times_can_wake_from_one_backend_capture(self) -> None:
        config = WakeGateConfig(wake_word_provider="double_clap")
        provider = DoubleClapWakeProvider(config)

        result = provider.detect({"audio_energy": 0.08, "timestamp_s": 10.0, "audio_peak_times_s": [0.02, 0.22]})

        self.assertTrue(result.detected)
        self.assertEqual(result.phrase, "double_clap")

    def test_double_clap_wake_stays_listening_through_quiet_gap(self) -> None:
        config = WakeGateConfig(wake_word_provider="double_clap")
        wake = DoubleClapWakeProvider(config)
        vad = EnergyVADProvider(0.015)
        state = WebState(
            UltronBrain(UltronAssistant(_test_settings())),
            voice=VoiceSession(
                wake=wake,
                vad=vad,
                configured_wake=wake,
                configured_vad=vad,
                wake_config=config,
            ),
        )

        state.wake_start()
        state.wake_process({"audio_energy": 0.05, "timestamp_s": 1.0})
        state.wake_process({"audio_energy": 0.001, "timestamp_s": 1.10})
        state.wake_process({"audio_energy": 0.05, "timestamp_s": 1.20})
        quiet = state.wake_process({"audio_energy": 0.001, "timestamp_s": 1.50})

        self.assertEqual(quiet["wake"]["mode"], "listening")
        self.assertEqual(quiet["message"], "Listening for a command, sir.")
        self.assertFalse(quiet["command_executed"])

    def test_full_command_capture_returns_to_clap_standby_when_silent(self) -> None:
        config = WakeGateConfig(wake_word_provider="double_clap")
        wake = DoubleClapWakeProvider(config)
        vad = EnergyVADProvider(0.015)
        state = WebState(
            UltronBrain(UltronAssistant(_test_settings())),
            voice=VoiceSession(
                wake=wake,
                vad=vad,
                configured_wake=wake,
                configured_vad=vad,
                wake_config=config,
            ),
        )

        state.wake_start()
        state.wake_process({"audio_energy": 0.08, "audio_peak_times_s": [0.02, 0.22], "timestamp_s": 1.0})
        silent = state.wake_process(
            {
                "audio_energy": 0.001,
                "audio_duration_ms": 6000,
                "speech_ms": 0,
                "command_capture": True,
                "timestamp_s": 2.0,
            }
        )

        self.assertEqual(silent["status"], "no_command")
        self.assertEqual(silent["wake"]["mode"], "waiting_for_wake_word")
        self.assertFalse(silent["voice"]["listening"])
        self.assertIn("Double clap", silent["message"])

    def test_full_command_capture_executes_after_double_clap(self) -> None:
        config = WakeGateConfig(wake_word_provider="double_clap")
        wake = DoubleClapWakeProvider(config)
        vad = EnergyVADProvider(0.015)
        state = WebState(
            UltronBrain(UltronAssistant(_test_settings())),
            voice=VoiceSession(
                stt=TextPayloadSTT(),
                wake=wake,
                vad=vad,
                configured_wake=wake,
                configured_vad=vad,
                wake_config=config,
            ),
        )

        state.wake_start()
        state.wake_process({"audio_energy": 0.08, "audio_peak_times_s": [0.02, 0.22], "timestamp_s": 1.0})
        command = state.wake_process(
            {
                "transcript": "what is 15 percent of 200",
                "audio_energy": 0.2,
                "audio_duration_ms": 1800,
                "speech_ms": 1500,
                "command_capture": True,
                "timestamp_s": 2.0,
            }
        )

        self.assertTrue(command["command_executed"])
        self.assertEqual(command["task"]["steps"][0]["tool_call"]["name"], "calculate")
        self.assertEqual(command["task"]["steps"][0]["result"]["data"]["value"], 30)

    def test_clap_authorized_audio_reaches_stt_even_below_local_vad_threshold(self) -> None:
        config = WakeGateConfig(wake_word_provider="double_clap")
        wake = DoubleClapWakeProvider(config)
        vad = EnergyVADProvider(0.015)
        state = WebState(
            UltronBrain(UltronAssistant(_test_settings())),
            voice=VoiceSession(
                stt=MockSTT("open notepad"),
                wake=wake,
                vad=vad,
                configured_wake=wake,
                configured_vad=vad,
                wake_config=config,
            ),
        )

        state.wake_start()
        state.wake_process({"audio_energy": 0.08, "audio_peak_times_s": [0.02, 0.22], "timestamp_s": 1.0})
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "quiet-command.wav"
            audio_path.write_bytes(b"RIFF-test")
            command = state.wake_process(
                {
                    "audio_path": str(audio_path),
                    "temporary_audio": True,
                    "audio_energy": 0.001,
                    "audio_duration_ms": 6000,
                    "speech_ms": 0,
                    "command_capture": True,
                    "timestamp_s": 2.0,
                }
            )

            self.assertFalse(audio_path.exists())

        self.assertTrue(command["command_executed"])
        self.assertEqual(command["task"]["steps"][0]["tool_call"]["name"], "open_application")
        self.assertEqual(command["voice_diagnostics"]["last_transcript"], "open notepad")

    def test_empty_authorized_audio_returns_to_clap_standby_after_stt(self) -> None:
        config = WakeGateConfig(wake_word_provider="double_clap")
        wake = DoubleClapWakeProvider(config)
        vad = EnergyVADProvider(0.015)
        state = WebState(
            UltronBrain(UltronAssistant(_test_settings())),
            voice=VoiceSession(
                stt=MockSTT(""),
                wake=wake,
                vad=vad,
                configured_wake=wake,
                configured_vad=vad,
                wake_config=config,
            ),
        )

        state.wake_start()
        state.wake_process({"audio_energy": 0.08, "audio_peak_times_s": [0.02, 0.22], "timestamp_s": 1.0})
        with tempfile.TemporaryDirectory() as tmp:
            audio_path = Path(tmp) / "silent-command.wav"
            audio_path.write_bytes(b"RIFF-test")
            empty = state.wake_process(
                {
                    "audio_path": str(audio_path),
                    "temporary_audio": True,
                    "audio_energy": 0.001,
                    "audio_duration_ms": 6000,
                    "speech_ms": 0,
                    "command_capture": True,
                    "timestamp_s": 2.0,
                }
            )

        self.assertEqual(empty["status"], "no_command")
        self.assertEqual(empty["wake"]["mode"], "waiting_for_wake_word")
        self.assertFalse(empty["voice"]["listening"])
        self.assertEqual(empty["voice_diagnostics"]["status"], "empty")

        standby = state.wake_process({"energy_only": True, "audio_energy": 0.001, "timestamp_s": 3.0})
        self.assertEqual(standby["voice_diagnostics"]["status"], "empty")

    def test_phase10_no_wake_word_does_not_execute(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        state.wake_start()
        payload = state.wake_process({"transcript": "create note ignored background speech", "audio_energy": 0.8})

        self.assertEqual(payload["status"], "ignored")
        self.assertFalse(payload["command_executed"])
        self.assertEqual(payload["wake"]["mode"], "waiting_for_wake_word")
        self.assertIsNone(payload["last_task"])
        self.assertEqual(payload["history"], [])

    def test_phase10_noisy_audio_is_ignored(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        state.wake_start()
        payload = state.wake_process({"transcript": "   ", "audio_energy": 0.0})

        self.assertEqual(payload["status"], "ignored")
        self.assertTrue(payload["wake"]["noisy_ignored"])
        self.assertFalse(payload["command_executed"])
        self.assertIsNone(payload["last_task"])

    def test_phase10_vad_speech_segment_calls_stt_after_wake(self) -> None:
        class CountingSTT(TextPayloadSTT):
            def __init__(self) -> None:
                self.calls = 0

            def transcribe(self, payload: dict) -> object:
                self.calls += 1
                return super().transcribe(payload)

        stt = CountingSTT()
        state = WebState(
            UltronBrain(UltronAssistant(_test_settings())),
            voice=VoiceSession(
                stt=stt,
                wake=MockWakeWordProvider(),
                vad=MockVADProvider(speech=True),
                configured_wake=MockWakeWordProvider(),
                configured_vad=MockVADProvider(speech=True),
                wake_config=WakeGateConfig(wake_word_provider="mock", vad_provider="mock"),
            ),
        )

        state.wake_start()
        payload = state.wake_process({"transcript": "ULTRON, create note wake test", "audio_energy": 0.9})

        self.assertEqual(stt.calls, 1)
        self.assertTrue(payload["command_executed"])
        self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "create_note")

    def test_wake_chat_response_keeps_listening_for_followup(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        state.wake_start()
        payload = state.wake_process({"transcript": "ULTRON, hi", "audio_energy": 0.9})

        self.assertTrue(payload["command_executed"])
        self.assertTrue(payload["continue_listening"])
        self.assertEqual(payload["wake"]["mode"], "listening")
        self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "assistant_reply")

    def test_phase10_wake_voice_safety_behavior_is_unchanged(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        state.wake_start()
        payload = state.wake_process({"transcript": "Hey ULTRON, delete project_report.txt", "audio_energy": 0.8})

        self.assertTrue(payload["needs_confirmation"])
        self.assertEqual(payload["task"]["status"], "waiting_for_confirmation")
        self.assertEqual(payload["voice"]["pending_confirmation_goal"], "delete project_report.txt")

    def test_phase10_wake_api_endpoints(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            started = json.loads(
                urlopen(
                    Request(
                        base + "/api/wake/start",
                        data=json.dumps({}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    ),
                    timeout=5,
                )
                .read()
                .decode("utf-8")
            )
            status = json.loads(urlopen(base + "/api/wake/status", timeout=5).read().decode("utf-8"))
            ignored = json.loads(
                urlopen(
                    Request(
                        base + "/api/wake/process",
                        data=json.dumps({"transcript": "background speech", "audio_energy": 0.8}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    ),
                    timeout=5,
                )
                .read()
                .decode("utf-8")
            )
            stopped = json.loads(
                urlopen(
                    Request(
                        base + "/api/wake/stop",
                        data=json.dumps({}).encode("utf-8"),
                        headers={"Content-Type": "application/json"},
                        method="POST",
                    ),
                    timeout=5,
                )
                .read()
                .decode("utf-8")
            )
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(started["wake"]["mode"], "waiting_for_wake_word")
        self.assertTrue(status["wake"]["always_listening"])
        self.assertEqual(ignored["status"], "ignored")
        self.assertEqual(stopped["wake"]["mode"], "inactive")

    def test_phase11_safe_root_blocks_explicit_outside_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            allowed = workspace / "allowed"
            outside = workspace / "outside"
            allowed.mkdir()
            outside.mkdir()
            outside_file = outside / "secret.txt"
            outside_file.write_text("nope", encoding="utf-8")

            executor = Executor(dry_run=False, workspace=workspace, safe_roots=(allowed,))

            opened = executor.execute(ToolCall("open_file", {"file_name": str(outside_file)}))
            searched = executor.execute(ToolCall("search_files", {"query": "secret", "folder": str(outside)}))

            self.assertEqual(opened.status, "blocked")
            self.assertEqual(searched.status, "blocked")

    def test_phase11_windows_app_alias_resolution_is_allowlisted(self) -> None:
        aliases = merge_windows_app_aliases({"editor": "notepad.exe", "bad": "cmd.exe && whoami"})

        self.assertEqual(resolve_app_alias("Chrome", aliases), "chrome.exe")
        self.assertEqual(resolve_app_alias("editor", aliases), "notepad.exe")
        self.assertEqual(resolve_app_alias("paint", aliases), "mspaint.exe")
        self.assertIsNone(resolve_app_alias("bad", aliases))
        self.assertIsNone(resolve_app_alias("unknown app", aliases))

    def test_open_application_can_resolve_start_menu_shortcuts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            shortcut_dir = root / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Tools"
            shortcut_dir.mkdir(parents=True)
            shortcut = shortcut_dir / "Example Studio.lnk"
            shortcut.write_text("", encoding="utf-8")

            with patch.dict(os.environ, {"PROGRAMDATA": str(root), "APPDATA": str(root)}, clear=False):
                target = resolve_app_target("example studio", merge_windows_app_aliases())

        self.assertEqual(target, str(shortcut))

    def test_open_application_can_resolve_store_apps(self) -> None:
        completed = subprocess.CompletedProcess(
            args=[],
            returncode=0,
            stdout=json.dumps([{"Name": "WhatsApp", "AppID": "5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App"}]),
        )

        with patch("subprocess.run", return_value=completed):
            target = resolve_app_target("Whatsapp", merge_windows_app_aliases())

        self.assertEqual(target, r"shell:AppsFolder\5319275A.WhatsAppDesktop_cv1g1gvanyjgm!App")

    def test_phase11_cursor_alias_is_available_without_raw_shell(self) -> None:
        aliases = merge_windows_app_aliases()

        target = resolve_app_alias("cursor", aliases)

        self.assertIsNotNone(target)
        self.assertNotIn("&&", target or "")
        self.assertNotIn("|", target or "")

    def test_phase11_medium_risk_terminal_requires_confirmation(self) -> None:
        plan = regex_plan("open terminal")
        decision = decide(plan, validate_tool_call(plan.tool_call))
        payload = UltronAssistant(_test_settings()).handle("open terminal")

        self.assertEqual(plan.tool_call.name, "open_terminal")
        self.assertEqual(decision.action, "confirm")
        self.assertEqual(decision.permission_level, "medium_risk_confirmation")
        self.assertEqual(payload["tool_call"]["name"], "open_terminal")
        self.assertEqual(payload["policy"]["action"], "confirm")

    def test_phase11_destructive_action_remains_unimplemented_after_confirmation(self) -> None:
        plan = regex_plan("delete project_report.txt")
        decision = decide(plan, validate_tool_call(plan.tool_call), confirmed=True)
        result = Executor(dry_run=False).execute(plan.tool_call)

        self.assertEqual(decision.action, "allow")
        self.assertEqual(decision.permission_level, "destructive_blocked_or_not_implemented")
        self.assertEqual(result.status, "not_implemented")

    def test_phase11_audit_reader_returns_recent_records(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            audit_path = Path(tmp) / "audit.jsonl"
            append_audit_record({"utterance": "first"}, audit_path)
            append_audit_record({"utterance": "second"}, audit_path)

            records = read_recent_audit_records(audit_path, limit=1)

            self.assertEqual(len(records), 1)
            self.assertEqual(records[0]["utterance"], "second")

    def test_phase11_audit_recent_api_endpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            settings = RuntimeSettings(
                dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
                audit_log=workspace / ".ultron" / "audit.jsonl",
                workspace=workspace,
                dry_run=True,
                safe_roots=(workspace,),
                app_aliases=None,
                screenshot_dir=workspace / ".ultron" / "screenshots",
                planner_mode="rules",
                llm_model="unused",
                llm_endpoint="http://localhost:11434",
                llm_timeout_seconds=1.0,
                write_audit=True,
            )
            state = WebState(UltronBrain(UltronAssistant(settings)))
            state.command("open notepad")
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_address[1]}"
                payload = json.loads(urlopen(base + "/api/audit/recent?limit=5", timeout=5).read().decode("utf-8"))
            finally:
                server.shutdown()
                server.server_close()

            self.assertEqual(payload["status"], "ok")
            self.assertTrue(payload["records"])
            self.assertTrue(any(record.get("utterance") == "open notepad" for record in payload["records"]))

    def test_phase12_skill_schema_validation(self) -> None:
        registry = SkillRegistry.with_builtins(
            UltronAssistant(_test_settings()),
            KnowledgeBase(Path(".ultron/test-knowledge.json"), workspace=Path("."), safe_roots=(Path("."),)),
        )
        spec = registry.specs["notes"]

        validation = validate_skill_input(spec, {"action": "create"})

        self.assertFalse(validation.valid)
        self.assertIn("Missing required input: title", validation.errors)

    def test_phase12_unknown_skill_is_rejected(self) -> None:
        registry = SkillRegistry.with_builtins(
            UltronAssistant(_test_settings()),
            KnowledgeBase(Path(".ultron/test-knowledge.json"), workspace=Path("."), safe_roots=(Path("."),)),
        )

        result = registry.run("unknown_skill", {})

        self.assertEqual(result["status"], "unknown_skill")

    def test_phase12_notes_skill_runs_through_safe_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            assistant = UltronAssistant(_workspace_settings(workspace, dry_run=False, write_audit=False))
            knowledge = KnowledgeBase(workspace / ".ultron" / "knowledge.json", workspace=workspace, safe_roots=(workspace,))
            registry = SkillRegistry.with_builtins(assistant, knowledge)

            result = registry.run("notes", {"action": "create", "title": "phase twelve", "content": "skills work"})

            self.assertEqual(result["status"], "success")
            self.assertTrue((workspace / "notes" / "phase_twelve.md").exists())
            self.assertEqual(result["result"]["runtime"]["tool_call"]["name"], "create_note")
            self.assertEqual(result["result"]["runtime"]["policy"]["action"], "allow")

    def test_phase12_knowledge_ingest_and_search(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "phase12.md"
            source.write_text("Phase 12 adds reusable skills and a local knowledge base for project planning.", encoding="utf-8")
            knowledge = KnowledgeBase(workspace / ".ultron" / "knowledge.json", workspace=workspace, safe_roots=(workspace,))

            ingest = knowledge.ingest(source)
            search = knowledge.search("reusable skills", limit=3)

            self.assertEqual(ingest["status"], "ok")
            self.assertEqual(search["status"], "ok")
            self.assertEqual(search["matches"][0]["title"], "phase12")

    def test_phase12_knowledge_rejects_secrets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "secret.txt"
            source.write_text("api_key = do-not-store-this", encoding="utf-8")
            knowledge = KnowledgeBase(workspace / ".ultron" / "knowledge.json", workspace=workspace, safe_roots=(workspace,))

            ingest = knowledge.ingest(source)

            self.assertEqual(ingest["status"], "rejected_sensitive")
            self.assertEqual(knowledge.sources(), [])

    def test_phase12_skill_policy_still_blocks_unconfirmed_medium_skill(self) -> None:
        registry = SkillRegistry.with_builtins(
            UltronAssistant(_test_settings()),
            KnowledgeBase(Path(".ultron/test-knowledge.json"), workspace=Path("."), safe_roots=(Path("."),)),
        )
        registry.register(
            SkillSpec(
                name="medium_test",
                description="A medium-risk test skill.",
                input_schema={"required": {"value": {"type": "string"}}, "optional": {}},
                risk_level=RiskLevel.MEDIUM,
            ),
            lambda _registry, _payload, _confirmed: {"status": "ok"},
        )

        result = registry.run("medium_test", {"value": "safe text"})

        self.assertEqual(result["status"], "confirmation_required")
        self.assertEqual(result["policy"]["permission_level"], "medium_risk_confirmation")

    def test_phase12_skills_and_knowledge_api_endpoints(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            workspace = Path(tmp)
            source = workspace / "project.txt"
            source.write_text("ULTRON skills can summarize local project knowledge.", encoding="utf-8")
            assistant = UltronAssistant(_workspace_settings(workspace, dry_run=True, write_audit=False))
            knowledge = KnowledgeBase(workspace / ".ultron" / "knowledge.json", workspace=workspace, safe_roots=(workspace,))
            state = WebState(UltronBrain(assistant), knowledge=knowledge, skills=SkillRegistry.with_builtins(assistant, knowledge))
            server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_address[1]}"
                skills = json.loads(urlopen(base + "/api/skills", timeout=5).read().decode("utf-8"))
                ingest = json.loads(
                    urlopen(
                        Request(
                            base + "/api/knowledge/ingest",
                            data=json.dumps({"path": str(source)}).encode("utf-8"),
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        ),
                        timeout=5,
                    )
                    .read()
                    .decode("utf-8")
                )
                search = json.loads(urlopen(base + "/api/knowledge/search?query=skills", timeout=5).read().decode("utf-8"))
                skill_run = json.loads(
                    urlopen(
                        Request(
                            base + "/api/skills/run",
                            data=json.dumps({"name": "project_summary", "input": {"query": "skills"}}).encode("utf-8"),
                            headers={"Content-Type": "application/json"},
                            method="POST",
                        ),
                        timeout=5,
                    )
                    .read()
                    .decode("utf-8")
                )
            finally:
                server.shutdown()
                server.server_close()

            self.assertEqual(skills["status"], "ok")
            self.assertTrue(any(skill["name"] == "notes" for skill in skills["skills"]))
            self.assertEqual(ingest["status"], "ok")
            self.assertEqual(search["knowledge"]["matches"][0]["title"], "project")
            self.assertEqual(skill_run["status"], "ok")

    def test_phase13_diagnostics_snapshot_contains_readiness(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))

        payload = build_diagnostics(state)

        self.assertEqual(payload["status"], "ok")
        self.assertIn("backend", payload)
        self.assertEqual(payload["brain"]["planner_mode"], "rules")
        self.assertIn("audit_log", payload["runtime"])
        self.assertIn("providers", payload["voice"])
        self.assertIn("recent_errors", payload)

    def test_phase13_diagnostics_api_endpoint(self) -> None:
        state = WebState(UltronBrain(UltronAssistant(_test_settings())))
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{server.server_address[1]}"
            payload = json.loads(urlopen(base + "/api/diagnostics", timeout=5).read().decode("utf-8"))
        finally:
            server.shutdown()
            server.server_close()

        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["version"].startswith("UltronPhase13"))
        self.assertIn("safe_roots", payload["runtime"])

    def test_phase13_config_wizard_defaults_are_safe(self) -> None:
        config = generate_config(workspace="workspace", safe_roots=["workspace"], stt_provider="mock", tts_provider="mock")

        self.assertTrue(config["dry_run"])
        self.assertEqual(config["workspace"], "workspace")
        self.assertEqual(config["safe_roots"], ["workspace"])
        self.assertEqual(config["voice_stt_provider"], "mock")
        self.assertEqual(config["voice_tts_provider"], "mock")

    def test_phase13_launcher_finds_next_port_when_busy(self) -> None:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as busy:
            busy.bind(("127.0.0.1", 0))
            busy.listen(1)
            used_port = busy.getsockname()[1]

            open_port = find_open_port("127.0.0.1", used_port, attempts=3)

        self.assertNotEqual(open_port, used_port)

    def test_phase8_wake_word_is_removed_from_transcript(self) -> None:
        self.assertEqual(strip_wake_word("ULTRON, create note demo"), "create note demo")
        self.assertEqual(strip_wake_word("hey ultron: open notepad"), "open notepad")
        self.assertEqual(strip_wake_word("ULTRON play a video on YouTube"), "play a video on YouTube")

    def test_phase14_transcript_cleanup_removes_fillers_and_repeats(self) -> None:
        cleaned = clean_transcript("Hey ULTRON, um open open notepad please")

        self.assertEqual(cleaned, "open notepad please")

    def test_phase14_transcript_cleanup_removes_leading_by_before_command(self) -> None:
        cleaned = clean_transcript("Bye play Blinding Lights on Spotify")

        self.assertEqual(cleaned, "play Blinding Lights on Spotify")

    def test_command_capture_removes_wake_greeting_echo(self) -> None:
        self.assertEqual(strip_wake_greeting("At your service, sir. Open Notepad"), "Open Notepad")
        self.assertEqual(strip_wake_greeting("Service sir, play Blinding Lights"), "play Blinding Lights")

    def test_multilingual_transcript_keyterm_repair_preserves_command_separator(self) -> None:
        cleaned = clean_transcript(
            "Whats app M Hitansh: hi",
            keyterms=("WhatsApp", "Em Hitansh"),
        )

        self.assertEqual(cleaned, "WhatsApp Em Hitansh: hi")

    def test_phase14_audio_analysis_rejects_short_or_noisy_input(self) -> None:
        short = analyze_audio_payload({"audio_duration_ms": 90, "audio_energy": 0.2})
        noisy = analyze_audio_payload({"audio_duration_ms": 1200, "speech_ms": 900, "audio_energy": 0.3, "noisy": True})

        self.assertTrue(short["rejected"])
        self.assertIn("too short", short["reason"])
        self.assertTrue(noisy["rejected"])
        self.assertTrue(noisy["noisy"])

    def test_phase14_backend_mock_capture_executes_through_voice_pipeline(self) -> None:
        voice = VoiceSession(capture=MockMicrophoneCapture("ULTRON, create note backend voice"), stt=TextPayloadSTT())
        state = WebState(UltronBrain(UltronAssistant(_test_settings())), voice=voice)

        payload = state.voice_capture({})

        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["voice_diagnostics"]["capture_provider"], "mock_capture")
        self.assertEqual(payload["transcript"]["text"], "create note backend voice")
        self.assertEqual(payload["task"]["steps"][0]["tool_call"]["name"], "create_note")

    def test_phase14_backend_capture_unavailable_is_nonfatal(self) -> None:
        class UnavailableCapture:
            name = "unavailable_capture"

            def capture(self, payload: dict[str, object]) -> dict[str, object]:
                return {"status": "unavailable", "message": "No backend microphone."}

            def health(self):
                from ultron27.voice import ProviderHealth

                return ProviderHealth("capture", self.name, configured=True, active=True, available=False, detail="No backend microphone.")

        state = WebState(
            UltronBrain(UltronAssistant(_test_settings())),
            voice=VoiceSession(capture=UnavailableCapture(), configured_capture=UnavailableCapture()),
        )

        payload = state.voice_capture({})

        self.assertEqual(payload["status"], "capture_unavailable")
        self.assertEqual(payload["last_task"], None)
        self.assertIn("No backend microphone", payload["message"])


def _test_settings() -> RuntimeSettings:
    return RuntimeSettings(
        dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
        audit_log=Path(".ultron/test-audit.jsonl"),
        workspace=Path("."),
        dry_run=True,
        safe_roots=(Path("."),),
        app_aliases=None,
        screenshot_dir=Path(".ultron/screenshots"),
        planner_mode="rules",
        llm_model="unused",
        llm_endpoint="http://localhost:11434",
        llm_timeout_seconds=1.0,
        write_audit=False,
    )


def _workspace_settings(workspace: Path, *, dry_run: bool = True, write_audit: bool = False) -> RuntimeSettings:
    return RuntimeSettings(
        dataset_path=Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl"),
        audit_log=workspace / ".ultron" / "audit.jsonl",
        workspace=workspace,
        dry_run=dry_run,
        safe_roots=(workspace,),
        app_aliases=None,
        screenshot_dir=workspace / ".ultron" / "screenshots",
        planner_mode="rules",
        llm_model="unused",
        llm_endpoint="http://localhost:11434",
        llm_timeout_seconds=1.0,
        write_audit=write_audit,
    )


if __name__ == "__main__":
    unittest.main()

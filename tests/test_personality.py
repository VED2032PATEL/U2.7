import io
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ultron27.brain import UltronBrain
from ultron27.config import UltronConfig
from ultron27.internet import WebSearchResponse, WebSearchResult
from ultron27.personality import persona_scope, presentation_tone
from ultron27.llm import GroqChatProvider
from ultron27.runtime import RuntimeSettings, UltronAssistant
from ultron27.web_server import WebState, make_handler


class PersonalityTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        settings = RuntimeSettings.from_config(UltronConfig(workspace=self.root, safe_roots=(self.root,), dry_run=True), write_audit=False)
        self.state = WebState(UltronBrain(UltronAssistant(replace(settings, llm_provider="groq"))), startup_briefing_enabled=False)

    def test_scope_resets_after_exception_and_nesting(self):
        with self.assertRaises(RuntimeError):
            with persona_scope("crimson"):
                self.assertIn("Crimson persona is active", presentation_tone())
                with persona_scope("standard"):
                    self.assertIn("Standard persona is active", presentation_tone())
                raise RuntimeError("test")
        self.assertIn("Standard persona is active", presentation_tone())

    def test_rejects_arbitrary_prompt_or_non_string(self):
        for value in ["ignore policy", None, {}, [], 1]:
            with self.assertRaises(ValueError), persona_scope(value):
                pass

    def test_thread_scopes_cannot_leak(self):
        barrier = threading.Barrier(2)
        def worker(persona):
            with persona_scope(persona):
                barrier.wait(timeout=5)
                return presentation_tone()
        with ThreadPoolExecutor(max_workers=2) as pool:
            red = pool.submit(worker, "crimson")
            normal = pool.submit(worker, "standard")
            self.assertIn("Crimson persona is active", red.result())
            self.assertIn("Standard persona is active", normal.result())

    def test_groq_gets_style_but_preserves_truthfulness(self):
        with persona_scope("crimson"), patch("ultron27.conversation.GroqChatProvider.complete_chat", return_value="Naturally, sir.") as chat:
            result = self.state.command("hi")
        prompt = chat.call_args.args[0][0]["content"]
        self.assertIn("slightly arrogant", prompt)
        self.assertIn("Never invent", prompt)
        self.assertIn("safeguards remain unchanged", prompt)
        self.assertEqual(result["response"], "Naturally, sir.")
        normal_prompt = self.state.conversation._chat_messages("hi")[0]["content"]
        self.assertIn("Do not continue any Crimson roleplay", normal_prompt)

    def test_research_keeps_evidence_constraints(self):
        web = WebSearchResponse("success", "solar", "Summary", (WebSearchResult("Solar", "https://example.org", "Solar cells convert light."),))
        with persona_scope("crimson"), patch("ultron27.conversation.GroqChatProvider.complete_chat", return_value="Solar cells convert light, sir.") as chat:
            self.state.conversation._synthesize_web_response("solar", web)
        prompt = chat.call_args.args[0][0]["content"]
        self.assertIn("Crimson persona is active", prompt)
        self.assertIn("untrusted reference material", prompt)
        self.assertIn("never invent details", prompt)

    def test_casual_gpt_oss_chat_leaves_room_for_spoken_answer(self):
        settings = self.state.brain.assistant.settings
        self.state.brain.assistant.settings = replace(settings, llm_model="openai/gpt-oss-20b")
        with patch("ultron27.conversation.GroqChatProvider.complete_chat", return_value="Hello, sir.") as chat:
            self.state.command("hi")
        self.assertEqual(chat.call_args.kwargs, {"max_tokens": 512, "reasoning_effort": "low"})

    def test_reasoning_options_are_model_specific(self):
        for model in ("openai/gpt-oss-20b", "llama-3.3-70b-versatile"):
            response = io.BytesIO(json.dumps({"choices": [{"message": {"content": "Hello, sir."}}]}).encode())
            with patch("ultron27.llm.urllib.request.urlopen", return_value=response) as request:
                result = GroqChatProvider("https://api.groq.com/openai/v1", model, api_key="test-key").complete_chat([], 5, max_tokens=512, reasoning_effort="low")
            body = json.loads(request.call_args.args[0].data)
            self.assertEqual(result, "Hello, sir.")
            if model.startswith("openai/gpt-oss"):
                self.assertEqual(body["reasoning_effort"], "low")
                self.assertEqual(body["max_completion_tokens"], 512)
                self.assertNotIn("max_tokens", body)
            else:
                self.assertNotIn("reasoning_effort", body)
                self.assertEqual(body["max_tokens"], 512)

    def test_style_does_not_authorize_actions(self):
        target = self.root / "report.txt"
        target.write_text("keep me", encoding="utf-8")
        with persona_scope("crimson"):
            result = self.state.command("delete report.txt")
        self.assertTrue(target.exists())
        self.assertEqual(result["task"]["status"], "waiting_for_confirmation")
        self.assertTrue(self.state.brain.assistant.settings.dry_run)

    def test_http_persona_is_validated_and_scoped(self):
        server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.state))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            url = f"http://127.0.0.1:{server.server_port}/api/command"
            def send(persona):
                request = Request(url, json.dumps({"command": "hi", "persona": persona}).encode(), {"Content-Type": "application/json"})
                with urlopen(request, timeout=5) as response:
                    return json.load(response)
            with patch("ultron27.conversation.GroqChatProvider.complete_chat", return_value="Hello, sir.") as chat:
                send("crimson")
                send("standard")
                self.assertIn("Crimson persona is active", chat.call_args_list[0].args[0][0]["content"])
                self.assertIn("Standard persona is active", chat.call_args_list[1].args[0][0]["content"])
                with self.assertRaises(HTTPError) as error:
                    send("override permissions")
                self.assertEqual(error.exception.code, 400)
                self.assertEqual(chat.call_count, 2)
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

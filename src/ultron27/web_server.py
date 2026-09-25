from __future__ import annotations

import argparse
import base64
import binascii
import json
import mimetypes
import re
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

from .app_paths import resource_root
from .audit import append_audit_record, read_recent_audit_records
from .brain import TaskState, UltronBrain
from .config import load_config
from .conversation import ConversationManager
from .diagnostics import PHASE13_VERSION, build_diagnostics
from .knowledge import KnowledgeBase
from .modeling import generate_model_scene
from .missions import MissionManager
from .runtime import RuntimeSettings, UltronAssistant
from .skills import SkillRegistry
from .voice import VoiceSession, build_voice_session
from .weather import get_current_weather
from .youtube import is_youtube_video_id


ROOT = resource_root()
WEB_ROOT = ROOT / "web"


@dataclass(frozen=True)
class TaskPlanProxy:
    payload: dict[str, Any]

    @property
    def status(self) -> str:
        return str(self.payload.get("status", "completed"))

    @property
    def summary(self) -> str:
        return str(self.payload.get("summary") or "")


def _task_from_payload(payload: dict[str, Any] | None) -> TaskPlanProxy:
    task = payload.get("task") if isinstance(payload, dict) else None
    return TaskPlanProxy(task if isinstance(task, dict) else {})


@dataclass
class WebState:
    brain: UltronBrain
    knowledge: KnowledgeBase | None = None
    skills: SkillRegistry | None = None
    conversation: ConversationManager | None = None
    voice: VoiceSession = field(default_factory=VoiceSession)
    visual_state: str = "idle"
    subtitles_enabled: bool = True
    last_subtitle: str = "ULTRON 2.7 online."
    last_task: dict[str, Any] | None = None
    recent_tasks: list[dict[str, Any]] = field(default_factory=list)
    assistant_location: str = "Jabalpur"
    startup_briefing_enabled: bool = True
    speech_barge_in_enabled: bool = True
    _briefing_cache: dict[str, Any] | None = field(default=None, init=False, repr=False)
    _briefing_cached_at: float = field(default=0.0, init=False, repr=False)
    missions: MissionManager = field(init=False, repr=False)

    def __post_init__(self) -> None:
        settings = self.brain.assistant.settings
        self.missions = MissionManager(self.brain.assistant)
        if self.conversation is None:
            self.conversation = ConversationManager(self.brain)
        if self.knowledge is None:
            self.knowledge = KnowledgeBase(
                settings.workspace / ".ultron" / "knowledge" / "index.json",
                workspace=settings.workspace,
                safe_roots=settings.safe_roots,
            )
        if self.skills is None:
            self.skills = SkillRegistry.with_builtins(self.brain.assistant, self.knowledge)
        if self.voice.wake_status.always_listening:
            self.visual_state = "waiting_for_wake_word"
            self.last_subtitle = (
                "Voice standby is active. Double clap to wake me."
                if self.voice.wake_status.wake_provider == "double_clap"
                else "Wake standby is active."
            )

    def command(self, text: str, *, confirmed: bool = False, mode: str = "do") -> dict[str, Any]:
        command = text.strip()
        self.visual_state = "thinking"
        if not command:
            self.visual_state = "idle"
            self.last_subtitle = "No command received."
            return self.snapshot({"status": "empty", "message": self.last_subtitle})

        lowered = command.lower()
        if lowered.startswith("/agent "):
            try:
                mission = self.missions.create(command[7:].strip())
            except ValueError as exc:
                self.visual_state = "idle"
                self.last_subtitle = str(exc)
                return self.snapshot({"status": "error", "message": str(exc), "subtitle": str(exc)})
            self.visual_state = "idle"
            self.last_subtitle = "Your agent task is ready to review, sir."
            return self.snapshot({"status": "ok", "subtitle": self.last_subtitle,
                                  "ui_directive": {"kind": "agent", "id": mission["id"]}})
        interface_request = _interface_request(command) if mode != "plan" and not lowered.startswith("/plan ") else None
        ui_directive = None
        if interface_request is not None:
            response, ui_directive = interface_request
            conversation_payload = self.conversation.interface_reply(command, response, route="interface") if self.conversation else None
            task = _task_from_payload(conversation_payload)
        elif lowered.startswith("/plan "):
            task = self.brain.plan(command[6:].strip())
            conversation_payload = None
        elif lowered.startswith("/do "):
            conversation_payload = self.conversation.handle(command[4:].strip(), confirmed=confirmed) if self.conversation else None
            task = _task_from_payload(conversation_payload)
        elif mode == "plan":
            task = self.brain.plan(command)
            conversation_payload = None
        else:
            conversation_payload = self.conversation.handle(command, confirmed=confirmed) if self.conversation else None
            task = _task_from_payload(conversation_payload)

        if task is not None and isinstance(task, TaskPlanProxy):
            self.last_task = task.payload
            task_status = task.status
            summary = task.summary
        else:
            self.last_task = task.to_dict()
            task_status = task.status.value
            summary = task.summary
        self._remember_task(self.last_task)
        self.last_subtitle = (
            str(conversation_payload.get("response") or conversation_payload.get("subtitle"))
            if isinstance(conversation_payload, dict)
            else summary or f"Task {task_status}."
        )
        self.visual_state = "listening" if task_status == TaskState.WAITING_FOR_CONFIRMATION.value else "speaking"
        extra = {"status": "ok", "task": self.last_task, "subtitle": self.last_subtitle}
        if isinstance(conversation_payload, dict):
            extra.update(
                {
                    "route": conversation_payload.get("route"),
                    "understood": conversation_payload.get("understood"),
                    "response": conversation_payload.get("response"),
                    "conversation": conversation_payload.get("conversation"),
                    "conversation_history": conversation_payload.get("conversation_history"),
                    "memory_enabled": conversation_payload.get("memory_enabled"),
                }
            )
            if conversation_payload.get("route") == "web_search":
                ui_directive = _research_directive(self.last_task)
        if ui_directive is None:
            ui_directive = _youtube_player_directive(self.last_task)
        if ui_directive:
            extra["ui_directive"] = ui_directive
        return self.snapshot(extra)

    def research(self, query: str) -> dict[str, Any]:
        clean = " ".join(str(query or "").strip().split())
        if not clean:
            return self.snapshot({"status": "empty", "message": "Enter a topic for the research console."})
        return self.command(f"search the internet for {clean}")

    def model_generate(self, description: str) -> dict[str, Any]:
        result = generate_model_scene(description, self.brain.assistant.settings)
        self.last_subtitle = str(result.get("message") or "3D model request processed.")
        self.visual_state = "speaking" if result.get("status") == "success" else "listening"
        if self.brain.assistant.settings.write_audit:
            append_audit_record(
                {
                    "record_type": "model_generation",
                    "description": str(description or "")[:180],
                    "status": result.get("status"),
                    "source": result.get("source"),
                    "object_count": len((result.get("scene") or {}).get("objects") or []),
                },
                self.brain.assistant.settings.audit_log,
            )
        return self.snapshot(result)

    def startup_briefing(self, *, force: bool = False) -> dict[str, Any]:
        greeting = _time_greeting(datetime.now().hour)
        if not self.startup_briefing_enabled:
            return self.snapshot(
                {
                    "status": "disabled",
                    "message": f"{greeting}, sir. ULTRON 2.7 is online.",
                    "location": self.assistant_location,
                    "barge_in_enabled": self.speech_barge_in_enabled,
                }
            )

        now = time.time()
        if not force and self._briefing_cache is not None and now - self._briefing_cached_at < 900:
            return self.snapshot(dict(self._briefing_cache))

        try:
            weather = get_current_weather(self.assistant_location)
            message = (
                f"{greeting}, sir. In {weather.location}, it is {round(weather.temperature_c)} degrees Celsius "
                f"and {weather.condition}. It feels like {round(weather.apparent_temperature_c)} degrees, "
                f"with {weather.humidity_percent} percent humidity and wind near {round(weather.wind_speed_kmh)} kilometers per hour."
            )
            payload = {
                "status": "ok",
                "message": message,
                "location": self.assistant_location,
                "weather": weather.to_dict(),
                "barge_in_enabled": self.speech_barge_in_enabled,
            }
        except Exception as exc:
            payload = {
                "status": "weather_unavailable",
                "message": f"{greeting}, sir. ULTRON 2.7 is online. I could not retrieve the Jabalpur weather briefing right now.",
                "location": self.assistant_location,
                "weather": None,
                "weather_error": str(exc),
                "barge_in_enabled": self.speech_barge_in_enabled,
            }
        self._briefing_cache = payload
        self._briefing_cached_at = now
        self.last_subtitle = str(payload["message"])
        return self.snapshot(dict(payload))

    def camera_capture(self, payload: dict[str, Any]) -> dict[str, Any]:
        data_url = str(payload.get("image") or payload.get("data_url") or "")
        match = re.fullmatch(r"data:image/(?P<kind>png|jpeg);base64,(?P<data>[A-Za-z0-9+/=\r\n]+)", data_url)
        if not match:
            return self.snapshot({"status": "error", "message": "Camera capture did not contain a valid PNG or JPEG image."})
        try:
            image = base64.b64decode(match.group("data"), validate=True)
        except (ValueError, binascii.Error):
            return self.snapshot({"status": "error", "message": "Camera capture could not be decoded."})
        if not image or len(image) > 8 * 1024 * 1024:
            return self.snapshot({"status": "error", "message": "Camera capture is empty or larger than 8 MB."})
        kind = match.group("kind")
        signature_ok = image.startswith(b"\x89PNG\r\n\x1a\n") if kind == "png" else image.startswith(b"\xff\xd8\xff")
        if not signature_ok:
            return self.snapshot({"status": "error", "message": "Camera image signature did not match its declared format."})

        directory = self.brain.assistant.settings.screenshot_dir.resolve()
        directory.mkdir(parents=True, exist_ok=True)
        suffix = ".png" if kind == "png" else ".jpg"
        path = directory / f"ultron-camera-{datetime.now().strftime('%Y%m%d-%H%M%S-%f')}{suffix}"
        path.write_bytes(image)
        self.last_subtitle = f"Photo captured and saved as {path.name}, sir."
        if self.brain.assistant.settings.write_audit:
            append_audit_record(
                {"record_type": "camera_capture", "path": str(path), "bytes": len(image)},
                self.brain.assistant.settings.audit_log,
            )
        return self.snapshot({"status": "saved", "message": self.last_subtitle, "filename": path.name, "path": str(path), "bytes": len(image)})

    def voice_start(self, *, push_to_talk: bool | None = None) -> dict[str, Any]:
        self.visual_state = "listening"
        return self.snapshot(self.voice.start(push_to_talk=push_to_talk))

    def voice_stop(self) -> dict[str, Any]:
        payload = self.voice.stop()
        self.visual_state = "idle"
        return self.snapshot(payload)

    def voice_transcribe(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.visual_state = "thinking"
        voice_payload = self.voice.transcribe_and_run(payload, lambda goal, confirmed=False: self.command(goal, confirmed=confirmed))
        return self._voice_response_snapshot(voice_payload)

    def voice_capture(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.visual_state = "listening"
        voice_payload = self.voice.capture_and_run(payload, lambda goal, confirmed=False: self.command(goal, confirmed=confirmed))
        return self._voice_response_snapshot(voice_payload)

    def _voice_response_snapshot(self, voice_payload: dict[str, Any]) -> dict[str, Any]:
        if voice_payload.get("status") == "empty":
            self.last_subtitle = str(voice_payload.get("message", "No speech was detected."))
            self.visual_state = "listening"
            return self.snapshot(voice_payload)
        if voice_payload.get("status") == "capture_unavailable":
            self.last_subtitle = str(voice_payload.get("message", "Backend microphone capture is unavailable."))
            self.visual_state = "listening"
            return self.snapshot(voice_payload)
        record = voice_payload.get("record", {})
        spoken = str(voice_payload.get("spoken_response", self.last_subtitle))
        self.last_subtitle = spoken
        self.visual_state = "speaking" if not self.voice.status.muted else "idle"
        return self.snapshot({**voice_payload, "subtitle": self.last_subtitle, "voice_record": record})

    def memory_status(self) -> dict[str, Any]:
        if self.conversation is None:
            return {"status": "ok", "enabled": True, "memory": self.brain.memory.list()}
        snapshot = self.conversation.memory_snapshot()
        return self.snapshot({"status": "ok", "enabled": snapshot["enabled"], "memory": snapshot["items"]})

    def memory_forget(self, query: str) -> dict[str, Any]:
        if self.conversation is None:
            removed = self.brain.memory.forget(query)
            return self.snapshot({"status": "ok", "removed": removed, "memory": self.brain.memory.list()})
        snapshot = self.conversation.forget_memory(query)
        self.last_subtitle = f"Forgot {snapshot['removed']} matching memory item(s)." if snapshot["removed"] else "No matching memory item found."
        return self.snapshot({"status": "ok", "enabled": snapshot["enabled"], "removed": snapshot["removed"], "memory": snapshot["items"]})

    def memory_toggle(self, enabled: bool) -> dict[str, Any]:
        if self.conversation is None:
            self.brain.memory.remember("memory_enabled", str(bool(enabled)).lower(), kind="control")
            return self.snapshot({"status": "ok", "enabled": bool(enabled), "memory": self.brain.memory.list()})
        snapshot = self.conversation.set_memory_enabled(bool(enabled))
        self.last_subtitle = "Memory is now on." if snapshot["enabled"] else "Memory is now off."
        return self.snapshot({"status": "ok", "enabled": snapshot["enabled"], "memory": snapshot["items"]})

    def wake_start(self) -> dict[str, Any]:
        self.visual_state = "waiting_for_wake_word"
        payload = self.voice.start_wake()
        if self.voice.wake_status.wake_provider == "double_clap":
            self.last_subtitle = "Voice standby. Double clap to wake me."
        else:
            self.last_subtitle = "Always-listening is on. Say ULTRON or Hey ULTRON."
        return self.snapshot(payload)

    def wake_stop(self) -> dict[str, Any]:
        payload = self.voice.stop_wake()
        self.visual_state = "idle"
        self.last_subtitle = "Always-listening is off."
        return self.snapshot(payload)

    def wake_status(self) -> dict[str, Any]:
        return self.snapshot(self.voice.wake_snapshot())

    def wake_process(self, payload: dict[str, Any]) -> dict[str, Any]:
        self.visual_state = "transcribing"
        if payload.get("capture"):
            capture_payload = self.voice.capture.capture(payload)
            if capture_payload.get("status") not in {"ok", "delegated"}:
                self.last_subtitle = str(capture_payload.get("message", "Backend microphone capture is unavailable."))
                self.visual_state = "waiting_for_wake_word" if self.voice.wake_status.always_listening else "idle"
                return self.snapshot(self.voice.snapshot({"status": "capture_unavailable", "capture": capture_payload, "message": self.last_subtitle}))
            payload = {**payload, **capture_payload}
        try:
            wake_payload = self.voice.process_wake_input(payload, lambda goal, confirmed=False: self.command(goal, confirmed=confirmed))
        finally:
            self.voice.cleanup_capture(payload)
        status = wake_payload.get("status")
        if status in {"ignored", "inactive"}:
            self.last_subtitle = str(wake_payload.get("message", "Input ignored by wake/VAD gate."))
            self.visual_state = "waiting_for_wake_word" if self.voice.wake_status.always_listening else "idle"
            return self.snapshot(wake_payload)
        if status == "wake_detected":
            self.last_subtitle = str(wake_payload.get("spoken_response") or wake_payload.get("message") or "Wake detected. Listening.")
            self.visual_state = "listening"
            return self.snapshot({**wake_payload, "subtitle": self.last_subtitle})
        if wake_payload.get("command_executed"):
            record = wake_payload.get("record", {})
            spoken = str(wake_payload.get("spoken_response", self.last_subtitle))
            self.last_subtitle = spoken
            self.visual_state = "speaking" if not self.voice.status.muted else "waiting_for_wake_word"
            return self.snapshot({**wake_payload, "subtitle": self.last_subtitle, "voice_record": record})
        self.visual_state = "waiting_for_wake_word"
        return self.snapshot(wake_payload)

    def voice_status(self) -> dict[str, Any]:
        return self.snapshot({"status": "ok", **self.voice.snapshot()})

    def voice_providers(self) -> dict[str, Any]:
        return self.snapshot({"status": "ok", **self.voice.providers_status()})

    def audit_recent(self, *, limit: int = 25) -> dict[str, Any]:
        audit_log = self.brain.assistant.settings.audit_log
        return self.snapshot({"status": "ok", "audit_log": str(audit_log), "records": read_recent_audit_records(audit_log, limit=limit)})

    def diagnostics(self) -> dict[str, Any]:
        return build_diagnostics(self)

    def skills_list(self) -> dict[str, Any]:
        return self.snapshot({"status": "ok", "skills": self.skills.list() if self.skills else []})

    def skills_run(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.skills is None:
            return self.snapshot({"status": "error", "message": "Skill registry is unavailable."})
        name = str(payload.get("name") or payload.get("skill") or "")
        skill_input = payload.get("input") if isinstance(payload.get("input"), dict) else {}
        result = self.skills.run(name, skill_input, confirmed=bool(payload.get("confirmed", False)))
        self.last_subtitle = str(result.get("result", {}).get("message") or result.get("message") or "Skill run completed.")
        self.visual_state = "speaking" if result.get("status") not in {"blocked", "confirmation_required"} else "listening"
        return self.snapshot(result)

    def knowledge_ingest(self, payload: dict[str, Any]) -> dict[str, Any]:
        if self.knowledge is None:
            return self.snapshot({"status": "error", "message": "Knowledge base is unavailable."})
        result = self.knowledge.ingest(str(payload.get("path") or ""))
        self._audit_knowledge("knowledge_ingest", result)
        self.last_subtitle = str(result.get("message", "Knowledge ingest completed."))
        return self.snapshot({"status": result.get("status", "ok"), "knowledge": result, "sources": self.knowledge.sources()})

    def knowledge_search(self, query: str, *, limit: int = 5) -> dict[str, Any]:
        if self.knowledge is None:
            return self.snapshot({"status": "error", "message": "Knowledge base is unavailable."})
        result = self.knowledge.search(query, limit=limit)
        self._audit_knowledge("knowledge_search", {"query": query, "limit": limit, "match_count": len(result.get("matches", []))})
        return self.snapshot({"status": result.get("status", "ok"), "knowledge": result})

    def voice_test_stt(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.snapshot(self.voice.test_stt(payload))

    def voice_test_tts(self, payload: dict[str, Any]) -> dict[str, Any]:
        text = str(payload.get("text") or "ULTRON voice provider test.")
        return self.snapshot(self.voice.test_tts(text))

    def voice_calibrate(self, payload: dict[str, Any]) -> dict[str, Any]:
        result = self.voice.calibrate_microphone(payload)
        self.last_subtitle = str(result.get("message") or "Voice calibration completed.")
        return self.snapshot(result)

    def voice_warmup(self) -> dict[str, Any]:
        stt = self.voice.stt
        health = stt.warm_up() if hasattr(stt, "warm_up") else self.voice.providers_status()["providers"]["active_stt"]
        return self.snapshot({"status": "ok", "stt": health.to_dict() if hasattr(health, "to_dict") else health, **self.voice.providers_status()})

    def speak(self, payload: dict[str, Any]) -> dict[str, Any]:
        action = str(payload.get("action", "speak"))
        if action == "stop":
            self.visual_state = "listening"
            return self.snapshot(self.voice.stop_speaking())
        if "muted" in payload:
            self.voice.set_muted(bool(payload.get("muted")))
        text = str(payload.get("text") or self.last_subtitle or "").strip()
        speech = self.voice.speak(text)
        audio = speech.get("speech")
        if isinstance(audio, dict) and audio.get("status") == "audio_stream":
            stream_id = str(audio.get("stream_id") or "")
            if re.fullmatch(r"[0-9a-f]{32}", stream_id):
                audio["stream_url"] = f"/api/voice/audio/{stream_id}"
        self.visual_state = "speaking" if speech.get("voice", {}).get("speaking") else self.visual_state
        return self.snapshot(speech)

    def cancel_confirmation(self) -> dict[str, Any]:
        self.visual_state = "listening" if self.voice.status.microphone_enabled else "idle"
        self.last_subtitle = "Action cancelled."
        return self.snapshot(self.voice.cancel_confirmation())

    def toggle_subtitles(self, enabled: bool | None = None) -> dict[str, Any]:
        self.subtitles_enabled = not self.subtitles_enabled if enabled is None else bool(enabled)
        return self.snapshot({"status": "ok", "subtitles_enabled": self.subtitles_enabled})

    def set_visual_state(self, state: str) -> dict[str, Any]:
        if state not in {"idle", "inactive", "waiting_for_wake_word", "listening", "transcribing", "thinking", "speaking"}:
            return self.snapshot({"status": "error", "message": f"Unknown state: {state}"})
        self.visual_state = state
        return self.snapshot({"status": "ok", "visual_state": self.visual_state})

    def snapshot(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "visual_state": self.visual_state,
            "subtitles_enabled": self.subtitles_enabled,
            "last_subtitle": self.last_subtitle,
            "last_task": self.last_task,
            "recent_tasks": self.recent_tasks[-8:],
            "knowledge_sources": self.knowledge.sources() if self.knowledge else [],
            "memory_enabled": self.conversation.memory_enabled if self.conversation else True,
            "conversation_history": [item.to_dict() for item in self.conversation.turns[-10:]] if self.conversation else [],
        }
        if extra:
            payload.update(extra)
        return payload

    def _remember_task(self, task: dict[str, Any]) -> None:
        self.recent_tasks.append(
            {
                "task_id": task.get("task_id"),
                "goal": task.get("original_goal"),
                "status": task.get("status"),
                "summary": task.get("summary"),
                "created_at": task.get("created_at"),
            }
        )
        self.recent_tasks = self.recent_tasks[-20:]

    def _audit_knowledge(self, record_type: str, payload: dict[str, Any]) -> None:
        settings = self.brain.assistant.settings
        if not settings.write_audit:
            return
        append_audit_record({"record_type": record_type, **payload}, settings.audit_log)


def build_state(args: argparse.Namespace) -> WebState:
    config = load_config(args.config)
    dry_run = config.dry_run
    if args.execute:
        dry_run = False
    if args.dry_run:
        dry_run = True
    settings = RuntimeSettings.from_config(
        config,
        dataset_path=args.dataset,
        workspace=args.workspace,
        dry_run=dry_run,
        execute_requested=args.execute,
        write_audit=not args.no_audit,
        planner_mode=args.planner_mode,
        llm_model=args.llm_model,
        llm_endpoint=args.llm_endpoint,
    )
    assistant = UltronAssistant(settings)
    knowledge = KnowledgeBase(
        settings.workspace / ".ultron" / "knowledge" / "index.json",
        workspace=settings.workspace,
        safe_roots=settings.safe_roots,
    )
    return WebState(
        UltronBrain(assistant),
        knowledge=knowledge,
        skills=SkillRegistry.with_builtins(assistant, knowledge),
        voice=build_voice_session(config),
        assistant_location=config.assistant_location,
        startup_briefing_enabled=config.startup_briefing_enabled,
        speech_barge_in_enabled=config.speech_barge_in_enabled,
    )


def make_handler(state: WebState, web_root: Path = WEB_ROOT) -> type[BaseHTTPRequestHandler]:
    class Handler(BaseHTTPRequestHandler):
        server_version = PHASE13_VERSION

        @staticmethod
        def shutdown_agent() -> None:
            if getattr(state, "missions", None) is not None:
                state.missions.shutdown()

        def do_GET(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path == "/favicon.ico":
                self.send_response(204)
                self.end_headers()
                return
            if parsed.path == "/api/status":
                self._json(state.snapshot({"status": "ok"}))
                return
            if parsed.path == "/api/agent":
                selected = (parse_qs(parsed.query).get("id") or [""])[0]
                try:
                    self._json(state.missions.snapshot(selected))
                except ValueError as exc:
                    self._json({"status": "error", "message": str(exc)}, status=404)
                return
            if parsed.path == "/api/diagnostics":
                self._json(state.diagnostics())
                return
            if parsed.path == "/api/memory":
                self._json(state.memory_status())
                return
            if parsed.path == "/api/skills":
                self._json(state.skills_list())
                return
            if parsed.path == "/api/knowledge/search":
                query = parse_qs(parsed.query)
                search = str((query.get("query") or query.get("q") or [""])[0])
                try:
                    limit = int((query.get("limit") or ["5"])[0])
                except ValueError:
                    limit = 5
                self._json(state.knowledge_search(search, limit=max(1, min(limit, 25))))
                return
            if parsed.path == "/api/voice/status":
                self._json(state.voice_status())
                return
            if parsed.path == "/api/voice/providers":
                self._json(state.voice_providers())
                return
            if parsed.path == "/api/wake/status":
                self._json(state.wake_status())
                return
            if parsed.path == "/api/audit/recent":
                query = parse_qs(parsed.query)
                try:
                    limit = int((query.get("limit") or ["25"])[0])
                except ValueError:
                    limit = 25
                self._json(state.audit_recent(limit=max(1, min(limit, 100))))
                return
            if parsed.path == "/api/briefing":
                query = parse_qs(parsed.query)
                force = str((query.get("force") or [""])[0]).lower() in {"1", "true", "yes"}
                self._json(state.startup_briefing(force=force))
                return
            if parsed.path.startswith("/api/voice/audio/"):
                self._stream_voice_audio(parsed.path.rsplit("/", 1)[-1])
                return
            self._serve_static(parsed.path)

        def do_POST(self) -> None:  # noqa: N802
            parsed = urlparse(self.path)
            if parsed.path.startswith("/api/agent/"):
                origin = self.headers.get("Origin")
                if (origin and urlparse(origin).netloc != self.headers.get("Host")) or self.headers.get_content_type() != "application/json":
                    self._json({"status": "error", "message": "Agent requests must originate from this ULTRON interface."}, status=403)
                    return
            body = self._read_json()
            from .personality import persona_scope

            persona = body.get("persona", "standard")
            if not isinstance(persona, str) or persona not in {"standard", "crimson"}:
                self._json({"status": "error", "message": "Unknown presentation persona."}, status=400)
                return
            with persona_scope(persona):
                self._dispatch_post(parsed, body)

        def _dispatch_post(self, parsed: Any, body: dict[str, Any]) -> None:
            if parsed.path.startswith("/api/agent/"):
                self._agent_request(parsed.path, body)
                return
            if parsed.path == "/api/command":
                self._json(state.command(str(body.get("command", "")), confirmed=bool(body.get("confirmed", False)), mode=str(body.get("mode", "do"))))
                return
            if parsed.path == "/api/skills/run":
                self._json(state.skills_run(body))
                return
            if parsed.path == "/api/knowledge/ingest":
                self._json(state.knowledge_ingest(body))
                return
            if parsed.path == "/api/memory/forget":
                self._json(state.memory_forget(str(body.get("query") or body.get("key") or "")))
                return
            if parsed.path == "/api/memory/toggle":
                self._json(state.memory_toggle(bool(body.get("enabled", True))))
                return
            if parsed.path == "/api/voice/start":
                push_to_talk = body.get("push_to_talk")
                self._json(state.voice_start(push_to_talk=push_to_talk if isinstance(push_to_talk, bool) else None))
                return
            if parsed.path == "/api/voice/stop":
                self._json(state.voice_stop())
                return
            if parsed.path == "/api/voice/transcribe":
                self._json(state.voice_transcribe(body))
                return
            if parsed.path == "/api/voice/capture":
                self._json(state.voice_capture(body))
                return
            if parsed.path == "/api/voice/test-stt":
                self._json(state.voice_test_stt(body))
                return
            if parsed.path == "/api/voice/test-tts":
                self._json(state.voice_test_tts(body))
                return
            if parsed.path == "/api/research":
                self._json(state.research(str(body.get("query") or "")))
                return
            if parsed.path == "/api/model/generate":
                self._json(state.model_generate(str(body.get("description") or body.get("prompt") or "")))
                return
            if parsed.path == "/api/camera/capture":
                self._json(state.camera_capture(body))
                return
            if parsed.path == "/api/voice/calibrate":
                self._json(state.voice_calibrate(body))
                return
            if parsed.path == "/api/voice/warmup":
                self._json(state.voice_warmup())
                return
            if parsed.path == "/api/wake/start":
                self._json(state.wake_start())
                return
            if parsed.path == "/api/wake/stop":
                self._json(state.wake_stop())
                return
            if parsed.path == "/api/wake/process":
                self._json(state.wake_process(body))
                return
            if parsed.path == "/api/speak":
                self._json(state.speak(body))
                return
            if parsed.path == "/api/confirmation/cancel":
                self._json(state.cancel_confirmation())
                return
            if parsed.path == "/api/subtitles/toggle":
                enabled = body.get("enabled")
                self._json(state.toggle_subtitles(enabled if isinstance(enabled, bool) else None))
                return
            if parsed.path == "/api/state":
                self._json(state.set_visual_state(str(body.get("state", ""))))
                return
            self._json({"status": "not_found", "message": "Unknown API route."}, status=404)

        def _agent_request(self, path: str, body: dict[str, Any]) -> None:
            manager = state.missions
            identifier = str(body.get("id", ""))
            try:
                if path == "/api/agent/plan":
                    task = manager.create(str(body.get("goal", "")))
                elif path == "/api/agent/control":
                    action = str(body.get("action", ""))
                    if action in {"start", "resume", "approve"}:
                        task = manager.start(identifier, confirmed=action == "approve")
                    else:
                        task = manager.control(identifier, action)
                elif path == "/api/agent/routines/save":
                    manager.save_routine(identifier, str(body.get("name", "")))
                    task = manager.store.get(identifier)
                elif path == "/api/agent/routines/plan":
                    task = manager.plan_routine(identifier)
                elif path == "/api/agent/routines/delete":
                    manager.store.delete_routine(identifier)
                    task = None
                else:
                    self._json({"status": "error", "message": "Unknown agent route."}, status=404)
                    return
                self._json(manager.snapshot(task["id"] if task else ""))
            except ValueError as exc:
                self._json({"status": "error", "message": str(exc)}, status=400)

        def log_message(self, format: str, *args: object) -> None:
            return

        def _read_json(self) -> dict[str, Any]:
            length = int(self.headers.get("Content-Length", "0") or "0")
            if length <= 0 or length > 12 * 1024 * 1024:
                return {}
            try:
                payload = json.loads(self.rfile.read(length).decode("utf-8"))
            except json.JSONDecodeError:
                return {}
            return payload if isinstance(payload, dict) else {}

        def _json(self, payload: dict[str, Any], *, status: int = 200) -> None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            try:
                self.wfile.write(data)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return

        def _stream_voice_audio(self, stream_id: str) -> None:
            if not re.fullmatch(r"[0-9a-f]{32}", stream_id):
                self._json({"status": "not_found", "message": "Unknown speech stream."}, status=404)
                return
            try:
                upstream = state.voice.open_tts_stream(stream_id)
            except KeyError:
                self._json({"status": "not_found", "message": "Unknown or expired speech stream."}, status=404)
                return
            except RuntimeError:
                self._json({"status": "unavailable", "message": "Neural speech is temporarily unavailable."}, status=502)
                return

            try:
                with upstream as response:
                    content_type = str(response.headers.get("Content-Type") or "audio/mpeg").split(";", 1)[0]
                    content_length = str(response.headers.get("Content-Length") or "")
                    read_chunk = getattr(response, "read1", response.read)
                    self.send_response(200)
                    self.send_header("Content-Type", content_type)
                    self.send_header("Cache-Control", "no-store")
                    self.send_header("X-Content-Type-Options", "nosniff")
                    if content_length.isdigit():
                        self.send_header("Content-Length", content_length)
                    self.end_headers()
                    while True:
                        chunk = read_chunk(8 * 1024)
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return

        def _serve_static(self, request_path: str) -> None:
            if request_path in {"", "/"}:
                relative = "index.html"
            elif request_path == "/diagnostics":
                relative = "diagnostics.html"
            else:
                relative = request_path.lstrip("/")
            path = (web_root / relative).resolve()
            try:
                path.relative_to(web_root.resolve())
            except ValueError:
                self.send_error(403)
                return
            if not path.exists() or not path.is_file():
                self.send_error(404)
                return
            data = path.read_bytes()
            content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
            if path.suffix == ".js":
                content_type = "text/javascript"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-cache, must-revalidate")
            self.send_header("Referrer-Policy", "strict-origin-when-cross-origin")
            self.end_headers()
            self.wfile.write(data)

    return Handler


def _interface_request(command: str) -> tuple[str, dict[str, Any]] | None:
    lowered = " ".join(command.lower().strip().split())
    gesture_guide = bool(
        re.search(r"\b(?:open|show|display|teach|explain)\b.*\b(?:hand|gesture)\b.*\b(?:guide|controls?|mapping|instructions?)\b", lowered)
        or re.search(r"\bwhat\s+(?:hand\s+)?gestures?\s+(?:can\s+i\s+use|are\s+available)\b", lowered)
    )
    if gesture_guide:
        return "Opening the hand gesture guide, sir.", {"kind": "gestures", "action": "guide"}

    pauses_gestures = bool(re.search(r"\b(?:pause|hold|freeze)\b.*\b(?:hand|gesture|cursor|mouse)\b", lowered))
    if pauses_gestures:
        return "Desktop hand control paused, sir.", {"kind": "gestures", "action": "pause"}

    resumes_gestures = bool(re.search(r"\b(?:resume|continue|unpause)\b.*\b(?:hand|gesture|cursor|mouse)\b", lowered))
    if resumes_gestures:
        return "Desktop hand control resumed, sir.", {"kind": "gestures", "action": "resume"}

    disables_gestures = bool(
        re.search(r"\b(?:disable|stop|turn\s+off|close)\s+(?:the\s+)?(?:hand(?:\s+gesture)?|gesture)\s+(?:controls?|tracking|mode)\b", lowered)
    )
    if disables_gestures:
        return "Hand controls are off, sir.", {"kind": "gestures", "action": "stop"}

    enables_gestures = bool(
        re.search(r"\b(?:enable|start|turn\s+on|open|use)\s+(?:the\s+)?(?:hand(?:\s+gesture)?|gesture)\s+(?:controls?|tracking|mode)\b", lowered)
        or re.search(r"\b(?:move|control)\s+(?:the\s+)?(?:windows?|tabs?|panels?)\s+with\s+(?:my\s+)?hand\b", lowered)
        or re.search(r"\b(?:move|control|use)\s+(?:the\s+)?(?:mouse|cursor|pointer|laptop|computer|screen|desktop)\b.*\b(?:with|using)\s+(?:my\s+)?hand\b", lowered)
    )
    if enables_gestures:
        desktop_mode = bool(re.search(r"\b(?:mouse|cursor|pointer|laptop|computer|whole\s+screen|desktop)\b", lowered))
        directive: dict[str, Any] = {"kind": "gestures", "action": "start"}
        if desktop_mode:
            directive["mode"] = "desktop"
        return "Hand controls are coming online, sir.", directive

    model_controls = (
        (r"(?:\b(?:enlarge|scale\s+up)\s+(?:it|this|that)\b|\b(?:enlarge|increase|scale\s+up|make\s+(?:it|the\s+model)\s+bigger|zoom\s+in)\b.*\b(?:model|object|mesh)\b)", "scale_up", "Enlarging the 3D model, sir."),
        (r"(?:\b(?:diminish|shrink|scale\s+down)\s+(?:it|this|that)\b|\b(?:diminish|shrink|reduce|scale\s+down|make\s+(?:it|the\s+model)\s+smaller|zoom\s+out)\b.*\b(?:model|object|mesh)\b)", "scale_down", "Reducing the 3D model, sir."),
        (r"(?:\bvanish\s+(?:it|this|that)\b|\b(?:hide|vanish|make\s+invisible)\b.*\b(?:model|object|mesh)\b)", "hide", "The 3D model is hidden, sir."),
        (r"\b(?:show|restore|reappear|make\s+visible)\b.*\b(?:model|object|mesh)\b", "show", "The 3D model is visible, sir."),
        (r"\b(?:remove|delete|clear)\b.*\b(?:3d\s+)?(?:model|mesh)\b", "clear", "The 3D model has been cleared, sir."),
        (r"\breset\b.*\b(?:3d\s+)?(?:model|view|mesh)\b", "reset", "The 3D view is reset, sir."),
    )
    for pattern, action, message in model_controls:
        if re.search(pattern, lowered):
            return message, {"kind": "modeler", "action": action}

    scan_360 = bool(
        re.search(r"\b(?:scan|capture|model|reconstruct)\b.*\b360(?:\s*degree)?\b", lowered)
        or re.search(r"\b360(?:\s*degree)?\b.*\b(?:scan|model|reconstruction)\b", lowered)
    )
    if scan_360:
        target = _scan_target(command)
        return (
            f"Starting a 360-degree object scan{f' for {target}' if target else ''}, sir.",
            {"kind": "modeler", "action": "scan_360", "target": target, "required_views": 12},
        )

    camera_object_scan = bool(
        re.search(
            r"\bscan\b.*\b(?:bottle|cup|vase|can|book|phone|chair|shoe|object|item|thing)\b",
            lowered,
        )
    )
    if camera_object_scan:
        target = _scan_target(command)
        return (
            f"I will isolate {target or 'the object'} from the camera frame, sir.",
            {"kind": "modeler", "action": "scan_object", "target": target, "fallback_360": True},
        )

    model_intent = bool(
        re.search(r"\b(?:make|create|build|generate|design|turn)\b.*\b3d\s+(?:model|mesh|relief)\b", lowered)
        or re.search(r"\b(?:open|show|start)\s+(?:the\s+)?(?:3d\s+)?(?:designer|modeler|modeller)\b", lowered)
    )
    if model_intent:
        description = _model_description(command)
        camera_reference = bool(
            re.search(
                r"\b(?:this|it|the\s+object|object\s+in\s+(?:the\s+)?camera|what\s+i(?:'m|\s+am)\s+(?:holding|showing)|camera\s+object)\b",
                lowered,
            )
            or re.search(r"\bfrom\s+(?:the\s+)?camera\b", lowered)
        )
        if camera_reference:
            target = _scan_target(command)
            return (
                f"I will isolate {target or 'the object'} from the camera frame and reconstruct only that object, sir.",
                {"kind": "modeler", "action": "scan_object", "target": target, "fallback_360": True},
            )
        if description:
            return (
                f"Building a manipulable 3D {description}, sir.",
                {"kind": "modeler", "action": "generate", "description": description},
            )
        return "3D designer ready, sir.", {"kind": "modeler", "action": "open"}

    opens_camera = bool(re.search(r"\b(?:open|show|start|launch)\s+(?:the\s+)?camera\b", lowered))
    takes_photo = bool(re.search(r"\b(?:take|capture|click)\s+(?:a\s+)?(?:photo|picture|selfie)\b", lowered))
    if opens_camera or takes_photo:
        message = "Camera console ready, sir." if not takes_photo else "Camera ready. I will frame the shot in ULTRON, sir."
        return message, {"kind": "camera", "action": "open", "auto_capture": takes_photo}

    browser_only = re.fullmatch(
        r"(?:please\s+)?(?:open|show|launch|start)\s+(?:the\s+)?(?:web\s+)?(?:browser|research\s+console|internet)(?:\s+in\s+ultron)?[.!]?",
        lowered,
    )
    if browser_only:
        return "Research console ready, sir. What should I look into?", {"kind": "research", "action": "open", "query": "", "answer": "", "results": []}
    return None


def _model_description(command: str) -> str:
    patterns = (
        r"\b(?:make|create|build|generate|design)\s+(?:me\s+)?(?:an?\s+)?3d\s+(?:model|mesh)\s+(?:of\s+)?(?P<description>.+)$",
        r"\bturn\s+(?P<description>.+?)\s+into\s+(?:an?\s+)?3d\s+(?:model|mesh)$",
    )
    for pattern in patterns:
        match = re.search(pattern, command, flags=re.IGNORECASE)
        if not match:
            continue
        description = re.sub(r"^(?:an?|the)\s+", "", match.group("description").strip(" .?!"), flags=re.IGNORECASE)
        if description.lower() not in {"this", "it", "this object", "the object"}:
            return description[:180]
    return ""


def _scan_target(command: str) -> str:
    match = re.search(
        r"\b(?:this|the)\s+(?P<target>bottle|cup|vase|can|book|phone|chair|shoe|object|item|thing)\b",
        command,
        flags=re.IGNORECASE,
    )
    if match and match.group("target").lower() not in {"object", "item", "thing"}:
        return match.group("target").lower()
    return ""


def _research_directive(task: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(task, dict):
        return None
    for step in task.get("steps") or []:
        result = step.get("result") if isinstance(step, dict) else None
        data = result.get("data") if isinstance(result, dict) else None
        web = data.get("web") if isinstance(data, dict) else None
        if isinstance(web, dict):
            return {
                "kind": "research",
                "action": "show",
                "query": str(web.get("query") or ""),
                "answer": str(web.get("answer") or ""),
                "results": web.get("results") if isinstance(web.get("results"), list) else [],
                "status": str(web.get("status") or "unknown"),
                "synthesized": bool(web.get("synthesized", False)),
            }
    return None


def _youtube_player_directive(task: dict[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(task, dict):
        return None
    for step in task.get("steps") or []:
        if not isinstance(step, dict):
            continue
        tool_call = step.get("tool_call")
        if not isinstance(tool_call, dict) or tool_call.get("name") != "play_youtube_video":
            continue
        result = step.get("result")
        if not isinstance(result, dict) or result.get("status") != "success":
            continue
        data = result.get("data")
        if not isinstance(data, dict) or data.get("playback_target") != "ultron_mini_player":
            continue
        video_id = data.get("video_id")
        if not is_youtube_video_id(video_id):
            continue
        candidate_video_ids: list[str] = []
        raw_candidates = data.get("candidate_video_ids")
        if isinstance(raw_candidates, list):
            for candidate in raw_candidates:
                if is_youtube_video_id(candidate) and candidate not in candidate_video_ids:
                    candidate_video_ids.append(candidate)
                if len(candidate_video_ids) >= 6:
                    break
        candidate_video_ids = [video_id, *(candidate for candidate in candidate_video_ids if candidate != video_id)][:6]
        return {
            "kind": "youtube_player",
            "action": "cue",
            "query": str(data.get("query") or "YouTube video")[:240],
            "video_id": video_id,
            "video_ids": candidate_video_ids,
            "autoplay": False,
        }
    return None


def _time_greeting(hour: int) -> str:
    if hour < 12:
        return "Good morning"
    if hour < 17:
        return "Good afternoon"
    return "Good evening"


def serve(args: argparse.Namespace) -> ThreadingHTTPServer:
    state = build_state(args)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the ULTRON 2.7 visual and voice interface")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-audit", action="store_true")
    parser.add_argument("--planner-mode", choices=["rules", "hybrid", "llm"], default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-endpoint", default=None)
    args = parser.parse_args(argv)

    state = build_state(args)
    server = ThreadingHTTPServer((args.host, args.port), make_handler(state))
    print(f"ULTRON 2.7 interface running at http://{args.host}:{args.port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Shutting down ULTRON interface.")
    finally:
        state.missions.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()

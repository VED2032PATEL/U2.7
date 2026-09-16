from __future__ import annotations

import importlib.util
import json
import re
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import wave
import uuid
from dataclasses import asdict, dataclass, field
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable, Protocol

from .wake import (
    DEFAULT_WAKE_PHRASES,
    EnergyVADProvider,
    TextWakeWordProvider,
    VADProvider,
    WakeGateConfig,
    WakeStatus,
    WakeWordProvider,
    WakeWordResult,
    build_vad_provider,
    build_wake_provider,
    gate_providers_status,
    strip_wake_phrase,
)
from .secrets import get_secret


CONFIRMATION_PHRASES = {"yes confirm", "confirm", "confirmed", "yes proceed", "proceed"}
LOW_CONFIDENCE_THRESHOLD = 0.45
MIN_SPEECH_MS = 180
WAKE_GREETING = "At your service, sir."


class STTProvider(Protocol):
    name: str

    def transcribe(self, payload: dict[str, Any]) -> "STTResult":
        ...


class TTSProvider(Protocol):
    name: str

    def speak(self, text: str, *, voice: str = "ULTRON") -> dict[str, Any]:
        ...

    def stop(self) -> dict[str, Any]:
        ...


class MicrophoneCaptureProvider(Protocol):
    name: str

    def capture(self, payload: dict[str, Any]) -> dict[str, Any]:
        ...


@dataclass(frozen=True)
class VoiceProviderConfig:
    stt_provider: str = "text_payload"
    capture_provider: str = "browser"
    microphone_device: str | None = None
    sample_rate: int = 16000
    capture_seconds: float = 4.0
    tts_provider: str = "browser_speech_synthesis"
    tts_model: str | None = "aura-2-orion-en"
    stt_model_path: Path | None = None
    tts_model_path: Path | None = None
    tts_voice_path: Path | None = None
    device: str = "cpu"
    voice_identity: str = "ULTRON"
    voice_preference: str = "Microsoft George"
    rate: float = 1.03
    pitch: float = 1.0
    volume: float = 1.0
    stt_model: str | None = None
    stt_language: str = "multi"
    stt_keyterms: tuple[str, ...] = ("ULTRON", "WhatsApp", "Spotify")

    @classmethod
    def from_config(cls, config: Any) -> "VoiceProviderConfig":
        return cls(
            stt_provider=str(getattr(config, "voice_stt_provider", cls.stt_provider)).lower(),
            capture_provider=str(getattr(config, "voice_capture_provider", cls.capture_provider)).lower(),
            microphone_device=getattr(config, "voice_microphone_device", None),
            sample_rate=int(getattr(config, "voice_sample_rate", cls.sample_rate)),
            capture_seconds=float(getattr(config, "voice_capture_seconds", cls.capture_seconds)),
            tts_provider=str(getattr(config, "voice_tts_provider", cls.tts_provider)).lower(),
            tts_model=getattr(config, "voice_tts_model", cls.tts_model),
            stt_model=getattr(config, "voice_stt_model", None),
            stt_language=str(getattr(config, "voice_stt_language", cls.stt_language)).strip() or "multi",
            stt_keyterms=_voice_keyterms(config),
            stt_model_path=getattr(config, "voice_stt_model_path", None),
            tts_model_path=getattr(config, "voice_tts_model_path", None),
            tts_voice_path=getattr(config, "voice_tts_voice_path", None),
            device=str(getattr(config, "voice_device", cls.device)).lower(),
            voice_identity=str(getattr(config, "voice_identity", cls.voice_identity)),
            voice_preference=str(getattr(config, "voice_preference", cls.voice_preference)),
            rate=float(getattr(config, "voice_rate", cls.rate)),
            pitch=float(getattr(config, "voice_pitch", cls.pitch)),
            volume=float(getattr(config, "voice_volume", cls.volume)),
        )


def _voice_keyterms(config: Any) -> tuple[str, ...]:
    configured = getattr(config, "voice_stt_keyterms", ()) or ()
    if isinstance(configured, str):
        configured = tuple(item.strip() for item in configured.split(";") if item.strip())
    contacts = getattr(config, "whatsapp_contacts", None) or {}
    contact_names = contacts.keys() if isinstance(contacts, dict) else ()
    builtins = ("ULTRON", "WhatsApp", "Spotify", "YouTube", "Groq", "Deepgram", "Notepad")
    return _dedupe_keyterms((*builtins, *configured, *contact_names))


def _dedupe_keyterms(values: Iterable[str]) -> tuple[str, ...]:
    terms: list[str] = []
    seen: set[str] = set()
    for value in values:
        term = " ".join(str(value).strip().split())
        key = term.casefold()
        if not term or len(term) > 80 or key in seen or any(ord(char) < 32 for char in term):
            continue
        seen.add(key)
        terms.append(term)
        if len(terms) >= 100:
            break
    return tuple(terms)


@dataclass
class ProviderHealth:
    kind: str
    name: str
    configured: bool
    active: bool
    available: bool
    detail: str
    fallback_to: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class STTResult:
    text: str
    confidence: float = 1.0
    provider: str = "text_payload"
    empty: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class AudioDiagnostics:
    active_microphone: str = "browser"
    capture_provider: str = "browser"
    stt_provider: str = "text_payload"
    stt_model_path: str | None = None
    last_transcript: str = ""
    confidence: float = 0.0
    audio_duration_ms: int = 0
    speech_duration_ms: int = 0
    audio_energy: float = 0.0
    rejected: bool = False
    noisy: bool = False
    status: str = "idle"
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class VoiceStatus:
    microphone_enabled: bool = False
    listening: bool = False
    muted: bool = False
    speaking: bool = False
    push_to_talk: bool = False
    stt_provider: str = "text_payload"
    tts_provider: str = "browser_speech_synthesis"
    configured_stt_provider: str = "text_payload"
    configured_tts_provider: str = "browser_speech_synthesis"
    voice_identity: str = "ULTRON"
    voice_preference: str = "Microsoft George"
    voice_rate: float = 1.03
    voice_pitch: float = 1.0
    voice_volume: float = 1.0
    pending_confirmation_goal: str | None = None
    last_error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class TranscriptRecord:
    transcript_id: str
    user_said: str
    ultron_understood: str
    tool_selected: str | None
    action_result: str | None
    spoken_response: str
    needs_confirmation: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TextPayloadSTT:
    name = "text_payload"

    def transcribe(self, payload: dict[str, Any]) -> STTResult:
        text = str(payload.get("transcript") or payload.get("text") or "").strip()
        normalized = clean_transcript(text)
        confidence = _payload_confidence(payload, default=1.0 if normalized else 0.0)
        return STTResult(text=normalized, confidence=confidence, provider=self.name, empty=not bool(normalized))

    def health(self) -> ProviderHealth:
        return ProviderHealth("stt", self.name, configured=True, active=True, available=True, detail="Accepts transcript/text payloads.")


class BrowserTranscriptSTT(TextPayloadSTT):
    name = "browser"

    def health(self) -> ProviderHealth:
        return ProviderHealth("stt", self.name, configured=True, active=True, available=True, detail="Uses browser speech recognition transcript payloads.")


class MockSTT(TextPayloadSTT):
    name = "mock_stt"

    def __init__(self, transcript: str = "create note mock voice") -> None:
        self.transcript = transcript

    def transcribe(self, payload: dict[str, Any]) -> STTResult:
        if payload.get("transcript") or payload.get("text"):
            return super().transcribe(payload)
        normalized = clean_transcript(self.transcript)
        return STTResult(text=normalized, confidence=1.0, provider=self.name, empty=not bool(normalized))

    def health(self) -> ProviderHealth:
        return ProviderHealth("stt", self.name, configured=True, active=True, available=True, detail="Deterministic mock STT provider for tests and demos.")


class FasterWhisperSTT(TextPayloadSTT):
    name = "faster_whisper"

    def __init__(self, model_path: Path | None, *, model_name: str | None = None, device: str = "cpu") -> None:
        self.model_path = model_path
        self.model_name = model_name
        self.device = device
        self._model: Any | None = None
        self._model_error: str | None = None

    def transcribe(self, payload: dict[str, Any]) -> STTResult:
        if payload.get("transcript") or payload.get("text"):
            result = super().transcribe(payload)
            result.provider = self.name
            return result
        audio_path = _payload_audio_path(payload)
        health = self.health()
        if not audio_path or not health.available:
            return STTResult(text="", confidence=0.0, provider=self.name, empty=True)
        try:
            model = self._load_model()
            segments, info = model.transcribe(str(audio_path), vad_filter=True, beam_size=5)
            text = " ".join(segment.text.strip() for segment in segments).strip()
            confidence = float(getattr(info, "language_probability", 1.0))
            normalized = clean_transcript(text)
            return STTResult(text=normalized, confidence=confidence, provider=self.name, empty=not bool(normalized))
        except Exception as exc:
            self._model_error = str(exc)
            return STTResult(text="", confidence=0.0, provider=self.name, empty=True)

    def health(self) -> ProviderHealth:
        if importlib.util.find_spec("faster_whisper") is None:
            return ProviderHealth("stt", self.name, configured=True, active=False, available=False, detail="Python package faster-whisper is not installed.", fallback_to="browser")
        if self._model_error:
            return ProviderHealth("stt", self.name, configured=True, active=True, available=True, detail=f"Installed; last model load/transcribe warning: {self._model_error}")
        if self._model is not None:
            return ProviderHealth("stt", self.name, configured=True, active=True, available=True, detail=f"Model loaded and warm: {self._model_reference()}.")
        if self.model_name:
            return ProviderHealth("stt", self.name, configured=True, active=True, available=True, detail=f"Ready to use faster-whisper model name: {self.model_name}.")
        if self.model_path is None:
            return ProviderHealth("stt", self.name, configured=True, active=False, available=False, detail="No faster-whisper model name or model path is configured.", fallback_to="browser")
        if not self.model_path.exists():
            return ProviderHealth("stt", self.name, configured=True, active=False, available=False, detail=f"Model path not found: {self.model_path}", fallback_to="browser")
        return ProviderHealth("stt", self.name, configured=True, active=True, available=True, detail=f"Ready on {self.device}.")

    def warm_up(self) -> ProviderHealth:
        health = self.health()
        if not health.available:
            return health
        try:
            self._load_model()
        except Exception as exc:
            self._model_error = str(exc)
            return ProviderHealth("stt", self.name, configured=True, active=True, available=True, detail=f"Installed, but model warm-up failed: {exc}")
        return self.health()

    def _model_reference(self) -> str:
        if self.model_name:
            return self.model_name
        if self.model_path is not None:
            return str(self.model_path)
        return "base.en"

    def _load_model(self) -> Any:
        if self._model is not None:
            return self._model
        from faster_whisper import WhisperModel  # type: ignore[import-not-found]

        device = "auto" if self.device == "auto" else self.device
        compute_type = "int8" if device in {"cpu", "auto"} else "float16"
        self._model = WhisperModel(self._model_reference(), device=device, compute_type=compute_type)
        self._model_error = None
        return self._model


class WhisperCppSTT(TextPayloadSTT):
    name = "whisper_cpp"

    def __init__(self, model_path: Path | None, *, device: str = "cpu") -> None:
        self.model_path = model_path
        self.device = device
        self.executable = shutil.which("whisper-cli") or shutil.which("main") or shutil.which("whisper.cpp")

    def transcribe(self, payload: dict[str, Any]) -> STTResult:
        if payload.get("transcript") or payload.get("text"):
            result = super().transcribe(payload)
            result.provider = self.name
            return result
        audio_path = _payload_audio_path(payload)
        health = self.health()
        if not audio_path or not health.available or not self.executable:
            return STTResult(text="", confidence=0.0, provider=self.name, empty=True)
        try:
            process = subprocess.run(
                [self.executable, "-m", str(self.model_path), "-f", str(audio_path), "-nt"],
                check=False,
                capture_output=True,
                text=True,
                timeout=45,
            )
        except Exception:
            return STTResult(text="", confidence=0.0, provider=self.name, empty=True)
        output = process.stdout.strip()
        normalized = clean_transcript(output)
        return STTResult(text=normalized, confidence=1.0 if normalized else 0.0, provider=self.name, empty=not bool(normalized))

    def health(self) -> ProviderHealth:
        if not self.executable:
            return ProviderHealth("stt", self.name, configured=True, active=False, available=False, detail="whisper.cpp executable was not found on PATH.", fallback_to="browser")
        if self.model_path is None:
            return ProviderHealth("stt", self.name, configured=True, active=False, available=False, detail="No whisper.cpp model path is configured.", fallback_to="browser")
        if not self.model_path.exists():
            return ProviderHealth("stt", self.name, configured=True, active=False, available=False, detail=f"Model path not found: {self.model_path}", fallback_to="browser")
        return ProviderHealth("stt", self.name, configured=True, active=True, available=True, detail=f"Ready on {self.device}.")


class DeepgramSTT(TextPayloadSTT):
    name = "deepgram"

    def __init__(
        self,
        *,
        model_name: str | None = None,
        language: str = "multi",
        keyterms: Iterable[str] = (),
        api_key: str | None = None,
        endpoint: str = "https://api.deepgram.com/v1/listen",
    ) -> None:
        self.model_name = model_name or "nova-3"
        self.language = language.strip() or "multi"
        self.keyterms = _dedupe_keyterms(keyterms)
        self.api_key = api_key
        self.endpoint = endpoint
        self._last_error: str | None = None

    def transcribe(self, payload: dict[str, Any]) -> STTResult:
        if payload.get("transcript") or payload.get("text"):
            text = str(payload.get("transcript") or payload.get("text") or "").strip()
            normalized = clean_transcript(text, keyterms=self.keyterms)
            confidence = _payload_confidence(payload, default=1.0 if normalized else 0.0)
            return STTResult(text=normalized, confidence=confidence, provider=self.name, empty=not bool(normalized))
        audio_path = _payload_audio_path(payload)
        health = self.health()
        if not audio_path or not health.available:
            return STTResult(text="", confidence=0.0, provider=self.name, empty=True)
        query_params = [
            ("model", self.model_name),
            ("language", self.language),
            ("smart_format", "true"),
            ("punctuate", "true"),
        ]
        query_params.extend(("keyterm", term) for term in self.keyterms)
        query = urllib.parse.urlencode(query_params)
        request = urllib.request.Request(
            f"{self.endpoint}?{query}",
            data=audio_path.read_bytes(),
            headers={
                "Authorization": f"Token {self._api_key()}",
                "Content-Type": _audio_content_type(audio_path),
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=float(payload.get("timeout", 30) or 30)) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            self._last_error = str(exc)
            return STTResult(text="", confidence=0.0, provider=self.name, empty=True)
        transcript, confidence = _deepgram_transcript(data)
        normalized = clean_transcript(transcript, keyterms=self.keyterms)
        self._last_error = None
        return STTResult(text=normalized, confidence=confidence, provider=self.name, empty=not bool(normalized))

    def health(self) -> ProviderHealth:
        if not self._api_key():
            return ProviderHealth("stt", self.name, configured=True, active=False, available=False, detail="Deepgram API key is missing. Set DEEPGRAM_API_KEY.", fallback_to="browser")
        if self._last_error:
            return ProviderHealth("stt", self.name, configured=True, active=True, available=True, detail=f"Ready with model {self.model_name} ({self.language}); last transcription warning: {self._last_error}")
        return ProviderHealth("stt", self.name, configured=True, active=True, available=True, detail=f"Ready with model {self.model_name} ({self.language}) and {len(self.keyterms)} keyterm hint(s).")

    def _api_key(self) -> str:
        return self.api_key or get_secret("DEEPGRAM_API_KEY")


class BrowserSpeechTTS:
    name = "browser_speech_synthesis"

    def speak(self, text: str, *, voice: str = "ULTRON") -> dict[str, Any]:
        if not text.strip():
            return {"status": "empty", "provider": self.name, "voice": voice}
        return {
            "status": "delegated",
            "provider": self.name,
            "voice": voice,
            "message": "Speech synthesis is delegated to the browser client.",
            "text": text,
        }

    def stop(self) -> dict[str, Any]:
        return {"status": "stopped", "provider": self.name}

    def health(self) -> ProviderHealth:
        return ProviderHealth("tts", self.name, configured=True, active=True, available=True, detail="Browser SpeechSynthesis handles playback.")


class DeepgramTTS:
    name = "deepgram"
    _stream_ttl_seconds = 90.0
    _max_pending_streams = 24

    def __init__(
        self,
        *,
        model_name: str | None = None,
        rate: float = 1.0,
        api_key: str | None = None,
        endpoint: str = "https://api.deepgram.com/v1/speak",
        timeout: float = 20.0,
    ) -> None:
        self.model_name = model_name or "aura-2-orion-en"
        self.rate = max(0.7, min(1.5, float(rate)))
        self.api_key = api_key
        self.endpoint = endpoint
        self.timeout = timeout
        self._last_error: str | None = None
        self._pending_streams: dict[str, tuple[float, str]] = {}
        self._stream_lock = threading.Lock()

    def speak(self, text: str, *, voice: str = "ULTRON") -> dict[str, Any]:
        clean = " ".join(text.strip().split())
        if not clean:
            return {"status": "empty", "provider": self.name, "voice": voice}
        health = self.health()
        if not health.available:
            return {"status": "unavailable", "provider": self.name, "voice": voice, "message": health.detail, "text": clean}
        if len(clean) > 2000:
            return {
                "status": "unavailable",
                "provider": self.name,
                "voice": voice,
                "message": "Deepgram TTS input exceeded 2000 characters; using the browser fallback.",
                "text": clean,
            }
        stream_id = self._queue_stream(clean)
        self._last_error = None
        return {
            "status": "audio_stream",
            "provider": self.name,
            "voice": voice,
            "model": self.model_name,
            "mime_type": "audio/mpeg",
            "stream_id": stream_id,
            "speed": self.rate,
            "text": clean,
        }

    def open_audio_stream(self, stream_id: str) -> Any:
        clean = self._take_stream(stream_id)
        request = self._build_request(clean)
        try:
            response = urllib.request.urlopen(request, timeout=self.timeout)
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            self._last_error = f"HTTP {exc.code}: {detail or exc.reason}"
            raise RuntimeError(self._last_error) from exc
        except (OSError, urllib.error.URLError) as exc:
            self._last_error = str(exc)
            raise RuntimeError(self._last_error) from exc
        self._last_error = None
        return response

    def stop(self) -> dict[str, Any]:
        with self._stream_lock:
            self._pending_streams.clear()
        return {"status": "stopped", "provider": self.name}

    def health(self) -> ProviderHealth:
        if not self._api_key():
            return ProviderHealth(
                "tts",
                self.name,
                configured=True,
                active=False,
                available=False,
                detail="Deepgram API key is missing. Set DEEPGRAM_API_KEY.",
                fallback_to="browser_speech_synthesis",
            )
        detail = f"Aura-2 neural voice ready with model {self.model_name}."
        if self._last_error:
            detail = f"{detail} Last synthesis warning: {self._last_error}"
        return ProviderHealth("tts", self.name, configured=True, active=True, available=True, detail=detail)

    def _api_key(self) -> str:
        return self.api_key or get_secret("DEEPGRAM_API_KEY")

    def _build_request(self, text: str) -> urllib.request.Request:
        query = urllib.parse.urlencode(
            {
                "model": self.model_name,
                "encoding": "mp3",
                "bit_rate": "48000",
                "speed": f"{self.rate:.2f}",
            }
        )
        return urllib.request.Request(
            f"{self.endpoint}?{query}",
            data=json.dumps({"text": text}).encode("utf-8"),
            headers={
                "Authorization": f"Token {self._api_key()}",
                "Content-Type": "application/json",
            },
            method="POST",
        )

    def _queue_stream(self, text: str) -> str:
        now = time.monotonic()
        stream_id = uuid.uuid4().hex
        with self._stream_lock:
            self._discard_expired_streams(now)
            while len(self._pending_streams) >= self._max_pending_streams:
                oldest = next(iter(self._pending_streams))
                self._pending_streams.pop(oldest, None)
            self._pending_streams[stream_id] = (now, text)
        return stream_id

    def _take_stream(self, stream_id: str) -> str:
        now = time.monotonic()
        with self._stream_lock:
            self._discard_expired_streams(now)
            pending = self._pending_streams.pop(stream_id, None)
        if pending is None:
            raise KeyError("Unknown or expired speech stream.")
        return pending[1]

    def _discard_expired_streams(self, now: float) -> None:
        expired = [
            stream_id
            for stream_id, (created_at, _text) in self._pending_streams.items()
            if now - created_at > self._stream_ttl_seconds
        ]
        for stream_id in expired:
            self._pending_streams.pop(stream_id, None)


class PiperTTS:
    name = "piper"

    def __init__(self, model_path: Path | None, *, voice_path: Path | None = None, rate: float = 0.92, pitch: float = 0.72, volume: float = 0.95) -> None:
        self.model_path = model_path
        self.voice_path = voice_path
        self.rate = rate
        self.pitch = pitch
        self.volume = volume
        self.executable = shutil.which("piper")

    def speak(self, text: str, *, voice: str = "ULTRON") -> dict[str, Any]:
        if not text.strip():
            return {"status": "empty", "provider": self.name, "voice": voice}
        health = self.health()
        if not health.available or not self.executable or not self.model_path:
            return {"status": "unavailable", "provider": self.name, "voice": voice, "message": health.detail, "text": text}
        output = tempfile.NamedTemporaryFile(prefix="ultron-piper-", suffix=".wav", delete=False)
        output.close()
        command = [self.executable, "--model", str(self.model_path), "--output_file", output.name]
        if self.voice_path:
            command.extend(["--config", str(self.voice_path)])
        try:
            process = subprocess.run(command, input=text, check=False, capture_output=True, text=True, timeout=30)
        except Exception as exc:
            return {"status": "error", "provider": self.name, "voice": voice, "message": str(exc), "text": text}
        if process.returncode != 0:
            return {"status": "error", "provider": self.name, "voice": voice, "message": process.stderr.strip(), "text": text}
        return {"status": "audio_file", "provider": self.name, "voice": voice, "audio_path": output.name, "text": text}

    def stop(self) -> dict[str, Any]:
        return {"status": "stopped", "provider": self.name}

    def health(self) -> ProviderHealth:
        if not self.executable:
            return ProviderHealth("tts", self.name, configured=True, active=False, available=False, detail="Piper executable was not found on PATH.", fallback_to="browser_speech_synthesis")
        if self.model_path is None:
            return ProviderHealth("tts", self.name, configured=True, active=False, available=False, detail="No Piper model path is configured.", fallback_to="browser_speech_synthesis")
        if not self.model_path.exists():
            return ProviderHealth("tts", self.name, configured=True, active=False, available=False, detail=f"Model path not found: {self.model_path}", fallback_to="browser_speech_synthesis")
        if self.voice_path is not None and not self.voice_path.exists():
            return ProviderHealth("tts", self.name, configured=True, active=False, available=False, detail=f"Piper voice config not found: {self.voice_path}", fallback_to="browser_speech_synthesis")
        return ProviderHealth("tts", self.name, configured=True, active=True, available=True, detail="Piper is ready for local synthesis.")


class Pyttsx3TTS:
    name = "pyttsx3"

    def __init__(self, *, rate: float = 0.92, pitch: float = 0.72, volume: float = 0.95) -> None:
        self.rate = rate
        self.pitch = pitch
        self.volume = volume

    def speak(self, text: str, *, voice: str = "ULTRON") -> dict[str, Any]:
        if not text.strip():
            return {"status": "empty", "provider": self.name, "voice": voice}
        health = self.health()
        if not health.available:
            return {"status": "unavailable", "provider": self.name, "voice": voice, "message": health.detail, "text": text}
        try:
            import pyttsx3  # type: ignore[import-not-found]

            engine = pyttsx3.init()
            engine.setProperty("rate", max(80, min(260, int(185 * self.rate))))
            engine.setProperty("volume", max(0.0, min(1.0, self.volume)))
            engine.say(text)
            engine.runAndWait()
        except Exception as exc:
            return {"status": "error", "provider": self.name, "voice": voice, "message": str(exc), "text": text}
        return {"status": "spoken", "provider": self.name, "voice": voice, "text": text, "pitch": self.pitch}

    def stop(self) -> dict[str, Any]:
        return {"status": "stopped", "provider": self.name}

    def health(self) -> ProviderHealth:
        if importlib.util.find_spec("pyttsx3") is None:
            return ProviderHealth("tts", self.name, configured=True, active=False, available=False, detail="Python package pyttsx3 is not installed.", fallback_to="browser_speech_synthesis")
        return ProviderHealth("tts", self.name, configured=True, active=True, available=True, detail="pyttsx3 is importable for local speech synthesis.")


class MockTTS:
    name = "mock_tts"

    def __init__(self) -> None:
        self.spoken: list[str] = []
        self.stopped = False

    def speak(self, text: str, *, voice: str = "ULTRON") -> dict[str, Any]:
        self.spoken.append(text)
        return {"status": "spoken", "provider": self.name, "voice": voice, "text": text}

    def stop(self) -> dict[str, Any]:
        self.stopped = True
        return {"status": "stopped", "provider": self.name}

    def health(self) -> ProviderHealth:
        return ProviderHealth("tts", self.name, configured=True, active=True, available=True, detail="Deterministic mock TTS provider for tests.")


class BrowserMicrophoneCapture:
    name = "browser"

    def capture(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {
            "status": "delegated",
            "provider": self.name,
            "message": "Microphone capture is delegated to the browser client.",
            "transcript": payload.get("transcript") or payload.get("text") or "",
        }

    def health(self) -> ProviderHealth:
        return ProviderHealth("capture", self.name, configured=True, active=True, available=True, detail="Browser captures audio/transcripts.")


class MockMicrophoneCapture:
    name = "mock_capture"

    def __init__(self, transcript: str = "ULTRON, create note backend voice is working") -> None:
        self.transcript = transcript

    def capture(self, payload: dict[str, Any]) -> dict[str, Any]:
        transcript = str(payload.get("transcript") or payload.get("text") or self.transcript)
        return {
            "status": "ok",
            "provider": self.name,
            "transcript": transcript,
            "audio_duration_ms": int(payload.get("audio_duration_ms", 1200)),
            "speech_ms": int(payload.get("speech_ms", 850)),
            "audio_energy": float(payload.get("audio_energy", 0.22)),
            "message": "Mock microphone capture completed.",
        }

    def health(self) -> ProviderHealth:
        return ProviderHealth("capture", self.name, configured=True, active=True, available=True, detail="Deterministic mock microphone capture.")


class SoundDeviceMicrophoneCapture:
    name = "sounddevice"

    def __init__(self, *, sample_rate: int = 16000, default_seconds: float = 4.0, device: str | None = None) -> None:
        self.sample_rate = max(8000, min(48000, int(sample_rate)))
        self.default_seconds = max(0.25, min(15.0, float(default_seconds)))
        self.device = device

    def capture(self, payload: dict[str, Any]) -> dict[str, Any]:
        health = self.health()
        if not health.available:
            return {"status": "unavailable", "provider": self.name, "message": health.detail}
        seconds = max(0.25, min(15.0, float(payload.get("seconds", self.default_seconds))))
        frames = int(self.sample_rate * seconds)
        try:
            import sounddevice as sd  # type: ignore[import-not-found]

            audio = sd.rec(frames, samplerate=self.sample_rate, channels=1, dtype="int16", device=self.device)
            sd.wait()
        except Exception as exc:  # pragma: no cover - hardware dependent
            return {"status": "error", "provider": self.name, "message": f"Microphone capture failed: {exc}"}

        raw = audio.tobytes()
        energy = _pcm16_energy(raw)
        peak_times = _pcm16_peak_times(raw, self.sample_rate)
        speech_ms = int(seconds * 1000) if energy > 0.012 else 0
        if bool(payload.get("energy_only")):
            return {
                "status": "ok",
                "provider": self.name,
                "energy_only": True,
                "audio_duration_ms": int(seconds * 1000),
                "speech_ms": speech_ms,
                "audio_energy": energy,
                "audio_peak_times_s": peak_times,
                "sample_rate": self.sample_rate,
                "microphone": self.device or "default",
                "message": "Backend microphone energy capture completed.",
            }

        output = tempfile.NamedTemporaryFile(prefix="ultron-mic-", suffix=".wav", delete=False)
        output.close()
        path = Path(output.name)
        try:
            with wave.open(str(path), "wb") as handle:
                handle.setnchannels(1)
                handle.setsampwidth(2)
                handle.setframerate(self.sample_rate)
                handle.writeframes(raw)
        except Exception as exc:  # pragma: no cover - filesystem defensive
            return {"status": "error", "provider": self.name, "message": f"Could not save captured audio: {exc}"}

        return {
            "status": "ok",
            "provider": self.name,
            "audio_path": str(path),
            "temporary_audio": True,
            "audio_duration_ms": int(seconds * 1000),
            "speech_ms": speech_ms,
            "audio_energy": energy,
            "audio_peak_times_s": peak_times,
            "sample_rate": self.sample_rate,
            "microphone": self.device or "default",
            "message": "Backend microphone capture completed.",
        }

    def health(self) -> ProviderHealth:
        if importlib.util.find_spec("sounddevice") is None:
            return ProviderHealth("capture", self.name, configured=True, active=False, available=False, detail="Python package sounddevice is not installed.", fallback_to="browser")
        return ProviderHealth("capture", self.name, configured=True, active=True, available=True, detail=f"Ready at {self.sample_rate} Hz.")


class VoiceSession:
    def __init__(
        self,
        stt: STTProvider | None = None,
        tts: TTSProvider | None = None,
        *,
        configured_stt: STTProvider | None = None,
        configured_tts: TTSProvider | None = None,
        wake: WakeWordProvider | None = None,
        vad: VADProvider | None = None,
        configured_wake: WakeWordProvider | None = None,
        configured_vad: VADProvider | None = None,
        capture: MicrophoneCaptureProvider | None = None,
        configured_capture: MicrophoneCaptureProvider | None = None,
        provider_config: VoiceProviderConfig | None = None,
        wake_config: WakeGateConfig | None = None,
        history_limit: int = 20,
    ):
        self.provider_config = provider_config or VoiceProviderConfig()
        self.wake_config = wake_config or WakeGateConfig()
        self.stt = stt or TextPayloadSTT()
        self.tts = tts or BrowserSpeechTTS()
        self.wake = wake or TextWakeWordProvider(self.wake_config.wake_phrases)
        self.vad = vad or EnergyVADProvider(self.wake_config.vad_energy_threshold)
        self.configured_stt = configured_stt or self.stt
        self.configured_tts = configured_tts or self.tts
        self.configured_wake = configured_wake or self.wake
        self.configured_vad = configured_vad or self.vad
        self.capture = capture or BrowserMicrophoneCapture()
        self.configured_capture = configured_capture or self.capture
        self.status = VoiceStatus(
            stt_provider=self.stt.name,
            tts_provider=self.tts.name,
            configured_stt_provider=self.configured_stt.name,
            configured_tts_provider=self.configured_tts.name,
            voice_identity=self.provider_config.voice_identity,
            voice_preference=self.provider_config.voice_preference,
            voice_rate=self.provider_config.rate,
            voice_pitch=self.provider_config.pitch,
            voice_volume=self.provider_config.volume,
        )
        self.wake_status = WakeStatus(
            wake_provider=self.wake.name,
            vad_provider=self.vad.name,
            wake_phrases=self.wake_config.wake_phrases or DEFAULT_WAKE_PHRASES,
        )
        self.history: list[TranscriptRecord] = []
        self.history_limit = history_limit
        self.diagnostics = AudioDiagnostics(
            active_microphone=self.provider_config.microphone_device or "browser",
            capture_provider=self.capture.name,
            stt_provider=self.stt.name,
            stt_model_path=str(self.provider_config.stt_model_path) if self.provider_config.stt_model_path else None,
        )

    def start(self, *, push_to_talk: bool | None = None) -> dict[str, Any]:
        if push_to_talk is not None:
            self.status.push_to_talk = bool(push_to_talk)
        self.status.microphone_enabled = True
        self.status.listening = True
        self.status.last_error = None
        return self.snapshot({"status": "ok"})

    def stop(self) -> dict[str, Any]:
        self.status.microphone_enabled = False
        self.status.listening = False
        if self.wake_status.always_listening:
            self.stop_wake()
        return self.snapshot({"status": "ok"})

    def cancel_confirmation(self) -> dict[str, Any]:
        self.status.pending_confirmation_goal = None
        return self.snapshot({"status": "ok", "message": "Pending confirmation cancelled."})

    def set_muted(self, muted: bool) -> dict[str, Any]:
        self.status.muted = bool(muted)
        if muted:
            self.status.speaking = False
        return self.snapshot({"status": "ok"})

    def transcribe_and_run(self, payload: dict[str, Any], command_runner) -> dict[str, Any]:
        self.status.listening = False
        self.wake_status.mode = "transcribing" if self.wake_status.always_listening else self.wake_status.mode
        audio = analyze_audio_payload(payload)
        if audio["rejected"] and not (payload.get("transcript") or payload.get("text")):
            self.status.last_error = str(audio["reason"])
            self._update_diagnostics(payload, None, status="rejected", detail=self.status.last_error, audio=audio)
            _cleanup_temporary_audio(payload)
            return self.snapshot({"status": "empty", "message": self.status.last_error, "audio": audio, "voice_diagnostics": self.diagnostics.to_dict()})
        try:
            result = self.stt.transcribe(payload)
        finally:
            _cleanup_temporary_audio(payload)
        if bool(payload.get("command_capture")):
            command_text = strip_wake_greeting(result.text)
            if command_text != result.text:
                result = STTResult(
                    text=command_text,
                    confidence=result.confidence,
                    provider=result.provider,
                    empty=not bool(command_text),
                )
        self._update_diagnostics(payload, result, status="transcribed", detail="Transcript received.", audio=audio)
        if result.empty or (not result.text.strip() and _looks_like_empty_audio(payload)):
            self.status.last_error = "No speech was detected."
            self._update_diagnostics(payload, result, status="empty", detail=self.status.last_error, audio=audio)
            return self.snapshot({"status": "empty", "transcript": result.to_dict(), "audio": audio, "message": self.status.last_error, "voice_diagnostics": self.diagnostics.to_dict()})

        confirmed = False
        goal = result.text
        normalized = normalize_confirmation(result.text)
        if normalized in CONFIRMATION_PHRASES and self.status.pending_confirmation_goal:
            confirmed = True
            goal = self.status.pending_confirmation_goal

        if not confirmed and _needs_clarification(result):
            spoken_response = clarification_response(result.text)
            record = TranscriptRecord(
                transcript_id=str(uuid.uuid4()),
                user_said=str(payload.get("transcript") or payload.get("text") or result.text),
                ultron_understood=result.text,
                tool_selected=None,
                action_result="clarification_required",
                spoken_response=spoken_response,
                needs_confirmation=False,
            )
            self._remember(record)
            self.status.last_error = "Transcript confidence was too low."
            self.status.speaking = not self.status.muted
            if self.wake_status.always_listening:
                self.wake_status.mode = "listening"
                self.status.listening = True
            self._update_diagnostics(payload, result, status="clarification_required", detail=self.status.last_error, audio=audio)
            return self.snapshot(
                {
                    "status": "clarification_required",
                    "transcript": result.to_dict(),
                    "audio": audio,
                    "spoken_response": spoken_response,
                    "needs_confirmation": False,
                    "continue_listening": True,
                    "record": record.to_dict(),
                    "voice_diagnostics": self.diagnostics.to_dict(),
                }
            )

        command_payload = command_runner(goal, confirmed=confirmed)
        task = command_payload.get("task") if isinstance(command_payload, dict) else None
        spoken_response = response_for_task(task, command_payload.get("subtitle") if isinstance(command_payload, dict) else None)
        needs_confirmation = bool(task and task.get("status") == "waiting_for_confirmation")
        continue_listening = first_tool(task) == "assistant_reply" and not needs_confirmation
        if needs_confirmation:
            self.status.pending_confirmation_goal = goal
            spoken_response = "I need explicit confirmation before doing that. Say yes confirm or click Confirm."
        else:
            self.status.pending_confirmation_goal = None

        record = TranscriptRecord(
            transcript_id=str(uuid.uuid4()),
            user_said=str(payload.get("transcript") or payload.get("text") or result.text),
            ultron_understood=goal,
            tool_selected=first_tool(task),
            action_result=first_result(task),
            spoken_response=spoken_response,
            needs_confirmation=needs_confirmation,
        )
        self._remember(record)
        self.status.speaking = not self.status.muted
        if self.wake_status.always_listening:
            if continue_listening:
                self.wake_status.mode = "listening"
                self.status.listening = True
            else:
                self.wake_status.mode = "speaking" if self.status.speaking else "waiting_for_wake_word"
        self.status.last_error = None
        return self.snapshot(
            {
                "status": "ok",
                "transcript": result.to_dict(),
                "audio": audio,
                "confirmed": confirmed,
                "task": task,
                "ui_directive": command_payload.get("ui_directive") if isinstance(command_payload, dict) else None,
                "spoken_response": spoken_response,
                "needs_confirmation": needs_confirmation,
                "continue_listening": continue_listening,
                "record": record.to_dict(),
                "voice_diagnostics": self.diagnostics.to_dict(),
            }
        )

    def capture_and_run(self, payload: dict[str, Any], command_runner) -> dict[str, Any]:
        self.status.microphone_enabled = True
        self.status.listening = True
        capture_payload = self.capture.capture(payload)
        if capture_payload.get("status") not in {"ok", "delegated"}:
            self.status.last_error = str(capture_payload.get("message", "Microphone capture is unavailable."))
            self._update_diagnostics(capture_payload, None, status=str(capture_payload.get("status", "unavailable")), detail=self.status.last_error)
            return self.snapshot({"status": "capture_unavailable", "capture": capture_payload, "message": self.status.last_error, "voice_diagnostics": self.diagnostics.to_dict()})
        merged = {**payload, **capture_payload}
        result = self.transcribe_and_run(merged, command_runner)
        if not self.wake_status.always_listening:
            self.status.microphone_enabled = False
            self.status.listening = False
            result["voice"] = self.status.to_dict()
        return result

    def calibrate_microphone(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = payload or {}
        seconds = max(1.0, min(6.0, float(payload.get("seconds", 2.5))))
        capture_payload = self.capture.capture({**payload, "seconds": seconds})
        if capture_payload.get("status") not in {"ok", "delegated"}:
            detail = str(capture_payload.get("message", "Microphone capture is unavailable."))
            self._update_diagnostics(capture_payload, None, status=str(capture_payload.get("status", "unavailable")), detail=detail)
            return self.snapshot({"status": "capture_unavailable", "capture": capture_payload, "message": detail, "voice_diagnostics": self.diagnostics.to_dict()})

        audio = analyze_audio_payload(capture_payload)
        energy = float(audio.get("audio_energy", 0.0))
        suggested_threshold = max(0.006, min(0.045, energy * 0.45 if energy else self.wake_config.vad_energy_threshold))
        if isinstance(self.vad, EnergyVADProvider):
            self.vad.threshold = suggested_threshold
        detail = (
            f"Calibration captured {audio.get('audio_duration_ms', 0)} ms. "
            f"Energy {energy:.3f}; VAD threshold now {suggested_threshold:.3f}."
        )
        self._update_diagnostics(capture_payload, None, status="calibrated", detail=detail, audio=audio)
        return self.snapshot(
            {
                "status": "ok",
                "capture": capture_payload,
                "audio": audio,
                "suggested_vad_energy_threshold": round(suggested_threshold, 6),
                "message": detail,
                "voice_diagnostics": self.diagnostics.to_dict(),
                **self.gate_status(),
            }
        )

    def speak(self, text: str) -> dict[str, Any]:
        if self.status.muted:
            self.status.speaking = False
            return self.snapshot({"status": "muted", "message": "Voice output is muted.", "text": text})
        payload = self.tts.speak(text, voice=self.provider_config.voice_identity)
        self.status.speaking = payload.get("status") not in {"empty", "error", "unavailable"}
        return self.snapshot({"status": "ok", "speech": payload})

    def open_tts_stream(self, stream_id: str) -> Any:
        open_stream = getattr(self.tts, "open_audio_stream", None)
        if not callable(open_stream):
            raise KeyError("The active voice provider does not expose audio streams.")
        return open_stream(stream_id)

    def stop_speaking(self) -> dict[str, Any]:
        payload = self.tts.stop()
        self.status.speaking = False
        if self.wake_status.always_listening:
            self.wake_status.mode = "waiting_for_wake_word"
        return self.snapshot({"status": "ok", "speech": payload})

    def start_wake(self) -> dict[str, Any]:
        if hasattr(self.wake, "reset"):
            self.wake.reset()
        self.wake_status.always_listening = True
        self.wake_status.mode = "waiting_for_wake_word"
        self.wake_status.wake_word_detected = False
        self.wake_status.voice_detected = False
        self.wake_status.noisy_ignored = False
        self.wake_status.last_wake_phrase = None
        self.wake_status.last_event = (
            "Voice standby. Double clap to wake me."
            if self.wake.name == "double_clap"
            else "Always-listening mode is waiting for ULTRON."
        )
        self.status.microphone_enabled = True
        self.status.listening = False
        self.status.push_to_talk = False
        self.status.last_error = None
        return self.snapshot({"status": "ok"})

    def stop_wake(self) -> dict[str, Any]:
        self.wake_status.always_listening = False
        self.wake_status.mode = "inactive"
        self.wake_status.wake_word_detected = False
        self.wake_status.voice_detected = False
        self.wake_status.noisy_ignored = False
        self.wake_status.last_event = "Always-listening mode stopped."
        self.status.microphone_enabled = False
        self.status.listening = False
        return self.snapshot({"status": "ok"})

    def wake_snapshot(self) -> dict[str, Any]:
        return self.snapshot({"status": "ok", **self.gate_status()})

    def cleanup_capture(self, payload: dict[str, Any]) -> None:
        _cleanup_temporary_audio(payload)

    def process_wake_input(self, payload: dict[str, Any], command_runner) -> dict[str, Any]:
        if not self.wake_status.always_listening:
            self.wake_status.mode = "inactive"
            self.wake_status.last_event = "Always-listening mode is off."
            return self.snapshot({"status": "inactive", "message": self.wake_status.last_event, **self.gate_status()})

        already_listening = self.wake_status.mode == "listening"
        authorized_command_audio = bool(
            already_listening
            and payload.get("command_capture")
            and _payload_audio_path(payload) is not None
        )
        early_wake_result = self.wake.detect(payload) if self.wake.name == "double_clap" and not already_listening else None
        vad_result = self.vad.detect(payload)
        self.wake_status.voice_detected = bool(vad_result.speech)
        self.wake_status.noisy_ignored = bool(vad_result.noisy or not vad_result.speech)
        if bool(payload.get("energy_only")) and self.diagnostics.status in {"idle", "wake_monitoring"}:
            self._update_diagnostics(
                payload,
                None,
                status="wake_monitoring",
                detail="Clap standby energy sample processed without speech-to-text.",
            )
        if not vad_result.speech and not authorized_command_audio:
            if self.wake_status.mode == "listening":
                if bool(payload.get("command_capture")):
                    self.wake_status.mode = "waiting_for_wake_word"
                    self.wake_status.wake_word_detected = False
                    self.wake_status.last_wake_phrase = None
                    self.wake_status.last_event = "I did not hear a command. Double clap when you are ready, sir."
                    self.status.listening = False
                    return self.snapshot(
                        {
                            "status": "no_command",
                            "message": self.wake_status.last_event,
                            "vad": vad_result.to_dict(),
                            "command_executed": False,
                            **self.gate_status(),
                        }
                    )
                self.wake_status.wake_word_detected = True
                self.wake_status.last_event = "Listening for a command, sir."
                self.status.listening = True
                return self.snapshot(
                    {
                        "status": "ignored",
                        "message": self.wake_status.last_event,
                        "vad": vad_result.to_dict(),
                        "command_executed": False,
                        **self.gate_status(),
                    }
                )
            if early_wake_result is not None and early_wake_result.detected:
                self.wake_status.mode = "listening"
                self.wake_status.wake_word_detected = True
                self.wake_status.noisy_ignored = False
                self.wake_status.last_wake_phrase = early_wake_result.phrase
                self.wake_status.last_event = "Double clap detected. At your service, sir."
                self.status.listening = True
                return self.snapshot(
                    {
                        "status": "wake_detected",
                        "message": self.wake_status.last_event,
                        "spoken_response": WAKE_GREETING,
                        "listen_after_greeting": True,
                        "wake_detection": early_wake_result.to_dict(),
                        "vad": vad_result.to_dict(),
                        "command_executed": False,
                        **self.gate_status(),
                    }
                )
            self.wake_status.mode = "waiting_for_wake_word"
            self.wake_status.wake_word_detected = False
            self.wake_status.last_wake_phrase = None
            self.wake_status.last_event = vad_result.reason
            return self.snapshot(
                {
                    "status": "ignored",
                    "message": vad_result.reason,
                    "vad": vad_result.to_dict(),
                    "command_executed": False,
                    **self.gate_status(),
                }
            )

        wake_result = early_wake_result or (
            WakeWordResult(False, provider=self.wake.name)
            if already_listening
            else self.wake.detect(payload)
        )
        raw_text = str(payload.get("transcript") or payload.get("text") or "").strip()
        if self.wake_status.mode != "listening" and not wake_result.detected:
            self.wake_status.wake_word_detected = False
            self.wake_status.last_wake_phrase = None
            self.wake_status.last_event = "Speech detected, but wake word was not detected."
            return self.snapshot(
                {
                    "status": "ignored",
                    "message": self.wake_status.last_event,
                    "wake_detection": wake_result.to_dict(),
                    "vad": vad_result.to_dict(),
                    "command_executed": False,
                    **self.gate_status(),
                }
            )

        authorized_text = raw_text
        if wake_result.detected:
            self.wake_status.wake_word_detected = True
            self.wake_status.last_wake_phrase = wake_result.phrase
            authorized_text = strip_wake_phrase(raw_text, self.wake_status.wake_phrases)
            if not authorized_text:
                self.wake_status.mode = "listening"
                self.wake_status.last_event = "Wake detected. At your service, sir."
                self.status.listening = True
                return self.snapshot(
                    {
                        "status": "wake_detected",
                        "message": self.wake_status.last_event,
                        "spoken_response": WAKE_GREETING,
                        "listen_after_greeting": True,
                        "wake_detection": wake_result.to_dict(),
                        "vad": vad_result.to_dict(),
                        "command_executed": False,
                        **self.gate_status(),
                    }
                )

        self.wake_status.mode = "thinking"
        self.wake_status.last_event = "Wake gate authorized a speech segment."
        command_payload = dict(payload)
        command_payload["transcript"] = authorized_text
        command_payload["wake_authorized"] = True
        voice_payload = self.transcribe_and_run(command_payload, command_runner)
        if voice_payload.get("status") == "empty":
            command_capture = bool(payload.get("command_capture"))
            self.wake_status.mode = "waiting_for_wake_word" if command_capture else "listening"
            self.wake_status.noisy_ignored = True
            self.wake_status.wake_word_detected = not command_capture
            self.wake_status.last_wake_phrase = None if command_capture else self.wake_status.last_wake_phrase
            self.status.listening = not command_capture
            if command_capture:
                self.status.speaking = False
                self.wake_status.last_event = "I did not hear a command. Double clap when you are ready, sir."
                voice_payload["status"] = "no_command"
                voice_payload["message"] = self.wake_status.last_event
                voice_payload["voice"] = self.status.to_dict()
            else:
                self.wake_status.last_event = str(voice_payload.get("message", "No speech was detected."))
            return self.snapshot(
                {
                    **voice_payload,
                    "wake_detection": wake_result.to_dict(),
                    "vad": vad_result.to_dict(),
                    "command_executed": False,
                    **self.gate_status(),
                }
            )
        return self.snapshot(
            {
                **voice_payload,
                "wake_detection": wake_result.to_dict(),
                "vad": vad_result.to_dict(),
                "command_executed": True,
                **self.gate_status(),
            }
        )

    def providers_status(self) -> dict[str, Any]:
        stt_configured = _health(self.configured_stt, kind="stt", configured=True, active=self.configured_stt.name == self.stt.name)
        tts_configured = _health(self.configured_tts, kind="tts", configured=True, active=self.configured_tts.name == self.tts.name)
        capture_configured = _health(self.configured_capture, kind="capture", configured=True, active=self.configured_capture.name == self.capture.name)
        stt_active = _health(self.stt, kind="stt", configured=self.configured_stt.name == self.stt.name, active=True)
        tts_active = _health(self.tts, kind="tts", configured=self.configured_tts.name == self.tts.name, active=True)
        capture_active = _health(self.capture, kind="capture", configured=self.configured_capture.name == self.capture.name, active=True)
        if self.configured_stt.name != self.stt.name:
            stt_configured.fallback_to = self.stt.name
        if self.configured_tts.name != self.tts.name:
            tts_configured.fallback_to = self.tts.name
        if self.configured_capture.name != self.capture.name:
            capture_configured.fallback_to = self.capture.name
        return {
            "configured": {"stt": self.configured_stt.name, "tts": self.configured_tts.name, "capture": self.configured_capture.name},
            "active": {"stt": self.stt.name, "tts": self.tts.name, "capture": self.capture.name},
            "providers": {
                "stt": stt_configured.to_dict(),
                "tts": tts_configured.to_dict(),
                "capture": capture_configured.to_dict(),
                "active_stt": stt_active.to_dict(),
                "active_tts": tts_active.to_dict(),
                "active_capture": capture_active.to_dict(),
            },
            "voice_identity": self.provider_config.voice_identity,
            "speech_settings": {
                "voice_preference": self.provider_config.voice_preference,
                "rate": self.provider_config.rate,
                "pitch": self.provider_config.pitch,
                "volume": self.provider_config.volume,
                "device": self.provider_config.device,
                "microphone": self.provider_config.microphone_device or "default",
                "sample_rate": self.provider_config.sample_rate,
                "capture_seconds": self.provider_config.capture_seconds,
            },
            "voice_diagnostics": self.diagnostics.to_dict(),
        }

    def gate_status(self) -> dict[str, Any]:
        return {
            "wake": self.wake_status.to_dict(),
            "gate_providers": gate_providers_status(self.configured_wake, self.wake, self.configured_vad, self.vad),
        }

    def test_stt(self, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        test_payload = {"transcript": "ULTRON, create note provider test"} if payload is None else payload
        result = self.stt.transcribe(test_payload)
        return self.snapshot({"status": "ok" if not result.empty else "empty", "transcript": result.to_dict(), **self.providers_status()})

    def test_tts(self, text: str = "ULTRON voice provider test.") -> dict[str, Any]:
        if self.status.muted:
            return self.snapshot({"status": "muted", "message": "Voice output is muted.", **self.providers_status()})
        speech = self.tts.speak(text, voice=self.provider_config.voice_identity)
        provider_status = self.providers_status()
        return self.snapshot({"status": "ok", **provider_status, "speech": speech})

    def snapshot(self, extra: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "voice": self.status.to_dict(),
            "wake": self.wake_status.to_dict(),
            "voice_diagnostics": self.diagnostics.to_dict(),
            "history": [item.to_dict() for item in self.history],
        }
        if extra:
            payload.update(extra)
        return payload

    def _remember(self, record: TranscriptRecord) -> None:
        self.history.append(record)
        if len(self.history) > self.history_limit:
            self.history = self.history[-self.history_limit :]

    def _update_diagnostics(
        self,
        payload: dict[str, Any],
        result: STTResult | None,
        *,
        status: str,
        detail: str,
        audio: dict[str, Any] | None = None,
    ) -> None:
        audio = audio or analyze_audio_payload(payload)
        self.diagnostics = AudioDiagnostics(
            active_microphone=str(payload.get("microphone") or self.provider_config.microphone_device or "browser/default"),
            capture_provider=self.capture.name,
            stt_provider=self.stt.name,
            stt_model_path=str(self.provider_config.stt_model_path) if self.provider_config.stt_model_path else None,
            last_transcript=result.text if result else "",
            confidence=result.confidence if result else 0.0,
            audio_duration_ms=int(audio.get("audio_duration_ms", 0)),
            speech_duration_ms=int(audio.get("speech_ms", 0)),
            audio_energy=float(audio.get("audio_energy", 0.0)),
            rejected=bool(audio.get("rejected", False)),
            noisy=bool(audio.get("noisy", False)),
            status=status,
            detail=detail,
        )


def build_voice_session(config: Any | None = None) -> VoiceSession:
    provider_config = VoiceProviderConfig.from_config(config) if config is not None else VoiceProviderConfig()
    wake_config = WakeGateConfig.from_config(config) if config is not None else WakeGateConfig()
    requested_stt = _create_stt_provider(provider_config)
    requested_tts = _create_tts_provider(provider_config)
    requested_capture = _create_capture_provider(provider_config)
    configured_wake, wake = build_wake_provider(wake_config)
    configured_vad, vad = build_vad_provider(wake_config)
    stt = requested_stt if _health(requested_stt, kind="stt", configured=True, active=False).available else BrowserTranscriptSTT()
    tts = requested_tts if _health(requested_tts, kind="tts", configured=True, active=False).available else BrowserSpeechTTS()
    capture = requested_capture if _health(requested_capture, kind="capture", configured=True, active=False).available else BrowserMicrophoneCapture()
    session = VoiceSession(
        stt=stt,
        tts=tts,
        capture=capture,
        configured_stt=requested_stt,
        configured_tts=requested_tts,
        configured_capture=requested_capture,
        wake=wake,
        vad=vad,
        configured_wake=configured_wake,
        configured_vad=configured_vad,
        provider_config=provider_config,
        wake_config=wake_config,
    )
    if config is not None and bool(getattr(config, "wake_auto_start", False)):
        session.start_wake()
    return session


def clean_transcript(text: str, *, keyterms: Iterable[str] = ()) -> str:
    value = strip_wake_word(text)
    value = re.sub(r"\b(?:uh+|um+|erm|hmm)\b[\s,.-]*", "", value, flags=re.IGNORECASE)
    value = re.sub(r"^(?:please\s+|can\s+you\s+|could\s+you\s+)", "", value, flags=re.IGNORECASE)
    value = re.sub(
        r"^(?:bye|by)\s+(?=(?:play|open|launch|start|bring|search|create|write|type|jot|set)\b)",
        "",
        value,
        flags=re.IGNORECASE,
    )
    value = _dedupe_repeated_words(value)
    value = re.sub(r"\s+", " ", value).strip(" .!?\"'")
    value = _restore_keyterms(value, keyterms)
    return value


def _restore_keyterms(text: str, keyterms: Iterable[str]) -> str:
    value = re.sub(r"\bwhats\s+app\b", "WhatsApp", text, flags=re.IGNORECASE)
    value = re.sub(r"\byou\s+tube\b", "YouTube", value, flags=re.IGNORECASE)
    words = value.split()
    for term in sorted(_dedupe_keyterms(keyterms), key=lambda item: len(item.split()), reverse=True):
        canonical_words = term.split()
        width = len(canonical_words)
        target = " ".join(_speech_token(word) for word in canonical_words)
        if not target:
            continue
        threshold = 0.80 if width > 1 else 0.86
        index = 0
        while index + width <= len(words):
            candidate = " ".join(_speech_token(word) for word in words[index : index + width])
            if candidate and SequenceMatcher(None, candidate, target).ratio() >= threshold:
                trailing = re.search(r"([^\w]+)$", words[index + width - 1], flags=re.UNICODE)
                replacement = list(canonical_words)
                if trailing:
                    replacement[-1] = f"{replacement[-1]}{trailing.group(1)}"
                words[index : index + width] = replacement
                index += width
            else:
                index += 1
    return " ".join(words)


def _speech_token(value: str) -> str:
    return re.sub(r"[^\w]+", "", value.casefold(), flags=re.UNICODE)


def strip_wake_word(text: str) -> str:
    value = " ".join(text.strip().split())
    value = re.sub(r"^(?:hey\s+)?ultron\b[\s,.:;-]+(?=\S)", "", value, flags=re.IGNORECASE)
    return value.strip()


def strip_wake_greeting(text: str) -> str:
    value = " ".join(text.strip().split())
    value = re.sub(
        r"^(?:at\s+your\s+service(?:\s*,?\s*sir)?|your\s+service\s*,?\s*sir|service\s*,?\s*sir)\b[\s,.:;-]*",
        "",
        value,
        flags=re.IGNORECASE,
    )
    return value.strip()


def normalize_confirmation(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip().lower())


def _payload_confidence(payload: dict[str, Any], *, default: float) -> float:
    raw = payload.get("confidence")
    try:
        confidence = float(raw)
    except (TypeError, ValueError):
        return max(0.0, min(1.0, default))
    return max(0.0, min(1.0, confidence))


def _looks_like_empty_audio(payload: dict[str, Any]) -> bool:
    if payload.get("transcript") or payload.get("text"):
        return False
    speech_ms = payload.get("speech_ms")
    try:
        if speech_ms is not None and float(speech_ms) < MIN_SPEECH_MS:
            return True
    except (TypeError, ValueError):
        pass
    audio_energy = payload.get("audio_energy")
    try:
        if audio_energy is not None and float(audio_energy) <= 0.01:
            return True
    except (TypeError, ValueError):
        pass
    return False


def analyze_audio_payload(payload: dict[str, Any]) -> dict[str, Any]:
    duration_ms = _int_payload(payload, "audio_duration_ms", fallback=_duration_from_seconds(payload))
    speech_ms = _int_payload(payload, "speech_ms", fallback=duration_ms if payload.get("transcript") or payload.get("text") else 0)
    energy = _float_payload(payload, "audio_energy", fallback=0.0)
    noisy = bool(payload.get("noisy", False))
    rejected = False
    reason = ""
    if not (payload.get("transcript") or payload.get("text") or payload.get("audio_path")):
        if duration_ms and duration_ms < MIN_SPEECH_MS:
            rejected = True
            reason = "Audio was too short to transcribe."
        elif speech_ms and speech_ms < MIN_SPEECH_MS:
            rejected = True
            reason = "Speech segment was too short."
        elif energy and energy <= 0.01:
            rejected = True
            reason = "Audio energy was too low."
    if noisy:
        rejected = True
        reason = reason or "Audio was marked as noisy."
    return {
        "audio_duration_ms": duration_ms,
        "speech_ms": speech_ms,
        "audio_energy": round(energy, 6),
        "noisy": noisy,
        "rejected": rejected,
        "reason": reason,
    }


def _needs_clarification(result: STTResult) -> bool:
    if normalize_confirmation(result.text) in CONFIRMATION_PHRASES:
        return False
    if result.confidence < LOW_CONFIDENCE_THRESHOLD:
        return True
    words = result.text.split()
    if len(words) == 1 and result.confidence < 0.72 and words[0].lower() not in {"hi", "hello", "thanks", "help"}:
        return True
    return False


def clarification_response(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in ("spotify", "song", "music", "play")):
        return "I did not catch that music request clearly. Say the song or playlist once more, or type it and I will take it from there."
    if any(word in lowered for word in ("delete", "remove", "close", "clear")):
        return "I am not fully sure about that request, and it may affect something important. Please repeat it clearly or type it once."
    return "I did not catch that clearly enough. Please say it once more, or type it so I can handle the right task."


def response_for_task(task: dict[str, Any] | None, fallback: str | None = None) -> str:
    if not task:
        return fallback or "I could not process that command."
    if task.get("summary"):
        return str(task["summary"])
    status = task.get("status", "updated")
    return f"Task {status}."


def first_tool(task: dict[str, Any] | None) -> str | None:
    if not task:
        return None
    steps = task.get("steps")
    if not isinstance(steps, list) or not steps:
        return None
    tool = steps[0].get("tool_call") if isinstance(steps[0], dict) else None
    return tool.get("name") if isinstance(tool, dict) else None


def first_result(task: dict[str, Any] | None) -> str | None:
    if not task:
        return None
    steps = task.get("steps")
    if not isinstance(steps, list) or not steps:
        return None
    result = steps[-1].get("result") if isinstance(steps[-1], dict) else None
    if not isinstance(result, dict):
        return None
    status = result.get("status")
    message = result.get("message")
    if status and message:
        return f"{status}: {message}"
    return str(status or message or "")


def _create_stt_provider(config: VoiceProviderConfig) -> STTProvider:
    provider = config.stt_provider
    if provider == "faster_whisper":
        return FasterWhisperSTT(config.stt_model_path, model_name=config.stt_model, device=config.device)
    if provider == "whisper_cpp":
        return WhisperCppSTT(config.stt_model_path, device=config.device)
    if provider == "deepgram":
        return DeepgramSTT(model_name=config.stt_model, language=config.stt_language, keyterms=config.stt_keyterms)
    if provider == "browser":
        return BrowserTranscriptSTT()
    if provider == "mock":
        return MockSTT()
    return TextPayloadSTT()


def _create_tts_provider(config: VoiceProviderConfig) -> TTSProvider:
    provider = "browser_speech_synthesis" if config.tts_provider == "browser" else config.tts_provider
    if provider == "deepgram":
        return DeepgramTTS(model_name=config.tts_model, rate=config.rate)
    if provider == "piper":
        return PiperTTS(
            config.tts_model_path,
            voice_path=config.tts_voice_path,
            rate=config.rate,
            pitch=config.pitch,
            volume=config.volume,
        )
    if provider == "pyttsx3":
        return Pyttsx3TTS(rate=config.rate, pitch=config.pitch, volume=config.volume)
    if provider == "mock":
        return MockTTS()
    return BrowserSpeechTTS()


def _create_capture_provider(config: VoiceProviderConfig) -> MicrophoneCaptureProvider:
    provider = "browser" if config.capture_provider in {"", "browser"} else config.capture_provider
    if provider == "sounddevice":
        return SoundDeviceMicrophoneCapture(
            sample_rate=config.sample_rate,
            default_seconds=config.capture_seconds,
            device=config.microphone_device,
        )
    if provider == "mock":
        return MockMicrophoneCapture()
    return BrowserMicrophoneCapture()


def _health(provider: Any, *, kind: str, configured: bool, active: bool) -> ProviderHealth:
    if hasattr(provider, "health"):
        health = provider.health()
        health.configured = configured
        health.active = active
        return health
    return ProviderHealth(kind, getattr(provider, "name", "unknown"), configured=configured, active=active, available=True, detail="Provider does not expose a detailed health check.")


def _payload_audio_path(payload: dict[str, Any]) -> Path | None:
    raw = payload.get("audio_path")
    if not raw:
        return None
    path = Path(str(raw)).expanduser()
    return path if path.exists() and path.is_file() else None


def _cleanup_temporary_audio(payload: dict[str, Any]) -> None:
    if not bool(payload.get("temporary_audio")):
        return
    raw = payload.get("audio_path")
    if not raw:
        return
    try:
        Path(str(raw)).expanduser().unlink(missing_ok=True)
    except OSError:
        pass


def _audio_content_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix == ".wav":
        return "audio/wav"
    if suffix == ".mp3":
        return "audio/mpeg"
    if suffix == ".m4a":
        return "audio/mp4"
    if suffix == ".ogg":
        return "audio/ogg"
    if suffix == ".webm":
        return "audio/webm"
    return "application/octet-stream"


def _deepgram_transcript(payload: dict[str, Any]) -> tuple[str, float]:
    channels = (((payload.get("results") or {}).get("channels")) if isinstance(payload.get("results"), dict) else None)
    if not isinstance(channels, list) or not channels:
        return "", 0.0
    alternatives = channels[0].get("alternatives") if isinstance(channels[0], dict) else None
    if not isinstance(alternatives, list) or not alternatives:
        return "", 0.0
    transcript = alternatives[0].get("transcript") if isinstance(alternatives[0], dict) else ""
    confidence = alternatives[0].get("confidence", 1.0) if isinstance(alternatives[0], dict) else 0.0
    if not isinstance(transcript, str):
        transcript = ""
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        confidence = 1.0 if transcript else 0.0
    return transcript, max(0.0, min(1.0, float(confidence)))


def _duration_from_seconds(payload: dict[str, Any]) -> int:
    try:
        return int(float(payload.get("duration_seconds", 0)) * 1000)
    except (TypeError, ValueError):
        return 0


def _int_payload(payload: dict[str, Any], key: str, *, fallback: int = 0) -> int:
    try:
        return max(0, int(float(payload.get(key, fallback) or 0)))
    except (TypeError, ValueError):
        return fallback


def _float_payload(payload: dict[str, Any], key: str, *, fallback: float = 0.0) -> float:
    try:
        return max(0.0, float(payload.get(key, fallback) or 0.0))
    except (TypeError, ValueError):
        return fallback


def _dedupe_repeated_words(value: str) -> str:
    words = value.split()
    kept: list[str] = []
    for word in words:
        if kept and kept[-1].lower().strip(".,!?") == word.lower().strip(".,!?"):
            continue
        kept.append(word)
    return " ".join(kept)


def _pcm16_energy(raw: bytes) -> float:
    if not raw:
        return 0.0
    sample_count = len(raw) // 2
    if sample_count <= 0:
        return 0.0
    total = 0.0
    for index in range(0, len(raw) - 1, 2):
        sample = int.from_bytes(raw[index : index + 2], byteorder="little", signed=True)
        total += (sample / 32768.0) ** 2
    return min(1.0, (total / sample_count) ** 0.5)


def _pcm16_peak_times(raw: bytes, sample_rate: int) -> list[float]:
    if not raw or sample_rate <= 0:
        return []
    sample_count = len(raw) // 2
    if sample_count <= 0:
        return []
    window = max(1, int(sample_rate * 0.018))
    hop = max(1, int(sample_rate * 0.012))
    rms_values: list[tuple[int, float]] = []
    for start in range(0, sample_count - window + 1, hop):
        total = 0.0
        for index in range(start, start + window):
            byte_index = index * 2
            sample = int.from_bytes(raw[byte_index : byte_index + 2], byteorder="little", signed=True)
            total += (sample / 32768.0) ** 2
        rms_values.append((start, (total / window) ** 0.5))
    if not rms_values:
        return []
    baseline = sorted(value for _start, value in rms_values)[len(rms_values) // 2]
    threshold = max(0.035, baseline * 6.0)
    peaks: list[float] = []
    last_peak_s = -1.0
    for start, value in rms_values:
        when = start / sample_rate
        if value >= threshold and (last_peak_s < 0 or when - last_peak_s >= 0.07):
            peaks.append(round(when, 3))
            last_peak_s = when
            if len(peaks) >= 4:
                break
    return peaks

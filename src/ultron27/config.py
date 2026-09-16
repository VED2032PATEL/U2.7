from __future__ import annotations

import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Mapping

from .audit import DEFAULT_AUDIT_LOG
from .planner import DEFAULT_DATASET_PATH


DEFAULT_CONFIG_CANDIDATES = (
    Path("ultron.config.json"),
    Path(".ultron/config.json"),
)


@dataclass(frozen=True)
class UltronConfig:
    dataset_path: Path = DEFAULT_DATASET_PATH
    audit_log: Path = DEFAULT_AUDIT_LOG
    dry_run: bool = True
    workspace: Path = Path(".")
    safe_roots: tuple[Path, ...] = (Path("."),)
    app_aliases: dict[str, str] | None = None
    whatsapp_contacts: dict[str, str] | None = None
    whatsapp_require_confirmation: bool = True
    screenshot_dir: Path = Path(".ultron/screenshots")
    planner_mode: str = "rules"
    llm_provider: str = "ollama"
    llm_model: str = "qwen2.5:7b-instruct"
    llm_endpoint: str = "http://localhost:11434"
    llm_timeout_seconds: float = 8.0
    neural_router_enabled: bool = False
    neural_router_model: Path = Path(".ultron/models/neural_router.pt")
    voice_stt_provider: str = "text_payload"
    voice_capture_provider: str = "browser"
    voice_microphone_device: str | None = None
    voice_sample_rate: int = 16000
    voice_capture_seconds: float = 4.0
    voice_tts_provider: str = "browser_speech_synthesis"
    voice_stt_model: str | None = None
    voice_tts_model: str | None = "aura-2-orion-en"
    voice_stt_language: str = "multi"
    voice_stt_keyterms: tuple[str, ...] = ("ULTRON", "WhatsApp", "Spotify", "YouTube")
    voice_stt_model_path: Path | None = None
    voice_tts_model_path: Path | None = None
    voice_tts_voice_path: Path | None = None
    voice_device: str = "cpu"
    voice_identity: str = "ULTRON"
    voice_preference: str = "Microsoft George"
    voice_rate: float = 1.03
    voice_pitch: float = 1.0
    voice_volume: float = 1.0
    wake_word_provider: str = "text"
    wake_auto_start: bool = False
    wake_phrases: tuple[str, ...] = ("ultron", "hey ultron")
    wake_model_path: Path | None = None
    vad_provider: str = "energy"
    vad_energy_threshold: float = 0.015
    clap_spike_ratio: float = 7.0
    clap_min_rms: float = 0.012
    clap_min_gap_s: float = 0.05
    clap_max_gap_s: float = 0.35
    clap_cooldown_s: float = 0.45
    clap_retrigger_ratio: float = 0.55
    clap_noise_floor_alpha: float = 0.992
    clap_quiet_gate_mult: float = 2.2
    startup_briefing_enabled: bool = True
    assistant_location: str = "Jabalpur"
    speech_barge_in_enabled: bool = True


def load_config(
    config_path: Path | None = None,
    environ: Mapping[str, str] | None = None,
    base_dir: Path | None = None,
) -> UltronConfig:
    base = base_dir or Path.cwd()
    env = environ or os.environ
    config = UltronConfig()

    selected_path = _resolve_config_path(config_path, base)
    if selected_path is not None:
        config = _merge_json_config(config, selected_path)

    return _merge_env_config(config, env, base)


def _resolve_config_path(config_path: Path | None, base_dir: Path) -> Path | None:
    if config_path is not None:
        path = _resolve_path(config_path, base_dir)
        if not path.exists():
            raise FileNotFoundError(f"Config file not found: {path}")
        return path

    for candidate in DEFAULT_CONFIG_CANDIDATES:
        path = _resolve_path(candidate, base_dir)
        if path.exists():
            return path
    return None


def _merge_json_config(config: UltronConfig, path: Path) -> UltronConfig:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON config in {path}: {exc}") from exc

    if not isinstance(raw, dict):
        raise ValueError(f"Config file must contain a JSON object: {path}")

    base = path.parent
    updates: dict[str, object] = {}
    if "dataset_path" in raw:
        updates["dataset_path"] = _resolve_path(_expect_string(raw, "dataset_path"), base)
    if "audit_log" in raw:
        updates["audit_log"] = _resolve_path(_expect_string(raw, "audit_log"), base)
    if "dry_run" in raw:
        updates["dry_run"] = _expect_bool(raw, "dry_run")
    if "workspace" in raw:
        updates["workspace"] = _resolve_path(_expect_string(raw, "workspace"), base)
    if "safe_roots" in raw:
        updates["safe_roots"] = tuple(_resolve_path(Path(item), base) for item in _expect_string_list(raw, "safe_roots"))
    if "app_aliases" in raw:
        updates["app_aliases"] = _expect_string_mapping(raw, "app_aliases")
    if "whatsapp_contacts" in raw:
        updates["whatsapp_contacts"] = _expect_string_mapping(raw, "whatsapp_contacts")
    if "whatsapp_require_confirmation" in raw:
        updates["whatsapp_require_confirmation"] = _expect_bool(raw, "whatsapp_require_confirmation")
    if "screenshot_dir" in raw:
        updates["screenshot_dir"] = _resolve_path(_expect_string(raw, "screenshot_dir"), base)
    if "planner_mode" in raw:
        updates["planner_mode"] = _expect_choice(raw, "planner_mode", {"rules", "hybrid", "llm"})
    if "llm_provider" in raw:
        updates["llm_provider"] = _expect_choice(raw, "llm_provider", {"ollama", "groq"})
    if "llm_model" in raw:
        updates["llm_model"] = _expect_plain_string(raw, "llm_model")
    if "llm_endpoint" in raw:
        updates["llm_endpoint"] = _expect_plain_string(raw, "llm_endpoint")
    if "llm_timeout_seconds" in raw:
        updates["llm_timeout_seconds"] = _expect_number(raw, "llm_timeout_seconds")
    if "neural_router_enabled" in raw:
        updates["neural_router_enabled"] = _expect_bool(raw, "neural_router_enabled")
    if "neural_router_model" in raw:
        updates["neural_router_model"] = _resolve_path(_expect_string(raw, "neural_router_model"), base)
    if "voice_stt_provider" in raw:
        updates["voice_stt_provider"] = _expect_choice(
            raw,
            "voice_stt_provider",
            {"text_payload", "browser", "faster_whisper", "whisper_cpp", "deepgram", "mock"},
        )
    if "voice_capture_provider" in raw:
        updates["voice_capture_provider"] = _expect_choice(raw, "voice_capture_provider", {"browser", "sounddevice", "mock"})
    if "voice_microphone_device" in raw:
        value = raw["voice_microphone_device"]
        updates["voice_microphone_device"] = None if value is None else _expect_plain_string(raw, "voice_microphone_device")
    if "voice_sample_rate" in raw:
        updates["voice_sample_rate"] = int(_expect_number(raw, "voice_sample_rate"))
    if "voice_capture_seconds" in raw:
        updates["voice_capture_seconds"] = _expect_number(raw, "voice_capture_seconds")
    if "voice_tts_provider" in raw:
        updates["voice_tts_provider"] = _expect_choice(
            raw,
            "voice_tts_provider",
            {"browser_speech_synthesis", "browser", "deepgram", "piper", "pyttsx3", "mock"},
        )
    if "voice_stt_model" in raw:
        value = raw["voice_stt_model"]
        updates["voice_stt_model"] = None if value is None or value == "" else _expect_plain_string(raw, "voice_stt_model")
    if "voice_tts_model" in raw:
        value = raw["voice_tts_model"]
        updates["voice_tts_model"] = None if value is None or value == "" else _expect_plain_string(raw, "voice_tts_model")
    if "voice_stt_language" in raw:
        updates["voice_stt_language"] = _expect_plain_string(raw, "voice_stt_language").strip() or "multi"
    if "voice_stt_keyterms" in raw:
        updates["voice_stt_keyterms"] = tuple(_expect_string_list(raw, "voice_stt_keyterms"))
    if "voice_stt_model_path" in raw:
        updates["voice_stt_model_path"] = _resolve_optional_path(raw, "voice_stt_model_path", base)
    if "voice_tts_model_path" in raw:
        updates["voice_tts_model_path"] = _resolve_optional_path(raw, "voice_tts_model_path", base)
    if "voice_tts_voice_path" in raw:
        updates["voice_tts_voice_path"] = _resolve_optional_path(raw, "voice_tts_voice_path", base)
    if "voice_device" in raw:
        updates["voice_device"] = _expect_choice(raw, "voice_device", {"cpu", "cuda", "auto"})
    if "voice_identity" in raw:
        updates["voice_identity"] = _expect_plain_string(raw, "voice_identity")
    if "voice_preference" in raw:
        updates["voice_preference"] = _expect_plain_string(raw, "voice_preference")
    if "voice_rate" in raw:
        updates["voice_rate"] = _expect_number(raw, "voice_rate")
    if "voice_pitch" in raw:
        updates["voice_pitch"] = _expect_number(raw, "voice_pitch")
    if "voice_volume" in raw:
        updates["voice_volume"] = _expect_number(raw, "voice_volume")
    if "wake_word_provider" in raw:
        updates["wake_word_provider"] = _expect_choice(raw, "wake_word_provider", {"text", "openwakeword", "double_clap", "mock"})
    if "wake_auto_start" in raw:
        updates["wake_auto_start"] = _expect_bool(raw, "wake_auto_start")
    if "wake_phrases" in raw:
        updates["wake_phrases"] = tuple(_expect_string_list(raw, "wake_phrases"))
    if "wake_model_path" in raw:
        updates["wake_model_path"] = _resolve_optional_path(raw, "wake_model_path", base)
    if "vad_provider" in raw:
        updates["vad_provider"] = _expect_choice(raw, "vad_provider", {"energy", "silero", "webrtc", "mock"})
    if "vad_energy_threshold" in raw:
        updates["vad_energy_threshold"] = _expect_number(raw, "vad_energy_threshold")
    if "clap_spike_ratio" in raw:
        updates["clap_spike_ratio"] = _expect_number(raw, "clap_spike_ratio")
    if "clap_min_rms" in raw:
        updates["clap_min_rms"] = _expect_number(raw, "clap_min_rms")
    if "clap_min_gap_s" in raw:
        updates["clap_min_gap_s"] = _expect_number(raw, "clap_min_gap_s")
    if "clap_max_gap_s" in raw:
        updates["clap_max_gap_s"] = _expect_number(raw, "clap_max_gap_s")
    if "clap_cooldown_s" in raw:
        updates["clap_cooldown_s"] = _expect_number(raw, "clap_cooldown_s")
    if "clap_retrigger_ratio" in raw:
        updates["clap_retrigger_ratio"] = _expect_number(raw, "clap_retrigger_ratio")
    if "clap_noise_floor_alpha" in raw:
        updates["clap_noise_floor_alpha"] = _expect_number(raw, "clap_noise_floor_alpha")
    if "clap_quiet_gate_mult" in raw:
        updates["clap_quiet_gate_mult"] = _expect_number(raw, "clap_quiet_gate_mult")
    if "startup_briefing_enabled" in raw:
        updates["startup_briefing_enabled"] = _expect_bool(raw, "startup_briefing_enabled")
    if "assistant_location" in raw:
        updates["assistant_location"] = _expect_plain_string(raw, "assistant_location").strip() or "Jabalpur"
    if "speech_barge_in_enabled" in raw:
        updates["speech_barge_in_enabled"] = _expect_bool(raw, "speech_barge_in_enabled")
    return replace(config, **updates)


def _merge_env_config(config: UltronConfig, env: Mapping[str, str], base_dir: Path) -> UltronConfig:
    updates: dict[str, object] = {}
    if "ULTRON_DATASET_PATH" in env:
        updates["dataset_path"] = _resolve_path(Path(env["ULTRON_DATASET_PATH"]), base_dir)
    if "ULTRON_AUDIT_LOG" in env:
        updates["audit_log"] = _resolve_path(Path(env["ULTRON_AUDIT_LOG"]), base_dir)
    if "ULTRON_DRY_RUN" in env:
        updates["dry_run"] = parse_bool(env["ULTRON_DRY_RUN"])
    if "ULTRON_WORKSPACE" in env:
        updates["workspace"] = _resolve_path(Path(env["ULTRON_WORKSPACE"]), base_dir)
    if "ULTRON_SAFE_ROOTS" in env:
        updates["safe_roots"] = tuple(_resolve_path(Path(item.strip()), base_dir) for item in env["ULTRON_SAFE_ROOTS"].split(";") if item.strip())
    if "ULTRON_WHATSAPP_CONTACTS" in env:
        updates["whatsapp_contacts"] = _parse_string_mapping_json(env["ULTRON_WHATSAPP_CONTACTS"], "ULTRON_WHATSAPP_CONTACTS")
    if "ULTRON_WHATSAPP_REQUIRE_CONFIRMATION" in env:
        updates["whatsapp_require_confirmation"] = parse_bool(env["ULTRON_WHATSAPP_REQUIRE_CONFIRMATION"])
    if "ULTRON_SCREENSHOT_DIR" in env:
        updates["screenshot_dir"] = _resolve_path(Path(env["ULTRON_SCREENSHOT_DIR"]), base_dir)
    if "ULTRON_PLANNER_MODE" in env:
        updates["planner_mode"] = _parse_choice(env["ULTRON_PLANNER_MODE"], "ULTRON_PLANNER_MODE", {"rules", "hybrid", "llm"})
    if "ULTRON_LLM_PROVIDER" in env:
        updates["llm_provider"] = _parse_choice(env["ULTRON_LLM_PROVIDER"], "ULTRON_LLM_PROVIDER", {"ollama", "groq"})
    if "ULTRON_LLM_MODEL" in env:
        updates["llm_model"] = env["ULTRON_LLM_MODEL"]
    if "ULTRON_LLM_ENDPOINT" in env:
        updates["llm_endpoint"] = env["ULTRON_LLM_ENDPOINT"]
    if "ULTRON_LLM_TIMEOUT_SECONDS" in env:
        updates["llm_timeout_seconds"] = float(env["ULTRON_LLM_TIMEOUT_SECONDS"])
    if "ULTRON_NEURAL_ROUTER_ENABLED" in env:
        updates["neural_router_enabled"] = parse_bool(env["ULTRON_NEURAL_ROUTER_ENABLED"])
    if "ULTRON_NEURAL_ROUTER_MODEL" in env:
        updates["neural_router_model"] = _resolve_path(Path(env["ULTRON_NEURAL_ROUTER_MODEL"]), base_dir)
    if "ULTRON_STT_PROVIDER" in env:
        updates["voice_stt_provider"] = _parse_choice(
            env["ULTRON_STT_PROVIDER"],
            "ULTRON_STT_PROVIDER",
            {"text_payload", "browser", "faster_whisper", "whisper_cpp", "deepgram", "mock"},
        )
    if "ULTRON_CAPTURE_PROVIDER" in env:
        updates["voice_capture_provider"] = _parse_choice(env["ULTRON_CAPTURE_PROVIDER"], "ULTRON_CAPTURE_PROVIDER", {"browser", "sounddevice", "mock"})
    if "ULTRON_MICROPHONE_DEVICE" in env:
        updates["voice_microphone_device"] = env["ULTRON_MICROPHONE_DEVICE"]
    if "ULTRON_VOICE_SAMPLE_RATE" in env:
        updates["voice_sample_rate"] = int(env["ULTRON_VOICE_SAMPLE_RATE"])
    if "ULTRON_VOICE_CAPTURE_SECONDS" in env:
        updates["voice_capture_seconds"] = float(env["ULTRON_VOICE_CAPTURE_SECONDS"])
    if "ULTRON_TTS_PROVIDER" in env:
        updates["voice_tts_provider"] = _parse_choice(
            env["ULTRON_TTS_PROVIDER"],
            "ULTRON_TTS_PROVIDER",
            {"browser_speech_synthesis", "browser", "deepgram", "piper", "pyttsx3", "mock"},
        )
    if "ULTRON_STT_MODEL" in env:
        updates["voice_stt_model"] = env["ULTRON_STT_MODEL"]
    if "ULTRON_TTS_MODEL" in env:
        updates["voice_tts_model"] = env["ULTRON_TTS_MODEL"]
    if "ULTRON_STT_LANGUAGE" in env:
        updates["voice_stt_language"] = env["ULTRON_STT_LANGUAGE"].strip() or "multi"
    if "ULTRON_STT_KEYTERMS" in env:
        updates["voice_stt_keyterms"] = tuple(item.strip() for item in env["ULTRON_STT_KEYTERMS"].split(";") if item.strip())
    if "ULTRON_STT_MODEL_PATH" in env:
        updates["voice_stt_model_path"] = _resolve_path(Path(env["ULTRON_STT_MODEL_PATH"]), base_dir)
    if "ULTRON_TTS_MODEL_PATH" in env:
        updates["voice_tts_model_path"] = _resolve_path(Path(env["ULTRON_TTS_MODEL_PATH"]), base_dir)
    if "ULTRON_TTS_VOICE_PATH" in env:
        updates["voice_tts_voice_path"] = _resolve_path(Path(env["ULTRON_TTS_VOICE_PATH"]), base_dir)
    if "ULTRON_VOICE_DEVICE" in env:
        updates["voice_device"] = _parse_choice(env["ULTRON_VOICE_DEVICE"], "ULTRON_VOICE_DEVICE", {"cpu", "cuda", "auto"})
    if "ULTRON_VOICE_IDENTITY" in env:
        updates["voice_identity"] = env["ULTRON_VOICE_IDENTITY"]
    if "ULTRON_VOICE_PREFERENCE" in env:
        updates["voice_preference"] = env["ULTRON_VOICE_PREFERENCE"]
    if "ULTRON_VOICE_RATE" in env:
        updates["voice_rate"] = float(env["ULTRON_VOICE_RATE"])
    if "ULTRON_VOICE_PITCH" in env:
        updates["voice_pitch"] = float(env["ULTRON_VOICE_PITCH"])
    if "ULTRON_VOICE_VOLUME" in env:
        updates["voice_volume"] = float(env["ULTRON_VOICE_VOLUME"])
    if "ULTRON_WAKE_WORD_PROVIDER" in env:
        updates["wake_word_provider"] = _parse_choice(env["ULTRON_WAKE_WORD_PROVIDER"], "ULTRON_WAKE_WORD_PROVIDER", {"text", "openwakeword", "double_clap", "mock"})
    if "ULTRON_WAKE_AUTO_START" in env:
        updates["wake_auto_start"] = parse_bool(env["ULTRON_WAKE_AUTO_START"])
    if "ULTRON_WAKE_PHRASES" in env:
        updates["wake_phrases"] = tuple(item.strip() for item in env["ULTRON_WAKE_PHRASES"].split(";") if item.strip())
    if "ULTRON_WAKE_MODEL_PATH" in env:
        updates["wake_model_path"] = _resolve_path(Path(env["ULTRON_WAKE_MODEL_PATH"]), base_dir)
    if "ULTRON_VAD_PROVIDER" in env:
        updates["vad_provider"] = _parse_choice(env["ULTRON_VAD_PROVIDER"], "ULTRON_VAD_PROVIDER", {"energy", "silero", "webrtc", "mock"})
    if "ULTRON_VAD_ENERGY_THRESHOLD" in env:
        updates["vad_energy_threshold"] = float(env["ULTRON_VAD_ENERGY_THRESHOLD"])
    if "ULTRON_CLAP_SPIKE_RATIO" in env:
        updates["clap_spike_ratio"] = float(env["ULTRON_CLAP_SPIKE_RATIO"])
    if "ULTRON_CLAP_MIN_RMS" in env:
        updates["clap_min_rms"] = float(env["ULTRON_CLAP_MIN_RMS"])
    if "ULTRON_CLAP_MIN_GAP_S" in env:
        updates["clap_min_gap_s"] = float(env["ULTRON_CLAP_MIN_GAP_S"])
    if "ULTRON_CLAP_MAX_GAP_S" in env:
        updates["clap_max_gap_s"] = float(env["ULTRON_CLAP_MAX_GAP_S"])
    if "ULTRON_CLAP_COOLDOWN_S" in env:
        updates["clap_cooldown_s"] = float(env["ULTRON_CLAP_COOLDOWN_S"])
    if "ULTRON_CLAP_RETRIGGER_RATIO" in env:
        updates["clap_retrigger_ratio"] = float(env["ULTRON_CLAP_RETRIGGER_RATIO"])
    if "ULTRON_CLAP_NOISE_FLOOR_ALPHA" in env:
        updates["clap_noise_floor_alpha"] = float(env["ULTRON_CLAP_NOISE_FLOOR_ALPHA"])
    if "ULTRON_CLAP_QUIET_GATE_MULT" in env:
        updates["clap_quiet_gate_mult"] = float(env["ULTRON_CLAP_QUIET_GATE_MULT"])
    if "ULTRON_STARTUP_BRIEFING_ENABLED" in env:
        updates["startup_briefing_enabled"] = parse_bool(env["ULTRON_STARTUP_BRIEFING_ENABLED"])
    if "ULTRON_LOCATION" in env:
        updates["assistant_location"] = env["ULTRON_LOCATION"].strip() or "Jabalpur"
    if "ULTRON_SPEECH_BARGE_IN_ENABLED" in env:
        updates["speech_barge_in_enabled"] = parse_bool(env["ULTRON_SPEECH_BARGE_IN_ENABLED"])
    return replace(config, **updates)


def parse_bool(value: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "y", "on"}:
        return True
    if normalized in {"0", "false", "no", "n", "off"}:
        return False
    raise ValueError(f"Expected a boolean value, got: {value}")


def _resolve_path(path: str | Path, base_dir: Path) -> Path:
    candidate = Path(path).expanduser()
    if candidate.is_absolute():
        return candidate
    return base_dir / candidate


def _expect_string(raw: dict[str, object], key: str) -> Path:
    value = raw[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string path")
    return Path(value)


def _expect_plain_string(raw: dict[str, object], key: str) -> str:
    value = raw[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return value


def _resolve_optional_path(raw: dict[str, object], key: str, base_dir: Path) -> Path | None:
    value = raw[key]
    if value is None or value == "":
        return None
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string path or null")
    return _resolve_path(Path(value), base_dir)


def _expect_bool(raw: dict[str, object], key: str) -> bool:
    value = raw[key]
    if not isinstance(value, bool):
        raise ValueError(f"{key} must be true or false")
    return value


def _expect_string_list(raw: dict[str, object], key: str) -> list[str]:
    value = raw[key]
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"{key} must be a list of string paths")
    return value


def _expect_string_mapping(raw: dict[str, object], key: str) -> dict[str, str]:
    value = raw[key]
    if not isinstance(value, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in value.items()):
        raise ValueError(f"{key} must be an object with string keys and values")
    return dict(value)


def _parse_string_mapping_json(value: str, key: str) -> dict[str, str]:
    try:
        payload = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"{key} must be a JSON object with string keys and values") from exc
    if not isinstance(payload, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in payload.items()):
        raise ValueError(f"{key} must be a JSON object with string keys and values")
    return dict(payload)


def _expect_choice(raw: dict[str, object], key: str, allowed: set[str]) -> str:
    value = raw[key]
    if not isinstance(value, str):
        raise ValueError(f"{key} must be a string")
    return _parse_choice(value, key, allowed)


def _parse_choice(value: str, key: str, allowed: set[str]) -> str:
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise ValueError(f"{key} must be one of: {', '.join(sorted(allowed))}")
    return normalized


def _expect_number(raw: dict[str, object], key: str) -> float:
    value = raw[key]
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        raise ValueError(f"{key} must be a number")
    return float(value)

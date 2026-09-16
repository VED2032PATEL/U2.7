from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Protocol

from .models import Plan, RiskLevel, ToolCall
from .secrets import get_secret
from .tools import TOOL_SPECS, get_tool_spec, validate_tool_call


class LLMPlannerError(RuntimeError):
    pass


class LLMChatError(RuntimeError):
    pass


class LLMProvider(Protocol):
    def complete(self, prompt: str, timeout: float) -> str:
        ...


@dataclass(frozen=True)
class OllamaProvider:
    endpoint: str
    model: str

    def complete(self, prompt: str, timeout: float) -> str:
        payload = {
            "model": self.model,
            "stream": False,
            "format": "json",
            "think": False,
            "options": {"temperature": 0, "num_predict": 220},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }
        request = urllib.request.Request(
            self.endpoint.rstrip("/") + "/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise LLMPlannerError(f"Ollama request failed: {exc}") from exc
        message = data.get("message") or {}
        content = message.get("content")
        if not isinstance(content, str):
            raise LLMPlannerError("Ollama response did not include message.content")
        return content


@dataclass(frozen=True)
class GroqProvider:
    endpoint: str
    model: str
    api_key: str | None = None

    def complete(self, prompt: str, timeout: float) -> str:
        key = self.api_key or get_secret("GROQ_API_KEY")
        if not key:
            raise LLMPlannerError("Groq API key is missing. Set GROQ_API_KEY.")
        payload = {
            "model": self.model,
            "temperature": 0,
            "max_tokens": 220,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
        }
        request = urllib.request.Request(
            _chat_completions_url(self.endpoint),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "ultron27/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise LLMPlannerError(f"Groq request failed: {exc}") from exc
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMPlannerError("Groq response did not include choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str):
            raise LLMPlannerError("Groq response did not include choices[0].message.content")
        return content


@dataclass(frozen=True)
class GroqChatProvider:
    endpoint: str
    model: str
    api_key: str | None = None

    def complete_chat(self, messages: list[dict[str, str]], timeout: float, *, max_tokens: int = 180) -> str:
        key = self.api_key or get_secret("GROQ_API_KEY")
        if not key:
            raise LLMChatError("Groq API key is missing. Set GROQ_API_KEY.")
        payload = {
            "model": self.model,
            "temperature": 0.65,
            "max_tokens": max_tokens,
            "messages": messages,
        }
        request = urllib.request.Request(
            _chat_completions_url(self.endpoint),
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
                "User-Agent": "ultron27/0.1",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                data = json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, json.JSONDecodeError) as exc:
            raise LLMChatError(f"Groq chat request failed: {exc}") from exc
        choices = data.get("choices")
        if not isinstance(choices, list) or not choices:
            raise LLMChatError("Groq chat response did not include choices")
        message = choices[0].get("message") if isinstance(choices[0], dict) else None
        content = message.get("content") if isinstance(message, dict) else None
        if not isinstance(content, str) or not content.strip():
            raise LLMChatError("Groq chat response did not include choices[0].message.content")
        return content.strip()


class LLMPlanner:
    def __init__(self, provider: LLMProvider, timeout: float = 8.0, *, min_confidence: float = 0.52):
        self.provider = provider
        self.timeout = timeout
        self.min_confidence = min_confidence

    def plan(self, utterance: str) -> Plan:
        raw = self.provider.complete(build_prompt(utterance), self.timeout)
        call, intent, confidence = parse_llm_tool_call(raw)
        if call.name not in {"ask_clarification", "unsupported_request"} and confidence < self.min_confidence:
            call = ToolCall(
                "ask_clarification",
                {"question": "I am not fully sure what action you want. Please say it another way or add one detail."},
            )
            intent = "clarify_intent"
        validation = validate_tool_call(call)
        if not validation.valid:
            raise LLMPlannerError("; ".join(validation.errors))
        spec = get_tool_spec(call.name)
        if spec is None:
            raise LLMPlannerError(f"Unknown tool: {call.name}")
        return Plan(
            utterance=utterance,
            intent=intent or call.name,
            tool_call=call,
            risk_level=spec.risk_level,
            requires_confirmation=spec.requires_confirmation,
            source="llm",
            confidence=confidence,
        )


class SemanticIntentRouter:
    """Local-LLM semantic router that can only return validated typed tool plans."""

    def __init__(self, planner: LLMPlanner):
        self.planner = planner

    def route(self, utterance: str) -> Plan:
        return self.planner.plan(utterance)


SYSTEM_PROMPT = """You are ULTRON 2.7's private planner.
Return only one JSON object. Do not execute commands. Do not write thoughts, reasoning, narration, markdown, or conversational prose."""


COMMAND_CLASSIFICATION_TEMPLATE = """Classify whether the user wants chat, clarification, or an executable typed tool."""
TOOL_SELECTION_TEMPLATE = """Select exactly one allowlisted tool and fill only schema-supported arguments."""
MULTI_STEP_TEMPLATE = """If the user asks for a multi-step task, choose the next safest atomic tool step."""
CLARIFICATION_TEMPLATE = """If required information is missing or the intent is ambiguous, use ask_clarification."""


def build_prompt(utterance: str) -> str:
    tool_lines = []
    for name, spec in sorted(TOOL_SPECS.items()):
        required = ", ".join(spec.required) or "none"
        optional = ", ".join(spec.optional) or "none"
        tool_lines.append(f"- {name}: required={required}; optional={optional}; risk={spec.risk_level.value}")
    tools = "\n".join(tool_lines)
    return (
        "Map the user command to one allowlisted tool call. The model is not allowed to execute anything.\n"
        "Do not explain your thinking. Do not speak as ULTRON. Output JSON only.\n"
        f"{COMMAND_CLASSIFICATION_TEMPLATE}\n"
        f"{TOOL_SELECTION_TEMPLATE}\n"
        f"{MULTI_STEP_TEMPLATE}\n"
        f"{CLARIFICATION_TEMPLATE}\n\n"
        "Return JSON in this exact shape:\n"
        '{"intent":"...", "tool_name":"...", "tool_arguments":{...}, "confidence":0.0, "needs_clarification":false, "clarification_question":""}\n'
        "If no safe tool fits, use unsupported_request with reason.\n"
        "If the request is ambiguous, missing key details, or asks to type into another app before that tool exists, use ask_clarification with a direct question.\n"
        "Examples:\n"
        '- "open notepad" -> {"intent":"open_app","tool_name":"open_application","tool_arguments":{"app":"notepad"},"confidence":0.95}\n'
        '- "launch notepad" -> {"intent":"open_app","tool_name":"open_application","tool_arguments":{"app":"notepad"},"confidence":0.92}\n'
        '- "bring up notepad" -> {"intent":"open_app","tool_name":"open_application","tool_arguments":{"app":"notepad"},"confidence":0.9}\n'
        '- "start the notes app" -> {"intent":"open_app","tool_name":"open_application","tool_arguments":{"app":"notepad"},"confidence":0.82}\n'
        '- "open notepad and write alien in it" -> {"intent":"write_text_in_app","tool_name":"write_text_in_application","tool_arguments":{"app":"notepad","text":"alien"},"confidence":0.88}\n'
        '- "type hello into notepad" -> {"intent":"write_text_in_app","tool_name":"write_text_in_application","tool_arguments":{"app":"notepad","text":"hello"},"confidence":0.86}\n'
        '- "turn the volume up by 10 percent" -> {"intent":"adjust_volume","tool_name":"adjust_system_volume","tool_arguments":{"direction":"up","delta":10},"confidence":0.94}\n'
        '- "unmute the sound" -> {"intent":"unmute_volume","tool_name":"mute_system_volume","tool_arguments":{"mute":false},"confidence":0.96}\n'
        '- "play the next song" -> {"intent":"next_track","tool_name":"next_media_track","tool_arguments":{},"confidence":0.95}\n'
        '- "play blinding lights on Spotify" -> {"intent":"play_music","tool_name":"play_music","tool_arguments":{"query":"blinding lights"},"confidence":0.91}\n'
        '- "play the Python tutorial on YouTube" -> {"intent":"play_youtube_video","tool_name":"play_youtube_video","tool_arguments":{"query":"the Python tutorial"},"confidence":0.94}\n'
        '- "put on some lofi music" -> {"intent":"play_music","tool_name":"play_music","tool_arguments":{"query":"lofi music"},"confidence":0.78}\n'
        '- "send a WhatsApp message to Mom saying I will be home at seven" -> {"intent":"send_whatsapp_message","tool_name":"send_whatsapp_message","tool_arguments":{"recipient":"Mom","message":"I will be home at seven"},"confidence":0.94}\n'
        '- "write this in notepad" -> {"intent":"clarify_intent","tool_name":"ask_clarification","tool_arguments":{"question":"What text should I write in Notepad?"},"confidence":0.72,"needs_clarification":true}\n'
        '- "jot this down: voice mode works" -> {"intent":"create_note","tool_name":"create_note","tool_arguments":{"title":"quick note","content":"voice mode works"},"confidence":0.78}\n\n'
        '- "search YouTube for Python tutorials" -> {"intent":"open_website","tool_name":"open_website","tool_arguments":{"site":"youtube","query":"Python tutorials"},"confidence":0.94}\n'
        '- "what is 15 percent of 200" -> {"intent":"calculate","tool_name":"calculate","tool_arguments":{"expression":"15 percent of 200"},"confidence":0.96}\n'
        '- "how much battery is left" -> {"intent":"get_battery","tool_name":"get_system_status","tool_arguments":{"category":"battery"},"confidence":0.95}\n'
        '- "find PDF files in Downloads" -> {"intent":"search_files","tool_name":"search_files","tool_arguments":{"query":"*","file_type":"pdf","folder":"Downloads"},"confidence":0.93}\n\n'
        f"Available tools:\n{tools}\n\n"
        f"User command: {utterance}"
    )


def parse_llm_tool_call(raw: str) -> tuple[ToolCall, str, float]:
    payload = _extract_json_object(raw)
    if payload.get("needs_clarification") is True:
        question = str(payload.get("clarification_question") or payload.get("question") or "Could you clarify what you want me to do?")
        return ToolCall("ask_clarification", {"question": question}), str(payload.get("intent", "clarify_intent")), _confidence(payload)
    tool_name = payload.get("tool_name") or payload.get("name")
    arguments = payload.get("tool_arguments", payload.get("arguments", {}))
    intent = str(payload.get("intent", tool_name or ""))

    if not isinstance(tool_name, str) or not tool_name:
        raise LLMPlannerError("LLM output must include tool_name")
    if not isinstance(arguments, dict):
        raise LLMPlannerError("LLM output tool_arguments must be an object")
    return ToolCall(tool_name, arguments), intent, _confidence(payload)


def _extract_json_object(raw: str) -> dict[str, Any]:
    text = raw.strip()
    text = _strip_thinking_blocks(text)
    if text.startswith("```"):
        text = text.strip("`")
        if text.startswith("json"):
            text = text[4:].strip()
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        start = text.find("{")
        end = text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            raise LLMPlannerError("LLM output was not valid JSON")
        payload = json.loads(text[start : end + 1])
    if not isinstance(payload, dict):
        raise LLMPlannerError("LLM output must be a JSON object")
    return payload


def _strip_thinking_blocks(text: str) -> str:
    while "<think>" in text.lower() and "</think>" in text.lower():
        lowered = text.lower()
        start = lowered.find("<think>")
        end = lowered.find("</think>", start)
        if start == -1 or end == -1:
            break
        text = text[:start] + text[end + len("</think>") :]
    return text.strip()


def _confidence(payload: dict[str, Any]) -> float:
    confidence = payload.get("confidence", 0.5)
    if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
        confidence = 0.5
    return max(0.0, min(1.0, float(confidence)))


def make_ollama_planner(endpoint: str, model: str, timeout: float) -> LLMPlanner:
    return LLMPlanner(OllamaProvider(endpoint=endpoint, model=model), timeout=timeout)


def make_ollama_router(endpoint: str, model: str, timeout: float) -> SemanticIntentRouter:
    return SemanticIntentRouter(make_ollama_planner(endpoint, model, timeout))


def make_groq_planner(endpoint: str, model: str, timeout: float) -> LLMPlanner:
    return LLMPlanner(GroqProvider(endpoint=endpoint, model=model), timeout=timeout)


def make_groq_router(endpoint: str, model: str, timeout: float) -> SemanticIntentRouter:
    return SemanticIntentRouter(make_groq_planner(endpoint, model, timeout))


def _chat_completions_url(endpoint: str) -> str:
    base = endpoint.rstrip("/")
    if base.endswith("/chat/completions"):
        return base
    return base + "/chat/completions"

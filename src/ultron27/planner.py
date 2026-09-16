from __future__ import annotations

import json
import re
import string
from dataclasses import dataclass
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable

from .models import Plan, RiskLevel, ToolCall
from .tools import get_tool_spec


DEFAULT_DATASET_PATH = Path("data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl")

_REGEX_PRIORITY_TOOLS = {
    "adjust_screen_brightness",
    "adjust_system_volume",
    "append_to_note",
    "calculate",
    "close_application",
    "copy_to_clipboard",
    "create_folder",
    "create_note",
    "draft_email",
    "get_system_status",
    "lock_screen",
    "move_file",
    "mute_system_volume",
    "next_media_track",
    "open_file",
    "open_terminal",
    "open_website",
    "pause_media",
    "play_youtube_video",
    "previous_media_track",
    "rename_file",
    "search_files",
    "send_whatsapp_message",
    "set_screen_brightness",
    "set_system_volume",
    "switch_application",
}


@dataclass(frozen=True)
class DatasetExample:
    utterance: str
    intent: str
    tool_call: ToolCall
    risk_level: RiskLevel
    requires_confirmation: bool


class DatasetPlanner:
    def __init__(self, examples: Iterable[DatasetExample] = ()):
        self.examples = list(examples)
        self._by_normalized = {normalize_text(example.utterance): example for example in self.examples}

    @classmethod
    def from_jsonl(cls, path: Path = DEFAULT_DATASET_PATH) -> "DatasetPlanner":
        if not path.exists():
            return cls()

        examples: list[DatasetExample] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            row = json.loads(line)
            examples.append(
                DatasetExample(
                    utterance=row["utterance"],
                    intent=row["intent"],
                    tool_call=ToolCall(row["tool_name"], row.get("tool_arguments") or {}),
                    risk_level=RiskLevel(row["risk_level"]),
                    requires_confirmation=bool(row["requires_confirmation"]),
                )
            )
        return cls(examples)

    def plan(self, utterance: str) -> Plan:
        normalized = normalize_text(utterance)
        deterministic = regex_plan(utterance)
        if deterministic.source == "regex" and deterministic.tool_call.name in _REGEX_PRIORITY_TOOLS:
            return deterministic

        exact = self._by_normalized.get(normalized)
        if exact is not None:
            return self._to_plan(utterance, exact, "dataset_exact", 1.0)

        if deterministic.source == "regex":
            return deterministic

        fuzzy = self._nearest(normalized)
        if fuzzy is not None:
            example, confidence = fuzzy
            return self._to_plan(utterance, example, "dataset_fuzzy", confidence)

        return deterministic

    def _nearest(self, normalized: str) -> tuple[DatasetExample, float] | None:
        best: tuple[DatasetExample, float] | None = None
        for key, example in self._by_normalized.items():
            ratio = SequenceMatcher(None, normalized, key).ratio()
            if best is None or ratio > best[1]:
                best = (example, ratio)
        if best and best[1] >= 0.82:
            return best
        return None

    @staticmethod
    def _to_plan(utterance: str, example: DatasetExample, source: str, confidence: float) -> Plan:
        return Plan(
            utterance=utterance,
            intent=example.intent,
            tool_call=example.tool_call,
            risk_level=example.risk_level,
            requires_confirmation=example.requires_confirmation,
            source=source,
            confidence=confidence,
        )


def normalize_text(text: str) -> str:
    table = str.maketrans("", "", string.punctuation)
    return " ".join(text.lower().translate(table).split())


def regex_plan(utterance: str) -> Plan:
    whatsapp = _whatsapp_plan(utterance)
    if whatsapp is not None:
        return whatsapp

    for specialized_planner in (
        _calculation_plan,
        _note_plan,
        _website_plan,
        _file_operation_plan,
        _file_search_plan,
        _draft_email_plan,
    ):
        specialized = specialized_planner(utterance)
        if specialized is not None:
            return specialized

    text = normalize_text(utterance)
    text = _normalize_app_alias_words(text)

    if re.fullmatch(r"(?:hello|hi|hey)(?: ultron)?", text) or text in {"ultron", "hey ultron"}:
        return _plan_from_tool(
            utterance,
            "assistant_reply",
            "assistant_reply",
            {"message": "At your service. Tell me what you need, and I will handle the safe parts for you."},
            "regex",
            0.78,
        )

    if re.search(r"\b(?:what can you do|help|commands|capabilities)\b", text):
        return _plan_from_tool(
            utterance,
            "assistant_reply",
            "assistant_reply",
            {
                "message": "I can open, switch, and safely close apps; control volume, brightness, and media; use Spotify and WhatsApp; open websites; calculate; report time, date, battery, storage, and system status; organize approved files and folders; create notes, reminders, timers, screenshots, and email drafts; use the clipboard; and search local files or the web."
            },
            "regex",
            0.78,
        )

    if re.search(r"\b(?:thank you|thanks|good job)\b", text):
        return _plan_from_tool(
            utterance,
            "assistant_reply",
            "assistant_reply",
            {"message": "Of course. I am ready for the next task."},
            "regex",
            0.76,
        )

    volume_up_by_match = re.search(
        r"\b(?:raise|increase)\s+(?:the\s+)?(?:volume|sound)(?:\s+level)?(?:\s+(?:up|higher))?\s+by\s+(\d{1,3})\b",
        text,
    )
    if volume_up_by_match:
        delta = clamp(int(volume_up_by_match.group(1)), 1, 100)
        return _plan_from_tool(utterance, "adjust_volume", "adjust_system_volume", {"direction": "up", "delta": delta}, "regex", 0.84)

    volume_up_match = re.search(
        r"\b(?:(?:turn|raise|increase)\s+(?:the\s+)?(?:volume|sound)(?:\s+level)?\s+(?:up|higher)|"
        r"(?:volume|sound)\s+(?:up|higher)|(?:make\s+it\s+)?louder)(?:\s+by)?(?:\s+(\d{1,3}))?\b",
        text,
    )
    if volume_up_match:
        explicit_delta = re.search(r"\bby\s+(\d{1,3})\b", text)
        delta = clamp(int((explicit_delta.group(1) if explicit_delta else volume_up_match.group(1)) or 10), 1, 100)
        return _plan_from_tool(utterance, "adjust_volume", "adjust_system_volume", {"direction": "up", "delta": delta}, "regex", 0.82)

    volume_down_match = re.search(
        r"\b(?:(?:lower|decrease|reduce)\s+(?:the\s+)?(?:volume|sound)(?:\s+level)?\s*(?:down|lower)?|"
        r"turn\s+(?:the\s+)?(?:volume|sound)(?:\s+level)?\s+(?:down|lower)|"
        r"(?:volume|sound)\s+(?:down|lower)|(?:make\s+it\s+)?quieter)(?:\s+by)?(?:\s+(\d{1,3}))?\b",
        text,
    )
    if volume_down_match:
        explicit_delta = re.search(r"\bby\s+(\d{1,3})\b", text)
        delta = clamp(int((explicit_delta.group(1) if explicit_delta else volume_down_match.group(1)) or 10), 1, 100)
        return _plan_from_tool(utterance, "adjust_volume", "adjust_system_volume", {"direction": "down", "delta": delta}, "regex", 0.82)

    volume_match = re.search(r"\b(?:set|change|put|turn)\s+(?:the\s+)?(?:volume|sound)(?:\s+level)?\s+(?:to|at)\s+(\d{1,3})\b", text)
    if volume_match is None:
        volume_match = re.search(r"\b(?:volume|sound)(?:\s+level)?\s+(?:to|at)\s+(\d{1,3})\b", text)
    if volume_match is None:
        volume_match = re.search(r"\bmake\s+(?:the\s+)?(?:volume|sound)(?:\s+level)?\s+(\d{1,3})\b", text)
    if volume_match:
        level = clamp(int(volume_match.group(1)), 0, 100)
        return _plan_from_tool(utterance, "set_volume", "set_system_volume", {"level": level}, "regex", 0.76)

    brightness_up_by_match = re.search(
        r"\b(?:raise|increase)\s+(?:the\s+)?(?:screen\s+)?brightness(?:\s+(?:up|higher))?\s+by\s+(\d{1,3})\b",
        text,
    )
    if brightness_up_by_match:
        delta = clamp(int(brightness_up_by_match.group(1)), 1, 100)
        return _plan_from_tool(utterance, "adjust_brightness", "adjust_screen_brightness", {"direction": "up", "delta": delta}, "regex", 0.84)

    brightness_up_match = re.search(
        r"\b(?:(?:raise|increase|turn)\s+(?:the\s+)?(?:screen\s+)?brightness\s+(?:up|higher)|"
        r"(?:brightness)\s+(?:up|higher)|brighten\s+(?:the\s+)?screen)(?:\s+by)?(?:\s+(\d{1,3}))?\b",
        text,
    )
    if brightness_up_match:
        explicit_delta = re.search(r"\bby\s+(\d{1,3})\b", text)
        delta = clamp(int((explicit_delta.group(1) if explicit_delta else brightness_up_match.group(1)) or 10), 1, 100)
        return _plan_from_tool(utterance, "adjust_brightness", "adjust_screen_brightness", {"direction": "up", "delta": delta}, "regex", 0.80)

    brightness_down_match = re.search(
        r"\b(?:(?:lower|decrease|reduce)\s+(?:the\s+)?(?:screen\s+)?brightness\s*(?:down|lower)?|"
        r"turn\s+(?:the\s+)?(?:screen\s+)?brightness\s+(?:down|lower)|"
        r"(?:brightness)\s+(?:down|lower)|dim\s+(?:the\s+)?screen)(?:\s+by)?(?:\s+(\d{1,3}))?\b",
        text,
    )
    if brightness_down_match:
        explicit_delta = re.search(r"\bby\s+(\d{1,3})\b", text)
        delta = clamp(int((explicit_delta.group(1) if explicit_delta else brightness_down_match.group(1)) or 10), 1, 100)
        return _plan_from_tool(utterance, "adjust_brightness", "adjust_screen_brightness", {"direction": "down", "delta": delta}, "regex", 0.80)

    brightness_match = re.search(r"\b(?:set|change|put|turn)\s+(?:the\s+)?(?:screen\s+)?brightness\s+(?:to|at)\s+(\d{1,3})\b", text)
    if brightness_match is None:
        brightness_match = re.search(r"\bbrightness\s+(?:to|at)\s+(\d{1,3})\b", text)
    if brightness_match is None:
        brightness_match = re.search(r"\bmake\s+(?:the\s+)?(?:screen\s+)?brightness\s+(\d{1,3})\b", text)
    if brightness_match:
        level = clamp(int(brightness_match.group(1)), 0, 100)
        return _plan_from_tool(utterance, "set_brightness", "set_screen_brightness", {"level": level}, "regex", 0.74)

    if re.search(r"\b(?:unmute|turn\s+(?:the\s+)?sound\s+back\s+on|sound\s+on)\b", text):
        return _plan_from_tool(utterance, "unmute_volume", "mute_system_volume", {"mute": False}, "regex", 0.84)

    if re.search(r"\b(?:mute|sound\s+off)\b", text):
        return _plan_from_tool(utterance, "mute_volume", "mute_system_volume", {"mute": True}, "regex", 0.72)

    open_and_write_match = re.search(
        r"\b(?:open|launch|start)\s+(?:the\s+)?(?P<app>notepad)\s+(?:and\s+)?(?:write|type|enter|put)\s+(?P<content>.+)",
        text,
    )
    if open_and_write_match:
        content = _clean_app_write_content(open_and_write_match.group("content"))
        if content:
            return _plan_from_tool(
                utterance,
                "write_text_in_app",
                "write_text_in_application",
                {"app": open_and_write_match.group("app").strip(), "text": content},
                "regex",
                0.74,
            )

    write_in_app_match = re.search(
        r"\b(?:write|type|enter|put)\s+(?P<content>.+?)\s+(?:in|inside|into)\s+(?:the\s+)?(?P<app>notepad)\b",
        text,
    )
    if write_in_app_match:
        content = _clean_app_write_content(write_in_app_match.group("content"))
        if content:
            return _plan_from_tool(
                utterance,
                "write_text_in_app",
                "write_text_in_application",
                {"app": write_in_app_match.group("app").strip(), "text": content},
                "regex",
                0.74,
            )

    notepad_write_match = re.search(r"\b(?:write|type|jot)\s+(?:this\s+)?(?:in|inside|into)\s+notepad\b", text)
    if notepad_write_match:
        return _plan_from_tool(
            utterance,
            "clarify_intent",
            "ask_clarification",
            {"question": "What text should I write in Notepad?"},
            "regex",
            0.66,
        )

    reminder_match = re.search(r"\bremind\s+me\s+to\s+(.+?)\s+(?:at|on|in)\s+(.+)", text)
    if reminder_match:
        return _plan_from_tool(
            utterance,
            "set_reminder",
            "set_reminder",
            {"task": reminder_match.group(1).strip(), "time": reminder_match.group(2).strip()},
            "regex",
            0.70,
        )

    timer_match = re.search(r"\b(?:start|set)\s+(?:a\s+)?timer\s+(?:for\s+)?(.+)", text)
    if timer_match:
        return _plan_from_tool(utterance, "start_timer", "start_timer", {"duration": timer_match.group(1).strip()}, "regex", 0.70)

    if re.search(r"\b(?:what(?:s| is)\s+the\s+time|what\s+time\s+is\s+it|tell\s+me\s+the\s+time|current\s+time)\b", text):
        return _plan_from_tool(utterance, "get_time", "get_system_status", {"category": "time"}, "regex", 0.90)

    if re.search(r"\b(?:what(?:s| is)\s+(?:today(?:s)?|the)\s+date|what\s+date\s+is\s+it|todays\s+date|current\s+date|what\s+day\s+is\s+it)\b", text):
        return _plan_from_tool(utterance, "get_date", "get_system_status", {"category": "date"}, "regex", 0.90)

    if re.search(r"\b(?:battery|charge)\b", text) and re.search(r"\b(?:status|level|left|remaining|percent|percentage|how\s+much|check|show)\b", text):
        return _plan_from_tool(utterance, "get_battery", "get_system_status", {"category": "battery"}, "regex", 0.86)

    if re.search(r"\b(?:storage|disk\s+space|drive\s+space)\b", text) and re.search(r"\b(?:status|left|remaining|free|available|check|show|how\s+much)\b", text):
        return _plan_from_tool(utterance, "get_storage", "get_system_status", {"category": "storage"}, "regex", 0.84)

    if re.search(r"\b(?:system|computer|pc)\s+(?:information|info|status|specs|specifications)\b", text):
        return _plan_from_tool(utterance, "get_system_info", "get_system_status", {"category": "system"}, "regex", 0.86)

    if re.search(r"\b(?:next\s+(?:song|track)|skip\s+(?:this\s+)?(?:song|track)|play\s+the\s+next\s+(?:song|track))\b", text):
        return _plan_from_tool(utterance, "next_track", "next_media_track", {}, "regex", 0.88)

    if re.search(r"\b(?:previous\s+(?:song|track)|last\s+(?:song|track)|go\s+back\s+to\s+the\s+previous\s+(?:song|track)|play\s+the\s+previous\s+(?:song|track))\b", text):
        return _plan_from_tool(utterance, "previous_track", "previous_media_track", {}, "regex", 0.88)

    if re.search(r"\b(?:pause|stop)\s+(?:the\s+)?(?:music|audio|media|playback|song|spotify)\b", text):
        return _plan_from_tool(utterance, "pause_media", "pause_media", {"action": "pause"}, "regex", 0.86)

    if re.search(r"\b(?:resume|continue)\s+(?:the\s+)?(?:music|audio|media|playback|song|spotify)\b", text):
        return _plan_from_tool(utterance, "resume_media", "pause_media", {"action": "play"}, "regex", 0.86)

    switch_app_match = re.search(r"^(?:switch|go|change|tab)\s+(?:back\s+)?to\s+(?:the\s+)?(?P<app>[a-z0-9 ._-]+?)(?:\s+app)?$", text)
    if switch_app_match:
        return _plan_from_tool(utterance, "switch_app", "switch_application", {"app": switch_app_match.group("app").strip()}, "regex", 0.80)

    close_app_match = re.search(r"^(?:close|exit|quit)\s+(?:the\s+)?(?P<app>[a-z0-9 ._-]+?)(?:\s+app)?$", text)
    if close_app_match:
        return _plan_from_tool(utterance, "close_app", "close_application", {"app": close_app_match.group("app").strip()}, "regex", 0.80)

    if re.search(r"\b(?:lock\s+(?:my|the)\s+(?:computer|pc|screen)|lock\s+screen)\b", text):
        return _plan_from_tool(utterance, "lock_screen", "lock_screen", {}, "regex", 0.86)

    if "screenshot" in text:
        return _plan_from_tool(utterance, "take_screenshot", "take_screenshot", {}, "regex", 0.70)

    information_patterns = (
        r"^(?:gather|collect)\s+(?:(?:some|the)\s+)?(?:information|info|details|facts|research)\s+(?:on|about|for)\s+(.+)$",
        r"^(?:research|investigate|look\s+into)\s+(.+)$",
        r"^(?:find|fetch|get|give\s+me)\s+(?:some\s+)?(?:information|info|details|facts)\s+(?:on|about|for)\s+(.+)$",
        r"^tell\s+me\s+more\s+about\s+(.+)$",
    )
    for pattern in information_patterns:
        information_match = re.match(pattern, text)
        if information_match:
            query = information_match.group(1).strip()
            if query:
                return _plan_from_tool(utterance, "search_web", "search_web", {"query": query}, "regex", 0.76)

    web_search_match = re.search(r"\b(?:search|look up|google)\s+(?:the\s+)?(?:web|internet|online|google)?\s*(?:for\s+)?(.+)", text)
    if web_search_match and re.search(r"\b(?:web|internet|online|google)\b", text):
        query = web_search_match.group(1).strip()
        if query and query not in {"web", "internet", "online", "google"}:
            return _plan_from_tool(utterance, "search_web", "search_web", {"query": query}, "regex", 0.70)

    spotify_match = re.search(
        r"\b(?:play|stream)\s+(?:the\s+song\s+|song\s+|music\s+|track\s+)?(.+?)(?:\s+(?:on|through|in)\s+spotify)?$",
        text,
    )
    if spotify_match and ("spotify" in text or re.search(r"\b(?:play|stream)\b", text)):
        query = re.sub(r"\s+(?:on|through|in)\s+spotify$", "", spotify_match.group(1).strip())
        if query and query != "spotify":
            return _plan_from_tool(utterance, "play_music", "play_music", {"query": query}, "regex", 0.70)

    copy_match = re.search(r"\bcopy\s+(.+)\s+to\s+(?:the\s+)?clipboard", text)
    if copy_match:
        return _plan_from_tool(utterance, "copy_clipboard", "copy_to_clipboard", {"text": copy_match.group(1).strip()}, "regex", 0.68)

    if "read clipboard" in text or "show clipboard" in text:
        return _plan_from_tool(utterance, "read_clipboard", "read_clipboard", {}, "regex", 0.68)

    open_folder_match = re.search(r"\bopen\s+(?:folder\s+)?(?:my\s+)?(downloads|documents|desktop|pictures|music|videos)\b", text)
    if open_folder_match:
        return _plan_from_tool(utterance, "open_folder", "open_folder", {"folder": open_folder_match.group(1).title()}, "regex", 0.70)

    open_terminal_match = re.search(r"\bopen\s+(terminal|windows terminal|command prompt|cmd|powershell)\b", text)
    if open_terminal_match:
        return _plan_from_tool(
            utterance,
            "open_terminal",
            "open_terminal",
            {"terminal_type": open_terminal_match.group(1).strip()},
            "regex",
            0.70,
        )

    open_app_match = re.search(r"\b(?:open|launch|start|run|bring up|pull up|show me)\s+(?:the\s+)?([a-z0-9 ._-]+?)(?:\s+app)?$", text)
    if open_app_match:
        app = open_app_match.group(1).strip()
        return _plan_from_tool(utterance, "open_app", "open_application", {"app": app}, "regex", 0.68)

    search_match = re.search(r"\b(?:find|search|look for)\s+(.+)", text)
    if search_match:
        query = search_match.group(1).strip()
        return _plan_from_tool(utterance, "search_files", "search_files", {"query": query}, "regex", 0.64)

    delete_match = re.search(r"\bdelete\s+(.+)", text)
    if delete_match:
        file_name = delete_match.group(1).strip()
        return _plan_from_tool(utterance, "delete_file", "delete_file", {"file_name": file_name}, "regex", 0.63)

    return _plan_from_tool(
        utterance,
        "unsupported_request",
        "unsupported_request",
        {"reason": "No safe tool matched this command."},
        "fallback",
        0.0,
    )


def _plan_from_tool(
    utterance: str,
    intent: str,
    tool_name: str,
    arguments: dict[str, Any],
    source: str,
    confidence: float,
) -> Plan:
    spec = get_tool_spec(tool_name)
    risk_level = spec.risk_level if spec else RiskLevel.BLOCKED
    requires_confirmation = spec.requires_confirmation if spec else True
    return Plan(utterance, intent, ToolCall(tool_name, arguments), risk_level, requires_confirmation, source, confidence)


def clamp(value: int, minimum: int, maximum: int) -> int:
    return max(minimum, min(maximum, value))


def _normalize_app_alias_words(text: str) -> str:
    replacements = {
        "notes app": "notepad",
        "note app": "notepad",
        "text editor": "notepad",
        "basic text editor": "notepad",
    }
    value = text
    for source, target in sorted(replacements.items(), key=lambda item: len(item[0]), reverse=True):
        value = re.sub(rf"\b{re.escape(source)}\b", target, value)
    return value


def _clean_app_write_content(value: str) -> str:
    return re.sub(r"\s+(?:in|inside|into)\s+(?:it|there|notepad)$", "", value.strip()).strip()


def _calculation_plan(utterance: str) -> Plan | None:
    value = " ".join(utterance.strip().split())
    explicit = re.match(r"^(?:please\s+)?(?:calculate|compute|work\s+out|solve)\s+(?P<expression>.+?)[?]?$", value, flags=re.IGNORECASE)
    if explicit:
        expression = explicit.group("expression").strip()
        if expression:
            return _plan_from_tool(utterance, "calculate", "calculate", {"expression": expression}, "regex", 0.92)

    question = re.match(r"^(?:what(?:'s|\s+is))\s+(?P<expression>.+?)[?]?$", value, flags=re.IGNORECASE)
    if question:
        expression = question.group("expression").strip()
        if _looks_like_arithmetic_expression(expression):
            return _plan_from_tool(utterance, "calculate", "calculate", {"expression": expression}, "regex", 0.88)
    return None


def _looks_like_arithmetic_expression(value: str) -> bool:
    return bool(
        re.search(r"\d", value)
        and re.search(
            r"(?:[+*/%^]|\s-\s|\bplus\b|\bminus\b|\btimes\b|\bmultiplied\b|\bdivided\b|\bpercent\b|\bsquare\s+root\b)",
            value,
            flags=re.IGNORECASE,
        )
    )


def _note_plan(utterance: str) -> Plan | None:
    value = " ".join(utterance.strip().split())
    append_match = re.match(
        r"^(?:please\s+)?(?:append|add)\s+(?:that\s+)?(?P<content>.+?)\s+to\s+(?:the\s+)?note\s+(?P<title>.+?)[.]?$",
        value,
        flags=re.IGNORECASE,
    )
    if append_match:
        title = _strip_wrapping_quotes(append_match.group("title").strip(" ."))
        content = _strip_wrapping_quotes(append_match.group("content").strip())
        if title and content:
            return _plan_from_tool(utterance, "append_note", "append_to_note", {"title": title, "content": content}, "regex", 0.86)

    create_with_content = re.match(
        r"^(?:please\s+)?(?:create|make)\s+(?:a\s+)?note\s+(?:called|named)\s+"
        r"(?P<title>.+?)\s+(?:with|containing|that\s+says|and\s+(?:add|write|put))\s+(?P<content>.+?)[.]?$",
        value,
        flags=re.IGNORECASE,
    )
    if create_with_content:
        title = _strip_wrapping_quotes(create_with_content.group("title"))
        content = _strip_wrapping_quotes(create_with_content.group("content"))
        if title and content:
            return _plan_from_tool(utterance, "create_note", "create_note", {"title": title, "content": content}, "regex", 0.88)

    create_match = re.match(
        r"^(?:please\s+)?(?:create|make)\s+(?:a\s+)?note(?:\s+(?:called|named))?\s+(?P<title>.+?)[.]?$",
        value,
        flags=re.IGNORECASE,
    )
    if create_match:
        title = _strip_wrapping_quotes(create_match.group("title").strip(" ."))
        if title:
            return _plan_from_tool(utterance, "create_note", "create_note", {"title": title, "content": ""}, "regex", 0.82)

    quick_match = re.match(
        r"^(?:please\s+)?(?:jot\s+(?:this\s+)?down|take\s+(?:a\s+)?note|note\s+this)(?:\s+that)?\s*[:,-]?\s*(?P<content>.+)$",
        value,
        flags=re.IGNORECASE,
    )
    if quick_match:
        content = _strip_wrapping_quotes(quick_match.group("content").strip())
        if content:
            return _plan_from_tool(utterance, "create_note", "create_note", {"title": "quick note", "content": content}, "regex", 0.82)
    return None


def _file_operation_plan(utterance: str) -> Plan | None:
    value = " ".join(utterance.strip().split())
    rename_match = re.match(r"^(?:please\s+)?rename\s+(?P<old>.+?)\s+to\s+(?P<new>.+?)$", value, flags=re.IGNORECASE)
    if rename_match:
        old_name = _strip_wrapping_quotes(rename_match.group("old").strip())
        new_name = _strip_wrapping_quotes(rename_match.group("new").strip())
        if old_name and new_name:
            return _plan_from_tool(
                utterance,
                "rename_file",
                "rename_file",
                {"old_name": old_name, "new_name": new_name},
                "regex",
                0.90,
            )

    move_match = re.match(r"^(?:please\s+)?move\s+(?P<file>.+?)\s+to\s+(?P<destination>.+?)$", value, flags=re.IGNORECASE)
    if move_match:
        file_name = _strip_wrapping_quotes(move_match.group("file").strip())
        destination = _strip_wrapping_quotes(move_match.group("destination").strip())
        if file_name and destination:
            return _plan_from_tool(
                utterance,
                "move_file",
                "move_file",
                {"file_name": file_name, "destination": destination},
                "regex",
                0.88,
            )

    folder_match = re.match(
        r"^(?:please\s+)?(?:create|make)\s+(?:a\s+)?(?:folder|directory)(?:\s+(?:called|named))?\s+"
        r"(?P<folder>.+?)(?:\s+(?:in|inside|under)\s+(?P<parent>.+))?$",
        value,
        flags=re.IGNORECASE,
    )
    if folder_match:
        folder = _strip_wrapping_quotes(folder_match.group("folder").strip())
        parent = _strip_wrapping_quotes((folder_match.group("parent") or "").strip())
        arguments = {"folder": folder}
        if parent:
            arguments["parent"] = parent
        if folder:
            return _plan_from_tool(utterance, "create_folder", "create_folder", arguments, "regex", 0.84)

    open_file_match = re.match(
        r"^(?:please\s+)?(?:open|launch|show)\s+(?:the\s+)?(?:file\s+)?(?P<file>.+\.[a-z0-9]{1,10})$",
        value,
        flags=re.IGNORECASE,
    )
    if open_file_match:
        file_name = _strip_wrapping_quotes(open_file_match.group("file").strip())
        return _plan_from_tool(utterance, "open_file", "open_file", {"file_name": file_name}, "regex", 0.86)
    return None


def _file_search_plan(utterance: str) -> Plan | None:
    value = " ".join(utterance.strip().split())
    type_aliases = {
        "pdf": "pdf",
        "text": "txt",
        "txt": "txt",
        "word": "docx",
        "excel": "xlsx",
        "powerpoint": "pptx",
        "image": "jpg",
        "python": "py",
    }
    type_match = re.match(
        r"^(?:please\s+)?(?:find|search\s+for|look\s+for)\s+(?:all\s+)?"
        r"(?P<type>pdf|text|txt|word|excel|powerpoint|image|python)\s+files?"
        r"(?:\s+(?:named|called|matching|containing)\s+(?P<query>.+?))?"
        r"(?:\s+(?:in|inside|under)\s+(?P<folder>.+))?$",
        value,
        flags=re.IGNORECASE,
    )
    if type_match:
        arguments = {
            "query": _strip_wrapping_quotes((type_match.group("query") or "*").strip()),
            "file_type": type_aliases[type_match.group("type").lower()],
        }
        folder = _strip_wrapping_quotes((type_match.group("folder") or "").strip())
        if folder:
            arguments["folder"] = folder
        return _plan_from_tool(utterance, "search_files", "search_files", arguments, "regex", 0.86)

    named_match = re.match(
        r"^(?:please\s+)?(?:find|search\s+for|look\s+for)\s+(?:the\s+)?(?:file|document)\s+"
        r"(?:called|named)?\s*(?P<query>.+?)(?:\s+in\s+(?P<folder>.+))?$",
        value,
        flags=re.IGNORECASE,
    )
    if named_match:
        query = _strip_wrapping_quotes(named_match.group("query").strip())
        arguments = {"query": query}
        folder = _strip_wrapping_quotes((named_match.group("folder") or "").strip())
        if folder:
            arguments["folder"] = folder
        return _plan_from_tool(utterance, "search_files", "search_files", arguments, "regex", 0.82)

    computer_match = re.match(
        r"^(?:please\s+)?(?:find|search)\s+(?:my\s+)?(?:computer|pc|files)\s+for\s+(?P<query>.+)$",
        value,
        flags=re.IGNORECASE,
    )
    if computer_match:
        query = _strip_wrapping_quotes(computer_match.group("query").strip())
        return _plan_from_tool(utterance, "search_files", "search_files", {"query": query}, "regex", 0.80)
    return None


def _draft_email_plan(utterance: str) -> Plan | None:
    value = " ".join(utterance.strip().split())
    match = re.match(
        r"^(?:please\s+)?(?:draft|compose|write)\s+(?:an?\s+)?email\s+to\s+(?P<recipient>.+?)"
        r"(?:\s+(?:with\s+(?:the\s+)?subject|about)\s+(?P<subject>.+?))?"
        r"(?:\s+(?:saying|that\s+says|with\s+(?:the\s+)?message)\s+(?P<message>.+))?$",
        value,
        flags=re.IGNORECASE,
    )
    if not match:
        return None
    recipient = _strip_wrapping_quotes(match.group("recipient").strip())
    arguments: dict[str, Any] = {"recipient": recipient}
    subject = _strip_wrapping_quotes((match.group("subject") or "").strip())
    message = _strip_wrapping_quotes((match.group("message") or "").strip())
    if subject:
        arguments["subject"] = subject
    if message:
        arguments["message"] = message
    if recipient:
        return _plan_from_tool(utterance, "draft_email", "draft_email", arguments, "regex", 0.86)
    return None


_WEBSITE_ALIASES = {
    "amazon": "amazon",
    "gmail": "gmail",
    "github": "github",
    "google": "google",
    "google maps": "google maps",
    "linkedin": "linkedin",
    "netflix": "netflix",
    "reddit": "reddit",
    "stack overflow": "stack overflow",
    "youtube": "youtube",
}


def _website_plan(utterance: str) -> Plan | None:
    value = " ".join(utterance.strip().split()).rstrip(" .!?")
    site_pattern = "|".join(re.escape(site) for site in sorted(_WEBSITE_ALIASES, key=len, reverse=True))
    compound = re.match(
        rf"^(?:please\s+)?(?:open|visit|go\s+to|launch)\s+(?:the\s+)?(?P<site>{site_pattern})\s+"
        r"(?:and\s+then|then|and)\s+(?P<action>search(?:\s+for)?|look\s+up|find|play|watch)\s+(?P<query>.+)$",
        value,
        flags=re.IGNORECASE,
    )
    if compound:
        site = _WEBSITE_ALIASES[compound.group("site").lower()]
        action = compound.group("action").lower()
        raw_query = compound.group("query").strip()
        if site == "youtube" and action in {"play", "watch"}:
            raw_query = re.sub(r"[\s,]+please$", "", raw_query, flags=re.IGNORECASE)
        query = _strip_wrapping_quotes(raw_query)
        if query:
            if site == "youtube" and action in {"play", "watch"}:
                return _plan_from_tool(utterance, "play_youtube_video", "play_youtube_video", {"query": query}, "regex", 0.94)
            return _plan_from_tool(utterance, "open_website", "open_website", {"site": site, "query": query}, "regex", 0.91)

    youtube_play = re.match(
        r"^(?:please\s+)?(?:play|watch)\s+(?P<query>.+?)\s+(?:on|in|from|through)\s+youtube(?:[\s,]+please)?$",
        value,
        flags=re.IGNORECASE,
    )
    if youtube_play:
        query = _strip_wrapping_quotes(youtube_play.group("query").strip())
        if query:
            return _plan_from_tool(utterance, "play_youtube_video", "play_youtube_video", {"query": query}, "regex", 0.94)

    search_patterns = (
        rf"^(?:please\s+)?(?:search|look\s+up|find)\s+(?:on\s+)?(?P<site>{site_pattern})\s+(?:for\s+)?(?P<query>.+)$",
        rf"^(?:please\s+)?(?:search|look\s+up|find)\s+(?:for\s+)?(?P<query>.+?)\s+on\s+(?P<site>{site_pattern})$",
    )
    for pattern in search_patterns:
        match = re.match(pattern, value, flags=re.IGNORECASE)
        if match:
            site = _WEBSITE_ALIASES[match.group("site").lower()]
            query = _strip_wrapping_quotes(match.group("query").strip())
            if query:
                return _plan_from_tool(utterance, "open_website", "open_website", {"site": site, "query": query}, "regex", 0.88)

    open_site = re.match(
        rf"^(?:please\s+)?(?:open|visit|go\s+to|bring\s+up)\s+(?:the\s+)?(?P<site>{site_pattern})(?:\s+(?:website|site))?$",
        value,
        flags=re.IGNORECASE,
    )
    if open_site:
        site = _WEBSITE_ALIASES[open_site.group("site").lower()]
        return _plan_from_tool(utterance, "open_website", "open_website", {"site": site}, "regex", 0.88)

    explicit_url = re.match(
        r"^(?:please\s+)?(?:open|visit|go\s+to)\s+(?P<site>(?:https?://|www\.)?[a-z0-9][a-z0-9.-]+\."
        r"(?:com|org|net|io|ai|dev|app|co|in|me|tv|edu|gov)(?:/\S*)?)$",
        value,
        flags=re.IGNORECASE,
    )
    if explicit_url:
        return _plan_from_tool(
            utterance,
            "open_website",
            "open_website",
            {"site": explicit_url.group("site")},
            "regex",
            0.86,
        )
    return None


def _whatsapp_plan(utterance: str) -> Plan | None:
    value = " ".join(utterance.strip().split())
    if not value or "whatsapp" not in value.lower():
        return None

    patterns = (
        re.compile(
            r"^(?:please\s+)?(?:open\s+whatsapp\s+and\s+)?"
            r"(?:send\s+(?:a\s+)?(?:whatsapp\s+)?message|text|message)\s+"
            r"(?:to\s+)?(?P<recipient>.+?)\s+(?:on\s+whatsapp\s+)?"
            r"(?:saying|that|with\s+(?:the\s+)?message)\s+(?P<message>.+)$",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"^(?:please\s+)?(?:open\s+whatsapp\s+and\s+)?send\s+"
            r"(?P<message>.+?)\s+to\s+(?P<recipient>.+?)"
            r"(?:\s+(?:on|through)\s+whatsapp)?$",
            flags=re.IGNORECASE,
        ),
        re.compile(
            r"^(?:please\s+)?(?:open\s+whatsapp\s+and\s+)?(?:whatsapp|text|message)[\s,:-]+"
            r"(?P<recipient>[^:,-]+?)\s*[:,-]\s*(?P<message>.+)$",
            flags=re.IGNORECASE,
        ),
    )
    for pattern in patterns:
        match = pattern.match(value)
        if not match:
            continue
        recipient = _strip_wrapping_quotes(match.group("recipient"))
        message = _clean_whatsapp_message(match.group("message"))
        if recipient and message:
            return _plan_from_tool(
                utterance,
                "send_whatsapp_message",
                "send_whatsapp_message",
                {"recipient": recipient, "message": message},
                "regex",
                0.92,
            )

    if re.search(r"\b(?:send|text|message)\b", value, flags=re.IGNORECASE):
        return _plan_from_tool(
            utterance,
            "clarify_intent",
            "ask_clarification",
            {"question": "Who should I message on WhatsApp, and what exact text should I send?"},
            "regex",
            0.72,
        )
    return None


def _clean_whatsapp_message(value: str) -> str:
    cleaned = re.sub(
        r"\s+and\s+(?:send|deliver)(?:\s+(?:it|that|the\s+message))?$",
        "",
        value.strip(),
        flags=re.IGNORECASE,
    ).strip()
    return _strip_wrapping_quotes(cleaned)


def _strip_wrapping_quotes(value: str) -> str:
    cleaned = value.strip()
    if len(cleaned) >= 2 and cleaned[0] == cleaned[-1] and cleaned[0] in {'"', "'"}:
        return cleaned[1:-1].strip()
    return cleaned

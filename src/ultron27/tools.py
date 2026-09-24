from __future__ import annotations

from typing import Any

from .models import RiskLevel, ToolCall, ToolSpec, ValidationResult


TOOL_SPECS: dict[str, ToolSpec] = {
    "append_to_note": ToolSpec("append_to_note", "Append text to an existing note.", RiskLevel.LOW, ("title", "content")),
    "assistant_reply": ToolSpec("assistant_reply", "Reply conversationally without executing an OS action.", RiskLevel.NONE, ("message",)),
    "ask_clarification": ToolSpec("ask_clarification", "Ask the user for missing information.", RiskLevel.NONE, ("question",)),
    "calculate": ToolSpec("calculate", "Evaluate a bounded arithmetic expression locally.", RiskLevel.NONE, ("expression",)),
    "check_calendar": ToolSpec("check_calendar", "Check calendar events for a date.", RiskLevel.LOW, ("date",)),
    "close_application": ToolSpec("close_application", "Close an application.", RiskLevel.MEDIUM, ("app",)),
    "control_smart_home_device": ToolSpec("control_smart_home_device", "Switch a smart-home device on or off.", RiskLevel.MEDIUM, ("device", "state"), ("room",)),
    "create_calendar_event": ToolSpec("create_calendar_event", "Create a calendar event draft.", RiskLevel.MEDIUM, ("title", "date", "time"), requires_confirmation=True),
    "create_folder": ToolSpec("create_folder", "Create a folder inside an approved safe root.", RiskLevel.LOW, ("folder",), ("parent",)),
    "create_note": ToolSpec("create_note", "Create a local note.", RiskLevel.LOW, ("title",), ("content",)),
    "copy_to_clipboard": ToolSpec("copy_to_clipboard", "Copy text to the system clipboard.", RiskLevel.LOW, ("text",)),
    "delete_file": ToolSpec("delete_file", "Delete a file after confirmation.", RiskLevel.HIGH, ("file_name",), ("mode",), requires_confirmation=True),
    "draft_email": ToolSpec("draft_email", "Open an email draft without sending it.", RiskLevel.MEDIUM, ("recipient",), ("subject", "message"), requires_confirmation=True),
    "get_system_status": ToolSpec("get_system_status", "Read local time, date, battery, storage, or system information.", RiskLevel.NONE, ("category",)),
    "lock_screen": ToolSpec("lock_screen", "Lock the current user session.", RiskLevel.MEDIUM, requires_confirmation=True),
    "move_file": ToolSpec("move_file", "Move a file after confirmation.", RiskLevel.MEDIUM, ("file_name", "destination"), requires_confirmation=True),
    "mute_system_volume": ToolSpec("mute_system_volume", "Mute or unmute system audio.", RiskLevel.LOW, ("mute",)),
    "next_media_track": ToolSpec("next_media_track", "Skip to the next media track.", RiskLevel.LOW),
    "open_application": ToolSpec("open_application", "Open an installed application.", RiskLevel.LOW, ("app",)),
    "open_file": ToolSpec("open_file", "Open a file by name.", RiskLevel.MEDIUM, ("file_name",)),
    "open_folder": ToolSpec("open_folder", "Open a folder by name.", RiskLevel.LOW, ("folder",)),
    "open_terminal": ToolSpec("open_terminal", "Open the default terminal.", RiskLevel.MEDIUM, ("terminal_type",)),
    "open_website": ToolSpec("open_website", "Open a validated website or site search in the default browser.", RiskLevel.LOW, ("site",), ("query",)),
    "pause_media": ToolSpec("pause_media", "Pause media playback.", RiskLevel.LOW, ("action",)),
    "play_music": ToolSpec("play_music", "Play music for a query.", RiskLevel.LOW, ("query",)),
    "play_youtube_video": ToolSpec(
        "play_youtube_video",
        "Resolve and load a YouTube video in ULTRON's in-app mini-player.",
        RiskLevel.LOW,
        ("query",),
    ),
    "previous_media_track": ToolSpec("previous_media_track", "Go to the previous media track.", RiskLevel.LOW),
    "read_clipboard": ToolSpec("read_clipboard", "Read text from the system clipboard.", RiskLevel.LOW),
    "rename_file": ToolSpec("rename_file", "Rename a file after confirmation.", RiskLevel.MEDIUM, ("old_name", "new_name"), requires_confirmation=True),
    "restart_system": ToolSpec("restart_system", "Restart the computer.", RiskLevel.HIGH, requires_confirmation=True),
    "run_script": ToolSpec("run_script", "Run a preapproved local script.", RiskLevel.HIGH, ("script_name",), requires_confirmation=True),
    "search_files": ToolSpec("search_files", "Search local files.", RiskLevel.LOW, ("query",), ("file_type", "folder")),
    "search_web": ToolSpec("search_web", "Search the web.", RiskLevel.LOW, ("query",)),
    "research_topic": ToolSpec("research_topic", "Gather web evidence and source links about a topic.", RiskLevel.LOW, ("query",)),
    "send_email": ToolSpec("send_email", "Send an email after confirmation.", RiskLevel.HIGH, ("recipient", "message"), requires_confirmation=True),
    "send_whatsapp_message": ToolSpec(
        "send_whatsapp_message",
        "Send a WhatsApp message to an exact phone number or verified contact.",
        RiskLevel.HIGH,
        ("recipient", "message"),
        requires_confirmation=True,
    ),
    "set_reminder": ToolSpec("set_reminder", "Set a reminder.", RiskLevel.LOW, ("task", "time")),
    "set_screen_brightness": ToolSpec("set_screen_brightness", "Set screen brightness percentage.", RiskLevel.LOW, ("level",), numeric_ranges={"level": (0, 100)}),
    "adjust_screen_brightness": ToolSpec("adjust_screen_brightness", "Adjust screen brightness.", RiskLevel.LOW, ("direction", "delta"), numeric_ranges={"delta": (1, 100)}),
    "set_smart_home_device_value": ToolSpec("set_smart_home_device_value", "Set a smart-home device value.", RiskLevel.MEDIUM, ("device", "value"), ("room", "unit")),
    "set_system_volume": ToolSpec("set_system_volume", "Set speaker volume percentage.", RiskLevel.LOW, ("level",), numeric_ranges={"level": (0, 100)}),
    "adjust_system_volume": ToolSpec("adjust_system_volume", "Adjust speaker volume.", RiskLevel.LOW, ("direction", "delta"), numeric_ranges={"delta": (1, 100)}),
    "shutdown_system": ToolSpec("shutdown_system", "Shut down the computer.", RiskLevel.HIGH, requires_confirmation=True),
    "start_timer": ToolSpec("start_timer", "Start a timer.", RiskLevel.LOW, ("duration",)),
    "switch_application": ToolSpec("switch_application", "Switch focus to an application.", RiskLevel.LOW, ("app",)),
    "take_screenshot": ToolSpec("take_screenshot", "Take a screenshot.", RiskLevel.LOW),
    "toggle_bluetooth": ToolSpec("toggle_bluetooth", "Enable or disable Bluetooth.", RiskLevel.MEDIUM, ("enabled",), requires_confirmation=True),
    "toggle_wifi": ToolSpec("toggle_wifi", "Enable or disable Wi-Fi.", RiskLevel.MEDIUM, ("enabled",), requires_confirmation=True),
    "write_text_in_application": ToolSpec("write_text_in_application", "Open an approved app and paste text into it.", RiskLevel.LOW, ("app", "text")),
    "unsupported_request": ToolSpec("unsupported_request", "Refuse an unsafe or unsupported request.", RiskLevel.NONE, ("reason",)),
}


def get_tool_spec(name: str) -> ToolSpec | None:
    return TOOL_SPECS.get(name)


def validate_tool_call(call: ToolCall) -> ValidationResult:
    spec = get_tool_spec(call.name)
    if spec is None:
        return ValidationResult(False, (f"Unknown tool: {call.name}",))

    errors: list[str] = []
    for key in spec.required:
        if key not in call.arguments:
            errors.append(f"Missing required argument: {key}")

    allowed = set(spec.required) | set(spec.optional)
    extras = set(call.arguments) - allowed
    if extras:
        errors.append(f"Unexpected arguments: {', '.join(sorted(extras))}")

    for key, (minimum, maximum) in spec.numeric_ranges.items():
        if key not in call.arguments:
            continue
        value = call.arguments[key]
        if not isinstance(value, int) or isinstance(value, bool):
            errors.append(f"{key} must be an integer")
        elif not minimum <= value <= maximum:
            errors.append(f"{key} must be between {minimum} and {maximum}")

    _validate_basic_types(call.arguments, errors)
    return ValidationResult(not errors, tuple(errors))


def _validate_basic_types(arguments: dict[str, Any], errors: list[str]) -> None:
    for key, value in arguments.items():
        if key in {"mute", "enabled"} and not isinstance(value, bool):
            errors.append(f"{key} must be a boolean")
        elif key in {"level", "delta", "value"}:
            if not isinstance(value, (int, float)) or isinstance(value, bool):
                errors.append(f"{key} must be numeric")
        elif value is not None and key not in {"level", "delta", "value", "mute", "enabled"} and not isinstance(value, str):
            errors.append(f"{key} must be a string")

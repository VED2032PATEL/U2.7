from __future__ import annotations

import ast
import math
import os
import platform
import re
import shutil
import subprocess
import sys
import time
import urllib.parse
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

from .models import ToolCall, ToolResult
from .spotify import SpotifyWebPlayer
from .youtube import YouTubeLookupError, normalize_youtube_query, resolve_first_youtube_video, youtube_search_url
from .windows_executor import (
    WindowsAutomationAdapter,
    is_windows,
    merge_windows_app_aliases,
    merge_windows_terminal_aliases,
)


DEFAULT_APP_ALIASES = merge_windows_app_aliases()

WEBSITE_URLS: dict[str, tuple[str, str | None]] = {
    "amazon": ("https://www.amazon.com", "https://www.amazon.com/s?k={query}"),
    "gmail": ("https://mail.google.com", "https://mail.google.com/mail/u/0/#search/{query}"),
    "github": ("https://github.com", "https://github.com/search?q={query}"),
    "google": ("https://www.google.com", "https://www.google.com/search?q={query}"),
    "google maps": ("https://www.google.com/maps", "https://www.google.com/maps/search/?api=1&query={query}"),
    "linkedin": ("https://www.linkedin.com", "https://www.linkedin.com/search/results/all/?keywords={query}"),
    "netflix": ("https://www.netflix.com", "https://www.netflix.com/search?q={query}"),
    "reddit": ("https://www.reddit.com", "https://www.reddit.com/search/?q={query}"),
    "stack overflow": ("https://stackoverflow.com", "https://stackoverflow.com/search?q={query}"),
    "youtube": ("https://www.youtube.com", "https://www.youtube.com/results?search_query={query}"),
}


class Executor:
    def __init__(
        self,
        dry_run: bool = True,
        workspace: Path | None = None,
        safe_roots: Iterable[Path] | None = None,
        app_aliases: dict[str, str] | None = None,
        screenshot_dir: Path | None = None,
        whatsapp_contacts: dict[str, str] | None = None,
    ):
        self.dry_run = dry_run
        self.workspace = (workspace or Path.cwd()).resolve()
        self.safe_roots = tuple(_resolve_safe_roots(safe_roots, self.workspace))
        self.app_aliases = merge_windows_app_aliases(app_aliases)
        self.terminal_aliases = merge_windows_terminal_aliases(app_aliases)
        self.screenshot_dir = _resolve_under_workspace(screenshot_dir or Path(".ultron/screenshots"), self.workspace)
        self.whatsapp_contacts = dict(whatsapp_contacts or {})
        self.windows = WindowsAutomationAdapter(dry_run=dry_run, screenshot_dir=self.screenshot_dir)

    def execute(self, call: ToolCall) -> ToolResult:
        handler = getattr(self, f"_handle_{call.name}", None)
        if handler is None:
            return self._generic(call)
        return handler(call)

    def _generic(self, call: ToolCall) -> ToolResult:
        if self.dry_run:
            return ToolResult("dry_run", f"Would run {call.name}", data={"arguments": call.arguments})
        return ToolResult("not_implemented", f"{call.name} needs an OS-specific executor.", data={"arguments": call.arguments})

    def _handle_open_application(self, call: ToolCall) -> ToolResult:
        app = str(call.arguments["app"])
        if is_windows():
            return self.windows.open_application(app, self.app_aliases)
        target = self.app_aliases.get(app.lower())
        if target is None:
            return ToolResult("blocked", f"Application is not in the approved alias registry: {app}", data={"app": app})
        if self.dry_run:
            return ToolResult("dry_run", f"Would open application: {app}", data={"app": app, "target": target})
        try:
            subprocess.Popen([target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            return ToolResult("error", f"Could not open application: {exc}", data={"app": app, "target": target})
        return ToolResult("success", f"Opened application: {app}", changed={"app": app, "target": target})

    def _handle_write_text_in_application(self, call: ToolCall) -> ToolResult:
        app = str(call.arguments["app"]).strip()
        text = str(call.arguments["text"])
        if not text.strip():
            return ToolResult("blocked", "There is no text to write.", data={"app": app})
        if len(text) > 4000:
            return ToolResult("blocked", "Text is too long for direct app typing. Use a note or file tool instead.", data={"app": app, "text_length": len(text)})
        if is_windows():
            return self.windows.write_text_in_application(app, text, self.app_aliases)
        return ToolResult("not_implemented", "Writing into another app needs the Windows automation adapter.", data={"app": app, "text_length": len(text)})

    def _handle_assistant_reply(self, call: ToolCall) -> ToolResult:
        message = str(call.arguments["message"]).strip()
        return ToolResult("success", message or "At your service, sir.")

    def _handle_ask_clarification(self, call: ToolCall) -> ToolResult:
        question = str(call.arguments["question"]).strip()
        return ToolResult("success", question or "Could you clarify what you want me to do?")

    def _handle_calculate(self, call: ToolCall) -> ToolResult:
        expression = str(call.arguments["expression"]).strip()
        try:
            normalized, value = _calculate_expression(expression)
        except ValueError as exc:
            return ToolResult("blocked", f"Could not calculate that safely: {exc}", data={"expression": expression})
        formatted = _format_calculation(value)
        return ToolResult(
            "success",
            f"The answer is {formatted}.",
            data={"expression": expression, "normalized_expression": normalized, "value": value},
        )

    def _handle_get_system_status(self, call: ToolCall) -> ToolResult:
        category = str(call.arguments["category"]).strip().lower()
        return _system_status(category)

    def _handle_open_website(self, call: ToolCall) -> ToolResult:
        site = str(call.arguments["site"]).strip()
        query = str(call.arguments.get("query", "")).strip()
        try:
            url, label = _website_target(site, query)
        except ValueError as exc:
            return ToolResult("blocked", str(exc), data={"site": site, "query": query})
        if self.dry_run:
            action = f"search {label} for: {query}" if query else f"open {label}"
            return ToolResult("dry_run", f"Would {action}.", data={"site": label, "query": query, "url": url})
        action = f"Opened {label} search for: {query}" if query else f"Opened {label}."
        return _open_url(url, action, {"site": label, "query": query, "url": url})

    def _handle_open_terminal(self, call: ToolCall) -> ToolResult:
        terminal_type = str(call.arguments.get("terminal_type", "default"))
        if is_windows():
            return self.windows.open_terminal(terminal_type, self.terminal_aliases)
        target = self.terminal_aliases.get(terminal_type.lower(), self.terminal_aliases.get("default", "sh"))
        if self.dry_run:
            return ToolResult("dry_run", f"Would open terminal: {terminal_type}", data={"target": target})
        try:
            subprocess.Popen([target], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except OSError as exc:
            return ToolResult("error", f"Could not open terminal: {exc}", data={"target": target})
        return ToolResult("success", f"Opened terminal: {terminal_type}", changed={"target": target})

    def _handle_search_files(self, call: ToolCall) -> ToolResult:
        query = str(call.arguments["query"]).lower()
        roots, unavailable = self._select_search_roots(call.arguments.get("folder"))
        if unavailable:
            return ToolResult(
                "blocked",
                f"Search folder is unavailable or outside configured safe roots: {call.arguments.get('folder')}",
                data={"safe_roots": [str(root) for root in self.safe_roots]},
            )
        file_type = str(call.arguments.get("file_type", "")).lower().lstrip(".")
        if self.dry_run:
            return ToolResult(
                "dry_run",
                f"Would search {len(roots)} approved folder(s) for: {query}",
                data={"roots": [str(root) for root in roots], "query": query, "file_type": file_type},
            )

        matches: list[str] = []
        seen_matches: set[str] = set()
        for root in roots:
            if not root.is_dir():
                continue
            for path in root.rglob("*"):
                if len(matches) >= 25:
                    break
                if not path.is_file():
                    continue
                if file_type and path.suffix.lower() != f".{file_type}":
                    continue
                if query in {"", "*"} or query in path.name.lower():
                    resolved_match = str(path.resolve())
                    if resolved_match not in seen_matches:
                        seen_matches.add(resolved_match)
                        matches.append(resolved_match)
            if len(matches) >= 25:
                break
        return ToolResult("success", f"Found {len(matches)} file(s).", data={"matches": matches})

    def _handle_open_file(self, call: ToolCall) -> ToolResult:
        file_name = str(call.arguments["file_name"])
        if self._is_explicit_path_outside_roots(file_name):
            return ToolResult("blocked", f"File is outside configured safe roots: {file_name}", data={"safe_roots": [str(root) for root in self.safe_roots]})
        path = self._find_file(file_name)
        if path is None:
            return ToolResult("not_found", f"Could not find file in safe roots: {file_name}", data={"safe_roots": [str(root) for root in self.safe_roots]})
        if self.dry_run:
            return ToolResult("dry_run", f"Would open file: {path.name}", data={"path": str(path)})
        if is_windows():
            return self.windows.open_path(path)
        return _open_path(path)

    def _handle_open_folder(self, call: ToolCall) -> ToolResult:
        folder = str(call.arguments["folder"])
        if self._is_explicit_path_outside_roots(folder):
            return ToolResult("blocked", f"Folder is outside configured safe roots: {folder}", data={"safe_roots": [str(root) for root in self.safe_roots]})
        path = self._find_folder(folder)
        if path is None:
            return ToolResult("not_found", f"Could not find folder in safe roots: {folder}", data={"safe_roots": [str(root) for root in self.safe_roots]})
        if self.dry_run:
            return ToolResult("dry_run", f"Would open folder: {path}", data={"path": str(path)})
        if is_windows():
            return self.windows.open_path(path)
        return _open_path(path)

    def _handle_create_folder(self, call: ToolCall) -> ToolResult:
        folder = str(call.arguments["folder"]).strip()
        parent_name = str(call.arguments.get("parent", "")).strip()
        if not _safe_folder_name(folder):
            return ToolResult("blocked", "Folder names cannot be empty, absolute, or contain path separators.", data={"folder": folder})
        parent = self._find_folder(parent_name) if parent_name else self.workspace
        if parent is None or not any(_is_relative_to(parent.resolve(), root) for root in self.safe_roots):
            return ToolResult(
                "blocked",
                f"Parent folder is unavailable or outside configured safe roots: {parent_name or self.workspace}",
                data={"safe_roots": [str(root) for root in self.safe_roots]},
            )
        target = (parent / folder).resolve()
        if not any(_is_relative_to(target, root) for root in self.safe_roots):
            return ToolResult("blocked", "The requested folder would be outside configured safe roots.", data={"path": str(target)})
        if target.exists():
            if target.is_dir():
                return ToolResult("success", f"Folder already exists: {target.name}", data={"path": str(target), "created": False})
            return ToolResult("blocked", f"A file already uses that name: {target.name}", data={"path": str(target)})
        if self.dry_run:
            return ToolResult("dry_run", f"Would create folder: {target.name}", data={"path": str(target)})
        target.mkdir()
        return ToolResult("success", f"Created folder: {target.name}", changed={"path": str(target)})

    def _handle_create_note(self, call: ToolCall) -> ToolResult:
        title = _safe_filename(str(call.arguments["title"]))
        content = str(call.arguments.get("content", ""))
        note_path = self.workspace / "notes" / f"{title}.md"
        if self.dry_run:
            return ToolResult("dry_run", f"Would create note: {note_path.name}", data={"path": str(note_path), "content": content})
        note_path.parent.mkdir(parents=True, exist_ok=True)
        note_path.write_text(content + os.linesep, encoding="utf-8")
        return ToolResult("success", f"Created note: {note_path.name}", changed={"path": str(note_path)})

    def _handle_append_to_note(self, call: ToolCall) -> ToolResult:
        title = _safe_filename(str(call.arguments["title"]))
        content = str(call.arguments["content"])
        note_path = self.workspace / "notes" / f"{title}.md"
        if self.dry_run:
            return ToolResult("dry_run", f"Would append to note: {note_path.name}", data={"path": str(note_path), "content": content})
        note_path.parent.mkdir(parents=True, exist_ok=True)
        with note_path.open("a", encoding="utf-8") as handle:
            handle.write(content + os.linesep)
        return ToolResult("success", f"Updated note: {note_path.name}", changed={"path": str(note_path)})

    def _handle_set_reminder(self, call: ToolCall) -> ToolResult:
        reminder = {
            "task": str(call.arguments["task"]),
            "time": str(call.arguments["time"]),
            "created_at": int(time.time()),
        }
        path = self.workspace / ".ultron" / "reminders.jsonl"
        if self.dry_run:
            return ToolResult("dry_run", f"Would set reminder: {reminder['task']} {reminder['time']}", data=reminder)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            import json

            handle.write(json.dumps(reminder, ensure_ascii=False, sort_keys=True) + "\n")
        return ToolResult("success", f"Reminder saved: {reminder['task']} {reminder['time']}", changed={"path": str(path), **reminder})

    def _handle_start_timer(self, call: ToolCall) -> ToolResult:
        duration = str(call.arguments["duration"]).strip()
        seconds = _parse_duration_seconds(duration)
        if seconds is None:
            return ToolResult(
                "blocked",
                "Timer duration must be between 1 second and 24 hours, for example: 10 minutes.",
                data={"duration": duration},
            )
        timer = {
            "duration": duration,
            "seconds": seconds,
            "created_at": int(time.time()),
            "due_at": int(time.time()) + seconds,
            "status": "scheduled",
        }
        path = self.workspace / ".ultron" / "timers.jsonl"
        if self.dry_run:
            return ToolResult("dry_run", f"Would start timer: {timer['duration']}", data=timer)
        if not is_windows():
            return ToolResult("not_implemented", "Timer notifications currently need the Windows adapter.", data=timer)
        try:
            notification_pid = _start_windows_timer_notification(seconds)
        except OSError as exc:
            return ToolResult("error", f"Could not start the timer notification: {exc}", data=timer)
        timer["notification_pid"] = notification_pid
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            import json

            handle.write(json.dumps(timer, ensure_ascii=False, sort_keys=True) + "\n")
        return ToolResult("success", f"Timer started for {timer['duration']}.", changed={"path": str(path), **timer})

    def _handle_search_web(self, call: ToolCall) -> ToolResult:
        query = str(call.arguments["query"]).strip()
        if not query:
            return ToolResult("blocked", "Web search needs a non-empty query.")
        url = f"https://www.google.com/search?q={urllib.parse.quote_plus(query)}"
        if self.dry_run:
            return ToolResult("dry_run", f"Would search the web for: {query}", data={"query": query, "url": url})
        return _open_url(url, f"Opened web search for: {query}", {"query": query, "url": url})

    def _handle_play_music(self, call: ToolCall) -> ToolResult:
        query = str(call.arguments["query"]).strip()
        if not query:
            return ToolResult("blocked", "Music playback needs a song, artist, or playlist name.")
        spotify_url = f"https://open.spotify.com/search/{urllib.parse.quote(query, safe='')}"
        spotify_uri = f"spotify:search:{urllib.parse.quote(query, safe='')}"
        if self.dry_run:
            return ToolResult(
                "dry_run",
                f"Would open Spotify and try to play: {query}",
                data={"query": query, "url": spotify_url, "spotify_uri": spotify_uri},
            )
        spotify = SpotifyWebPlayer.from_workspace(self.workspace)
        if spotify is not None:
            api_result = spotify.play(query)
            if api_result.status == "success":
                return api_result
            if api_result.status == "device_unavailable" and is_windows():
                activation = self.windows.activate_spotify()
                if activation.status == "success":
                    api_result = spotify.play(query)
                    if api_result.status == "success":
                        return api_result
        if is_windows():
            return self.windows.play_spotify_query(query)
        opened = _open_url(spotify_uri, f"Opened Spotify search for: {query}", {"query": query, "url": spotify_uri})
        if opened.status == "success":
            return opened
        return _open_url(spotify_url, f"Opened Spotify web search for: {query}", {"query": query, "url": spotify_url})

    def _handle_play_youtube_video(self, call: ToolCall) -> ToolResult:
        raw_query = call.arguments["query"]
        if not isinstance(raw_query, str):
            return ToolResult("blocked", "YouTube playback query must be text.", data={"query": raw_query})
        query = raw_query
        try:
            normalized = normalize_youtube_query(query)
            search_url = youtube_search_url(normalized)
        except ValueError as exc:
            return ToolResult("blocked", str(exc), data={"query": query})
        if self.dry_run:
            return ToolResult(
                "dry_run",
                f"Would resolve and load in ULTRON's YouTube mini-player: {normalized}",
                data={
                    "query": normalized,
                    "search_url": search_url,
                    "playback_target": "ultron_mini_player",
                    "playback_requested": False,
                    "playback_verified": False,
                },
            )
        try:
            video = resolve_first_youtube_video(normalized)
        except YouTubeLookupError as exc:
            return ToolResult(
                "error",
                f"Could not find a playable YouTube result for {normalized}: {exc}",
                data={
                    "query": normalized,
                    "search_url": search_url,
                    "playback_target": "ultron_mini_player",
                    "playback_requested": False,
                    "playback_verified": False,
                },
            )
        return ToolResult(
            "success",
            f"Loaded YouTube in ULTRON's mini-player: {normalized}",
            data={
                "provider": "youtube",
                "query": normalized,
                "video_id": video.video_id,
                "candidate_video_ids": list(video.candidate_ids or (video.video_id,)),
                "playback_target": "ultron_mini_player",
                "playback_requested": True,
                "playback_verified": False,
            },
        )

    def _handle_send_whatsapp_message(self, call: ToolCall) -> ToolResult:
        recipient = str(call.arguments["recipient"]).strip()
        message = str(call.arguments["message"]).strip()
        if not recipient:
            return ToolResult("blocked", "WhatsApp needs an exact recipient. Nothing was sent.")
        if not message:
            return ToolResult("blocked", "WhatsApp needs a non-empty message. Nothing was sent.", data={"recipient": recipient})
        if len(message) > 2000:
            return ToolResult(
                "blocked",
                "WhatsApp messages are limited to 2,000 characters in this automation path. Nothing was sent.",
                data={"recipient": recipient, "message_length": len(message)},
            )
        if is_windows():
            return self.windows.send_whatsapp_message(recipient, message, self.whatsapp_contacts)
        return ToolResult(
            "not_implemented",
            "WhatsApp sending currently needs the Windows automation adapter.",
            data={"recipient": recipient, "message_length": len(message)},
        )

    def _handle_take_screenshot(self, call: ToolCall) -> ToolResult:
        if is_windows():
            return self.windows.take_screenshot()
        path = self.screenshot_dir / f"screenshot-{int(time.time())}.png"
        if self.dry_run:
            return ToolResult("dry_run", f"Would save screenshot: {path}", data={"path": str(path)})
        try:
            from PIL import ImageGrab
        except ImportError:
            return ToolResult("not_implemented", "Screenshot capture needs Pillow with ImageGrab support.", data={"path": str(path)})
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            image = ImageGrab.grab()
            image.save(path)
        except Exception as exc:  # pragma: no cover - OS/display dependent
            return ToolResult("error", f"Could not capture screenshot: {exc}", data={"path": str(path)})
        return ToolResult("success", f"Screenshot saved: {path.name}", changed={"path": str(path)})

    def _handle_copy_to_clipboard(self, call: ToolCall) -> ToolResult:
        text = str(call.arguments["text"])
        if is_windows():
            return self.windows.write_clipboard(text)
        if self.dry_run:
            return ToolResult("dry_run", "Would copy text to clipboard.", data={"text_length": len(text)})
        return _write_clipboard(text)

    def _handle_read_clipboard(self, call: ToolCall) -> ToolResult:
        if is_windows():
            return self.windows.read_clipboard()
        if self.dry_run:
            return ToolResult("dry_run", "Would read clipboard text.")
        return _read_clipboard()

    def _handle_set_system_volume(self, call: ToolCall) -> ToolResult:
        level = int(call.arguments["level"])
        if is_windows():
            return self.windows.set_system_volume(level)
        if self.dry_run:
            return ToolResult("dry_run", f"Would set volume to {level}%", data={"level": level})
        return ToolResult("not_implemented", "Volume control needs an OS-specific adapter.", data={"level": level})

    def _handle_mute_system_volume(self, call: ToolCall) -> ToolResult:
        mute = bool(call.arguments["mute"])
        if is_windows():
            return self.windows.set_mute(mute)
        if self.dry_run:
            return ToolResult("dry_run", f"Would {'mute' if mute else 'unmute'} system audio.", data={"mute": mute})
        return ToolResult("not_implemented", "Mute control needs an OS-specific adapter.", data={"mute": mute})

    def _handle_set_screen_brightness(self, call: ToolCall) -> ToolResult:
        level = int(call.arguments["level"])
        if is_windows():
            return self.windows.set_screen_brightness(level)
        if self.dry_run:
            return ToolResult("dry_run", f"Would set brightness to {level}%", data={"level": level})
        return ToolResult("not_implemented", "Brightness control needs an OS-specific adapter.", data={"level": level})

    def _handle_adjust_system_volume(self, call: ToolCall) -> ToolResult:
        direction = str(call.arguments["direction"]).strip().lower()
        delta = int(call.arguments["delta"])
        if direction not in {"up", "down"}:
            return ToolResult("blocked", "Volume direction must be up or down.", data=call.arguments)
        if is_windows():
            return self.windows.adjust_system_volume(direction, delta)
        return ToolResult("not_implemented", "Relative volume adjustment needs an OS-specific adapter.", data=call.arguments)

    def _handle_adjust_screen_brightness(self, call: ToolCall) -> ToolResult:
        direction = str(call.arguments["direction"]).strip().lower()
        delta = int(call.arguments["delta"])
        if direction not in {"up", "down"}:
            return ToolResult("blocked", "Brightness direction must be up or down.", data=call.arguments)
        if is_windows():
            return self.windows.adjust_screen_brightness(direction, delta)
        return ToolResult("not_implemented", "Relative brightness adjustment needs an OS-specific adapter.", data=call.arguments)

    def _handle_pause_media(self, call: ToolCall) -> ToolResult:
        action = str(call.arguments["action"]).strip().lower()
        if action not in {"pause", "play", "toggle", "resume"}:
            return ToolResult("blocked", "Media action must be play, pause, resume, or toggle.", data=call.arguments)
        if is_windows():
            return self.windows.control_media("play" if action == "resume" else action)
        return ToolResult("not_implemented", "Media controls need an OS-specific adapter.", data=call.arguments)

    def _handle_next_media_track(self, call: ToolCall) -> ToolResult:
        if is_windows():
            return self.windows.control_media("next")
        return ToolResult("not_implemented", "Media controls need an OS-specific adapter.")

    def _handle_previous_media_track(self, call: ToolCall) -> ToolResult:
        if is_windows():
            return self.windows.control_media("previous")
        return ToolResult("not_implemented", "Media controls need an OS-specific adapter.")

    def _handle_switch_application(self, call: ToolCall) -> ToolResult:
        app = str(call.arguments["app"]).strip()
        if is_windows():
            return self.windows.switch_application(app, self.app_aliases)
        return ToolResult("not_implemented", "Switching applications needs an OS-specific adapter.", data={"app": app})

    def _handle_delete_file(self, call: ToolCall) -> ToolResult:
        file_name = str(call.arguments["file_name"])
        if self.dry_run:
            return ToolResult("dry_run", f"Would delete file after confirmation: {file_name}", data={"file_name": file_name})
        return ToolResult("not_implemented", "Destructive file deletion is intentionally not implemented in the MVP.", data=call.arguments)

    def _handle_run_script(self, call: ToolCall) -> ToolResult:
        return ToolResult("not_implemented", "Script execution requires a separate approved-script registry.", data=call.arguments)

    def _handle_draft_email(self, call: ToolCall) -> ToolResult:
        recipient = str(call.arguments["recipient"]).strip()
        subject = str(call.arguments.get("subject", "")).strip()
        message = str(call.arguments.get("message", "")).strip()
        if not _safe_email_recipient(recipient):
            return ToolResult("blocked", "The email recipient is empty or contains unsafe control characters.", data={"recipient": recipient})
        params: dict[str, str] = {}
        if subject:
            params["subject"] = subject
        if message:
            params["body"] = message
        query = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = f"mailto:{urllib.parse.quote(recipient, safe='@,; ')}"
        if query:
            url += f"?{query}"
        data = {"recipient": recipient, "subject": subject, "message_length": len(message), "send_submitted": False}
        if self.dry_run:
            return ToolResult("dry_run", f"Would open an email draft to {recipient}. Nothing would be sent.", data={**data, "url": url})
        return _open_url(url, f"Opened an email draft to {recipient}. Nothing was sent.", data)

    def _handle_send_email(self, call: ToolCall) -> ToolResult:
        return ToolResult("not_implemented", "Email sending is intentionally not implemented; use draft_email first.", data=call.arguments)

    def _handle_shutdown_system(self, call: ToolCall) -> ToolResult:
        return ToolResult("not_implemented", "Shutdown is intentionally not implemented in this prototype.", data=call.arguments)

    def _handle_restart_system(self, call: ToolCall) -> ToolResult:
        return ToolResult("not_implemented", "Restart is intentionally not implemented in this prototype.", data=call.arguments)

    def _handle_move_file(self, call: ToolCall) -> ToolResult:
        file_name = str(call.arguments["file_name"]).strip()
        destination = str(call.arguments["destination"]).strip()
        if self._is_explicit_path_outside_roots(file_name) or self._is_explicit_path_outside_roots(destination):
            return ToolResult("blocked", "The source or destination is outside configured safe roots.", data=call.arguments)
        source = self._find_file(file_name)
        target_folder = self._find_folder(destination)
        if source is None:
            return ToolResult("not_found", f"Could not find file in safe roots: {file_name}", data=call.arguments)
        if target_folder is None:
            return ToolResult("not_found", f"Could not find destination folder in safe roots: {destination}", data=call.arguments)
        target = (target_folder / source.name).resolve()
        if not any(_is_relative_to(target, root) for root in self.safe_roots):
            return ToolResult("blocked", "The destination is outside configured safe roots.", data=call.arguments)
        if target.exists():
            return ToolResult("blocked", f"A file already exists at the destination: {target.name}", data={"path": str(target)})
        if self.dry_run:
            return ToolResult("dry_run", f"Would move {source.name} to {target_folder.name} after confirmation.", data={"source": str(source), "target": str(target)})
        shutil.move(str(source), str(target))
        return ToolResult("success", f"Moved {source.name} to {target_folder.name}.", changed={"source": str(source), "target": str(target)})

    def _handle_rename_file(self, call: ToolCall) -> ToolResult:
        old_name = str(call.arguments["old_name"]).strip()
        new_name = str(call.arguments["new_name"]).strip()
        if not _safe_file_name(new_name):
            return ToolResult("blocked", "The new file name must be a plain file name without path separators.", data=call.arguments)
        if self._is_explicit_path_outside_roots(old_name):
            return ToolResult("blocked", "The source file is outside configured safe roots.", data=call.arguments)
        source = self._find_file(old_name)
        if source is None:
            return ToolResult("not_found", f"Could not find file in safe roots: {old_name}", data=call.arguments)
        target = source.with_name(new_name).resolve()
        if not any(_is_relative_to(target, root) for root in self.safe_roots):
            return ToolResult("blocked", "The renamed file would be outside configured safe roots.", data=call.arguments)
        if target.exists():
            return ToolResult("blocked", f"A file already uses the requested name: {new_name}", data={"path": str(target)})
        if self.dry_run:
            return ToolResult("dry_run", f"Would rename {source.name} to {new_name} after confirmation.", data={"source": str(source), "target": str(target)})
        source.rename(target)
        return ToolResult("success", f"Renamed {source.name} to {new_name}.", changed={"source": str(source), "target": str(target)})

    def _handle_close_application(self, call: ToolCall) -> ToolResult:
        app = str(call.arguments["app"]).strip()
        if is_windows():
            return self.windows.close_application(app, self.app_aliases)
        return ToolResult("not_implemented", "Closing applications needs an OS-specific adapter.", data={"app": app})

    def _handle_lock_screen(self, call: ToolCall) -> ToolResult:
        if is_windows():
            return self.windows.lock_screen()
        return ToolResult("not_implemented", "Screen locking needs an OS-specific adapter.")

    def _select_search_roots(self, folder: object | None) -> tuple[tuple[Path, ...], bool]:
        if not folder:
            return self.safe_roots, False
        explicit = Path(str(folder)).expanduser()
        if explicit.is_absolute():
            resolved = explicit.resolve()
            if resolved.is_dir() and any(_is_relative_to(resolved, root) for root in self.safe_roots):
                return (resolved,), False
            return (), True
        folder_name = str(folder).lower()
        for root in self.safe_roots:
            if root.name.lower() == folder_name and root.is_dir():
                return (root,), False
            candidate = root / str(folder)
            if candidate.exists() and candidate.is_dir() and _is_relative_to(candidate.resolve(), root):
                return (candidate.resolve(),), False
        return (), True

    def _find_file(self, file_name: str) -> Path | None:
        target = file_name.lower()
        explicit = Path(file_name).expanduser()
        if explicit.is_absolute():
            resolved = explicit.resolve()
            if resolved.is_file() and any(_is_relative_to(resolved, root) for root in self.safe_roots):
                return resolved
            return None
        for root in self.safe_roots:
            direct = root / file_name
            if direct.is_file() and _is_relative_to(direct.resolve(), root):
                return direct.resolve()
            for path in root.rglob("*"):
                if path.is_file() and path.name.lower() == target:
                    return path.resolve()
        return None

    def _find_folder(self, folder_name: str) -> Path | None:
        target = folder_name.lower()
        explicit = Path(folder_name).expanduser()
        if explicit.is_absolute():
            resolved = explicit.resolve()
            if resolved.is_dir() and any(_is_relative_to(resolved, root) for root in self.safe_roots):
                return resolved
            return None
        for root in self.safe_roots:
            if root.name.lower() == target and root.is_dir():
                return root
            direct = root / folder_name
            if direct.is_dir() and _is_relative_to(direct.resolve(), root):
                return direct.resolve()
            for path in root.rglob("*"):
                if path.is_dir() and path.name.lower() == target:
                    return path.resolve()
        return None

    def _is_explicit_path_outside_roots(self, value: str) -> bool:
        path = Path(value).expanduser()
        if not path.is_absolute():
            return False
        resolved = path.resolve()
        return not any(_is_relative_to(resolved, root) for root in self.safe_roots)


def _calculate_expression(expression: str) -> tuple[str, int | float]:
    normalized = _normalize_calculation_expression(expression)
    if not normalized or len(normalized) > 200:
        raise ValueError("the expression is empty or too long")
    try:
        tree = ast.parse(normalized, mode="eval")
        value = _eval_calculation_node(tree.body)
    except (SyntaxError, TypeError, ZeroDivisionError, OverflowError) as exc:
        raise ValueError("the arithmetic expression is invalid") from exc
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(float(value)):
        raise ValueError("the result is not a finite number")
    if abs(float(value)) > 1e15:
        raise ValueError("the result is outside ULTRON's calculation limit")
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return normalized, value


def _normalize_calculation_expression(expression: str) -> str:
    value = expression.lower().strip().rstrip("?=")
    value = re.sub(r"(?<=\d),(?=\d)", "", value)
    value = re.sub(r"\bsquare\s+root\s+of\s+(\d+(?:\.\d+)?)", r"sqrt(\1)", value)
    value = re.sub(
        r"(\d+(?:\.\d+)?)\s+percent\s+of\s+(\d+(?:\.\d+)?)",
        r"((\1 / 100) * \2)",
        value,
    )
    replacements = (
        (r"\bto\s+the\s+power\s+of\b", "**"),
        (r"\bmultiplied\s+by\b", "*"),
        (r"\bdivided\s+by\b", "/"),
        (r"\bover\b", "/"),
        (r"\btimes\b", "*"),
        (r"\bplus\b", "+"),
        (r"\bminus\b", "-"),
    )
    for pattern, replacement in replacements:
        value = re.sub(pattern, replacement, value)
    return re.sub(r"\s+", " ", value.replace("^", "**")).strip()


def _eval_calculation_node(node: ast.AST) -> int | float:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)) and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, (ast.UAdd, ast.USub)):
        value = _eval_calculation_node(node.operand)
        return value if isinstance(node.op, ast.UAdd) else -value
    if isinstance(node, ast.BinOp):
        left = _eval_calculation_node(node.left)
        right = _eval_calculation_node(node.right)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.Pow):
            if abs(float(right)) > 10 or abs(float(left)) > 1e6:
                raise ValueError("exponents are limited")
            return left**right
        raise ValueError("unsupported arithmetic operator")
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
        functions: dict[str, Any] = {"abs": abs, "round": round, "sqrt": math.sqrt}
        function = functions.get(node.func.id)
        if function is None or node.keywords or len(node.args) not in {1, 2}:
            raise ValueError("unsupported calculation function")
        arguments = [_eval_calculation_node(argument) for argument in node.args]
        return function(*arguments)
    raise ValueError("only arithmetic is allowed")


def _format_calculation(value: int | float) -> str:
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:,.10f}".rstrip("0").rstrip(".")


def _system_status(category: str) -> ToolResult:
    now = datetime.now()
    if category == "time":
        value = now.strftime("%I:%M %p").lstrip("0")
        return ToolResult("success", f"It is {value}.", data={"category": category, "local_time": now.isoformat(timespec="seconds")})
    if category == "date":
        value = now.strftime("%A, %B %d, %Y").replace(" 0", " ")
        return ToolResult("success", f"Today is {value}.", data={"category": category, "date": now.date().isoformat()})
    if category == "battery":
        battery = _windows_battery_status()
        if battery is None:
            return ToolResult("not_found", "Windows did not report an installed battery.", data={"category": category})
        percent, plugged_in = battery
        source = "plugged in" if plugged_in else "on battery"
        return ToolResult("success", f"Battery is at {percent}% and {source}.", data={"category": category, "percent": percent, "plugged_in": plugged_in})
    if category == "storage":
        drive = Path.home().anchor or str(Path.home())
        usage = shutil.disk_usage(drive)
        free_gb = round(usage.free / (1024**3), 1)
        total_gb = round(usage.total / (1024**3), 1)
        return ToolResult("success", f"The system drive has {free_gb} GB free of {total_gb} GB.", data={"category": category, "drive": drive, "free_gb": free_gb, "total_gb": total_gb})
    if category == "system":
        memory = _windows_memory_status()
        processor = platform.processor() or os.environ.get("PROCESSOR_IDENTIFIER", "Unknown processor")
        data: dict[str, Any] = {
            "category": category,
            "computer": platform.node(),
            "operating_system": f"{platform.system()} {platform.release()}",
            "processor": processor,
            "logical_cpu_count": os.cpu_count(),
            "python": platform.python_version(),
        }
        if memory is not None:
            data["memory_total_gb"], data["memory_available_gb"] = memory
        memory_text = f", {data['memory_total_gb']} GB RAM" if "memory_total_gb" in data else ""
        return ToolResult(
            "success",
            f"{data['computer']} is running {data['operating_system']} with {data['logical_cpu_count']} logical CPU cores{memory_text}.",
            data=data,
        )
    return ToolResult("blocked", f"Unknown system-status category: {category}", data={"category": category})


def _windows_battery_status() -> tuple[int, bool] | None:
    if os.name != "nt":
        return None
    import ctypes

    class SystemPowerStatus(ctypes.Structure):
        _fields_ = [
            ("ACLineStatus", ctypes.c_ubyte),
            ("BatteryFlag", ctypes.c_ubyte),
            ("BatteryLifePercent", ctypes.c_ubyte),
            ("SystemStatusFlag", ctypes.c_ubyte),
            ("BatteryLifeTime", ctypes.c_uint32),
            ("BatteryFullLifeTime", ctypes.c_uint32),
        ]

    status = SystemPowerStatus()
    if not ctypes.windll.kernel32.GetSystemPowerStatus(ctypes.byref(status)):
        return None
    if status.BatteryFlag == 128 or status.BatteryLifePercent == 255:
        return None
    return int(status.BatteryLifePercent), status.ACLineStatus == 1


def _windows_memory_status() -> tuple[float, float] | None:
    if os.name != "nt":
        return None
    import ctypes

    class MemoryStatus(ctypes.Structure):
        _fields_ = [
            ("dwLength", ctypes.c_uint32),
            ("dwMemoryLoad", ctypes.c_uint32),
            ("ullTotalPhys", ctypes.c_uint64),
            ("ullAvailPhys", ctypes.c_uint64),
            ("ullTotalPageFile", ctypes.c_uint64),
            ("ullAvailPageFile", ctypes.c_uint64),
            ("ullTotalVirtual", ctypes.c_uint64),
            ("ullAvailVirtual", ctypes.c_uint64),
            ("ullAvailExtendedVirtual", ctypes.c_uint64),
        ]

    status = MemoryStatus()
    status.dwLength = ctypes.sizeof(status)
    if not ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        return None
    return round(status.ullTotalPhys / (1024**3), 1), round(status.ullAvailPhys / (1024**3), 1)


def _website_target(site: str, query: str) -> tuple[str, str]:
    key = " ".join(site.lower().split())
    configured = WEBSITE_URLS.get(key)
    if configured is not None:
        home, search = configured
        if query:
            if search is None:
                raise ValueError(f"{site} does not have a configured safe search URL.")
            return search.format(query=urllib.parse.quote_plus(query)), key.title()
        return home, key.title()

    candidate = site.strip()
    if not re.match(r"^https?://", candidate, flags=re.IGNORECASE):
        candidate = f"https://{candidate}"
    parsed = urllib.parse.urlparse(candidate)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("Website must be a valid HTTP or HTTPS address without embedded credentials.")
    if any(ord(char) < 32 for char in candidate):
        raise ValueError("Website address contains invalid control characters.")
    if query:
        raise ValueError("Search is supported only for ULTRON's named website shortcuts.")
    return candidate, parsed.hostname


def _parse_duration_seconds(value: str) -> int | None:
    normalized = value.lower().strip()
    unit_seconds = {
        "s": 1,
        "sec": 1,
        "secs": 1,
        "second": 1,
        "seconds": 1,
        "m": 60,
        "min": 60,
        "mins": 60,
        "minute": 60,
        "minutes": 60,
        "h": 3600,
        "hr": 3600,
        "hrs": 3600,
        "hour": 3600,
        "hours": 3600,
    }
    pattern = r"(\d+(?:\.\d+)?)\s*(seconds?|secs?|s|minutes?|mins?|m|hours?|hrs?|h)\b"
    matches = re.findall(pattern, normalized)
    if not matches:
        return None
    residual = re.sub(pattern, "", normalized)
    residual = re.sub(r"[\s,]+|\band\b", "", residual)
    if residual:
        return None
    seconds = int(round(sum(float(amount) * unit_seconds[unit] for amount, unit in matches)))
    return seconds if 1 <= seconds <= 24 * 60 * 60 else None


def _start_windows_timer_notification(seconds: int) -> int:
    script = (
        "import ctypes,sys,time,winsound;"
        "time.sleep(float(sys.argv[1]));"
        "winsound.MessageBeep();"
        "ctypes.windll.user32.MessageBoxW(0,'Your timer is complete, sir.','ULTRON 2.7',0x40)"
    )
    process = subprocess.Popen(
        [sys.executable, "-c", script, str(seconds)],
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=0x00000008 | 0x00000200 | 0x08000000,
    )
    return process.pid


def _safe_folder_name(value: str) -> bool:
    candidate = value.strip()
    return bool(candidate) and candidate not in {".", ".."} and not Path(candidate).is_absolute() and not any(separator in candidate for separator in ("/", "\\"))


def _safe_file_name(value: str) -> bool:
    candidate = value.strip()
    return _safe_folder_name(candidate) and Path(candidate).name == candidate


def _safe_email_recipient(value: str) -> bool:
    candidate = value.strip()
    return bool(candidate) and len(candidate) <= 320 and not any(ord(char) < 32 for char in candidate)


def _safe_filename(value: str) -> str:
    cleaned = "".join(char for char in value if char.isalnum() or char in {" ", "-", "_"}).strip()
    return cleaned.replace(" ", "_") or "untitled"


def _resolve_safe_roots(safe_roots: Iterable[Path] | None, workspace: Path) -> list[Path]:
    roots = list(safe_roots or (workspace,))
    resolved: list[Path] = []
    for root in roots:
        candidate = _resolve_under_workspace(root, workspace)
        if candidate not in resolved:
            resolved.append(candidate)
    return resolved or [workspace]


def _resolve_under_workspace(path: Path, workspace: Path) -> Path:
    candidate = path.expanduser()
    if not candidate.is_absolute():
        candidate = workspace / candidate
    return candidate.resolve()


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root.resolve())
    except ValueError:
        return False
    return True


def _open_path(path: Path) -> ToolResult:
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:
            subprocess.Popen(["xdg-open", str(path)], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as exc:
        return ToolResult("error", f"Could not open path: {exc}", data={"path": str(path)})
    return ToolResult("success", f"Opened: {path.name}", changed={"path": str(path)})


def _open_url(url: str, success_message: str, changed: dict[str, str]) -> ToolResult:
    try:
        opened = webbrowser.open(url, new=2)
    except Exception as exc:
        return ToolResult("error", f"Could not open URL: {exc}", data=changed)
    if not opened:
        return ToolResult("error", "The system browser did not accept the URL.", data=changed)
    return ToolResult("success", success_message, changed=changed)


def _write_clipboard(text: str) -> ToolResult:
    if os.name == "nt":
        try:
            subprocess.run(["clip"], input=text, text=True, check=True)
        except OSError as exc:
            return ToolResult("error", f"Could not write clipboard: {exc}")
        except subprocess.CalledProcessError as exc:
            return ToolResult("error", f"Clipboard command failed: {exc}")
        return ToolResult("success", "Copied text to clipboard.", changed={"text_length": len(text)})
    return ToolResult("not_implemented", f"Clipboard write is not implemented on {platform.system()}.")


def _read_clipboard() -> ToolResult:
    if os.name != "nt":
        return ToolResult("not_implemented", f"Clipboard read is not implemented on {platform.system()}.")
    command = [
        "powershell.exe",
        "-NoProfile",
        "-Command",
        "Get-Clipboard -Raw",
    ]
    try:
        proc = subprocess.run(command, capture_output=True, text=True, check=True)
    except OSError as exc:
        return ToolResult("error", f"Could not read clipboard: {exc}")
    except subprocess.CalledProcessError as exc:
        return ToolResult("error", f"Clipboard command failed: {exc}")
    return ToolResult("success", "Read clipboard text.", data={"text": proc.stdout})


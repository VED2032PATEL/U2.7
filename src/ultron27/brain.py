from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import asdict, dataclass, field, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

from .audit import append_audit_record
from .runtime import UltronAssistant
from .policy import decide
from .tools import validate_tool_call


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    WAITING_FOR_CONFIRMATION = "waiting_for_confirmation"
    COMPLETED = "completed"
    FAILED = "failed"
    BLOCKED = "blocked"


@dataclass
class TaskStep:
    step_id: str
    utterance: str
    status: TaskState = TaskState.PENDING
    tool_call: dict[str, Any] | None = None
    policy: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error: str | None = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.updated_at = time.time()


@dataclass
class TaskPlan:
    task_id: str
    original_goal: str
    classification: str
    status: TaskState
    steps: list[TaskStep]
    summary: str = ""
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def touch(self) -> None:
        self.updated_at = time.time()

    def to_dict(self) -> dict[str, Any]:
        return _jsonable(asdict(self))


class MemoryStore:
    def __init__(self, path: Path):
        self.path = path

    def list(self) -> list[dict[str, Any]]:
        return list(self._read().get("items", []))

    def remember(self, key: str, value: str, *, kind: str = "fact") -> bool:
        if not key.strip():
            return False
        if _looks_sensitive(key) or _looks_sensitive(value):
            return False
        data = self._read()
        items = list(data.get("items", []))
        now = time.time()
        for item in items:
            if item.get("key") == key:
                item.update({"value": value, "kind": kind, "updated_at": now})
                self._write({"items": items})
                return True
        items.append({"key": key, "value": value, "kind": kind, "created_at": now, "updated_at": now})
        self._write({"items": items})
        return True

    def forget(self, query: str) -> int:
        normalized = query.strip().lower()
        if not normalized:
            return 0
        data = self._read()
        items = list(data.get("items", []))
        kept = [
            item
            for item in items
            if normalized not in str(item.get("key", "")).lower()
            and normalized not in str(item.get("value", "")).lower()
        ]
        removed = len(items) - len(kept)
        if removed:
            self._write({"items": kept})
        return removed

    def _read(self) -> dict[str, Any]:
        if not self.path.exists():
            return {"items": []}
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return {"items": []}
        if not isinstance(payload, dict):
            return {"items": []}
        items = payload.get("items", [])
        if not isinstance(items, list):
            return {"items": []}
        return {"items": [item for item in items if isinstance(item, dict)]}

    def _write(self, payload: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True), encoding="utf-8")


class UltronBrain:
    def __init__(self, assistant: UltronAssistant, memory_path: Path | None = None):
        self.assistant = assistant
        self.session_memory: dict[str, Any] = {}
        self.memory = MemoryStore(memory_path or assistant.settings.workspace / ".ultron" / "memory.json")

    def plan(self, goal: str) -> TaskPlan:
        utterances = self._decompose(goal)
        classification = "multi_step" if len(utterances) > 1 else "single_command"
        steps = [self._preview_step(index, utterance) for index, utterance in enumerate(utterances, start=1)]
        plan = TaskPlan(
            task_id=str(uuid.uuid4()),
            original_goal=goal,
            classification=classification,
            status=TaskState.PENDING,
            steps=steps,
            summary=f"Planned {len(steps)} step(s) for: {goal}",
        )
        self.session_memory["last_plan"] = plan.to_dict()
        return plan

    def execute(self, goal: str, *, confirmed: bool = False) -> TaskPlan:
        task = self.plan(goal)
        task.status = TaskState.RUNNING
        task.touch()
        for step in task.steps:
            step.status = TaskState.RUNNING
            step.touch()
            try:
                payload = self.assistant.handle(step.utterance, confirmed=confirmed)
            except Exception as exc:  # pragma: no cover - defensive runtime boundary
                step.status = TaskState.FAILED
                step.error = str(exc)
                task.status = TaskState.FAILED
                break
            step.tool_call = payload["tool_call"]
            step.policy = payload["policy"]
            step.result = payload["result"]
            step.status = self._step_status(payload)
            step.touch()
            self._remember_step(payload)
            if step.status in {TaskState.WAITING_FOR_CONFIRMATION, TaskState.BLOCKED, TaskState.FAILED}:
                task.status = step.status
                break
        else:
            task.status = TaskState.COMPLETED

        task.summary = self._summarize(task)
        task.touch()
        if task.status == TaskState.COMPLETED:
            self.memory.remember(f"completed_task:{task.task_id}", task.summary, kind="completed_task")
        self.memory.remember("last_goal", goal, kind="session")
        self.session_memory["last_task"] = task.to_dict()
        self._audit_task(task)
        return task

    def _preview_step(self, index: int, utterance: str) -> TaskStep:
        plan = self.assistant.planner.plan(utterance)
        validation = validate_tool_call(plan.tool_call)
        decision = decide(plan, validation)
        return TaskStep(
            step_id=str(index),
            utterance=utterance,
            tool_call=_jsonable(plan.tool_call),
            policy=_jsonable(decision),
        )

    def _decompose(self, goal: str) -> list[str]:
        normalized = " ".join(goal.strip().split())
        note_plan = self._decompose_note_goal(normalized)
        if note_plan:
            return note_plan
        parts = re.split(r"\s+(?:and then|then)\s+|;\s*|(?<=[.!?])\s+", normalized, flags=re.IGNORECASE)
        steps = [part.strip() for part in parts if part.strip()]
        if len(steps) > 1:
            return steps
        return [normalized]

    def _decompose_note_goal(self, goal: str) -> list[str] | None:
        match = re.search(
            r"\b(?:create|make|write)\s+(?:a\s+)?note\s+(?:called|named)?\s*(?P<title>.+?)\s+(?:and\s+)?(?:add|append|write)\s+(?:that\s+)?(?P<content>.+)",
            goal,
            flags=re.IGNORECASE,
        )
        if not match:
            return None
        title = _clean_text(match.group("title"))
        content = _clean_text(match.group("content"))
        if not title or not content:
            return None
        return [f"create note {title}", f"add {content} to note {title}"]

    def _step_status(self, payload: dict[str, Any]) -> TaskState:
        result_status = str(payload.get("result", {}).get("status", ""))
        policy_action = str(payload.get("policy", {}).get("action", ""))
        if result_status == "confirmation_required" or policy_action == "confirm":
            return TaskState.WAITING_FOR_CONFIRMATION
        if policy_action == "block" or result_status == "blocked":
            return TaskState.BLOCKED
        if result_status in {"error", "not_implemented", "not_found"}:
            return TaskState.FAILED
        return TaskState.COMPLETED

    def _remember_step(self, payload: dict[str, Any]) -> None:
        tool_call = payload.get("tool_call", {})
        arguments = tool_call.get("arguments", {})
        name = tool_call.get("name")
        if name in {"create_note", "append_to_note"} and isinstance(arguments, dict) and "title" in arguments:
            self.memory.remember("last_note", str(arguments["title"]), kind="recent_note")
        if name in {"open_file", "search_files"} and isinstance(arguments, dict):
            query = arguments.get("file_name") or arguments.get("query")
            if query:
                self.memory.remember("last_file_query", str(query), kind="recent_file_query")

    def _audit_task(self, task: TaskPlan) -> None:
        if not self.assistant.settings.write_audit:
            return
        append_audit_record(
            {"record_type": "brain_task", "task_plan": task.to_dict()},
            self.assistant.settings.audit_log,
        )

    def _summarize(self, task: TaskPlan) -> str:
        if task.status == TaskState.COMPLETED:
            return _assistant_completion_summary(task)
        if task.status == TaskState.WAITING_FOR_CONFIRMATION:
            step = self._first_noncompleted_task_step(task)
            reason = _step_reason(step) if step else "This command needs confirmation."
            return f"Paused for confirmation: {reason}"
        if task.status == TaskState.BLOCKED:
            step = self._first_noncompleted_task_step(task)
            reason = _step_reason(step) if step else "No safe supported tool matched the request."
            tool = (step.tool_call or {}).get("name") if step else "unknown"
            if tool == "unsupported_request":
                return f"I do not have a safe tool for that yet. {reason} Try: create a note, open Notepad, search files, set a timer, or use Mock Voice."
            return f"Blocked: {reason}"
        if task.status == TaskState.FAILED:
            step = self._first_noncompleted_task_step(task)
            reason = _step_reason(step) if step else "The selected tool failed."
            return f"Failed: {reason}"
        return f"Task status: {task.status.value}"

    def _first_noncompleted_step(self, task: TaskPlan) -> str:
        step = self._first_noncompleted_task_step(task)
        if step is not None:
            return step.step_id
        return str(len(task.steps))

    def _first_noncompleted_task_step(self, task: TaskPlan) -> TaskStep | None:
        for step in task.steps:
            if step.status != TaskState.COMPLETED:
                return step
        return None


def format_task_plan(task: TaskPlan) -> str:
    lines = [
        f"Task: {task.original_goal}",
        f"Status: {task.status.value} | Type: {task.classification} | Steps: {len(task.steps)}",
    ]
    for step in task.steps:
        tool = (step.tool_call or {}).get("name", "unknown")
        result = step.result or {}
        result_text = ""
        if result:
            result_text = f" | Result: {result.get('status')} - {result.get('message')}"
        lines.append(f"{step.step_id}. {step.status.value} - {step.utterance} | Tool: {tool}{result_text}")
    if task.summary:
        lines.append(f"Summary: {task.summary}")
    return "\n".join(lines)


def format_memory(items: list[dict[str, Any]]) -> str:
    if not items:
        return "Memory is empty."
    lines = ["Memory:"]
    for item in items:
        lines.append(f"- {item.get('key')}: {item.get('value')} ({item.get('kind', 'fact')})")
    return "\n".join(lines)


def _clean_text(value: str) -> str:
    cleaned = value.strip().strip(" .!?\"'")
    return re.sub(r"\s+", " ", cleaned)


def _looks_sensitive(value: str) -> bool:
    return bool(re.search(r"\b(password|passwd|secret|api[_ -]?key|token|credential|private key)\b", value, re.IGNORECASE))


def _step_reason(step: TaskStep | None) -> str:
    if step is None:
        return ""
    if step.error:
        return step.error
    result = step.result or {}
    policy = step.policy or {}
    validation = result.get("validation") if isinstance(result.get("validation"), dict) else {}
    for payload in (result, policy, validation):
        message = payload.get("message") or payload.get("reason")
        if message:
            return str(message)
    return f"Step {step.step_id} could not be completed."


def _assistant_completion_summary(task: TaskPlan) -> str:
    if len(task.steps) == 1 and (task.steps[0].tool_call or {}).get("name") == "assistant_reply":
        return _friendly_step_result(task.steps[0])
    dry_run_steps = [step for step in task.steps if str((step.result or {}).get("status")) == "dry_run"]
    prefix = "I am in dry-run mode, so I simulated this: " if dry_run_steps else "Done. "
    if len(task.steps) > 1:
        actions = [_friendly_step_result(step) for step in task.steps]
        return prefix + " ".join(action for action in actions if action)
    return prefix + (_friendly_step_result(task.steps[0]) if task.steps else f"Completed: {task.original_goal}")


def _friendly_step_result(step: TaskStep) -> str:
    tool = (step.tool_call or {}).get("name", "")
    arguments = (step.tool_call or {}).get("arguments", {})
    result = step.result or {}
    message = str(result.get("message") or "")
    status = str(result.get("status") or "")
    if tool == "open_application":
        return _would(status, f"opened {arguments.get('app', 'the application')}", message)
    if tool == "write_text_in_application":
        return _would(status, f"opened {arguments.get('app', 'the application')} and wrote the text", message)
    if tool == "assistant_reply":
        return message or str(arguments.get("message") or "At your service.")
    if tool == "ask_clarification":
        return message or str(arguments.get("question") or "Could you clarify what you want me to do?")
    if tool == "search_web":
        return _would(status, f"searched the web for {arguments.get('query', 'your query')}", message)
    if tool == "play_music":
        return _would(status, f"opened Spotify for {arguments.get('query', 'your music')}", message)
    if tool == "play_youtube_video":
        return _would(status, f"loaded {arguments.get('query', 'your video')} in ULTRON's YouTube mini-player", message)
    if tool == "create_note":
        return _would(status, f"created the note {arguments.get('title', 'untitled')}", message)
    if tool == "append_to_note":
        return _would(status, f"updated the note {arguments.get('title', 'untitled')}", message)
    if tool == "search_files":
        matches = result.get("data", {}).get("matches", []) if isinstance(result.get("data"), dict) else []
        if status == "success":
            return f"found {len(matches)} matching file(s)."
        return _would(status, f"searched your files for {arguments.get('query', 'your query')}", message)
    if tool == "set_reminder":
        return _would(status, f"set the reminder {arguments.get('task', '')} {arguments.get('time', '')}".strip(), message)
    if tool == "start_timer":
        return _would(status, f"started a timer for {arguments.get('duration', '')}".strip(), message)
    if tool == "take_screenshot":
        return _would(status, "captured a screenshot", message)
    return message or f"completed {step.utterance}."


def _would(status: str, phrase: str, fallback: str) -> str:
    if status == "dry_run":
        return f"would have {phrase}."
    if status == "success":
        return f"I {phrase}."
    return fallback or f"{phrase}."


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {key: _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, Enum):
        return value.value
    return value

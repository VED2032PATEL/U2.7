from __future__ import annotations

import sys
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .audit import append_audit_record
from .config import UltronConfig
from .executor import Executor
from .llm import LLMPlannerError, make_groq_router, make_ollama_router
from .planner import DatasetPlanner
from .policy import decide
from .models import Plan, RiskLevel, ToolCall
from .tools import get_tool_spec, validate_tool_call
from .windows_executor import merge_windows_app_aliases, resolve_app_alias


@dataclass(frozen=True)
class RuntimeSettings:
    dataset_path: Path
    audit_log: Path
    workspace: Path
    dry_run: bool
    safe_roots: tuple[Path, ...]
    app_aliases: dict[str, str] | None
    screenshot_dir: Path
    planner_mode: str
    llm_model: str
    llm_endpoint: str
    llm_timeout_seconds: float
    llm_provider: str = "ollama"
    neural_router_enabled: bool = False
    neural_router_model: Path = Path(".ultron/models/neural_router.pt")
    execute_requested: bool = False
    write_audit: bool = True
    whatsapp_contacts: dict[str, str] | None = None
    whatsapp_require_confirmation: bool = True

    @classmethod
    def from_config(
        cls,
        config: UltronConfig,
        *,
        dataset_path: Path | None = None,
        audit_log: Path | None = None,
        workspace: Path | None = None,
        dry_run: bool | None = None,
        execute_requested: bool = False,
        write_audit: bool = True,
        planner_mode: str | None = None,
        llm_model: str | None = None,
        llm_endpoint: str | None = None,
    ) -> "RuntimeSettings":
        return cls(
            dataset_path=dataset_path or config.dataset_path,
            audit_log=audit_log or config.audit_log,
            workspace=workspace or config.workspace,
            dry_run=config.dry_run if dry_run is None else dry_run,
            safe_roots=config.safe_roots,
            app_aliases=config.app_aliases,
            screenshot_dir=config.screenshot_dir,
            planner_mode=planner_mode or config.planner_mode,
            llm_model=llm_model or config.llm_model,
            llm_endpoint=llm_endpoint or config.llm_endpoint,
            llm_timeout_seconds=config.llm_timeout_seconds,
            llm_provider=config.llm_provider,
            neural_router_enabled=config.neural_router_enabled,
            neural_router_model=config.neural_router_model,
            execute_requested=execute_requested,
            write_audit=write_audit,
            whatsapp_contacts=config.whatsapp_contacts,
            whatsapp_require_confirmation=config.whatsapp_require_confirmation,
        )


class UltronAssistant:
    def __init__(self, settings: RuntimeSettings):
        if not settings.dataset_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {settings.dataset_path}")
        self.settings = settings
        self.execution_lock = threading.RLock()
        self.planner = DatasetPlanner.from_jsonl(settings.dataset_path)

    def handle(self, utterance: str, *, confirmed: bool = False) -> dict[str, Any]:
        plan = self.planner.plan(utterance)
        llm_trace: dict[str, Any] = {"attempted": False, "error": None}
        if self.settings.planner_mode in {"hybrid", "llm"} and self._should_try_llm(plan):
            llm_trace["attempted"] = True
            try:
                router_factory = make_groq_router if self.settings.llm_provider == "groq" else make_ollama_router
                router = router_factory(
                    endpoint=self.settings.llm_endpoint,
                    model=self.settings.llm_model,
                    timeout=self.settings.llm_timeout_seconds,
                )
                plan = router.route(utterance)
            except LLMPlannerError as exc:
                llm_trace["error"] = str(exc)
                if self.settings.planner_mode == "llm":
                    plan = self.planner.plan(utterance)

        return self._execute_plan(utterance, plan, confirmed=confirmed, llm_trace=llm_trace)

    def _should_try_llm(self, plan: Plan) -> bool:
        if self.settings.planner_mode == "llm":
            return True
        if plan.source == "fallback":
            return True
        if plan.source == "regex" and plan.tool_call.name == "open_application":
            aliases = merge_windows_app_aliases(self.settings.app_aliases or {})
            app = str(plan.tool_call.arguments.get("app", ""))
            return resolve_app_alias(app, aliases) is None
        return False

    def handle_tool_call(
        self,
        utterance: str,
        tool_call: ToolCall,
        *,
        intent: str = "skill",
        source: str = "skill",
        confidence: float = 1.0,
        confirmed: bool = False,
    ) -> dict[str, Any]:
        spec = get_tool_spec(tool_call.name)
        risk_level = spec.risk_level if spec else RiskLevel.BLOCKED
        requires_confirmation = spec.requires_confirmation if spec else True
        plan = Plan(
            utterance=utterance,
            intent=intent,
            tool_call=tool_call,
            risk_level=risk_level,
            requires_confirmation=requires_confirmation,
            source=source,
            confidence=confidence,
        )
        return self._execute_plan(utterance, plan, confirmed=confirmed, llm_trace={"attempted": False, "error": None})

    def _execute_plan(
        self,
        utterance: str,
        plan: Plan,
        *,
        confirmed: bool = False,
        llm_trace: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        llm_trace = llm_trace or {"attempted": False, "error": None}
        validation = validate_tool_call(plan.tool_call)
        whatsapp_auto_confirmed = (
            plan.tool_call.name == "send_whatsapp_message"
            and not self.settings.whatsapp_require_confirmation
        )
        decision = decide(plan, validation, confirmed=confirmed or whatsapp_auto_confirmed)
        executor = Executor(
            dry_run=self.settings.dry_run,
            workspace=self.settings.workspace,
            safe_roots=self.settings.safe_roots,
            app_aliases=self.settings.app_aliases or {},
            screenshot_dir=self.settings.screenshot_dir,
            whatsapp_contacts=self.settings.whatsapp_contacts or {},
        )
        if decision.action == "allow":
            with self.execution_lock:
                result = executor.execute(plan.tool_call)
        elif decision.action == "confirm":
            result = {
                "status": "confirmation_required",
                "message": decision.reason,
            }
        else:
            result = {
                "status": "blocked",
                "message": decision.reason,
            }

        payload: dict[str, Any] = {
            "utterance": utterance,
            "intent": plan.intent,
            "source": plan.source,
            "confidence": plan.confidence,
            "tool_call": asdict(plan.tool_call),
            "validation": asdict(validation),
            "policy": asdict(decision),
            "result": asdict(result) if hasattr(result, "__dataclass_fields__") else result,
            "runtime": {
                "dry_run": self.settings.dry_run,
                "execute_requested": self.settings.execute_requested,
                "confirmed": confirmed,
                "auto_confirmed": whatsapp_auto_confirmed,
                "whatsapp_require_confirmation": self.settings.whatsapp_require_confirmation,
                "dataset_path": str(self.settings.dataset_path),
                "workspace": str(self.settings.workspace),
                "safe_roots": [str(root) for root in self.settings.safe_roots],
                "planner_mode": self.settings.planner_mode,
                "llm_provider": self.settings.llm_provider,
                "llm": llm_trace,
                "python": sys.version.split()[0],
                "platform": sys.platform,
            },
        }
        if self.settings.write_audit:
            append_audit_record(payload, self.settings.audit_log)
        return payload

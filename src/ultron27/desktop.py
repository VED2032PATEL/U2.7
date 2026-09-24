from __future__ import annotations

import argparse
import ctypes
import json
import logging
import sys
import threading
from dataclasses import dataclass, field
from http.server import ThreadingHTTPServer
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

from . import __version__
from .app_paths import desktop_data_dir, resource_root
from .hand_input import DesktopHandInputController, build_hand_input_controller
from .planner import DEFAULT_DATASET_PATH
from .web_server import WebState, build_state, make_handler


APP_TITLE = "ULTRON 2.7"
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8765
DESKTOP_PROFILE_VERSION = 3
DESKTOP_PATH_KEYS = {
    "dataset_path",
    "audit_log",
    "workspace",
    "safe_roots",
    "screenshot_dir",
    "neural_router_model",
    "voice_stt_model_path",
    "voice_tts_model_path",
    "voice_tts_voice_path",
    "wake_model_path",
}
DESKTOP_USER_KEYS = {"whatsapp_contacts"}


class DesktopHTTPServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


@dataclass
class DesktopBackend:
    server: DesktopHTTPServer
    thread: threading.Thread
    url: str
    _stopped: bool = field(default=False, init=False, repr=False)
    _stop_lock: threading.Lock = field(default_factory=threading.Lock, init=False, repr=False)

    def stop(self) -> None:
        with self._stop_lock:
            if self._stopped:
                return
            self._stopped = True
        stop_agent = getattr(self.server.RequestHandlerClass, "shutdown_agent", None)
        if stop_agent:
            stop_agent()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)


class DesktopBridge:
    """Native-shell bridge. System input is available only inside pywebview."""

    def __init__(self, app_data: Path, hand_controller: DesktopHandInputController | None = None):
        self.app_data = app_data
        self.hand_controller = hand_controller

    def runtime_info(self) -> dict[str, str]:
        return {
            "application": APP_TITLE,
            "version": __version__,
            "shell": "desktop",
            "platform": sys.platform,
            "app_data": str(self.app_data),
            "hand_input_available": bool(self.hand_controller and self.hand_controller.available),
        }

    def hand_control_status(self) -> dict[str, Any]:
        if self.hand_controller is None:
            return {
                "available": False,
                "enabled": False,
                "paused": False,
                "pressed_buttons": [],
                "last_stop_reason": "bridge_unavailable",
                "virtual_desktop": None,
                "emergency_hotkey": "Ctrl+Alt+H",
                "ok": False,
            }
        return {**self.hand_controller.status(), "ok": True}

    def set_hand_control(self, enabled: bool) -> dict[str, Any]:
        if self.hand_controller is None:
            return {**self.hand_control_status(), "message": "Desktop hand control bridge is unavailable."}
        return self.hand_controller.set_enabled(bool(enabled))

    def hand_input(self, payload: dict[str, Any] | None) -> dict[str, Any]:
        if self.hand_controller is None:
            return {**self.hand_control_status(), "message": "Desktop hand control bridge is unavailable."}
        return self.hand_controller.dispatch(payload)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run ULTRON 2.7 as a native desktop application")
    parser.add_argument("--port", type=int, default=DEFAULT_PORT)
    parser.add_argument("--strict-port", action="store_true")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--dataset", type=Path, default=None)
    parser.add_argument("--workspace", type=Path, default=None)
    parser.add_argument("--execute", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--no-audit", action="store_true")
    parser.add_argument("--planner-mode", choices=["rules", "hybrid", "llm"], default=None)
    parser.add_argument("--llm-model", default=None)
    parser.add_argument("--llm-endpoint", default=None)
    parser.add_argument("--width", type=int, default=1440)
    parser.add_argument("--height", type=int, default=900)
    parser.add_argument("--windowed", action="store_false", dest="maximized", help="Open at the configured window size")
    parser.add_argument("--fullscreen", action="store_true")
    parser.add_argument("--debug", action="store_true", help="Enable the WebView developer tools")
    parser.set_defaults(maximized=True)
    return parser


def resolve_desktop_config(
    explicit: Path | None,
    *,
    root: Path | None = None,
    app_data: Path | None = None,
    frozen: bool | None = None,
) -> Path | None:
    resources = (root or resource_root()).resolve()
    data_dir = (app_data or desktop_data_dir()).resolve()
    is_frozen = bool(getattr(sys, "frozen", False)) if frozen is None else frozen

    if explicit is not None:
        return explicit.expanduser().resolve()

    candidates: list[Path] = []
    if is_frozen:
        candidates.append(Path(sys.executable).resolve().parent / "ultron.config.json")
        candidates.append(data_dir / "ultron.config.json")
    else:
        candidates.extend(
            (
                Path.cwd() / "ultron.config.json",
                resources / "ultron.config.json",
                data_dir / "ultron.config.json",
            )
        )
    for candidate in candidates:
        if candidate.exists():
            if is_frozen and candidate.resolve() == (data_dir / "ultron.config.json").resolve():
                return migrate_desktop_config(resources, candidate, data_dir)
            return candidate.resolve()

    if is_frozen:
        return create_desktop_config(resources, data_dir)
    return None


def create_desktop_config(resources: Path, app_data: Path, *, home: Path | None = None) -> Path:
    payload = _load_desktop_defaults(resources)

    user_home = (home or Path.home()).resolve()
    app_data.mkdir(parents=True, exist_ok=True)
    payload.update(
        {
            "dataset_path": str((resources / DEFAULT_DATASET_PATH).resolve()),
            "audit_log": str((app_data / "audit.jsonl").resolve()),
            "workspace": str(user_home),
            "safe_roots": [
                str(user_home),
                *(str(user_home / name) for name in ("Desktop", "Documents", "Downloads", "Pictures", "Music", "Videos")),
            ],
            "screenshot_dir": str((app_data / "screenshots").resolve()),
            "neural_router_model": str((app_data / "models" / "neural_router.pt").resolve()),
            "whatsapp_contacts": {},
            "dry_run": False,
            "desktop_profile_version": DESKTOP_PROFILE_VERSION,
        }
    )
    config_path = app_data / "ultron.config.json"
    config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return config_path.resolve()


def migrate_desktop_config(resources: Path, config_path: Path, app_data: Path) -> Path:
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Desktop config must contain a JSON object.")

    version = payload.get("desktop_profile_version", 0)
    if isinstance(version, bool) or not isinstance(version, int):
        version = 0
    needs_upgrade = version < DESKTOP_PROFILE_VERSION
    if needs_upgrade:
        defaults = _load_desktop_defaults(resources)
        preserved = {
            key: value
            for key, value in payload.items()
            if key in DESKTOP_PATH_KEYS or key in DESKTOP_USER_KEYS
        }
        payload.update(
            {
                key: value
                for key, value in defaults.items()
                if key not in DESKTOP_PATH_KEYS and key not in DESKTOP_USER_KEYS
            }
        )
        payload.update(preserved)
        payload["dry_run"] = False
        payload["desktop_profile_version"] = DESKTOP_PROFILE_VERSION

    managed_paths = {
        "dataset_path": str((resources / DEFAULT_DATASET_PATH).resolve()),
        "audit_log": str((app_data / "audit.jsonl").resolve()),
        "screenshot_dir": str((app_data / "screenshots").resolve()),
        "neural_router_model": str((app_data / "models" / "neural_router.pt").resolve()),
    }
    if needs_upgrade or any(payload.get(key) != value for key, value in managed_paths.items()):
        payload.update(managed_paths)
        config_path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return config_path.resolve()


def _load_desktop_defaults(resources: Path) -> dict[str, Any]:
    candidates = (resources / "ultron.config.json", resources / "ultron.config.example.json")
    template = next((candidate for candidate in candidates if candidate.exists()), None)
    if template is None:
        raise FileNotFoundError(f"Desktop config template was not packaged under: {resources}")
    payload = json.loads(template.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("Desktop config template must contain a JSON object.")
    return payload


def prepare_desktop_args(
    args: argparse.Namespace,
    *,
    root: Path | None = None,
    app_data: Path | None = None,
    frozen: bool | None = None,
) -> argparse.Namespace:
    resources = (root or resource_root()).resolve()
    args.host = DEFAULT_HOST
    args.config = resolve_desktop_config(args.config, root=resources, app_data=app_data, frozen=frozen)
    if args.config is None and args.dataset is None:
        args.dataset = resources / DEFAULT_DATASET_PATH
    return args


def start_backend(
    args: argparse.Namespace,
    *,
    web_root: Path | None = None,
    state_factory: Callable[[argparse.Namespace], WebState] = build_state,
) -> DesktopBackend:
    state = state_factory(args)
    requested_port = int(args.port)
    if not 0 <= requested_port <= 65535:
        raise ValueError("Desktop port must be between 0 and 65535.")
    ports = (
        [requested_port]
        if args.strict_port or requested_port == 0
        else list(range(requested_port, min(65535, requested_port + 19) + 1))
    )
    last_error: OSError | None = None
    server: DesktopHTTPServer | None = None
    handler_root = (web_root or resource_root() / "web").resolve()

    for port in ports:
        try:
            server = DesktopHTTPServer((DEFAULT_HOST, port), make_handler(state, handler_root))
            break
        except OSError as exc:
            last_error = exc
    if server is None:
        detail = f" ({last_error})" if last_error else ""
        raise RuntimeError(f"ULTRON could not reserve a local port starting at {requested_port}{detail}")

    actual_port = int(server.server_address[1])
    args.port = actual_port
    thread = threading.Thread(target=server.serve_forever, name="ultron-local-api", daemon=True)
    thread.start()
    return DesktopBackend(server=server, thread=thread, url=f"http://{DEFAULT_HOST}:{actual_port}")


def load_webview() -> ModuleType:
    try:
        import webview
    except ImportError as exc:
        raise RuntimeError(
            "The desktop runtime is not installed. Run: pip install -e .[desktop,windows]"
        ) from exc
    return webview


def attach_windows_icon(window: Any, icon_path: Path) -> None:
    if sys.platform != "win32" or not icon_path.exists() or not hasattr(window, "events"):
        return
    icon_references: list[Any] = []

    def apply_icon(window: Any) -> None:
        try:
            from System.Drawing import Icon  # type: ignore[import-not-found]

            icon = Icon(str(icon_path))
            window.native.Icon = icon
            icon_references.append(icon)
        except Exception:
            logging.getLogger(__name__).exception("Could not apply the ULTRON desktop icon.")

    window.events.before_show += apply_icon


def run_desktop(
    args: argparse.Namespace,
    *,
    webview_module: Any | None = None,
    root: Path | None = None,
    app_data: Path | None = None,
    state_factory: Callable[[argparse.Namespace], WebState] = build_state,
) -> int:
    resources = (root or resource_root()).resolve()
    data_dir = (app_data or desktop_data_dir()).resolve()
    prepare_desktop_args(args, root=resources, app_data=data_dir)
    data_dir.mkdir(parents=True, exist_ok=True)

    backend = start_backend(args, web_root=resources / "web", state_factory=state_factory)
    hand_controller = build_hand_input_controller()
    try:
        webview = webview_module or load_webview()
        webview.settings["ALLOW_DOWNLOADS"] = True
        webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
        webview.settings["OPEN_DEVTOOLS_IN_DEBUG"] = bool(args.debug)
        window = webview.create_window(
            APP_TITLE,
            f"{backend.url}/?shell=desktop",
            js_api=DesktopBridge(data_dir, hand_controller),
            width=max(960, int(args.width)),
            height=max(640, int(args.height)),
            min_size=(900, 620),
            resizable=True,
            fullscreen=bool(args.fullscreen),
            maximized=bool(args.maximized and not args.fullscreen),
            background_color="#020706",
            confirm_close=False,
            text_select=True,
            zoomable=True,
        )
        attach_windows_icon(window, resources / "assets" / "ultron.ico")
        start_options: dict[str, Any] = {
            "debug": bool(args.debug),
            "private_mode": False,
            "storage_path": str(data_dir / "webview"),
        }
        if sys.platform == "win32":
            start_options["gui"] = "edgechromium"
        webview.start(**start_options)
        return 0
    finally:
        hand_controller.close()
        backend.stop()


def _write_error_log(message: str) -> Path:
    directory = desktop_data_dir()
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "desktop-error.log"
    logging.basicConfig(filename=path, level=logging.ERROR, format="%(asctime)s %(levelname)s %(message)s")
    logging.exception(message)
    return path


def _show_error(message: str) -> None:
    if sys.platform == "win32":
        ctypes.windll.user32.MessageBoxW(0, message, f"{APP_TITLE} could not start", 0x10)
        return
    print(message, file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return run_desktop(args)
    except Exception as exc:
        log_path = _write_error_log("ULTRON desktop startup failed")
        _show_error(f"{exc}\n\nDetails were written to:\n{log_path}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

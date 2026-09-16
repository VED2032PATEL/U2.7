# ULTRON 2.7

ULTRON 2.7 is a local-first Jarvis-style desktop assistant. It turns natural-language commands into typed tool calls, validates them, applies a safety policy, and executes them only through an allowlisted tool layer.

The repo is built around the supplied research paper and synthetic laptop-command dataset. The current implementation keeps command planning, voice input, policy, and execution separated so ULTRON can grow toward a Jarvis-style assistant without giving any model raw shell access.

## What Works Now

- Dataset-backed command planner with fuzzy matching and regex fallbacks.
- Typed tool registry for app control, media, websites, local system status, calculations, files, reminders, notes, email drafts, and provider-backed messaging/music.
- Safety policy with low, medium, high, and blocked risk handling.
- Dry-run executor by default, so model/tool output can be tested without changing the computer.
- Real Windows execution for app launch/focus/graceful close, absolute and relative volume/brightness, mute/unmute, media keys, websites, notes, reminders, timer notifications, approved file search/open/create/move/rename, clipboard helpers, screenshots, calculations, and local time/date/battery/storage/system status.
- Configurable safe roots and app aliases for laptop-specific behavior.
- JSONL audit logging for every command.
- Dataset evaluation script for tool-name, argument, and confirmation-gate accuracy.
- Dataset quality analyzer for duplicate-label conflicts, underspecified commands, and safety case extraction.
- Safety regression evaluator for high-risk and confirmation-gated examples.
- Optional LLM planner adapter with Ollama or Groq support, strict JSON parsing, schema validation, and safe fallback behavior.
- Interactive assistant console for repeated commands, confirmations, and JSON inspection.
- Agentic brain layer for multi-step task planning, safe execution, and non-sensitive memory.
- Conversation manager with fast chat routing, clarification behavior, and a consistent calm assistant personality.
- Optional PyTorch neural intent-router training path using the 50,000-example ULTRON synthetic dataset.
- Native Windows desktop application with a persistent WebView2 profile, backed by the local brain/runtime API.
- Browser-hosted development interface using the same cyberpunk green command center.
- Voice mode with transcript cleanup, confidence handling, speech synthesis, transcript history, mute, push-to-talk, and confirmation controls.
- Voice provider layer with Deepgram Nova-3 STT, Aura-2 neural TTS, faster-whisper, whisper.cpp, Piper, and Windows/browser fallbacks.
- Wake-word and voice activity gates for always-listening mode, with push-to-talk still available.
- Backend microphone capture abstraction with sounddevice/mock/browser capture providers and voice diagnostics.
- YouTube playback that resolves the first matching video and loads it in a draggable ULTRON mini-player.
- Semantic LLM intent routing through Ollama or Groq, with strict typed JSON validation and clarification fallback.
- Windows automation executor pack with app aliases, safe-root file enforcement, confirmation modal support, and audit viewing.
- Skill registry and local knowledge base for reusable safe capabilities and document-grounded project context.
- Beta-ready local prototype tooling for setup, launch, diagnostics, demos, and verification.
- Pytest test suite for planner, validation, policy, and execution behavior.

## Project Layout

```text
src/ultron27/            Assistant package
web/                     Desktop and browser visual interface
scripts/                 Utility scripts
assets/                  Windows application icon
tests/                   Safety and planner tests
data/jarvis_dataset_v2/  Supplied synthetic command dataset
docs/                    Supplied research paper and architecture notes
```

## Quick Start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -e .[dev,desktop,windows]
ultron-desktop
ultron "set volume to 40 percent"
ultron "turn the volume up by 10 percent"
ultron "unmute the sound"
ultron "open notepad"
ultron "open YouTube"
ultron "what is 15 percent of 200"
ultron "how much battery is left"
ultron "search the web for Python speech recognition"
ultron "play lofi beats on Spotify"
ultron "hello ultron" --text
ultron "delete project_report.txt" --yes
python scripts/evaluate_dataset.py --split test
python scripts/analyze_dataset_quality.py
python scripts/evaluate_safety_regression.py
python -m ultron27 "launch the basic text editor" --planner-mode hybrid
python -m ultron27 --interactive
python -m ultron27 "/plan Create a note called project ideas and add that I should test voice mode next." --text
python -m ultron27 "/do Create a note called project ideas and add that I should test voice mode next." --text --execute --workspace .
python scripts/run_phase7_ui.py --port 8765
python scripts/run_phase8_voice_ui.py --port 8765
python scripts/run_phase9_voice_ui.py --port 8765
python scripts/run_phase10_wake_ui.py --port 8765
python scripts/run_phase11_windows_ui.py --port 8765
python scripts/run_phase12_skills_ui.py --port 8765
python scripts/launch_ultron.py --execute
python scripts/demo_phase13.py
python scripts/verify_phase13.py
python -m unittest discover -s tests
```

## Desktop Application

The recommended Windows setup now installs the native desktop runtime and creates an `ULTRON 2.7` shortcut on the desktop:

```powershell
.\scripts\setup_ultron_windows.ps1
```

Launch the native app from the shortcut or directly:

```powershell
.\.venv\Scripts\ultron-desktop.exe
```

ULTRON opens in its own resizable Windows window with native minimize, maximize, Alt+Tab, and close behavior. Its camera, research, and 3D-model windows remain movable workspaces inside the application. WebView state and permissions persist under `%LOCALAPPDATA%\ULTRON 2.7\webview`; source launches continue to use the repo's `ultron.config.json`.

Build a distributable application directory with:

```powershell
.\scripts\build_ultron_desktop.ps1
```

The resulting executable is `%LOCALAPPDATA%\ULTRON 2.7\desktop-build\dist\ULTRON 2.7\ULTRON 2.7.exe`. Keeping disposable build output outside the OneDrive checkout prevents sync-provider file locks. Pass `-OutputRoot .\dist` when building from a non-synced checkout and repo-local output is preferred. The build uses an `onedir` layout so startup stays fast and the bundled UI/data files remain inspectable. `ultron-ui` and `python scripts\launch_ultron.py --open` remain available for browser-based development.

### Whole-desktop hand control

The packaged Windows application can turn the camera hand tracker into system-wide mouse and touchpad input. Open **System**, find **Hand control**, select **Desktop**, and press **Start**. The book icon opens the complete gesture map inside ULTRON.

- index finger: move the cursor; thumb-index pinch: left click, double-click, or hold to drag,
- thumb-middle pinch: right click; thumb-ring pinch: middle click,
- two raised fingers: vertical/horizontal scroll; change their spread to zoom,
- three-finger swipe down/up: show the desktop or restore minimized windows,
- three-finger swipe left/right: switch apps,
- four-finger swipe left/right: switch virtual desktops; four-finger swipe up: Task View,
- little-finger swipe left/right: browser back or forward,
- hold a fist for one second: pause or resume hand input.

Press `Ctrl+Alt+H` at any time for the native emergency stop. Input also pauses and releases any held mouse button when the tracked hand disappears. Whole-desktop mode is deliberately available only through the trusted PyWebView desktop bridge; the ordinary browser interface keeps it disabled. Windows can reject synthetic input aimed at a process running with higher privileges, so run ULTRON at the same privilege level as the application being controlled.

Natural command examples:

```text
open Settings
switch to Spotify
close Notepad
increase brightness by 20 percent
pause the music
play the next song
search YouTube for Python tutorials
play Interstellar trailer on YouTube
find PDF files in Downloads
create a folder called invoices in Documents
rename report.txt to final_report.txt
move final_report.txt to Documents
create a note called groceries with milk and eggs
start a timer for 10 minutes
draft an email to alex@example.com about the report
WhatsApp, Em Hitansh, hi
```

Closing apps, moving or renaming files, opening email drafts, locking the PC, and other medium/high-risk actions remain confirmation-gated. WhatsApp confirmation is controlled separately by `whatsapp_require_confirmation`; your local config can opt into immediate exact-contact sending.

## Optional Neural Router

The larger synthetic router dataset lives at:

```text
data/ultron_synthetic_training_dataset_v2_large_50000.jsonl
```

Train the advisory neural router with:

```powershell
pip install -e .[neural]
python -m ultron27.neural_router.train --dataset data/ultron_synthetic_training_dataset_v2_large_50000.jsonl --output .ultron/models/neural_router.pt
```

Then enable it with either config or environment variables:

```powershell
$env:ULTRON_NEURAL_ROUTER_ENABLED = "true"
$env:ULTRON_NEURAL_ROUTER_MODEL = ".ultron/models/neural_router.pt"
```

The neural router only predicts route, intent, tool name, risk, and confirmation labels. It never executes tools directly and never bypasses schema validation, policy gates, executor safety checks, or audit logging.

If the `ultron` command is not available after installation, use:

```powershell
python -m ultron27 "set volume to 40 percent"
```

By default ULTRON runs in dry-run mode. In dry-run mode it will speak what it would do, but it will not actually open apps, launch browser searches, or open Spotify. Use `--execute` only after reviewing the tool, policy, and implementation. High-risk actions are still not implemented as destructive operations, even after confirmation.

## Configuration

ULTRON looks for `ultron.config.json` first, then `.ultron/config.json`. You can start from `ultron.config.example.json`:

```json
{
  "dataset_path": "data/jarvis_dataset_v2/jarvis_laptop_commands_synthetic_v2.jsonl",
  "audit_log": ".ultron/audit.jsonl",
  "dry_run": true,
  "workspace": ".",
  "safe_roots": [".", "~/Desktop", "~/Documents", "~/Downloads"],
  "screenshot_dir": ".ultron/screenshots",
  "app_aliases": {
    "chrome": "chrome.exe",
    "google chrome": "chrome.exe",
    "vs code": "code",
    "vscode": "code",
    "notepad": "notepad.exe",
    "spotify": "spotify.exe",
    "calculator": "calc.exe",
    "calc": "calc.exe",
    "file explorer": "explorer.exe",
    "explorer": "explorer.exe",
    "terminal": "wt.exe"
  },
  "planner_mode": "rules",
  "llm_provider": "ollama",
  "llm_model": "qwen2.5:7b-instruct",
  "llm_endpoint": "http://localhost:11434",
  "llm_timeout_seconds": 8,
  "voice_stt_provider": "browser",
  "voice_capture_provider": "browser",
  "voice_microphone_device": null,
  "voice_sample_rate": 16000,
  "voice_capture_seconds": 4,
  "voice_tts_provider": "browser_speech_synthesis",
  "voice_tts_model": "aura-2-orion-en",
  "voice_stt_model_path": null,
  "voice_tts_model_path": null,
  "voice_tts_voice_path": null,
  "voice_device": "cpu",
  "voice_identity": "ULTRON",
  "voice_preference": "Microsoft George",
  "voice_rate": 1.03,
  "voice_pitch": 1.0,
  "voice_volume": 1.0,
  "wake_word_provider": "text",
  "wake_auto_start": false,
  "wake_phrases": ["ULTRON", "Hey ULTRON"],
  "wake_model_path": null,
  "vad_provider": "energy",
  "vad_energy_threshold": 0.015,
  "clap_spike_ratio": 7.0,
  "clap_min_rms": 0.012,
  "clap_min_gap_s": 0.05,
  "clap_max_gap_s": 0.35,
  "clap_cooldown_s": 0.45,
  "startup_briefing_enabled": true,
  "assistant_location": "Jabalpur",
  "speech_barge_in_enabled": true
}
```

Environment variables override the JSON config:

```powershell
$env:ULTRON_DRY_RUN = "true"
$env:ULTRON_AUDIT_LOG = ".ultron/audit.jsonl"
$env:ULTRON_SAFE_ROOTS = ".;~/Desktop;~/Documents;~/Downloads"
$env:ULTRON_PLANNER_MODE = "rules"
$env:ULTRON_LLM_PROVIDER = "ollama"
$env:ULTRON_LLM_MODEL = "qwen2.5:7b-instruct"
$env:ULTRON_LLM_ENDPOINT = "http://localhost:11434"
$env:ULTRON_STT_PROVIDER = "browser"
$env:ULTRON_STT_LANGUAGE = "multi"
$env:ULTRON_STT_KEYTERMS = "ULTRON;WhatsApp;Spotify;Em Hitansh"
$env:ULTRON_STARTUP_BRIEFING_ENABLED = "true"
$env:ULTRON_LOCATION = "Jabalpur"
$env:ULTRON_SPEECH_BARGE_IN_ENABLED = "true"
$env:ULTRON_CAPTURE_PROVIDER = "browser"
$env:ULTRON_MICROPHONE_DEVICE = ""
$env:ULTRON_VOICE_SAMPLE_RATE = "16000"
$env:ULTRON_VOICE_CAPTURE_SECONDS = "4"
$env:ULTRON_TTS_PROVIDER = "browser_speech_synthesis"
$env:ULTRON_TTS_MODEL = "aura-2-orion-en"
$env:ULTRON_STT_MODEL_PATH = ".ultron/models/whisper"
$env:ULTRON_TTS_MODEL_PATH = ".ultron/models/piper.onnx"
$env:ULTRON_TTS_VOICE_PATH = ".ultron/models/piper.json"
$env:ULTRON_VOICE_DEVICE = "cpu"
$env:ULTRON_VOICE_IDENTITY = "ULTRON"
$env:ULTRON_WAKE_WORD_PROVIDER = "text"
$env:ULTRON_WAKE_PHRASES = "ULTRON;Hey ULTRON"
$env:ULTRON_VAD_PROVIDER = "energy"
$env:ULTRON_VAD_ENERGY_THRESHOLD = "0.015"
```

For the cloud-backed setup, use Groq for planning and Deepgram for speech recognition and natural Aura-2 speech:

```powershell
[Environment]::SetEnvironmentVariable("GROQ_API_KEY", "your-groq-key", "User")
[Environment]::SetEnvironmentVariable("DEEPGRAM_API_KEY", "your-deepgram-key", "User")
$env:ULTRON_LLM_PROVIDER = "groq"
$env:ULTRON_LLM_MODEL = "openai/gpt-oss-20b"
$env:ULTRON_LLM_ENDPOINT = "https://api.groq.com/openai/v1"
$env:ULTRON_STT_PROVIDER = "deepgram"
$env:ULTRON_STT_MODEL = "nova-3"
$env:ULTRON_STT_LANGUAGE = "multi"
$env:ULTRON_STT_KEYTERMS = "ULTRON;WhatsApp;Spotify;Em Hitansh"
$env:ULTRON_TTS_PROVIDER = "deepgram"
$env:ULTRON_TTS_MODEL = "aura-2-orion-en"
$env:ULTRON_VOICE_RATE = "1.03"
```

For Hinglish or other English/Hindi code-switching, use Deepgram Nova-3 with `voice_stt_language` set to `multi`. Add uncommon contact names and product terms to `voice_stt_keyterms`; ULTRON sends them as repeated Nova-3 keyterm hints and also uses them to repair close transcript spellings locally.

Aura-2 replies are relayed through a short-lived local stream. Playback can begin as soon as Deepgram returns the first audio instead of waiting for the complete MP3 to be generated, downloaded, and encoded.

For reliable Spotify Premium playback, create a Spotify Developer app, add this redirect URI to it, then authorize ULTRON:

```powershell
[Environment]::SetEnvironmentVariable("SPOTIFY_CLIENT_ID", "your-spotify-client-id", "User")
python scripts/spotify_auth.py
```

The redirect URI is `http://127.0.0.1:8766/callback`. You can also run `python scripts/spotify_auth.py --client-id your-spotify-client-id`; the PKCE login stores the public client ID with the local token. ULTRON uses the Spotify Web API first and targets an available Spotify Connect device. If authorization is missing, the Windows fallback searches the exact query and only reports success after it finds and clicks the visible Play button.

For the most deterministic WhatsApp sending, you can add contact-to-number mappings to `ultron.config.json`. Use international numbers with country code:

```json
"whatsapp_contacts": {
  "mom": "+919876543210",
  "project lead": "+15551234567"
}
```

You can also use the exact saved WhatsApp contact name without a number mapping, for example `WhatsApp, Em Hitansh, Hi`. WhatsApp sending requires confirmation by default. Set `"whatsapp_require_confirmation": false` in your local `ultron.config.json` (or `ULTRON_WHATSAPP_REQUIRE_CONFIRMATION=false`) to send immediately after a valid command. For saved names, ULTRON opens WhatsApp when needed, waits for its chat interface, selects a candidate only when the active chat header exactly matches the requested name, refuses to overwrite existing drafts, verifies the exact message in the composer, presses Send once, and checks that the composer cleared.

Useful CLI flags:

```powershell
ultron "open notepad" --no-audit
ultron "open notepad" --text
ultron --interactive
ultron "/plan create a note called ideas and add that voice mode is next" --text
ultron "/do create a note called ideas and add that voice mode is next" --text --execute
ultron "/memory" --text
ultron "/forget last_note" --text
ultron-ui --port 8765
python scripts/run_phase10_wake_ui.py --port 8765
python scripts/run_phase11_windows_ui.py --port 8765
python scripts/run_phase12_skills_ui.py --port 8765
python scripts/launch_ultron.py --port 8765 --execute
ultron "create note standup" --workspace .
ultron "open notepad" --execute
ultron "search the web for local voice assistants" --execute
ultron "find information about quantum computing" --execute
ultron "play lofi beats on Spotify" --execute
ultron "WhatsApp Mom: I will be home at seven" --yes
ultron "delete project_report.txt" --yes
```

## Phase 2 Safe Execution

Phase 2 adds real execution for low-risk tools while keeping destructive commands disabled:

- `create_note` and `append_to_note` write Markdown files under `notes/`.
- `set_reminder` and `start_timer` append JSONL records under `.ultron/`.
- `search_files`, `open_file`, and `open_folder` operate only inside configured `safe_roots`.
- `open_application` uses configurable `app_aliases`.
- `search_web` opens a browser search URL through a typed low-risk tool.
- `play_music` opens Spotify search through a typed low-risk tool.
- `play_youtube_video` resolves the first matching YouTube video and hands it to ULTRON's in-app mini-player.
- `copy_to_clipboard` and `read_clipboard` use Windows clipboard commands when available.
- `take_screenshot` saves under `screenshot_dir` when Pillow/ImageGrab is available.

The floating YouTube player stays inside the desktop interface and adds prominent Play/Pause, Back 10 seconds, and Forward 10 seconds buttons beneath the video. Playback pauses when the player or ULTRON is minimized and stops when the player is closed.

Use dry-run previews first:

```powershell
python -m ultron27 "start timer for 15 minutes"
python -m ultron27 "create note phase two" --execute --workspace .
```

## Phase 3 Dataset Quality

Phase 3 adds dataset quality and safety evaluation tooling:

- `scripts/analyze_dataset_quality.py` writes `docs/phase3_dataset_quality_report.json`.
- The same script extracts `data/regression/safety_cases.jsonl`.
- `scripts/evaluate_safety_regression.py` checks whether planner and policy behavior matches those safety cases.

Current audit summary:

```text
Total examples: 2500
Unique utterances: 2319
Duplicate utterance groups: 101
Conflicting duplicate groups: 101
Underspecified examples: 879
Safety examples: 362
Safety regression policy-action accuracy: 1.0
```

## Phase 4 LLM Planner

Phase 4 adds an optional LLM planner. The default remains `rules`, so ULTRON continues to work without any model server.

Planner modes:

- `rules`: dataset, regex, and fuzzy planning only.
- `hybrid`: use rules first; if no safe rule matches, try the LLM planner.
- `llm`: try the LLM planner first, then fall back safely if the provider is unavailable or invalid.

Example:

```powershell
python -m ultron27 "launch the basic text editor" --planner-mode hybrid
```

The LLM must return JSON like:

```json
{
  "intent": "open_app",
  "tool_name": "open_application",
  "tool_arguments": {
    "app": "notepad"
  },
  "confidence": 0.8
}
```

The returned tool call still goes through schema validation, risk policy, confirmation gates, and the safe executor.

## Phase 5 Interactive Prototype

Phase 5 adds a basic assistant console for day-to-day prototype testing:

```powershell
python -m ultron27 --interactive
```

Inside the console:

```text
/help              Show console commands.
/json <command>    Run a command and print the full JSON payload.
/plan <goal>       Show a safe multi-step plan without executing it.
/do <goal>         Plan and execute allowed steps through ULTRON's runtime.
/memory            Show stored non-sensitive memory.
/forget <query>    Remove matching memory entries.
/yes <command>     Confirm a command that needs confirmation.
/exit              Leave the console.
```

The console uses the same runtime pipeline as the one-shot CLI:

```text
utterance -> planner -> validator -> policy -> executor -> audit -> response
```

Single-command mode still prints JSON by default. Use `--text` for the same concise response format used by the console:

```powershell
python -m ultron27 "set volume to 40 percent" --text
```

## Phase 6 Brain Layer

Phase 6 adds `UltronBrain`, a task-level reasoning layer for multi-step goals. The brain can decompose a goal into steps, preview the tool calls, execute allowed steps, pause for confirmation, and remember useful non-sensitive context.

Example:

```powershell
python -m ultron27 "/plan Create a note called project ideas and add that I should test voice mode next." --text
python -m ultron27 "/do Create a note called project ideas and add that I should test voice mode next." --text --execute --workspace .
```

Brain commands:

```text
/plan <goal>       Build a TaskPlan without execution.
/do <goal>         Execute each allowed step through the safe runtime.
/memory            Show stored non-sensitive memory.
/forget <query>    Delete matching memory entries.
```

The brain stores memory at `.ultron/memory.json` by default. It rejects obvious sensitive keys or values such as passwords, API keys, tokens, credentials, and secrets.

## Phase 7 Visual Interface

Phase 7 adds a local web interface with a black cyberpunk scene, green particle field, and animated Three.js plasma sphere.

Run it with:

```powershell
python scripts/run_phase7_ui.py --port 8765
```

Then open:

```text
http://127.0.0.1:8765
```

The interface includes:

- a staged opening sequence that assembles the neural core, verifies local subsystems, and reveals the workspace before the spoken briefing,
- listening state: contracted calmer sphere,
- thinking state: spiraling green eclipse/ring animation,
- speaking state: expanded plasma lines and stronger glow,
- live subtitles below the sphere,
- subtitles on/off toggle,
- typed command input and Send button,
- development controls for Listening, Thinking, Speaking, and Idle.

The Jarvis workspace also supports:

- an in-interface Camera window for `open camera` and `take a picture`, with drag, resize, minimize, maximize, and validated saves under `screenshot_dir`,
- an in-interface Research window for web questions, with Groq synthesis in ULTRON's own wording and separate evidence links,
- a time-aware startup greeting with current Open-Meteo weather for `assistant_location`,
- speech barge-in: sustained speech while browser TTS is active cancels the reply and starts a fresh command capture,
- opt-in MediaPipe hand controls for both ULTRON workspace manipulation and Windows-wide cursor, click, drag, scroll, zoom, app switching, desktop switching, and navigation gestures,
- a Three.js Camera Relief designer that converts the visible frame into an adjustable textured depth mesh and exports OBJ geometry,
- automatic safe memory for phrasing such as `my favorite song is Blinding Lights`, including later resolution of `play my favorite song`.

Hand tracking loads the MediaPipe Tasks Vision runtime and hand-landmarker model from their pinned public CDN/model URLs the first time it is enabled. Camera frames stay in the browser for gesture inference. The 3D designer is intentionally described as a single-view depth relief; it cannot infer hidden sides of an object from one photograph.

Local API endpoints:

```text
POST /api/command
POST /api/research
POST /api/camera/capture
GET  /api/briefing
GET  /api/status
GET  /api/memory
POST /api/memory/forget
POST /api/memory/toggle
POST /api/subtitles/toggle
POST /api/state
```

Typed input first passes through the conversation manager. Simple chat, help, thanks, and memory commands are answered through a low-risk `assistant_reply` tool path. Laptop actions still go through the brain, typed tool call, schema validation, policy, executor, audit log, and response pipeline.

## Phase 8 Voice Mode

Phase 8 adds voice interaction on top of the Phase 7 interface. The browser captures speech when its speech-recognition API is available, sends the transcript to ULTRON's local API, and ULTRON answers through browser speech synthesis unless muted. The backend cleans wake words and filler text, rejects empty/noisy inputs, and asks for clarification when a provider reports low transcript confidence.

Run it with:

```powershell
python scripts/run_phase8_voice_ui.py --port 8765
```

Voice controls:

- Mic On/Off for browser speech capture.
- Push-to-talk or continuous recognition.
- Mute Off/Muted for ULTRON voice output.
- Stop Voice to cancel speech synthesis.
- Confirm for explicit high-risk action confirmation.
- Mock Voice to test the full voice pipeline without a microphone.

Voice API endpoints:

```text
POST /api/voice/start
POST /api/voice/stop
POST /api/voice/transcribe
POST /api/speak
GET  /api/voice/status
```

Voice still uses the same safe runtime:

```text
voice -> STT -> brain/runtime -> typed tool call -> validation -> policy
-> executor -> audit -> response -> TTS
```

If microphone/STT is unavailable, typed mode and Mock Voice still work. If TTS is unavailable or muted, subtitles still show the response.

Conversation history in the UI shows what the user said, what ULTRON understood, and the final response. Memory controls let the user view memory, forget matching facts, and turn learning on or off. ULTRON refuses to store obvious secrets such as passwords, tokens, credentials, and API keys.

## Phase 14 Backend Voice Capture

Phase 14 adds an optional backend capture path while keeping browser voice as a fallback. Configure it with:

```json
{
  "voice_capture_provider": "sounddevice",
  "voice_stt_provider": "faster_whisper",
  "voice_stt_model": "base.en",
  "voice_stt_model_path": null,
  "voice_sample_rate": 16000,
  "voice_capture_seconds": 4
}
```

Capture providers:

- `browser`: browser captures speech/transcripts.
- `sounddevice`: backend records microphone audio when the optional Python package is installed.
- `mock`: deterministic backend capture for tests and demos.

New route:

```text
POST /api/voice/capture
```

The voice diagnostics panel shows the capture provider, STT provider, active microphone, last understood transcript, confidence, audio duration, speech duration, and rejected/noisy status. Empty, noisy, or too-short audio is ignored before command execution. Low-confidence transcripts ask for clarification.

`voice_stt_model` accepts faster-whisper model names such as `base.en`, `small.en`, or `medium.en`. Use `voice_stt_model_path` instead when you have already downloaded a model folder and want a fully local path.

## Phase 15 Semantic Intent Routing

Phase 15 strengthens natural-language understanding with a semantic router. The fast rules still handle obvious commands first. If a command is unsupported by rules and `planner_mode` is `hybrid` or `llm`, ULTRON asks the configured Ollama or Groq model to return one strict JSON tool call.

The model can only propose typed tools:

```json
{
  "intent": "open_app",
  "tool_name": "open_application",
  "tool_arguments": {
    "app": "notepad"
  },
  "confidence": 0.92,
  "needs_clarification": false,
  "clarification_question": ""
}
```

Invalid JSON, unknown tools, invalid arguments, and low confidence are rejected or converted into `ask_clarification`. Provider unavailability does not crash ULTRON; it falls back to the safe rules result.

## Phase 9 Offline Voice Providers

Phase 9 strengthens the voice layer with offline-first provider adapters while keeping browser voice as the practical fallback. The browser UI now shows the configured and active STT/TTS providers, and the backend exposes health-check routes for provider readiness.

Run it with:

```powershell
python scripts/run_phase9_voice_ui.py --port 8765
```

Provider choices:

- `voice_stt_provider`: `browser`, `text_payload`, `faster_whisper`, `whisper_cpp`, `deepgram`, or `mock`.
- `voice_stt_model`: faster-whisper model name such as `base.en`, or Deepgram model name such as `nova-3`.
- `voice_tts_provider`: `deepgram`, `browser_speech_synthesis`, `piper`, `pyttsx3`, or `mock`.
- `voice_tts_model`: Deepgram Aura model such as `aura-2-orion-en`.
- `voice_stt_model_path`: local faster-whisper or whisper.cpp model path.
- `voice_tts_model_path`: local Piper model path.
- `voice_tts_voice_path`: optional Piper voice config path.
- `voice_device`: `cpu`, `cuda`, or `auto`.
- `voice_identity`, `voice_rate`, `voice_pitch`, and `voice_volume`: voice output tuning.

New provider endpoints:

```text
GET  /api/voice/providers
POST /api/voice/test-stt
POST /api/voice/test-tts
```

If a cloud or local voice provider is unavailable, ULTRON reports the issue and falls back to browser transcript/speech behavior. Typed commands, subtitles, and the safe runtime continue to work.

## Phase 10 Wake Word and VAD

Phase 10 adds an input gate before speech reaches STT and the brain. Wake word detection and VAD only decide whether a speech segment should be considered; they never execute tools directly.

Run it with:

```powershell
python scripts/run_phase10_wake_ui.py --port 8765
```

Always-listening states:

```text
inactive -> waiting_for_wake_word -> listening -> transcribing
-> thinking -> speaking
```

Wake/VAD providers:

- `wake_word_provider`: `text`, `openwakeword`, `double_clap`, or `mock`.
- `wake_auto_start`: starts wake standby with the server so no mic/unmute button is required.
- `wake_phrases`: defaults to `ULTRON` and `Hey ULTRON`.
- `wake_model_path`: optional openWakeWord model path.
- `vad_provider`: `energy`, `silero`, `webrtc`, or `mock`.
- `vad_energy_threshold`: fallback energy threshold for noisy/empty input.

For hands-free clap standby, set `wake_word_provider` to `double_clap`, `wake_auto_start` to `true`, and `voice_capture_provider` to `sounddevice`. ULTRON then records short energy-only windows without speech-to-text. A valid double clap triggers “At your service, sir,” followed by one full command capture using `voice_capture_seconds`; after the command or a silent timeout, it returns to clap standby automatically.
- `double_clap`: optional adaptive energy-spike wake gate inspired by the reviewed Jarvis script. It only opens listening mode and never executes actions directly.

Wake API endpoints:

```text
POST /api/wake/start
POST /api/wake/stop
GET  /api/wake/status
POST /api/wake/process
```

`/api/wake/process` is the browser adapter route for candidate speech segments. It ignores empty/noisy audio and speech without `ULTRON` or `Hey ULTRON` while the session is waiting for the wake word. Push-to-talk still uses `/api/voice/transcribe`.

## Phase 11 Windows Automation Pack

Phase 11 formalizes real low-risk Windows laptop automation inside the executor boundary. ULTRON still never gives the planner or LLM raw shell access. Every action must be a typed tool call that passes schema validation and policy before the executor adapter sees it.

Run it with:

```powershell
python scripts/run_phase11_windows_ui.py --port 8765
```

Implemented or safely fronted Windows tasks:

- open installed apps and built-in Settings, Camera, Task Manager, Control Panel, Clock, Photos, and Microsoft Store targets,
- switch to running apps and request graceful close without force-killing unsaved work,
- set or adjust volume and brightness, mute/unmute, and use play/pause/next/previous media commands,
- play verified Spotify results and send exact-recipient WhatsApp messages,
- open named websites or validated domains and run site-specific searches,
- answer local time, date, battery, storage, system-information, and bounded arithmetic requests without an LLM,
- search/open files and folders only inside configured `safe_roots`, create folders, and confirmation-gate collision-safe move/rename operations,
- create and append case-preserving notes, read/write clipboard text, and take screenshots,
- save reminders and start detached Windows timer notifications,
- open confirmation-gated email drafts through the default mail handler without sending them.

Permission behavior:

```text
low-risk -> allowed after validation
medium-risk -> confirmation required
high-risk -> confirmation required
destructive -> confirmation-gated but not implemented
blocked -> rejected
```

New API endpoint:

```text
GET /api/audit/recent?limit=25
```

The Phase 7-10 interface now shows a confirmation modal for risky typed or voice actions. Confirming retries the command with `confirmed: true`; cancelling clears the pending voice confirmation state.

## Phase 12 Skills and Local Knowledge

Phase 12 adds a skill registry and local knowledge base. Skills are reusable typed capabilities with input schemas, risk levels, handlers, examples, policy checks, and audit records. Knowledge retrieval can inform summaries and planning, but it cannot execute actions or bypass the safe tool runtime.

Run it with:

```powershell
python scripts/run_phase12_skills_ui.py --port 8765
```

Built-in skills:

- `notes`: create or append notes through safe note tools,
- `reminders`: save reminders through the safe reminder tool,
- `file_search`: search files inside safe roots,
- `project_summary`: summarize matching local knowledge,
- `daily_planning`: draft a daily plan from explicit priorities and local context.

Knowledge support:

- ingests Markdown, TXT, PDF, and DOCX where local dependencies are available,
- stores metadata and chunks under `.ultron/knowledge/index.json`,
- rejects obvious secrets such as passwords, API keys, tokens, credentials, and private keys,
- searches by keyword first, with an embedding-provider abstraction ready for later.

New endpoints:

```text
GET  /api/skills
POST /api/skills/run
POST /api/knowledge/ingest
GET  /api/knowledge/search?query=<text>&limit=5
```

The web interface now includes panels for skills, memory/knowledge, local knowledge search, and recent task history.

## Phase 13 Beta Prototype Tooling

Phase 13 makes ULTRON easier to install, launch, diagnose, demo, and verify on Windows.

Recommended setup:

```powershell
.\scripts\setup_ultron_windows.ps1
```

Recommended desktop launch:

```powershell
.\.venv\Scripts\ultron-desktop.exe
```

The desktop launcher starts the loopback-only backend, selects another local port if needed, opens the native window, and shuts the backend down when that window closes. Use `python scripts\launch_ultron.py --open` when a browser-hosted development session is preferable.

Operator scripts:

```powershell
python scripts\check_dependencies.py
python scripts\check_providers.py
python scripts\config_wizard.py --defaults
python scripts\demo_phase13.py
python scripts\verify_phase13.py
```

New diagnostics endpoint and page:

```text
GET /api/diagnostics
http://127.0.0.1:8765/diagnostics
```

Diagnostics show backend readiness, brain status, voice provider status, memory path, audit path, safe roots, and recent readiness errors. The diagnostics page is read-only and does not execute tools.

## Example

```powershell
python -m ultron27 "open notepad"
```

Example output:

```json
{
  "utterance": "open notepad",
  "tool_call": {
    "name": "open_application",
    "arguments": {
      "app": "notepad"
    }
  },
  "policy": {
    "action": "allow",
    "reason": "Low-risk command can run."
  },
  "result": {
    "status": "dry_run",
    "message": "Would open application: notepad"
  }
}
```

## Safety Model

ULTRON does not give an LLM unrestricted shell access. The intended production flow is:

```text
utterance -> planner -> typed tool call -> schema validator -> policy gate
-> executor -> audit log -> response
```

Medium-risk and high-risk operations require confirmation. In voice mode, confirmation must be explicit, such as `yes confirm`. Destructive execution is intentionally left unimplemented in this MVP.

Skills and knowledge do not create a side channel around this model. Skills validate their own schemas and then call the same safe runtime for any OS-facing action. Knowledge search returns context only.

Phase 13 setup, launcher, diagnostics, demo, and verification scripts are operator tooling. They do not give ULTRON a new execution path or raw shell authority.

## Roadmap

1. Install and tune real faster-whisper/whisper.cpp and Piper models for the target laptop.
2. Install real openWakeWord and Silero/WebRTC VAD dependencies for microphone audio.
3. Add streaming partial STT transcripts; neural TTS playback already uses progressive audio streaming.
4. Grow the dataset with real corrected transcripts and Hinglish/Hindi variants.
5. Add embeddings and source-aware answer generation for the local knowledge base.

# Reactive Aperture Core

The locally bundled Three.js scene uses a bevelled metal housing, overlapping iris blades, a shader-driven optical lens, counter-rotating segments, and instanced signal markers. No CDN, external image, microphone permission, or new API key is needed for the core itself.

## Activity reactions

| Activity | Reaction |
| --- | --- |
| Startup | Lens appears first, followed by housing and outer segments |
| Standby | Dim blue-green illumination, nearly closed aperture, slow motion |
| Listening | Cyan illumination, wider iris, expanding signal waveform |
| Transcribing | Lens scan with faster signal movement |
| Thinking | Warm illumination and accelerated counter-rotation |
| Speaking | Green-white pulses and moving iris, following speech start/stop and text cadence |
| Research | Blue lens sweep and circulating signals |
| Camera / model generation | Open aperture with a slower optical scan |
| Media task | Rhythmic waveform |
| Task execution | Active signal lanes; an outer arc shows completed-step fraction when available |
| Needs confirmation | Amber, slowed motion; stays until a response or cancellation |
| Success | Brief bright green acknowledgement |
| Failure / blocked action | Red illumination and a contracted aperture |
| Paused / cancelled / simulated | Quiet, muted lighting; simulations never flash success |

The activity controller wraps existing requests; it does not change tool policies or execute additional actions. Request animations reflect the requested category, then result animations use actual returned status. Agent progress is the completed-step fraction, not an invented time estimate. Opening the app does not replay success animations from task history. Speech motion is a visual cadence, not a live audio spectrum. Standard listening/speaking states take priority over background work, except brief results and confirmations.

Motion is delta-time based, pauses when the page is hidden, and becomes static when the OS/browser requests reduced motion. Desktop pointer movement gives subtle parallax without capturing clicks or changing the system cursor. Camera framing adapts to the drawer, subtitles, and window dimensions.

## Desktop update

The [Crimson cinematic persona](crimson-mode.md) adds core-first transitions and Python conversation styling. Install that feature with a full desktop rebuild. The visual-only updater below only handles the original aperture/activity modules.

New builds include these assets automatically through `ultron27.spec`. Existing supported PyInstaller packages can receive the visual update without replacing their Python backend:

```powershell
.\scripts\update_desktop_visuals.ps1 -WhatIf
.\scripts\update_desktop_visuals.ps1
```

By default the script resolves the `ULTRON 2.7.lnk` shortcut on the Windows desktop. If its target is missing, it checks the usual local AppData install, then the repository's `dist` package. Add `-UpdateShortcut` to back up and repair the desktop shortcut as well. To target a particular package:

```powershell
.\scripts\update_desktop_visuals.ps1 -DesktopRoot '.\dist\ULTRON 2.7'
```

The updater verifies known frontend hooks before writing, backs up affected files under `visual-backups`, copies the two local core modules, and adds request activity hooks to older frontends. It preserves settings, API keys, and the backend. Close and reopen the application afterward. Restore the backed-up files to `_internal\web` to roll back. This visual-only update does not install the separate Agent Tasks backend into an old executable; that requires a full desktop rebuild.

## Checks

```powershell
node scripts/core_visual_smoke.cjs
node scripts/agent_ui_smoke.cjs
python -m unittest discover -s tests
```

The browser tests require Playwright and pngjs. The core check covers all activity states, desktop/mobile framing, changing canvas pixels, pointer response, startup, reduced motion, shader errors, resource disposal, and activity-result mappings. Screenshots are saved locally in `.ultron/core-visual-smoke`.

Set `ULTRON_CORE_WEB_ROOT` to an installed package's `_internal\web` directory to run the same visual checks against the desktop assets. Set `ULTRON_BROWSER_EXECUTABLE` to select a browser; installed Edge is detected by default.

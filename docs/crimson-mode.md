# Crimson Cinematic Mode

The eclipse icon below the drawer toggle starts a 12-second transformation: two restrained signal glitches, lens ignition, mechanical housing illumination, then a crimson wave across the interface. Click it again or press Escape to restore the standard appearance. Restoration immediately resets the conversation persona, with the visuals fading back over four seconds. This works in both focus view and the full interface.

System > Cinematic events enables occasional automatic transformations. It is initially enabled and the preference is saved in this webview's local storage. After 7-12 accumulated minutes of visible, quiet standby, a transformation begins. It stays crimson for 90 seconds, then restores. Time while hidden, listening, speaking, processing a task, or awaiting confirmation does not count toward the automatic trigger. Automatic events do not speak or execute anything. Manual Crimson mode lasts until restored; reloading starts in standard mode.

With the OS/browser's reduced-motion preference, automatic events and glitches are disabled. Manual switching uses a short color fade, without moving rings or a traveling wave.

## Conversation and Voice

While Crimson is active, Groq chat and research replies receive a fixed, request-local presentation style: commanding, self-assured, dryly witty, and slightly arrogant, still addressing the user as sir. Standard mode explicitly resets that style despite earlier conversation history. No user-supplied prompt is accepted as a persona. Only `standard` and `crimson` are valid API values.

This is a fictional villain aesthetic, not an autonomous takeover. The planner, permissions, confirmation gates, file boundaries, memory and factual reporting remain unchanged. Tool receipts stay literal; errors are not rewritten as successes. Unknown answers remain unknown. Without Groq, existing local fallback replies remain available but do not gain model-generated swagger.

Neural speech uses the same configured voice with a 2% slower, pitch-preserving delivery; browser fallback adds a subtle pitch reduction. There is no additional synthesis request, voice cloning, artificial growling or audio delay. Speech visuals follow playback events and text cadence, not a measured audio spectrum.

Casual chat with Groq's GPT-OSS models uses low reasoning effort and a 512-token completion budget so internal reasoning does not exhaust the old 180-token limit before a visible reply. Other models, research and tool planning retain their existing settings. See [Groq's reasoning documentation](https://console.groq.com/docs/reasoning).

## Visual Reactions

Activity transitions emit expanding rings. Thinking tilts the outer assembly; execution lifts successive iris blades; speech opens and pulses the lens and iris. Crimson keeps distinct listening, thinking, speaking, confirmation, error and success signals. Camera frames, video, research images and 3D content are not recolored.

## Updating and Testing

This feature needs a full desktop rebuild, not the older visual-only updater, because it includes Python conversation changes and new web assets:

```powershell
.\scripts\build_ultron_desktop.ps1
```

The build preserves the separate AppData user configuration. Close the running executable before replacing its installed bundle; keep a backup of that bundle. Do not replace your user configuration with another person's keys.

```powershell
python -m unittest discover -s tests
node scripts/crimson_smoke.cjs
node scripts/core_visual_smoke.cjs
node scripts/agent_ui_smoke.cjs
```

The browser checks use Playwright and pngjs, and save desktop/mobile screenshots in `.ultron`. Backend tests mock Groq responses; they verify prompt selection and request isolation, not live voice quality or a guaranteed model response.

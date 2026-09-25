import * as THREE from "./vendor/three.module.min.js";
import { createArmillaryCore } from "./ultron-core.js";
import { createCoreActivityController } from "./core-activity.js";
import { createCrimsonMode } from "./crimson-mode.js";
import { createHandGestureController } from "./hand-gestures.js";
import { createDesktopGestureInterpreter } from "./hand-mouse.js";
import { createPhotoReliefModeler } from "./photo-modeler.js";
import { createObjectScanner } from "./object-scanner.js";
import { createAgentWorkspace } from "./agent-workspace.js";

const canvas = document.getElementById("ultron-scene");
const subtitlePanel = document.getElementById("subtitlePanel");
const subtitleText = document.getElementById("subtitleText");
const subtitleToggle = document.getElementById("subtitleToggle");
const commandInput = document.getElementById("commandInput");
const sendButton = document.getElementById("sendButton");
const detailToggle = document.getElementById("detailToggle");
const statusLabel = document.getElementById("statusLabel");
const voiceBadge = document.getElementById("voiceBadge");
const micToggle = document.getElementById("micToggle");
const coreMicButton = document.getElementById("coreMicButton");
const backendCaptureButton = document.getElementById("backendCaptureButton");
const alwaysListeningToggle = document.getElementById("alwaysListeningToggle");
const pushToTalkToggle = document.getElementById("pushToTalkToggle");
const muteToggle = document.getElementById("muteToggle");
const stopSpeakingButton = document.getElementById("stopSpeakingButton");
const confirmVoiceButton = document.getElementById("confirmVoiceButton");
const mockVoiceButton = document.getElementById("mockVoiceButton");
const sttProviderLabel = document.getElementById("sttProviderLabel");
const sttProviderDetail = document.getElementById("sttProviderDetail");
const captureProviderLabel = document.getElementById("captureProviderLabel");
const captureProviderDetail = document.getElementById("captureProviderDetail");
const ttsProviderLabel = document.getElementById("ttsProviderLabel");
const ttsProviderDetail = document.getElementById("ttsProviderDetail");
const refreshProvidersButton = document.getElementById("refreshProvidersButton");
const testProvidersButton = document.getElementById("testProvidersButton");
const calibrateVoiceButton = document.getElementById("calibrateVoiceButton");
const micStatusLabel = document.getElementById("micStatusLabel");
const micPrivacyDetail = document.getElementById("micPrivacyDetail");
const wakeStateLabel = document.getElementById("wakeStateLabel");
const wakeDetail = document.getElementById("wakeDetail");
const vadStateLabel = document.getElementById("vadStateLabel");
const vadDetail = document.getElementById("vadDetail");
const lastTranscriptLabel = document.getElementById("lastTranscriptLabel");
const confidenceDetail = document.getElementById("confidenceDetail");
const audioStateLabel = document.getElementById("audioStateLabel");
const audioDetail = document.getElementById("audioDetail");
const voiceHistory = document.getElementById("voiceHistory");
const skillsList = document.getElementById("skillsList");
const memoryToggle = document.getElementById("memoryToggle");
const memoryForgetInput = document.getElementById("memoryForgetInput");
const memoryForgetButton = document.getElementById("memoryForgetButton");
const knowledgeSearchInput = document.getElementById("knowledgeSearchInput");
const knowledgeSearchButton = document.getElementById("knowledgeSearchButton");
const knowledgeList = document.getElementById("knowledgeList");
const recentTasksList = document.getElementById("recentTasksList");
const stateButtons = [...document.querySelectorAll("[data-state]")];
const drawerTabs = [...document.querySelectorAll("[data-drawer-tab]")];
const drawerPanels = [...document.querySelectorAll("[data-drawer-panel]")];
const confirmationModal = document.getElementById("confirmationModal");
const confirmationTitle = document.getElementById("confirmationTitle");
const confirmationMessage = document.getElementById("confirmationMessage");
const confirmationTool = document.getElementById("confirmationTool");
const confirmationPermission = document.getElementById("confirmationPermission");
const approveConfirmationButton = document.getElementById("approveConfirmationButton");
const cancelConfirmationButton = document.getElementById("cancelConfirmationButton");
const gestureToggle = document.getElementById("gestureToggle");
const gestureCursor = document.getElementById("gestureCursor");
const gestureSystemToggle = document.getElementById("gestureSystemToggle");
const gesturePauseButton = document.getElementById("gesturePauseButton");
const gestureModeButtons = [...document.querySelectorAll("[data-gesture-mode]")];
const desktopGestureModeButton = document.getElementById("desktopGestureModeButton");
const gestureSensitivitySlider = document.getElementById("gestureSensitivitySlider");
const gestureSensitivityValue = document.getElementById("gestureSensitivityValue");
const handControlModeLabel = document.getElementById("handControlModeLabel");
const handControlStatusLabel = document.getElementById("handControlStatusLabel");
const handControlStatusDetail = document.getElementById("handControlStatusDetail");
const handGuideModal = document.getElementById("handGuideModal");
const handGuideCloseButton = document.getElementById("handGuideCloseButton");
const handGuideToggleButton = document.getElementById("handGuideToggleButton");
const handGuideStatusLabel = document.getElementById("handGuideStatusLabel");
const handGuideStatusDetail = document.getElementById("handGuideStatusDetail");
const handGuideLiveStatus = document.querySelector(".hand-guide-live-status");
const handGuideTriggers = [...document.querySelectorAll("[data-open-hand-guide]")];
const cameraWindow = document.getElementById("cameraWindow");
const cameraFeed = document.getElementById("cameraFeed");
const gestureOverlay = document.getElementById("gestureOverlay");
const objectOverlay = document.getElementById("objectOverlay");
const cameraSnapshot = document.getElementById("cameraSnapshot");
const cameraCanvas = document.getElementById("cameraCanvas");
const cameraCaptureButton = document.getElementById("cameraCaptureButton");
const cameraStatus = document.getElementById("cameraStatus");
const cameraPermissionMessage = document.getElementById("cameraPermissionMessage");
const youtubeWindow = document.getElementById("youtubeWindow");
let youtubePlayerHost = document.getElementById("youtubePlayerHost");
const youtubeWindowTitle = document.getElementById("youtubeWindowTitle");
const youtubePlayerMessage = document.getElementById("youtubePlayerMessage");
const youtubePlayerStatus = document.getElementById("youtubePlayerStatus");
const youtubeBackButton = document.getElementById("youtubeBackButton");
const youtubePlayButton = document.getElementById("youtubePlayButton");
const youtubeForwardButton = document.getElementById("youtubeForwardButton");
const objectScanProgress = document.getElementById("objectScanProgress");
const objectScanLabel = document.getElementById("objectScanLabel");
const objectScanPercent = document.getElementById("objectScanPercent");
const objectScanMeter = document.getElementById("objectScanMeter");
const objectScanViews = document.getElementById("objectScanViews");
const objectScanCancelButton = document.getElementById("objectScanCancelButton");
const researchWindow = document.getElementById("researchWindow");
const researchForm = document.getElementById("researchForm");
const researchQueryInput = document.getElementById("researchQueryInput");
const researchSubmitButton = document.getElementById("researchSubmitButton");
const researchStatus = document.getElementById("researchStatus");
const researchSourceCount = document.getElementById("researchSourceCount");
const researchSummary = document.getElementById("researchSummary");
const researchSources = document.getElementById("researchSources");
const modelWindow = document.getElementById("modelWindow");
const modelCanvas = document.getElementById("modelCanvas");
const modelStatus = document.getElementById("modelStatus");
const modelStats = document.getElementById("modelStats");
const modelScanButton = document.getElementById("modelScanButton");
const model360Button = document.getElementById("model360Button");
const modelScaleSlider = document.getElementById("modelScaleSlider");
const modelVisibilityButton = document.getElementById("modelVisibilityButton");
const modelWireframeButton = document.getElementById("modelWireframeButton");
const modelResetButton = document.getElementById("modelResetButton");
const modelExportButton = document.getElementById("modelExportButton");
const runtimeShellLabel = document.getElementById("runtimeShellLabel");
const startupSequence = document.getElementById("startupSequence");
const startupStatusText = document.getElementById("startupStatusText");
const startupProgressBar = document.getElementById("startupProgressBar");
const startupProgressValue = document.getElementById("startupProgressValue");
const startupModules = [...document.querySelectorAll("[data-startup-module]")];
const desktopShell = new URLSearchParams(window.location.search).get("shell") === "desktop";

document.documentElement.dataset.shell = desktopShell ? "desktop" : "browser";
if (runtimeShellLabel) runtimeShellLabel.textContent = desktopShell ? "Desktop" : "Local";

const scene = new THREE.Scene();
const camera = new THREE.PerspectiveCamera(44, window.innerWidth / window.innerHeight, 0.1, 100);
camera.position.set(0, 0.08, 4.35);

const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
renderer.setSize(window.innerWidth, window.innerHeight);
renderer.setClearColor(0x000000, 0);

const clock = new THREE.Clock();
const stateTargets = {
  inactive: { scale: 1.0, ring: 0.18, line: 0.36, particle: 0.06, glow: 0.86 },
  idle: { scale: 1.0, ring: 0.25, line: 0.45, particle: 0.08, glow: 1.0 },
  waiting_for_wake_word: { scale: 0.94, ring: 0.28, line: 0.28, particle: 0.035, glow: 0.72 },
  listening: { scale: 0.88, ring: 0.36, line: 0.32, particle: 0.04, glow: 0.78 },
  transcribing: { scale: 0.98, ring: 0.68, line: 0.48, particle: 0.12, glow: 1.0 },
  thinking: { scale: 1.0, ring: 1.0, line: 0.62, particle: 0.14, glow: 1.12 },
  speaking: { scale: 1.1, ring: 0.55, line: 1.0, particle: 0.22, glow: 1.36 },
};

let visualState = "idle";
let subtitlesEnabled = true;
let micEnabled = false;
let pushToTalk = false;
let voiceMuted = false;
let returnTimer = null;
let recognition = null;
let recognitionActive = false;
let providerStatus = null;
let alwaysListening = false;
let pendingConfirmation = null;
let memoryEnabled = true;
let detailsCollapsed = window.localStorage.getItem("ultronDetailsCollapsed") !== "false";
let activeDrawerTab = window.localStorage.getItem("ultronDrawerTab") || "activity";
let backendWakePolling = false;
let backendWakeTimer = null;
let backendWakeBusy = false;
let backendCommandCaptureActive = false;
let wakeProvider = null;
let cameraStream = null;
let cameraAutoCaptureTimer = null;
let latestCameraFrame = "";
let gestureActive = false;
let gestureGrab = null;
let gestureLastPoint = null;
let gestureMode = window.localStorage.getItem("ultronGestureMode") || (desktopShell ? "desktop" : "workspace");
let gestureSensitivity = Number(window.localStorage.getItem("ultronGestureSensitivity") || 1);
let desktopBridgeReady = false;
let desktopHandAvailable = false;
let desktopHandStatus = null;
let nativeHandQueue = [];
let nativeHandDispatching = false;
let handStatusSnapshot = { state: "off", detail: "Choose a mode, then start hand control", pose: "none", paused: false };
let lastHandStatusRenderAt = 0;
let modelWireframe = false;
let modelVisible = true;
let objectScanSession = 0;
let objectScanActive = false;
let windowStack = 30;
let youtubeIframeApiPromise = null;
let youtubePlayer = null;
let youtubePlayerReady = false;
let youtubePlayerPlaying = false;
let youtubeRequestedVideoId = "";
let youtubeCandidateVideoIds = [];
let youtubeCandidateIndex = 0;
let youtubePlayerGeneration = 0;
let currentSpeechResolve = null;
let currentSpeechAudio = null;
let currentSpeechUrl = null;
let browserVoiceCache = [];
let browserVoicePromise = null;
let bargeInMonitor = null;
let bargeInHandling = false;
let bargeInEnabled = true;
let startupBriefingStarted = false;
let openingSequencePromise = Promise.resolve();
let openingSequenceSkip = null;

const photoModeler = createPhotoReliefModeler({
  canvas: modelCanvas,
  onStatus: (_status, detail) => {
    if (modelStatus) modelStatus.textContent = detail;
  },
});
const objectScanner = createObjectScanner({
  video: cameraFeed,
  overlay: objectOverlay,
  onStatus: (_status, detail) => {
    if (objectScanActive && cameraStatus) cameraStatus.textContent = detail;
  },
});
const handGestureController = createHandGestureController({
  onFrame: handleGestureFrame,
  onSwipe: handleGestureSwipe,
  onStatus: handleGestureStatus,
  onActiveChange: (active) => {
    gestureActive = Boolean(active);
    updateHandControlUi();
  },
});
const desktopGestureInterpreter = createDesktopGestureInterpreter({
  sensitivity: gestureSensitivity,
  onEvent: enqueueNativeHandEvent,
  onStatus: handleDesktopGestureStatus,
  onAction: handleDesktopGestureAction,
  onPauseChange: () => updateHandControlUi(),
});

const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

const root = new THREE.Group();
root.position.y = 0.32;
scene.add(root);

const sphereUniforms = {
  time: { value: 0 },
  intensity: { value: 0.7 },
};

const sphere = new THREE.Mesh(
  new THREE.IcosahedronGeometry(1.03, 8),
  new THREE.ShaderMaterial({
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    uniforms: sphereUniforms,
    vertexShader: `
      varying vec3 vNormal;
      varying vec3 vPosition;
      void main() {
        vNormal = normalize(normalMatrix * normal);
        vPosition = position;
        gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
      }
    `,
    fragmentShader: `
      uniform float time;
      uniform float intensity;
      varying vec3 vNormal;
      varying vec3 vPosition;
      void main() {
        float rim = pow(1.0 - abs(dot(vNormal, vec3(0.0, 0.0, 1.0))), 2.45);
        float plasma = sin(vPosition.x * 9.0 + time * 1.8) * sin(vPosition.y * 7.0 - time * 1.4);
        float veins = smoothstep(0.72, 0.98, abs(plasma));
        vec3 deep = vec3(0.0, 0.11, 0.045);
        vec3 neon = vec3(0.0, 1.0, 0.38);
        vec3 lime = vec3(0.58, 1.0, 0.18);
        vec3 color = mix(deep, neon, rim * 1.4 + veins * 0.45);
        color = mix(color, lime, veins * 0.35);
        float alpha = 0.12 + rim * 0.58 + veins * 0.14;
        gl_FragColor = vec4(color * intensity, alpha);
      }
    `,
  })
);
root.add(sphere);

const glow = new THREE.Sprite(
  new THREE.SpriteMaterial({
    map: makeGlowTexture(),
    transparent: true,
    blending: THREE.AdditiveBlending,
    opacity: 0.64,
    depthWrite: false,
  })
);
glow.scale.set(3.15, 3.15, 1);
root.add(glow);

const plasmaLines = new THREE.Group();
for (let i = 0; i < 24; i += 1) {
  plasmaLines.add(makeArc(i));
}
root.add(plasmaLines);

const ringGroup = new THREE.Group();
for (let i = 0; i < 5; i += 1) {
  const arc = i % 2 === 0 ? Math.PI * 2 : Math.PI * 1.42;
  const ring = new THREE.Mesh(
    new THREE.TorusGeometry(1.18 + i * 0.045, 0.006 + i * 0.001, 10, 180, arc),
    new THREE.MeshBasicMaterial({
      color: i % 2 === 0 ? 0x00ff66 : 0xa6ff3f,
      transparent: true,
      opacity: 0.26,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
  ring.rotation.set(Math.PI / 2 + i * 0.22, i * 0.46, i * 0.31);
  ringGroup.add(ring);
}
root.add(ringGroup);

const particles = makeParticles();
scene.add(particles);

const fill = new THREE.PointLight(0x00ff66, 1.4, 7);
fill.position.set(1.8, 1.2, 2.4);
scene.add(fill);

root.visible = false;
particles.visible = false;
fill.intensity = 0;
const armillaryCore = createArmillaryCore({ scene, camera, renderer });
const coreActivity = createCoreActivityController(armillaryCore);
const crimsonMode = createCrimsonMode(armillaryCore, {
  eligible: () => document.body.classList.contains("app-ready")
    && ["idle", "waiting_for_wake_word"].includes(visualState)
    && ["idle", "waiting_for_wake_word"].includes(canvas.dataset.coreActivity)
    && !pendingConfirmation,
});
window.addEventListener("beforeunload", () => crimsonMode.dispose());

const agentWorkspace = createAgentWorkspace({
  onOpen: () => { setDetailsCollapsed(false); selectDrawerTab("agent"); },
  activity: coreActivity,
});
window.lucide?.createIcons({ attrs: { "aria-hidden": "true" } });
setVisualState("idle", { sync: false });
setDetailsCollapsed(detailsCollapsed);
selectDrawerTab(activeDrawerTab);
setupWorkspaceWindows();
initializeHandControlUi();
openingSequencePromise = runOpeningSequence();
animate();
loadStatus();
loadProviders();
warmBrowserVoiceCache();
setupSpeechRecognition();

stateButtons.forEach((button) => {
  button.addEventListener("click", () => setVisualState(button.dataset.state));
});

drawerTabs.forEach((button) => {
  button.addEventListener("click", () => selectDrawerTab(button.dataset.drawerTab));
});

subtitleToggle.addEventListener("click", async () => {
  subtitlesEnabled = !subtitlesEnabled;
  updateSubtitles();
  try {
    await fetch("/api/subtitles/toggle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled: subtitlesEnabled }),
    });
  } catch {
    // The local visual toggle should keep working even if the API is not ready.
  }
});

detailToggle.addEventListener("click", () => setDetailsCollapsed(!detailsCollapsed));

coreMicButton.addEventListener("click", () => {
  if (micEnabled || recognitionActive || alwaysListening) {
    if (alwaysListening) {
      stopAlwaysListening();
    } else {
      stopVoiceInput();
    }
    return;
  }
  if (providerStatus?.active?.capture === "sounddevice") {
    captureBackendVoice();
    return;
  }
  startVoiceInput();
});

micToggle.addEventListener("click", () => {
  if (micEnabled) {
    stopVoiceInput();
  } else {
    startVoiceInput();
  }
});
backendCaptureButton.addEventListener("click", captureBackendVoice);

pushToTalkToggle.addEventListener("click", () => {
  pushToTalk = !pushToTalk;
  setButtonLabel(pushToTalkToggle, pushToTalk ? "Push-to-talk" : "Continuous");
  pushToTalkToggle.setAttribute("aria-pressed", String(pushToTalk));
  micPrivacyDetail.textContent = pushToTalk ? "One command per mic start" : "Continuous listening until stopped";
});

alwaysListeningToggle.addEventListener("click", () => {
  if (alwaysListening) {
    stopAlwaysListening();
  } else {
    startAlwaysListening();
  }
});

muteToggle.addEventListener("click", async () => {
  voiceMuted = !voiceMuted;
  setButtonLabel(muteToggle, voiceMuted ? "Muted" : "Mute Off");
  muteToggle.setAttribute("aria-pressed", String(voiceMuted));
  await postJson("/api/speak", { muted: voiceMuted, text: "" });
  if (voiceMuted) stopBrowserSpeech();
});

stopSpeakingButton.addEventListener("click", async () => {
  stopBrowserSpeech();
  await postJson("/api/speak", { action: "stop" });
  setVisualState(micEnabled ? "listening" : "idle");
});

confirmVoiceButton.addEventListener("click", () => handleVoiceTranscript("yes confirm"));
mockVoiceButton.addEventListener("click", () =>
  handleVoiceTranscript("ULTRON, create a note called demo and write that voice mode is working.")
);
refreshProvidersButton.addEventListener("click", loadProviders);
testProvidersButton.addEventListener("click", testVoiceProviders);
calibrateVoiceButton.addEventListener("click", calibrateVoice);
approveConfirmationButton.addEventListener("click", approvePendingConfirmation);
cancelConfirmationButton.addEventListener("click", cancelPendingConfirmation);
knowledgeSearchButton.addEventListener("click", searchKnowledge);
knowledgeSearchInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") searchKnowledge();
});
memoryToggle.addEventListener("click", toggleMemory);
memoryForgetButton.addEventListener("click", forgetMemory);
memoryForgetInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") forgetMemory();
});

sendButton.addEventListener("click", sendCommand);
commandInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter") {
    sendCommand();
  }
});

window.addEventListener("resize", () => {
  camera.aspect = window.innerWidth / window.innerHeight;
  camera.updateProjectionMatrix();
  renderer.setSize(window.innerWidth, window.innerHeight);
  updateCoreLayout();
});

window.addEventListener("keydown", (event) => {
  if (event.key !== "Escape") return;
  if (openingSequenceSkip) openingSequenceSkip();
  if (handGuideModal && !handGuideModal.hidden) closeHandGuide();
});

async function sendCommand(options = {}) {
  const command = String(options.command ?? commandInput.value).trim();
  const confirmed = Boolean(options.confirmed);
  if (!command) return;
  if (!confirmed) commandInput.value = "";
  setSubtitle(confirmed ? `Confirmed: ${command}` : `Processing: ${command}`);
  setVisualState("thinking");
  try {
    const payload = await postJson("/api/command", { command, mode: "do", confirmed });
    const spoken = payload.subtitle || buildTaskSubtitle(payload.task) || payload.message || "Command processed.";
    setSubtitle(spoken);
    await handleUiDirective(payload.ui_directive);
    renderHistory(payload.conversation_history || []);
    renderRecentTasks(payload.recent_tasks || []);
    if (payload.memory_enabled !== undefined) memoryEnabled = Boolean(payload.memory_enabled);
    await loadMemoryKnowledge();
    if (taskNeedsConfirmation(payload.task)) {
      showConfirmation(payload.task, { command, source: "typed" });
      setVisualState("listening");
      return;
    }
    clearPendingConfirmation();
    setVisualState("speaking");
    await speakText(spoken);
    scheduleListeningReturn();
  } catch {
    setSubtitle("Local interface could not reach the ULTRON runtime.");
    setVisualState("idle");
  }
}

function runOpeningSequence() {
  const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const duration = reducedMotion ? 80 : 3400;
  const phases = [
    { threshold: 0, label: "Core handshake" },
    { threshold: 0.2, label: "Neural lattice assembly" },
    { threshold: 0.42, label: "Voice and memory links" },
    { threshold: 0.64, label: "Vision and research links" },
    { threshold: 0.84, label: "Action runtime verification" },
  ];

  armillaryCore.startBoot();
  if (!startupSequence) {
    armillaryCore.finishBoot();
    document.body.classList.remove("app-booting");
    document.body.classList.add("app-ready");
    return Promise.resolve();
  }

  startupSequence.hidden = false;
  startupSequence.classList.remove("is-exiting");
  startupSequence.setAttribute("aria-hidden", "false");

  return new Promise((resolve) => {
    let frame = null;
    let complete = false;
    const startedAt = performance.now();

    const updateReadout = (progress) => {
      const percent = Math.min(100, Math.round(progress * 100));
      startupProgressValue.textContent = String(percent).padStart(2, "0");
      startupProgressBar.style.transform = `scaleX(${progress.toFixed(4)})`;
      const phase = [...phases].reverse().find((item) => progress >= item.threshold) || phases[0];
      startupStatusText.textContent = phase.label;
      startupModules.forEach((item, index) => {
        const linkingAt = 0.08 + index * 0.115;
        const onlineAt = linkingAt + 0.11;
        const linking = progress >= linkingAt;
        const online = progress >= onlineAt;
        item.classList.toggle("is-linking", linking && !online);
        item.classList.toggle("is-online", online);
        const status = item.querySelector("[data-startup-module-status]");
        if (status) status.textContent = online ? "READY" : linking ? "LINK" : "WAIT";
      });
    };

    const finish = () => {
      if (complete) return;
      complete = true;
      if (frame) window.cancelAnimationFrame(frame);
      updateReadout(1);
      startupStatusText.textContent = "All systems ready";
      armillaryCore.setBootProgress(1);
      armillaryCore.finishBoot();
      document.body.classList.remove("app-booting");
      document.body.classList.add("app-revealing");
      startupSequence.classList.add("is-exiting");
      startupSequence.setAttribute("aria-hidden", "true");
      const exitDelay = reducedMotion ? 20 : 720;
      window.setTimeout(() => {
        startupSequence.hidden = true;
        document.body.classList.remove("app-revealing");
        document.body.classList.add("app-ready");
        openingSequenceSkip = null;
        resolve();
      }, exitDelay);
    };

    const tick = (now) => {
      const progress = Math.min(1, Math.max(0, (now - startedAt) / duration));
      const eased = 1 - Math.pow(1 - progress, 3);
      armillaryCore.setBootProgress(eased);
      updateReadout(progress);
      if (progress >= 1) {
        finish();
        return;
      }
      frame = window.requestAnimationFrame(tick);
    };

    openingSequenceSkip = finish;
    updateReadout(0);
    frame = window.requestAnimationFrame(tick);
  });
}

async function loadStatus() {
  try {
    const payload = await fetchJson("/api/status");
    subtitlesEnabled = Boolean(payload.subtitles_enabled);
    setSubtitle(payload.last_subtitle || "ULTRON 2.7 online.");
    setVisualState(payload.visual_state || "idle", { sync: false });
    updateSubtitles();
    const voicePayload = await fetchJson("/api/voice/status");
    applyVoiceStatus(voicePayload.voice);
    applyWakeStatus(voicePayload.wake);
    applyVoiceDiagnostics(voicePayload.voice_diagnostics || payload.voice_diagnostics);
    renderHistory(voicePayload.history || []);
    renderRecentTasks(payload.recent_tasks || []);
    memoryEnabled = payload.memory_enabled !== undefined ? Boolean(payload.memory_enabled) : memoryEnabled;
    renderKnowledgePanel({ sources: payload.knowledge_sources || [], memoryEnabled });
    await loadProviders();
    await loadWakeStatus();
    await loadSkills();
    await loadMemoryKnowledge();
    await openingSequencePromise;
    window.setTimeout(loadStartupBriefing, 220);
  } catch {
    setSubtitle("ULTRON visual shell loaded. Runtime API pending.");
  }
}

function setupWorkspaceWindows() {
  [cameraWindow, youtubeWindow, researchWindow, modelWindow].filter(Boolean).forEach((panel) => {
    const handle = panel.querySelector("[data-window-drag-handle]");
    panel.addEventListener("pointerdown", () => bringWindowToFront(panel));
    handle?.addEventListener("pointerdown", (event) => beginWindowDrag(event, panel));
    handle?.addEventListener("dblclick", (event) => {
      if (event.target.closest("button")) return;
      toggleWindowMaximize(panel);
    });
    panel.querySelectorAll("[data-window-action]").forEach((button) => {
      button.addEventListener("click", () => handleWindowAction(panel, button.dataset.windowAction));
    });
  });
  cameraCaptureButton?.addEventListener("click", captureCameraFrame);
  youtubeBackButton?.addEventListener("click", () => seekYouTubeVideo(-10));
  youtubePlayButton?.addEventListener("click", toggleYouTubePlayback);
  youtubeForwardButton?.addEventListener("click", () => seekYouTubeVideo(10));
  gestureToggle?.addEventListener("click", () => setGestureControls(!gestureActive));
  gestureSystemToggle?.addEventListener("click", () => setGestureControls(!gestureActive));
  handGuideToggleButton?.addEventListener("click", () => setGestureControls(!gestureActive));
  gesturePauseButton?.addEventListener("click", () => desktopGestureInterpreter.setPaused(!desktopGestureInterpreter.paused));
  gestureModeButtons.forEach((button) => {
    button.addEventListener("click", () => setGestureMode(button.dataset.gestureMode));
  });
  handGuideTriggers.forEach((button) => button.addEventListener("click", openHandGuide));
  handGuideCloseButton?.addEventListener("click", closeHandGuide);
  handGuideModal?.addEventListener("click", (event) => {
    if (event.target === handGuideModal) closeHandGuide();
  });
  gestureSensitivitySlider?.addEventListener("input", () => {
    gestureSensitivity = desktopGestureInterpreter.setSensitivity(gestureSensitivitySlider.value);
    window.localStorage.setItem("ultronGestureSensitivity", String(gestureSensitivity));
    updateHandControlUi();
  });
  modelScanButton?.addEventListener("click", () => buildModelFromCamera("", true));
  model360Button?.addEventListener("click", () => start360ObjectScan("", 12));
  modelScaleSlider?.addEventListener("input", () => {
    const scale = photoModeler.setModelScale(modelScaleSlider.value);
    modelStatus.textContent = `Model size ${Math.round(scale * 100)}%`;
  });
  modelVisibilityButton?.addEventListener("click", () => setModelVisibility(!modelVisible));
  modelWireframeButton?.addEventListener("click", () => {
    modelWireframe = !modelWireframe;
    modelWireframeButton.setAttribute("aria-pressed", String(modelWireframe));
    photoModeler.setWireframe(modelWireframe);
  });
  modelResetButton?.addEventListener("click", resetModelView);
  modelExportButton?.addEventListener("click", exportCameraModel);
  objectScanCancelButton?.addEventListener("click", () => cancelObjectScan("360 scan cancelled"));
  researchForm?.addEventListener("submit", (event) => {
    event.preventDefault();
    runResearch(researchQueryInput.value);
  });
  window.addEventListener("beforeunload", () => {
    cancelObjectScan();
    objectScanner.dispose();
    desktopGestureInterpreter.stop();
    void setNativeHandControl(false);
    handGestureController.dispose();
    photoModeler.dispose();
    stopCameraStream();
    destroyYouTubePlayer();
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden) pauseYouTubePlayer("Playback paused while ULTRON is hidden.");
  });
}

function openWorkspaceWindow(panel) {
  if (!panel) return;
  panel.hidden = false;
  panel.classList.remove("is-minimized");
  bringWindowToFront(panel);
}

function bringWindowToFront(panel) {
  windowStack += 1;
  panel.style.zIndex = String(windowStack);
}

function handleWindowAction(panel, action) {
  if (action === "close") {
    panel.hidden = true;
    panel.classList.remove("is-maximized", "is-minimized");
    if (panel === cameraWindow) {
      cancelObjectScan("360 scan cancelled");
      if (gestureActive) setGestureControls(false);
      stopCameraStream();
    }
    if (panel === youtubeWindow) destroyYouTubePlayer();
    return;
  }
  if (action === "minimize") {
    panel.classList.remove("is-maximized");
    if (panel === youtubeWindow && !panel.classList.contains("is-minimized")) {
      pauseYouTubePlayer("Playback paused while the mini-player is minimized.");
    }
    panel.classList.toggle("is-minimized");
    return;
  }
  if (action === "maximize") toggleWindowMaximize(panel);
}

function toggleWindowMaximize(panel) {
  panel.classList.remove("is-minimized");
  panel.classList.toggle("is-maximized");
  bringWindowToFront(panel);
}

function beginWindowDrag(event, panel) {
  if (event.button !== 0 || event.target.closest("button") || panel.classList.contains("is-maximized") || window.innerWidth <= 980) return;
  const rect = panel.getBoundingClientRect();
  const offsetX = event.clientX - rect.left;
  const offsetY = event.clientY - rect.top;
  bringWindowToFront(panel);
  event.preventDefault();

  const move = (pointerEvent) => {
    const maxLeft = Math.max(8, window.innerWidth - panel.offsetWidth - 8);
    const maxTop = Math.max(8, window.innerHeight - 56);
    panel.style.left = `${Math.max(8, Math.min(maxLeft, pointerEvent.clientX - offsetX))}px`;
    panel.style.top = `${Math.max(8, Math.min(maxTop, pointerEvent.clientY - offsetY))}px`;
    panel.style.right = "auto";
    panel.style.bottom = "auto";
  };
  const end = () => {
    window.removeEventListener("pointermove", move);
    window.removeEventListener("pointerup", end);
  };
  window.addEventListener("pointermove", move);
  window.addEventListener("pointerup", end, { once: true });
}

async function handleUiDirective(directive) {
  if (!directive || typeof directive !== "object") return;
  if (directive.kind === "agent") {
    await agentWorkspace.open(directive.id);
    return;
  }
  if (directive.kind === "youtube_player") {
    await openYouTubePlayer(directive);
    return;
  }
  if (directive.kind === "camera") {
    openCameraWindow(Boolean(directive.auto_capture));
    return;
  }
  if (directive.kind === "research") {
    renderResearchDirective(directive);
    return;
  }
  if (directive.kind === "gestures") {
    if (directive.action === "guide") {
      openHandGuide();
      return;
    }
    if (directive.action === "pause" || directive.action === "resume") {
      if (gestureMode !== "desktop" || !gestureActive) {
        setSubtitle("Desktop hand control is not active, sir.");
        return;
      }
      desktopGestureInterpreter.setPaused(directive.action === "pause");
      return;
    }
    if (directive.mode) await setGestureMode(directive.mode, { announce: false });
    await setGestureControls(directive.action !== "stop");
    return;
  }
  if (directive.kind === "modeler") {
    const action = String(directive.action || "open");
    if (action === "generate") {
      await buildGeneratedModel(directive.description);
      return;
    }
    if (action === "scan_object") {
      await buildModelFromCamera(directive.target, directive.fallback_360 !== false);
      return;
    }
    if (action === "scan_360") {
      void start360ObjectScan(directive.target, directive.required_views);
      return;
    }
    if (action === "scale_up" || action === "scale_down") {
      scaleModel(action === "scale_up" ? 1.25 : 0.8);
      return;
    }
    if (action === "hide" || action === "show") {
      setModelVisibility(action === "show");
      return;
    }
    if (action === "clear") {
      photoModeler.clearModel();
      modelStatus.textContent = "Model cleared";
      modelStats.textContent = "No mesh";
      return;
    }
    if (action === "reset") {
      resetModelView();
      return;
    }
    openWorkspaceWindow(modelWindow);
    window.requestAnimationFrame(() => photoModeler.resize());
  }
}

const YOUTUBE_VIDEO_ID_PATTERN = /^[A-Za-z0-9_-]{11}$/;

async function openYouTubePlayer(directive) {
  const videoId = String(directive?.video_id || "");
  if (!YOUTUBE_VIDEO_ID_PATTERN.test(videoId)) {
    if (youtubePlayerStatus) youtubePlayerStatus.textContent = "Rejected an invalid YouTube video identifier.";
    return false;
  }

  const generation = youtubePlayerGeneration;
  const candidateVideoIds = [videoId, ...(Array.isArray(directive?.video_ids) ? directive.video_ids : [])]
    .map((candidate) => String(candidate || ""))
    .filter((candidate, index, values) => YOUTUBE_VIDEO_ID_PATTERN.test(candidate) && values.indexOf(candidate) === index)
    .slice(0, 6);
  youtubeCandidateVideoIds = candidateVideoIds;
  youtubeCandidateIndex = 0;
  youtubeRequestedVideoId = candidateVideoIds[0];
  youtubeWindow.dataset.videoId = youtubeRequestedVideoId;
  youtubeWindowTitle.textContent = String(directive?.query || "YouTube video").slice(0, 240);
  youtubePlayerMessage.hidden = false;
  youtubePlayerMessage.textContent = "Preparing the YouTube mini-player.";
  youtubePlayerStatus.textContent = "Loading YouTube video.";
  setYouTubeControlsEnabled(false);
  updateYouTubePlayButton(false);
  openWorkspaceWindow(youtubeWindow);

  try {
    const api = await loadYouTubeIframeApi();
    if (generation !== youtubePlayerGeneration || youtubeWindow.hidden) return false;
    if (!youtubePlayer) {
      createYouTubePlayer(api, youtubeRequestedVideoId, generation);
      return true;
    }
    if (youtubePlayerReady) {
      youtubePlayer.cueVideoById(youtubeRequestedVideoId);
      youtubePlayerMessage.hidden = true;
      youtubePlayerStatus.textContent = "Video ready. Press play.";
      setYouTubeControlsEnabled(true);
      updateYouTubePlayButton(false);
    }
    return true;
  } catch (error) {
    if (generation !== youtubePlayerGeneration) return false;
    youtubePlayerMessage.hidden = false;
    youtubePlayerMessage.textContent = "YouTube could not load inside ULTRON. Check the connection and try again.";
    youtubePlayerStatus.textContent = String(error?.message || "YouTube player unavailable.");
    setYouTubeControlsEnabled(false);
    return false;
  }
}

function loadYouTubeIframeApi() {
  if (window.YT?.Player) return Promise.resolve(window.YT);
  if (youtubeIframeApiPromise) return youtubeIframeApiPromise;

  youtubeIframeApiPromise = new Promise((resolve, reject) => {
    let settled = false;
    let timeout = null;
    let script = document.querySelector('script[data-ultron-youtube-api]');
    if (script?.dataset.ultronYoutubeApiState === "failed") {
      script.remove();
      script = null;
    }
    const previousReady = window.onYouTubeIframeAPIReady;
    const onScriptError = () => finish(new Error("YouTube player API could not be reached."));
    const readyHandler = () => {
      try {
        if (typeof previousReady === "function") previousReady();
      } catch {
        // Another optional API-ready listener must not block this player.
      }
      finish();
    };
    const finish = (error = null) => {
      if (settled) return;
      settled = true;
      if (timeout) window.clearTimeout(timeout);
      script?.removeEventListener("error", onScriptError);
      if (window.onYouTubeIframeAPIReady === readyHandler) {
        window.onYouTubeIframeAPIReady = previousReady;
      }
      if (error) {
        if (script) script.dataset.ultronYoutubeApiState = "failed";
        script?.remove();
        reject(error);
      } else if (window.YT?.Player) {
        if (script) script.dataset.ultronYoutubeApiState = "ready";
        resolve(window.YT);
      } else {
        if (script) script.dataset.ultronYoutubeApiState = "failed";
        script?.remove();
        reject(new Error("YouTube player API was unavailable."));
      }
    };

    window.onYouTubeIframeAPIReady = readyHandler;
    timeout = window.setTimeout(() => finish(new Error("YouTube player API timed out.")), 12000);
    if (!script) {
      script = document.createElement("script");
      script.src = "https://www.youtube.com/iframe_api";
      script.async = true;
      script.dataset.ultronYoutubeApi = "true";
    }
    script.dataset.ultronYoutubeApiState = "loading";
    script.addEventListener("error", onScriptError, { once: true });
    if (!script.isConnected) document.head.append(script);
  }).catch((error) => {
    youtubeIframeApiPromise = null;
    throw error;
  });
  return youtubeIframeApiPromise;
}

function createYouTubePlayer(api, videoId, generation) {
  try {
    const embedUrl = new URL(`https://www.youtube.com/embed/${videoId}`);
    embedUrl.search = new URLSearchParams({
      autoplay: "0",
      controls: "1",
      enablejsapi: "1",
      iv_load_policy: "3",
      origin: window.location.origin,
      playsinline: "1",
      rel: "0",
    }).toString();
    const iframe = document.createElement("iframe");
    iframe.id = "youtubePlayerFrame";
    iframe.src = embedUrl.href;
    iframe.title = `YouTube video: ${youtubeWindowTitle.textContent}`;
    iframe.allow = "autoplay; encrypted-media; picture-in-picture";
    iframe.referrerPolicy = "strict-origin-when-cross-origin";
    iframe.setAttribute("allowfullscreen", "");
    youtubePlayerHost.replaceChildren(iframe);
    youtubePlayer = new api.Player(iframe, {
      events: {
        onReady: (event) => handleYouTubePlayerReady(event, videoId, generation),
        onStateChange: (event) => handleYouTubePlayerStateChange(event, generation),
        onError: (event) => handleYouTubePlayerError(event, generation),
        onAutoplayBlocked: (event) => {
          if (!isCurrentYouTubePlayerEvent(event, generation)) return;
          updateYouTubePlayButton(false);
          youtubePlayerStatus.textContent = "Autoplay was blocked. Press play to begin.";
        },
      },
    });
  } catch (error) {
    youtubePlayer = null;
    youtubePlayerMessage.hidden = false;
    youtubePlayerMessage.textContent = "YouTube could not initialize inside ULTRON.";
    youtubePlayerStatus.textContent = String(error?.message || "YouTube player initialization failed.");
  }
}

function handleYouTubePlayerReady(event, initialVideoId, generation) {
  if (
    generation !== youtubePlayerGeneration
    || youtubeWindow.hidden
    || (youtubePlayer && event?.target !== youtubePlayer)
  ) {
    try {
      event.target.destroy();
    } catch {
      // The player may already be gone while the window is closing.
    }
    return;
  }
  youtubePlayer = event.target;
  youtubePlayerReady = true;
  const iframe = youtubePlayer.getIframe?.();
  if (iframe) {
    iframe.title = `YouTube video: ${youtubeWindowTitle.textContent}`;
    iframe.setAttribute("allow", "autoplay; encrypted-media; picture-in-picture");
    iframe.setAttribute("referrerpolicy", "strict-origin-when-cross-origin");
  }
  if (youtubeRequestedVideoId && youtubeRequestedVideoId !== initialVideoId) {
    youtubePlayer.cueVideoById(youtubeRequestedVideoId);
  }
  youtubePlayerMessage.hidden = true;
  youtubePlayerStatus.textContent = "Video ready. Press play.";
  setYouTubeControlsEnabled(true);
  updateYouTubePlayButton(false);
}

function isCurrentYouTubePlayerEvent(event, generation) {
  return generation === youtubePlayerGeneration
    && !youtubeWindow.hidden
    && Boolean(youtubePlayer)
    && event?.target === youtubePlayer;
}

function handleYouTubePlayerStateChange(event, generation) {
  if (!isCurrentYouTubePlayerEvent(event, generation)) return;
  const state = Number(event?.data);
  if (state === 1) youtubePlayerPlaying = true;
  if ([-1, 0, 2, 5].includes(state)) youtubePlayerPlaying = false;
  updateYouTubePlayButton(youtubePlayerPlaying);
  if ([-1, 0, 1, 2, 3, 5].includes(state) && youtubePlayerMessage) youtubePlayerMessage.hidden = true;
  if ([1, 2, 3, 5].includes(state)) setYouTubeControlsEnabled(true);
  if (state === 0) youtubePlayerStatus.textContent = "Video ended.";
  if (state === 1) youtubePlayerStatus.textContent = "Video playing.";
  if (state === 2) youtubePlayerStatus.textContent = "Video paused.";
  if (state === 3) youtubePlayerStatus.textContent = "Video buffering.";
  if (state === 5) youtubePlayerStatus.textContent = "Video ready. Press play.";
}

function handleYouTubePlayerError(event, generation) {
  if (!isCurrentYouTubePlayerEvent(event, generation)) return;
  const code = Number(event?.data);
  if ([5, 100, 101, 150].includes(code) && tryNextYouTubeCandidate()) return;
  const messages = {
    2: "YouTube rejected this video identifier.",
    5: "This video could not play in the embedded player.",
    100: "This YouTube video is unavailable.",
    101: "The owner does not allow this video to be embedded.",
    150: "The owner does not allow this video to be embedded.",
    153: "YouTube could not verify the embedded player's origin.",
  };
  youtubePlayerPlaying = false;
  youtubePlayerMessage.hidden = false;
  youtubePlayerMessage.textContent = messages[code] || "YouTube could not play this video inside ULTRON.";
  youtubePlayerStatus.textContent = youtubePlayerMessage.textContent;
  setYouTubeControlsEnabled(false);
  updateYouTubePlayButton(false);
}

function tryNextYouTubeCandidate() {
  if (!youtubePlayer || !youtubePlayerReady || youtubeCandidateIndex + 1 >= youtubeCandidateVideoIds.length) return false;
  youtubeCandidateIndex += 1;
  youtubeRequestedVideoId = youtubeCandidateVideoIds[youtubeCandidateIndex];
  youtubeWindow.dataset.videoId = youtubeRequestedVideoId;
  youtubePlayerPlaying = false;
  youtubePlayerMessage.hidden = false;
  youtubePlayerMessage.textContent = "That result cannot play here. Trying the next YouTube video.";
  youtubePlayerStatus.textContent = "Trying another YouTube result.";
  setYouTubeControlsEnabled(false);
  updateYouTubePlayButton(false);
  try {
    youtubePlayer.cueVideoById(youtubeRequestedVideoId);
    return true;
  } catch {
    return tryNextYouTubeCandidate();
  }
}

function toggleYouTubePlayback() {
  if (!youtubePlayer || !youtubePlayerReady) return;
  try {
    const playing = Number(youtubePlayer.getPlayerState?.()) === 1 || youtubePlayerPlaying;
    if (playing) {
      youtubePlayer.pauseVideo();
      youtubePlayerStatus.textContent = "Video paused.";
    } else {
      youtubePlayer.playVideo();
      youtubePlayerStatus.textContent = "Starting video.";
    }
    updateYouTubePlayButton(!playing);
  } catch {
    youtubePlayerStatus.textContent = "YouTube playback controls are unavailable.";
  }
}

function seekYouTubeVideo(deltaSeconds) {
  if (!youtubePlayer || !youtubePlayerReady) return;
  try {
    const current = Math.max(0, Number(youtubePlayer.getCurrentTime?.()) || 0);
    const duration = Math.max(0, Number(youtubePlayer.getDuration?.()) || 0);
    const unclamped = current + Number(deltaSeconds || 0);
    const target = duration > 0 ? Math.min(duration, Math.max(0, unclamped)) : Math.max(0, unclamped);
    youtubePlayer.seekTo(target, true);
    youtubePlayerStatus.textContent = deltaSeconds < 0 ? "Skipped back 10 seconds." : "Skipped forward 10 seconds.";
  } catch {
    youtubePlayerStatus.textContent = "YouTube seeking is unavailable.";
  }
}

function pauseYouTubePlayer(message = "Video paused.") {
  if (!youtubePlayer || !youtubePlayerReady) return;
  try {
    youtubePlayer.pauseVideo();
  } catch {
    return;
  }
  youtubePlayerPlaying = false;
  updateYouTubePlayButton(false);
  youtubePlayerStatus.textContent = message;
}

function destroyYouTubePlayer() {
  youtubePlayerGeneration += 1;
  const player = youtubePlayer;
  youtubePlayer = null;
  youtubePlayerReady = false;
  youtubePlayerPlaying = false;
  youtubeRequestedVideoId = "";
  youtubeCandidateVideoIds = [];
  youtubeCandidateIndex = 0;
  if (youtubeWindow) delete youtubeWindow.dataset.videoId;
  if (player) {
    try {
      player.stopVideo?.();
      player.destroy?.();
    } catch {
      // Closing the app should remain safe even if the remote player is gone.
    }
  }
  resetYouTubePlayerHost();
  setYouTubeControlsEnabled(false);
  updateYouTubePlayButton(false);
  if (youtubePlayerMessage) {
    youtubePlayerMessage.hidden = false;
    youtubePlayerMessage.textContent = "Choose a video with ULTRON.";
  }
  if (youtubePlayerStatus) youtubePlayerStatus.textContent = "YouTube player closed.";
}

function resetYouTubePlayerHost() {
  if (youtubePlayerHost?.isConnected) {
    youtubePlayerHost.replaceChildren();
    return;
  }
  const viewport = youtubeWindow?.querySelector(".youtube-viewport");
  if (!viewport) return;
  const replacement = document.createElement("div");
  replacement.id = "youtubePlayerHost";
  replacement.className = "youtube-player-host";
  replacement.setAttribute("aria-label", "YouTube video player");
  viewport.append(replacement);
  youtubePlayerHost = replacement;
}

function setYouTubeControlsEnabled(enabled) {
  [youtubeBackButton, youtubePlayButton, youtubeForwardButton].filter(Boolean).forEach((button) => {
    button.disabled = !enabled;
  });
}

function updateYouTubePlayButton(playing) {
  if (!youtubePlayButton) return;
  const state = playing ? "pause" : "play";
  if (youtubePlayButton.dataset.state === state) return;
  youtubePlayButton.dataset.state = state;
  youtubePlayButton.setAttribute("aria-label", playing ? "Pause video" : "Play video");
  youtubePlayButton.title = playing ? "Pause" : "Play";
  youtubePlayButton.innerHTML = `<i data-lucide="${state}" aria-hidden="true"></i>`;
  window.lucide?.createIcons({ attrs: { "aria-hidden": "true" } });
}

async function openCameraWindow(autoCapture = false) {
  openWorkspaceWindow(cameraWindow);
  cameraSnapshot.hidden = true;
  cameraFeed.hidden = false;
  cameraPermissionMessage.hidden = false;
  cameraPermissionMessage.textContent = "Requesting camera access.";
  cameraStatus.textContent = "Connecting";
  if (!navigator.mediaDevices?.getUserMedia) {
    cameraPermissionMessage.textContent = "This browser does not expose camera capture.";
    cameraStatus.textContent = "Camera unavailable";
    return false;
  }
  try {
    if (!cameraStream) {
      cameraStream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: "user" },
        audio: false,
      });
      cameraFeed.srcObject = cameraStream;
      await cameraFeed.play();
    }
    cameraPermissionMessage.hidden = true;
    cameraStatus.textContent = "Live camera ready";
    if (cameraAutoCaptureTimer) window.clearTimeout(cameraAutoCaptureTimer);
    if (autoCapture) cameraAutoCaptureTimer = window.setTimeout(captureCameraFrame, 1100);
    return true;
  } catch (error) {
    cameraPermissionMessage.hidden = false;
    cameraPermissionMessage.textContent = "Allow camera access in the browser, then ask ULTRON to open the camera again.";
    cameraStatus.textContent = error?.name === "NotAllowedError" ? "Permission denied" : "Camera unavailable";
    return false;
  }
}

function stopCameraStream() {
  if (cameraAutoCaptureTimer) window.clearTimeout(cameraAutoCaptureTimer);
  cameraAutoCaptureTimer = null;
  if (cameraStream) cameraStream.getTracks().forEach((track) => track.stop());
  cameraStream = null;
  if (cameraFeed) cameraFeed.srcObject = null;
}

async function captureCameraFrame() {
  if (!cameraFeed.videoWidth || !cameraFeed.videoHeight) {
    cameraStatus.textContent = "Camera is not ready yet";
    return;
  }
  cameraCaptureButton.disabled = true;
  cameraStatus.textContent = "Capturing";
  const image = cameraFrameDataUrl();
  if (!image) {
    cameraCaptureButton.disabled = false;
    cameraStatus.textContent = "Camera is not ready yet";
    return;
  }
  latestCameraFrame = image;
  cameraSnapshot.src = image;
  cameraSnapshot.hidden = false;
  cameraFeed.hidden = true;
  try {
    const payload = await postJson("/api/camera/capture", { image });
    cameraStatus.textContent = payload.status === "saved" ? `Saved ${payload.filename}` : payload.message || "Capture failed";
    if (payload.status === "saved") setSubtitle(payload.message);
  } catch {
    cameraStatus.textContent = "Could not save the photo";
  } finally {
    cameraCaptureButton.disabled = false;
    window.setTimeout(() => {
      if (!cameraWindow.hidden && cameraStream) {
        cameraSnapshot.hidden = true;
        cameraFeed.hidden = false;
      }
    }, 1400);
  }
}

function cameraFrameDataUrl() {
  if (!cameraFeed.videoWidth || !cameraFeed.videoHeight) return "";
  cameraCanvas.width = cameraFeed.videoWidth;
  cameraCanvas.height = cameraFeed.videoHeight;
  const context = cameraCanvas.getContext("2d", { alpha: false });
  context.save();
  context.setTransform(1, 0, 0, 1, 0, 0);
  context.translate(cameraCanvas.width, 0);
  context.scale(-1, 1);
  context.drawImage(cameraFeed, 0, 0, cameraCanvas.width, cameraCanvas.height);
  context.restore();
  return cameraCanvas.toDataURL("image/png");
}

function initializeHandControlUi() {
  if (!['workspace', 'desktop'].includes(gestureMode)) gestureMode = desktopShell ? "desktop" : "workspace";
  gestureSensitivity = Math.max(0.55, Math.min(1.8, Number.isFinite(gestureSensitivity) ? gestureSensitivity : 1));
  desktopGestureInterpreter.setSensitivity(gestureSensitivity);
  if (gestureSensitivitySlider) gestureSensitivitySlider.value = String(gestureSensitivity);
  if (desktopShell) {
    window.addEventListener("pywebviewready", initializeDesktopHandBridge);
    if (window.pywebview?.api) void initializeDesktopHandBridge();
  }
  updateHandControlUi();
}

async function initializeDesktopHandBridge() {
  if (!desktopShell || !window.pywebview?.api?.hand_control_status) {
    desktopBridgeReady = false;
    desktopHandAvailable = false;
    updateHandControlUi();
    return false;
  }
  try {
    desktopHandStatus = await window.pywebview.api.hand_control_status();
    desktopBridgeReady = true;
    desktopHandAvailable = Boolean(desktopHandStatus?.available);
  } catch {
    desktopBridgeReady = false;
    desktopHandAvailable = false;
  }
  updateHandControlUi();
  return desktopHandAvailable;
}

async function setGestureMode(mode, options = {}) {
  const nextMode = mode === "desktop" ? "desktop" : "workspace";
  if (nextMode === "desktop") {
    const available = await initializeDesktopHandBridge();
    if (!available) {
      setSubtitle(desktopShell ? "Windows-wide hand control is unavailable on this system." : "Desktop hand control is available in the ULTRON desktop app.");
      return false;
    }
  }
  if (gestureActive) await setGestureControls(false);
  gestureMode = nextMode;
  window.localStorage.setItem("ultronGestureMode", gestureMode);
  handStatusSnapshot = { state: "off", detail: "Press Start when your hand is inside the camera frame", pose: "none", paused: false };
  updateHandControlUi();
  if (options.announce !== false) {
    setSubtitle(gestureMode === "desktop" ? "Desktop hand control selected, sir." : "ULTRON workspace hand control selected, sir.");
  }
  return true;
}

async function setGestureControls(enabled) {
  if (!enabled) {
    desktopGestureInterpreter.stop();
    if (gestureMode === "desktop") await setNativeHandControl(false);
    nativeHandQueue = [];
    handGestureController.stop();
    gestureActive = false;
    gestureGrab = null;
    gestureLastPoint = null;
    gestureCursor.hidden = true;
    handStatusSnapshot = { state: "off", detail: "Choose a mode, then start hand control", pose: "none", paused: false };
    updateHandControlUi();
    return;
  }
  gestureToggle.disabled = true;
  if (gestureSystemToggle) gestureSystemToggle.disabled = true;
  if (handGuideToggleButton) handGuideToggleButton.disabled = true;
  const preferredPanel = [modelWindow, researchWindow]
    .filter((panel) => panel && !panel.hidden)
    .sort((left, right) => Number(right.style.zIndex || 0) - Number(left.style.zIndex || 0))[0];
  try {
    if (gestureMode === "desktop" && !(await initializeDesktopHandBridge())) {
      throw new Error("Windows-wide hand control is unavailable. Use the packaged ULTRON desktop app.");
    }
    const cameraReady = await openCameraWindow(false);
    if (!cameraReady) throw new Error("Camera access is required for hand controls.");
    cameraSnapshot.hidden = true;
    cameraFeed.hidden = false;
    if (gestureMode === "desktop") {
      const nativeStatus = await setNativeHandControl(true);
      if (!nativeStatus?.ok || !nativeStatus?.enabled) throw new Error(nativeStatus?.message || "Windows-wide hand control could not start.");
    }
    await handGestureController.start(cameraFeed, gestureOverlay);
    if (gestureMode === "desktop") cameraWindow.classList.add("is-minimized");
    gestureActive = true;
    if (gestureMode === "workspace" && preferredPanel && window.innerWidth <= 980) {
      cameraWindow.classList.add("is-minimized");
      bringWindowToFront(preferredPanel);
    }
    handStatusSnapshot = {
      state: "ready",
      detail: gestureMode === "desktop" ? "Raise only your index finger to move the laptop cursor" : "Pinch a ULTRON window or model to move it",
      pose: "none",
      paused: false,
    };
    updateHandControlUi();
    setSubtitle(gestureMode === "desktop" ? "Desktop hand control online, sir. Hold a fist to pause." : "ULTRON hand controls online, sir.");
  } catch (error) {
    await setNativeHandControl(false);
    handGestureController.stop();
    gestureActive = false;
    handStatusSnapshot = { state: "error", detail: error?.message || "Hand controls could not start", pose: "none", paused: false };
    setSubtitle(error?.message || "Hand controls could not start.");
    cameraStatus.textContent = "Hand tracking unavailable";
    updateHandControlUi();
  } finally {
    gestureToggle.disabled = false;
    if (gestureSystemToggle) gestureSystemToggle.disabled = false;
    if (handGuideToggleButton) handGuideToggleButton.disabled = false;
  }
}

function handleGestureFrame(signal) {
  if (gestureMode === "desktop" && gestureActive) {
    gestureCursor.hidden = true;
    desktopGestureInterpreter.update(signal || { visible: false });
    return;
  }
  if (!gestureActive || !signal?.visible) {
    gestureCursor.hidden = true;
    if (gestureGrab && !signal?.pinching) gestureGrab = null;
    return;
  }
  gestureCursor.hidden = false;
  gestureCursor.style.transform = `translate3d(${signal.x}px, ${signal.y}px, 0)`;
  gestureCursor.classList.toggle("is-pinching", Boolean(signal.pinching));
  gestureToggle.title = signal.pinching ? "Pinch detected" : "Hand controls active";

  if (signal.justPinched) beginGestureGrab(signal.x, signal.y);
  if (signal.pinching && gestureGrab) updateGestureGrab(signal.x, signal.y);
  if (signal.justReleased) {
    gestureGrab = null;
    gestureLastPoint = null;
  }
}

function enqueueNativeHandEvent(event) {
  if (!event || gestureMode !== "desktop" || !gestureActive || !desktopBridgeReady) return;
  if (event.type === "move" && nativeHandQueue.at(-1)?.type === "move") nativeHandQueue[nativeHandQueue.length - 1] = event;
  else nativeHandQueue.push(event);
  if (nativeHandQueue.length > 18) {
    const removable = nativeHandQueue.findIndex((item) => item.type === "move");
    if (removable >= 0) nativeHandQueue.splice(removable, 1);
  }
  void pumpNativeHandQueue();
}

async function pumpNativeHandQueue() {
  if (nativeHandDispatching || !window.pywebview?.api?.hand_input) return;
  nativeHandDispatching = true;
  try {
    while (nativeHandQueue.length) {
      const event = nativeHandQueue.shift();
      const result = await window.pywebview.api.hand_input(event);
      desktopHandStatus = result;
      if (result && !result.enabled && result.last_stop_reason === "emergency_hotkey") {
        nativeHandQueue = [];
        desktopGestureInterpreter.stop();
        handGestureController.stop();
        gestureActive = false;
        handStatusSnapshot = { state: "off", detail: "Emergency stop received from Ctrl+Alt+H", pose: "none", paused: false };
        setSubtitle("Desktop hand control stopped safely.");
        updateHandControlUi();
        break;
      }
    }
  } catch {
    nativeHandQueue = [];
    handStatusSnapshot = { state: "error", detail: "Native cursor bridge stopped responding", pose: "none", paused: false };
    updateHandControlUi();
  } finally {
    nativeHandDispatching = false;
  }
}

async function setNativeHandControl(enabled) {
  if (!desktopShell || !window.pywebview?.api?.set_hand_control) {
    return { ok: !enabled, available: false, enabled: false, message: "Desktop hand control bridge is unavailable." };
  }
  try {
    desktopHandStatus = await window.pywebview.api.set_hand_control(Boolean(enabled));
    desktopBridgeReady = true;
    desktopHandAvailable = Boolean(desktopHandStatus?.available);
    return desktopHandStatus;
  } catch {
    desktopBridgeReady = false;
    desktopHandAvailable = false;
    return { ok: false, available: false, enabled: false, message: "Desktop hand control bridge stopped responding." };
  } finally {
    updateHandControlUi();
  }
}

function handleDesktopGestureStatus(snapshot) {
  const previousState = handStatusSnapshot.state;
  const previousPaused = handStatusSnapshot.paused;
  handStatusSnapshot = snapshot || handStatusSnapshot;
  const now = performance.now();
  const shouldRender = previousState !== handStatusSnapshot.state
    || previousPaused !== handStatusSnapshot.paused
    || now - lastHandStatusRenderAt >= 90;
  if (!shouldRender) return;
  lastHandStatusRenderAt = now;
  if (gestureMode === "desktop" && gestureActive && cameraStatus) {
    cameraStatus.textContent = handStatusSnapshot.detail || "Desktop hand control";
  }
  updateHandControlUi();
}

function handleDesktopGestureAction(command) {
  const labels = {
    minimize_all: "Showing the desktop.",
    restore_all: "Restoring your windows.",
    app_next: "Switching to the next app.",
    app_previous: "Switching to the previous app.",
    desktop_left: "Switching to the previous desktop.",
    desktop_right: "Switching to the next desktop.",
    task_view: "Opening Task View.",
    browser_back: "Going back.",
    browser_forward: "Going forward.",
  };
  if (labels[command]) setSubtitle(labels[command]);
}

function updateHandControlUi() {
  const paused = gestureMode === "desktop" && desktopGestureInterpreter.paused;
  const modeName = gestureMode === "desktop" ? "Whole desktop" : "ULTRON workspace";
  let statusName = gestureActive ? handStatusSnapshot.state.replaceAll("_", " ") : "Off";
  if (paused) statusName = "Paused";
  statusName = statusName ? statusName[0].toUpperCase() + statusName.slice(1) : "Off";
  if (handControlModeLabel) handControlModeLabel.textContent = modeName;
  if (handControlStatusLabel) handControlStatusLabel.textContent = statusName;
  if (handControlStatusDetail) handControlStatusDetail.textContent = handStatusSnapshot.detail;
  gestureModeButtons.forEach((button) => button.setAttribute("aria-pressed", String(button.dataset.gestureMode === gestureMode)));
  if (desktopGestureModeButton) desktopGestureModeButton.disabled = !desktopShell || (desktopBridgeReady && !desktopHandAvailable);
  [gestureToggle, gestureSystemToggle, handGuideToggleButton].filter(Boolean).forEach((button) => {
    button.setAttribute("aria-pressed", String(gestureActive));
    button.setAttribute("aria-label", gestureActive ? "Disable hand controls" : "Enable hand controls");
  });
  if (gestureSystemToggle) setButtonLabel(gestureSystemToggle, gestureActive ? "Stop" : "Start");
  if (handGuideToggleButton) setButtonLabel(handGuideToggleButton, gestureActive ? "Stop hand control" : "Start hand control");
  if (gesturePauseButton) {
    gesturePauseButton.disabled = !gestureActive || gestureMode !== "desktop";
    gesturePauseButton.setAttribute("aria-pressed", String(paused));
    setButtonLabel(gesturePauseButton, paused ? "Resume" : "Pause");
  }
  if (gestureSensitivityValue) gestureSensitivityValue.textContent = `${Math.round(gestureSensitivity * 100)}%`;
  document.body.classList.toggle("hand-desktop-live", gestureActive && gestureMode === "desktop" && !paused);
  document.body.classList.toggle("hand-control-paused", paused);
  if (handGuideLiveStatus) {
    handGuideLiveStatus.classList.toggle("is-live", gestureActive && !paused);
    handGuideLiveStatus.classList.toggle("is-paused", paused);
  }
  if (handGuideStatusLabel) handGuideStatusLabel.textContent = gestureActive ? `${modeName}: ${statusName}` : "Hand control is off";
  if (handGuideStatusDetail) {
    handGuideStatusDetail.textContent = gestureActive
      ? handStatusSnapshot.detail
      : gestureMode === "desktop" && !desktopShell
        ? "Desktop mode works only inside the ULTRON application"
        : "Select Desktop mode to control the entire Windows screen";
  }
}

function openHandGuide() {
  if (!handGuideModal) return;
  handGuideModal.hidden = false;
  updateHandControlUi();
  handGuideCloseButton?.focus();
}

function closeHandGuide() {
  if (handGuideModal) handGuideModal.hidden = true;
}

function beginGestureGrab(x, y) {
  const target = document.elementFromPoint(x, y);
  if (!target) return;
  if (target === modelCanvas || target.closest?.("#modelCanvas")) {
    gestureGrab = { mode: "model" };
    gestureLastPoint = { x, y };
    bringWindowToFront(modelWindow);
    return;
  }
  const panel = target.closest?.(".app-window");
  if (!panel || panel.hidden) return;
  const rect = panel.getBoundingClientRect();
  panel.classList.remove("is-maximized", "is-minimized");
  bringWindowToFront(panel);
  gestureGrab = { mode: "window", panel, offsetX: x - rect.left, offsetY: y - rect.top };
}

function updateGestureGrab(x, y) {
  if (gestureGrab.mode === "model") {
    if (gestureLastPoint) photoModeler.rotateBy(x - gestureLastPoint.x, y - gestureLastPoint.y);
    gestureLastPoint = { x, y };
    return;
  }
  const panel = gestureGrab.panel;
  const maxLeft = Math.max(8, window.innerWidth - panel.offsetWidth - 8);
  const maxTop = Math.max(8, window.innerHeight - 56);
  panel.style.left = `${Math.max(8, Math.min(maxLeft, x - gestureGrab.offsetX))}px`;
  panel.style.top = `${Math.max(8, Math.min(maxTop, y - gestureGrab.offsetY))}px`;
  panel.style.right = "auto";
  panel.style.bottom = "auto";
}

function handleGestureSwipe(direction) {
  if (gestureMode === "desktop") return;
  if (detailsCollapsed) setDetailsCollapsed(false);
  const names = drawerTabs.map((button) => button.dataset.drawerTab);
  const current = Math.max(0, names.indexOf(activeDrawerTab));
  const delta = direction === "left" ? 1 : -1;
  selectDrawerTab(names[(current + delta + names.length) % names.length]);
}

function handleGestureStatus(status, detail) {
  if (gestureToggle) gestureToggle.title = detail || "Hand controls";
  if (status === "loading" || status === "ready" || status === "error") cameraStatus.textContent = detail;
  if (status === "loading" || status === "error") {
    handStatusSnapshot = { state: status, detail: detail || "Hand tracking status changed", pose: "none", paused: false };
    updateHandControlUi();
  }
}

async function buildGeneratedModel(description) {
  const clean = String(description || "").trim();
  openWorkspaceWindow(modelWindow);
  bringWindowToFront(modelWindow);
  modelStatus.textContent = clean ? `Building ${clean}` : "Model description required";
  modelStats.textContent = "Generating";
  await new Promise((resolve) => window.requestAnimationFrame(resolve));
  if (!clean) return;
  try {
    const payload = await postJson("/api/model/generate", { description: clean });
    if (!payload.scene) throw new Error(payload.message || "A valid 3D scene was not generated.");
    const result = photoModeler.buildFromScene(payload.scene);
    finishModelBuild(result, `${payload.scene.name || clean} ready`);
  } catch (error) {
    modelStatus.textContent = error?.message || "3D generation failed";
    modelStats.textContent = "No mesh";
  }
}

async function buildModelFromCamera(target = "", fallback360 = true) {
  cancelObjectScan();
  openWorkspaceWindow(modelWindow);
  modelStatus.textContent = `Finding ${target || "camera object"}`;
  modelStats.textContent = "Detecting";
  const cameraReady = await openCameraWindow(false);
  if (!cameraReady) {
    modelStatus.textContent = "Camera unavailable";
    modelStats.textContent = "No mesh";
    return;
  }
  cameraSnapshot.hidden = true;
  cameraFeed.hidden = false;
  try {
    const capture = await objectScanner.captureFromVideo(String(target || ""));
    if (!capture || !targetMatchesLabel(target, capture.label)) {
      const label = target ? ` ${target}` : " object";
      cameraStatus.textContent = `No${label} isolated`;
      modelStatus.textContent = `Could not isolate${label}`;
      modelStats.textContent = "Try clearer lighting";
      return;
    }
    cameraStatus.textContent = `${titleCase(capture.label)} isolated`;
    if (isRotationalObject(capture.label, target)) {
      const result = photoModeler.buildFromScan([capture], { name: `${capture.label}-single-view` });
      finishModelBuild(result, `${titleCase(capture.label)} isolated; rotational model ready`);
      bringWindowToFront(modelWindow);
      return;
    }
    if (fallback360) {
      modelStatus.textContent = `${titleCase(capture.label)} needs multiple views`;
      modelStats.textContent = "Starting 360 scan";
      void start360ObjectScan(target || capture.label, 12, capture);
      return;
    }
    const result = await photoModeler.buildFromImage(capture.image, { name: `${capture.label}-isolated` });
    finishModelBuild(result, `${titleCase(capture.label)} isolated-object relief ready`);
    bringWindowToFront(modelWindow);
  } catch (error) {
    modelStatus.textContent = error?.message || "Object reconstruction failed";
    modelStats.textContent = "No mesh";
    cameraStatus.textContent = "Object scan unavailable";
  }
}

async function start360ObjectScan(target = "", requiredViews = 12, initialCapture = null) {
  cancelObjectScan();
  const required = Math.max(6, Math.min(24, Number(requiredViews) || 12));
  const session = ++objectScanSession;
  objectScanActive = true;
  const captures = initialCapture ? [initialCapture] : [];
  openWorkspaceWindow(modelWindow);
  modelStatus.textContent = `Scanning ${target || "object"} in 360 degrees`;
  modelStats.textContent = `${captures.length} / ${required} views`;
  const cameraReady = await openCameraWindow(false);
  if (!cameraReady || session !== objectScanSession) {
    cancelObjectScan("360 scan stopped");
    return;
  }
  cameraSnapshot.hidden = true;
  cameraFeed.hidden = false;
  updateObjectScanProgress(captures.length, required, target || initialCapture?.label || "object");
  objectScanProgress.hidden = false;
  cameraStatus.textContent = "Rotate the object slowly";

  try {
    await objectScanner.load();
    while (session === objectScanSession && captures.length < required) {
      await wait(720);
      if (session !== objectScanSession) return;
      const capture = await objectScanner.captureFromVideo(String(target || ""));
      if (!capture || !targetMatchesLabel(target, capture.label)) {
        cameraStatus.textContent = target ? `Keep the ${target} inside the frame` : "Keep the object inside the frame";
        continue;
      }
      if (capture.foregroundRatio < 0.025) {
        cameraStatus.textContent = "Move the object closer to the camera";
        continue;
      }
      captures.push(capture);
      updateObjectScanProgress(captures.length, required, target || capture.label);
      cameraStatus.textContent = captures.length < required ? "Keep rotating the object slowly" : "Fusing captured views";
      modelStats.textContent = `${captures.length} / ${required} views`;
    }
    if (session !== objectScanSession || captures.length < required) return;
    const result = photoModeler.buildFromScan(captures, { name: `${target || captures[0].label || "object"}-360-scan` });
    objectScanActive = false;
    objectScanProgress.hidden = true;
    finishModelBuild(result, `${titleCase(target || captures[0].label || "Object")} 360 scan ready`);
    cameraStatus.textContent = `360 scan complete: ${captures.length} views`;
    bringWindowToFront(modelWindow);
  } catch (error) {
    if (session !== objectScanSession) return;
    objectScanActive = false;
    objectScanProgress.hidden = true;
    modelStatus.textContent = error?.message || "360 scan failed";
    modelStats.textContent = "No mesh";
    cameraStatus.textContent = "360 scan failed";
  }
}

function cancelObjectScan(message = "") {
  objectScanSession += 1;
  objectScanActive = false;
  if (objectScanProgress) objectScanProgress.hidden = true;
  objectScanner.clearOverlay();
  if (message && cameraStatus) cameraStatus.textContent = message;
}

function updateObjectScanProgress(count, required, target) {
  const percent = Math.min(100, Math.round((count / required) * 100));
  objectScanLabel.textContent = `${titleCase(target)} 360 scan`;
  objectScanPercent.textContent = `${percent}%`;
  objectScanMeter.max = required;
  objectScanMeter.value = count;
  objectScanMeter.textContent = `${percent}%`;
  objectScanViews.textContent = `${count} / ${required} views`;
}

function finishModelBuild(result, status) {
  modelStats.textContent = `${result.vertices.toLocaleString()} vertices / ${result.triangles.toLocaleString()} triangles`;
  setModelVisibility(true);
  photoModeler.setModelScale(1);
  if (modelScaleSlider) modelScaleSlider.value = "1";
  photoModeler.resize();
  modelStatus.textContent = status;
}

function scaleModel(factor) {
  openWorkspaceWindow(modelWindow);
  const scale = photoModeler.scaleBy(factor);
  if (modelScaleSlider) modelScaleSlider.value = String(scale);
  modelStatus.textContent = `Model size ${Math.round(scale * 100)}%`;
  bringWindowToFront(modelWindow);
}

function setModelVisibility(visible) {
  modelVisible = photoModeler.setVisible(visible);
  if (!modelVisibilityButton) return;
  modelVisibilityButton.setAttribute("aria-pressed", String(modelVisible));
  modelVisibilityButton.setAttribute("aria-label", modelVisible ? "Hide 3D model" : "Show 3D model");
  modelVisibilityButton.title = modelVisible ? "Hide model" : "Show model";
  modelVisibilityButton.innerHTML = `<i data-lucide="${modelVisible ? "eye" : "eye-off"}" aria-hidden="true"></i>`;
  window.lucide?.createIcons({ attrs: { "aria-hidden": "true" } });
  modelStatus.textContent = modelVisible ? "Model visible" : "Model hidden";
}

function resetModelView() {
  photoModeler.resetView();
  modelVisible = true;
  if (modelScaleSlider) modelScaleSlider.value = "1";
  setModelVisibility(true);
  modelStatus.textContent = "3D view reset";
}

function targetMatchesLabel(target, label) {
  const expected = String(target || "").toLowerCase().trim();
  if (!expected || expected === "object") return true;
  const actual = String(label || "").toLowerCase();
  const aliases = {
    can: ["bottle", "cup", "can"],
    phone: ["cell phone", "phone"],
    shoe: ["shoe", "sports ball"],
  };
  return (aliases[expected] || [expected]).some((candidate) => actual.includes(candidate));
}

function isRotationalObject(label, target) {
  return /\b(?:bottle|cup|vase|can|wine glass)\b/.test(`${label || ""} ${target || ""}`.toLowerCase());
}

function titleCase(value) {
  const text = String(value || "object").trim();
  return text ? text.charAt(0).toUpperCase() + text.slice(1) : "Object";
}

function wait(milliseconds) {
  return new Promise((resolve) => window.setTimeout(resolve, milliseconds));
}

function exportCameraModel() {
  try {
    const result = photoModeler.exportOBJ();
    modelStatus.textContent = `Exported ${result.filename}`;
    modelStats.textContent = `${result.vertices.toLocaleString()} vertices / ${result.triangles.toLocaleString()} triangles`;
  } catch (error) {
    modelStatus.textContent = error?.message || "Model export failed";
  }
}

function renderResearchDirective(directive) {
  openWorkspaceWindow(researchWindow);
  const query = String(directive.query || "").trim();
  const answer = String(directive.answer || "").trim();
  const results = Array.isArray(directive.results) ? directive.results : [];
  if (query) researchQueryInput.value = query;
  researchStatus.textContent = directive.synthesized ? "Synthesized" : directive.status === "success" ? "Sources ready" : directive.status || "Ready";
  researchSourceCount.textContent = `${results.length} ${results.length === 1 ? "source" : "sources"}`;

  researchSummary.replaceChildren();
  const heading = document.createElement("h3");
  heading.textContent = query || "Research console ready";
  researchSummary.appendChild(heading);
  const paragraphs = answer ? answer.split(/\n\s*\n/).filter(Boolean) : ["Ask ULTRON to gather information or enter a topic above."];
  paragraphs.forEach((paragraph) => {
    const element = document.createElement("p");
    element.textContent = paragraph;
    researchSummary.appendChild(element);
  });

  researchSources.replaceChildren();
  results.forEach((result) => {
    const url = safeWebUrl(result.url);
    if (!url) return;
    const item = document.createElement("li");
    const link = document.createElement("a");
    link.href = url.href;
    link.target = "_blank";
    link.rel = "noopener noreferrer";
    const copy = document.createElement("span");
    const title = document.createElement("strong");
    const host = document.createElement("small");
    title.textContent = String(result.title || url.hostname);
    host.textContent = url.hostname.replace(/^www\./, "");
    copy.append(title, host);
    const icon = document.createElement("i");
    icon.dataset.lucide = "arrow-up-right";
    icon.setAttribute("aria-hidden", "true");
    link.append(copy, icon);
    item.appendChild(link);
    researchSources.appendChild(item);
  });
  window.lucide?.createIcons({ attrs: { "aria-hidden": "true" } });
  if (!query) window.setTimeout(() => researchQueryInput.focus(), 80);
}

async function runResearch(rawQuery) {
  const query = String(rawQuery || "").trim();
  if (!query) {
    researchQueryInput.focus();
    return;
  }
  openWorkspaceWindow(researchWindow);
  researchSubmitButton.disabled = true;
  researchStatus.textContent = "Researching";
  researchSourceCount.textContent = "Searching live web";
  setVisualState("thinking");
  setSubtitle(`Researching: ${query}`);
  try {
    const payload = await postJson("/api/research", { query });
    await handleUiDirective(payload.ui_directive);
    renderHistory(payload.conversation_history || []);
    renderRecentTasks(payload.recent_tasks || []);
    const response = payload.response || payload.subtitle || payload.message || "Research completed.";
    setSubtitle(response);
    setVisualState("speaking");
    await speakText(response);
    scheduleListeningReturn({ keepListening: true });
  } catch {
    researchStatus.textContent = "Unavailable";
    researchSourceCount.textContent = "0 sources";
    setSubtitle("The research service could not reach the ULTRON runtime.");
    setVisualState("idle");
  } finally {
    researchSubmitButton.disabled = false;
  }
}

function safeWebUrl(value) {
  try {
    const url = new URL(String(value || ""));
    return ["http:", "https:"].includes(url.protocol) ? url : null;
  } catch {
    return null;
  }
}

async function loadStartupBriefing() {
  if (startupBriefingStarted || window.sessionStorage.getItem("ultronStartupBriefingShown") === "true") return;
  startupBriefingStarted = true;
  try {
    const payload = await fetchJson("/api/briefing");
    bargeInEnabled = payload.barge_in_enabled !== false;
    window.sessionStorage.setItem("ultronStartupBriefingShown", "true");
    if (payload.status === "disabled") return;
    const message = String(payload.message || "ULTRON 2.7 is online.");
    setSubtitle(message);
    setVisualState("speaking");
    await speakText(message);
    scheduleListeningReturn();
  } catch {
    startupBriefingStarted = false;
  }
}

async function loadProviders() {
  try {
    providerStatus = await fetchJson("/api/voice/providers");
    applyProviders(providerStatus);
  } catch {
    providerStatus = null;
    sttProviderDetail.textContent = "Runtime API pending";
    captureProviderDetail.textContent = "Runtime API pending";
    ttsProviderDetail.textContent = "Runtime API pending";
  }
}

async function loadWakeStatus() {
  try {
    const payload = await fetchJson("/api/wake/status");
    applyWakeStatus(payload.wake);
  } catch {
    wakeStateLabel.textContent = "Pending";
    wakeDetail.textContent = "Wake API pending";
  }
}

async function loadSkills() {
  try {
    const payload = await fetchJson("/api/skills");
    renderSkills(payload.skills || []);
  } catch {
    renderSkills([]);
  }
}

async function loadMemoryKnowledge() {
  try {
    const memory = await fetchJson("/api/memory");
    const status = await fetchJson("/api/status");
    memoryEnabled = memory.enabled !== undefined ? Boolean(memory.enabled) : memoryEnabled;
    renderKnowledgePanel({ memory: memory.memory || [], sources: status.knowledge_sources || [], memoryEnabled });
    renderRecentTasks(status.recent_tasks || []);
  } catch {
    renderKnowledgePanel({ memory: [], sources: [], memoryEnabled });
  }
}

async function toggleMemory() {
  memoryEnabled = !memoryEnabled;
  try {
    const payload = await postJson("/api/memory/toggle", { enabled: memoryEnabled });
    memoryEnabled = Boolean(payload.enabled);
    renderKnowledgePanel({ memory: payload.memory || [], sources: payload.knowledge_sources || [], memoryEnabled });
    setSubtitle(memoryEnabled ? "Memory is now on." : "Memory is now off.");
  } catch {
    setSubtitle("Memory controls could not reach the ULTRON runtime.");
  }
}

async function forgetMemory() {
  const query = memoryForgetInput.value.trim();
  if (!query) return;
  try {
    const payload = await postJson("/api/memory/forget", { query });
    memoryForgetInput.value = "";
    memoryEnabled = payload.enabled !== undefined ? Boolean(payload.enabled) : memoryEnabled;
    renderKnowledgePanel({ memory: payload.memory || [], sources: payload.knowledge_sources || [], memoryEnabled });
    setSubtitle(payload.last_subtitle || `Forgot ${payload.removed || 0} matching memory item(s).`);
  } catch {
    setSubtitle("Forget memory could not reach the ULTRON runtime.");
  }
}

async function searchKnowledge() {
  const query = knowledgeSearchInput.value.trim();
  if (!query) {
    await loadMemoryKnowledge();
    return;
  }
  try {
    const payload = await fetchJson(`/api/knowledge/search?query=${encodeURIComponent(query)}&limit=5`);
    renderKnowledgePanel({ matches: payload.knowledge?.matches || [], sources: payload.knowledge?.sources || [] });
  } catch {
    renderKnowledgePanel({ error: "Knowledge search unavailable." });
  }
}

async function startAlwaysListening() {
  alwaysListening = true;
  const payload = await postJson("/api/wake/start", {});
  applyVoiceStatus(payload.voice);
  applyWakeStatus(payload.wake);
  const doubleClap = payload.wake?.wake_provider === "double_clap";
  setSubtitle(payload.last_subtitle || (doubleClap ? "Voice standby. Double clap to wake me." : "Always-listening is on. Say ULTRON or Hey ULTRON."));
  setVisualState("waiting_for_wake_word");
  if (doubleClap && providerStatus?.active?.capture === "sounddevice") {
    micEnabled = true;
    voiceBadge.textContent = "Double-clap standby";
    startBackendWakePolling();
    return;
  }
  if (!SpeechRecognition) {
    voiceBadge.textContent = "Wake mock available";
    return;
  }
  micEnabled = true;
  startRecognition();
}

async function stopAlwaysListening() {
  alwaysListening = false;
  stopBackendWakePolling();
  const payload = await postJson("/api/wake/stop", {});
  applyVoiceStatus(payload.voice);
  applyWakeStatus(payload.wake);
  setSubtitle(payload.last_subtitle || "Always-listening is off.");
  setVisualState("idle");
  if (recognition && recognitionActive) {
    recognition.stop();
  }
}

async function testVoiceProviders() {
  setVisualState("thinking");
  setSubtitle("Testing voice providers...");
  try {
    const stt = await postJson("/api/voice/test-stt", { transcript: "ULTRON, create note provider test" });
    const tts = await postJson("/api/voice/test-tts", { text: "ULTRON voice provider test." });
    providerStatus = tts;
    applyProviders(tts);
    applyVoiceDiagnostics(stt.voice_diagnostics || tts.voice_diagnostics);
    const transcript = stt.transcript?.text || "No transcript";
    const speechStatus = tts.speech?.status || "checked";
    setSubtitle(`STT: ${transcript}\nTTS: ${speechStatus}`);
    if (tts.speech?.provider === "browser_speech_synthesis" && !voiceMuted) {
      await playBrowserSpeech("ULTRON voice provider test.");
    }
    setVisualState("speaking");
    scheduleListeningReturn();
  } catch {
    setSubtitle("Voice provider test could not reach the ULTRON runtime.");
    setVisualState("idle");
  }
}

async function calibrateVoice() {
  setVisualState("listening");
  setSubtitle("Calibrating microphone. Speak normally for a moment.");
  voiceBadge.textContent = "Calibrating";
  try {
    const warmup = await postJson("/api/voice/warmup", {});
    providerStatus = warmup;
    applyProviders(warmup);
    const payload = await postJson("/api/voice/calibrate", { seconds: 2.5 });
    applyVoiceStatus(payload.voice);
    applyWakeStatus(payload.wake);
    applyVoiceDiagnostics(payload.voice_diagnostics);
    await loadProviders();
    setSubtitle(payload.message || "Voice calibration completed.");
    setVisualState("speaking");
    scheduleListeningReturn();
  } catch {
    setSubtitle("Voice calibration could not reach the ULTRON runtime.");
    setVisualState("idle");
  }
}

async function startVoiceInput() {
  if (alwaysListening) {
    await stopAlwaysListening();
  }
  micEnabled = true;
  setButtonLabel(micToggle, "Stop Mic");
  micStatusLabel.textContent = "On";
  micPrivacyDetail.textContent = pushToTalk ? "Listening for one command" : "Continuous listening until stopped";
  voiceBadge.textContent = SpeechRecognition ? "Listening" : "Speech API unavailable";
  setVisualState("listening");
  const payload = await postJson("/api/voice/start", { push_to_talk: pushToTalk });
  applyVoiceStatus(payload.voice);
  applyWakeStatus(payload.wake);
  if (!SpeechRecognition) {
    setSubtitle("This browser does not expose speech recognition. Open ULTRON in Chrome or Edge, then allow microphone access. Typed input and Mock Voice still work.");
    return;
  }
  setSubtitle(pushToTalk ? "Listening. Speak one command now." : "Continuous listening is on. Speak when ready.");
  startRecognition();
}

async function stopVoiceInput() {
  micEnabled = false;
  setButtonLabel(micToggle, "Start Mic");
  micStatusLabel.textContent = "Off";
  micPrivacyDetail.textContent = "Microphone stopped";
  voiceBadge.textContent = "Voice standby";
  setVisualState("idle");
  if (recognition && recognitionActive) {
    recognition.stop();
  }
  const payload = await postJson("/api/voice/stop", {});
  applyVoiceStatus(payload.voice);
  applyWakeStatus(payload.wake);
}

function setupSpeechRecognition() {
  if (!SpeechRecognition) return;
  recognition = new SpeechRecognition();
  recognition.lang = "en-US";
  recognition.interimResults = false;
  recognition.maxAlternatives = 1;
  recognition.onstart = () => {
    recognitionActive = true;
    voiceBadge.textContent = "Listening";
    setVisualState("listening");
  };
  recognition.onspeechstart = () => {
    voiceBadge.textContent = "Speech detected";
    setVisualState("listening");
  };
  recognition.onresult = (event) => {
    const transcript = event.results?.[0]?.[0]?.transcript || "";
    const confidence = event.results?.[0]?.[0]?.confidence;
    if (transcript.trim()) handleVoiceTranscript(transcript, { confidence });
  };
  recognition.onerror = (event) => {
    voiceBadge.textContent = `Voice error: ${event.error}`;
    if (event.error === "not-allowed" || event.error === "service-not-allowed") {
      setSubtitle("Microphone permission was blocked. Allow microphone access in the browser site settings, then press Start Mic again.");
      micEnabled = false;
      applyVoiceStatus({ microphone_enabled: false, muted: voiceMuted, push_to_talk: pushToTalk, listening: false, speaking: false });
      setVisualState("idle");
      return;
    }
    if (event.error === "no-speech") {
      setSubtitle(pushToTalk ? "I did not hear speech. Press Start Mic and try again, or switch to Continuous." : "I did not hear speech. Still listening...");
      setVisualState("listening");
      return;
    }
    setSubtitle(`Voice capture error: ${event.error}. Typed mode and Mock Voice still work.`);
    setVisualState(micEnabled ? "listening" : "idle");
  };
  recognition.onend = () => {
    recognitionActive = false;
    if (micEnabled && !alwaysListening && !pushToTalk) {
      window.setTimeout(startRecognition, 350);
    }
  };
}

function startRecognition() {
  if (!recognition || recognitionActive) return;
  recognition.continuous = alwaysListening || !pushToTalk;
  try {
    recognition.start();
  } catch {
    voiceBadge.textContent = "Voice restart pending";
  }
}

async function handleVoiceTranscript(transcript, options = {}) {
  if (!transcript.trim()) return;
  if (alwaysListening) {
    await handleWakeTranscript(transcript);
    return;
  }
  setSubtitle("Working on it.");
  setVisualState("thinking");
  voiceBadge.textContent = "Processing voice";
  try {
    const body = { transcript };
    if (typeof options.confidence === "number" && Number.isFinite(options.confidence) && options.confidence > 0.01) body.confidence = options.confidence;
    const payload = await postJson("/api/voice/transcribe", body);
    applyVoiceStatus(payload.voice);
    applyVoiceDiagnostics(payload.voice_diagnostics);
    renderHistory([...(payload.conversation_history || []), ...(payload.history || [])]);
    const response = payload.spoken_response || payload.subtitle || payload.message || "Voice command processed.";
    setSubtitle(formatAssistantSubtitle(payload, response));
    await handleUiDirective(payload.ui_directive);
    confirmVoiceButton.hidden = !payload.needs_confirmation;
    if (payload.needs_confirmation || taskNeedsConfirmation(payload.task)) {
      showConfirmation(payload.task, { command: payload.voice?.pending_confirmation_goal || transcript, source: "voice" });
    } else {
      clearPendingConfirmation();
    }
    if (payload.status === "empty") {
      setVisualState("listening");
      return;
    }
    setVisualState(payload.needs_confirmation ? "listening" : "speaking");
    await speakText(response);
    scheduleListeningReturn({ keepListening: shouldContinueConversation(payload) });
  } catch {
    setSubtitle("Voice mode could not reach the ULTRON runtime.");
    setVisualState("idle");
  }
}

async function captureBackendVoice(options = {}) {
  const fromBargeIn = Boolean(options.fromBargeIn);
  if (fromBargeIn) pauseBackendWakePolling();
  setSubtitle("Listening.");
  setVisualState("listening");
  voiceBadge.textContent = "Backend capture";
  try {
    const payload = await postJson("/api/voice/capture", {});
    applyVoiceStatus(payload.voice);
    applyWakeStatus(payload.wake);
    applyVoiceDiagnostics(payload.voice_diagnostics);
    renderHistory([...(payload.conversation_history || []), ...(payload.history || [])]);
    if (payload.status === "capture_unavailable") {
      setSubtitle(payload.message || "Backend microphone capture is unavailable. Browser mic and typed mode still work.");
      setVisualState("listening");
      return;
    }
    const response = payload.spoken_response || payload.subtitle || payload.message || "Voice command processed.";
    const understood = payload.record?.ultron_understood || payload.transcript?.text || "";
    setSubtitle(formatAssistantSubtitle(payload, response));
    await handleUiDirective(payload.ui_directive);
    if (payload.needs_confirmation || taskNeedsConfirmation(payload.task)) {
      showConfirmation(payload.task, { command: payload.voice?.pending_confirmation_goal || understood, source: "voice" });
      setVisualState("listening");
      return;
    }
    clearPendingConfirmation();
    if (fromBargeIn) bargeInHandling = false;
    setVisualState(payload.status === "empty" ? "listening" : "speaking");
    await speakText(response);
    scheduleListeningReturn({ keepListening: shouldContinueConversation(payload) });
  } catch {
    setSubtitle("Backend microphone capture could not reach the ULTRON runtime.");
    setVisualState(micEnabled ? "listening" : "idle");
  } finally {
    if (fromBargeIn) {
      bargeInHandling = false;
      if (alwaysListening && wakeProvider === "double_clap") startBackendWakePolling();
    }
  }
}

async function handleWakeTranscript(transcript) {
  setSubtitle("Checking the wake phrase.");
  setVisualState("transcribing");
  voiceBadge.textContent = "Checking wake gate";
  try {
    const payload = await postJson("/api/wake/process", { transcript, audio_energy: transcript.trim() ? 0.8 : 0.0 });
    applyVoiceStatus(payload.voice);
    applyWakeStatus(payload.wake);
    applyVoiceDiagnostics(payload.voice_diagnostics);
    renderHistory([...(payload.conversation_history || []), ...(payload.history || [])]);
    if (payload.status === "ignored") {
      setSubtitle(payload.message || "Input ignored by wake/VAD gate.");
      setVisualState(payload.visual_state || "waiting_for_wake_word");
      return;
    }
    if (payload.status === "wake_detected") {
      const greeting = payload.spoken_response || payload.subtitle || "At your service, sir.";
      setSubtitle(greeting);
      setVisualState("listening");
      await speakText(greeting);
      return;
    }
    const response = payload.spoken_response || payload.subtitle || payload.message || "Voice command processed.";
    setSubtitle(formatAssistantSubtitle(payload, response));
    await handleUiDirective(payload.ui_directive);
    confirmVoiceButton.hidden = !payload.needs_confirmation;
    if (payload.needs_confirmation || taskNeedsConfirmation(payload.task)) {
      showConfirmation(payload.task, { command: payload.voice?.pending_confirmation_goal || transcript, source: "voice" });
    } else {
      clearPendingConfirmation();
    }
    setVisualState(payload.needs_confirmation ? "listening" : "speaking");
    await speakText(response);
    scheduleListeningReturn({ keepListening: shouldContinueConversation(payload) });
  } catch {
    setSubtitle("Wake mode could not reach the ULTRON runtime.");
    setVisualState("waiting_for_wake_word");
  }
}

async function speakText(text) {
  armillaryCore.setSpeechText(text);
  const payload = await postJson("/api/speak", { text, muted: voiceMuted });
  applyVoiceStatus(payload.voice);
  if (payload.speech?.provider && providerStatus?.active) {
    providerStatus.active.tts = payload.speech.provider;
    applyProviders(providerStatus);
  }
  if (voiceMuted || !text.trim()) return;
  if (payload.speech?.provider && payload.speech.provider !== "browser_speech_synthesis") {
    const neuralAudioReady =
      (payload.speech.status === "audio_stream" && payload.speech.stream_url) ||
      (payload.speech.status === "audio_data" && payload.speech.audio_base64);
    if (neuralAudioReady) {
      voiceBadge.textContent = "Neural voice ready";
      const status = await playNeuralSpeech(text, payload.speech);
      if (status !== "error") return;
    }
    voiceBadge.textContent = "Using offline voice";
    await playBrowserSpeech(text);
    return;
  }
  await playBrowserSpeech(text);
}

async function playBrowserSpeech(text) {
  if (!window.speechSynthesis) {
    voiceBadge.textContent = "Speech output unavailable";
    return;
  }
  const resumeWakePolling = backendWakePolling && alwaysListening && !backendCommandCaptureActive;
  if (resumeWakePolling) pauseBackendWakePolling();
  stopBrowserSpeech();
  const utterance = new SpeechSynthesisUtterance(text);
  utterance.rate = providerStatus?.speech_settings?.rate || 1.08;
  utterance.pitch = providerStatus?.speech_settings?.pitch || 1.0;
  if (crimsonMode.persona === "crimson") {
    utterance.rate *= 0.98;
    utterance.pitch *= 0.95;
  }
  utterance.volume = providerStatus?.speech_settings?.volume || 1.0;
  const voices = await getBrowserVoices();
  const preferred = selectBrowserVoice(voices, providerStatus?.speech_settings?.voice_preference);
  utterance.lang = preferred?.lang || "en-GB";
  if (preferred) {
    utterance.voice = preferred;
    ttsProviderDetail.textContent = preferred.name;
  }
  utterance.onstart = () => {
    armillaryCore.setSpeechText(text);
    voiceBadge.textContent = "Speaking";
    setVisualState("speaking");
    startBargeInMonitor();
  };
  return await new Promise((resolve) => {
    let finished = false;
    const finish = (status) => {
      if (finished) return;
      finished = true;
      stopBargeInMonitor();
      if (currentSpeechResolve === finish) currentSpeechResolve = null;
      armillaryCore.setSpeechText("");
      if (!bargeInHandling) {
        voiceBadge.textContent = micEnabled ? "Listening" : "Voice standby";
        setVisualState(micEnabled ? "listening" : "idle");
        if (resumeWakePolling && alwaysListening) startBackendWakePolling();
      }
      resolve(status);
    };
    currentSpeechResolve = finish;
    utterance.onend = () => finish("ended");
    utterance.onerror = () => finish("error");
    window.speechSynthesis.speak(utterance);
  });
}

async function playNeuralSpeech(text, speech) {
  const resumeWakePolling = backendWakePolling && alwaysListening && !backendCommandCaptureActive;
  if (resumeWakePolling) pauseBackendWakePolling();
  stopBrowserSpeech();
  let objectUrl = null;
  let source = String(speech.stream_url || "");
  if (!source) {
    try {
      const binary = window.atob(String(speech.audio_base64 || ""));
      const bytes = new Uint8Array(binary.length);
      for (let index = 0; index < binary.length; index += 1) bytes[index] = binary.charCodeAt(index);
      objectUrl = URL.createObjectURL(new Blob([bytes], { type: speech.mime_type || "audio/mpeg" }));
      source = objectUrl;
    } catch {
      if (resumeWakePolling && alwaysListening) startBackendWakePolling();
      return "error";
    }
  }
  if (!source.startsWith("/api/voice/audio/") && !objectUrl) {
    if (resumeWakePolling && alwaysListening) startBackendWakePolling();
    return "error";
  }
  const audio = new Audio(source);
  audio.preload = "auto";
  audio.playbackRate = crimsonMode.persona === "crimson" ? 0.98 : 1;
  audio.preservesPitch = true;
  audio.volume = Math.max(0, Math.min(1, Number(providerStatus?.speech_settings?.volume ?? 1)));
  currentSpeechAudio = audio;
  currentSpeechUrl = objectUrl;
  return await new Promise((resolve) => {
    let finished = false;
    const finish = (status) => {
      if (finished) return;
      finished = true;
      stopBargeInMonitor();
      if (currentSpeechResolve === finish) currentSpeechResolve = null;
      if (currentSpeechAudio === audio) currentSpeechAudio = null;
      if (objectUrl && currentSpeechUrl === objectUrl) currentSpeechUrl = null;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
      armillaryCore.setSpeechText("");
      if (!bargeInHandling) {
        voiceBadge.textContent = micEnabled ? "Listening" : "Voice standby";
        setVisualState(micEnabled ? "listening" : "idle");
        if (resumeWakePolling && alwaysListening) startBackendWakePolling();
      }
      resolve(status);
    };
    currentSpeechResolve = finish;
    audio.onplay = () => {
      armillaryCore.setSpeechText(text);
      voiceBadge.textContent = `Speaking via ${speech.model || "Aura-2"}`;
      setVisualState("speaking");
      startBargeInMonitor();
    };
    audio.onended = () => finish("ended");
    audio.onerror = () => finish("error");
    audio.play().catch(() => finish("error"));
  });
}

function startBackendWakePolling() {
  if (backendWakePolling || backendCommandCaptureActive) return;
  backendWakePolling = true;
  runBackendWakePoll();
}

function pauseBackendWakePolling() {
  backendWakePolling = false;
  if (backendWakeTimer) {
    window.clearTimeout(backendWakeTimer);
    backendWakeTimer = null;
  }
}

function stopBackendWakePolling() {
  pauseBackendWakePolling();
  backendWakeBusy = false;
  backendCommandCaptureActive = false;
}

function syncBackendWakePolling() {
  const shouldPoll = alwaysListening && !backendCommandCaptureActive && wakeProvider === "double_clap" && providerStatus?.active?.capture === "sounddevice";
  if (shouldPoll) {
    startBackendWakePolling();
  } else if (!alwaysListening) {
    stopBackendWakePolling();
  }
}

async function runBackendWakePoll() {
  if (!backendWakePolling || !alwaysListening || backendWakeBusy) return;
  backendWakeBusy = true;
  try {
    const payload = await postJson("/api/wake/process", { capture: true, seconds: 0.55, energy_only: true });
    applyVoiceStatus(payload.voice);
    applyWakeStatus(payload.wake);
    applyVoiceDiagnostics(payload.voice_diagnostics);
    renderHistory([...(payload.conversation_history || []), ...(payload.history || [])]);
    if (payload.status === "wake_detected") {
      const greeting = payload.spoken_response || payload.subtitle || "At your service, sir.";
      setSubtitle(greeting);
      setVisualState("listening");
      backendCommandCaptureActive = true;
      pauseBackendWakePolling();
      try {
        const commandCapture = captureBackendWakeCommand();
        await Promise.all([commandCapture, speakText(greeting)]);
      } finally {
        backendCommandCaptureActive = false;
        if (alwaysListening) backendWakePolling = true;
      }
    } else if (payload.command_executed) {
      const response = payload.spoken_response || payload.subtitle || payload.message || "Voice command processed.";
      setSubtitle(formatAssistantSubtitle(payload, response));
      await handleUiDirective(payload.ui_directive);
      if (payload.needs_confirmation || taskNeedsConfirmation(payload.task)) {
        showConfirmation(payload.task, { command: payload.voice?.pending_confirmation_goal || "", source: "voice" });
      } else {
        clearPendingConfirmation();
      }
      stopBackendWakePolling();
      await speakText(response);
      if (alwaysListening) startBackendWakePolling();
      scheduleListeningReturn({ keepListening: shouldContinueConversation(payload) });
    } else if (payload.status === "capture_unavailable") {
      setSubtitle(payload.message || "Backend microphone capture is unavailable.");
      stopBackendWakePolling();
    }
  } catch {
    setSubtitle("Double-clap wake polling could not reach the ULTRON runtime.");
  } finally {
    backendWakeBusy = false;
    if (backendWakePolling && alwaysListening) {
      backendWakeTimer = window.setTimeout(runBackendWakePoll, 90);
    }
  }
}

async function captureBackendWakeCommand(followUpDepth = 0) {
  if (!alwaysListening) return;
  const configuredSeconds = Number(providerStatus?.speech_settings?.capture_seconds || 6);
  const seconds = Math.max(2, Math.min(12, configuredSeconds));
  setSubtitle(followUpDepth ? "Listening for your response, sir." : "Listening. Speak your command, sir.");
  setVisualState("listening");
  voiceBadge.textContent = "Listening for command";

  const payload = await postJson("/api/wake/process", {
    capture: true,
    command_capture: true,
    seconds,
  });
  applyVoiceStatus(payload.voice);
  applyWakeStatus(payload.wake);
  applyVoiceDiagnostics(payload.voice_diagnostics);
  renderHistory([...(payload.conversation_history || []), ...(payload.history || [])]);

  if (payload.status === "capture_unavailable") {
    setSubtitle(payload.message || "Backend microphone capture is unavailable.");
    return;
  }
  if (payload.status === "no_command" || payload.status === "empty" || payload.status === "ignored") {
    setSubtitle(payload.message || "I did not hear a command. Double clap when you are ready, sir.");
    setVisualState("waiting_for_wake_word");
    return;
  }
  if (!payload.command_executed) {
    setSubtitle(payload.message || "I could not process that command. Double clap and try again, sir.");
    setVisualState("waiting_for_wake_word");
    return;
  }

  const response = payload.spoken_response || payload.subtitle || payload.message || "Voice command processed.";
  setSubtitle(formatAssistantSubtitle(payload, response));
  await handleUiDirective(payload.ui_directive);
  const needsConfirmation = payload.needs_confirmation || taskNeedsConfirmation(payload.task);
  if (needsConfirmation) {
    showConfirmation(payload.task, { command: payload.voice?.pending_confirmation_goal || "", source: "voice" });
  } else {
    clearPendingConfirmation();
  }
  setVisualState(needsConfirmation ? "listening" : "speaking");
  await speakText(response);

  if (!needsConfirmation && shouldContinueConversation(payload) && followUpDepth < 5 && alwaysListening) {
    await captureBackendWakeCommand(followUpDepth + 1);
    return;
  }
  setVisualState(alwaysListening ? "waiting_for_wake_word" : "idle");
}

async function getBrowserVoices() {
  if (browserVoiceCache.length) return browserVoiceCache;
  const immediate = window.speechSynthesis.getVoices();
  if (immediate.length) {
    browserVoiceCache = immediate;
    return browserVoiceCache;
  }
  if (browserVoicePromise) return await browserVoicePromise;
  browserVoicePromise = new Promise((resolve) => {
    let finished = false;
    const finish = () => {
      if (finished) return;
      finished = true;
      const voices = window.speechSynthesis.getVoices();
      if (voices.length) browserVoiceCache = voices;
      resolve(browserVoiceCache);
    };
    const timeout = window.setTimeout(finish, 250);
    window.speechSynthesis.addEventListener(
      "voiceschanged",
      () => {
        window.clearTimeout(timeout);
        finish();
      },
      { once: true }
    );
  });
  const voices = await browserVoicePromise;
  browserVoicePromise = null;
  return voices;
}

function warmBrowserVoiceCache() {
  if (!window.speechSynthesis) return;
  getBrowserVoices().catch(() => {});
}

function selectBrowserVoice(voices, preference = "") {
  if (!voices.length) return null;
  const english = voices.filter((voice) => String(voice.lang || "").toLowerCase().startsWith("en"));
  const candidates = english.length ? english : voices;
  const requested = String(preference || "").trim().toLowerCase();
  if (requested) {
    const configured = candidates.find((voice) => String(voice.name || "").toLowerCase().includes(requested));
    if (configured) return configured;
  }
  const score = (voice) => {
    const name = String(voice.name || "").toLowerCase();
    const lang = String(voice.lang || "").toLowerCase();
    let value = voice.localService ? 30 : 0;
    if (lang === "en-gb") value += 15;
    if (/george/.test(name)) value += 120;
    else if (/mark/.test(name)) value += 100;
    else if (/ravi/.test(name)) value += 90;
    else if (/andrew|ryan|guy/.test(name)) value += 75;
    else if (/aria|jenny|zira|hazel/.test(name)) value += 55;
    if (/natural|neural/.test(name)) value += 35;
    if (/online/.test(name)) value -= 20;
    if (/david/.test(name)) value -= 45;
    if (/desktop/.test(name)) value -= 10;
    return value;
  };
  return [...candidates].sort((left, right) => score(right) - score(left))[0] || null;
}

async function startBargeInMonitor() {
  if (!bargeInEnabled || bargeInHandling || voiceMuted || !navigator.mediaDevices?.getUserMedia || !window.AudioContext) return;
  stopBargeInMonitor();
  const monitor = { cancelled: false, stream: null, context: null, animation: null };
  bargeInMonitor = monitor;
  try {
    monitor.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 },
      video: false,
    });
    if (monitor.cancelled || bargeInMonitor !== monitor) {
      monitor.stream.getTracks().forEach((track) => track.stop());
      return;
    }
    monitor.context = new AudioContext();
    const source = monitor.context.createMediaStreamSource(monitor.stream);
    const analyser = monitor.context.createAnalyser();
    analyser.fftSize = 512;
    analyser.smoothingTimeConstant = 0.18;
    source.connect(analyser);
    const samples = new Uint8Array(analyser.fftSize);
    const startedAt = performance.now();
    let baseline = 0.008;
    let aboveSince = 0;

    const inspect = () => {
      if (monitor.cancelled || bargeInMonitor !== monitor || !speechPlaybackActive()) return;
      analyser.getByteTimeDomainData(samples);
      let energy = 0;
      for (const sample of samples) {
        const centered = (sample - 128) / 128;
        energy += centered * centered;
      }
      const rms = Math.sqrt(energy / samples.length);
      const elapsed = performance.now() - startedAt;
      if (elapsed < 650) {
        baseline = Math.max(0.006, baseline * 0.88 + rms * 0.12);
      } else {
        const threshold = Math.max(0.026, baseline * 2.45);
        if (rms >= threshold) {
          aboveSince = aboveSince || performance.now();
          if (performance.now() - aboveSince >= 150) {
            handleSpeechBargeIn();
            return;
          }
        } else {
          aboveSince = 0;
          baseline = Math.max(0.006, baseline * 0.995 + rms * 0.005);
        }
      }
      monitor.animation = window.requestAnimationFrame(inspect);
    };
    monitor.animation = window.requestAnimationFrame(inspect);
  } catch {
    stopBargeInMonitor();
  }
}

function stopBargeInMonitor() {
  const monitor = bargeInMonitor;
  bargeInMonitor = null;
  if (!monitor) return;
  monitor.cancelled = true;
  if (monitor.animation) window.cancelAnimationFrame(monitor.animation);
  if (monitor.stream) monitor.stream.getTracks().forEach((track) => track.stop());
  if (monitor.context && monitor.context.state !== "closed") monitor.context.close().catch(() => {});
}

async function handleSpeechBargeIn() {
  if (bargeInHandling) return;
  bargeInHandling = true;
  stopBrowserSpeech();
  postJson("/api/speak", { action: "stop" }).catch(() => {});
  setSubtitle("I stopped. Listening, sir.");
  setVisualState("listening");
  voiceBadge.textContent = "Interruption detected";
  if (providerStatus?.active?.capture === "sounddevice") {
    await captureBackendVoice({ fromBargeIn: true });
    return;
  }
  bargeInHandling = false;
  if (!recognitionActive) await startVoiceInput();
}

function stopBrowserSpeech() {
  armillaryCore.setSpeechText("");
  stopBargeInMonitor();
  if (currentSpeechAudio) {
    currentSpeechAudio.pause();
    currentSpeechAudio.removeAttribute("src");
    currentSpeechAudio.load();
    currentSpeechAudio = null;
  }
  if (currentSpeechUrl) {
    URL.revokeObjectURL(currentSpeechUrl);
    currentSpeechUrl = null;
  }
  if (window.speechSynthesis?.speaking || window.speechSynthesis?.pending) {
    window.speechSynthesis.cancel();
  }
  if (currentSpeechResolve) {
    const resolve = currentSpeechResolve;
    currentSpeechResolve = null;
    resolve("cancelled");
  }
}

function speechPlaybackActive() {
  const neuralPlaying = currentSpeechAudio && !currentSpeechAudio.paused && !currentSpeechAudio.ended;
  return Boolean(neuralPlaying || window.speechSynthesis?.speaking);
}

function scheduleListeningReturn(options = {}) {
  if (bargeInHandling) return;
  window.clearTimeout(returnTimer);
  const keepListening = Boolean(options.keepListening);
  returnTimer = window.setTimeout(() => {
    if (keepListening) {
      setVisualState("listening");
      voiceBadge.textContent = "Listening";
      return;
    }
    setVisualState(alwaysListening ? "waiting_for_wake_word" : micEnabled ? "listening" : "idle");
  }, keepListening ? 450 : 3200);
}

function setVisualState(state, options = {}) {
  if (!stateTargets[state]) state = "idle";
  visualState = state;
  armillaryCore.setState(state);
  document.body.classList.remove(
    "state-inactive",
    "state-idle",
    "state-waiting_for_wake_word",
    "state-listening",
    "state-transcribing",
    "state-thinking",
    "state-speaking"
  );
  document.body.classList.add(`state-${state}`);
  statusLabel.textContent = displayState(state);
  stateButtons.forEach((button) => button.classList.toggle("is-active", button.dataset.state === state));
  refreshCoreMicButton();
  if (options.sync !== false) {
    fetch("/api/state", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ state }),
    }).catch(() => {});
  }
}

function setDetailsCollapsed(collapsed) {
  detailsCollapsed = Boolean(collapsed);
  document.body.classList.toggle("details-collapsed", detailsCollapsed);
  updateCoreLayout();
  detailToggle.setAttribute("aria-pressed", String(detailsCollapsed));
  detailToggle.setAttribute("aria-label", detailsCollapsed ? "Show operations drawer" : "Hide operations drawer");
  detailToggle.title = detailsCollapsed ? "Show operations drawer" : "Hide operations drawer";
  window.localStorage.setItem("ultronDetailsCollapsed", String(detailsCollapsed));
}

function updateCoreLayout() {
  const compact = detailsCollapsed || window.innerWidth <= 980;
  armillaryCore.setLayoutMode(compact ? "compact" : "full");
}

function selectDrawerTab(tab) {
  const available = drawerTabs.some((button) => button.dataset.drawerTab === tab);
  activeDrawerTab = available ? tab : "activity";
  drawerTabs.forEach((button) => {
    const active = button.dataset.drawerTab === activeDrawerTab;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
    button.tabIndex = active ? 0 : -1;
  });
  drawerPanels.forEach((panel) => {
    const active = panel.dataset.drawerPanel === activeDrawerTab;
    panel.classList.toggle("is-active", active);
    panel.hidden = panel.dataset.drawerPanel === "activity" ? false : !active;
  });
  window.localStorage.setItem("ultronDrawerTab", activeDrawerTab);
}

function setButtonLabel(button, text) {
  const label = button?.querySelector("[data-button-label]");
  if (label) {
    label.textContent = text;
  } else if (button) {
    button.textContent = text;
  }
}

function setSubtitle(text) {
  subtitleText.textContent = text;
}

function updateSubtitles() {
  subtitlePanel.classList.toggle("is-hidden", !subtitlesEnabled);
  setButtonLabel(subtitleToggle, subtitlesEnabled ? "On" : "Off");
  subtitleToggle.setAttribute("aria-pressed", String(subtitlesEnabled));
}

function applyVoiceStatus(status) {
  if (!status) return;
  micEnabled = Boolean(status.microphone_enabled);
  voiceMuted = Boolean(status.muted);
  pushToTalk = Boolean(status.push_to_talk);
  setButtonLabel(micToggle, micEnabled ? "Stop Mic" : "Start Mic");
  micStatusLabel.textContent = micEnabled ? "On" : "Off";
  micPrivacyDetail.textContent = alwaysListening
    ? "Always-listening enabled"
    : micEnabled
      ? pushToTalk
        ? "Listening for one command"
        : "Continuous listening until stopped"
      : SpeechRecognition
        ? "Microphone stopped"
        : "Speech recognition unavailable";
  setButtonLabel(muteToggle, voiceMuted ? "Muted" : "Mute Off");
  muteToggle.setAttribute("aria-pressed", String(voiceMuted));
  setButtonLabel(pushToTalkToggle, pushToTalk ? "Push-to-talk" : "Continuous");
  pushToTalkToggle.setAttribute("aria-pressed", String(pushToTalk));
  confirmVoiceButton.hidden = !status.pending_confirmation_goal;
  voiceBadge.textContent = status.listening
    ? SpeechRecognition ? "Listening" : "Speech API unavailable"
    : status.speaking
      ? `Speaking via ${displayProviderName(status.tts_provider)}`
      : "Voice standby";
  if (!providerStatus) {
    sttProviderLabel.textContent = status.stt_provider || "text_payload";
    ttsProviderLabel.textContent = status.tts_provider || "browser_speech_synthesis";
  }
  refreshCoreMicButton();
}

function applyVoiceDiagnostics(diagnostics) {
  if (!diagnostics) return;
  const transcript = diagnostics.last_transcript || "None";
  lastTranscriptLabel.textContent = transcript.length > 42 ? `${transcript.slice(0, 39)}...` : transcript;
  const confidence = Number(diagnostics.confidence || 0);
  const confidenceText = diagnostics.status === "clarification_required" || (confidence > 0 && confidence < 0.45)
    ? `Low confidence: ${Math.round(confidence * 100)}%`
    : confidence > 0
      ? `Confidence: ${Math.round(confidence * 100)}%`
      : "Confidence pending";
  confidenceDetail.textContent = confidenceText;
  audioStateLabel.textContent = diagnostics.rejected ? "Rejected" : displayState(diagnostics.status || "idle");
  const duration = Number(diagnostics.audio_duration_ms || 0);
  const speech = Number(diagnostics.speech_duration_ms || 0);
  const energy = Number(diagnostics.audio_energy || 0);
  audioDetail.textContent = diagnostics.detail || `${duration} ms audio, ${speech} ms speech, energy ${energy.toFixed(3)}`;
}

function applyWakeStatus(wake) {
  if (!wake) return;
  alwaysListening = Boolean(wake.always_listening);
  wakeProvider = wake.wake_provider || wakeProvider;
  setButtonLabel(alwaysListeningToggle, alwaysListening ? "Always On" : "Always Off");
  alwaysListeningToggle.setAttribute("aria-pressed", String(alwaysListening));
  micStatusLabel.textContent = alwaysListening || micEnabled ? "On" : "Off";
  micPrivacyDetail.textContent = alwaysListening ? "Always-listening enabled" : "Push-to-talk available";
  wakeStateLabel.textContent = displayState(wake.mode || "inactive");
  wakeDetail.textContent = wake.last_event || `Wake phrases: ${(wake.wake_phrases || ["ULTRON", "Hey ULTRON"]).join(", ")}`;
  if (wake.noisy_ignored) {
    vadStateLabel.textContent = "Ignored";
    vadDetail.textContent = wake.last_event || "Noisy or empty input ignored";
  } else if (wake.voice_detected) {
    vadStateLabel.textContent = "Voice detected";
    vadDetail.textContent = wake.wake_word_detected ? `Wake: ${wake.last_wake_phrase || "detected"}` : "Waiting for wake phrase";
  } else {
    vadStateLabel.textContent = "Idle";
    vadDetail.textContent = alwaysListening ? "Monitoring for speech gate events" : "Always-listening disabled";
  }
  if (alwaysListening && (visualState === "idle" || visualState === "inactive")) {
    setVisualState(wake.mode || "waiting_for_wake_word", { sync: false });
  }
  syncBackendWakePolling();
}

function applyProviders(payload) {
  if (!payload) return;
  if (payload.speech_settings) {
    armillaryCore.setVoiceProfile(payload.speech_settings);
  }
  const activeStt = payload.active?.stt || payload.voice?.stt_provider || "text_payload";
  const activeTts = payload.active?.tts || payload.voice?.tts_provider || "browser_speech_synthesis";
  const activeCapture = payload.active?.capture || payload.voice_diagnostics?.capture_provider || "browser";
  const configuredStt = payload.configured?.stt || activeStt;
  const configuredTts = payload.configured?.tts || activeTts;
  const configuredCapture = payload.configured?.capture || activeCapture;
  const sttHealth = payload.providers?.stt;
  const ttsHealth = payload.providers?.tts;
  const captureHealth = payload.providers?.capture;
  sttProviderLabel.textContent = activeStt;
  ttsProviderLabel.textContent = activeTts;
  captureProviderLabel.textContent = activeCapture;
  sttProviderDetail.textContent = providerDetail(configuredStt, activeStt, sttHealth);
  ttsProviderDetail.textContent = providerDetail(configuredTts, activeTts, ttsHealth);
  captureProviderDetail.textContent = providerDetail(configuredCapture, activeCapture, captureHealth);
  applyVoiceDiagnostics(payload.voice_diagnostics);
  refreshCoreMicButton();
  syncBackendWakePolling();
}

function refreshCoreMicButton() {
  if (!coreMicButton) return;
  const active = micEnabled || recognitionActive || alwaysListening || visualState === "listening" || visualState === "transcribing";
  coreMicButton.classList.toggle("is-hot", active);
  coreMicButton.setAttribute("aria-pressed", String(active));
  coreMicButton.setAttribute("aria-label", active ? "Mute microphone" : "Unmute microphone");
  coreMicButton.title = active ? "Mute microphone" : "Unmute microphone";
}

function providerDetail(configured, active, health) {
  const fallback = configured !== active ? `Fallback from ${configured}` : "Active";
  if (!health) return fallback;
  const state = health.available ? fallback : `Unavailable: ${health.detail}`;
  return health.fallback_to ? `${state}; using ${health.fallback_to}` : state;
}

function displayState(state) {
  if (state === "inactive") return "Shutdown";
  if (state === "waiting_for_wake_word") return "Standby";
  return String(state || "idle")
    .replace(/_/g, " ")
    .replace(/\b\w/g, (char) => char.toUpperCase());
}

function renderHistory(items) {
  voiceHistory.innerHTML = "";
  const recent = [...items].slice(-6).reverse();
  if (!recent.length) {
    const empty = document.createElement("li");
    empty.textContent = "No conversation yet.";
    voiceHistory.append(empty);
    return;
  }
  for (const item of recent) {
    const li = document.createElement("li");
    if (item.user_said !== undefined) {
      const tool = item.tool_selected ? `Tool: ${item.tool_selected}` : "No tool selected";
      li.innerHTML = `<strong>You said</strong>: ${escapeHtml(item.user_said)}<br><strong>Understood</strong>: ${escapeHtml(item.ultron_understood)}<br><strong>ULTRON</strong>: ${escapeHtml(item.spoken_response)}<br><span>${escapeHtml(tool)}</span>`;
    } else {
      const route = item.route ? `Route: ${item.route}` : "Route: conversation";
      li.innerHTML = `<strong>You</strong>: ${escapeHtml(item.user_input)}<br><strong>Understood</strong>: ${escapeHtml(item.understood)}<br><strong>ULTRON</strong>: ${escapeHtml(item.response)}<br><span>${escapeHtml(route)}</span>`;
    }
    voiceHistory.append(li);
  }
}

function renderSkills(skills) {
  skillsList.innerHTML = "";
  if (!skills.length) {
    appendListItem(skillsList, "No skills loaded.");
    return;
  }
  for (const skill of skills) {
    const li = document.createElement("li");
    const name = document.createElement("strong");
    name.textContent = skill.name;
    const detail = document.createElement("span");
    detail.textContent = ` ${skill.risk_level}: ${skill.description}`;
    li.append(name, detail);
    skillsList.append(li);
  }
}

function renderKnowledgePanel({ memory = [], sources = [], matches = [], error = "", memoryEnabled: enabled = memoryEnabled }) {
  knowledgeList.innerHTML = "";
  memoryEnabled = Boolean(enabled);
  setButtonLabel(memoryToggle, memoryEnabled ? "Memory On" : "Memory Off");
  memoryToggle.setAttribute("aria-pressed", String(memoryEnabled));
  if (error) {
    appendListItem(knowledgeList, error);
    return;
  }
  appendListItem(knowledgeList, `Memory: ${memoryEnabled ? "on" : "off"}`);
  if (matches.length) {
    for (const match of matches) {
      appendListItem(knowledgeList, `${match.title}: ${match.snippet}`);
    }
    return;
  }
  if (sources.length) {
    for (const source of sources.slice(-4).reverse()) {
      appendListItem(knowledgeList, `${source.title} (${source.chunk_count} chunks)`);
    }
  }
  if (memory.length) {
    for (const item of memory.slice(-3).reverse()) {
      appendListItem(knowledgeList, `${item.key}: ${item.value}`);
    }
  }
  if (!sources.length && !memory.length) {
    appendListItem(knowledgeList, "No memory or knowledge sources yet.");
  }
}

function renderRecentTasks(items) {
  recentTasksList.innerHTML = "";
  const recent = [...items].slice(-5).reverse();
  if (!recent.length) {
    appendListItem(recentTasksList, "No recent tasks yet.");
    return;
  }
  for (const task of recent) {
    appendListItem(recentTasksList, `${task.status}: ${task.summary || task.goal || "Task updated"}`);
  }
}

function appendListItem(list, text) {
  const li = document.createElement("li");
  li.textContent = text;
  list.append(li);
}

function buildTaskSubtitle(task) {
  if (!task) return "";
  if (task.summary) return task.summary;
  return `Task ${task.status || "updated"}.`;
}

function formatAssistantSubtitle(payload, fallback) {
  const text = payload?.spoken_response || payload?.subtitle || payload?.response || payload?.message || fallback || "";
  return String(text || "Ready.").replace(/^(?:ULTRON:\s*)+/i, "").trim();
}

function taskNeedsConfirmation(task) {
  if (!task) return false;
  if (task.status === "waiting_for_confirmation") return true;
  return Boolean((task.steps || []).some((step) => step.status === "waiting_for_confirmation"));
}

function displayProviderName(provider) {
  const names = {
    browser_speech_synthesis: "browser voice",
    deepgram: "Deepgram",
    sounddevice: "system microphone",
    pyttsx3: "Windows voice",
    piper: "Piper",
  };
  return names[provider] || String(provider || "voice").replace(/_/g, " ");
}

function shouldContinueConversation(payload) {
  if (!payload) return false;
  if (payload.continue_listening) return true;
  if (payload.route === "chat") return true;
  const task = payload.task;
  return Boolean((task?.steps || []).some((step) => step?.tool_call?.name === "assistant_reply"));
}

function showConfirmation(task, context) {
  const step = firstPendingStep(task);
  const policy = step?.policy || {};
  const tool = step?.tool_call?.name || "unknown";
  pendingConfirmation = { ...context, task };
  confirmationTitle.textContent = "Review before execution";
  confirmationMessage.textContent = task?.summary || policy.reason || "ULTRON paused before running this action.";
  confirmationTool.textContent = tool;
  confirmationPermission.textContent = policy.permission_level || policy.risk_level || "confirmation_required";
  confirmationModal.hidden = false;
}

function firstPendingStep(task) {
  return (task?.steps || []).find((step) => step.status === "waiting_for_confirmation") || task?.steps?.[0] || null;
}

async function approvePendingConfirmation() {
  if (!pendingConfirmation) return;
  const { command, source } = pendingConfirmation;
  confirmationModal.hidden = true;
  if (source === "voice") {
    await handleVoiceTranscript("yes confirm");
    return;
  }
  await sendCommand({ command, confirmed: true });
}

async function cancelPendingConfirmation() {
  clearPendingConfirmation();
  confirmVoiceButton.hidden = true;
  await postJson("/api/confirmation/cancel", {}).catch(() => {});
  setSubtitle("Action cancelled.");
  setVisualState(alwaysListening ? "waiting_for_wake_word" : micEnabled ? "listening" : "idle");
}

function clearPendingConfirmation() {
  pendingConfirmation = null;
  confirmationModal.hidden = true;
}

async function fetchJson(url) {
  const response = await fetch(url);
  return response.json();
}

async function postJson(url, payload) {
  payload = { ...payload, persona: crimsonMode.persona };
  return coreActivity.run(url, async () => {
    const response = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const result = await response.json();
    if (!response.ok) throw new Error(result.message || "ULTRON request failed.");
    return result;
  }, payload);
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[char]);
}

function animate() {
  const elapsed = clock.getElapsedTime();
  crimsonMode.update(elapsed);
  const target = stateTargets[visualState];
  const pulse = 1 + Math.sin(elapsed * (visualState === "listening" ? 2.0 : 3.8)) * 0.018;
  const sphereScale = target.scale * pulse;

  root.scale.lerp(new THREE.Vector3(sphereScale, sphereScale, sphereScale), 0.08);
  root.rotation.y += 0.002 + target.ring * 0.004;
  root.rotation.x = Math.sin(elapsed * 0.35) * 0.035;
  sphere.rotation.y -= 0.002;
  sphereUniforms.time.value = elapsed;
  sphereUniforms.intensity.value += (target.glow - sphereUniforms.intensity.value) * 0.08;
  glow.material.opacity += (0.42 + target.glow * 0.22 - glow.material.opacity) * 0.08;
  glow.scale.setScalar(2.75 + target.glow * 0.38 + Math.sin(elapsed * 2.2) * 0.04);

  plasmaLines.children.forEach((line, i) => {
    line.material.opacity += (target.line * (0.36 + (i % 5) * 0.08) - line.material.opacity) * 0.08;
    line.rotation.z += (visualState === "speaking" ? 0.006 : 0.002) * (i % 2 ? 1 : -1);
  });

  ringGroup.children.forEach((ring, i) => {
    ring.material.opacity += ((visualState === "thinking" ? 0.72 : target.ring * 0.24) - ring.material.opacity) * 0.08;
    ring.rotation.z += (0.006 + i * 0.0015) * (visualState === "thinking" ? 2.8 : 0.7);
    ring.rotation.x += 0.0015 * (i % 2 ? 1 : -1);
  });

  particles.rotation.y += target.particle * 0.003;
  particles.rotation.x = Math.sin(elapsed * 0.11) * 0.07;
  particles.material.opacity += ((visualState === "speaking" ? 0.75 : 0.42) - particles.material.opacity) * 0.04;

  armillaryCore.update(elapsed, visualState);
  renderer.render(scene, camera);
  requestAnimationFrame(animate);
}

function makeArc(seed) {
  const points = [];
  const radius = 1.055 + (seed % 4) * 0.006;
  const basePhi = 0.38 + (((seed * 37) % 180) / 180) * Math.PI * 0.72;
  const baseTheta = (((seed * 53) % 360) / 360) * Math.PI * 2;
  const length = 0.7 + (((seed * 29) % 100) / 100) * 1.6;
  for (let i = 0; i < 42; i += 1) {
    const t = i / 41;
    const wobble = Math.sin(t * Math.PI * 4 + seed) * 0.06;
    const phi = Math.max(0.18, Math.min(Math.PI - 0.18, basePhi + Math.sin(t * Math.PI * 2 + seed) * 0.22));
    const theta = baseTheta + t * length + wobble;
    points.push(new THREE.Vector3().setFromSpherical(new THREE.Spherical(radius, phi, theta)));
  }
  const material = new THREE.LineBasicMaterial({
    color: seed % 3 === 0 ? 0xa6ff3f : 0x00ff66,
    transparent: true,
    opacity: 0.35,
    blending: THREE.AdditiveBlending,
    depthWrite: false,
  });
  return new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), material);
}

function makeParticles() {
  const count = 780;
  const positions = new Float32Array(count * 3);
  for (let i = 0; i < count; i += 1) {
    const radius = 3.5 + Math.random() * 8.5;
    const theta = Math.random() * Math.PI * 2;
    const phi = Math.acos(2 * Math.random() - 1);
    positions[i * 3] = Math.sin(phi) * Math.cos(theta) * radius;
    positions[i * 3 + 1] = Math.sin(phi) * Math.sin(theta) * radius * 0.72;
    positions[i * 3 + 2] = Math.cos(phi) * radius - 2.2;
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3));
  return new THREE.Points(
    geometry,
    new THREE.PointsMaterial({
      color: 0x00ff66,
      size: 0.025,
      transparent: true,
      opacity: 0.42,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    })
  );
}

function makeGlowTexture() {
  const size = 256;
  const glowCanvas = document.createElement("canvas");
  glowCanvas.width = size;
  glowCanvas.height = size;
  const ctx = glowCanvas.getContext("2d");
  const gradient = ctx.createRadialGradient(size / 2, size / 2, 8, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, "rgba(0,255,102,0.78)");
  gradient.addColorStop(0.34, "rgba(0,255,102,0.26)");
  gradient.addColorStop(0.68, "rgba(0,255,102,0.07)");
  gradient.addColorStop(1, "rgba(0,0,0,0)");
  ctx.fillStyle = gradient;
  ctx.fillRect(0, 0, size, size);
  return new THREE.CanvasTexture(glowCanvas);
}

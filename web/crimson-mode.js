const clamp = (value) => Math.max(0, Math.min(1, value));
const smooth = (value) => { const t = clamp(value); return t * t * (3 - 2 * t); };

// Delta-driven so hidden windows cannot skip the cinematic or trigger an event.
export function createCrimsonTimeline({ random = Math.random } = {}) {
  let phase = "standard", age = 0, level = 0, restoreFrom = 0, automatic = false;
  let countdown = 420 + random() * 300;
  const schedule = () => { countdown = 420 + random() * 300; };
  return {
    enter(auto = false) { if (phase !== "standard") return; phase = "ignition"; age = 0; automatic = auto; },
    restore() { if (phase === "standard" || phase === "restoring") return; restoreFrom = level; phase = "restoring"; age = 0; schedule(); },
    tick(dt, { reduced = false, hidden = false, eligible = false, enabled = true } = {}) {
      if (!hidden) {
        const delta = Math.max(0, Math.min(dt, 0.1));
        age += delta;
        if (phase === "standard" && enabled && !reduced && eligible) {
          countdown -= delta;
          if (countdown <= 0) this.enter(true);
        }
        if (phase === "ignition") {
          level = clamp(age / (reduced ? 0.8 : 12));
          if (level === 1) { phase = "crimson"; age = 0; }
        } else if (phase === "crimson" && automatic && age >= 90) this.restore();
        else if (phase === "restoring") {
          level = restoreFrom * (1 - smooth(age / (reduced ? 0.6 : 4)));
          if (level === 0) { phase = "standard"; age = 0; }
        }
      }
      const glitch = !reduced && phase === "ignition"
        ? Math.exp(-(((age - 0.6) / 0.19) ** 2)) + 0.65 * Math.exp(-(((age - 1.65) / 0.24) ** 2)) : 0;
      return {
        phase, level, glitch,
        core: smooth(level / 0.34),
        shell: smooth((level - 0.14) / 0.5),
        spread: reduced ? smooth(level) : smooth((level - 0.28) / 0.72),
        persona: level >= 0.3 && phase !== "restoring" ? "crimson" : "standard",
      };
    },
  };
}

export function createCrimsonMode(core, { eligible = () => false } = {}) {
  const timeline = createCrimsonTimeline();
  const motion = matchMedia("(prefers-reduced-motion: reduce)");
  const toggle = document.getElementById("crimsonToggle");
  const setting = document.getElementById("crimsonAutomatic");
  const status = document.getElementById("crimsonStatus");
  const field = document.createElement("div");
  field.className = "crimson-field";
  field.setAttribute("aria-hidden", "true");
  document.getElementById("ultron-scene").before(field);
  const fracture = document.createElement("div");
  fracture.className = "crimson-fracture";
  fracture.setAttribute("aria-hidden", "true");
  document.body.append(fracture);
  let enabled = true;
  try { enabled = localStorage.getItem("ultronCrimsonAutomatic") !== "false"; } catch { /* Storage can be disabled in a webview. */ }
  if (setting) setting.checked = enabled;
  let state = timeline.tick(0), previous = null, surfaces = [], refresh = 0, disposed = false, renderedLevel = -1;
  const onToggle = () => state.phase === "standard" ? timeline.enter() : timeline.restore();
  const onEscape = (event) => { if (event.key === "Escape") timeline.restore(); };
  const onSetting = () => {
    enabled = setting.checked;
    try { localStorage.setItem("ultronCrimsonAutomatic", String(enabled)); } catch { /* Optional preference only. */ }
    if (!enabled) timeline.restore();
  };
  toggle?.addEventListener("click", onToggle);
  setting?.addEventListener("change", onSetting);
  window.addEventListener("keydown", onEscape);
  const selector = ".topbar,.operations-drawer,.mic-dock,.detail-toggle,.crimson-toggle,.subtitles,.command-row,.app-window,.interface-grid,.scanline,.hand-guide-dialog";
  return {
    get persona() { return state.persona; },
    update(time) {
      if (disposed) return;
      const dt = previous === null ? 0 : Math.min(Math.max(time - previous, 0), 0.1);
      previous = time;
      state = timeline.tick(dt, { reduced: motion.matches, hidden: document.hidden, eligible: eligible(), enabled });
      core.setCinematic(state);
      document.body.dataset.cinematic = state.phase;
      document.body.dataset.persona = state.persona;
      const active = state.phase !== "standard";
      const label = active ? "Return to standard mode" : "Activate Crimson mode";
      if (toggle?.getAttribute("aria-label") !== label) {
        toggle?.setAttribute("aria-label", label);
        toggle?.setAttribute("title", active ? "Return to standard mode (Escape)" : "Activate Crimson mode");
        toggle?.setAttribute("aria-pressed", String(active));
      }
      const statusText = { standard: "Standard", ignition: "Crimson / awakening", crimson: "Crimson", restoring: "Restoring" }[state.phase];
      if (status && status.textContent !== statusText) status.textContent = statusText;
      if (state.phase === "standard" && renderedLevel === 0) return;
      renderedLevel = state.level;
      refresh -= dt;
      if (refresh <= 0) {
        surfaces = [...document.querySelectorAll(selector)].map((element) => {
          element.classList.add("crimson-surface");
          return { element, rect: element.getBoundingClientRect() };
        });
        refresh = 0.25;
      }
      const center = core.getScreenCenter();
      const reach = Math.hypot(Math.max(center.x, innerWidth - center.x), Math.max(center.y, innerHeight - center.y)) + 180;
      const radius = state.spread * reach;
      field.style.clipPath = motion.matches ? "none" : `circle(${radius.toFixed(1)}px at ${center.x.toFixed(1)}px ${center.y.toFixed(1)}px)`;
      field.style.opacity = String(motion.matches ? state.spread : Math.min(1, state.spread * 5));
      fracture.style.setProperty("--fracture", state.glitch.toFixed(3));
      for (const { element, rect } of surfaces) {
        const distance = Math.hypot(rect.x + rect.width / 2 - center.x, rect.y + rect.height / 2 - center.y);
        const mix = motion.matches ? state.spread : state.spread === 0 ? 0 : smooth((radius - distance) / 180);
        element.style.setProperty("--crimson-local", `${(mix * 100).toFixed(1)}%`);
        element.dataset.tinted = mix > 0 ? "true" : "false";
      }
    },
    dispose() {
      disposed = true;
      toggle?.removeEventListener("click", onToggle);
      setting?.removeEventListener("change", onSetting);
      window.removeEventListener("keydown", onEscape);
      for (const { element } of surfaces) { element.classList.remove("crimson-surface"); element.style.removeProperty("--crimson-local"); delete element.dataset.tinted; }
      field.remove(); fracture.remove();
      delete document.body.dataset.cinematic; delete document.body.dataset.persona;
      core.setCinematic({});
    },
  };
}

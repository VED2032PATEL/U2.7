const TERMINAL = new Set(["completed", "simulated", "cancelled"]);
const READ_ONLY = new Set(["calculate", "get_system_status", "search_files", "research_topic", "read_clipboard"]);

export function createAgentWorkspace({ onOpen, activity } = {}) {
  const byId = (id) => document.getElementById(id);
  const panel = byId("agentPanel");
  let selected = "";
  let snapshot = null;
  let busy = false;
  let revision = 0;
  let rendered = "";
  let disposed = false;
  let refreshPending = false;

  function feedback(message, error = false) {
    byId("agentFeedback").textContent = message;
    byId("agentFeedback").classList.toggle("is-error", error);
  }

  async function request(url, body) {
    const operation = async () => {
      const response = await fetch(url, body ? {
        method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
      } : { cache: "no-store" });
      const payload = await response.json();
      if (!response.ok || payload.status === "error") throw new Error(payload.message || "Task service unavailable.");
      return payload;
    };
    return activity ? activity.run(url, operation) : operation();
  }

  async function mutate(url, body, success = "") {
    if (busy) return;
    busy = true;
    revision += 1;
    byId("agentPlanButton").disabled = true;
    feedback(url.endsWith("/plan") ? "Preparing your plan..." : "Updating task...");
    try {
      const payload = await request(url, body);
      if (payload.selected) selected = payload.selected.id;
      snapshot = payload;
      render();
      feedback(success);
    } catch (error) {
      feedback(error.message || "Could not update the task.", true);
    } finally {
      busy = false;
      byId("agentPlanButton").disabled = false;
    }
  }

  async function refresh() {
    if (refreshPending || busy || disposed) return;
    refreshPending = true;
    const currentRevision = revision;
    try {
      const payload = await request(`/api/agent${selected ? `?id=${encodeURIComponent(selected)}` : ""}`);
      if (currentRevision !== revision) return;
      snapshot = payload;
      if (!selected && payload.tasks.length) selected = payload.tasks[0].id;
      render();
    } catch (error) {
      feedback(error.message || "Agent tasks are offline.", true);
    } finally {
      refreshPending = false;
    }
  }

  function taskButton(icon, label, action, parent, className = "") {
    const button = element("button", "", className);
    button.type = "button";
    button.title = label;
    button.setAttribute("aria-label", label);
    const symbol = document.createElement("i");
    symbol.dataset.lucide = icon;
    symbol.setAttribute("aria-hidden", "true");
    button.append(symbol, element("span", label));
    button.addEventListener("click", action);
    parent.append(button);
    return button;
  }

  function render() {
    if (!snapshot) return;
    activity?.observeAgent(snapshot);
    const signature = JSON.stringify({ selected, snapshot });
    if (signature === rendered) return;
    rendered = signature;
    byId("agentMode").textContent = snapshot.dry_run ? "Simulation" : "Live actions";
    byId("agentMode").dataset.state = snapshot.dry_run ? "simulated" : "completed";
    const task = snapshot.selected?.id === selected ? snapshot.selected : snapshot.tasks.find((item) => item.id === selected);
    byId("agentDetail").hidden = !task;
    if (task) renderTask(task);
    const history = byId("agentHistory");
    history.replaceChildren();
    for (const item of snapshot.tasks) {
      const row = element("li");
      const button = element("button", "", "agent-history-button");
      button.type = "button";
      button.setAttribute("aria-pressed", String(item.id === selected));
      button.append(element("span", item.goal), element("small", label(item.status), "agent-badge"));
      button.addEventListener("click", () => { selected = item.id; revision += 1; render(); void refresh(); });
      row.append(button);
      history.append(row);
    }
    if (!snapshot.tasks.length) history.append(element("li", "No agent tasks yet.", "agent-empty"));
    const routines = byId("agentRoutines");
    routines.replaceChildren();
    for (const routine of snapshot.routines) {
      const row = element("li", "", "agent-routine-row");
      row.append(element("span", routine.name));
      taskButton("list-tree", `Plan ${routine.name}`, () => mutate("/api/agent/routines/plan", { id: routine.id }), row, "agent-icon-action");
      taskButton("trash-2", `Remove ${routine.name}`, () => mutate("/api/agent/routines/delete", { id: routine.id }, "Routine removed."), row, "agent-icon-action");
      routines.append(row);
    }
    if (!snapshot.routines.length) routines.append(element("li", "No saved routines.", "agent-empty"));
    window.lucide?.createIcons({ attrs: { "aria-hidden": "true" } });
  }

  function renderTask(task) {
    byId("agentTitle").textContent = task.goal;
    byId("agentStatus").textContent = label(task.status);
    byId("agentStatus").dataset.state = task.status;
    byId("agentProgress").max = task.steps.length;
    byId("agentProgress").value = task.steps.filter((step) => ["completed", "simulated"].includes(step.status)).length;
    byId("agentSummary").textContent = task.summary;
    const actions = byId("agentActions");
    actions.replaceChildren();
    const control = (action) => mutate("/api/agent/control", { id: task.id, action });
    const next = task.steps.find((step) => !["completed", "simulated"].includes(step.status));
    if (task.status === "planned") taskButton("play", task.dry_run ? "Simulate plan" : "Run plan", () => control("start"), actions);
    if (task.status === "paused") taskButton("play", "Resume", () => control("resume"), actions);
    if (["failed", "interrupted"].includes(task.status) && next && READ_ONLY.has(next.tool)) taskButton("rotate-cw", "Retry current step", () => control("resume"), actions);
    if (task.status === "waiting_for_confirmation") taskButton("check", "Approve step", () => control("approve"), actions);
    if (task.status === "running") taskButton("pause", "Pause", () => control("pause"), actions);
    if (!TERMINAL.has(task.status)) taskButton("square", "Cancel", () => control("cancel"), actions);
    const steps = byId("agentSteps");
    const openSteps = new Set([...steps.querySelectorAll("details[open]")].map((item) => item.dataset.step));
    steps.replaceChildren();
    task.steps.forEach((step, index) => {
      const row = element("li", "", "agent-step");
      row.dataset.state = step.status;
      const detail = element("details");
      detail.dataset.step = `${task.id}:${step.id}`;
      detail.open = openSteps.has(detail.dataset.step) || ["running", "waiting_for_confirmation", "failed", "interrupted"].includes(step.status);
      const summary = element("summary");
      summary.append(element("span", String(index + 1), "agent-step-number"), element("strong", step.title), element("small", label(step.status)));
      detail.append(summary);
      const body = element("div", "", "agent-step-detail");
      body.append(element("p", step.tool.replaceAll("_", " "), "agent-tool-name"));
      body.append(element("pre", JSON.stringify(step.resolved_arguments || step.arguments, null, 2), "agent-arguments"));
      if (step.policy.action === "confirm") body.append(element("p", step.policy.reason, "agent-policy"));
      if (step.verification) body.append(element("p", `${label(step.verification.status)}: ${step.verification.message}`, "agent-verification"));
      if (step.result) body.append(element("pre", step.output || step.result.message || "", "agent-result"));
      const path = step.result?.changed?.path || step.result?.data?.path;
      if (path) body.append(element("p", path, "agent-artifact"));
      if (step.attempts) body.append(element("small", `Attempts: ${step.attempts}`));
      detail.append(body);
      row.append(detail);
      steps.append(row);
    });
    const events = byId("agentEvents");
    events.replaceChildren();
    for (const event of task.events.slice(-16)) {
      const row = element("li");
      row.append(element("time", new Date(event.at * 1000).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })), element("span", event.message));
      events.append(row);
    }
  }

  byId("agentGoalForm").addEventListener("submit", (event) => {
    event.preventDefault();
    void mutate("/api/agent/plan", { goal: byId("agentGoal").value.trim() });
  });
  byId("agentExamples").addEventListener("change", (event) => {
    if (event.target.value) byId("agentGoal").value = event.target.value;
    event.target.value = "";
  });
  byId("agentRoutineForm").addEventListener("submit", (event) => {
    event.preventDefault();
    if (selected) void mutate("/api/agent/routines/save", { id: selected, name: byId("agentRoutineName").value.trim() }, "Routine saved.");
  });
  async function poll() {
    if (disposed) return;
    if (!document.hidden && (!panel.hidden || snapshot?.active_id)) await refresh();
    if (!disposed) window.setTimeout(poll, 1200);
  }
  window.addEventListener("beforeunload", () => { disposed = true; });
  void refresh();
  void poll();
  return {
    async open(id) {
      selected = id || selected;
      revision += 1;
      onOpen?.();
      await refresh();
    },
  };
}

function element(tag, text = "", className = "") {
  const node = document.createElement(tag);
  if (text) node.textContent = text;
  if (className) node.className = className;
  return node;
}

function label(value) {
  return String(value || "").replaceAll("_", " ").replace(/^./, (char) => char.toUpperCase());
}

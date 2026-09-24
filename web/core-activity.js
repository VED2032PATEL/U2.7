const BUSY = new Set(["running", "pausing", "cancelling", "executing"]);
const FAILED = new Set(["failed", "error", "blocked", "interrupted"]);

export function activityForTask(task) {
  if (!task) return null;
  const steps = task.steps || [];
  const progress = steps.length ? steps.filter((step) => ["completed", "simulated"].includes(step.status)).length / steps.length : undefined;
  if (FAILED.has(task.status)) return { kind: "error", progress };
  if (task.status === "waiting_for_confirmation") return { kind: "confirmation", progress };
  if (["paused", "cancelled", "simulated"].includes(task.status)) return { kind: "paused", progress };
  // Legacy task status may say completed even when all its tools were dry runs.
  if (task.status === "completed") return { kind: steps.some((step) => step.result?.status === "dry_run") ? "paused" : "success", progress };
  if (!BUSY.has(task.status)) return null;
  const step = steps.find((item) => ["running", "pending", "executing"].includes(item.status));
  const tool = step?.tool || step?.tool_call?.name || "";
  return { kind: kindForTool(tool), progress };
}

function kindForTool(tool) {
  if (/research|search_web|browse|internet/.test(tool)) return "research";
  if (/camera|model|screenshot|vision/.test(tool)) return "vision";
  if (/music|spotify|youtube|media|song/.test(tool)) return "media";
  if (tool === "assistant_reply") return "thinking";
  return "executing";
}

function requestKind(url, request) {
  if (url === "/api/command") {
    const command = String(request.command || "").trim();
    if (/^(?:research|gather (?:info|information)|search (?:the )?(?:web|internet)|look up)\b/i.test(command)) return "research";
    if (/\b(?:camera|3d model|scan object)\b/i.test(command)) return "vision";
    if (/^(?:play|pause|resume)\b.*\b(?:song|music|spotify|youtube|video)\b/i.test(command)) return "media";
    if (/^(?:open|launch|create|save|send|write|set|move|rename)\b/i.test(command)) return "executing";
  }
  if (/^\/api\/(?:research|knowledge\/search)/.test(url)) return "research";
  if (/^\/api\/(?:camera|model)/.test(url)) return "vision";
  if (/^\/api\/(?:command|voice\/(?:transcribe|capture|wake-command|wake-transcribe)|agent\/(?:plan|routines\/plan))$/.test(url)) return "thinking";
  if (/^\/api\/(?:skills\/run|agent\/control)$/.test(url)) return "executing";
  return null;
}

export function createCoreActivityController(core) {
  let sequence = 0, background = null, agentSignature = null;
  const pending = new Map();
  const showPending = () => {
    const current = [...pending.values()].at(-1);
    if (current) core.setActivity({ kind: current });
    else if (background) core.setActivity(background);
    return Boolean(current || background);
  };
  return {
    async run(url, operation, request = {}) {
      if (url === "/api/confirmation/cancel") {
        const payload = await operation();
        if (!showPending()) core.setActivity({ kind: "paused" }, 1800);
        return payload;
      }
      const kind = url === "/api/wake/process" && request.command_capture ? "listening" : requestKind(url, request);
      if (!kind) return operation();
      const ticket = ++sequence;
      pending.set(ticket, kind);
      showPending();
      try {
        const payload = await operation();
        pending.delete(ticket);
        if (!showPending()) {
          const failure = FAILED.has(payload?.status) || ["not_found", "unavailable", "capture_unavailable", "clarification_required"].includes(payload?.status);
          const result = failure ? { kind: "error" } : activityForTask(payload?.task);
          // A planned task is not an executed action; do not show success for it.
          if (result) core.setActivity(result, result.kind === "confirmation" ? 0 : 2600);
          else if (["success", "saved"].includes(payload?.status)) core.setActivity({ kind: "success" }, 1800);
          else core.setActivity(null);
        }
        return payload;
      } catch (error) {
        pending.delete(ticket);
        if (!showPending()) core.setActivity({ kind: "error" }, 4000);
        throw error;
      }
    },
    observeAgent(snapshot) {
      const tasks = snapshot?.tasks || [];
      const live = tasks.find((task) => task.id === snapshot.active_id) || tasks.find((task) => task.status === "waiting_for_confirmation");
      const latest = live || tasks[0];
      const signature = latest ? JSON.stringify([latest.id, latest.updated_at, latest.status]) : "empty";
      if (signature === agentSignature) return;
      const firstSnapshot = agentSignature === null;
      agentSignature = signature;
      background = live ? activityForTask(live) : null;
      if (!showPending() && !firstSnapshot && latest) {
        const activity = activityForTask(latest);
        if (activity) core.setActivity(activity, 2600);
        else core.setActivity(null);
      }
    },
    clear() { pending.clear(); background = null; core.setActivity(null); },
  };
}

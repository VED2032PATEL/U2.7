# Agent Tasks

Agent Tasks adds a durable plan-observe-execute loop to the existing ULTRON runtime. It is available in the Operations Tasks tab and from `/agent <goal>` in the command input.

## What changes

A task is planned once into typed tools and reviewed before execution. The worker executes those exact calls, saves each outcome, and resolves dependencies from prior results. It does not ask the model to reinterpret the user's command at each step.

Local planning supports explicit `then` sequences, research-to-note, and clipboard-to-note. Groq can produce more general plans using the available tool schemas; malformed plans, unknown tools, missing arguments, forward references, and plans over 12 steps are rejected before execution. Unsupported goals ask for more detail instead of guessing.

The plan is fixed after review. This release supports bounded retries of transient read failures, not autonomous strategy changes or unrestricted computer operation.

## State and recovery

The SQLite file at `<workspace>/.ultron/missions.sqlite3` stores tasks and routines. Each snapshot is committed before starting a tool and again after saving its result. A process restart cannot silently turn an interrupted side effect into a second action.

States: planned, running, pausing, paused, waiting_for_confirmation, completed, simulated, failed, interrupted, cancelling, cancelled. Only one task worker runs in an application instance. Normal tool execution also shares the runtime lock to avoid overlapping desktop actions.

Pausing or cancelling waits for the current synchronous adapter to return. It cannot undo a sent message, stop a tool halfway through, or reverse completed steps. Closing the desktop asks the worker to pause; an unfinished call is recovered as interrupted on the next launch. Do not run two ULTRON server processes against the same workspace database.

Each confirmation authorizes one waiting step. It does not approve later risky steps. Failed or interrupted writes cannot be retried automatically or through Resume; inspect the outcome, then create a goal for the remaining work. Read operations can retry once automatically for transient failures, and can be retried explicitly afterward.

## Data flow and evidence

Text arguments `content`, `text`, and `message` may contain `{{step_1.output}}` references to earlier steps. References are rejected in recipients, file paths, application names, and other control arguments. Outputs are substituted as data only; they are never parsed again as commands. Oversized output is rejected before the dependent action.

Research gathers up to five web sources. Groq synthesizes those source notes with an instruction to treat them as untrusted evidence. The saved note includes source links. If cloud synthesis is unavailable, the result is explicitly labeled as excerpts. Search-engine snippets are limited evidence and do not establish that every assertion on a linked page is verified.

Verification labels distinguish an artifact checked on disk, a tool-reported outcome, and a simulation. Note verification checks the file contents; folder verification checks existence. Other tool outcomes are not advertised as independently verified.

## HTTP interface

All POST requests use JSON and must come from the same origin as ULTRON. Services without an Origin header can call the loopback API directly. There is no new remote authentication service; keep the server bound to loopback.

| Endpoint | Purpose |
| --- | --- |
| `GET /api/agent?id=<task-id>` | Recent tasks, routines, active task, selected task |
| `POST /api/agent/plan` | `{"goal":"..."}` creates a preview |
| `POST /api/agent/control` | `{"id":"...","action":"start"}`; also resume, approve, pause, cancel |
| `POST /api/agent/routines/save` | `{"id":"task-id","name":"..."}` saves reviewed instructions |
| `POST /api/agent/routines/plan` | `{"id":"routine-id"}` makes a new task preview |
| `POST /api/agent/routines/delete` | `{"id":"routine-id"}` removes a saved routine |

SQLite parameters protect record lookups. Tool names and arguments still pass through ULTRON's registry, validation, policy, and executor. Agent Tasks does not add arbitrary shell execution. Records, snippets, and note content stay in the ignored local `.ultron`/`notes` directories; optional Groq planning/synthesis transmits the goal or web source notes needed for that request.

## Verification

```powershell
python -m unittest discover -s tests -p test_missions.py
python -m unittest discover -s tests
node scripts/agent_ui_smoke.cjs
```

The browser test needs `playwright` and `pngjs` resolvable by Node. It uses Edge when installed, or Playwright's Chromium. Set `ULTRON_TEST_PYTHON` and `ULTRON_BROWSER_EXECUTABLE` to override its executables. Its temporary workspace and desktop/mobile screenshots are saved under `.ultron/agent-ui-smoke`. It runs real note creation only in that isolated test workspace.

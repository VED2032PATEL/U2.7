/* Run with Playwright + pngjs installed and ULTRON_TEST_PYTHON pointing to Python. */
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { spawn } = require("node:child_process");
const { chromium } = require("playwright");
const { expect } = require("playwright/test");
const { PNG } = require("pngjs");

async function main() {
  const out = path.resolve(".ultron/agent-ui-smoke");
  fs.mkdirSync(out, { recursive: true });
  const workspace = fs.mkdtempSync(path.join(out, "workspace-"));
  const python = process.env.ULTRON_TEST_PYTHON || path.resolve(".venv/Scripts/python.exe");
  const source = `
import sys
sys.path.insert(0, 'src')
from pathlib import Path
from http.server import ThreadingHTTPServer
from ultron27.brain import UltronBrain
from ultron27.config import UltronConfig
from ultron27.runtime import UltronAssistant, RuntimeSettings
from ultron27.web_server import WebState, make_handler
workspace = Path(sys.argv[1])
config = UltronConfig(workspace=workspace, safe_roots=(workspace,), dry_run=False)
state = WebState(UltronBrain(UltronAssistant(RuntimeSettings.from_config(config, write_audit=False))), startup_briefing_enabled=False)
server = ThreadingHTTPServer(('127.0.0.1', 0), make_handler(state))
print(server.server_address[1], flush=True)
server.serve_forever()
`;
  const child = spawn(python, ["-u", "-c", source, workspace], { cwd: path.resolve("."), stdio: ["ignore", "pipe", "pipe"], windowsHide: true });
  let browser;
  try {
    const port = await new Promise((resolve, reject) => {
      let output = "", errors = "";
      const timeout = setTimeout(() => reject(new Error(`Preview startup timed out: ${errors}`)), 15000);
      child.stderr.on("data", (data) => { errors += data; });
      child.stdout.on("data", (data) => {
        output += data;
        if (/^\d+\s/.test(output)) { clearTimeout(timeout); resolve(Number(output.trim())); }
      });
      child.once("error", (error) => { clearTimeout(timeout); reject(error); });
      child.once("exit", (code) => { clearTimeout(timeout); reject(new Error(`Preview exited ${code}: ${errors}`)); });
    });
    const edge = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
    const executablePath = process.env.ULTRON_BROWSER_EXECUTABLE || (fs.existsSync(edge) ? edge : undefined);
    browser = await chromium.launch({ headless: true, executablePath });
    const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.addInitScript(() => {
      localStorage.setItem("ultronDetailsCollapsed", "false");
      localStorage.setItem("ultronDrawerTab", "agent");
    });
    await page.goto(`http://127.0.0.1:${port}`, { waitUntil: "networkidle" });
    await expect(page.locator("body")).toHaveClass(/app-ready/, { timeout: 15000 });
    await page.getByRole("tab", { name: "Tasks", exact: true }).click();
    await page.getByLabel("Goal", { exact: true }).fill("create note first then create note second");
    await page.getByRole("button", { name: "Plan task", exact: true }).click();
    await expect(page.locator("#agentStatus")).toHaveText("Planned");
    await expect(page.locator(".agent-step")).toHaveCount(2);
    assert.equal(fs.existsSync(path.join(workspace, "notes", "first.md")), false);
    await page.getByRole("button", { name: "Run plan", exact: true }).click();
    await expect(page.locator("#agentStatus")).toHaveText("Completed", { timeout: 10000 });
    await expect(page.locator("#ultron-scene")).toHaveAttribute("data-core-activity", "success");
    assert.ok(fs.existsSync(path.join(workspace, "notes", "first.md")));
    assert.ok(fs.existsSync(path.join(workspace, "notes", "second.md")));
    await page.locator(".agent-step summary").first().click();
    await expect(page.locator(".agent-verification").first()).toContainText("Verified");
    await page.screenshot({ path: path.join(out, "desktop.png") });
    await page.getByLabel("Routine name", { exact: true }).fill("Daily notes");
    await page.getByRole("button", { name: "Save routine", exact: true }).click();
    await expect(page.locator("#agentRoutines")).toContainText("Daily notes");
    await page.getByRole("button", { name: "Plan Daily notes", exact: true }).click();
    await expect(page.locator("#agentStatus")).toHaveText("Planned");
    await page.getByRole("button", { name: "Cancel", exact: true }).click();
    await expect(page.locator("#agentStatus")).toHaveText("Cancelled");
    await page.setViewportSize({ width: 390, height: 844 });
    await page.getByLabel("Task examples").selectOption({ label: "Research brief" });
    await page.getByRole("button", { name: "Plan task", exact: true }).click();
    await expect(page.locator("#agentStatus")).toHaveText("Planned");
    await expect(page.locator(".agent-step")).toHaveCount(2);
    await page.screenshot({ path: path.join(out, "mobile.png") });
    const overflow = await page.evaluate(() => {
      const panel = document.querySelector("#agentPanel");
      return { page: document.documentElement.scrollWidth > innerWidth, panel: panel.scrollWidth > panel.clientWidth + 1 };
    });
    assert.deepEqual(overflow, { page: false, panel: false });
    const canvas = page.locator("#ultron-scene");
    const before = await canvas.screenshot();
    await page.waitForTimeout(300);
    const after = await canvas.screenshot();
    const pixels = PNG.sync.read(after).data;
    let bright = 0;
    for (let i = 0; i < pixels.length; i += 4) if (Math.max(pixels[i], pixels[i + 1], pixels[i + 2]) > 65) bright++;
    assert.ok(bright > 100, "Core canvas should render");
    assert.notDeepEqual(before, after, "Core canvas should animate");
    await page.setViewportSize({ width: 1440, height: 960 });
    await page.getByRole("button", { name: "Hide operations drawer", exact: true }).click();
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(out, "core-focus-desktop.png") });
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(out, "core-focus-mobile.png") });
    await page.setViewportSize({ width: 1440, height: 960 });
    await page.getByRole("button", { name: "Show operations drawer", exact: true }).click();
    let releaseResearch;
    const researchGate = new Promise((resolve) => { releaseResearch = resolve; });
    await page.route("**/api/command", async (route) => {
      await researchGate;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ status: "error", message: "Test service unavailable" }) });
    });
    await page.locator("#commandInput").fill("research optical sensors");
    await page.locator("#commandInput").press("Enter");
    try {
      await expect(canvas).toHaveAttribute("data-core-activity", "research");
    } finally {
      releaseResearch();
    }
    await expect(canvas).toHaveAttribute("data-core-activity", "error");
    await page.unroute("**/api/command");
    await page.getByRole("button", { name: "Activate Crimson mode", exact: true }).click();
    await page.waitForTimeout(2500);
    await expect(page.locator("body")).toHaveAttribute("data-cinematic", "ignition");
    assert.equal(await page.locator(".operations-drawer").getAttribute("data-tinted"), "false", "Core ignites before the drawer changes");
    await page.screenshot({ path: path.join(out, "crimson-ignition.png") });
    await page.waitForTimeout(4200);
    await page.screenshot({ path: path.join(out, "crimson-spread.png") });
    await expect(page.locator("body")).toHaveAttribute("data-cinematic", "crimson", { timeout: 20000 });
    await expect(page.locator("body")).toHaveAttribute("data-persona", "crimson");
    assert.equal(await page.locator(".operations-drawer").getAttribute("data-tinted"), "true");
    await page.screenshot({ path: path.join(out, "crimson-desktop.png") });
    let sentPersona;
    await page.route("**/api/command", async (route) => {
      sentPersona = route.request().postDataJSON().persona;
      await route.fulfill({ status: 503, contentType: "application/json", body: JSON.stringify({ message: "Test service unavailable" }) });
    });
    await page.locator("#commandInput").fill("hi");
    await page.locator("#commandInput").press("Enter");
    await expect(canvas).toHaveAttribute("data-core-activity", "error");
    assert.equal(sentPersona, "crimson");
    await page.setViewportSize({ width: 390, height: 844 });
    await page.waitForTimeout(800);
    await page.screenshot({ path: path.join(out, "crimson-mobile.png") });
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth > innerWidth), false);
    await page.getByRole("button", { name: "Hide operations drawer", exact: true }).click();
    await page.waitForTimeout(500);
    await page.screenshot({ path: path.join(out, "crimson-focus-mobile.png") });
    await page.keyboard.press("Escape");
    await expect(page.locator("body")).toHaveAttribute("data-persona", "standard");
    await expect(page.locator("body")).toHaveAttribute("data-cinematic", "standard", { timeout: 10000 });
    await page.getByRole("button", { name: "Activate Crimson mode", exact: true }).click();
    await page.waitForTimeout(700);
    await page.keyboard.press("Escape");
    await expect(page.locator("body")).toHaveAttribute("data-cinematic", "standard", { timeout: 10000 });
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.getByRole("button", { name: "Activate Crimson mode", exact: true }).click();
    await expect(page.locator("body")).toHaveAttribute("data-cinematic", "crimson");
    assert.equal(await page.locator(".crimson-fracture").evaluate((el) => getComputedStyle(el).display), "none");
    await page.getByRole("button", { name: "Return to standard mode", exact: true }).click();
    await expect(page.locator("body")).toHaveAttribute("data-cinematic", "standard");
    await page.getByRole("button", { name: "Show operations drawer", exact: true }).click();
    await page.getByRole("tab", { name: "System", exact: true }).click();
    await page.getByLabel("Cinematic events", { exact: true }).uncheck();
    assert.equal(await page.evaluate(() => localStorage.getItem("ultronCrimsonAutomatic")), "false");
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ status: "ok", checks: ["preview without actions", "real two-step execution", "verified artifacts", "routine replay preview", "cancel", "mobile plan", "no overflow", "animated canvas", "task success reaction", "research and failure reactions", "focus layout", "core-first Crimson spread", "request persona", "mid-transition restore", "Crimson mobile", "reduced motion", "automatic preference", "no JS errors"], screenshots: out, brightPixels: bright }, null, 2));
  } finally {
    if (browser) await browser.close();
    child.kill();
    if (child.exitCode === null) await new Promise((resolve) => child.once("exit", resolve));
  }
}

main().catch((error) => { console.error(error); process.exitCode = 1; });

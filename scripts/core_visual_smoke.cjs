const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const http = require("node:http");
const { chromium } = require("playwright");
const { PNG } = require("pngjs");

async function main() {
  const root = path.resolve(process.env.ULTRON_CORE_WEB_ROOT || "web");
  const out = path.resolve(".ultron/core-visual-smoke", process.env.ULTRON_CORE_WEB_ROOT ? "desktop-package" : "source");
  fs.mkdirSync(out, { recursive: true });
  const activity = await import(`data:text/javascript;base64,${fs.readFileSync(path.join(root, "core-activity.js")).toString("base64")}`);
  const { activityForTask, createCoreActivityController } = activity;
  assert.equal(activityForTask({ status: "failed" }).kind, "error");
  assert.equal(activityForTask({ status: "waiting_for_confirmation" }).kind, "confirmation");
  assert.equal(activityForTask({ status: "planned" }), null);
  assert.equal(activityForTask({ status: "completed", steps: [{ result: { status: "dry_run" } }] }).kind, "paused");
  assert.equal(activityForTask({ status: "running", steps: [{ status: "completed" }, { status: "running", tool: "research_topic" }] }).progress, 0.5);
  for (const [tool, kind] of [["research_topic", "research"], ["take_screenshot", "vision"], ["play_music", "media"], ["create_note", "executing"]]) {
    assert.equal(activityForTask({ status: "running", steps: [{ status: "running", tool }] }).kind, kind);
  }
  const signals = [];
  const controller = createCoreActivityController({ setActivity: (value) => signals.push(value) });
  await assert.rejects(controller.run("/api/command", async () => { throw new Error("offline"); }));
  assert.equal(signals.at(-1).kind, "error");
  await controller.run("/api/command", async () => ({ task: { status: "completed" } }));
  assert.equal(signals.at(-1).kind, "success");
  await controller.run("/api/confirmation/cancel", async () => ({ status: "ok" }));
  assert.equal(signals.at(-1).kind, "paused");
  const before = signals.length;
  controller.observeAgent({ tasks: [{ id: "old", status: "completed", updated_at: 1 }] });
  assert.equal(signals.length, before, "Historical completed tasks must not flash success on load");

  const html = `<!doctype html><html><head><meta name="viewport" content="width=device-width,initial-scale=1"><style>html,body{margin:0;background:#06090b;overflow:hidden}canvas{position:fixed;inset:0;width:100vw;height:100vh}</style></head><body><canvas id="ultron-scene"></canvas><script type="module">
  import * as THREE from '/vendor/three.module.min.js';
  import {createArmillaryCore} from '/ultron-core.js';
  const renderer=new THREE.WebGLRenderer({canvas:document.querySelector('canvas'),antialias:true,alpha:true});
  renderer.setPixelRatio(1);renderer.setSize(innerWidth,innerHeight);
  const camera=new THREE.PerspectiveCamera(44,innerWidth/innerHeight,0.1,100),scene=new THREE.Scene();
  const core=createArmillaryCore({scene,camera,renderer});
  let state='idle';const clock=new THREE.Clock();
  function frame(){core.update(clock.getElapsedTime(),state);renderer.render(scene,camera);requestAnimationFrame(frame)}frame();
  addEventListener('resize',()=>{renderer.setSize(innerWidth,innerHeight);camera.aspect=innerWidth/innerHeight;camera.updateProjectionMatrix();core.setLayoutMode('compact')});
  window.harness={core,renderer,scene,setState(value){state=value;core.setState(value);core.setActivity(null);if(value==='speaking')core.setSpeechText('At your service, sir. Your research is ready.')}};
  </script></body></html>`;
  const server = http.createServer((req, res) => {
    const pathname = new URL(req.url, "http://localhost").pathname;
    if (pathname === "/") { res.setHeader("Content-Type", "text/html"); res.end(html); return; }
    if (pathname === "/favicon.ico") { res.writeHead(204); res.end(); return; }
    const file = path.resolve(root, `.${decodeURIComponent(pathname)}`);
    const relative = path.relative(root, file);
    if (relative.startsWith("..") || path.isAbsolute(relative) || !fs.existsSync(file) || !fs.statSync(file).isFile()) { res.writeHead(404); res.end(); return; }
    res.setHeader("Content-Type", file.endsWith(".js") ? "text/javascript" : "application/octet-stream");
    fs.createReadStream(file).pipe(res);
  });
  await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
  let browser;
  try {
    const edge = "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe";
    browser = await chromium.launch({ headless: true, executablePath: process.env.ULTRON_BROWSER_EXECUTABLE || (fs.existsSync(edge) ? edge : undefined) });
    const page = await browser.newPage({ viewport: { width: 1440, height: 960 } });
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    page.on("console", (message) => { if (message.type() === "error") errors.push(message.text()); });
    await page.goto(`http://127.0.0.1:${server.address().port}`);
    await page.waitForFunction(() => window.harness);
    const metrics = {};
    for (const state of ["idle", "listening", "thinking", "speaking", "waiting_for_wake_word", "inactive"]) {
      await page.evaluate((state) => window.harness.setState(state), state);
      await page.waitForTimeout(800);
      metrics[state] = await capture(page, out, state);
      assert.equal(await page.locator("canvas").getAttribute("data-core-activity"), state);
    }
    await page.evaluate(() => window.harness.setState("idle"));
    for (const kind of ["research", "vision", "media", "executing", "confirmation", "success", "error", "paused"]) {
      await page.evaluate((kind) => window.harness.core.setActivity({ kind, progress: kind === "executing" ? 0.5 : undefined }), kind);
      await page.waitForTimeout(600);
      metrics[kind] = await capture(page, out, kind);
      assert.equal(await page.locator("canvas").getAttribute("data-core-activity"), kind);
    }
    await page.evaluate(() => window.harness.setState("idle"));
    await page.waitForTimeout(1000);
    const frameA = await page.locator("canvas").screenshot();
    await page.waitForTimeout(300);
    const frameB = await page.locator("canvas").screenshot();
    assert.ok(difference(frameA, frameB) > 100, "Core must animate");
    await page.mouse.move(1430, 900);
    await page.waitForTimeout(600);
    assert.ok(difference(frameB, await page.locator("canvas").screenshot()) > 100, "Pointer parallax must render");
    await page.evaluate(() => { window.harness.core.startBoot(); window.harness.core.setBootProgress(0); });
    await page.waitForTimeout(50);
    const bootStart = await page.locator("canvas").screenshot();
    await page.evaluate(() => { window.harness.core.setBootProgress(1); window.harness.core.finishBoot(); });
    await page.waitForTimeout(600);
    assert.ok(difference(bootStart, await page.locator("canvas").screenshot()) > 1000, "Boot must reveal the assembly");
    for (const [width, height] of [[390, 844], [800, 600], [1920, 1080]]) {
      await page.setViewportSize({ width, height });
      await page.waitForTimeout(800);
      metrics[`${width}x${height}`] = await capture(page, out, `${width}x${height}`);
    }
    await page.emulateMedia({ reducedMotion: "reduce" });
    await page.evaluate(() => window.harness.core.setCinematic({ core: 1, shell: 1 }));
    await page.waitForTimeout(100);
    metrics.crimson = await capture(page, out, "crimson");
    const redPixels = PNG.sync.read(await page.locator("canvas").screenshot()).data;
    let redCount = 0;
    for (let i = 0; i < redPixels.length; i += 4) if (redPixels[i] > 65 && redPixels[i] > redPixels[i + 1] * 1.4) redCount++;
    assert.ok(redCount > 3000, "Crimson must visibly change the rendered core");
    await page.waitForTimeout(2500);
    const still = await page.locator("canvas").screenshot();
    await page.waitForTimeout(500);
    assert.ok(difference(still, await page.locator("canvas").screenshot()) < 25, "Reduced motion should settle to a still core");
    const renderStats = await page.evaluate(() => ({ calls: window.harness.renderer.info.render.calls, triangles: window.harness.renderer.info.render.triangles }));
    assert.ok(renderStats.calls < 220, `Unexpected draw-call count: ${renderStats.calls}`);
    await page.evaluate(() => window.harness.core.dispose());
    assert.equal(await page.evaluate(() => window.harness.scene.children.length), 0);
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ status: "ok", metrics, renderStats, screenshots: out, errors }, null, 2));
  } finally {
    if (browser) await browser.close();
    await new Promise((resolve) => server.close(resolve));
  }
}

async function capture(page, out, name) {
  const buffer = await page.locator("canvas").screenshot({ path: path.join(out, `${name}.png`) });
  const png = PNG.sync.read(buffer);
  let bright = 0, minX = png.width, maxX = 0, minY = png.height, maxY = 0;
  for (let y = 0; y < png.height; y++) for (let x = 0; x < png.width; x++) {
    const i = (y * png.width + x) * 4;
    if (Math.max(png.data[i], png.data[i + 1], png.data[i + 2]) > 60) {
      bright++; minX = Math.min(minX, x); maxX = Math.max(maxX, x); minY = Math.min(minY, y); maxY = Math.max(maxY, y);
    }
  }
  assert.ok(bright > 1000, `${name}: blank core`);
  assert.ok(minX > 5 && maxX < png.width - 5 && minY > 5 && maxY < png.height - 5, `${name}: clipped core`);
  return { bright, bounds: [minX, minY, maxX, maxY] };
}
function difference(a, b) {
  const left = PNG.sync.read(a).data, right = PNG.sync.read(b).data;
  let changed = 0;
  for (let i = 0; i < left.length; i += 4) if (Math.abs(left[i] - right[i]) + Math.abs(left[i + 1] - right[i + 1]) + Math.abs(left[i + 2] - right[i + 2]) > 20) changed++;
  return changed;
}
main().catch((error) => { console.error(error); process.exitCode = 1; });

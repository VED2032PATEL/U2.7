const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

async function main() {
  const { createCrimsonTimeline } = await import(`data:text/javascript;base64,${fs.readFileSync(path.resolve("web/crimson-mode.js")).toString("base64")}`);
  const create = () => createCrimsonTimeline({ random: () => 0 });
  const advance = (timeline, seconds, flags = {}) => {
    let value;
    for (let i = 0; i < Math.ceil(seconds * 60); i++) value = timeline.tick(1 / 60, flags);
    return value;
  };
  let timeline = create();
  timeline.enter();
  let value = advance(timeline, 2);
  assert.ok(value.core > 0.4 && value.spread === 0, "Core must ignite before the UI");
  value = advance(timeline, 11);
  assert.equal(value.phase, "crimson");
  assert.equal(value.persona, "crimson");
  assert.equal(value.spread, 1);
  assert.equal(advance(timeline, 120).phase, "crimson", "Manual mode stays on");
  timeline.restore();
  assert.equal(timeline.tick(0).persona, "standard", "Restoring immediately stops the persona");
  assert.equal(advance(timeline, 5).phase, "standard");
  timeline.enter();
  advance(timeline, 2);
  timeline.restore();
  assert.equal(advance(timeline, 5).level, 0, "Cancel mid-ignition fully restores");
  timeline = create();
  assert.equal(advance(timeline, 800, { eligible: false }).phase, "standard");
  assert.equal(advance(timeline, 800, { eligible: true, hidden: true }).phase, "standard");
  assert.equal(advance(timeline, 800, { eligible: true, reduced: true }).phase, "standard");
  assert.equal(advance(timeline, 800, { eligible: true, enabled: false }).phase, "standard");
  assert.equal(advance(timeline, 433, { eligible: true }).phase, "crimson");
  assert.equal(advance(timeline, 96).phase, "standard", "Automatic mode expires");
  timeline.enter();
  value = advance(timeline, 1, { reduced: true });
  assert.equal(value.glitch, 0);
  assert.equal(value.phase, "crimson");
  console.log("Crimson timeline: ignition order, auto scheduling, restore, visibility and reduced motion passed.");
}
main().catch((error) => { console.error(error); process.exitCode = 1; });

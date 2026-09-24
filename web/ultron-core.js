import * as THREE from "./vendor/three.module.min.js";

const TAU = Math.PI * 2;
const STATES = {
  inactive: { color: 0x66828c, energy: 0.08, speed: 0.03, aperture: 0.82 },
  idle: { color: 0x68f0c5, energy: 0.58, speed: 0.22, aperture: 1 },
  waiting_for_wake_word: { color: 0x72a9b7, energy: 0.3, speed: 0.1, aperture: 0.94 },
  listening: { color: 0x69dcff, energy: 0.95, speed: 0.32, aperture: 1.08 },
  transcribing: { color: 0x91e9ff, energy: 1.1, speed: 0.74, aperture: 1.04 },
  thinking: { color: 0xffcb83, energy: 1.2, speed: 1.1, aperture: 1 },
  speaking: { color: 0x80ffd2, energy: 1.05, speed: 0.55, aperture: 1.06 },
  research: { color: 0x80ccff, energy: 1, speed: 0.8, aperture: 1.04 },
  vision: { color: 0x97e6ff, energy: 0.9, speed: 0.3, aperture: 1.12 },
  media: { color: 0xb6f8cf, energy: 1, speed: 0.48, aperture: 1.03 },
  executing: { color: 0x94ffe2, energy: 1.15, speed: 0.9, aperture: 1 },
  confirmation: { color: 0xffca75, energy: 0.7, speed: 0.05, aperture: 0.95 },
  paused: { color: 0x819baa, energy: 0.3, speed: 0, aperture: 0.9 },
  success: { color: 0x9effd4, energy: 1.35, speed: 0.25, aperture: 1.1 },
  error: { color: 0xff7c72, energy: 0.72, speed: 0, aperture: 0.84 },
};

// Preserve the factory API used by older packaged desktop frontends.
export function createArmillaryCore({ scene, camera, renderer }) {
  camera.position.set(0, 0, 10);
  camera.lookAt(0, 0, 0);
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.toneMappingExposure = 1.2;
  renderer.domElement.dataset.coreDesign = "aperture-v2";
  const root = new THREE.Group(), assembly = new THREE.Group();
  root.add(assembly);
  scene.add(root);
  const materials = {
    titanium: new THREE.MeshStandardMaterial({ color: 0x38505b, metalness: 0.65, roughness: 0.3 }),
    graphite: new THREE.MeshStandardMaterial({ color: 0x101c24, metalness: 0.55, roughness: 0.37 }),
    silver: new THREE.MeshStandardMaterial({ color: 0x6a848e, metalness: 0.6, roughness: 0.29 }),
    mint: glow(0x72f3c8, 0.95), ice: glow(0x9de4fa, 0.8), amber: glow(0xf5bd74, 0.9),
    edge: new THREE.LineBasicMaterial({ color: 0x88a5ae, transparent: true, opacity: 0.22 }),
  };
  const lights = new THREE.Group();
  lights.add(new THREE.HemisphereLight(0xc6e9f4, 0x16352e, 2.8));
  for (const [color, intensity, x, y, z] of [[0xd7f6ff, 5, -3, 4, 5], [0x5dffba, 3, 4, -2, 3], [0xffd8a0, 2, 1, 3, -1]]) {
    const light = new THREE.DirectionalLight(color, intensity);
    light.position.set(x, y, z);
    lights.add(light);
  }
  scene.add(lights);
  const housing = new THREE.Group(), halo = new THREE.Group(), iris = new THREE.Group();
  assembly.add(housing, halo, iris);

  // Bevelled radial plates form a physical housing around the optical center.
  for (let i = 0; i < 18; i++) {
    const start = i * TAU / 18;
    sector(housing, 1.53, 1.86, start, TAU / 18 - 0.075, 0.14, -0.18, materials.titanium, materials.edge);
    arc(housing, 1.77, start + 0.04, 0.14, 0.012, 0.015, i % 6 === 0 ? materials.amber : materials.mint);
    sector(housing, 1.40, 1.48, start + 0.03, 0.16, 0.035, 0.07, materials.graphite);
  }
  arc(housing, 1.5, 0, TAU, 0.017, 0.015, materials.ice);
  arc(housing, 1.9, 0, TAU, 0.009, -0.2, materials.ice);
  housing.add(ticks(1.97, 144, 0.02, 0.10, materials.edge));
  const gimbal = new THREE.Group();
  gimbal.rotation.set(0.3, -0.24, 0);
  halo.add(gimbal);
  for (let i = 0; i < 3; i++) {
    const start = i * TAU / 3 + 0.16;
    sector(gimbal, 2.16, 2.25, start, 1.6, 0.06, -0.25, materials.graphite, materials.edge);
    arc(gimbal, 2.25, start + 0.03, 1.46, 0.012, -0.14, i === 1 ? materials.amber : materials.ice);
    arc(gimbal, 2.31, start + 0.13, 0.47, 0.007, -0.14, materials.mint);
  }
  const indexRing = ticks(2.4, 96, 0.015, 0.06, new THREE.LineBasicMaterial({ color: 0x63818b, transparent: true, opacity: 0.4 }));
  indexRing.position.z = -0.36;
  halo.add(indexRing);
  const blades = [];
  for (let i = 0; i < 12; i++) {
    const pivot = new THREE.Group(), start = i * TAU / 12, shape = new THREE.Shape();
    [[0.81, start + 0.29], [1.34, start + 0.08], [1.37, start + 0.45], [0.9, start + 0.62]].forEach(([r, a], n) => shape[n ? "lineTo" : "moveTo"](Math.cos(a) * r, Math.sin(a) * r));
    shape.closePath();
    const geometry = new THREE.ExtrudeGeometry(shape, { depth: 0.055, bevelEnabled: true, bevelSize: 0.025, bevelThickness: 0.018, bevelSegments: 2, steps: 1 });
    const plate = new THREE.Mesh(geometry, i % 3 === 0 ? materials.silver : materials.graphite);
    plate.position.z = 0.2 + i % 2 * 0.035;
    pivot.add(plate);
    const edge = new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 22), materials.edge);
    edge.position.copy(plate.position);
    pivot.add(edge);
    arc(pivot, 1.29, start + 0.15, 0.17, 0.009, 0.31, materials.mint);
    iris.add(pivot);
    blades.push(pivot);
  }
  const lens = makeLens();
  lens.mesh.position.z = 0.25;
  assembly.add(lens.mesh);
  arc(assembly, 0.7, 0, TAU, 0.026, 0.3, materials.mint);
  arc(assembly, 0.755, 0, TAU, 0.007, 0.29, materials.ice);
  const lensTicks = ticks(0.78, 96, 0.01, 0.03, materials.edge);
  lensTicks.position.z = 0.32;
  assembly.add(lensTicks);
  const fibers = makeFibers(), packets = makePackets(), waveform = makeWaveform();
  assembly.add(fibers.group, packets.mesh, waveform.line);
  const progressPoints = Array.from({ length: 129 }, (_, i) => new THREE.Vector3(Math.cos(i / 128 * TAU + Math.PI / 2) * 2.49, Math.sin(i / 128 * TAU + Math.PI / 2) * 2.49, 0));
  const progressRing = new THREE.Line(new THREE.BufferGeometry().setFromPoints(progressPoints), new THREE.LineBasicMaterial({ color: 0xa4ffdb, transparent: true, opacity: 0.8 }));
  assembly.add(progressRing);
  const sweep = new THREE.Line(new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(-0.6, 0, 0.94), new THREE.Vector3(0.6, 0, 0.94)]), new THREE.LineBasicMaterial({ color: 0xb7f4ff, transparent: true, opacity: 0.65 }));
  assembly.add(sweep);

  const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
  const pointer = new THREE.Vector2(), target = new THREE.Vector3();
  const color = new THREE.Color(STATES.idle.color), desiredColor = color.clone();
  let layoutMode = "compact", fit = 1, disposed = false, activity = null, activityUntil = 0;
  let state = "idle", energy = 0.58, speed = 0.22, aperture = 1;
  let phase = 0, rotation = 0, previousTime = null, speechStart = 0;
  let speechStrength = 0.6, volume = 1, rate = 1, boot = 1, bootActive = false;
  const onPointer = (event) => {
    if (event.pointerType === "touch") return;
    const rect = renderer.domElement.getBoundingClientRect();
    pointer.set((event.clientX - rect.left) / Math.max(rect.width, 1) * 2 - 1, (event.clientY - rect.top) / Math.max(rect.height, 1) * 2 - 1);
  };
  window.addEventListener("pointermove", onPointer, { passive: true });
  function fitLayout() {
    const { width, height } = renderer.domElement.getBoundingClientRect();
    if (!width || !height) return;
    const drawer = document.querySelector(".operations-drawer");
    const drawerWidth = layoutMode === "full" ? (drawer?.getBoundingClientRect().width || 420) + 32 : 0;
    const usableWidth = Math.max(240, width - drawerWidth);
    const subtitleTop = document.getElementById("subtitlePanel")?.getBoundingClientRect().top;
    const bottom = subtitleTop > 220 ? Math.min(subtitleTop - 22, height * 0.74) : height * 0.71;
    const top = width < 600 ? 100 : 106, usableHeight = Math.max(150, bottom - top);
    const pixelsPerUnit = height / (2 * Math.tan(THREE.MathUtils.degToRad(camera.fov / 2)) * camera.position.z);
    fit = Math.min(usableWidth * 0.85, usableHeight * 0.94, 650) / (5.1 * pixelsPerUnit);
    target.set((usableWidth / 2 - width / 2) / pixelsPerUnit, (height / 2 - (top + usableHeight / 2)) / pixelsPerUnit, 0);
  }
  fitLayout();
  root.position.copy(target);
  window.addEventListener("resize", fitLayout);
  return {
    startBoot() { boot = 0; bootActive = true; root.scale.setScalar(0.001); },
    setBootProgress(value) { boot = THREE.MathUtils.clamp(Number(value) || 0, 0, 1); },
    finishBoot() { boot = 1; bootActive = false; fitLayout(); },
    setState(value) { state = STATES[value] ? value : "idle"; },
    setActivity(value, duration = 0) {
      activity = value && STATES[value.kind] ? value : null;
      activityUntil = duration > 0 ? performance.now() + duration : 0;
    },
    setSpeechText(text) { speechStart = phase; speechStrength = text ? Math.min(1, 0.45 + String(text).length / 240) : 0; },
    setVoiceProfile(profile = {}) {
      volume = THREE.MathUtils.clamp(Number(profile.volume ?? 1), 0, 1);
      rate = THREE.MathUtils.clamp(Number(profile.rate ?? 1), 0.5, 2);
    },
    setLayoutMode(mode) { layoutMode = mode; fitLayout(); },
    update(time, nextState = state) {
      if (disposed) return;
      state = STATES[nextState] ? nextState : "idle";
      if (activityUntil && performance.now() >= activityUntil) activity = null;
      const voiceActive = ["listening", "speaking", "transcribing"].includes(state);
      const kind = ["error", "success", "confirmation"].includes(activity?.kind) ? activity.kind : voiceActive ? state : activity?.kind || state;
      renderer.domElement.dataset.coreActivity = kind;
      const dt = previousTime === null ? 1 / 60 : THREE.MathUtils.clamp(time - previousTime, 0, 0.05);
      previousTime = time;
      const blend = motion.matches ? 1 : 1 - Math.exp(-dt * 4.5), profile = STATES[kind];
      energy = THREE.MathUtils.lerp(energy, profile.energy, blend);
      speed = THREE.MathUtils.lerp(speed, profile.speed, blend);
      aperture = THREE.MathUtils.lerp(aperture, profile.aperture, blend);
      if (!motion.matches && !document.hidden) { phase += dt; rotation += dt * speed; }
      const t = motion.matches ? 0 : phase;
      const speech = state === "speaking" && !motion.matches ? (0.5 + 0.3 * Math.sin((t - speechStart) * 9 * rate) + 0.2 * Math.sin((t - speechStart) * 17)) * speechStrength * volume : 0;
      color.lerp(desiredColor.setHex(profile.color), blend);
      const reveal = bootActive ? THREE.MathUtils.smootherstep(boot, 0, 1) : 1;
      root.position.lerp(target, blend);
      root.scale.setScalar(fit * THREE.MathUtils.lerp(0.5, 1, reveal));
      root.visible = reveal > 0.002;
      assembly.rotation.x = THREE.MathUtils.lerp(assembly.rotation.x, 0.09 + (motion.matches ? 0 : pointer.y * 0.045), blend);
      assembly.rotation.y = THREE.MathUtils.lerp(assembly.rotation.y, -0.12 + (motion.matches ? 0 : pointer.x * 0.075), blend);
      housing.rotation.z = rotation * 0.15 + (1 - reveal) * 0.8;
      halo.rotation.z = -rotation * 0.09;
      gimbal.rotation.z = rotation * 0.19 + (1 - reveal) * 1.4;
      iris.rotation.z = -rotation * 0.11;
      const shellReveal = THREE.MathUtils.smootherstep(boot, 0.22, 0.82);
      housing.scale.setScalar(0.75 + shellReveal * 0.25);
      halo.scale.setScalar(0.65 + shellReveal * 0.35);
      housing.visible = boot > 0.18;
      halo.visible = boot > 0.32;
      blades.forEach((blade, i) => {
        const s = aperture + speech * 0.04;
        blade.scale.set(s, s, 1);
        blade.position.z = Math.sin(t * 0.5 + i * 0.52) * 0.018;
      });
      materials.mint.color.copy(color);
      materials.mint.opacity = (0.55 + energy * 0.34) * reveal;
      materials.ice.opacity = (0.38 + energy * 0.34) * reveal;
      lens.uniforms.uTime.value = t;
      lens.uniforms.uEnergy.value = energy + speech * 0.6;
      lens.uniforms.uColor.value.copy(color);
      lens.uniforms.uReveal.value = reveal;
      lens.mesh.scale.setScalar(0.96 + speech * 0.055);
      fibers.group.rotation.z = rotation * 0.08;
      fibers.lines.forEach((line, i) => { line.material.opacity = reveal * (0.1 + energy * 0.14 + Math.pow(0.5 + 0.5 * Math.sin(t * 1.7 - i), 5) * 0.32); });
      updatePackets(packets, rotation, energy, reveal);
      const amplitude = kind === "listening" ? 0.07 : kind === "media" ? 0.05 + Math.sin(t * 3) * 0.02 : 0.016 + speech * 0.075;
      updateWaveform(waveform, t, amplitude, color, reveal);
      progressRing.visible = Number.isFinite(activity?.progress) && !["error", "paused"].includes(kind);
      if (progressRing.visible) progressRing.geometry.setDrawRange(0, Math.floor(THREE.MathUtils.clamp(activity.progress, 0, 1) * 128) + 1);
      sweep.visible = kind === "research" || kind === "vision" || kind === "transcribing";
      sweep.position.y = Math.sin(t * (kind === "vision" ? 1.4 : 2.5)) * 0.5;
      sweep.scale.x = Math.sqrt(Math.max(0, 0.36 - sweep.position.y ** 2)) / 0.6;
    },
    dispose() {
      if (disposed) return;
      disposed = true;
      window.removeEventListener("pointermove", onPointer);
      window.removeEventListener("resize", fitLayout);
      const geometries = new Set(), usedMaterials = new Set(Object.values(materials));
      root.traverse((object) => {
        if (object.geometry) geometries.add(object.geometry);
        for (const material of Array.isArray(object.material) ? object.material : [object.material]) if (material) usedMaterials.add(material);
      });
      geometries.forEach((geometry) => geometry.dispose());
      usedMaterials.forEach((material) => material.dispose());
      scene.remove(root, lights);
    },
  };
}

function glow(color, opacity) {
  return new THREE.MeshBasicMaterial({ color, transparent: true, opacity, blending: THREE.AdditiveBlending, depthWrite: false });
}
function arc(parent, radius, start, length, thickness, z, material) {
  const mesh = new THREE.Mesh(new THREE.TorusGeometry(radius, thickness, 6, Math.max(8, Math.ceil(length * 40)), length), material);
  mesh.rotation.z = start;
  mesh.position.z = z;
  parent.add(mesh);
  return mesh;
}
function sector(parent, inner, outer, start, length, depth, z, material, edgeMaterial) {
  const shape = new THREE.Shape();
  shape.absarc(0, 0, outer, start, start + length, false);
  shape.absarc(0, 0, inner, start + length, start, true);
  shape.closePath();
  const geometry = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: true, bevelSize: 0.012, bevelThickness: 0.012, bevelSegments: 2, curveSegments: 28, steps: 1 });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.position.z = z;
  parent.add(mesh);
  if (edgeMaterial) { const edges = new THREE.LineSegments(new THREE.EdgesGeometry(geometry, 28), edgeMaterial); edges.position.z = z; parent.add(edges); }
}
function ticks(radius, count, short, long, material) {
  const points = [];
  for (let i = 0; i < count; i++) {
    const a = i * TAU / count, end = radius + (i % 8 === 0 ? long : short);
    points.push(new THREE.Vector3(Math.cos(a) * radius, Math.sin(a) * radius, 0), new THREE.Vector3(Math.cos(a) * end, Math.sin(a) * end, 0));
  }
  return new THREE.LineSegments(new THREE.BufferGeometry().setFromPoints(points), material);
}
function makeLens() {
  const uniforms = { uTime: { value: 0 }, uEnergy: { value: 0.6 }, uReveal: { value: 1 }, uColor: { value: new THREE.Color(0x68f0c5) } };
  const material = new THREE.ShaderMaterial({
    uniforms,
    vertexShader: `
      varying vec3 vPosition;
      varying vec3 vNormal;
      varying vec3 vView;
      void main() {
        vPosition = position;
        vec4 viewPosition = modelViewMatrix * vec4(position, 1.0);
        vNormal = normalize(normalMatrix * normal);
        vView = -viewPosition.xyz;
        gl_Position = projectionMatrix * viewPosition;
      }
    `,
    fragmentShader: `
      uniform float uTime;
      uniform float uEnergy;
      uniform float uReveal;
      uniform vec3 uColor;
      varying vec3 vPosition;
      varying vec3 vNormal;
      varying vec3 vView;
      void main() {
        vec3 p = normalize(vPosition);
        float angle = atan(p.y, p.x);
        float radius = length(p.xy);
        float facing = max(dot(normalize(vNormal), normalize(vView)), 0.0);
        float field = sin(angle * 7.0 + radius * 24.0 - uTime * 1.1 + sin(p.y * 12.0 + uTime * 0.5) * 2.0);
        float filaments = pow(0.5 + 0.5 * field, 9.0);
        float fine = pow(0.5 + 0.5 * sin(radius * 115.0 + angle * 3.0 - uTime * 2.0), 18.0);
        float nucleus = exp(-radius * radius * 18.0);
        float rim = pow(1.0 - facing, 2.0);
        vec3 color = uColor * (0.08 + filaments * 0.8 + fine * 0.2 + rim * 1.4);
        color += vec3(0.78, 0.95, 1.0) * nucleus * (1.2 + uEnergy * 0.65);
        color *= (0.5 + uEnergy * 0.7) * uReveal;
        gl_FragColor = vec4(color, 1.0);
        #include <tonemapping_fragment>
        #include <colorspace_fragment>
      }
    `,
  });
  return { uniforms, mesh: new THREE.Mesh(new THREE.SphereGeometry(0.65, 64, 40), material) };
}
function makeFibers() {
  const group = new THREE.Group(), lines = [];
  for (let i = 0; i < 24; i++) {
    const positions = [];
    for (let j = 0; j <= 72; j++) {
      const t = j / 72, angle = i * TAU / 24 + t * 1.3;
      const radius = 0.78 + Math.sin(t * Math.PI) * (0.25 + i % 3 * 0.065);
      positions.push(new THREE.Vector3(Math.cos(angle) * radius, Math.sin(angle) * radius, 0.38 + Math.sin(t * TAU) * 0.055));
    }
    const material = new THREE.LineBasicMaterial({ color: i % 4 === 0 ? 0xb8e9ff : 0x56dbb5, transparent: true, opacity: 0.25, blending: THREE.AdditiveBlending, depthWrite: false });
    const line = new THREE.Line(new THREE.BufferGeometry().setFromPoints(positions), material);
    group.add(line); lines.push(line);
  }
  return { group, lines };
}
function makePackets() {
  const mesh = new THREE.InstancedMesh(new THREE.BoxGeometry(0.017, 0.045, 0.018), glow(0xffffff, 0.9), 54);
  mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
  mesh.frustumCulled = false;
  const color = new THREE.Color();
  for (let i = 0; i < 54; i++) mesh.setColorAt(i, color.setHex(i % 9 === 0 ? 0xf6cb85 : i % 3 === 0 ? 0xb0eeff : 0x72efc0));
  return { mesh, dummy: new THREE.Object3D() };
}
function updatePackets({ mesh, dummy }, phase, energy, reveal) {
  for (let i = 0; i < mesh.count; i++) {
    const lane = i % 3, angle = i * TAU / 18 + phase * (lane === 1 ? -0.8 : 0.65) + lane * 0.27;
    const radius = [1.46, 1.94, 2.12][lane];
    dummy.position.set(Math.cos(angle) * radius, Math.sin(angle) * radius, 0.09);
    dummy.rotation.z = angle;
    dummy.scale.setScalar(reveal * (i % 6 === 0 ? 1.4 : 0.65 + energy * 0.2));
    dummy.updateMatrix(); mesh.setMatrixAt(i, dummy.matrix);
  }
  mesh.instanceMatrix.needsUpdate = true;
}
function makeWaveform() {
  const positions = new Float32Array(257 * 3), geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.BufferAttribute(positions, 3).setUsage(THREE.DynamicDrawUsage));
  const material = new THREE.LineBasicMaterial({ color: 0x92ffc8, transparent: true, opacity: 0.7, blending: THREE.AdditiveBlending, depthWrite: false });
  const line = new THREE.LineLoop(geometry, material);
  line.frustumCulled = false;
  return { line, positions };
}
function updateWaveform({ line, positions }, time, amplitude, color, reveal) {
  for (let i = 0; i < 257; i++) {
    const angle = i / 257 * TAU;
    const radius = 1.12 + amplitude * (Math.sin(angle * 18 - time * 4) * 0.6 + Math.sin(angle * 31 + time * 3) * 0.4);
    positions[i * 3] = Math.cos(angle) * radius;
    positions[i * 3 + 1] = Math.sin(angle) * radius;
    positions[i * 3 + 2] = 0.46;
  }
  line.material.color.copy(color); line.material.opacity = 0.7 * reveal;
  line.geometry.attributes.position.needsUpdate = true;
}

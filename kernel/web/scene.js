import * as THREE from "/vendor/three.module.min.js";

function latLonToVec3(lat, lon, radius) {
  const phi = (90 - lat) * (Math.PI / 180);
  const theta = (lon + 180) * (Math.PI / 180);
  return new THREE.Vector3(
    -radius * Math.sin(phi) * Math.cos(theta),
    radius * Math.cos(phi),
    radius * Math.sin(phi) * Math.sin(theta),
  );
}

function glowTexture(rgb) {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
  g.addColorStop(0, `rgba(${rgb},0.82)`);
  g.addColorStop(0.28, `rgba(${rgb},0.32)`);
  g.addColorStop(0.62, `rgba(${rgb},0.09)`);
  g.addColorStop(1, `rgba(${rgb},0)`);
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, 128, 128);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function edgeTube(lat1, lon1, lat2, lon2, color, radius) {
  const pts = [];
  const n = 28;
  for (let i = 0; i <= n; i += 1) {
    const t = i / n;
    pts.push(latLonToVec3(lat1 + (lat2 - lat1) * t, lon1 + (lon2 - lon1) * t, 1.008));
  }
  const curve = new THREE.CatmullRomCurve3(pts);
  return new THREE.Mesh(
    new THREE.TubeGeometry(curve, n * 2, radius, 8, false),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.92 }),
  );
}

function bboxFrame(box, color, radius = 0.0042) {
  const { west, south, east, north } = box;
  const group = new THREE.Group();
  group.add(
    edgeTube(north, west, north, east, color, radius),
    edgeTube(north, east, south, east, color, radius),
    edgeTube(south, east, south, west, color, radius),
    edgeTube(south, west, north, west, color, radius),
  );
  return group;
}

function pin(lat, lon, color, sprite, scale = 1) {
  const group = new THREE.Group();
  group.position.copy(latLonToVec3(lat, lon, 1.014));
  const radius = 0.0078 * scale;
  const core = new THREE.Mesh(
    new THREE.SphereGeometry(radius, 12, 12),
    new THREE.MeshBasicMaterial({ color, transparent: true, opacity: 0.88, depthWrite: false }),
  );
  const glow = new THREE.Sprite(new THREE.SpriteMaterial({
    map: sprite, color, transparent: true, depthWrite: false,
    blending: THREE.AdditiveBlending, opacity: 0.42,
  }));
  glow.scale.set(radius * 9, radius * 9, 1);
  group.add(core, glow);
  group.userData = { core, glow, seed: lat * 0.17 + lon * 0.09, radius, kind: "pin" };
  return group;
}

function pulseRing(lat, lon, color) {
  const mesh = new THREE.Mesh(
    new THREE.RingGeometry(0.018, 0.022, 48),
    new THREE.MeshBasicMaterial({
      color, transparent: true, opacity: 0.0, side: THREE.DoubleSide, depthWrite: false,
    }),
  );
  const p = latLonToVec3(lat, lon, 1.02);
  mesh.position.copy(p);
  mesh.lookAt(p.clone().multiplyScalar(2));
  mesh.userData = { kind: "ring", seed: lat * 0.31 + lon * 0.13, origin: p.clone() };
  return mesh;
}

function regionWash(lat, lon, rgb, scale) {
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
    map: glowTexture(rgb),
    color: 0xffffff,
    transparent: true,
    depthWrite: false,
    blending: THREE.AdditiveBlending,
    opacity: 0.34,
  }));
  sprite.position.copy(latLonToVec3(lat, lon, 1.03));
  sprite.scale.set(scale, scale, 1);
  return sprite;
}

const DESKS = {
  tideline: {
    face: [51.45, -0.28],
    atmosphere: 0x3dd6c6,
    hud: ["Earth", "Thames to Estuary", "WARNING · GAUGE", "not a flood model"],
    caption: "NASA Blue Marble · LIVE warning vs in-situ gauge · two lists · no model",
    wash: { lat: 51.45, lon: -0.2, rgb: "61,214,198", scale: 0.42 },
    frames: [
      { west: -5.8, south: 50.2, east: 2.4, north: 53.4, color: 0x1f6f68, radius: 0.0046 },
      { west: -1.2, south: 51.2, east: 0.6, north: 51.7, color: 0x3dd6c6, radius: 0.0032 },
    ],
    points: [
      { lat: 51.51, lon: -0.09, rgb: "61,214,198", color: 0x3dd6c6, scale: 1.25, ring: true },
      { lat: 51.46, lon: 0.22, rgb: "61,214,198", color: 0x3dd6c6, scale: 1.05, ring: true },
      { lat: 51.44, lon: 0.72, rgb: "61,214,198", color: 0x3dd6c6, scale: 0.95, ring: true },
      { lat: 51.40, lon: -0.51, rgb: "196,165,116", color: 0xc4a574, scale: 1.05 },
      { lat: 51.41, lon: -0.31, rgb: "196,165,116", color: 0xc4a574, scale: 0.95 },
      { lat: 51.49, lon: -0.88, rgb: "196,165,116", color: 0xc4a574, scale: 0.88 },
      { lat: 51.89, lon: 0.90, rgb: "61,214,198", color: 0x3dd6c6, scale: 0.8, ring: true },
      { lat: 52.48, lon: 1.75, rgb: "61,214,198", color: 0x3dd6c6, scale: 0.75 },
    ],
  },
  solrecord: {
    face: [35.0, -117.5],
    atmosphere: 0xf0b429,
    hud: ["Earth", "Mojave plant pin", "NASA POWER · CAMS", "not a yield forecast"],
    caption: "NASA Blue Marble · retrospective irradiance · not a pyranometer",
    wash: { lat: 35.1, lon: -117.4, rgb: "240,180,41", scale: 0.48 },
    frames: [
      { west: -119.6, south: 33.4, east: -114.3, north: 37.4, color: 0xc4922a, radius: 0.0046 },
    ],
    points: [
      { lat: 35.00, lon: -117.50, rgb: "240,180,41", color: 0xf0b429, scale: 1.7, ring: true },
      { lat: 34.72, lon: -118.16, rgb: "240,180,41", color: 0xf0b429, scale: 1.05, ring: true },
      { lat: 35.38, lon: -116.84, rgb: "232,201,138", color: 0xe8c98a, scale: 0.95 },
      { lat: 34.50, lon: -117.32, rgb: "240,180,41", color: 0xf0b429, scale: 0.9 },
      { lat: 35.62, lon: -117.68, rgb: "232,201,138", color: 0xe8c98a, scale: 0.85 },
      { lat: 33.92, lon: -116.54, rgb: "240,180,41", color: 0xf0b429, scale: 0.8, ring: true },
      { lat: 36.24, lon: -116.02, rgb: "232,201,138", color: 0xe8c98a, scale: 0.72 },
    ],
  },
  seamark: {
    face: [62.4, 14.8],
    atmosphere: 0x5b8def,
    hud: ["Earth", "FI + NO waters", "FINTRAFFIC · KYSTVERKET", "not global AIS"],
    caption: "NASA Blue Marble · licensed Nordic AIS · two lists · not GFW",
    wash: { lat: 62.0, lon: 15.0, rgb: "91,141,239", scale: 0.72 },
    frames: [
      { west: 19.0, south: 59.5, east: 30.5, north: 66.2, color: 0x3dd6c6, radius: 0.0044 },
      { west: 4.0, south: 57.8, east: 19.0, north: 71.4, color: 0x5b8def, radius: 0.0044 },
      { west: 24.4, south: 59.8, east: 25.4, north: 60.4, color: 0x7ef0e4, radius: 0.0028 },
      { west: 10.4, south: 59.7, east: 10.9, north: 59.99, color: 0x9bb8ff, radius: 0.0028 },
    ],
    points: [
      { lat: 60.15, lon: 24.94, rgb: "61,214,198", color: 0x3dd6c6, scale: 1.15, ais: 1 },
      { lat: 60.02, lon: 25.12, rgb: "61,214,198", color: 0x3dd6c6, scale: 0.95, ais: 1 },
      { lat: 59.92, lon: 24.65, rgb: "61,214,198", color: 0x3dd6c6, scale: 0.9, ais: 1 },
      { lat: 61.50, lon: 21.50, rgb: "61,214,198", color: 0x3dd6c6, scale: 0.85, ais: 1 },
      { lat: 63.10, lon: 21.80, rgb: "61,214,198", color: 0x3dd6c6, scale: 0.8, ais: 1 },
      { lat: 59.88, lon: 10.65, rgb: "91,141,239", color: 0x5b8def, scale: 1.1, ais: -1 },
      { lat: 59.78, lon: 10.52, rgb: "91,141,239", color: 0x5b8def, scale: 0.95, ais: -1 },
      { lat: 60.45, lon: 5.30, rgb: "91,141,239", color: 0x5b8def, scale: 1.0, ais: -1 },
      { lat: 63.43, lon: 10.40, rgb: "91,141,239", color: 0x5b8def, scale: 0.88, ais: -1 },
      { lat: 68.44, lon: 17.42, rgb: "91,141,239", color: 0x5b8def, scale: 0.82, ais: -1, ring: true },
    ],
  },
  plinth: {
    face: [39.04, -77.45],
    atmosphere: 0xc4a574,
    hud: ["Earth", "Ashburn colo campus", "WEATHER · AIR · GRID", "not a BMS"],
    caption: "NASA Blue Marble · named-site nowcast · five lists · no campus score",
    wash: { lat: 39.04, lon: -77.45, rgb: "196,165,116", scale: 0.46 },
    frames: [
      { west: -80.6, south: 36.7, east: -74.7, north: 41.3, color: 0x6b7c86, radius: 0.0046 },
      { west: -77.52, south: 39.00, east: -77.38, north: 39.08, color: 0xc4a574, radius: 0.003 },
    ],
    points: [
      { lat: 39.043, lon: -77.448, rgb: "196,165,116", color: 0xc4a574, scale: 1.45, ring: true },
      { lat: 39.036, lon: -77.462, rgb: "120,170,220", color: 0x78aad8, scale: 1.1 },
      { lat: 38.95, lon: -77.45, rgb: "232,201,138", color: 0xe8c98a, scale: 0.95 },
      { lat: 38.85, lon: -77.04, rgb: "120,170,220", color: 0x78aad8, scale: 0.9 },
      { lat: 39.18, lon: -76.67, rgb: "232,201,138", color: 0xe8c98a, scale: 0.88 },
      { lat: 37.54, lon: -77.44, rgb: "120,170,220", color: 0x78aad8, scale: 0.8 },
      { lat: 40.22, lon: -76.88, rgb: "196,165,116", color: 0xc4a574, scale: 0.78 },
    ],
  },
};

function earthMesh(texture) {
  const mat = texture
    ? new THREE.MeshStandardMaterial({ map: texture, roughness: 0.58, metalness: 0.02 })
    : new THREE.MeshStandardMaterial({ color: 0x2c3a36, roughness: 0.7, metalness: 0.04 });
  if (texture) {
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.anisotropy = 8;
  }
  return new THREE.Mesh(new THREE.SphereGeometry(1, 96, 96), mat);
}

window.mountDeskScene = function mountDeskScene(deskId) {
  const canvas = document.getElementById("desk-scene");
  const stage = canvas && canvas.parentElement;
  if (!canvas || !stage) return;
  if (canvas._deskDispose) canvas._deskDispose();

  const spec = DESKS[deskId] || DESKS.tideline;
  const hud = document.getElementById("scene-hud");
  if (hud) {
    hud.innerHTML = spec.hud.map((line, i) =>
      `<span class="${i === spec.hud.length - 1 ? "live" : ""}">${line}</span>`
    ).join("");
  }
  const cap = document.getElementById("scene-caption");
  if (cap) cap.textContent = spec.caption;

  const renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.NoToneMapping;

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(30, 1, 0.4, 20);
  camera.position.set(0.18, 0.04, 3.15);
  camera.lookAt(0, 0, 0);

  scene.add(new THREE.AmbientLight(0xffffff, 0.75));
  scene.add(new THREE.HemisphereLight(0xcfe4f4, 0x1a1814, 0.35));
  const key = new THREE.DirectionalLight(0xfff6ea, 1.55);
  key.position.set(2.2, 1.2, 2.8);
  scene.add(key);

  const facing = new THREE.Group();
  const look = latLonToVec3(spec.face[0], spec.face[1], 1).normalize();
  facing.quaternion.setFromUnitVectors(look, new THREE.Vector3(0, 0, 1));
  scene.add(facing);

  const earth = earthMesh(null);
  facing.add(earth);
  const atmosphere = new THREE.Mesh(
    new THREE.SphereGeometry(1, 64, 64),
    new THREE.MeshBasicMaterial({
      color: spec.atmosphere || 0x8fb4d4,
      transparent: true,
      opacity: 0.11,
      side: THREE.BackSide,
      depthWrite: false,
    }),
  );
  atmosphere.scale.setScalar(1.028);
  facing.add(atmosphere);

  if (spec.wash) facing.add(regionWash(spec.wash.lat, spec.wash.lon, spec.wash.rgb, spec.wash.scale));
  spec.frames.forEach((frame) => facing.add(bboxFrame(frame, frame.color, frame.radius)));

  const moving = [];
  spec.points.forEach((p) => {
    const sprite = glowTexture(p.rgb);
    const node = pin(p.lat, p.lon, p.color, sprite, p.scale || 1);
    node.userData.ais = p.ais || 0;
    node.userData.origin = { lat: p.lat, lon: p.lon };
    facing.add(node);
    moving.push(node);
    if (p.ring) {
      const ring = pulseRing(p.lat, p.lon, p.color);
      facing.add(ring);
      moving.push(ring);
    }
  });

  new THREE.TextureLoader().load("/earth-day.jpg", (tex) => {
    earth.material.map = tex;
    earth.material.color.set(0xffffff);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    earth.material.needsUpdate = true;
  });

  function resize() {
    const w = Math.max(stage.clientWidth, 280);
    const h = Math.max(stage.clientHeight, 360);
    renderer.setSize(w, h, false);
    camera.aspect = w / h;
    camera.updateProjectionMatrix();
  }
  resize();
  const ro = new ResizeObserver(resize);
  ro.observe(stage);

  const orbit = { theta: Math.atan2(camera.position.x, camera.position.z), dragging: false, lastX: 0 };
  const radius = Math.hypot(camera.position.x, camera.position.z);
  const camY = camera.position.y;

  const onDown = (event) => {
    orbit.dragging = true;
    orbit.lastX = event.clientX;
  };
  const onMove = (event) => {
    if (!orbit.dragging) return;
    orbit.theta -= (event.clientX - orbit.lastX) * 0.005;
    orbit.lastX = event.clientX;
  };
  const onUp = () => { orbit.dragging = false; };
  canvas.addEventListener("pointerdown", onDown);
  window.addEventListener("pointermove", onMove);
  window.addEventListener("pointerup", onUp);

  let raf = 0;
  function frame(now) {
    const t = now * 0.001;
    if (!orbit.dragging) orbit.theta += 0.00048;
    camera.position.set(Math.sin(orbit.theta) * radius, camY, Math.cos(orbit.theta) * radius);
    camera.lookAt(0, 0, 0);
    moving.forEach((node) => {
      if (node.userData.kind === "ring") {
        const wave = (t * 0.35 + node.userData.seed) % 1;
        node.scale.setScalar(1 + wave * 3.2);
        node.material.opacity = 0.55 * (1 - wave);
        return;
      }
      const energy = 0.5 + 0.38 * Math.sin(t * 1.9 + node.userData.seed) + 0.12 * Math.sin(t * 3.3 + node.userData.seed * 1.5);
      node.userData.core.scale.setScalar(0.9 + energy * 0.28);
      node.userData.core.material.opacity = 0.62 + energy * 0.32;
      const size = node.userData.radius * (8.2 + energy * 3.4);
      node.userData.glow.scale.set(size, size, 1);
      node.userData.glow.material.opacity = 0.26 + energy * 0.3;
      if (node.userData.ais) {
        const origin = node.userData.origin;
        const drift = origin.lon + Math.sin(t * 0.22 * node.userData.ais) * 0.22;
        node.position.copy(latLonToVec3(origin.lat, drift, 1.014));
      }
    });
    renderer.render(scene, camera);
    raf = requestAnimationFrame(frame);
  }
  raf = requestAnimationFrame(frame);

  canvas._deskDispose = () => {
    cancelAnimationFrame(raf);
    ro.disconnect();
    canvas.removeEventListener("pointerdown", onDown);
    window.removeEventListener("pointermove", onMove);
    window.removeEventListener("pointerup", onUp);
    renderer.dispose();
  };
};

const preview = new URLSearchParams(location.search).get("desk");
if (preview && DESKS[preview]) {
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", () => window.mountDeskScene(preview));
  } else {
    window.mountDeskScene(preview);
  }
}

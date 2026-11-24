import * as THREE from './vendor/three.module.min.js';
import { GLTFLoader } from './vendor/addons/loaders/GLTFLoader.js';
import { OrbitControls } from './vendor/addons/controls/OrbitControls.js';
import { sceneBounds } from './bounds.js';

const $ = (id) => document.getElementById(id);
const SETTINGS_KEY = 'cs2mb_viewer3d_v1';
const DEFAULT_LAYERS = {
  collision: true,
  floors: true,
  walls: true,
  clips: false,
  nav: true,
  connections: false,
  entities: true,
  places: true,
  routes: true,
};
const LAYER_KEYS = Object.keys(DEFAULT_LAYERS);
const COLORS = {
  floor: 0x6f8798,
  wall: 0x34434e,
  other: 0x5b5349,
  clip: 0x3fb0c2,
  nav: 0x45bdd0,
  navLink: 0x2d7f8c,
  ct: 0x4ea8ff,
  t: 0xdca552,
  place: 0x7ad7e2,
  marker: 0x8c9aa3,
};

const state = {
  data: null,
  renderer: null,
  scene: null,
  camera: null,
  controls: null,
  needsRender: true,
  ready: false,
  layers: { ...DEFAULT_LAYERS },
  quality: 'balanced',
  remember: true,
  groups: {},
  pickables: [],
  navAreaIds: [],
  areaLinks: new Map(),
  settings: null,
  lastFrame: performance.now(),
  frames: 0,
  fpsTimer: performance.now(),
};
let notice = '';

const clamp = (value, min, max) => Math.min(max, Math.max(min, value));

function num(value) {
  return new Intl.NumberFormat('en-US').format(Math.round(value));
}

function readSettings() {
  let saved = {};
  try {
    saved = JSON.parse(localStorage.getItem(SETTINGS_KEY) || '{}') || {};
  } catch {
    saved = {};
  }
  const layers = { ...DEFAULT_LAYERS };
  for (const key of LAYER_KEYS) {
    if (typeof saved.layers?.[key] === 'boolean') layers[key] = saved.layers[key];
  }
  return {
    layers,
    quality: ['performance', 'balanced', 'quality'].includes(saved.quality) ? saved.quality : 'balanced',
    remember: saved.remember !== false,
  };
}

function saveSettings() {
  if (!state.remember) return;
  try {
    localStorage.setItem(
      SETTINGS_KEY,
      JSON.stringify({ layers: state.layers, quality: state.quality, remember: true }),
    );
  } catch {
    /* private mode / quota: settings remain session-only */
  }
}

function applySettings(settings, save = true) {
  if (!settings) return;
  if (settings.layers) {
    for (const key of LAYER_KEYS) {
      if (typeof settings.layers[key] === 'boolean') state.layers[key] = settings.layers[key];
    }
  }
  if (['performance', 'balanced', 'quality'].includes(settings.quality)) {
    state.quality = settings.quality;
  }
  if (typeof settings.remember === 'boolean') state.remember = settings.remember;
  syncControls();
  applyLayers();
  setQuality();
  if (save) saveSettings();
}

function syncControls() {
  for (const key of LAYER_KEYS) {
    const input = document.querySelector(`[data-layer="${key}"]`);
    if (input) input.checked = state.layers[key];
  }
  const quality = $('quality');
  if (quality) quality.value = state.quality;
  const remember = $('remember');
  if (remember) remember.checked = state.remember;
}

function applyLayers() {
  const groups = state.groups;
  if (groups.collision) groups.collision.visible = state.layers.collision;
  if (groups.floor) groups.floor.visible = state.layers.floors;
  if (groups.wall) groups.wall.visible = state.layers.walls;
  if (groups.clip) groups.clip.visible = state.layers.clips;
  if (groups.nav) groups.nav.visible = state.layers.nav;
  if (groups.links) groups.links.visible = state.layers.connections;
  if (groups.entities) groups.entities.visible = state.layers.entities;
  if (groups.places) groups.places.visible = state.layers.entities && state.layers.places;
  if (groups.routes) groups.routes.visible = state.layers.routes;
  state.needsRender = true;
}

function setQuality() {
  if (!state.renderer) return;
  const ratio =
    state.quality === 'performance'
      ? 1
      : state.quality === 'quality'
        ? Math.min(window.devicePixelRatio || 1, 2)
        : Math.min(window.devicePixelRatio || 1, 1.5);
  state.renderer.setPixelRatio(ratio);
  resize();
}

function setStats() {
  const data = state.data;
  if (!data) return;
  $('stat-areas').textContent = num(data.stats.nav_areas);
  $('stat-links').textContent = num(data.stats.nav_edges);
  $('stat-triangles').textContent = num(data.stats.collision_triangles);
  $('stat-entities').textContent = num(data.stats.spawns + data.entities.markers.length + data.entities.places.length);
  $('stat-routes').textContent = num(data.stats.routes);
  $('count-collision').textContent = num(data.stats.collision_triangles) + ' tri';
  $('count-clips').textContent = num(data.collision.nodes.filter((n) => n.clip).length) + ' nodes';
  $('count-nav').textContent = num(data.stats.nav_areas);
  $('count-links').textContent = num(data.stats.nav_edges);
  $('count-entities').textContent = num(data.stats.spawns + data.entities.markers.length);
  $('count-routes').textContent = num(data.stats.routes);
}

function showError(message) {
  $('loading').hidden = true;
  $('error').hidden = false;
  $('error-text').textContent = message;
}

function setLoading(text) {
  const element = $('loading-text');
  if (element) element.textContent = text;
}

function validateData(data) {
  if (!data || data.schema !== 'cs2mb.viewer3d/1') throw new Error('unsupported 3DsVW data schema');
  if (!Array.isArray(data.nav?.areas)) throw new Error('NAV data is missing');
  if (!data.bounds || !Array.isArray(data.bounds.center) || data.bounds.center.length !== 3) {
    throw new Error('map bounds are missing');
  }
  if (!Number.isFinite(data.bounds.center[0])) throw new Error('map bounds are invalid');
}

function initRenderer() {
  const canvas = $('canvas');
  try {
    state.renderer = new THREE.WebGLRenderer({ canvas, antialias: true, powerPreference: 'high-performance' });
  } catch (error) {
    throw new Error('WebGL is unavailable in this browser.');
  }
  if (!state.renderer.capabilities.isWebGL2) {
    throw new Error('WebGL2 is required for 3DsVW.');
  }
  state.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
  state.renderer.setClearColor(0x0b1319, 1);
  state.scene = new THREE.Scene();
  state.camera = new THREE.PerspectiveCamera(48, 1, 1, 300000);
  state.camera.up.set(0, 0, 1);
  const ambient = new THREE.HemisphereLight(0xdfeaf0, 0x1b2730, 0.95);
  state.scene.add(ambient);
  const key = new THREE.DirectionalLight(0xffffff, 1.25);
  key.position.set(-0.4, -0.65, 1);
  state.scene.add(key);
  const fill = new THREE.DirectionalLight(0x9fc2d4, 0.35);
  fill.position.set(0.7, 0.4, 0.25);
  state.scene.add(fill);
  state.controls = new OrbitControls(state.camera, canvas);
  state.controls.enableDamping = true;
  state.controls.dampingFactor = 0.09;
  state.controls.screenSpacePanning = true;
  state.controls.minDistance = 30;
  state.controls.maxDistance = 300000;
  state.controls.maxPolarAngle = Math.PI * 0.495;
  state.controls.addEventListener('change', () => {
    state.needsRender = true;
  });
  const size = viewportSize();
  state.camera.aspect = size.width / Math.max(1, size.height);
  state.camera.updateProjectionMatrix();
  state.renderer.setSize(size.width, size.height, false);
  const resizeObserver = new ResizeObserver(() => resize());
  resizeObserver.observe($('viewport'));
}

function viewportSize() {
  const rect = $('viewport').getBoundingClientRect();
  return { width: Math.max(1, Math.round(rect.width)), height: Math.max(1, Math.round(rect.height)) };
}

function resize() {
  if (!state.renderer || !state.camera) return;
  const size = viewportSize();
  state.camera.aspect = size.width / Math.max(1, size.height);
  state.camera.updateProjectionMatrix();
  state.renderer.setSize(size.width, size.height, false);
  state.needsRender = true;
}

function addGrid() {
  const bounds = sceneBounds(state.data);
  if (!bounds) return;
  const { min, max } = bounds;
  const size = Math.max(max[0] - min[0], max[1] - min[1], 1000) * 1.1;
  const grid = new THREE.GridHelper(size, 20, 0x243640, 0x17252d);
  grid.rotation.x = Math.PI / 2;
  grid.position.set(
    (min[0] + max[0]) / 2,
    (min[1] + max[1]) / 2,
    min[2] - 6,
  );
  grid.material.transparent = true;
  grid.material.opacity = 0.45;
  state.scene.add(grid);
}

function buildNav() {
  const data = state.data;
  const positions = [];
  const areaIds = [];
  const areaLinks = new Map();
  for (const edge of data.nav.edges) {
    areaLinks.set(edge[0], (areaLinks.get(edge[0]) || 0) + 1);
  }
  state.areaLinks = areaLinks;
  for (const area of data.nav.areas) {
    const corners = area.corners;
    if (corners.length < 3) continue;
    const z = (area.center?.[2] ?? corners[0][2]) + 4;
    for (let i = 1; i < corners.length - 1; i += 1) {
      const a = corners[0];
      const b = corners[i];
      const c = corners[i + 1];
      positions.push(a[0], a[1], (a[2] ?? z) + 4, b[0], b[1], (b[2] ?? z) + 4, c[0], c[1], (c[2] ?? z) + 4);
      areaIds.push(area.id);
    }
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.computeVertexNormals();
  const material = new THREE.MeshBasicMaterial({
    color: COLORS.nav,
    transparent: true,
    opacity: 0.16,
    side: THREE.DoubleSide,
    depthWrite: false,
    polygonOffset: true,
    polygonOffsetFactor: -1,
  });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.renderOrder = 2;
  mesh.userData = { kind: 'nav', areaIds, areaById: new Map(data.nav.areas.map((a) => [a.id, a])) };
  state.groups.nav = mesh;
  state.scene.add(mesh);
  state.pickables.push(mesh);

  const linkPositions = [];
  const byId = new Map(data.nav.areas.map((a) => [a.id, a]));
  for (const [from, to] of data.nav.edges) {
    const a = byId.get(from);
    const b = byId.get(to);
    if (!a || !b) continue;
    linkPositions.push(a.center[0], a.center[1], a.center[2] + 5, b.center[0], b.center[1], b.center[2] + 5);
  }
  const linkGeometry = new THREE.BufferGeometry();
  linkGeometry.setAttribute('position', new THREE.Float32BufferAttribute(linkPositions, 3));
  const links = new THREE.LineSegments(
    linkGeometry,
    new THREE.LineBasicMaterial({ color: COLORS.navLink, transparent: true, opacity: 0.3 }),
  );
  links.renderOrder = 3;
  state.groups.links = links;
  state.scene.add(links);
}

function buildRoutes() {
  const group = new THREE.Group();
  for (const route of state.data.routes) {
    if (!Array.isArray(route.points) || route.points.length < 2) continue;
    const geometry = new THREE.BufferGeometry().setFromPoints(
      route.points.map((p) => new THREE.Vector3(p[0], p[1], p[2] + 5)),
    );
    const line = new THREE.Line(
      geometry,
      new THREE.LineBasicMaterial({
        color: route.side === 'CT' ? COLORS.ct : COLORS.t,
        transparent: true,
        opacity: 0.9,
      }),
    );
    line.userData = { kind: 'route', side: route.side, target: route.target, distance: route.distance };
    group.add(line);
  }
  state.groups.routes = group;
  state.scene.add(group);
}

function textSprite(text) {
  const canvas = document.createElement('canvas');
  canvas.width = 256;
  canvas.height = 64;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = 'rgba(8, 13, 17, 0.86)';
  ctx.fillRect(0, 0, 256, 64);
  ctx.strokeStyle = 'rgba(67, 183, 201, 0.8)';
  ctx.lineWidth = 2;
  ctx.strokeRect(1, 1, 254, 62);
  ctx.fillStyle = '#dff4f7';
  ctx.font = '600 26px Segoe UI, Arial, sans-serif';
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.fillText(text.slice(0, 18), 128, 33);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(
    new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false }),
  );
  sprite.scale.set(200, 50, 1);
  sprite.material.depthTest = false;
  sprite.renderOrder = 10;
  return sprite;
}

function buildEntities() {
  const data = state.data;
  const entities = new THREE.Group();
  const places = new THREE.Group();
  const spawnGeometry = new THREE.ConeGeometry(9, 24, 4);
  spawnGeometry.rotateX(Math.PI / 2);
  const spawnMeshes = { CT: [], T: [] };
  for (const spawn of data.entities.spawns) {
    const material = new THREE.MeshBasicMaterial({ color: spawn.side === 'CT' ? COLORS.ct : COLORS.t });
    const mesh = new THREE.Mesh(spawnGeometry, material);
    mesh.position.set(spawn.origin[0], spawn.origin[1], spawn.origin[2] + 12);
    mesh.userData = {
      kind: 'entity',
      label: `Spawn ${spawn.side}`,
      classname: `info_player_${spawn.side === 'CT' ? 'counterterrorist' : 'terrorist'}`,
      targetname: spawn.targetname || '',
      origin: spawn.origin,
      angles: spawn.angles,
      side: spawn.side,
    };
    spawnMeshes[spawn.side].push(mesh);
    entities.add(mesh);
    state.pickables.push(mesh);
  }
  for (const place of data.entities.places) {
    const marker = new THREE.Mesh(
      new THREE.OctahedronGeometry(12),
      new THREE.MeshBasicMaterial({ color: COLORS.place, transparent: true, opacity: 0.9 }),
    );
    marker.position.set(place.origin[0], place.origin[1], place.origin[2] + 16);
    marker.userData = {
      kind: 'place',
      label: place.label,
      place_name: place.place_name,
      origin: place.origin,
      area_id: place.area_id,
    };
    const label = textSprite(place.label);
    label.position.set(place.origin[0], place.origin[1], place.origin[2] + 110);
    label.userData = marker.userData;
    places.add(marker);
    places.add(label);
    state.pickables.push(marker, label);
  }
  for (const marker of data.entities.markers) {
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(8, 8, 8),
      new THREE.MeshBasicMaterial({ color: COLORS.marker }),
    );
    mesh.position.set(marker.origin[0], marker.origin[1], marker.origin[2] + 6);
    mesh.userData = {
      kind: 'entity',
      label: marker.classname,
      classname: marker.classname,
      targetname: marker.targetname || '',
      origin: marker.origin,
      angles: marker.angles,
    };
    entities.add(mesh);
    state.pickables.push(mesh);
  }
  state.groups.entities = entities;
  state.groups.places = places;
  state.scene.add(entities);
  state.scene.add(places);
}

function collisionMaterials() {
  return {
    floor: new THREE.MeshLambertMaterial({ color: COLORS.floor, flatShading: true }),
    wall: new THREE.MeshLambertMaterial({ color: COLORS.wall, flatShading: true }),
    other: new THREE.MeshLambertMaterial({ color: COLORS.other, flatShading: true }),
    clip: new THREE.MeshBasicMaterial({
      color: COLORS.clip,
      transparent: true,
      opacity: 0.12,
      wireframe: true,
      depthWrite: false,
    }),
  };
}

function addCollisionMesh(positions, category, meta, materials, group) {
  if (!positions.length) return;
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(positions, 3));
  geometry.computeVertexNormals();
  geometry.computeBoundingSphere();
  const mesh = new THREE.Mesh(geometry, materials[category]);
  mesh.userData = {
    kind: 'collision',
    name: meta.node || meta.name || 'collision',
    material: meta.name || '',
    surface: meta.surface || '',
    interactAs: meta.interactAs || [],
    collisionGroup: meta.collisionGroup || '',
    category,
    triangles: positions.length / 9,
  };
  group.add(mesh);
  state.pickables.push(mesh);
}

async function loadCollision() {
  const data = state.data;
  const loader = new GLTFLoader();
  const gltf = await loader.loadAsync('./scene.gltf', (event) => {
    if (event.total) {
      const pct = clamp(Math.round((event.loaded / event.total) * 100), 0, 100);
      setLoading(`Loading collision geometry… ${pct}%`);
    }
  });
  const metaByName = new Map();
  for (const node of data.collision.nodes) metaByName.set(node.node, node);
  const materials = collisionMaterials();
  const groups = {
    collision: new THREE.Group(),
    floor: new THREE.Group(),
    wall: new THREE.Group(),
    other: new THREE.Group(),
    clip: new THREE.Group(),
  };
  groups.collision.add(groups.floor, groups.wall, groups.other, groups.clip);
  state.scene.add(groups.collision);
  const meshes = [];
  gltf.scene.updateMatrixWorld(true);
  gltf.scene.traverse((object) => {
    if (object.isMesh) meshes.push(object);
  });
  const split = data.stats.collision_triangles <= 3000000;
  for (const object of meshes) {
    const materialName = Array.isArray(object.material) ? '' : object.material?.name || '';
    const nodeMeta =
      metaByName.get(object.name) ||
      metaByName.get(object.parent?.name) || {
        node: object.name,
        name: materialName,
        surface: '',
        interactAs: [],
        collisionGroup: '',
        clip: /clip|sky/i.test(object.name) || /clip|sky/i.test(materialName),
      };
    const primitiveMeta = Array.isArray(nodeMeta.primitives)
      ? nodeMeta.primitives.find((item) => item.material === materialName) || nodeMeta.primitives[0]
      : null;
    const meta = primitiveMeta
      ? { ...nodeMeta, ...primitiveMeta, name: primitiveMeta.material || nodeMeta.name }
      : nodeMeta;
    const geometry = object.geometry.clone();
    geometry.applyMatrix4(object.matrixWorld);
    if (meta.clip) {
      if (geometry.index) {
        // Keep the indexed form for clip volumes; it is only drawn when enabled.
        geometry.computeVertexNormals();
      }
      const mesh = new THREE.Mesh(geometry, materials.clip);
      mesh.userData = { ...meta, kind: 'collision', category: 'clip', triangles: geometry.index ? geometry.index.count / 3 : geometry.attributes.position.count / 3 };
      groups.clip.add(mesh);
      state.pickables.push(mesh);
      continue;
    }
    if (!split) {
      geometry.computeVertexNormals();
      const mesh = new THREE.Mesh(geometry, materials.other);
      mesh.userData = { ...meta, kind: 'collision', category: 'solid' };
      groups.other.add(mesh);
      state.pickables.push(mesh);
      continue;
    }
    const source = geometry.index ? geometry.toNonIndexed() : geometry;
    const position = source.attributes.position.array;
    const buckets = { floor: [], wall: [], other: [] };
    for (let i = 0; i + 8 < position.length; i += 9) {
      const ax = position[i], ay = position[i + 1], az = position[i + 2];
      const bx = position[i + 3], by = position[i + 4], bz = position[i + 5];
      const cx = position[i + 6], cy = position[i + 7], cz = position[i + 8];
      const ux = bx - ax, uy = by - ay, uz = bz - az;
      const vx = cx - ax, vy = cy - ay, vz = cz - az;
      let nx = uy * vz - uz * vy;
      let ny = uz * vx - ux * vz;
      let nz = ux * vy - uy * vx;
      const length = Math.hypot(nx, ny, nz);
      if (length < 1e-7) continue;
      nz /= length;
      const category = nz > 0.55 ? 'floor' : Math.abs(nz) < 0.35 ? 'wall' : 'other';
      buckets[category].push(ax, ay, az, bx, by, bz, cx, cy, cz);
    }
    for (const category of ['floor', 'wall', 'other']) {
      addCollisionMesh(buckets[category], category, meta, materials, groups[category]);
    }
  }
  state.groups.collision = groups.collision;
  state.groups.floor = groups.floor;
  state.groups.wall = groups.wall;
  state.groups.clip = groups.clip;
  applyLayers();
}

function fitView() {
  const bounds = sceneBounds(state.data);
  if (!bounds) return;
  const center = new THREE.Vector3(...bounds.center);
  const size = new THREE.Vector3(...bounds.size);
  const radius = Math.max(50, size.length() * 0.5);
  const distance = radius / Math.sin(THREE.MathUtils.degToRad(48 * 0.5)) * 1.02;
  state.camera.up.set(0, 0, 1);
  state.controls.target.copy(center);
  state.camera.position.copy(center).add(new THREE.Vector3(0.9, -0.9, 1.0).normalize().multiplyScalar(distance));
  state.controls.minDistance = Math.max(20, radius * 0.08);
  state.controls.maxDistance = Math.max(2000, radius * 8);
  state.controls.update();
  state.needsRender = true;
}

function topView() {
  const bounds = sceneBounds(state.data);
  if (!bounds) return;
  const center = new THREE.Vector3(...bounds.center);
  const radius = Math.max(50, new THREE.Vector3(...bounds.size).length() * 0.5);
  const distance = radius / Math.tan(THREE.MathUtils.degToRad(48 * 0.5)) * 1.1;
  state.camera.up.set(0, 0, 1);
  state.controls.target.copy(center);
  state.camera.position.copy(center).add(new THREE.Vector3(0.001, -0.001, distance));
  state.controls.update();
  state.needsRender = true;
}

function isoView() {
  const bounds = sceneBounds(state.data);
  if (!bounds) return;
  const center = new THREE.Vector3(...bounds.center);
  const radius = Math.max(50, new THREE.Vector3(...bounds.size).length() * 0.5);
  const distance = radius / Math.tan(THREE.MathUtils.degToRad(48 * 0.5)) * 1.05;
  state.camera.up.set(0, 0, 1);
  state.controls.target.copy(center);
  state.camera.position.copy(center).add(new THREE.Vector3(1.2, -1.2, 1.0).normalize().multiplyScalar(distance));
  state.controls.update();
  state.needsRender = true;
}

function isVisible(object) {
  let current = object;
  while (current) {
    if (!current.visible) return false;
    current = current.parent;
  }
  return true;
}

function selectionRows(hit) {
  const object = hit.object;
  const data = object.userData || {};
  const rows = [];
  if (data.kind === 'collision') {
    rows.push(['Type', 'Collision geometry']);
    rows.push(['Node', data.name || '—']);
    rows.push(['Category', data.category || '—']);
    rows.push(['Surface', data.surface || '—']);
    rows.push(['CollisionGroup', data.collisionGroup || '—']);
    rows.push(['InteractAs', (data.interactAs || []).join(', ') || '—']);
    rows.push(['Material', data.material || '—']);
    if (data.triangles) rows.push(['Triangles', num(data.triangles)]);
  } else if (data.kind === 'nav') {
    const areaId = data.areaIds?.[hit.faceIndex];
    const area = data.areaById?.get(areaId);
    if (!area) return [['Type', 'Navigation mesh'], ['Area', '—']];
    rows.push(['Type', 'NAV area']);
    rows.push(['Area ID', String(area.id)]);
    rows.push(['Flags', `0x${Number(area.flags || 0).toString(16)}`]);
    rows.push(['Hull', String(area.hull ?? '—')]);
    rows.push(['Centroid', area.center.map((v) => v.toFixed(1)).join(', ')]);
    rows.push(['Corners', String(area.corners.length)]);
    rows.push(['Connections', String(state.areaLinks.get(area.id) || 0)]);
  } else if (data.kind === 'place') {
    rows.push(['Type', 'Site / place marker']);
    rows.push(['Label', data.label || '—']);
    rows.push(['Place name', data.place_name || '—']);
    rows.push(['NAV area', String(data.area_id ?? '—')]);
    rows.push(['Origin', (data.origin || []).map((v) => v.toFixed(1)).join(', ')]);
  } else if (data.kind === 'entity') {
    rows.push(['Type', data.side ? `Spawn ${data.side}` : 'Entity']);
    rows.push(['Class', data.classname || '—']);
    rows.push(['Targetname', data.targetname || '—']);
    rows.push(['Origin', (data.origin || []).map((v) => v.toFixed(1)).join(', ')]);
    rows.push(['Angles', (data.angles || []).map((v) => v.toFixed(1)).join(', ')]);
  } else if (data.kind === 'route') {
    rows.push(['Type', 'Representative route']);
    rows.push(['Side', data.side || '—']);
    rows.push(['Target', data.target || '—']);
    rows.push(['Distance', `${data.distance ?? '—'} u`]);
  }
  if (hit.point) {
    rows.push(['Hit point', `${hit.point.x.toFixed(1)}, ${hit.point.y.toFixed(1)}, ${hit.point.z.toFixed(1)}`]);
  }
  return rows;
}

function showSelection(hit) {
  const rows = selectionRows(hit);
  const list = $('selection-data');
  list.replaceChildren();
  for (const [label, value] of rows) {
    const row = document.createElement('div');
    const dt = document.createElement('dt');
    const dd = document.createElement('dd');
    dt.textContent = label;
    dd.textContent = value;
    row.append(dt, dd);
    list.append(row);
  }
  list.hidden = false;
  $('selection-empty').hidden = true;
}

function clearSelection() {
  $('selection-data').hidden = true;
  $('selection-data').replaceChildren();
  $('selection-empty').hidden = false;
}

function pick(event) {
  if (!state.ready || !state.camera) return;
  const rect = $('canvas').getBoundingClientRect();
  const ndc = new THREE.Vector2(
    ((event.clientX - rect.left) / rect.width) * 2 - 1,
    -((event.clientY - rect.top) / rect.height) * 2 + 1,
  );
  const raycaster = new THREE.Raycaster();
  raycaster.setFromCamera(ndc, state.camera);
  const candidates = state.pickables.filter(isVisible);
  const hits = raycaster.intersectObjects(candidates, false);
  if (!hits.length) {
    clearSelection();
    return;
  }
  showSelection(hits[0]);
}

function render() {
  if (!state.renderer || !state.scene || !state.camera) return;
  state.renderer.render(state.scene, state.camera);
  state.needsRender = false;
  state.frames += 1;
  const now = performance.now();
  if (now - state.fpsTimer >= 500) {
    const fps = Math.round((state.frames * 1000) / (now - state.fpsTimer));
    $('stat-fps').textContent = `${fps} fps`;
    state.frames = 0;
    state.fpsTimer = now;
  }
  $('stat-calls').textContent = `${state.renderer.info.render.calls} draws`;
  updateCompass();
}

function updateCompass() {
  if (!state.controls) return;
  const dx = state.camera.position.x - state.controls.target.x;
  const dy = state.camera.position.y - state.controls.target.y;
  const angle = Math.atan2(dy, dx) * (180 / Math.PI);
  const needle = $('compass-needle');
  if (needle) needle.style.transform = `rotate(${angle}deg)`;
}

function tick() {
  if (document.hidden) {
    requestAnimationFrame(tick);
    return;
  }
  const changed = state.controls ? state.controls.update() : false;
  if (state.needsRender || changed) render();
  requestAnimationFrame(tick);
}

function bindControls() {
  document.querySelectorAll('[data-view]').forEach((button) => {
    button.addEventListener('click', () => {
      if (button.dataset.view === 'fit') fitView();
      if (button.dataset.view === 'top') topView();
      if (button.dataset.view === 'iso') isoView();
    });
  });
  $('reset-view').addEventListener('click', fitView);
  $('open-tab').addEventListener('click', () => window.open(location.href, '_blank', 'noopener'));
  if (window.top === window) $('open-tab').hidden = true;
  $('toggle-left').addEventListener('click', () => $('left-panel').classList.toggle('open'));
  for (const key of LAYER_KEYS) {
    const input = document.querySelector(`[data-layer="${key}"]`);
    input.addEventListener('change', () => {
      state.layers[key] = input.checked;
      applyLayers();
      saveSettings();
    });
  }
  $('quality').addEventListener('change', () => {
    state.quality = $('quality').value;
    setQuality();
    saveSettings();
  });
  $('remember').addEventListener('change', () => {
    state.remember = $('remember').checked;
    if (!state.remember) {
      try {
        localStorage.removeItem(SETTINGS_KEY);
      } catch {
        /* ignore */
      }
    } else {
      saveSettings();
    }
  });
  $('reset-layers').addEventListener('click', () => {
    state.layers = { ...DEFAULT_LAYERS };
    state.quality = 'balanced';
    syncControls();
    applyLayers();
    setQuality();
    saveSettings();
  });
  const canvas = $('canvas');
  let down = null;
  canvas.addEventListener('pointerdown', (event) => {
    down = { x: event.clientX, y: event.clientY };
  });
  canvas.addEventListener('pointerup', (event) => {
    if (!down) return;
    const moved = Math.hypot(event.clientX - down.x, event.clientY - down.y);
    down = null;
    if (moved < 4) pick(event);
  });
  window.addEventListener('keydown', (event) => {
    if (event.target.matches('input, select, textarea')) return;
    const key = event.key.toLowerCase();
    if (key === 'f') fitView();
    if (key === 't') topView();
    if (key === 'i') isoView();
    if (key === 'r') fitView();
    if (key === 'c') toggleLayer('collision');
    if (key === 'n') toggleLayer('nav');
    if (key === 'e') toggleLayer('entities');
  });
  window.addEventListener('message', (event) => {
    if (event.origin !== location.origin) return;
    if (event.data?.type === 'cs2mb:viewer-settings') {
      applySettings(event.data.settings, false);
    }
  });
}

function toggleLayer(key) {
  if (!(key in state.layers)) return;
  state.layers[key] = !state.layers[key];
  syncControls();
  applyLayers();
  saveSettings();
}

async function boot() {
  try {
    const response = await fetch('./data.json', { cache: 'no-store' });
    if (!response.ok) throw new Error(`data.json returned HTTP ${response.status}`);
    const data = await response.json();
    validateData(data);
    state.data = data;
    state.settings = readSettings();
    state.layers = state.settings.layers;
    state.quality = state.settings.quality;
    state.remember = state.settings.remember;
    $('map-name').textContent = data.map;
    $('status-source').textContent = `SRI collision · CS2 NAV · ${num(data.stats.collision_triangles)} tris`;
    setStats();
    syncControls();
    initRenderer();
    addGrid();
    buildNav();
    buildEntities();
    buildRoutes();
    bindControls();
    applyLayers();
    setQuality();
    try {
      await loadCollision();
    } catch (error) {
      notice = 'Collision geometry unavailable; showing NAV and entities only.';
      state.collisionError = `${error?.name || 'Error'}: ${error?.message || error}`;
      state.collisionStack = String(error?.stack || '');
      $('status-source').textContent = notice;
      console.warn('3DsVW collision load failed:', state.collisionError);
    }
    fitView();
    state.ready = true;
    $('loading').hidden = true;
    $('error').hidden = true;
    render();
    tick();
  } catch (error) {
    console.error(error);
    showError(error?.message || 'Unable to load 3DsVW data.');
  }
}

window.__cs2mbViewer = state;
if (window.top !== window) document.body.classList.add('embedded');
boot();

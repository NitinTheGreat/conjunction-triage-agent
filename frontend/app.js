/**
 * ConjunctionTriage — 3D conjunction geometry viewer.
 *
 * Renders both objects of every sampled conjunction at their ECI position at TCA, with a
 * line joining each pair. Everything is offline: three.js is vendored in ./lib and the
 * only fetches are the two local JSON files.
 *
 * Rendering approach: two buffered geometries total — one THREE.Points for all object
 * markers and one THREE.LineSegments for all pair lines — rather than a mesh per object.
 * Filtering rewrites the buffers in place and adjusts the draw range, so changing a
 * filter costs one array pass rather than rebuilding the scene graph.
 */

import * as THREE from 'three';
import { OrbitControls } from './lib/OrbitControls.js';
import { renderCharts } from './charts.js';

const EARTH_RADIUS_KM = 6378.137;
const PC_FLOOR = 1e-10;
const ACTION_THRESHOLD = 1e-4;
/** Scene units are 1000 km, keeping coordinates small and depth precision comfortable. */
const SCALE = 1 / 1000;

// ---------------------------------------------------------------------------------------
// colour encoding
// ---------------------------------------------------------------------------------------

/** Continuous ramp for uncensored Pc, blue (low) through red (high). */
const PC_RAMP = [
  [0.00, [0.169, 0.247, 0.839]],
  [0.20, [0.133, 0.694, 0.839]],
  [0.40, [0.247, 0.816, 0.478]],
  [0.60, [1.000, 0.847, 0.302]],
  [0.80, [1.000, 0.549, 0.204]],
  [1.00, [1.000, 0.184, 0.184]],
];

/**
 * Censored and null Pc are given flat, deliberately desaturated colours that sit off the
 * continuous ramp entirely. A censored value is a bound, not a measurement, so placing it
 * at the ramp's low end would assert something the data does not say.
 */
const COLOUR_CENSORED = [0.533, 0.569, 0.659];
const COLOUR_NULL = [0.698, 0.420, 0.847];

function pcColour(event) {
  if (event.pc === null || event.pc === undefined) return COLOUR_NULL;
  if (event.pc_is_floored) return COLOUR_CENSORED;
  // log-scale position between the floor and the action threshold.
  const lo = Math.log10(PC_FLOOR);
  const hi = Math.log10(ACTION_THRESHOLD);
  const t = Math.min(1, Math.max(0, (Math.log10(event.pc) - lo) / (hi - lo)));
  for (let i = 1; i < PC_RAMP.length; i++) {
    if (t <= PC_RAMP[i][0]) {
      const [t0, c0] = PC_RAMP[i - 1];
      const [t1, c1] = PC_RAMP[i];
      const k = (t - t0) / (t1 - t0);
      return [0, 1, 2].map((j) => c0[j] + k * (c1[j] - c0[j]));
    }
  }
  return PC_RAMP[PC_RAMP.length - 1][1];
}

// ---------------------------------------------------------------------------------------
// state
// ---------------------------------------------------------------------------------------

let events = [];
let summary = null;
let visible = [];            // indices of events passing the current filters
let selected = null;

const filters = {
  source: 'all',
  altitude: 'all',
  dilution: 'all',
  minPc: -11,               // log10; -11 means "no minimum"
  includeCensored: true,
  includeNull: true,
  maxMiss: 70,
};

// ---------------------------------------------------------------------------------------
// scene
// ---------------------------------------------------------------------------------------

const canvas = document.getElementById('c');
const renderer = new THREE.WebGLRenderer({ canvas, antialias: true });
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));

const scene = new THREE.Scene();
scene.background = new THREE.Color(0x07090f);

const camera = new THREE.PerspectiveCamera(45, 1, 0.1, 2000);
camera.position.set(16, 9, 16);

const controls = new OrbitControls(camera, renderer.domElement);
controls.enableDamping = true;
controls.dampingFactor = 0.07;
controls.minDistance = 7;
controls.maxDistance = 400;

scene.add(new THREE.AmbientLight(0xffffff, 0.55));
const sun = new THREE.DirectionalLight(0xffffff, 1.7);
sun.position.set(5, 3, 5);
scene.add(sun);

// --- Earth: procedurally shaded, no texture fetched (constraint 3) ---------------------
const earthRadius = EARTH_RADIUS_KM * SCALE;
const earth = new THREE.Mesh(
  new THREE.SphereGeometry(earthRadius, 64, 48),
  new THREE.MeshPhongMaterial({ color: 0x16406e, emissive: 0x04101f, shininess: 12, flatShading: false }),
);
scene.add(earth);

scene.add(new THREE.Mesh(
  new THREE.SphereGeometry(earthRadius * 1.015, 48, 32),
  new THREE.MeshBasicMaterial({ color: 0x2f7fd0, transparent: true, opacity: 0.10, side: THREE.BackSide }),
));

/** Lat/long graticule so orientation is readable without a texture. */
function graticule() {
  const points = [];
  const push = (a, b) => { points.push(a.x, a.y, a.z, b.x, b.y, b.z); };
  const at = (latDeg, lonDeg, r) => {
    const lat = THREE.MathUtils.degToRad(latDeg);
    const lon = THREE.MathUtils.degToRad(lonDeg);
    return new THREE.Vector3(
      r * Math.cos(lat) * Math.cos(lon),
      r * Math.sin(lat),
      -r * Math.cos(lat) * Math.sin(lon),
    );
  };
  const r = earthRadius * 1.002;
  for (let lat = -60; lat <= 60; lat += 30) {
    for (let lon = 0; lon < 360; lon += 5) push(at(lat, lon, r), at(lat, lon + 5, r));
  }
  for (let lon = 0; lon < 360; lon += 30) {
    for (let lat = -90; lat < 90; lat += 5) push(at(lat, lon, r), at(lat + 5, lon, r));
  }
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute('position', new THREE.Float32BufferAttribute(points, 3));
  return new THREE.LineSegments(
    geometry,
    new THREE.LineBasicMaterial({ color: 0x3d8ac4, transparent: true, opacity: 0.22 }),
  );
}
scene.add(graticule());

/** Equator, highlighted separately from the graticule. */
const equatorPoints = [];
for (let i = 0; i <= 256; i++) {
  const a = (i / 256) * Math.PI * 2;
  equatorPoints.push(new THREE.Vector3(Math.cos(a), 0, Math.sin(a)).multiplyScalar(earthRadius * 1.004));
}
scene.add(new THREE.Line(
  new THREE.BufferGeometry().setFromPoints(equatorPoints),
  new THREE.LineBasicMaterial({ color: 0x7fd4ff, transparent: true, opacity: 0.75 }),
));

/** Polar axis, extended past the poles so north/south is unambiguous. */
scene.add(new THREE.Line(
  new THREE.BufferGeometry().setFromPoints([
    new THREE.Vector3(0, -earthRadius * 1.45, 0),
    new THREE.Vector3(0, earthRadius * 1.45, 0),
  ]),
  new THREE.LineBasicMaterial({ color: 0xffd88a, transparent: true, opacity: 0.6 }),
));

// --- object markers and pair lines -----------------------------------------------------

/** Round sprite, drawn on a canvas so nothing is fetched. */
function discTexture(ring) {
  const size = 64;
  const c = document.createElement('canvas');
  c.width = c.height = size;
  const g = c.getContext('2d');
  g.clearRect(0, 0, size, size);
  if (ring) {
    g.strokeStyle = '#ffb638';
    g.lineWidth = 7;
    g.beginPath();
    g.arc(size / 2, size / 2, size / 2 - 6, 0, Math.PI * 2);
    g.stroke();
  } else {
    const grad = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
    grad.addColorStop(0, 'rgba(255,255,255,1)');
    grad.addColorStop(0.45, 'rgba(255,255,255,0.95)');
    grad.addColorStop(1, 'rgba(255,255,255,0)');
    g.fillStyle = grad;
    g.beginPath();
    g.arc(size / 2, size / 2, size / 2, 0, Math.PI * 2);
    g.fill();
  }
  const texture = new THREE.CanvasTexture(c);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

let pointGeometry, pointCloud, lineGeometry, lineSegments, ringGeometry, ringCloud;

function buildBuffers(total) {
  // Two vertices per event (one per object) for points and rings; two for each line.
  pointGeometry = new THREE.BufferGeometry();
  pointGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(total * 2 * 3), 3));
  pointGeometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(total * 2 * 3), 3));
  pointCloud = new THREE.Points(pointGeometry, new THREE.PointsMaterial({
    size: 0.42, sizeAttenuation: true, vertexColors: true,
    map: discTexture(false), transparent: true, alphaTest: 0.12, depthWrite: false,
  }));
  scene.add(pointCloud);

  ringGeometry = new THREE.BufferGeometry();
  ringGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(total * 2 * 3), 3));
  ringCloud = new THREE.Points(ringGeometry, new THREE.PointsMaterial({
    size: 0.95, sizeAttenuation: true, color: 0xffb638,
    map: discTexture(true), transparent: true, alphaTest: 0.08, depthWrite: false, opacity: 0.9,
  }));
  scene.add(ringCloud);

  lineGeometry = new THREE.BufferGeometry();
  lineGeometry.setAttribute('position', new THREE.BufferAttribute(new Float32Array(total * 2 * 3), 3));
  lineGeometry.setAttribute('color', new THREE.BufferAttribute(new Float32Array(total * 2 * 3), 3));
  lineSegments = new THREE.LineSegments(lineGeometry, new THREE.LineBasicMaterial({
    vertexColors: true, transparent: true, opacity: 0.55,
  }));
  scene.add(lineSegments);
}

// ---------------------------------------------------------------------------------------
// filtering
// ---------------------------------------------------------------------------------------

function passes(event) {
  if (filters.source !== 'all' && event.source !== filters.source) return false;

  if (filters.altitude !== 'all') {
    const altitude = event.objects[0].altitude_km;
    if (filters.altitude === 'leo' && !(altitude < 2000)) return false;
    if (filters.altitude === 'meo' && !(altitude >= 2000 && altitude < 35000)) return false;
    if (filters.altitude === 'geo' && !(altitude >= 35000)) return false;
  }

  if (filters.dilution === 'robust' && event.dilution !== 0) return false;
  if (filters.dilution === 'diluted' && event.dilution !== 1) return false;

  if (event.miss_distance_km > filters.maxMiss) return false;

  const isNull = event.pc === null || event.pc === undefined;
  if (isNull) return filters.includeNull;
  if (event.pc_is_floored) return filters.includeCensored;
  // The Pc slider applies only to uncensored values; a censored record has no magnitude
  // to compare against, so it is governed by its own toggle instead.
  if (filters.minPc > -11 && Math.log10(event.pc) < filters.minPc) return false;
  return true;
}

function applyFilters() {
  visible = [];
  const positions = pointGeometry.attributes.position.array;
  const colours = pointGeometry.attributes.color.array;
  const linePositions = lineGeometry.attributes.position.array;
  const lineColours = lineGeometry.attributes.color.array;
  const ringPositions = ringGeometry.attributes.position.array;

  let point = 0;
  let ring = 0;

  for (let i = 0; i < events.length; i++) {
    const event = events[i];
    if (!passes(event)) continue;
    visible.push(i);

    const colour = pcColour(event);
    for (let o = 0; o < 2; o++) {
      const p = event.objects[o].position_km;
      const base = point * 3;
      positions[base] = p[0] * SCALE;
      positions[base + 1] = p[2] * SCALE;   // ECI z is "up"; three.js y is up
      positions[base + 2] = -p[1] * SCALE;
      colours[base] = colour[0];
      colours[base + 1] = colour[1];
      colours[base + 2] = colour[2];

      linePositions[base] = positions[base];
      linePositions[base + 1] = positions[base + 1];
      linePositions[base + 2] = positions[base + 2];
      lineColours[base] = colour[0];
      lineColours[base + 1] = colour[1];
      lineColours[base + 2] = colour[2];

      if (event.dilution === 1) {
        const r = ring * 3;
        ringPositions[r] = positions[base];
        ringPositions[r + 1] = positions[base + 1];
        ringPositions[r + 2] = positions[base + 2];
        ring++;
      }
      point++;
    }
  }

  pointGeometry.attributes.position.needsUpdate = true;
  pointGeometry.attributes.color.needsUpdate = true;
  lineGeometry.attributes.position.needsUpdate = true;
  lineGeometry.attributes.color.needsUpdate = true;
  ringGeometry.attributes.position.needsUpdate = true;
  pointGeometry.setDrawRange(0, point);
  lineGeometry.setDrawRange(0, point);
  ringGeometry.setDrawRange(0, ring);
  pointGeometry.computeBoundingSphere();

  document.getElementById('shown-count').textContent = visible.length.toLocaleString();
}

// ---------------------------------------------------------------------------------------
// picking
// ---------------------------------------------------------------------------------------

const raycaster = new THREE.Raycaster();
raycaster.params.Points.threshold = 0.32;
const pointer = new THREE.Vector2();

renderer.domElement.addEventListener('click', (e) => {
  const rect = renderer.domElement.getBoundingClientRect();
  pointer.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
  pointer.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;
  raycaster.setFromCamera(pointer, camera);

  const hits = raycaster.intersectObject(pointCloud, false)
    .filter((h) => h.index < pointGeometry.drawRange.count)
    .sort((a, b) => a.distanceToRay - b.distanceToRay);
  if (!hits.length) return;

  // Two vertices per event, in `visible` order.
  const eventIndex = visible[Math.floor(hits[0].index / 2)];
  const objectIndex = hits[0].index % 2;
  if (eventIndex !== undefined) showDetail(events[eventIndex], objectIndex);
});

// ---------------------------------------------------------------------------------------
// detail panel
// ---------------------------------------------------------------------------------------

const fmt = (v, digits = 4) =>
  v === null || v === undefined ? '—' :
  (Math.abs(v) !== 0 && (Math.abs(v) < 1e-3 || Math.abs(v) >= 1e6))
    ? v.toExponential(digits) : Number(v.toFixed(digits)).toLocaleString();

function objectCard(object, index, highlight) {
  return `
    <div class="objcard" ${highlight ? 'style="border-color:var(--accent)"' : ''}>
      <h3>Object ${index + 1} — ${object.catalog_id}${highlight ? ' ◄' : ''}</h3>
      <dl class="kv">
        <dt>Altitude</dt><dd>${fmt(object.altitude_km, 1)} km</dd>
        <dt>Position X</dt><dd>${fmt(object.position_km[0], 1)} km</dd>
        <dt>Position Y</dt><dd>${fmt(object.position_km[1], 1)} km</dd>
        <dt>Position Z</dt><dd>${fmt(object.position_km[2], 1)} km</dd>
        <dt>Speed</dt><dd>${fmt(Math.hypot(...object.velocity_kms), 3)} km/s</dd>
        <dt>Hard-body radius</dt><dd>${fmt(object.hbr_m, 4)} m</dd>
        <dt>Covariance σ²<sub>max</sub></dt><dd>${fmt(object.cov_max_eigenvalue_km2, 3)} km²</dd>
        <dt>Position σ<sub>max</sub></dt><dd>${object.cov_max_eigenvalue_km2 === null ? '—'
          : fmt(Math.sqrt(object.cov_max_eigenvalue_km2), 3) + ' km'}</dd>
        <dt>Met screening criteria</dt><dd>${object.met_criteria ? 'yes' : 'no'}</dd>
      </dl>
    </div>`;
}

function showDetail(event, objectIndex) {
  selected = event;
  const isNull = event.pc === null || event.pc === undefined;

  let pcStatus;
  if (isNull) {
    pcStatus = `<div class="status nullpc"><strong>No collision probability.</strong>
      P<sub>c</sub> could not be computed for this event — per the Users Guide, most likely
      because the covariance at TCA is not positive-definite.</div>`;
  } else if (event.pc_is_floored) {
    pcStatus = `<div class="status censored"><strong>Censored.</strong>
      P<sub>c</sub> sits at the 1e-10 reporting floor. This is an <em>upper bound</em>, not a
      measurement — the true probability is somewhere at or below it. The floor itself is
      inferred from the data; the Users Guide does not document it.</div>`;
  } else {
    pcStatus = `<div class="status ${event.pc >= ACTION_THRESHOLD ? 'diluted' : 'robust'}">
      <strong>P<sub>c</sub> = ${event.pc.toExponential(4)}</strong> — a computed value
      ${event.pc >= ACTION_THRESHOLD
        ? 'at or above the 1e-4 operational manoeuvre threshold.'
        : 'below the 1e-4 operational manoeuvre threshold.'}</div>`;
  }

  const dilutionStatus = event.dilution === 1
    ? `<div class="status diluted"><strong>Covariance diluted (dilution = 1).</strong>
       The uncertainty is large enough that P<sub>c</sub> has passed its maximum on the
       P<sub>c</sub>-versus-scale-factor curve, so a lower value here reflects <em>worse</em>
       knowledge rather than lower risk. Treat this P<sub>c</sub> as unreliable.</div>`
    : event.dilution === 0
      ? `<div class="status robust"><strong>Covariance robust (dilution = 0).</strong>
         The uncertainty is on the trustworthy side of the P<sub>c</sub> curve.</div>`
      : `<div class="status nullpc"><strong>Dilution unknown.</strong> Not reported for this event.</div>`;

  document.getElementById('detail').innerHTML = `
    <h2>Event detail</h2>
    <dl class="kv">
      <dt>Event</dt><dd style="font-size:11px">${event.event_id}</dd>
      <dt>Conjunction id</dt><dd>${event.conj_id}</dd>
      <dt>Answer key</dt><dd>${event.source === 'TRACSS_SPHERICAL' ? 'Spherical' : 'SFSH'}</dd>
      <dt>TCA (UTC)</dt><dd style="font-size:11px">${event.tca.replace('T', ' ').replace('Z', '')}</dd>
      <dt>Miss distance</dt><dd>${fmt(event.miss_distance_km, 4)} km</dd>
      <dt>Relative speed</dt><dd>${fmt(event.relative_speed_kms, 4)} km/s</dd>
      <dt>Mahalanobis distance</dt><dd>${fmt(event.mahalanobis_distance, 4)} σ</dd>
    </dl>
    ${pcStatus}
    ${dilutionStatus}
    <h2>Objects</h2>
    <div class="objgrid">
      ${objectCard(event.objects[0], 0, objectIndex === 0)}
      ${objectCard(event.objects[1], 1, objectIndex === 1)}
    </div>
    <h2>Sampling</h2>
    <dl class="kv"><dt>Stratum</dt><dd style="font-size:11px">${event.stratum}</dd></dl>
    <div class="notice">Positions are at <strong>time of closest approach</strong>, not live.
      Public orbital data must not be used for operational collision avoidance.</div>`;
}

// ---------------------------------------------------------------------------------------
// controls wiring
// ---------------------------------------------------------------------------------------

function wire() {
  const bind = (id, handler, eventName = 'change') =>
    document.getElementById(id).addEventListener(eventName, handler);

  bind('f-source', (e) => { filters.source = e.target.value; applyFilters(); });
  bind('f-altitude', (e) => { filters.altitude = e.target.value; applyFilters(); });
  bind('f-dilution', (e) => { filters.dilution = e.target.value; applyFilters(); });
  bind('f-censored', (e) => { filters.includeCensored = e.target.checked; applyFilters(); });
  bind('f-null', (e) => { filters.includeNull = e.target.checked; applyFilters(); });

  bind('f-pc', (e) => {
    filters.minPc = parseFloat(e.target.value);
    document.getElementById('f-pc-val').textContent =
      filters.minPc <= -11 ? 'any' : `≥ 1e${filters.minPc}`;
    applyFilters();
  }, 'input');

  bind('f-miss', (e) => {
    filters.maxMiss = parseFloat(e.target.value);
    document.getElementById('f-miss-val').textContent = `${filters.maxMiss} km`;
    applyFilters();
  }, 'input');

  bind('reset', () => {
    Object.assign(filters, {
      source: 'all', altitude: 'all', dilution: 'all', minPc: -11,
      includeCensored: true, includeNull: true, maxMiss: 70,
    });
    document.getElementById('f-source').value = 'all';
    document.getElementById('f-altitude').value = 'all';
    document.getElementById('f-dilution').value = 'all';
    document.getElementById('f-pc').value = -11;
    document.getElementById('f-pc-val').textContent = 'any';
    document.getElementById('f-miss').value = 70;
    document.getElementById('f-miss-val').textContent = '70 km';
    document.getElementById('f-censored').checked = true;
    document.getElementById('f-null').checked = true;
    applyFilters();
  }, 'click');

  // Phase 3 had two tabs and switched them with a boolean. Phase 9 adds three more, so
  // the switch is driven off `aria-controls` instead. Every `.view` is hidden and one is
  // shown, which keeps the two original views behaving exactly as they did.
  const tabs = [...document.querySelectorAll('.tab')];
  const show = (viewId) => {
    for (const view of document.querySelectorAll('.view')) view.hidden = view.id !== viewId;
    for (const tab of tabs) {
      tab.setAttribute('aria-selected', String(tab.getAttribute('aria-controls') === viewId));
    }
    if (viewId === 'scene-view') resize();
    dispatchEvent(new CustomEvent('viewchange', { detail: { viewId } }));
  };
  for (const tab of tabs) {
    tab.addEventListener('click', () => show(tab.getAttribute('aria-controls')));
  }
  window.showView = show;
}

// ---------------------------------------------------------------------------------------
// loop
// ---------------------------------------------------------------------------------------

function resize() {
  const wrap = document.getElementById('canvas-wrap');
  const { clientWidth: w, clientHeight: h } = wrap;
  if (!w || !h) return;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
addEventListener('resize', resize);

let frames = 0;
let lastSecond = performance.now();
let fps = 0;

function animate() {
  requestAnimationFrame(animate);
  controls.update();
  renderer.render(scene, camera);

  frames++;
  const now = performance.now();
  if (now - lastSecond >= 1000) {
    fps = frames;
    frames = 0;
    lastSecond = now;
    document.getElementById('hud').textContent =
      `${fps} fps · ${visible.length.toLocaleString()} events · ` +
      `${(visible.length * 2).toLocaleString()} objects · ${visible.length.toLocaleString()} lines`;
  }
}

// ---------------------------------------------------------------------------------------
// boot
// ---------------------------------------------------------------------------------------

async function main() {
  const [eventData, summaryData] = await Promise.all([
    fetch('./data/events.json').then((r) => r.json()),
    fetch('./data/summary.json').then((r) => r.json()),
  ]);
  events = eventData;
  summary = summaryData;

  document.getElementById('sample-total').textContent = events.length.toLocaleString();
  const population = summary.population.events;
  document.getElementById('population-line').textContent =
    `The full dataset holds ${population.toLocaleString()} ingested events — ` +
    `this sample is ${(100 * events.length / population).toFixed(2)}% of it, and is ` +
    `deliberately weighted toward rare high-probability cases.`;
  document.getElementById('pop-n').textContent = population.toLocaleString();
  document.getElementById('samp-n').textContent = events.length.toLocaleString();

  const excluded = summary.sample.excluded_unrenderable || {};
  const excludedTotal = Object.values(excluded).reduce((a, b) => a + b, 0);
  if (excludedTotal > 0) {
    const notice = document.createElement('div');
    notice.className = 'notice hard';
    notice.innerHTML = `<strong>${excludedTotal} sampled event(s) are not rendered</strong>
      because their positions are not finite: ${JSON.stringify(excluded)}. They are counted
      here rather than dropped silently.`;
    document.querySelector('aside.left').prepend(notice);
  }

  buildBuffers(events.length);
  wire();
  applyFilters();
  renderCharts(document.getElementById('charts'), summary, events);

  document.getElementById('loading').remove();
  resize();
  animate();
}

main().catch((error) => {
  document.getElementById('loading').innerHTML =
    `<div style="color:#ff5c5c;max-width:520px;text-align:center">
       <strong>Failed to load.</strong><br>${error}<br><br>
       This page reads ./data/events.json, so it must be served over HTTP
       (<code>python -m http.server</code> from the viz/ directory) rather than opened
       directly from the filesystem.
     </div>`;
  throw error;
});

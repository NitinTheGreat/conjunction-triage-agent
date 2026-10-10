"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import { EARTH_RADIUS, atlasTexture, latitudeLongitude, markerTexture } from "@/components/planet-scene";
import { decodeLand, type LandTopology } from "@/lib/land";
import { palette } from "@/lib/findings";

export type GlobeTarget = { kind: "observation"; id: number } | { kind: "message"; index: number };
export type GlobeHover = GlobeTarget & { x: number; y: number };

type LineageGlobeProps = {
  windows: number[][];
  availability: number[];
  messageTimes: number[];
  message: number;
  highlight: number | null;
  paused: boolean;
  onHover: (target: GlobeHover | null) => void;
  onSelectMessage: (index: number) => void;
};

const ORBIT_RADIUS = 10.6;
const RAIL_RADIUS = 14.2;
const FUTURE = 60;
// Angles in degrees along the observed track, with closest approach at 0. Observations keep their
// time order; messages sit on an outer rail above the observations they summarise.
const OBSERVATION_ARC: [number, number] = [-150, -50];
const FUTURE_ARC: [number, number] = [-36, -8];
const RAIL_ARC: [number, number] = [-136, -58];

/** Illustrative geometry: days of tracking are compressed into one orbit. */
function orbitFrame(normal: THREE.Vector3, through: THREE.Vector3) {
  const u = through.clone().normalize();
  const w = new THREE.Vector3().crossVectors(normal, u).normalize();
  return (degrees: number, radius = ORBIT_RADIUS) => {
    const angle = THREE.MathUtils.degToRad(degrees);
    return u.clone().multiplyScalar(Math.cos(angle) * radius).add(w.clone().multiplyScalar(Math.sin(angle) * radius));
  };
}

function labelSprite(text: string) {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 64;
  const ctx = canvas.getContext("2d")!;
  ctx.font = "500 34px 'IBM Plex Mono', Consolas, monospace";
  ctx.fillStyle = "#f5f1e8";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  ctx.fillText(text, 64, 34);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: texture, transparent: true, depthWrite: false, depthTest: false }));
  sprite.scale.set(0.9, 0.45, 1);
  sprite.renderOrder = 6;
  return sprite;
}

export default function LineageGlobe({ windows, availability, messageTimes, message, highlight, paused, onHover, onSelectMessage }: LineageGlobeProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const apiRef = useRef<{ refresh: () => void } | null>(null);
  const stateRef = useRef({ windows, message, highlight, paused, onHover, onSelectMessage });
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    stateRef.current = { windows, message, highlight, paused, onHover, onSelectMessage };
    apiRef.current?.refresh();
  }, [windows, message, highlight, paused, onHover, onSelectMessage]);

  useEffect(() => {
    const host = hostRef.current;
    if (!host) return;
    let renderer: THREE.WebGLRenderer;
    try {
      renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true, powerPreference: "low-power" });
    } catch {
      let cancelled = false;
      queueMicrotask(() => { if (!cancelled) setFailed(true); });
      return () => { cancelled = true; };
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.5;
    renderer.setClearColor("#25271e", 0);
    renderer.domElement.setAttribute("role", "img");
    renderer.domElement.setAttribute("aria-label", "Illustrative globe. One satellite's track carries the observations behind six conjunction messages; each message is drawn as a fan of lines to the observations it used. Drag to rotate. The same information is available in the controls and tables on this page.");
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(36, 1, 0.1, 500);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.07;
    controls.enablePan = false;
    controls.minDistance = 18;
    controls.maxDistance = 60;

    scene.add(new THREE.AmbientLight("#cdc49c", 0.7));
    const sun = new THREE.DirectionalLight("#ffedc2", 3.2);
    sun.position.set(-12, 12, 16);
    scene.add(sun);
    const rim = new THREE.DirectionalLight("#c8a766", 1.4);
    rim.position.set(13, -3, -12);
    scene.add(rim);

    let surface = atlasTexture();
    surface.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 4);
    const earthMaterial = new THREE.MeshStandardMaterial({ map: surface, roughness: 0.98, metalness: 0.08 });
    const earth = new THREE.Group();
    earth.add(new THREE.Mesh(new THREE.SphereGeometry(EARTH_RADIUS, 96, 64), earthMaterial));
    earth.add(latitudeLongitude(EARTH_RADIUS * 1.003));
    scene.add(earth);
    scene.add(new THREE.Mesh(new THREE.SphereGeometry(EARTH_RADIUS * 1.025, 64, 48), new THREE.ShaderMaterial({
      uniforms: { glowColor: { value: new THREE.Color("#beb772") } },
      vertexShader: "varying vec3 vNormal; varying vec3 vPosition; void main(){vNormal=normalize(normalMatrix*normal); vec4 mvPosition=modelViewMatrix*vec4(position,1.0);vPosition=-mvPosition.xyz;gl_Position=projectionMatrix*mvPosition;}",
      fragmentShader: "uniform vec3 glowColor;varying vec3 vNormal;varying vec3 vPosition;void main(){float intensity=pow(1.0-abs(dot(normalize(vNormal),normalize(vPosition))),3.8);gl_FragColor=vec4(glowColor,intensity*0.3);}",
      transparent: true, depthWrite: false, side: THREE.BackSide, blending: THREE.AdditiveBlending,
    })));

    // Two orbital planes that cross at the encounter point, which is placed at 0 degrees on both tracks.
    const normalA = new THREE.Vector3(0.22, 1, 0.12).normalize();
    const normalB = new THREE.Vector3(-0.62, 0.66, 0.42).normalize();
    const encounter = new THREE.Vector3().crossVectors(normalA, normalB).normalize().multiplyScalar(ORBIT_RADIUS);
    const trackA = orbitFrame(normalA, encounter);
    const trackB = orbitFrame(normalB, encounter);
    const ring = (track: (degrees: number, radius?: number) => THREE.Vector3, color: string, opacity: number, radius = ORBIT_RADIUS) => {
      const points = Array.from({ length: 361 }, (_, i) => track(i - 180, radius));
      return new THREE.Line(new THREE.BufferGeometry().setFromPoints(points), new THREE.LineBasicMaterial({ color, transparent: true, opacity }));
    };
    scene.add(ring(trackA, "#dedf9f", 0.42), ring(trackB, "#c6875e", 0.42, ORBIT_RADIUS + 0.16));
    const pulse = new THREE.Sprite(new THREE.SpriteMaterial({ map: markerTexture(true), color: palette.acid, transparent: true, opacity: 0.9, depthWrite: false }));
    pulse.position.copy(encounter);
    pulse.scale.set(0.9, 0.9, 1);
    scene.add(pulse);
    const encounterLabel = labelSprite("TCA");
    encounterLabel.position.copy(encounter.clone().multiplyScalar(1.09));
    scene.add(encounterLabel);

    // Observations sit just outside the observed track at the time they became available.
    const angleOf = (id: number) => id < FUTURE
      ? OBSERVATION_ARC[0] + (OBSERVATION_ARC[1] - OBSERVATION_ARC[0]) * id / (FUTURE - 1)
      : FUTURE_ARC[0] + (FUTURE_ARC[1] - FUTURE_ARC[0]) * (id - FUTURE) / Math.max(1, availability.length - FUTURE - 1);
    const observationPositions = availability.map((_, id) => trackA(angleOf(id), ORBIT_RADIUS + 0.09));
    const observationGeometry = new THREE.BufferGeometry();
    observationGeometry.setAttribute("position", new THREE.Float32BufferAttribute(observationPositions.slice(0, FUTURE).flatMap((p) => p.toArray()), 3));
    observationGeometry.setAttribute("color", new THREE.Float32BufferAttribute(new Array(FUTURE * 3).fill(0.5), 3));
    const disc = markerTexture();
    const observations = new THREE.Points(observationGeometry, new THREE.PointsMaterial({ vertexColors: true, map: disc, size: 12, sizeAttenuation: false, transparent: true, depthWrite: false, alphaTest: 0.02 }));
    observations.renderOrder = 3;
    const future = new THREE.Points(new THREE.BufferGeometry().setFromPoints(observationPositions.slice(FUTURE)), new THREE.PointsMaterial({ map: markerTexture(true), color: "#8e9078", size: 7, sizeAttenuation: false, transparent: true, opacity: 0.55, depthWrite: false }));
    const focus = new THREE.Points(new THREE.BufferGeometry(), new THREE.PointsMaterial({ map: markerTexture(true), color: palette.acid, size: 22, sizeAttenuation: false, transparent: true, depthWrite: false, depthTest: false }));
    focus.renderOrder = 8;
    scene.add(observations, future, focus);

    const rail = Array.from({ length: 121 }, (_, i) => trackA(RAIL_ARC[0] - 9 + (RAIL_ARC[1] - RAIL_ARC[0] + 18) * i / 120, RAIL_RADIUS));
    scene.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(rail), new THREE.LineBasicMaterial({ color: "#7d806a", transparent: true, opacity: 0.55 })));
    const messageMarkers = messageTimes.map((_, index) => {
      const angle = RAIL_ARC[0] + (RAIL_ARC[1] - RAIL_ARC[0]) * index / Math.max(1, messageTimes.length - 1);
      const marker = new THREE.Mesh(new THREE.OctahedronGeometry(0.24), new THREE.MeshBasicMaterial({ color: "#e8e4da" }));
      marker.position.copy(trackA(angle, RAIL_RADIUS));
      marker.userData.index = index;
      const label = labelSprite(`m${index + 1}`);
      label.position.copy(trackA(angle, RAIL_RADIUS + 0.9));
      scene.add(marker, label);
      return marker;
    });
    const fan = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.85 }));
    fan.renderOrder = 2;
    scene.add(fan);

    // Sensor sites under the observation arc; a beam shows the site behind a focused observation.
    const sites = [8, 28, 50].map((id) => observationPositions[id].clone().normalize().multiplyScalar(EARTH_RADIUS * 1.004));
    scene.add(new THREE.Points(new THREE.BufferGeometry().setFromPoints(sites), new THREE.PointsMaterial({ color: "#f5f1e8", size: 6, sizeAttenuation: false })));
    const beam = new THREE.LineSegments(new THREE.BufferGeometry(), new THREE.LineBasicMaterial({ color: palette.acid, transparent: true, opacity: 0.75 }));
    scene.add(beam);

    const objectA = new THREE.Mesh(new THREE.SphereGeometry(0.15, 16, 16), new THREE.MeshBasicMaterial({ color: "#dedf9f" }));
    const objectB = new THREE.Mesh(new THREE.SphereGeometry(0.15, 16, 16), new THREE.MeshBasicMaterial({ color: "#c6875e" }));
    for (const [object, color] of [[objectA, "#dedf9f"], [objectB, "#c6875e"]] as const) {
      const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: disc, color, transparent: true, opacity: 0.5, depthWrite: false, blending: THREE.AdditiveBlending }));
      halo.scale.set(0.9, 0.9, 1);
      object.add(halo);
      scene.add(object);
    }

    // Look obliquely down onto the observation arc from outside it, with the Earth behind.
    const middle = trackA(-90, 1).normalize();
    const view = normalA.clone().multiplyScalar(0.5).add(middle.clone().multiplyScalar(0.87)).normalize();
    controls.target.copy(middle.clone().multiplyScalar(9).add(normalA.clone().multiplyScalar(2.2)));
    camera.position.copy(controls.target).add(view.multiplyScalar(37));
    controls.update();

    const fresh = new THREE.Color(palette.freshDark);
    const reused = new THREE.Color(palette.reusedDark);
    const used = new THREE.Color("#b9b99d");
    const unused = new THREE.Color("#4d4f40");
    const refresh = () => {
      const { windows: sets, message: current, highlight: focused } = stateRef.current;
      const selected = sets[current] ?? [];
      const earlier = new Set(sets.slice(0, current).flat());
      const anywhere = new Set(sets.flat());
      const colors = observationGeometry.getAttribute("color") as THREE.BufferAttribute;
      for (let id = 0; id < FUTURE; id++) {
        const color = selected.includes(id) ? (earlier.has(id) ? reused : fresh) : anywhere.has(id) ? used : unused;
        colors.setXYZ(id, color.r, color.g, color.b);
      }
      colors.needsUpdate = true;
      const origin = messageMarkers[current]?.position;
      const segments: number[] = [];
      const segmentColors: number[] = [];
      if (origin) for (const id of selected) {
        const color = earlier.has(id) ? reused : fresh;
        segments.push(...origin.toArray(), ...observationPositions[id].toArray());
        segmentColors.push(color.r, color.g, color.b, color.r, color.g, color.b);
      }
      fan.geometry.setAttribute("position", new THREE.Float32BufferAttribute(segments, 3));
      fan.geometry.setAttribute("color", new THREE.Float32BufferAttribute(segmentColors, 3));
      fan.geometry.computeBoundingSphere();
      messageMarkers.forEach((marker, index) => (marker.material as THREE.MeshBasicMaterial).color.set(index === current ? palette.acid : "#bdb9a8"));
      if (focused != null && focused < FUTURE) {
        focus.geometry.setAttribute("position", new THREE.Float32BufferAttribute(observationPositions[focused].toArray(), 3));
        beam.geometry.setAttribute("position", new THREE.Float32BufferAttribute([...sites[Math.min(2, Math.floor(focused / 20))].toArray(), ...observationPositions[focused].toArray()], 3));
        focus.visible = beam.visible = true;
      } else focus.visible = beam.visible = false;
      invalidate();
    };

    let frame: number | null = null;
    let active = true;
    let inView = true;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let reduced = motion.matches;
    let clock = 0;
    let last = 0;
    const place = () => {
      // Both objects run towards the encounter, pause there, and start again.
      const angle = Math.min(0, -175 + 175 * (clock % 18) / 15);
      objectA.position.copy(trackA(angle));
      objectB.position.copy(trackB(angle, ORBIT_RADIUS + 0.16));
      pulse.material.opacity = angle > -12 ? 1 : 0.55;
    };
    const render = (time: number) => {
      frame = null;
      if (!active || !inView || document.hidden) return;
      const delta = last ? Math.min((time - last) / 1000, 0.05) : 0;
      last = time;
      const animate = !stateRef.current.paused && !reduced;
      if (animate) clock += delta;
      place();
      controls.update();
      renderer.render(scene, camera);
      if (animate) invalidate();
    };
    const invalidate = () => { if (active && inView && !document.hidden && frame === null) frame = requestAnimationFrame(render); };
    const cancel = () => { if (frame !== null) cancelAnimationFrame(frame); frame = null; last = 0; };
    apiRef.current = { refresh };
    clock = 9;
    refresh();

    const resize = () => {
      const width = host.clientWidth;
      const height = host.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      // Narrow screens widen the view instead of cropping the arc and the message rail.
      camera.zoom = Math.min(1, camera.aspect / 1.15);
      camera.updateProjectionMatrix();
      invalidate();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    const intersection = new IntersectionObserver(([entry]) => { inView = entry.isIntersecting; if (inView) invalidate(); else cancel(); }, { rootMargin: "100px" });
    intersection.observe(host);

    const raycaster = new THREE.Raycaster();
    const pick = (event: PointerEvent): GlobeTarget | null => {
      const rect = renderer.domElement.getBoundingClientRect();
      const pointer = new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
      raycaster.setFromCamera(pointer, camera);
      raycaster.params.Points.threshold = 0.16;
      const marker = raycaster.intersectObjects(messageMarkers)[0];
      if (marker) return { kind: "message", index: marker.object.userData.index as number };
      const hit = raycaster.intersectObject(observations)[0];
      return hit?.index != null ? { kind: "observation", id: hit.index } : null;
    };
    let down: { x: number; y: number } | null = null;
    const onMove = (event: PointerEvent) => {
      if (event.buttons) return;
      const found = pick(event);
      renderer.domElement.style.cursor = found ? "pointer" : "grab";
      stateRef.current.onHover(found ? { ...found, x: event.clientX, y: event.clientY } : null);
    };
    const onLeave = () => stateRef.current.onHover(null);
    const onDown = (event: PointerEvent) => { down = { x: event.clientX, y: event.clientY }; };
    const onUp = (event: PointerEvent) => {
      if (!down || Math.hypot(event.clientX - down.x, event.clientY - down.y) > 5) return;
      const found = pick(event);
      if (found?.kind === "message") stateRef.current.onSelectMessage(found.index);
    };
    const visibility = () => { if (document.hidden) cancel(); else invalidate(); };
    const motionChange = () => { reduced = motion.matches; invalidate(); };
    const contextLost = (event: Event) => { event.preventDefault(); cancel(); setFailed(true); };
    controls.addEventListener("change", invalidate);
    renderer.domElement.addEventListener("pointermove", onMove);
    renderer.domElement.addEventListener("pointerleave", onLeave);
    renderer.domElement.addEventListener("pointerdown", onDown);
    renderer.domElement.addEventListener("pointerup", onUp);
    renderer.domElement.addEventListener("webglcontextlost", contextLost);
    document.addEventListener("visibilitychange", visibility);
    motion.addEventListener("change", motionChange);
    resize();
    invalidate();

    const mapRequest = new AbortController();
    void fetch("/maps/land-110m.json", { signal: mapRequest.signal }).then(async (response) => {
      if (!response.ok) return;
      const topology = await response.json() as LandTopology;
      if (!active || mapRequest.signal.aborted) return;
      const refined = atlasTexture(decodeLand(topology));
      refined.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 4);
      earthMaterial.map = refined;
      earthMaterial.needsUpdate = true;
      surface.dispose();
      surface = refined;
      invalidate();
    }).catch(() => { /* The procedural continents remain if the local map fails. */ });

    return () => {
      active = false;
      mapRequest.abort();
      cancel();
      apiRef.current = null;
      observer.disconnect();
      intersection.disconnect();
      controls.removeEventListener("change", invalidate);
      controls.dispose();
      renderer.domElement.removeEventListener("pointermove", onMove);
      renderer.domElement.removeEventListener("pointerleave", onLeave);
      renderer.domElement.removeEventListener("pointerdown", onDown);
      renderer.domElement.removeEventListener("pointerup", onUp);
      renderer.domElement.removeEventListener("webglcontextlost", contextLost);
      document.removeEventListener("visibilitychange", visibility);
      motion.removeEventListener("change", motionChange);
      const textures = new Set<THREE.Texture>();
      const geometries = new Set<THREE.BufferGeometry>();
      const materials = new Set<THREE.Material>();
      scene.traverse((object) => {
        const drawable = object as THREE.Mesh;
        if (drawable.geometry) geometries.add(drawable.geometry);
        if (drawable.material) for (const material of Array.isArray(drawable.material) ? drawable.material : [drawable.material]) {
          materials.add(material);
          for (const value of Object.values(material)) if (value instanceof THREE.Texture) textures.add(value);
        }
      });
      textures.forEach((texture) => texture.dispose());
      geometries.forEach((geometry) => geometry.dispose());
      materials.forEach((material) => material.dispose());
      renderer.dispose();
      renderer.forceContextLoss();
      if (host.contains(renderer.domElement)) host.removeChild(renderer.domElement);
    };
  }, [availability, messageTimes]);

  return <div ref={hostRef} className="lineage-globe" style={{ width: "100%", height: "100%", position: "relative" }}>
    {failed && <div className="lineage-fallback" role="status"><strong>3D is unavailable in this browser.</strong><p>The observation windows, message controls and tables below carry the same information.</p></div>}
  </div>;
}

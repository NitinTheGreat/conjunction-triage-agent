"use client";

import { useEffect, useRef, useState } from "react";
import * as THREE from "three";
import { OrbitControls } from "three/examples/jsm/controls/OrbitControls.js";
import gsap from "gsap";
import type { ConjunctionEvent } from "@/lib/types";
import { decodeLand, type LandPolygon, type LandTopology } from "@/lib/land";

type PlanetSceneProps = {
  variant?: "hero" | "data";
  events?: ConjunctionEvent[];
  selectedId?: string | null;
  onSelect?: (event: ConjunctionEvent) => void;
  focusToken?: number;
  paused?: boolean;
  className?: string;
};

type SceneAPI = {
  update: (events: ConjunctionEvent[]) => void;
  select: (id: string | null) => void;
  reset: () => void;
  invalidate: () => void;
  stopTransition: () => void;
};

export const EARTH_RADIUS = 6.378137;
const RAMP = [new THREE.Color("#858c56"), new THREE.Color("#d1d58a"), new THREE.Color("#d49a58"), new THREE.Color("#d35c3d")];

function probabilityColor(event: ConjunctionEvent) {
  if (event.pc == null) return new THREE.Color("#b09b8a");
  if (event.pc_is_floored) return new THREE.Color("#8e9085");
  const amount = THREE.MathUtils.clamp((Math.log10(Math.max(event.pc, 1e-30)) + 10) / 6, 0, 1) * 3;
  const lower = Math.min(2, Math.floor(amount));
  return RAMP[lower].clone().lerp(RAMP[lower + 1], amount - lower);
}

function xyz(position: number[]) {
  return new THREE.Vector3(position[0] / 1000, position[2] / 1000, -position[1] / 1000);
}

export function markerTexture(ring = false) {
  const canvas = document.createElement("canvas");
  canvas.width = canvas.height = 64;
  const ctx = canvas.getContext("2d")!;
  if (ring) {
    ctx.strokeStyle = "white";
    ctx.lineWidth = 5;
    ctx.beginPath();
    ctx.arc(32, 32, 23, 0, Math.PI * 2);
    ctx.stroke();
  } else {
    const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 31);
    gradient.addColorStop(0, "rgba(255,255,255,1)");
    gradient.addColorStop(0.25, "rgba(255,255,255,.95)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 64, 64);
  }
  return new THREE.CanvasTexture(canvas);
}

/** Natural Earth coastlines plus decorative contour lines; all assets are bundled locally. */
export function atlasTexture(land?: LandPolygon[]) {
  const canvas = document.createElement("canvas");
  canvas.width = 2048;
  canvas.height = 1024;
  const ctx = canvas.getContext("2d")!;
  ctx.fillStyle = "#4c513b";
  ctx.fillRect(0, 0, 2048, 1024);
  const continents = [
    [[-168, 65], [-145, 72], [-122, 70], [-108, 78], [-83, 70], [-58, 52], [-66, 45], [-82, 25], [-98, 18], [-105, 23], [-119, 35], [-129, 52], [-155, 58]],
    [[-82, 12], [-66, 11], [-52, 3], [-35, -7], [-42, -24], [-53, -34], [-68, -55], [-75, -42], [-72, -17]],
    [[-17, 36], [7, 37], [23, 32], [35, 31], [43, 12], [51, 10], [41, -12], [32, -29], [20, -35], [12, -20], [9, 0], [-9, 5], [-17, 16]],
    [[-10, 36], [-8, 44], [5, 44], [6, 56], [21, 71], [39, 70], [55, 60], [84, 73], [117, 73], [139, 62], [177, 66], [162, 51], [144, 47], [134, 34], [119, 23], [109, 5], [99, 17], [82, 8], [68, 24], [50, 29], [38, 40], [28, 41], [21, 38]],
    [[112, -12], [131, -11], [139, -17], [145, -15], [154, -27], [146, -39], [131, -32], [115, -34], [112, -24]],
    [[-53, 60], [-43, 62], [-20, 76], [-28, 83], [-50, 82], [-62, 72]],
    [[46, -13], [51, -15], [47, -26], [43, -23]],
    [[130, 31], [140, 37], [144, 44], [142, 34]],
    [[166, -34], [178, -38], [172, -45], [167, -47]],
  ];
  const polygons = land ?? continents.map((polygon) => [polygon as [number, number][]]);
  const landPath = new Path2D();
  for (const polygon of polygons) for (const ring of polygon) {
    // Unwrap consecutive longitudes before drawing across the map's antimeridian.
    let previous = ring[0][0];
    const unwrapped = ring.map(([rawLongitude, latitude]): [number, number] => {
      let longitude = rawLongitude;
      while (longitude - previous > 180) longitude -= 360;
      while (longitude - previous < -180) longitude += 360;
      previous = longitude;
      return [longitude, latitude];
    });
    const first = unwrapped[0];
    const last = unwrapped[unwrapped.length - 1];
    // The Antarctic coastline circles the pole; close it at the map's southern edge.
    if (Math.abs(last[0] - first[0]) > 300 && unwrapped.every((point) => point[1] < -58)) unwrapped.push([last[0], -90], [first[0], -90]);
    for (const offset of [-360, 0, 360]) {
      unwrapped.forEach(([longitude, latitude], index) => {
        const x = (longitude + offset + 180) / 360 * 2048;
        const y = (90 - latitude) / 180 * 1024;
        if (index === 0) landPath.moveTo(x, y); else landPath.lineTo(x, y);
      });
      landPath.closePath();
    }
  }
  ctx.fillStyle = "#85845a";
  ctx.fill(landPath, "evenodd");
  ctx.strokeStyle = "#b1a676";
  ctx.lineWidth = 1;
  ctx.lineJoin = "round";
  ctx.stroke(landPath);
  ctx.save();
  ctx.clip(landPath, "evenodd");
  ctx.strokeStyle = "rgba(229,221,168,.12)";
  ctx.lineWidth = 0.8;
  for (let i = 0; i < 70; i++) {
    ctx.beginPath();
    for (let x = 0; x <= 2048; x += 12) {
      const y = i * 19 + Math.sin(x * 0.013 + i * 0.7) * 14 + Math.cos(x * 0.024) * 7;
      if (x === 0) ctx.moveTo(x, y); else ctx.lineTo(x, y);
    }
    ctx.stroke();
  }
  ctx.restore();
  let seed = 4261;
  for (let i = 0; i < 42000; i++) {
    seed = (seed * 16807) % 2147483647;
    const x = seed % 2048;
    seed = (seed * 16807) % 2147483647;
    ctx.fillStyle = i % 2 ? "rgba(225,220,181,.06)" : "rgba(12,19,10,.08)";
    ctx.fillRect(x, seed % 1024, 1.5, 1.5);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

export function latitudeLongitude(radius: number) {
  const points: number[] = [];
  const at = (lat: number, lon: number) => {
    const phi = THREE.MathUtils.degToRad(lat);
    const theta = THREE.MathUtils.degToRad(lon);
    return [radius * Math.cos(phi) * Math.cos(theta), radius * Math.sin(phi), radius * Math.cos(phi) * Math.sin(theta)];
  };
  for (let lat = -75; lat <= 75; lat += 15) for (let lon = 0; lon < 360; lon += 4) points.push(...at(lat, lon), ...at(lat, lon + 4));
  for (let lon = 0; lon < 360; lon += 15) for (let lat = -90; lat < 90; lat += 4) points.push(...at(lat, lon), ...at(lat + 4, lon));
  const geometry = new THREE.BufferGeometry();
  geometry.setAttribute("position", new THREE.Float32BufferAttribute(points, 3));
  return new THREE.LineSegments(geometry, new THREE.LineBasicMaterial({ color: "#c2bc8a", transparent: true, opacity: 0.14 }));
}

export default function PlanetScene({ variant = "hero", events = [], selectedId = null, onSelect, focusToken = 0, paused = false, className = "" }: PlanetSceneProps) {
  const hostRef = useRef<HTMLDivElement>(null);
  const sceneRef = useRef<SceneAPI | null>(null);
  const eventRef = useRef(events);
  const callbackRef = useRef(onSelect);
  const pausedRef = useRef(paused);
  const selectionRef = useRef(selectedId);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    eventRef.current = events;
    callbackRef.current = onSelect;
    pausedRef.current = paused;
    selectionRef.current = selectedId;
  }, [events, onSelect, paused, selectedId]);

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
    const isHero = variant === "hero";
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.55;
    renderer.setClearColor("#25271e", 0);
    renderer.domElement.setAttribute("aria-label", isHero ? "Interactive illustrative globe with animated satellite paths. Drag to rotate." : "Interactive three-dimensional benchmark conjunction geometry. Drag to rotate; use the encounter list to inspect data without a mouse.");
    renderer.domElement.setAttribute("role", "img");
    host.appendChild(renderer.domElement);

    const scene = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(isHero ? 38 : 42, 1, 0.1, 1500);
    const defaultPosition = isHero ? new THREE.Vector3(14, 8, 21) : new THREE.Vector3(16, 11, 18);
    camera.position.copy(defaultPosition);
    const controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.065;
    controls.enablePan = !isHero;
    controls.enableZoom = !isHero;
    controls.minDistance = EARTH_RADIUS * 1.15;
    controls.maxDistance = 300;
    controls.autoRotate = false;

    scene.add(new THREE.AmbientLight("#cdc49c", 0.68));
    const sun = new THREE.DirectionalLight("#ffedc2", 3.4);
    sun.position.set(-12, 11, 15);
    scene.add(sun);
    const rim = new THREE.DirectionalLight("#c8a766", 1.5);
    rim.position.set(13, -3, -12);
    scene.add(rim);
    const earthGroup = new THREE.Group();
    const earthGeometry = new THREE.SphereGeometry(EARTH_RADIUS, 96, 64);
    let surface = atlasTexture();
    surface.anisotropy = Math.min(renderer.capabilities.getMaxAnisotropy(), 4);
    const earthMaterial = new THREE.MeshStandardMaterial({ map: surface, roughness: 0.98, metalness: 0.08 });
    earthGroup.add(new THREE.Mesh(earthGeometry, earthMaterial));
    earthGroup.add(latitudeLongitude(EARTH_RADIUS * 1.003));
    earthGroup.rotation.z = isHero ? 0.23 : 0;
    earthGroup.rotation.y = isHero ? 0.25 : 0;
    scene.add(earthGroup);
    const atmosphere = new THREE.Mesh(new THREE.SphereGeometry(EARTH_RADIUS * 1.025, 64, 48), new THREE.ShaderMaterial({
      uniforms: { glowColor: { value: new THREE.Color("#beb772") } },
      vertexShader: "varying vec3 vNormal; varying vec3 vPosition; void main(){vNormal=normalize(normalMatrix*normal); vec4 mvPosition=modelViewMatrix*vec4(position,1.0);vPosition=-mvPosition.xyz;gl_Position=projectionMatrix*mvPosition;}",
      fragmentShader: "uniform vec3 glowColor;varying vec3 vNormal;varying vec3 vPosition;void main(){float intensity=pow(1.0-abs(dot(normalize(vNormal),normalize(vPosition))),3.8);gl_FragColor=vec4(glowColor,intensity*0.3);}",
      transparent: true, depthWrite: false, side: THREE.BackSide, blending: THREE.AdditiveBlending,
    }));
    scene.add(atmosphere);

    const orbiters: { marker: THREE.Mesh; angle: number; a: number; b: number; plane: THREE.Group; speed: number }[] = [];
    if (isHero) {
      [{ a: 9.4, b: 7.5, x: 0.4, z: 0.3, color: "#dedf9f", speed: 0.15 }, { a: 8.6, b: 8.2, x: 1.15, z: -0.52, color: "#c6875e", speed: -0.11 }].forEach((orbit, index) => {
        const plane = new THREE.Group();
        plane.rotation.x = orbit.x;
        plane.rotation.z = orbit.z;
        const coordinates = Array.from({ length: 321 }, (_, i) => new THREE.Vector3(Math.cos(i / 320 * Math.PI * 2) * orbit.a, 0, Math.sin(i / 320 * Math.PI * 2) * orbit.b));
        plane.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(coordinates), new THREE.LineBasicMaterial({ color: orbit.color, transparent: true, opacity: 0.5 })));
        const marker = new THREE.Mesh(new THREE.SphereGeometry(0.085, 12, 12), new THREE.MeshBasicMaterial({ color: orbit.color }));
        plane.add(marker);
        const halo = new THREE.Sprite(new THREE.SpriteMaterial({ map: markerTexture(), color: orbit.color, transparent: true, opacity: 0.5, depthWrite: false, blending: THREE.AdditiveBlending }));
        halo.scale.set(0.75, 0.75, 0.75);
        marker.add(halo);
        scene.add(plane);
        orbiters.push({ marker, angle: index ? 3.8 : 0.8, a: orbit.a, b: orbit.b, plane, speed: orbit.speed });
      });
      const specks: number[] = [];
      let seed = 913;
      const random = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
      for (let i = 0; i < 220; i++) {
        const r = 35 + random() * 40;
        const theta = random() * Math.PI * 2;
        const phi = Math.acos(2 * random() - 1);
        specks.push(r * Math.sin(phi) * Math.cos(theta), r * Math.cos(phi), r * Math.sin(phi) * Math.sin(theta));
      }
      const stars = new THREE.BufferGeometry();
      stars.setAttribute("position", new THREE.Float32BufferAttribute(specks, 3));
      scene.add(new THREE.Points(stars, new THREE.PointsMaterial({ color: "#d8d1b1", size: 1.3, sizeAttenuation: false, transparent: true, opacity: 0.48 })));
    }

    const pointGeometry = new THREE.BufferGeometry();
    const lineGeometry = new THREE.BufferGeometry();
    const ringGeometry = new THREE.BufferGeometry();
    const selectionGeometry = new THREE.BufferGeometry();
    const disc = markerTexture();
    const ringTexture = markerTexture(true);
    const cloud = new THREE.Points(pointGeometry, new THREE.PointsMaterial({ vertexColors: true, map: disc, size: 6.5, sizeAttenuation: false, transparent: true, depthWrite: false, alphaTest: 0.01 }));
    const links = new THREE.LineSegments(lineGeometry, new THREE.LineBasicMaterial({ vertexColors: true, transparent: true, opacity: 0.5 }));
    const rings = new THREE.Points(ringGeometry, new THREE.PointsMaterial({ map: ringTexture, color: "#cc985c", size: 10, sizeAttenuation: false, transparent: true, opacity: 0.7, depthWrite: false }));
    const selected = new THREE.Points(selectionGeometry, new THREE.PointsMaterial({ map: ringTexture, color: "#f8f4c4", size: 25, sizeAttenuation: false, transparent: true, depthWrite: false, depthTest: false }));
    selected.renderOrder = 10;
    selected.visible = false;
    scene.add(cloud, links, rings, selected);

    let frame: number | null = null;
    let active = true;
    let inView = true;
    const motion = window.matchMedia("(prefers-reduced-motion: reduce)");
    let reduced = motion.matches;
    let lastTime = 0;
    let lastSelectedId: string | null = null;
    let cameraTween: gsap.core.Tween | null = null;
    let pointerDown: { x: number; y: number } | null = null;
    const render = (time: number) => {
      frame = null;
      if (!active || !inView || document.hidden) return;
      const delta = lastTime ? Math.min((time - lastTime) / 1000, 0.05) : 0;
      lastTime = time;
      if (isHero && !pausedRef.current && !reduced) earthGroup.rotation.y += delta * 0.045;
      for (const orbiter of orbiters) {
        if (!pausedRef.current && !reduced) orbiter.angle += delta * orbiter.speed;
        orbiter.marker.position.set(Math.cos(orbiter.angle) * orbiter.a, 0, Math.sin(orbiter.angle) * orbiter.b);
      }
      controls.update();
      renderer.render(scene, camera);
      if (isHero && !pausedRef.current && !reduced) invalidate();
    };
    const invalidate = () => { if (active && inView && !document.hidden && frame === null) frame = requestAnimationFrame(render); };
    const cancel = () => { if (frame !== null) cancelAnimationFrame(frame); frame = null; lastTime = 0; };
    const select = (id: string | null) => {
      const event = eventRef.current.find((item) => item.event_id === id);
      selected.visible = Boolean(event);
      if (event) {
        selectionGeometry.setAttribute("position", new THREE.Float32BufferAttribute(event.objects.flatMap((object) => xyz(object.position_km).toArray()), 3));
        selectionGeometry.computeBoundingSphere();
        if (id !== lastSelectedId && !isHero) {
          const target = xyz(event.objects[0].position_km);
          target.normalize().multiplyScalar(Math.max(23, xyz(event.objects[0].position_km).length() * 1.65));
          cameraTween?.kill();
          controls.target.set(0, 0, 0);
          if (reduced || pausedRef.current) { camera.position.copy(target); controls.update(); }
          else cameraTween = gsap.to(camera.position, { x: target.x, y: target.y, z: target.z, duration: 1.15, ease: "power3.inOut", onUpdate: () => { controls.update(); invalidate(); } });
        }
      }
      lastSelectedId = id;
      invalidate();
    };
    const update = (data: ConjunctionEvent[]) => {
      const positions: number[] = [];
      const colors: number[] = [];
      const ringPositions: number[] = [];
      for (const event of data) {
        const color = probabilityColor(event);
        for (const object of event.objects) {
          const point = xyz(object.position_km).toArray();
          positions.push(...point);
          colors.push(color.r, color.g, color.b);
          if (event.dilution === 1) ringPositions.push(...point);
        }
      }
      pointGeometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      pointGeometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
      pointGeometry.computeBoundingSphere();
      lineGeometry.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
      lineGeometry.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
      lineGeometry.computeBoundingSphere();
      ringGeometry.setAttribute("position", new THREE.Float32BufferAttribute(ringPositions, 3));
      ringGeometry.computeBoundingSphere();
      select(selectionRef.current);
      invalidate();
    };
    const reset = () => { cameraTween?.kill(); camera.position.copy(defaultPosition); controls.target.set(0, 0, 0); controls.update(); invalidate(); };
    sceneRef.current = { update, select, reset, invalidate, stopTransition: () => { cameraTween?.kill(); } };
    update(eventRef.current);

    const resize = () => {
      const width = host.clientWidth;
      const height = host.clientHeight;
      if (!width || !height) return;
      renderer.setSize(width, height);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      invalidate();
    };
    const observer = new ResizeObserver(resize);
    observer.observe(host);
    const intersection = new IntersectionObserver(([entry]) => { inView = entry.isIntersecting; if (inView) invalidate(); else cancel(); }, { rootMargin: "100px" });
    intersection.observe(host);
    const visibility = () => { if (document.hidden) cancel(); else invalidate(); };
    const motionChange = () => { reduced = motion.matches; if (reduced) cameraTween?.kill(); invalidate(); };
    const onPointerDown = (event: PointerEvent) => { cameraTween?.kill(); pointerDown = { x: event.clientX, y: event.clientY }; invalidate(); };
    const onPointerUp = (event: PointerEvent) => {
      if (isHero || !pointerDown || Math.hypot(event.clientX - pointerDown.x, event.clientY - pointerDown.y) > 5) return;
      const rect = renderer.domElement.getBoundingClientRect();
      const pointer = new THREE.Vector2((event.clientX - rect.left) / rect.width * 2 - 1, -(event.clientY - rect.top) / rect.height * 2 + 1);
      const raycaster = new THREE.Raycaster();
      raycaster.params.Points.threshold = camera.position.distanceTo(controls.target) * 0.009;
      raycaster.setFromCamera(pointer, camera);
      const hit = raycaster.intersectObject(cloud)[0];
      if (hit?.index != null) {
        const item = eventRef.current[Math.floor(hit.index / 2)];
        if (item) callbackRef.current?.(item);
      }
    };
    const contextLost = (event: Event) => { event.preventDefault(); cancel(); setFailed(true); };
    controls.addEventListener("change", invalidate);
    renderer.domElement.addEventListener("pointerdown", onPointerDown);
    renderer.domElement.addEventListener("pointerup", onPointerUp);
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
    }).catch(() => { /* The procedural illustration remains available if the local map fails. */ });

    return () => {
      active = false;
      mapRequest.abort();
      cameraTween?.kill();
      cancel();
      sceneRef.current = null;
      observer.disconnect();
      intersection.disconnect();
      controls.removeEventListener("change", invalidate);
      controls.dispose();
      renderer.domElement.removeEventListener("pointerdown", onPointerDown);
      renderer.domElement.removeEventListener("pointerup", onPointerUp);
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
  }, [variant]);

  useEffect(() => { sceneRef.current?.update(events); }, [events]);
  useEffect(() => { sceneRef.current?.select(selectedId); }, [selectedId]);
  useEffect(() => { sceneRef.current?.reset(); }, [focusToken]);
  useEffect(() => { if (paused) sceneRef.current?.stopTransition(); sceneRef.current?.invalidate(); }, [paused]);

  return <div ref={hostRef} className={`planet-scene ${className}`} style={{ width: "100%", height: "100%", position: "relative" }}>
    {failed && <div className="planet-fallback" role="status" style={{ position: "absolute", inset: 0, display: "grid", placeContent: "center", textAlign: "center", color: "#e8e4da", padding: "2rem", background: "radial-gradient(circle at 45% 40%, #606447 0, #333628 35%, #25271e 65%)" }}><span style={{ fontSize: "4rem", color: "#d0d68b" }}>◎</span><strong>Geometry beyond the canvas.</strong><p>{variant === "hero" ? "The illustrated globe is unavailable in this browser. Enter the observatory to explore the encounter data." : "3D is unavailable in this browser. The encounter list, filters and measurements remain available below."}</p></div>}
  </div>;
}

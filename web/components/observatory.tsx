"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import { ArrowDown, ArrowRight, ArrowUpRight, Crosshair, Globe2, Layers3, RotateCcw, SlidersHorizontal } from "lucide-react";
import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import type { ConjunctionEvent, OrbitalObject } from "@/lib/types";
import { useMotion } from "@/lib/motion";
import DistributionAtlas from "@/components/distributions";
import "./observatory.css";

const PlanetScene = dynamic(() => import("@/components/planet-scene"), { ssr: false, loading: () => <div className="observatory-canvas-loading"><span className="observatory-loader" /><span>Preparing the orbital atlas</span></div> });
gsap.registerPlugin(useGSAP);
const initialFilters = { source: "all", altitude: "all", dilution: "all", minPc: -11, maxMiss: 70, censored: true, missing: true };
const number = (value: number | null | undefined, digits = 3) => value == null || !Number.isFinite(value) ? "—" : Math.abs(value) > 0 && Math.abs(value) < 0.001 ? value.toExponential(2) : value.toLocaleString("en-US", { maximumFractionDigits: digits });
const sourceName = (source: string) => source === "TRACSS_SPHERICAL" ? "Spherical" : "SFSH";
const probability = (event: ConjunctionEvent) => event.pc == null ? "Unavailable" : event.pc_is_floored ? "≤ 1 × 10⁻¹⁰" : event.pc.toExponential(3);

function ObjectDetails({ object, index }: { object: OrbitalObject; index: number }) {
  return <details className="observatory-object">
    <summary><span className="observatory-object-index">0{index + 1}</span><span>Object {object.catalog_id}<small>Altitude {number(object.altitude_km, 1)} km</small></span><span className="observatory-expand">+</span></summary>
    <div className="observatory-object-content">
      <p>State in J2000 / Earth-centered inertial coordinates at the encounter’s closest approach.</p>
      <dl className="observatory-kv">
        <dt>Position X / Y / Z <small>km</small></dt><dd>{object.position_km.map((value) => number(value, 3)).join(" / ")}</dd>
        <dt>Velocity X / Y / Z <small>km/s</small></dt><dd>{object.velocity_kms.map((value) => number(value, 4)).join(" / ")}</dd>
        <dt>Speed</dt><dd>{number(Math.hypot(...object.velocity_kms))} km/s</dd>
        <dt>Hard-body radius</dt><dd>{number(object.hbr_m, 4)} m</dd>
        <dt>Largest covariance eigenvalue</dt><dd>{number(object.cov_max_eigenvalue_km2)} km²</dd>
        <dt>Largest 1σ position uncertainty</dt><dd>{object.cov_max_eigenvalue_km2 == null || object.cov_max_eigenvalue_km2 < 0 ? "Unavailable" : `${number(Math.sqrt(object.cov_max_eigenvalue_km2))} km`}</dd>
        <dt>Met screening criteria</dt><dd>{object.met_criteria ? "Yes" : "No"}</dd>
      </dl>
      <p>Hard-body radius describes physical size. Covariance describes uncertainty in the estimated position. They measure different things.</p>
    </div>
  </details>;
}

function Inspector({ event }: { event: ConjunctionEvent | null }) {
  if (!event) return <aside className="observatory-inspector observatory-inspector-empty">
    <span className="eyebrow">Encounter inspector</span>
    <Crosshair size={42} strokeWidth={1} />
    <h2>Every point has<br />a story.</h2>
    <p>Select a point on the globe, inspect a featured encounter, or choose any record in the list below.</p>
    <div className="observatory-mini-guide"><span>01</span><p><strong>Distance</strong>How closely are the objects predicted to pass?</p></div>
    <div className="observatory-mini-guide"><span>02</span><p><strong>Probability</strong>How does uncertainty change the estimate?</p></div>
    <div className="observatory-mini-guide"><span>03</span><p><strong>Context</strong>Is the probability a value, a bound, or missing?</p></div>
  </aside>;

  return <aside className="observatory-inspector" aria-live="polite" aria-atomic="false">
    <div className="observatory-inspector-top"><span className="eyebrow">Selected encounter</span><span className="tag">{sourceName(event.source)}</span></div>
    <h2>How close<br />is close?</h2>
    <div className="observatory-miss">{number(event.miss_distance_km, 4)}<span>km</span></div>
    <p className="observatory-small">Predicted separation at closest approach. Pale rings identify the selected pair; marker sizes are illustrative.</p>
    <dl className="observatory-kv observatory-primary-kv">
      <dt>Time of closest approach <small>UTC</small></dt><dd>{event.tca.replace("T", " ").replace("Z", "")}</dd>
      <dt>Relative speed</dt><dd>{number(event.relative_speed_kms, 4)} km/s</dd>
      <dt>Mahalanobis distance</dt><dd>{number(event.mahalanobis_distance, 4)}</dd>
    </dl>
    <p className="observatory-small">Mahalanobis distance measures separation relative to the combined uncertainty. It has no unit.</p>
    <div className={`observatory-probability ${event.pc == null ? "is-missing" : event.pc_is_floored ? "is-censored" : ""}`}>
      <span className="eyebrow">Collision probability · P<sub>c</sub></span><strong>{probability(event)}</strong>
      <p>{event.pc == null ? "The source does not report a probability. An invalid covariance is one possible cause; missing does not mean zero." : event.pc_is_floored ? "An upper bound at the inferred reporting floor. Treat this as censored information, not an exact probability." : `This calculated value is ${(event.pc ?? 0) >= 1e-4 ? "at or above" : "below"} the 10⁻⁴ reference used in this view. It depends on geometry, physical size and the uncertainty model.`}</p>
    </div>
    <div className="observatory-dilution"><span className={`observatory-status-dot ${event.dilution === 1 ? "is-diluted" : ""}`} /><div><strong>{event.dilution === 1 ? "Probability dilution flagged" : event.dilution === 0 ? "No dilution flag" : "Dilution status unavailable"}</strong><p>{event.dilution === 1 ? "Spreading uncertainty further can lower the calculated probability in this regime. A small number alone does not establish a well-known separation." : event.dilution === 0 ? "The source does not flag dilution. This does not establish that the covariance is accurate." : "The source supplies no dilution classification for this record."}</p></div></div>
    <div className="observatory-object-heading"><span className="eyebrow">The two objects</span><ArrowDown size={14} /></div>
    {event.objects.map((object, index) => <ObjectDetails key={`${object.catalog_id}-${index}`} object={object} index={index} />)}
    <details className="observatory-record"><summary>Record & sampling details <span>+</span></summary><dl className="observatory-kv"><dt>Event identifier</dt><dd>{event.event_id}</dd><dt>Conjunction identifier</dt><dd>{event.conj_id}</dd><dt>Answer key</dt><dd>{sourceName(event.source)}</dd><dt>Sampling stratum</dt><dd>{event.stratum}</dd></dl><p className="observatory-small">The stratum combines source, probability class and dilution status to keep the display sample varied.</p></details>
  </aside>;
}

export default function Observatory() {
  const rootRef = useRef<HTMLElement>(null);
  const { enabled } = useMotion();
  const [tab, setTab] = useState<"orbital" | "distributions">("orbital");
  const [events, setEvents] = useState<ConjunctionEvent[]>([]);
  const [loadError, setLoadError] = useState("");
  const [loading, setLoading] = useState(true);
  const [retry, setRetry] = useState(0);
  const [filters, setFilters] = useState(initialFilters);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [focusToken, setFocusToken] = useState(0);
  const [listPage, setListPage] = useState(0);

  useGSAP(() => {
    if (!enabled) return;
    gsap.timeline({ defaults: { ease: "power3.out" } })
      .from(".observatory-page-top .eyebrow", { y: 10, autoAlpha: 0, duration: 0.6 }, 0)
      .from(".observatory-page-top .page-title", { y: 30, autoAlpha: 0, duration: 0.9 }, 0.08)
      .from(".observatory-intro", { y: 20, autoAlpha: 0, duration: 0.8 }, 0.22)
      .from(".observatory-tabs-row, .observatory-filter-panel", { y: 18, autoAlpha: 0, duration: 0.7, stagger: 0.08 }, 0.28)
      .from(".observatory-stage", { y: 24, autoAlpha: 0, duration: 1 }, 0.4);
  }, { scope: rootRef, dependencies: [enabled], revertOnUpdate: true });

  useGSAP(() => {
    if (!enabled || !selectedId) return;
    gsap.from(".observatory-inspector", { y: 12, autoAlpha: 0.4, duration: 0.45, ease: "power2.out", clearProps: "all" });
  }, { scope: rootRef, dependencies: [selectedId, enabled], revertOnUpdate: true });

  useEffect(() => {
    const controller = new AbortController();
    async function load() {
      setLoading(true);
      setLoadError("");
      try {
        const response = await fetch("/data/events.json", { signal: controller.signal });
        if (!response.ok) throw new Error(`The saved geometry could not be loaded (HTTP ${response.status}).`);
        const data = await response.json() as ConjunctionEvent[];
        if (!Array.isArray(data)) throw new Error("The saved geometry has an unexpected format.");
        setEvents(data);
      } catch (error) {
        if (!controller.signal.aborted) setLoadError(error instanceof Error ? error.message : "The geometry could not be loaded.");
      } finally { if (!controller.signal.aborted) setLoading(false); }
    }
    void load();
    return () => controller.abort();
  }, [retry]);

  const visible = useMemo(() => events.filter((event) => {
    if (filters.source !== "all" && event.source !== filters.source) return false;
    const altitude = event.objects[0].altitude_km;
    if (filters.altitude === "leo" && altitude >= 2000) return false;
    if (filters.altitude === "meo" && (altitude < 2000 || altitude >= 35000)) return false;
    if (filters.altitude === "geo" && altitude < 35000) return false;
    if (filters.dilution !== "all" && event.dilution !== Number(filters.dilution)) return false;
    if (event.miss_distance_km > filters.maxMiss) return false;
    if (event.pc == null) return filters.missing;
    if (event.pc_is_floored) return filters.censored;
    return filters.minPc === -11 || Math.log10(Math.max(event.pc, 1e-30)) >= filters.minPc;
  }), [events, filters]);
  const selected = useMemo(() => visible.find((event) => event.event_id === selectedId) ?? null, [visible, selectedId]);
  const pageCount = Math.ceil(visible.length / 8);
  const currentPage = Math.min(listPage, Math.max(0, pageCount - 1));
  const displayed = visible.slice(currentPage * 8, currentPage * 8 + 8);
  const featured = useMemo(() => [...visible].filter((event) => event.pc != null && !event.pc_is_floored).sort((a, b) => (b.pc ?? 0) - (a.pc ?? 0))[0] ?? visible[0], [visible]);
  const updateFilter = <K extends keyof typeof initialFilters>(key: K, value: typeof initialFilters[K]) => { setFilters((current) => ({ ...current, [key]: value })); setListPage(0); };
  const nextEvent = () => { const index = visible.findIndex((event) => event.event_id === selectedId); setSelectedId(visible[(index + 1) % visible.length]?.event_id ?? null); };

  return <main ref={rootRef} className="page-shell observatory-page">
    <div className="observatory-page-top"><div><span className="eyebrow">01 / The observatory</span><h1 className="page-title">A little distance.<br /><em>A lot of uncertainty.</em></h1></div><div className="observatory-intro"><p className="lede">Two objects. One close approach. Explore the geometry, then look beyond the number that calls it safe.</p><span className="observatory-dataset-label"><span />TraCSS benchmark · January 2025 snapshot</span></div></div>
    <div className="observatory-tabs-row"><div className="tab-switch" role="tablist" aria-label="Observatory workspace"><button type="button" role="tab" id="orbital-tab" aria-selected={tab === "orbital"} aria-controls="orbital-panel" onClick={() => setTab("orbital")} className={tab === "orbital" ? "active" : ""}><Globe2 size={16} />Orbital view</button><button type="button" role="tab" id="distributions-tab" aria-selected={tab === "distributions"} aria-controls="distributions-panel" onClick={() => setTab("distributions")} className={tab === "distributions" ? "active" : ""}><Layers3 size={16} />Distributions</button></div><span className="observatory-snapshot">Historical geometry. Each pair at its own closest approach.</span></div>

    <section id="orbital-panel" role="tabpanel" aria-labelledby="orbital-tab" hidden={tab !== "orbital"}>
      <div className="observatory-filter-panel">
        <div className="observatory-filter-title"><SlidersHorizontal size={16} /><span>Shape the view</span><button type="button" onClick={() => { setFilters(initialFilters); setListPage(0); }}><RotateCcw size={13} />Reset filters</button></div>
        <div className="observatory-filter-grid">
          <label className="field"><span>Benchmark source</span><select aria-label="Benchmark source" value={filters.source} onChange={(event) => updateFilter("source", event.target.value)}><option value="all">Both answer keys</option><option value="TRACSS_SPHERICAL">Spherical · 0.5 m radius</option><option value="TRACSS_SFSH">SFSH · object-specific radii</option></select></label>
          <label className="field"><span>Altitude of first object</span><select aria-label="Altitude of first object" value={filters.altitude} onChange={(event) => updateFilter("altitude", event.target.value)}><option value="all">All orbital regions</option><option value="leo">LEO · below 2,000 km</option><option value="meo">MEO · 2,000–35,000 km</option><option value="geo">GEO+ · 35,000 km or more</option></select></label>
          <label className="field"><span>Probability dilution</span><select aria-label="Probability dilution" value={filters.dilution} onChange={(event) => updateFilter("dilution", event.target.value)}><option value="all">All classifications</option><option value="0">No flag · 0</option><option value="1">Dilution flagged · 1</option></select></label>
          <label className="field observatory-range"><span><span>Minimum uncensored P<sub>c</sub></span><b className="mono">{filters.minPc === -11 ? "Any" : <>10<sup>{filters.minPc}</sup></>}</b></span><input aria-label="Minimum uncensored collision probability" type="range" min="-11" max="-3" step="0.5" value={filters.minPc} onChange={(event) => updateFilter("minPc", Number(event.target.value))} /><small>Bounds and missing values use the toggles below.</small></label>
          <label className="field observatory-range"><span>Maximum miss distance<b className="mono">{filters.maxMiss} km</b></span><input aria-label="Maximum miss distance in kilometers" type="range" min="0" max="70" step="0.5" value={filters.maxMiss} onChange={(event) => updateFilter("maxMiss", Number(event.target.value))} /><small>Predicted separation at closest approach.</small></label>
        </div>
        <div className="observatory-filter-bottom"><div><label><input type="checkbox" checked={filters.censored} onChange={(event) => updateFilter("censored", event.target.checked)} />Include censored probabilities</label><label><input type="checkbox" checked={filters.missing} onChange={(event) => updateFilter("missing", event.target.checked)} />Include missing probabilities</label></div><span><strong>{visible.length.toLocaleString()}</strong> of {events.length.toLocaleString()} sampled encounters</span></div>
      </div>

      {loadError && <div className="notice" role="alert"><strong>Geometry is temporarily unavailable.</strong><p>{loadError}</p><button className="button button-outline" type="button" onClick={() => setRetry((value) => value + 1)}>Retry loading</button></div>}

      <div className="observatory-layout">
        <div className="observatory-main-column">
          <div className="observatory-stage">
            <div className="observatory-stage-top"><div><span className="eyebrow">Earth-centered / J2000</span><h2>Close approaches,<br />in perspective.</h2></div><span className="observatory-stage-count"><b>{visible.length.toLocaleString()}</b><small>encounters in view</small></span></div>
            <div className="observatory-canvas"><PlanetScene variant="data" events={visible} selectedId={selected?.event_id} onSelect={(event) => setSelectedId(event.event_id)} focusToken={focusToken} paused={!enabled} />{loading && <div className="observatory-canvas-loading"><span className="observatory-loader" /><span>Loading the benchmark sample</span></div>}{!loading && !loadError && visible.length === 0 && <div className="observatory-empty-canvas"><strong>No encounters match.</strong><span>Widen a filter or reset the view to explore again.</span></div>}</div>
            <div className="observatory-stage-bottom"><span>Drag to rotate · Scroll to zoom · Right-drag to pan</span><button type="button" onClick={() => setFocusToken((value) => value + 1)} aria-label="Reset camera"><RotateCcw size={14} />Reset camera</button></div>
            <div className="observatory-stage-legend"><div><span className="observatory-color-ramp" /><span>10⁻¹⁰ <i>Calculated P<sub>c</sub></i> ≥ 10⁻⁴</span></div><span><i className="legend-dot censored" />Censored</span><span><i className="legend-dot missing" />Unavailable</span><span><i className="legend-ring" />Dilution</span></div>
          </div>

          <div className="observatory-explore-bar"><p><Crosshair size={17} />Start with an encounter.</p><button className="button button-dark" type="button" disabled={!featured} onClick={() => featured && setSelectedId(featured.event_id)}><span>{featured?.pc != null && !featured.pc_is_floored ? <>Inspect highest P<sub>c</sub></> : "Inspect an example"}</span><ArrowUpRight size={15} /></button><button className="button button-outline" type="button" disabled={!visible.length} onClick={nextEvent}>Next encounter<ArrowRight size={15} /></button></div>

          <div className="observatory-encounters">
            <div className="observatory-list-heading"><div><span className="eyebrow">The encounter index</span><h2>Every record, within reach.</h2></div><span className="mono">{currentPage * 8 + (visible.length ? 1 : 0)}–{Math.min((currentPage + 1) * 8, visible.length)} / {visible.length}</span></div>
            <label className="field observatory-picker"><span>Jump to any filtered encounter</span><select aria-label="Jump to any filtered encounter" value={selected?.event_id ?? ""} onChange={(event) => setSelectedId(event.target.value || null)}><option value="">Choose a record…</option>{visible.map((event) => <option value={event.event_id} key={event.event_id}>{event.objects.map((object) => object.catalog_id).join(" ↔ ")} · {number(event.miss_distance_km, 2)} km · {sourceName(event.source)} · {event.conj_id}</option>)}</select></label>
            <div className="table-wrap"><table className="observatory-table"><thead><tr><th>Object pair</th><th>Miss distance</th><th>P<sub>c</sub></th><th><span className="observatory-sr-only">Inspect</span></th></tr></thead><tbody>{displayed.map((event) => <tr key={event.event_id} className={event.event_id === selected?.event_id ? "is-selected" : ""}><td><button type="button" onClick={() => setSelectedId(event.event_id)}>{event.objects[0].catalog_id}<span>↔</span>{event.objects[1].catalog_id}<small>{sourceName(event.source)}</small></button></td><td>{number(event.miss_distance_km, 3)}<small> km</small></td><td>{probability(event)}</td><td><button className="observatory-inspect-arrow" type="button" onClick={() => setSelectedId(event.event_id)} aria-label={`Inspect encounter ${event.conj_id}`}><ArrowUpRight size={17} /></button></td></tr>)}</tbody></table></div>
            {!visible.length && <p className="observatory-list-empty">{loading ? "Loading encounters…" : "No records match the current filters."}</p>}
            <div className="observatory-pagination"><button type="button" disabled={currentPage === 0} onClick={() => setListPage(currentPage - 1)}>← Previous</button><span>Page {pageCount ? currentPage + 1 : 0} of {pageCount}</span><button type="button" disabled={currentPage + 1 >= pageCount} onClick={() => setListPage(currentPage + 1)}>Next →</button></div>
          </div>

          <details className="observatory-reading-guide"><summary><span>Read the scene, without reading too much into it.</span><span>+</span></summary><div className="observatory-guide-grid"><div><span>01 / Geometry</span><p>Each pair is drawn at its own time of closest approach between January 1 and 8, 2025. This is a collection of historical snapshots, not a live view of everything sharing the sky.</p></div><div><span>02 / Representation</span><p>Positions preserve their relative scale. Dots, rings and the stylized Earth surface aid reading; they do not show physical object sizes, uncertainty ellipses or geographic ground tracks.</p></div><div><span>03 / Sample & population</span><p>The 2,000 displayed encounters are a stratified sample. Distribution charts separately identify full-population counts so rare cases in this view do not imply their population frequency.</p></div><div><span>04 / Research context</span><p>TraCSS uses real object states alongside synthetic edge cases. This is benchmark geometry for evaluating methods. A probability estimate does not establish operational safety.</p></div></div></details>
        </div>
        <Inspector event={selected} />
      </div>
      <div className="observatory-next-chapter"><div><span className="eyebrow">From position to probability</span><h2>The distance is only<br />the beginning.</h2><p>Explore how object sizes and position uncertainty enter the collision-probability calculation.</p></div><Link href="/laboratory" className="button button-dark">Enter the calculation lab<ArrowUpRight size={17} /></Link></div>
    </section>
    <section id="distributions-panel" role="tabpanel" aria-labelledby="distributions-tab" hidden={tab !== "distributions"}><DistributionAtlas /></section>
  </main>;
}
